import os
import subprocess
import sys
import shutil
from pathlib import Path

def load_env(env_path: Path):
    """Load .env variables into current environment (temporary)."""
    if not env_path.exists():
        print(f".env file not found at {env_path}")
        return
    print(f"Loading environment variables from {env_path}")
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, _, value = line.strip().partition("=")
                os.environ[key.strip()] = value.strip()


def ensure_installed(cmd, install_instructions):
    """Check if a command is available; print instructions if not."""
    if shutil.which(cmd):
        print(f"✅ {cmd} is already installed.")
        return True

    print(f"{cmd} is not installed.")
    print(f"{install_instructions}")
    return False


def run_command(cmd, cwd=None, check=True):
    """Run a system command with optional working directory."""
    print(f"\nRunning: {' '.join(cmd)} (in {cwd or os.getcwd()})")
    subprocess.run(cmd, cwd=cwd, check=check)


def main():
    # Step 1. Load environment variables
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / ".env"
    load_env(env_path)
    os.environ["TF_VAR_availability_zone"] = os.environ.get("AWS_DEFAULT_REGION", "us-east-1a")
    # Step 2. Check for Terraform & Ansible
    terraform_ok = ensure_installed(
        "terraform",
        "Please install Terraform before running the deployment python file."
    )
    ansible_ok = ensure_installed(
        "ansible-playbook",
        "Please install Ansible before running the deployment python file."
    )

    if not (terraform_ok and ansible_ok):
        print("Missing dependencies. Install them and re-run the script.")
        sys.exit(1)

    aws_arch_dir = Path(__file__).parent / "aws_architecture"
    if not aws_arch_dir.exists():
        print(f"Terraform directory not found: {aws_arch_dir}")
        sys.exit(1)

    terraform_dir = aws_arch_dir / ".terraform"
    if terraform_dir.exists():
        print("✅ Terraform already initialized, skipping 'terraform init'.")
    else:
        run_command(["terraform", "init"], cwd=aws_arch_dir)

    run_command(["terraform", "apply", "-auto-approve"], cwd=aws_arch_dir)

    # Step 4. Get Terraform output for attacker host
    print("\n🔍 Fetching Terraform outputs...")
    tf_output = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=aws_arch_dir,
        capture_output=True,
        text=True,
        check=True
    )
    print(f"Terraform Output:\n{tf_output.stdout}")

    # (Optional) You could parse the JSON here to extract host IPs
    # Example:
    # import json
    # output = json.loads(tf_output.stdout)
    # attacker_ip = output.get("attacker_public_ip", {}).get("value")

    # Step 5. Run Ansible playbook for the attacker machine
    att_dir = Path(__file__).parent / "att"
    playbook_path = att_dir / "att.yml"

    if not playbook_path.exists():
        print(f"Playbook not found: {playbook_path}")
        sys.exit(1)

    print("\nRunning Ansible playbook on attacker host...")
    run_command(["ansible-playbook", str(playbook_path)], cwd=att_dir)

    print("\nDeployment complete.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}: {e.cmd}")
        sys.exit(e.returncode)
