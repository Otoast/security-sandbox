#!/usr/bin/env python3
import os
import subprocess
import sys
import shutil
import json
import argparse
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"


def load_env(env_path: Path):
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
    if shutil.which(cmd):
        print(f"✅ {cmd} is already installed.")
        return True
    print(f"{cmd} is not installed.")
    print(f"{install_instructions}")
    return False


def run_command(cmd, cwd=None, check=True):
    print(f"\nRunning: {' '.join(cmd)} (in {cwd or os.getcwd()})")
    subprocess.run(cmd, cwd=cwd, check=check)


def get_public_ip():
    services = [
        "https://api.ipify.org?format=json",
        "https://ifconfig.co/json",
        "https://ipinfo.io/json",
    ]
    headers = {"User-Agent": "curl/7.0"}
    for svc in services:
        try:
            req = Request(svc, headers=headers)
            with urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    ip = raw.strip()
                    if ip:
                        return ip
                    continue
                for key in ("ip", "query", "address"):
                    if key in data:
                        return str(data[key])
        except (URLError, HTTPError) as e:
            print(f"Service {svc} failed: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error querying {svc}: {e}")
            continue
    print("Unable to determine public IP from known services.")
    return None


def update_config_with_ip(config_path: Path, ip: str):
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
        except Exception:
            print(f"Warning: could not parse existing {config_path}, overwriting.")
            cfg = {}
    else:
        cfg = {}
    cfg["ssh_client_ip"] = ip
    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"Updated {config_path} with public_ip = {ip}")


def reset_all(terraform_dir: Path):
    print("--> Resetting all EC2 instances (attacker, target, logging_machine)")
    run_command(["terraform", "destroy", "-auto-approve"], cwd=terraform_dir)
    run_command(["terraform", "apply", "-auto-approve"], cwd=terraform_dir)
    print("All instances reset complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Deployment utility for Terraform + Ansible",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("--apply", action="store_true", help="Apply (deploy) Terraform configuration")
    parser.add_argument("--destroy", action="store_true", help="Destroy all Terraform-managed resources")
    parser.add_argument("--reset", action="store_true", help="Destroy and redeploy all EC2 instances")
    parser.add_argument("--update-ip", action="store_true", help="Query public IP and update config.json (no Terraform)")
    parser.add_argument("--no-ansible", action="store_true", help="Skip running the Ansible playbook")

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(0)

    args = parser.parse_args()

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / ".env"
    load_env(env_path)

    if args.update_ip:
        ip = get_public_ip()
        if ip:
            update_config_with_ip(DEFAULT_CONFIG_PATH, ip)
            print("--update-ip completed; exiting.")
            return
        else:
            print("Public IP lookup failed; nothing was changed.")
            return

    os.environ["TF_VAR_availability_zone"] = os.environ.get("AWS_DEFAULT_REGION", "us-east-1a")

    terraform_ok = ensure_installed(
        "terraform",
        "Please install Terraform before running this deployment tool."
    )
    if not terraform_ok:
        print("Terraform is required. Install it and re-run the script.")
        sys.exit(1)

    aws_arch_dir = Path(__file__).parent / "aws_architecture"
    if not aws_arch_dir.exists():
        print(f"Terraform directory not found: {aws_arch_dir}")
        sys.exit(1)

    terraform_state_dir = aws_arch_dir / ".terraform"
    if terraform_state_dir.exists():
        print("✅ Terraform already initialized, skipping 'terraform init'.")
    else:
        run_command(["terraform", "init"], cwd=aws_arch_dir)

    if args.reset:
        reset_all(aws_arch_dir)
        return

    if args.destroy:
        print("--> Running terraform destroy (auto-approved)")
        run_command(["terraform", "destroy", "-auto-approve"], cwd=aws_arch_dir)
        print("Terraform destroy complete.")
        return

    if args.apply:
        run_command(["terraform", "apply", "-auto-approve"], cwd=aws_arch_dir)

        print("\n🔍 Fetching Terraform outputs...")
        tf_output = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=aws_arch_dir,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"Terraform Output:\n{tf_output.stdout}")

        if not args.no_ansible:
            ansible_ok = ensure_installed(
                "ansible-playbook",
                "Please install Ansible before running the deployment python file."
            )
            if not ansible_ok:
                print("Ansible not available; skipping playbook run.")
            else:
                att_dir = Path(__file__).parent / "att"
                playbook_path = att_dir / "att.yml"
                if not playbook_path.exists():
                    print(f"Playbook not found: {playbook_path}")
                    sys.exit(1)
                print("\nRunning Ansible playbook on attacker host...")
                run_command(["ansible-playbook", str(playbook_path)], cwd=att_dir)

        print("\nDeployment complete.")
    else:
        print("No action specified. Use --apply, --destroy, --reset, or --update-ip.")
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}: {e.cmd}")
        sys.exit(e.returncode)
