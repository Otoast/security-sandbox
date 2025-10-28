# Logging Server Deployment

This directory contains the Ansible playbook and configuration for deploying the centralized logging server in a security sandbox environment.

## 📋 Overview

The logging server is the central hub of the security monitoring infrastructure. It collects, stores, analyzes, and visualizes security events and logs from all target machines.

### Components Deployed

| Component | Port | Purpose |
|-----------|------|---------|
| **Elasticsearch** | 9200 | Search and analytics engine for log storage |
| **Kibana** | 5601 | Web-based UI for visualization and management |
| **Fleet Server** | 8220 | Centralized agent enrollment and policy management |

## 🚀 Quick Start

### 1. Configure Inventory

Edit `logging_server.ini` with your server's IP address:

```ini
[logging_server]
10.0.1.50

[logging_server:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/your-key.pem
```

### 2. Deploy

```bash
cd logging/linux
ansible-playbook -i logging_server.ini main.yml
```

### 3. Access Kibana

After deployment completes (10-15 minutes):

1. Open browser to: `http://<server-ip>:5601`
2. Login with:
   - Username: `elastic`
   - Password: (displayed in playbook output)

## 📁 Files

- `main.yml` - Main Ansible playbook for logging server setup
- `logging_server.ini` - Inventory file (configure your server IP here)
- `README.md` - This file

## 💾 System Requirements

### Minimum

- **RAM**: 4GB
- **CPU**: 2 cores
- **Disk**: 20GB
- **OS**: Ubuntu 20.04+ or RHEL/CentOS 8+

### Recommended

- **RAM**: 8GB
- **CPU**: 4 cores
- **Disk**: 50GB+ (depends on log retention needs)
- **Network**: 1Gbps NIC

### Network Ports

Ensure these ports are open in security groups/firewall:

| Port | Source | Purpose |
|------|--------|---------|
| 22 | Ansible control machine | SSH for deployment |
| 9200 | Internal/trusted IPs only | Elasticsearch API |
| 5601 | Your IP(s) | Kibana web UI |
| 8220 | Target machine IPs | Fleet Server (agent enrollment) |

## 🔧 Configuration

### Changing Versions

Edit `main.yml` variables section:

```yaml
vars:
  elasticsearch_version: "9.1.5"
  kibana_version: "9.1.5"
```

### Network Binding

By default, services bind to `0.0.0.0` (all interfaces). To restrict:

Edit `main.yml` and change:
```yaml
- { regexp: '^network.host:', line: 'network.host: 10.0.1.50' }
```

## 📊 Post-Deployment

### Verify Installation

1. **Check Elasticsearch**:
   ```bash
   curl http://localhost:9200
   ```

2. **Check Kibana**:
   ```bash
   curl http://localhost:5601/api/status
   ```

3. **Check Fleet Server**:
   ```bash
   sudo elastic-agent status
   ```

### Access Credentials

Credentials are automatically saved to:
```
../../.fleet_credentials.yml
```

This file contains:
- Elasticsearch URL and password
- Kibana URL
- Fleet Server URL
- Fleet enrollment token (for target machines)

### View Logs

If troubleshooting is needed:

```bash
# Elasticsearch logs
tail -f /var/log/elasticsearch.log

# Kibana logs
tail -f /var/log/kibana.log

# Fleet Server logs
sudo journalctl -u elastic-agent -f
```

## 🔍 Fleet Server Management

### Check Fleet Status

In Kibana:
1. Go to: **Management → Fleet**
2. View: Fleet Server health and connected agents

### Generate New Enrollment Token

```bash
cd /opt/elasticsearch-9.1.5
./bin/elasticsearch-create-enrollment-token -s fleet-server
```

### View Fleet Server Status

```bash
sudo elastic-agent status
```

## 🛡️ Security Considerations

⚠️ **This configuration is for testing/sandbox environments only!**

For production deployments, implement:

1. **TLS/SSL Encryption**
   - Enable HTTPS for all services
   - Use proper certificates (not self-signed)

2. **Authentication**
   - Enable SAML/LDAP integration
   - Implement role-based access control (RBAC)

3. **Network Security**
   - Use private networks/VPNs
   - Implement firewall rules
   - Bind services to specific interfaces

4. **Data Protection**
   - Enable encryption at rest
   - Configure backup and retention policies
   - Implement audit logging

5. **Service Management**
   - Use systemd services (not nohup)
   - Configure log rotation
   - Set up monitoring and alerting

## 🐛 Troubleshooting

### Elasticsearch Won't Start

```bash
# Check logs
tail -n 100 /var/log/elasticsearch.log

# Check if port is in use
sudo lsof -i :9200

# Check system resources
free -h
df -h
```

### Kibana Can't Connect to Elasticsearch

```bash
# Verify Elasticsearch is running
curl http://localhost:9200

# Check Kibana logs
tail -n 100 /var/log/kibana.log

# Verify network connectivity
telnet localhost 9200
```

### Fleet Server Not Starting

```bash
# Check agent status
sudo elastic-agent status

# View agent logs
sudo elastic-agent logs

# Check certificate issues
ls -la /opt/elasticsearch-9.1.5/config/certs/
```

### Out of Memory

Elasticsearch and Kibana are memory-intensive. If you see OOM errors:

1. Add more RAM to the server
2. Or reduce heap size in config files:
   - Elasticsearch: `jvm.options`
   - Kibana: `kibana.yml` (node.options)

### Ports Already in Use

If ports 9200, 5601, or 8220 are already in use:

```bash
# Find what's using the port
sudo lsof -i :9200

# Kill the process if needed
sudo kill -9 <PID>
```

## 📚 Additional Resources

- [Elasticsearch Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Kibana Documentation](https://www.elastic.co/guide/en/kibana/current/index.html)
- [Fleet and Elastic Agent Guide](https://www.elastic.co/guide/en/fleet/current/index.html)
- [Security Best Practices](https://www.elastic.co/guide/en/elasticsearch/reference/current/security-basic-setup.html)

## 🔄 Updating

To update to a newer version:

1. Update version variables in `main.yml`
2. Re-run the playbook
3. Note: May require migration steps - check Elastic upgrade guides

## 🗑️ Uninstallation

To completely remove the logging server:

```bash
# Stop services
sudo pkill -f elasticsearch
sudo pkill -f kibana
sudo elastic-agent uninstall

# Remove installations
sudo rm -rf /opt/elasticsearch-*
sudo rm -rf /opt/kibana-*
sudo rm -rf /opt/Elastic

# Remove logs
sudo rm -f /var/log/elasticsearch.log
sudo rm -f /var/log/kibana.log

# Remove credentials file (on control machine)
rm ../../.fleet_credentials.yml
```

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Ansible playbook output for specific errors
3. Consult Elastic's official documentation
4. Check system logs for detailed error messages
