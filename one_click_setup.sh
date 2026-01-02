#!/usr/bin/env bash
set -euo pipefail

# Single entry point for provisioning the security sandbox from a clean host.
# Steps:
#   1. Verify required CLI tools exist on the controller machine.
#   2. Create/activate a Python virtual environment in .venv.
#   3. Install Python dependencies (Ansible & cryptography).
#   4. Generate SSH key pairs defined in config.json.
#   5. Update the attacker security-group ingress rule with the current client IP.
#   6. Run Terraform apply and kick off Ansible playbooks via deploy.py.

# Allow callers to override the interpreter (e.g., PYTHON_BIN=python3.11 ./one_click_setup.sh)
PYTHON_BIN=${PYTHON_BIN:-python3}
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# If a .env file exists in the repo root, load it and export its variables so
# subsequent commands (Terraform, AWS CLI, etc.) see them. This mirrors the
# behaviour of `deploy.py` which also loads a .env when present.
if [[ -f "$ROOT_DIR/.env" ]]; then
  echo "[INFO] Loading environment variables from .env"
  # shellcheck disable=SC1090
  set -a
  . "$ROOT_DIR/.env"
  set +a
  # Check whether the .env file actually defines AWS credentials; warn if it doesn't.
  if ! grep -Eq '^\s*(AWS_PROFILE|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY)\s*=' "$ROOT_DIR/.env"; then
    echo "[WARN] .env exists but does not define AWS_PROFILE or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY."
    echo "       Terraform will need credentials from another source (environment, ~/.aws/credentials, or instance role)."
  else
    # If it contains some AWS vars, ensure it's not missing a pair (ACCESS_KEY without SECRET, etc.)
    has_profile=false
    has_access=false
    has_secret=false
    if grep -Eq '^\s*AWS_PROFILE\s*=' "$ROOT_DIR/.env"; then has_profile=true; fi
    if grep -Eq '^\s*AWS_ACCESS_KEY_ID\s*=' "$ROOT_DIR/.env"; then has_access=true; fi
    if grep -Eq '^\s*AWS_SECRET_ACCESS_KEY\s*=' "$ROOT_DIR/.env"; then has_secret=true; fi
    if [[ "$has_profile" = false && ( "$has_access" = true && "$has_secret" = false ) ]]; then
      echo "[WARN] .env defines AWS_ACCESS_KEY_ID but not AWS_SECRET_ACCESS_KEY; credentials may be incomplete."
    fi
    if [[ "$has_profile" = false && ( "$has_access" = false && "$has_secret" = true ) ]]; then
      echo "[WARN] .env defines AWS_SECRET_ACCESS_KEY but not AWS_ACCESS_KEY_ID; credentials may be incomplete."
    fi
  fi
else
  echo "[INFO] No .env file found at $ROOT_DIR; continuing without it."
fi

require_cmd() {
  local cmd="$1"
  local install_hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[ERROR] Required command '$cmd' not found. $install_hint" >&2
    exit 1
  fi
}

require_cmd "$PYTHON_BIN" "Install a compatible Python interpreter (set PYTHON_BIN to override, e.g., python3.11)."
require_cmd terraform "Install Terraform from https://developer.hashicorp.com/terraform/install"
require_cmd ssh "Install OpenSSH client for SSH/Ansible connectivity."

if [[ -z "${AWS_PROFILE:-}" && ( -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ) ]]; then
  cat >&2 <<'WARN'
[WARN] No AWS credentials detected (AWS_PROFILE or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY).
       Terraform commands will fail unless credentials are available via another mechanism (e.g., ~/.aws/credentials or instance profile).
WARN
fi

# Verify Python version supports Ansible (>=3.10 required for ansible 9.x).
PY_VERSION=$($PYTHON_BIN -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PY_MAJOR=${PY_VERSION%.*}
PY_MINOR=${PY_VERSION#*.}
if (( PY_MAJOR < 3 )) || (( PY_MAJOR == 3 && PY_MINOR < 10 )); then
  echo "[ERROR] Python $PY_VERSION detected via $PYTHON_BIN; ansible>=9.0.0 requires Python 3.10+." >&2
  echo "        Install Python 3.10+ (e.g., python3.11) and re-run as PYTHON_BIN=python3.11 ./one_click_setup.sh" >&2
  exit 1
fi

VENV_DIR="$ROOT_DIR/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
  echo "[INFO] Creating Python virtual environment at $VENV_DIR using $PYTHON_BIN"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

"$PYTHON_BIN" -m pip install --upgrade pip >/dev/null
"$PYTHON_BIN" -m pip install --pre -r requirements.txt

# ansible-playbook lives in the venv after pip install; fail fast if it didn't land.
require_cmd ansible-playbook "Run pip install -r requirements.txt to install Ansible in the virtualenv."

echo "[INFO] Generating SSH keys (if missing)..."
"$PYTHON_BIN" key_generation.py

# Ensure Terraform plugins are initialized before any apply/destroy calls.
echo "[INFO] Initializing Terraform providers..."
pushd aws_architecture >/dev/null
terraform init -upgrade -input=false >/dev/null
popd >/dev/null

echo "[INFO] Syncing SSH client IP with Terraform security group..."
"$PYTHON_BIN" deploy.py --update-ip auto


echo "[INFO] Running Terraform Configuration + Ansible playbooks..."
"$PYTHON_BIN" deploy.py --apply "$@"

echo "[SUCCESS] Security sandbox provisioning complete."
