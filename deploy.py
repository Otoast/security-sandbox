import os
import subprocess
import sys
import json
import argparse
from pathlib import Path
from urllib.request import urlopen


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

def run_command(cmd, cwd=None, check=True):
    print(f"\nRunning: {' '.join(cmd)} (in {cwd or os.getcwd()})")
    subprocess.run(cmd, cwd=cwd, check=check)

def get_public_ip():
    """Detect public IP using ipify service."""
    try:
        with urlopen("https://api.ipify.org", timeout=10) as resp:
            return resp.read().decode().strip()
    except Exception as e:
        print(f"Failed to detect public IP: {e}")
        return None

def update_config(config_path: Path, updates: dict):
    with open(config_path, "r") as f:
        cfg = json.load(f)
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
    """Attempt to retrieve attacker public IP from Terraform outputs; fallback to config.json."""
    aws_arch_dir = Path(__file__).parent / "aws_architecture"
    try:
        result = subprocess.run(["terraform", "output", "-json"], cwd=aws_arch_dir, capture_output=True, text=True, check=True)
        outputs = json.loads(result.stdout or "{}")
        attacker_pub = outputs.get("attacker_public_ip", {}).get("value")
        if attacker_pub:
            # Persist into config.json for later runs
            update_config(DEFAULT_CONFIG_PATH, {"attacker_ip": attacker_pub, "attacker_public_ip": attacker_pub})
            return attacker_pub
        else:
            print("[INFO] Terraform output missing 'attacker_public_ip'. Falling back to config.json.")
    except Exception as e:
        print(f"[INFO] Terraform outputs not available for attacker IP: {e}")
    cfg = load_config()
    return cfg.get("attacker_ip")

# Modular setup functions
def setup_attacker():
    """Run attacker/main.yml playbook with attacker/attacker.ini inventory."""
    att_dir = Path(__file__).parent / "attacker"
    playbook = att_dir / "main.yml"
    inventory = att_dir / "inventory.ini"
    attacker_host = get_attacker_ip()
    lines = inventory.read_text().splitlines()
    new_lines = []
    in_attacker_section = False
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            # entering a (new) section
            in_attacker_section = (stripped.lower() == "[attacker]")
            new_lines.append(line)
            continue
        if in_attacker_section and not replaced:
            # replace the first non-empty, non-comment line in attacker section with the IP
            if stripped and not stripped.startswith("#"):
                new_lines.append(str(attacker_host))
                replaced = True
                continue
        new_lines.append(line)
    # If attacker section was found but had no host line, append it
    if in_attacker_section and not replaced:
        new_lines.append(str(attacker_host))
    inventory.write_text("\n".join(new_lines) + "\n")

    print("Running attacker setup...")
    run_command([
        "ansible-playbook", str(playbook), "-i", str(inventory),
        "-e", 'ansible_ssh_common_args="-o StrictHostKeyChecking=no"'
    ], cwd=att_dir)

def setup_logging(attacker_host: str, attacker_user: str, ssh_key_path: Path):
    """Run logging playbook locally. Pass ansible_ssh_common_args to use attacker as jump host."""
    log_dir = Path(__file__).parent / "logging"
    playbook = log_dir / "main.yml"
    inventory = log_dir / "logging_server.ini"
    proxy = f'\'-o StrictHostKeyChecking=no -o ProxyCommand="ssh -i {ssh_key_path} -o StrictHostKeyChecking=no {attacker_user}@{attacker_host} -W %h:%p"\''
    print(f"Running logging setup locally (inventory: {inventory}) using attacker {attacker_host} as jump host")
    run_command([
        "ansible-playbook",
        str(playbook),
        "-i",
        str(inventory),
        "-e",
        f'ansible_ssh_common_args={proxy}'
    ], cwd=log_dir)

def setup_target(os_name: str, attacker_host: str, attacker_user: str, ssh_key_path: Path):
    """Copy target files and ssh_keys to attacker, then run ansible-playbook on attacker."""
    log_dir = Path(__file__).parent / "target"
    playbook = log_dir / "main.yml"
    inventory = log_dir / f"target_{os_name}.ini"
    print(f"Running target ({os_name}) setup on attacker...")
    proxy = f'\'-o StrictHostKeyChecking=no -o ProxyCommand="ssh -i {ssh_key_path} -o StrictHostKeyChecking=no {attacker_user}@{attacker_host} -W %h:%p"\''
    run_command([
        "ansible-playbook",
        str(playbook),
        "-i",
        str(inventory),
        "-e",
        f"ansible_ssh_common_args={proxy}"
    ], cwd=log_dir)

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
    aws_arch_dir = Path(__file__).parent / "aws_architecture"

    print("Loading environment variables...")
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

    if args.update_ip:
        if args.update_ip in [None, 'auto']:
            ip = get_public_ip()
            if not ip:
                print("Public IP lookup failed; cannot proceed with --update-ip.")
                return
            print(f"Auto-detected public IP: {ip}")
        else:
            ip = args.update_ip
            print(f"Using provided IP: {ip} instead of auto-detect.")
        update_config(DEFAULT_CONFIG_PATH, {"user_ip": ip})
        run_command(
            ["terraform", "apply", "-target=aws_security_group.attacker_machine_sg", "-auto-approve"],
            cwd=aws_arch_dir
        )
        print("Config.json and environment successfully updated with new IP")
        return

    os.environ["TF_VAR_availability_zone"] = os.environ.get("AWS_DEFAULT_REGION", "us-east-1a")
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
        print("Terraform apply complete.")
        if not args.no_ansible:
            attacker_host = get_attacker_ip() 
            complete_setup = args.setup in [None, "all"]
            if complete_setup or args.setup == "attacker":
                setup_attacker()
            if complete_setup or args.setup == "logging": 
                setup_logging(attacker_host, "ec2-user", user_to_attacker_key) # user_to_attacker_key
            if complete_setup or args.setup == "target":
                setup_target(os_name, attacker_host, "ec2-user", user_to_attacker_key)
            
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
