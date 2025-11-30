import os
import subprocess
import sys
import json
import argparse
import time
from pathlib import Path
from urllib.request import urlopen


DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"

INSTANCE_MAP = {
    "attacker": "attacker_instance_id",
    "target": "target_instance_id",
    "logging": "logging_instance_id"
}

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


def run_command(cmd, cwd=None, check=True, capture_output=False):
    if not capture_output:
        print(f"\nRunning: {' '.join(cmd)} (in {cwd or os.getcwd()})")
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=capture_output, text=True)

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
    ], cwd=Path(__file__).parent )

def setup_logging(attacker_host: str, attacker_user: str, ssh_key_path: Path):
    """Run logging playbook locally. Pass ansible_ssh_common_args to use attacker as jump host."""
    log_dir = Path(__file__).parent / "logging"
    playbook = log_dir / "main.yml"
    inventory = log_dir / "logging_server.ini"

    proxy = f'-o StrictHostKeyChecking=no -o ProxyCommand="ssh -o StrictHostKeyChecking=no -W %h:%p -q {attacker_user}@{attacker_host} -i {ssh_key_path} "'
    print(f"Running logging setup locally (inventory: {inventory}) using attacker {attacker_host} as jump host")
    run_command([
        "ansible-playbook",
        str(playbook),
        "-i",
        str(inventory),
        "-e",
        f"ansible_ssh_common_args='{proxy}'"
    ], cwd=Path(__file__).parent )

def setup_target(os_name: str, attacker_host: str, attacker_user: str, ssh_key_path: Path):
    """Copy target files and ssh_keys to attacker, then run ansible-playbook on attacker."""
    target_dir = Path(__file__).parent / "target" / os_name
    playbook = target_dir / "main.yml"
    inventory = target_dir / f"target_{os_name}.ini"
    print(f"Running target ({os_name}) setup on attacker...")
    proxy = f'-o StrictHostKeyChecking=no -o ProxyCommand="ssh -o StrictHostKeyChecking=no -W %h:%p -q {attacker_user}@{attacker_host} -i {ssh_key_path} "'
    run_command([
        "ansible-playbook",
        str(playbook),
        "-i",
        str(inventory),
        "-e",
        f"ansible_ssh_common_args='{proxy}'"
    ], cwd=Path(__file__).parent )

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

def get_terraform_outputs(cwd):
    """Retrieves all outputs from Terraform state as a dictionary."""
    try:
        proc = run_command(["terraform", "output", "-json"], cwd=cwd, capture_output=True)
        return json.loads(proc.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error fetching terraform outputs: {e}")
        return {}

def create_snapshot(role_name, terraform_dir):
    """
    1. Gets Instance ID from Terraform output.
    2. Uses AWS CLI to create an AMI.
    3. Saves the AMI ID to role_name/snapshot.json.
    """
    if not ensure_installed("aws", "Please install the AWS CLI (https://aws.amazon.com/cli/)."):
        return

    outputs = get_terraform_outputs(terraform_dir)
    output_key = INSTANCE_MAP.get(role_name)
    
    if not output_key or output_key not in outputs:
        print(f"❌ Could not find output '{output_key}' in Terraform state.")
        print(f"   Available outputs: {list(outputs.keys())}")
        return

    instance_id = outputs[output_key]['value']
    print(f"--> Found {role_name} instance ID: {instance_id}")

    timestamp = int(time.time())
    image_name = f"{role_name}-snapshot-{timestamp}"
    
    print(f"--> Triggering AWS Snapshot (AMI) creation: {image_name}...")
    
    try:
        # Create Image (AMI)
        cmd = [
            "aws", "ec2", "create-image",
            "--instance-id", instance_id,
            "--name", image_name,
            "--description", f"Snapshot of {role_name} created by deploy.py",
            "--no-reboot", 
            "--output", "json"
        ]
        
        result = run_command(cmd, check=True, capture_output=True)
        response = json.loads(result.stdout)
        ami_id = response.get("ImageId")
        
        if not ami_id:
            print("❌ Failed to get AMI ID from AWS response.")
            return

        print(f"✅ Snapshot started. AMI ID: {ami_id}")

        # Save to local folder: e.g. ./attacker/snapshot.json
        role_dir = Path(__file__).parent / role_name
        role_dir.mkdir(exist_ok=True, parents=True)
        snapshot_file = role_dir / "snapshot.json"
        
        snapshot_data = {
            "created_at": timestamp,
            "instance_id": instance_id,
            "ami_id": ami_id,
            "name": image_name
        }
        
        with open(snapshot_file, "w") as f:
            json.dump(snapshot_data, f, indent=2)
            
        print(f"✅ Snapshot info saved to: {snapshot_file}")
        print("   (Note: It may take a few minutes for the AMI to become 'available' in AWS console)")

    except subprocess.CalledProcessError as e:
        print(f"❌ AWS CLI command failed: {e.stderr}")

def load_snapshots_into_env():
    """
    Checks attacker/target/logging folders for snapshot.json.
    If found, sets TF_VAR_{role}_custom_ami environment variables.
    """
    print("\n--> Checking for local snapshots to apply...")
    found_any = False
    
    for role in INSTANCE_MAP.keys():
        snapshot_file = Path(__file__).parent / role / "snapshot.json"
        if snapshot_file.exists():
            try:
                with open(snapshot_file, 'r') as f:
                    data = json.load(f)
                    ami_id = data.get("ami_id")
                    if ami_id:
                        # Set the environment variable for Terraform
                        env_var_name = f"TF_VAR_{role}_custom_ami"
                        os.environ[env_var_name] = ami_id
                        print(f"   ✓ Found {role} snapshot: {ami_id}")
                        print(f"     Setting {env_var_name}...")
                        found_any = True
            except Exception as e:
                print(f"   ! Error reading {snapshot_file}: {e}")
    
    if not found_any:
        print("   No local snapshots found. Using default AMIs defined in vars.tf.")
    else:
        print("   Terraform will use these custom AMIs for the next apply.\n")

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
    ], cwd=Path(__file__).parent )

def setup_logging(attacker_host: str, attacker_user: str, ssh_key_path: Path):
    """Run logging playbook locally. Pass ansible_ssh_common_args to use attacker as jump host."""
    log_dir = Path(__file__).parent / "logging"
    playbook = log_dir / "main.yml"
    inventory = log_dir / "logging_server.ini"

    proxy = f'-o StrictHostKeyChecking=no -o ProxyCommand="ssh -o StrictHostKeyChecking=no -W %h:%p -q {attacker_user}@{attacker_host} -i {ssh_key_path} "'
    print(f"Running logging setup locally (inventory: {inventory}) using attacker {attacker_host} as jump host")
    run_command([
        "ansible-playbook",
        str(playbook),
        "-i",
        str(inventory),
        "-e",
        f"ansible_ssh_common_args='{proxy}'"
    ], cwd=Path(__file__).parent )

def setup_target(os_name: str, attacker_host: str, attacker_user: str, ssh_key_path: Path):
    """Copy target files and ssh_keys to attacker, then run ansible-playbook on attacker."""
    target_dir = Path(__file__).parent / "target" / os_name
    playbook = target_dir / "main.yml"
    inventory = target_dir / f"target_{os_name}.ini"
    print(f"Running target ({os_name}) setup on attacker...")
    proxy = f'-o StrictHostKeyChecking=no -o ProxyCommand="ssh -o StrictHostKeyChecking=no -W %h:%p -q {attacker_user}@{attacker_host} -i {ssh_key_path} "'
    run_command([
        "ansible-playbook",
        str(playbook),
        "-i",
        str(inventory),
        "-e",
        f"ansible_ssh_common_args='{proxy}'"
    ], cwd=Path(__file__).parent )

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
    parser.add_argument("--connect", action="store_true", help="Open an interactive SSH shell to ec2-user@<attacker-ip> using the user_to_attacker_key")
    parser.add_argument("--update-ip", nargs='?', const='auto', metavar='IP', help="Update SSH client IP in config.json and attacker security group via targeted Terraform apply. Optionally provide IP address (default: auto-detect)")
    parser.add_argument("--target", choices=['macos', 'windows', 'linux'], help="Set target_machine_os in config.json (works with --apply)")
    parser.add_argument("--no-ansible", action="store_true", help="Skip running the Ansible playbook")
    parser.add_argument("--setup", choices=["attacker", "logging", "target", "all"], help="Run only a specific setup step (remote SSH execution for logging/target)")
    parser.add_argument("--create-snapshot", choices=['attacker', 'target', 'logging', 'all'], 
                    help="Create an AMI snapshot of the specified running instance")

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

    # If user only wants to connect to the attacker instance, fetch its IP and open an interactive shell
    if args.connect:
        attacker_host = get_attacker_ip()
        if not attacker_host:
            print("Could not determine attacker IP (terraform outputs missing and config.json fallback empty).")
            return
        if not user_to_attacker_key.exists():
            print(f"SSH key not found: {user_to_attacker_key}. Ensure the key file exists relative to repo root.")
            return
        print(f"Opening SSH session to ec2-user@{attacker_host} using key {user_to_attacker_key}")
        try:
            run_command(["ssh", "-o", "StrictHostKeyChecking=no", "-i", str(user_to_attacker_key), f"ec2-user@{attacker_host}"], cwd=Path(__file__).parent)
        except subprocess.CalledProcessError as e:
            print(f"SSH command failed: {e}")
        return

    if args.create_snapshot:
        if args.create_snapshot == 'all':
            print("--> Snapshotting ALL instances...")
            for role in INSTANCE_MAP.keys():
                create_snapshot(role, aws_arch_dir)
        else:
            create_snapshot(args.create_snapshot, aws_arch_dir)
        return

    if args.destroy:
        print("--> Running terraform destroy (auto-approved)")
        run_command(["terraform", "init"], cwd=aws_arch_dir)
        run_command(["terraform", "destroy", "-auto-approve"], cwd=aws_arch_dir)
        print("Terraform destroy complete.")
        return

    if args.apply:
        if args.target:
            update_config(DEFAULT_CONFIG_PATH, {"target_machine_os": args.target})

        load_snapshots_into_env()
        run_command(["terraform", "init"], cwd=aws_arch_dir)
        run_command(["terraform", "apply", "-auto-approve"], cwd=aws_arch_dir)
        print("Terraform apply complete.")
        if not args.no_ansible:
            attacker_host = get_attacker_ip() 
            complete_setup = args.setup in [None, "all"]
            if complete_setup or args.setup == "attacker":
                setup_attacker()
            if complete_setup or args.setup == "logging": 
                setup_logging(attacker_host, "ec2-user", user_to_attacker_key)
            if complete_setup or args.setup == "target":
                setup_target(os_name, attacker_host, "ec2-user", user_to_attacker_key)
            
        print("\nDeployment complete.")

        # Display important information and next steps
        attacker_ip = get_attacker_ip()
        print("\n================ Deployment Summary ================")
        print(f"Attacker Public IP: {attacker_ip if attacker_ip else 'Not available'}")
        print("\nNext Steps:")
        print("1. Connect to the attacker instance:")
        print("   Use the '--connect' command: \n   python deploy.py --connect")
        print("   (Alternatively, use: ssh -i <path-to-key> ec2-user@<attacker-ip>)")
        print("2. Access Fleet server (if applicable): \n   Use the credentials in 'logging/fleet_credentials.yml'.")
        print("3. Create snapshots of instances for backup:")
        print("   Use the '--create-snapshot' command: \n   python deploy.py --create-snapshot <role>\n   (Roles: attacker, target, logging, or all)")
        print("4. Review logs and ensure all services are running as expected.")
        print("===================================================\n")
    else:
        print("No valid action specified.")
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}: {e.cmd}")
        sys.exit(e.returncode)