
**Let me just set up and go!!**
one_click_setup.sh handles deploying the lab on a completely new instance! Please utilize the file first to make setup easier.

Note: AWS API credentials are required for Terraform to run sucessfully. You set these parameters in the .env file.
----
**Information**
Requirements:
- Python
    - key_generation.py requires cryptography module to generate keys. Running the file automatically installs the dependency
- Terraform
- Ansible
- AWS CLI (if you want to take snapshots of instnaces for redeployment)

If you are on Windows, please execute this environment in WSL, as issues with SSH key permissions may occur due to difference in OS. Subsequent version updates might be perfomed to properly handle key permission changes on Windows.

Please refer to config.json for configurable settings. Most importantly:
    - Set your user!
    - Set your current client IP so you are able to ssh into the attacker host.
        - You can use the following website to determine your current ip: https://whatismyipaddress.com/
        - You can execute python deploy.py --update-ip auto to handle the ip configuration and Terraform changes related to it
    - Set what operating system the target machine will be using

Note: AWS EC2 key pairs created by Terraform are automatically suffixed with an 8-character MD5 hash of the `user` value from `config.json`. This keeps key names unique per IAM user even when multiple people share an AWS account.

deploy.py handles terraform and ansible setup, as well as instance screenshots. To see all possible options, run the command `python deploy.py --help`

**Limitations**
- If you change the private IP address of any of the instances in config.json, changes to the .ini files must be made to reflect this. Future versions should have automatic handling of this configuration change.
- The Logging (ELK Stack) instance is lacks internet access to promote lab isolation. This might lead to difficulty in installing additional integrations unless the packages are first installed via the attacker instance, SCP'd to the Logging instance, and then subsequently installed manually.
    - If this limitation becomes too much of a hassle, future versions can allow for the Logging instance to have internet access, and consequently streamline installation and updates

**Future Work**
- Better organization of deploy.py, likely moving helper functions to different files to keep logic understandbale
- .ini files might be better off dynamically configured instead of hard-coded (so specification of ssh_keys dir is better and ip's are more easily configurable)