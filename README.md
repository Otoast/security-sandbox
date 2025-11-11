Requirements:
- Python
    - ssh-keygen.py requires cryptography module to generate keys. Running the file automatically installs the dependency
- Terraform
- Ansible

Please refer to config.json for configurable settings. Most importantly:
    - Set your current client IP so you are able to ssh into the attacker host.
        - You can use the following website to determine your current ip: https://whatismyipaddress.com/
    - Set what operating system the target machine will be using

Additionally, authentication needs to be prvided to connect to the aws console. This can be done by setting env variables or providing credentials in providers.tf

This lab was intended to be straightforward to deploy and utilize