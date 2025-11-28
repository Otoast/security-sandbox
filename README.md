one_click_setup.sh handles deploying the lab on a completely new instance! Please utilize the file to make setup easier.
Note: AWS API credentials are required for Terraform to run sucessfully. You set these parameters in the .env file.

----

Requirements:
- Python
    - key_generation.py requires cryptography module to generate keys. Running the file automatically installs the dependency
- Terraform
- Ansible

If you are on Windows, please execute this environment in WSL, as issues with SSH key permissions may occur due to difference in OS. Subsequent updates might be needed to properly handle key permission changes on WIndows.

Please refer to config.json for configurable settings. Most importantly:
    - Set your user!
    - Set your current client IP so you are able to ssh into the attacker host.
        - You can use the following website to determine your current ip: https://whatismyipaddress.com/
        - You can execute python deploy.py --update-ip auto to handle the ip configuration and Terraform changes related to it
    - Set what operating system the target machine will be using

Note: AWS EC2 key pairs created by Terraform are automatically suffixed with an 8-character MD5 hash of the `user` value from `config.json`. This keeps key names unique per IAM user even when multiple people share an AWS account.

deploy.py handles terraform and ansible setup. To see all possible options, run the command `python deploy.py --help`

