# Attacker Machine Configuration

**Author:** Archit  
**Purpose:** Configure the attacker EC2 instance with Atomic Red Team and necessary tools

## What This Does

This Ansible playbook configures the attacker machine with:
- **Atomic Red Team** framework for simulating attacks
- **PowerShell Core** (required by Atomic Red Team)
- **SSH access** to target and control machines
- **Ansible** for running playbooks on other instances
- **Project repository** cloned for easy access

## Requirements

### AMI Recommendations
- **Ubuntu 22.04 LTS** (Recommended)
  - us-east-1: `ami-0c7217cdde317cfec`
  - us-west-2: `ami-0efcece6bed30fd98`
- **Amazon Linux 2023** (Alternative)
  - us-east-1: `ami-0cf10cdf9fcd62d37`

### Instance Requirements
- **Instance Type:** t3.medium minimum (4GB RAM needed)
- **Storage:** 20GB minimum
- **Security Group:** 
  - Inbound: SSH (22) from your IP
  - Outbound: All traffic (for installing packages)

## Installation Steps

### 1. Prerequisites
Ensure you have:
- Ansible installed locally
- SSH key pair for the attacker machine (`attacker-machine-key.pem`)
- Lab internal key pair (`lab-internal-key.pem`)
- Public IP of the EC2 instance

### 2. Update Inventory
Edit `inventory.ini` and replace:
- `<PUBLIC_IP>` with the actual public IP from Terraform
- Update `ansible_user` if using Amazon Linux (use `ec2-user`)

### 3. Store SSH Keys
Create a keys directory:
```bash
mkdir -p keys
# Save your keys here
keys/
├── attacker-machine-key.pem  (from Terraform)
└── lab-internal-key.pem       (from Terraform)

# Set permissions
chmod 600 keys/*.pem
```

### 4. Run the Playbook

**Dry run (check for errors):**
```bash
ansible-playbook -i inventory.ini attacker-playbook.yml --check
```

**Actual run:**
```bash
ansible-playbook -i inventory.ini attacker-playbook.yml \
  --extra-vars "lab_internal_key='$(cat keys/lab-internal-key.pem)'"
```

This will take approximately 5-10 minutes.

## Verification

After the playbook completes, SSH into the instance:
```bash
ssh -i keys/attacker-machine-key.pem ubuntu@<PUBLIC_IP>
```

### Verify Installations

**1. Check PowerShell:**
```bash
pwsh --version
# Should show: PowerShell 7.4.0
```

**2. Check Atomic Red Team:**
```bash
ls /opt/AtomicRedTeam
# Should show the repository files
```

**3. Test Atomic Red Team:**
```bash
pwsh
```
Then in PowerShell:
```powershell
Import-Module invoke-atomicredteam
Invoke-AtomicTest T1003.001 -ShowDetails
exit
```

**4. Check SSH Configuration:**
```bash
cat ~/.ssh/config
# Should show target-machine and control-machine entries
```

**5. Check Project Repository:**
```bash
ls /opt/security-sandbox
# Should show this repository cloned
```

## Usage for Students

Once logged into the attacker machine, students can:

### Run Atomic Red Team Tests
```bash
cd /opt/AtomicRedTeam
pwsh
Import-Module invoke-atomicredteam

# List available tests
Invoke-AtomicTest T1003.001 -ShowDetails

# Run a test
Invoke-AtomicTest T1003.001
```

### SSH to Other Machines
```bash
ssh target-machine    # Connects to target
ssh control-machine   # Connects to control/ELK
```

### Run Ansible Playbooks
```bash
cd /opt/security-sandbox
ansible-playbook control/control-playbook.yml
ansible-playbook target/target-playbook.yml
```

## Troubleshooting

### SSH Connection Fails
```bash
# Verify key permissions
chmod 600 keys/attacker-machine-key.pem

# Test connection with verbose output
ssh -vvv -i keys/attacker-machine-key.pem ubuntu@<PUBLIC_IP>

# Check security group allows SSH from your IP
```

### Ansible Playbook Fails
```bash
# Run with verbose output
ansible-playbook -i inventory.ini attacker-playbook.yml -vvv

# Check connectivity
ansible -i inventory.ini attacker -m ping
```

### PowerShell Installation Fails
The playbook downloads PowerShell from GitHub. If this fails:
- Check internet connectivity from the EC2 instance
- Verify security group allows outbound HTTPS (443)
- Try manually: `curl -I https://github.com`

### Atomic Red Team Module Not Found
```bash
# SSH into instance and reinstall
pwsh
Install-Module -Name invoke-atomicredteam -Scope AllUsers -Force
Import-Module invoke-atomicredteam
```

## Integration with Terraform

This playbook is designed to work with Lyle's Terraform configuration. 

### What Terraform Should Provide:
1. EC2 instance with Ubuntu 22.04 LTS
2. Public IP address
3. SSH key pair (`attacker-machine-key.pem`)
4. Lab internal key pair (`lab-internal-key.pem`)
5. Security group with proper rules

### Terraform Provisioner Example:
```hcl
resource "null_resource" "configure_attacker" {
  depends_on = [aws_instance.attacker_machine]
  
  provisioner "local-exec" {
    command = <<-EOT
      cd attacker
      ansible-playbook -i '${aws_instance.attacker_machine.public_ip},' \
      -u ubuntu \
      --private-key ../keys/attacker-machine-key.pem \
      attacker-playbook.yml \
      --extra-vars "lab_internal_key='${file("../keys/lab-internal-key.pem")}'"
    EOT
  }
}
```

## Files in This Directory
```
attacker/
├── attacker-playbook.yml    # Main Ansible playbook
├── inventory.ini            # Ansible inventory file
├── README.md               # This file
├── test-atomic.sh          # Quick test script (optional)
└── keys/                   # SSH keys directory (gitignored)
    ├── attacker-machine-key.pem
    └── lab-internal-key.pem
```

## Security Notes

- **Never commit SSH keys to Git**
- The `keys/` directory should be in `.gitignore`
- Lab internal key is passed via `--extra-vars`, not stored in files
- Security groups should restrict SSH to specific IPs only

## Next Steps

After this playbook succeeds:
1. Coordinate with Tyler/Otokini/Bao for control and target playbooks
2. Test SSH connectivity to other instances
3. Run test Atomic Red Team attacks
4. Verify alerts appear in Kibana

## Contact

For questions or issues with this playbook:
- **Archit** - Attacker machine configuration
- GitHub: https://github.com/Otoast/security-sandbox