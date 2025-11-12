import json
import subprocess
import os
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
except ImportError:
    print("🔧 'cryptography' not found — installing with pip...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "cryptography"])
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519, rsa


def generate_with_cryptography(dest_path: Path, key_type: str, passphrase: str, comment: str = ""):
    """Generate private/public keypair using cryptography (ed25519 or rsa)."""
    key_type_l = key_type.lower()
    if key_type_l == "ed25519":
        private_key = ed25519.Ed25519PrivateKey.generate()
    elif key_type_l == "rsa":
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    else:
        raise ValueError(f"Unsupported key type: {key_type}")

    encryption = (
        serialization.BestAvailableEncryption(passphrase.encode())
        if passphrase else serialization.NoEncryption()
    )

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=encryption,
    )

    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )

    # write private/public keys
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(private_bytes)
    with open(f"{dest_path}.pub", "wb") as f:
        f.write(public_bytes)

    try:
        os.chmod(dest_path, 0o600)
    except Exception:
        pass

    print(f"✅ Created key pair:\n  {dest_path}\n  {dest_path}.pub")


def main():
    with open("config.json") as f:
        config = json.load(f)

    for key_config_name in ["user_to_attacker_ssh_key", "internal_lab_ssh_key"]:
        ssh_key_details = config[key_config_name]
        ssh_key_dir = Path(config["ssh_keys_dir"]).expanduser().resolve()
        ssh_key_dir.mkdir(parents=True, exist_ok=True)

        key_name = ssh_key_details["name"]
        key_passphrase = ssh_key_details.get("passphrase", "")
        key_type = ssh_key_details.get("type", "ed25519")
        comment = ssh_key_details.get("comment", "")

        dest = ssh_key_dir / key_name

        if (dest.exists() or (dest.with_suffix(dest.suffix + ".pub").exists())):
            print(f"Warning: Key already exists: {dest} or {dest}.pub. Skipping generation.")
            continue

        print(f"🔑 Generating {key_type} keypair at: {dest}")
        generate_with_cryptography(dest, key_type, key_passphrase, comment)


if __name__ == "__main__":
    main()
