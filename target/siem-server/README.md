# **SIEM Server Automated Deployment Guide**

This guide provides the necessary files and instructions to automatically deploy and configure a complete SIEM (Security Information and Event Management) server using Ansible.  
This server will host Elasticsearch, Kibana, and the Elastic Fleet Server, which will act as the central management hub for your entire security lab.

## **Prerequisites**

1. **Ansible Control Node:** You must have Ansible installed on your local computer (or a dedicated "control" machine).  
2. **AWS EC2 Instance:** You must have already provisioned a Debian-based (e.g., Ubuntu 22.04) EC2 instance to act as your siem-server.  
3. **EC2 Key Pair:** You need the .pem private key file for your EC2 instance.  
4. **IP Addresses:** You need two IP addresses from the AWS EC2 Console:  
   * **Public IPv4 address:** To connect via SSH.  
   * **Private IPv4 address:** For the server's internal configuration.

## **1\. File Configuration**

You need two files to run this deployment:

### **A. The Playbook (siem\_server\_playbook.yml)**

This is the main Ansible script. It contains all the automated tasks for installing and configuring Elasticsearch, Kibana, and the Elastic Agent.  
**Before you run this file, you MUST edit the vars: section at the top:**  
  \# \--- Required Variables \---  
  \#  
  \# You MUST replace these values.  
  \# For 'siem\_password', use a strong password you create.  
  \# For 'siem\_private\_ip', get this from your AWS EC2 console.  
  \#  
  vars:  
    siem\_password: "YOUR\_SECURE\_PASSWORD\_HERE" \# CHANGE THIS\!  
    siem\_private\_ip: "10.0.1.10"                 \# CHANGE THIS\!  
    elastic\_version: "8.10.4"

1. **siem\_password**: Replace "YOUR\_SECURE\_PASSWORD\_HERE" with a strong, unique password. This will be the password for the elastic superuser.  
2. **siem\_private\_ip**: Replace "10.0.1.10" with the **Private IPv4 address** of your siem-server instance from the AWS Console.

### **B. The Inventory (inventory.ini)**

This file tells Ansible *where* your server is and *how* to connect to it. Create a new file named inventory.ini in the same directory as your playbook.  
**Copy the template below and edit it with your server's information:**  
\[siem\_server\]  
YOUR\_SERVER\_PUBLIC\_IP ansible\_user=ubuntu ansible\_ssh\_private\_key\_file=\~/.ssh/your-aws-key.pem

1. **YOUR\_SERVER\_PUBLIC\_IP**: Replace this with the **Public IPv4 address** of your siem-server from the AWS Console.  
2. **ansible\_user**: Replace ubuntu if you are using a different AMI (e.g., ec2-user for Amazon Linux). ubuntu is correct for Ubuntu AMIs.  
3. **ansible\_ssh\_private\_key\_file**: Replace \~/.ssh/your-aws-key.pem with the full file path to your EC2 private key file.

## **2\. How to Run the Deployment**

Once you have both files saved and configured, follow these steps.

1. Open your computer's terminal (e.g., Terminal, PowerShell, or WSL).  
2. Navigate to the directory containing your siem\_server\_playbook.yml and inventory.ini files.  
3. Run the following command:  
   ansible-playbook \-i inventory.ini siem\_server\_playbook.yml

Ansible will now connect to your server via SSH and automatically execute all the tasks in the playbook. This may take 5-10 minutes to complete.

## **3\. Verification**

If the playbook finishes without any red "fatal" errors, your SIEM server is up and running.  
You can verify this by opening your web browser and navigating to the Kibana dashboard:

* **URL:** http://\<YOUR\_SERVER\_PUBLIC\_IP\>:5601  
* **User:** elastic  
* **Password:** The siem\_password you set in the siem\_server\_playbook.yml file.

You should see the Kibana login page. If you can log in, your SIEM server is successfully deployed and ready for the next steps.