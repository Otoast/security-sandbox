# Target Machine Deployment

This directory contains the Ansible playbook and configuration for deploying Elastic Agents to target machines in a security sandbox environment.

## 📋 Overview

Target machines are the systems being monitored for security events. Each target runs an Elastic Agent that collects logs, metrics, and security events, then sends them to the central logging server.

### What Gets Monitored

- 🔒 **Security Events**: Authentication attempts, privilege escalation, user changes
- 📝 **System Logs**: Syslog, auth.log, application logs
- ⚙️ **Process Activity**: Execution, network connections, file access
- 🌐 **Network Traffic**: Connection metadata, DNS queries, HTTP requests
- 📊 **System Metrics**: CPU, memory, disk usage, network stats

## 🚀 Quick Start

### Prerequisites

**IMPORTANT**: Deploy the logging server first!

```bash
cd ../../logging/linux
ansible-playbook -i logging_server.ini main.yml
```

This creates the `.fleet_credentials.yml` file needed for target enrollment.

### 1. Configure Inventory

Edit `target_linux.ini` with your target machine IPs:

```ini
[target_linux]
10.0.2.10
10.0.2.11
10.0.2.12
# Add as many targets as needed

[target_linux:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/your-key.pem
```

### 2. Deploy Agents

```bash
cd target/linux
ansible-playbook -i target_linux.ini main.yml
```

### 3. Verify Enrollment

1. Open Kibana: `http://<logging-server>:5601`
2. Go to: **Management → Fleet → Agents**
3. All targets should appear with "Healthy" status

## 📁 Files

- `main.yml` - Main Ansible playbook for Elastic Agent deployment
- `target_linux.ini` - Inventory file (configure your target IPs here)
- `configure_linux_ec2_user_data` - Optional EC2 user data script
- `README.md` - This file

## 💾 System Requirements

### Minimum per Target

- **RAM**: 512MB
- **CPU**: 1 core
- **Disk**: 5GB
- **OS**: Ubuntu 20.04+ or RHEL/CentOS 8+

### Recommended per Target

- **RAM**: 1GB (more if collecting high-volume logs)
- **CPU**: 2 cores
- **Disk**: 10GB+ (for log buffering)

### Network Requirements

Target machines must be able to reach:

| Destination | Port | Purpose |
|-------------|------|---------|
| Logging Server | 8220 | Fleet Server (enrollment & management) |
| Internet | 443 | Download Elastic Agent (during installation only) |

## 🔧 Configuration

### Changing Agent Version

Edit `main.yml` variables section:

```yaml
vars:
  elastic_agent_version: "9.1.5"
```

**Note**: Agent version should match the logging server version.

### TLS Certificate Verification

By default, the playbook skips TLS verification (`insecure: true`).

For production with proper certificates:

```yaml
vars:
  insecure: false  # Change to false
```

## 📊 Post-Deployment

### Verify Agent Installation

On any target machine:

```bash
# Check agent status
sudo elastic-agent status

# View agent logs
sudo elastic-agent logs

# Check systemd service
sudo systemctl status elastic-agent
```

### View Collected Data

In Kibana:

1. Go to: **Discover**
2. Select data view: `logs-*`
3. Filter by hostname: `host.name: your-target-hostname`

### Check Fleet Management

In Kibana:

1. Go to: **Management → Fleet → Agents**
2. Click on an agent to see:
   - Connection status
   - Applied policy
   - Collected metrics
   - Recent errors

## 🔍 Data Collection Details

### Default Integrations

The default Fleet policy collects:

#### System Logs
- `/var/log/syslog`
- `/var/log/auth.log`
- `/var/log/messages`
- `/var/log/secure`

#### System Metrics
- CPU usage per core and total
- Memory usage (used, free, cached)
- Disk I/O and space usage
- Network interface stats

#### Process Information
- Running processes
- Process hierarchies
- Network connections per process

### Adding More Integrations

To collect additional data:

1. In Kibana: **Management → Fleet → Agent Policies**
2. Click your policy name
3. Click **Add integration**
4. Popular security integrations:
   - **Auditd**: Linux security audit daemon
   - **File Integrity Monitoring (FIM)**: Detect file changes
   - **Osquery**: Query OS information like a database
   - **Packet Capture**: Network traffic analysis
   - **Custom Logs**: Monitor specific log files

### Example: Adding Auditd

1. Install auditd on target: `sudo apt-get install auditd`
2. In Kibana Fleet, add "Auditd Manager" integration
3. Agent automatically starts collecting audit events

## 🐛 Troubleshooting

### Agent Not Appearing in Fleet

```bash
# Check if agent is running
sudo systemctl status elastic-agent

# Check agent logs for errors
sudo elastic-agent logs

# Verify network connectivity to Fleet Server
telnet <logging-server-ip> 8220

# Check credentials file exists on control machine
cat ../../.fleet_credentials.yml
```

### Agent Shows "Offline"

```bash
# Restart agent
sudo systemctl restart elastic-agent

# Check for errors
sudo journalctl -u elastic-agent -n 50

# Verify Fleet Server is accessible
curl -k https://<logging-server-ip>:8220/api/status
```

### No Data Appearing in Elasticsearch

```bash
# Check agent components
sudo elastic-agent status

# View agent logs
sudo elastic-agent logs

# Check if policy is applied
# In Kibana: Fleet → Agents → Click agent → View policy
```

### Enrollment Failed

Common causes:

1. **Logging server not deployed**: Run logging playbook first
2. **Network connectivity**: Check firewall rules, security groups
3. **Wrong enrollment token**: Re-deploy logging server to generate new token
4. **Port 8220 blocked**: Ensure target can reach logging server

```bash
# Test connectivity
nc -zv <logging-server-ip> 8220

# Check credentials file
cat ../../.fleet_credentials.yml
```

### High Resource Usage

If agent is using too much CPU/memory:

1. **Reduce log collection frequency**:
   - In Fleet policy, adjust collection intervals

2. **Limit data types**:
   - Disable unnecessary integrations
   - Filter specific log paths

3. **Optimize system**:
   - Add more RAM
   - Reduce other running services

## 🔄 Agent Management

### Update Agent

```bash
# Via Fleet (recommended)
# In Kibana: Fleet → Agents → Select agents → Actions → Upgrade agent

# Manual update
sudo elastic-agent upgrade 9.1.5
```

### Restart Agent

```bash
sudo systemctl restart elastic-agent
```

### View Agent Configuration

```bash
sudo elastic-agent inspect
```

### Unenroll Agent

```bash
# Via Kibana
# Fleet → Agents → Select agent → Actions → Unenroll

# Or on target machine
sudo elastic-agent unenroll
```

### Uninstall Agent

```bash
sudo elastic-agent uninstall
```

## 🛡️ Security Considerations

### Agent Permissions

The agent runs with root/sudo privileges to collect system-level data. This is necessary but should be carefully managed:

- Agents should only connect to trusted Fleet Servers
- Use TLS certificate verification in production
- Regularly update agents to patch security issues

### Network Security

- Restrict port 8220 access to only target machine IPs
- Use VPN or private networks when possible
- Enable TLS for Fleet Server communications

### Data Privacy

Logs may contain sensitive information:

- Configure data filtering in Fleet policies
- Use field exclusions for PII data
- Implement data retention policies in Elasticsearch

## 📚 Additional Resources

- [Elastic Agent Documentation](https://www.elastic.co/guide/en/fleet/current/elastic-agent-installation.html)
- [Fleet and Agent Guide](https://www.elastic.co/guide/en/fleet/current/index.html)
- [Integrations Library](https://www.elastic.co/integrations)
- [Agent Troubleshooting](https://www.elastic.co/guide/en/fleet/current/fleet-troubleshooting.html)

## 🚀 Advanced Usage

### Deploy to Specific Targets

```bash
# Deploy to only certain IPs
ansible-playbook -i target_linux.ini --limit "10.0.2.10,10.0.2.11" main.yml
```

### Parallel Deployment

Ansible runs in parallel by default (5 hosts at a time). To change:

```bash
# Deploy to 10 hosts at once
ansible-playbook -i target_linux.ini -f 10 main.yml
```

### Different Policies per Target

To assign different Fleet policies:

1. Create multiple policies in Kibana Fleet
2. Tag targets in inventory:
   ```ini
   [target_linux_webservers]
   10.0.2.10
   
   [target_linux_databases]
   10.0.2.20
   ```
3. Modify playbook to use different enrollment tokens per group

## 📊 Monitoring Best Practices

1. **Start Small**: Begin with basic system logs and metrics
2. **Add Gradually**: Add more integrations as needed
3. **Test Policies**: Test new policies on one agent first
4. **Monitor Performance**: Watch agent resource usage
5. **Review Data**: Regularly check what data is being collected
6. **Clean Up**: Remove unnecessary data streams

## 🔄 Scaling Considerations

As you add more target machines:

- Monitor logging server resources
- Consider adding more Elasticsearch nodes for storage
- Use multiple Fleet Servers for high availability
- Implement data retention policies
- Use index lifecycle management (ILM)

## 📞 Support

For issues or questions:
1. Check agent logs: `sudo elastic-agent logs`
2. Review Fleet UI for agent status
3. Consult Elastic's official documentation
4. Check network connectivity and firewall rules
