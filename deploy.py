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
        print(f"{cmd} is already installed.")
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


def update_config(config_path: Path, updates: dict):
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
        except Exception:
            print(f"Warning: could not parse existing {config_path}, overwriting.")
            cfg = {}
    else:
        cfg = {}
    cfg.update(updates)
    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"Updated {config_path} with: {updates}")


def reset_all(terraform_dir: Path):
    print("--> Resetting all EC2 instances (attacker, target, logging_machine)")
    run_command(["terraform", "destroy", "-auto-approve"], cwd=terraform_dir)
    run_command(["terraform", "apply", "-auto-approve"], cwd=terraform_dir)
    print("All instances reset complete.")


def load_config():
    """Load config.json and return dict; empty dict on failure."""
    try:
        with open(DEFAULT_CONFIG_PATH) as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Could not load config.json: {e}")
        return {}


def get_attacker_ip():
    """Attempt to retrieve attacker public IP from Terraform outputs; fallback to config.json.

    Requires that terraform outputs define one of: attacker_ip, attacker_public_ip, attacker_machine_ip
    Example Terraform output block to add (if missing):
        output "attacker_public_ip" { value = aws_instance.attacker_machine.public_ip }
    """
    aws_arch_dir = Path(__file__).parent / "aws_architecture"
    try:
        result = subprocess.run([
            "terraform", "output", "-json"
        ], cwd=aws_arch_dir, capture_output=True, text=True, check=True)
        outputs = json.loads(result.stdout or "{}")
        for key in ("attacker_ip", "attacker_public_ip", "attacker_machine_ip"):
            if key in outputs and isinstance(outputs[key], dict) and "value" in outputs[key]:
                return outputs[key]["value"]
    except Exception as e:
        print(f"[INFO] Terraform outputs not available for attacker IP: {e}")
    cfg = load_config()
    return cfg.get("attacker_ip")

# Modular setup functions
def setup_attacker():
    """Run attacker/main.yml playbook with attacker/attacker.ini inventory."""
    att_dir = Path(__file__).parent / "attacker"
    playbook = att_dir / "main.yml"
    inventory = att_dir / "attacker.ini"
    print("Running attacker setup...")
    run_command([
        "ansible-playbook", str(playbook), "-i", str(inventory)
    ], cwd=att_dir)

def setup_logging(attacker_host: str, attacker_user: str, ssh_key_path: Path):
    """SSH into attacker and run logging/main.yml that resides ON the attacker host.
    """
    config = load_config()
    remote_repo_path = config.get("remote_repo_path", "~/security-sandbox")  # assumption if not provided
    remote_playbook = f"{remote_repo_path}/logging/main.yml"
    remote_inventory = f"{remote_repo_path}/logging/logging_server.ini"
    print(f"Remote executing playbook on attacker host {attacker_host}...")
    remote_cmd = (
        f"ansible-playbook {remote_playbook} -i {remote_inventory} "
        f"--private-key {remote_repo_path}/ssh_keys/{ssh_key_path.name} -u {attacker_user}"
    )
    run_remote_ssh(ssh_key_path, attacker_user, attacker_host, remote_cmd)

def setup_target(os_name: str, attacker_host: str, attacker_user: str, ssh_key_path: Path):
    """SSH into attacker and run target/{os}/main.yml that resides ON the attacker host.
    """
    config = load_config()
    remote_repo_path = config.get("remote_repo_path", "~/security-sandbox")
    remote_playbook = f"{remote_repo_path}/target/{os_name}/main.yml"
    remote_inventory = f"{remote_repo_path}/target/{os_name}/target_{os_name}.ini"
    print(f"[Target] Remote executing target/{os_name}/main.yml on attacker host {attacker_host} ...")
    remote_cmd = (
        f"ansible-playbook {remote_playbook} -i {remote_inventory} "
        f"--private-key {remote_repo_path}/ssh_keys/{ssh_key_path.name} -u {attacker_user}"
    )
    run_remote_ssh(ssh_key_path, attacker_user, attacker_host, remote_cmd)

def run_remote_ssh(key_path: Path, user: str, host: str, remote_command: str):
    """Execute a remote shell command on attacker via SSH.
    """
    ssh_cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no", "-i", str(key_path), f"{user}@{host}", remote_command
    ]
    print(f"[SSH] Executing on {host}: {remote_command}")
    try:
        run_command(ssh_cmd)
    except subprocess.CalledProcessError as e:
        print(f"Remote SSH command failed (exit {e.returncode}). Command: {remote_command}")

def main():
    parser = argparse.ArgumentParser(
        description="Deployment utility for Terraform + Ansible",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--apply", action="store_true", help="Apply (deploy) Terraform configuration")
    parser.add_argument("--destroy", action="store_true", help="Destroy all Terraform-managed resources")
    parser.add_argument("--reset", action="store_true", help="Destroy and redeploy all EC2 instances")
    parser.add_argument("--update-ip", nargs='?', const='auto', metavar='IP', help="Update SSH client IP in config.json and attacker security group via targeted Terraform apply. Optionally provide IP address (default: auto-detect)")
    parser.add_argument("--target", choices=['macos', 'windows', 'linux'], help="Set target_machine_os in config.json (works with --apply)")
    parser.add_argument("--no-ansible", action="store_true", help="Skip running the Ansible playbook")
    parser.add_argument("--setup", choices=["attacker", "logging", "target", "all"], help="Run only a specific setup step (remote SSH execution for logging/target)")

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(0)

    args = parser.parse_args()

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / ".env"
    load_env(env_path)

    # Load config.json for keys and OS
    with open(DEFAULT_CONFIG_PATH) as f:
        config = json.load(f)
    os_name = config.get("target_machine_os", "linux")
    ssh_keys_dir = Path(config.get("ssh_keys_dir", "./ssh_keys"))
    user_to_attacker_key = ssh_keys_dir / config["user_to_attacker_ssh_key"]["name"]
    internal_lab_key = ssh_keys_dir / config["internal_lab_ssh_key"]["name"]

    # For demo, attacker host/user are hardcoded; in real use, fetch from Terraform output or config
    attacker_host = get_attacker_ip() or "attacker_host_ip"  # TODO: ensure terraform outputs or config.json contains attacker_ip
    attacker_user = config.get("attacker_ssh_user", "ec2-user")  # optional config override

    if args.update_ip:
        # Determine which IP to use
        if args.update_ip == 'auto':
            # Auto-detect IP
            ip = get_public_ip()
            if not ip:
                print("Public IP lookup failed; cannot proceed with --update-ip.")
                return
            print(f"Auto-detected public IP: {ip}")
        else:
            # User provided an IP
            ip = args.update_ip
            print(f"Using provided IP: {ip}")
            
            # Query web services to compare
            detected_ip = get_public_ip()
            if detected_ip and detected_ip != ip:
                print(f"\n⚠️  WARNING: Provided IP ({ip}) differs from auto-detected IP ({detected_ip})")
                print("    Continuing with provided IP...\n")
            elif detected_ip:
                print(f"✓ Provided IP matches auto-detected IP")
        
        # Update config.json
        update_config(DEFAULT_CONFIG_PATH, {"ssh_client_ip": ip})
        
        # Run targeted Terraform apply to update only the security group
        terraform_ok = ensure_installed(
            "terraform",
            "Please install Terraform to update the security group."
        )
        if not terraform_ok:
            print("Terraform is required for security group update. Exiting.")
            return
        
        aws_arch_dir = Path(__file__).parent / "aws_architecture"
        if not aws_arch_dir.exists():
            print(f"Terraform directory not found: {aws_arch_dir}")
            return
        
        print("\n--> Running targeted Terraform apply to update attacker_machine_sg only...")
        print("    This will update the security group without redeploying instances.\n")
        
        run_command(
            ["terraform", "apply", "-target=aws_security_group.attacker_machine_sg", "-auto-approve"],
            cwd=aws_arch_dir
        )
        
        print("\n✓ Security group updated successfully!")
        print("  Config.json updated with new IP")
        print("  Attacker security group SSH rule updated via Terraform")
        print("  No instance redeployment required")
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
        print("Terraform already initialized, skipping 'terraform init'.")
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
        if args.target:
            update_config(DEFAULT_CONFIG_PATH, {"target_machine_os": args.target})

        run_command(["terraform", "apply", "-auto-approve"], cwd=aws_arch_dir)

        print("\nFetching Terraform outputs...")
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
                # Modular setup calls
                if args.setup in [None, "all"]:
                    setup_attacker()
                    setup_logging(attacker_host, attacker_user, user_to_attacker_key)
                    setup_target(os_name, attacker_host, attacker_user, internal_lab_key)
                elif args.setup == "attacker":
                    setup_attacker()
                elif args.setup == "logging":
                    setup_logging(attacker_host, attacker_user, user_to_attacker_key)
                elif args.setup == "target":
                    setup_target(os_name, attacker_host, attacker_user, internal_lab_key)

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
