# CogniMail Production Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying CogniMail Anti-Phishing & Spam Filtering System to production environments. Follow these instructions carefully to ensure a secure and reliable deployment.

**Estimated Deployment Time:** 30-45 minutes  
**Skill Level Required:** Intermediate to Advanced

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Server Requirements](#server-requirements)
3. [Pre-Deployment Checklist](#pre-deployment-checklist)
4. [Installation Steps](#installation-steps)
5. [Configuration](#configuration)
6. [DNS Setup](#dns-setup)
7. [SSL/TLS Certificates](#ssltls-certificates)
8. [Starting Services](#starting-services)
9. [Post-Deployment Verification](#post-deployment-verification)
10. [Monitoring Setup](#monitoring-setup)
11. [Backup Strategy](#backup-strategy)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Operating System:** Ubuntu 22.04 LTS or later (recommended)
- **Docker:** v24.0+ with Docker Compose v2.20+
- **Git:** v2.34+
- **Domain:** Registered domain with DNS access
- **SSL Certificate:** Let's Encrypt (recommended) or commercial cert

### Required Access

- Root or sudo access to server
- DNS management access
- Email service account (for outbound SMTP if using relay mode)
- GitHub repository access

### Required Knowledge

- Linux command line basics
- Docker and Docker Compose
- DNS record management
- Basic networking concepts

---

## Server Requirements

### Minimum Specifications

| Component | Minimum | Recommended | Production |
|-----------|---------|-------------|------------|
| CPU | 4 cores | 8 cores | 16 cores |
| RAM | 8 GB | 16 GB | 32 GB |
| Storage | 50 GB SSD | 100 GB SSD | 500 GB NVMe |
| Network | 100 Mbps | 1 Gbps | 10 Gbps |

### Port Requirements

| Port | Service | Access | Required |
|------|---------|--------|----------|
| 25 | SMTP | Public | Yes |
| 80 | HTTP | Public | Yes (redirect to HTTPS) |
| 443 | HTTPS | Public | Yes |
| 22 | SSH | Restricted | Yes (management) |

**Firewall Rules:**
```bash
# Allow SSH (restrict to your IP)
sudo ufw allow from YOUR_IP to any port 22

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow SMTP
sudo ufw allow 25/tcp

# Enable firewall
sudo ufw enable
```

---

## Pre-Deployment Checklist

### ☐ Infrastructure

- [ ] VPS/Server provisioned and accessible
- [ ] Domain name registered and configured
- [ ] DNS access available
- [ ] Firewall configured
- [ ] SSH key authentication set up
- [ ] Backup solution planned

### ☐ Security

- [ ] Strong passwords generated
- [ ] Secrets management strategy defined
- [ ] SSL/TLS certificate obtained
- [ ] Security policies reviewed
- [ ] Audit logging configured

### ☐ Dependencies

- [ ] Docker installed
- [ ] Docker Compose installed
- [ ] Git installed
- [ ] Certbot installed (for Let's Encrypt)

---

## Installation Steps

### Step 1: Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y git curl wget ufw certbot python3-certbot-nginx

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install -y docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installations
docker --version
docker compose version
git --version
```

### Step 2: Clone Repository

```bash
# Create application directory
sudo mkdir -p /opt/cognimail
sudo chown $USER:$USER /opt/cognimail
cd /opt/cognimail

# Clone repository
git clone https://github.com/wi5nuu/ML-Powered-Anti-Phishing-and-Spam-Filtering.git .

# Checkout production branch (if applicable)
git checkout main
```

### Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Generate strong secrets
python3 -c "import secrets; print('DASHBOARD_SECRET_KEY=' + secrets.token_hex(32))" >> .env.tmp
python3 -c "import secrets; print('DB_PASSWORD=' + secrets.token_urlsafe(32))" >> .env.tmp

# Edit .env with your configuration
nano .env
```

**Required .env Configuration:**

```bash
# ═══════════════════════════════════════════════════════════════════════════
# CogniMail Production Environment Configuration
# ═══════════════════════════════════════════════════════════════════════════

ENV=production
APP_TIMEZONE=Asia/Jakarta

# Domains
DASHBOARD_DOMAIN=cognimail.yourdomain.com
VITE_MAIL_DOMAIN=yourdomain.com
GRAFANA_DOMAIN=grafana.cognimail.yourdomain.com
PROMETHEUS_DOMAIN=prometheus.cognimail.yourdomain.com
CADDY_TLS_EMAIL=admin@yourdomain.com

# Database (Generate strong password!)
DB_USER=cogniuser
DB_PASSWORD=CHANGE_ME_STRONG_PASSWORD_HERE
POSTGRES_DB=cognimail

# Dashboard Security (Generate with: python3 -c "import secrets; print(secrets.token_hex(32))")
DASHBOARD_SECRET_KEY=CHANGE_ME_64_HEX_CHARS

# SMTP Configuration
SMTP_DOMAIN=cognimail.yourdomain.com
ACCEPTED_MAIL_DOMAINS=yourdomain.com
SMTP_REQUIRE_TLS=true  # CRITICAL: Must be true in production
SMTP_TLS_CERT=/certs/live/cognimail.yourdomain.com/fullchain.pem
SMTP_TLS_KEY=/certs/live/cognimail.yourdomain.com/privkey.pem

# Outbound Email
OUTBOUND_SMTP_MODE=direct
OUTBOUND_HELO_HOSTNAME=cognimail.yourdomain.com

# Superadmin Account
SUPERADMIN_USERNAME=admin
SUPERADMIN_PASSWORD=CHANGE_ME_STRONG_PASSWORD
SUPERADMIN_EMAIL=admin@yourdomain.com

# Monitoring
METRICS_ENABLED=true
GF_SECURITY_ADMIN_PASSWORD=CHANGE_ME_GRAFANA_PASSWORD
```

### Step 4: Set Secure Permissions

```bash
# Restrict .env file access
chmod 600 .env

# Create required directories
mkdir -p certs/live/cognimail.yourdomain.com
mkdir -p logs
mkdir -p data/backups

# Set proper permissions
chmod 755 logs
chmod 700 certs
```

---

## DNS Setup

Configure DNS records for your domain:

### Required DNS Records

```dns
# A Records
cognimail.yourdomain.com.     IN  A     YOUR_SERVER_IP
grafana.cognimail.yourdomain.com.  IN  A     YOUR_SERVER_IP
prometheus.cognimail.yourdomain.com. IN  A     YOUR_SERVER_IP

# MX Record (for receiving emails)
yourdomain.com.               IN  MX    10 cognimail.yourdomain.com.

# SPF Record (for sending emails)
yourdomain.com.               IN  TXT   "v=spf1 ip4:YOUR_SERVER_IP -all"

# DMARC Record
_dmarc.yourdomain.com.        IN  TXT   "v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com"

# DKIM Record (generate key first)
default._domainkey.yourdomain.com. IN TXT "v=DKIM1; k=rsa; p=YOUR_PUBLIC_KEY"
```

### Verify DNS Propagation

```bash
# Check A record
dig cognimail.yourdomain.com +short

# Check MX record
dig yourdomain.com MX +short

# Check SPF
dig yourdomain.com TXT +short | grep spf

# Wait for propagation (can take up to 48 hours, usually <1 hour)
```

---

## SSL/TLS Certificates

### Option 1: Let's Encrypt (Recommended)

```bash
# Stop any running web server on port 80
sudo systemctl stop nginx 2>/dev/null || true

# Obtain certificate
sudo certbot certonly --standalone \
  -d cognimail.yourdomain.com \
  -d grafana.cognimail.yourdomain.com \
  -d prometheus.cognimail.yourdomain.com \
  --email admin@yourdomain.com \
  --agree-tos \
  --non-interactive

# Copy certificates to project directory
sudo cp -r /etc/letsencrypt /opt/cognimail/certs/

# Set permissions
sudo chown -R $USER:$USER /opt/cognimail/certs
chmod 600 /opt/cognimail/certs/live/*/privkey.pem

# Setup auto-renewal
echo "0 2 * * * certbot renew --quiet && docker-compose restart smtp_receiver dashboard" | sudo crontab -
```

### Option 2: Commercial Certificate

```bash
# Place your certificate files
sudo cp your-cert.pem /opt/cognimail/certs/live/cognimail.yourdomain.com/fullchain.pem
sudo cp your-key.pem /opt/cognimail/certs/live/cognimail.yourdomain.com/privkey.pem

# Set permissions
chmod 600 /opt/cognimail/certs/live/*/privkey.pem
```

---

## Starting Services

### Build and Start Services

```bash
cd /opt/cognimail

# Build images (first time only)
docker compose build

# Start all services
docker compose up -d

# Verify all services are running
docker compose ps

# Check logs
docker compose logs -f --tail=100
```

### Initialize Database

```bash
# Wait for PostgreSQL to be ready
sleep 10

# Run database migrations
docker compose run --rm seed

# Verify database
docker compose exec postgres psql -U cogniuser -d cognimail -c "\dt"
```

### Expected Output

```
NAME                COMMAND                  SERVICE          STATUS          PORTS
redis               "redis-server --app…"    redis            Up 30 seconds   127.0.0.1:6379->6379/tcp
postgres            "docker-entrypoint.s…"   postgres         Up 30 seconds   5432/tcp
spamassassin        "spamd -u spamd -s s…"   spamassassin     Up 30 seconds   127.0.0.1:783->783/tcp
classifier          "python -m classifier"   classifier       Up 25 seconds   127.0.0.1:8001->8001/tcp
worker              "python -m worker.pi…"   worker           Up 20 seconds   
smtp_receiver       "python -m worker.sm…"   smtp_receiver    Up 20 seconds   0.0.0.0:25->25/tcp
dashboard           "uvicorn dashboard.a…"   dashboard        Up 15 seconds   127.0.0.1:8080->8080/tcp
prometheus          "prometheus --config…"   prometheus       Up 10 seconds   127.0.0.1:9090->9090/tcp
grafana             "/run.sh"                grafana          Up 10 seconds   127.0.0.1:3000->3000/tcp
```

---

## Post-Deployment Verification

### Step 1: Health Checks

```bash
# Check API health
curl http://localhost:8080/api/health

# Expected response:
# {"status":"healthy","services":{"database":"connected","redis":"connected"}}

# Check classifier
curl http://localhost:8001/health

# Check SMTP
telnet localhost 25
# Type: QUIT
```

### Step 2: Test Email Flow

```bash
# Send test email to your domain
echo "Subject: Test Email

This is a test email." | sendmail test@yourdomain.com

# Check logs
docker compose logs smtp_receiver | tail -20
docker compose logs worker | tail -20

# Verify in dashboard at https://cognimail.yourdomain.com
```

### Step 3: Access Dashboard

1. Open browser: `https://cognimail.yourdomain.com`
2. Login with superadmin credentials from .env
3. Verify:
   - Dashboard loads correctly
   - No JavaScript errors in console
   - Email inbox shows test email
   - Statistics are updating

### Step 4: Security Verification

```bash
# Check SSL/TLS grade
curl https://www.ssllabs.com/ssltest/analyze.html?d=cognimail.yourdomain.com

# Check security headers
curl -I https://cognimail.yourdomain.com | grep -E "X-Frame|X-Content|Strict-Transport"

# Verify port exposure
nmap -p 25,80,443,8080,5432,6379 localhost
# Should show: 25, 80, 443 open; others closed to external
```

---

## Monitoring Setup

### Prometheus

Access: `https://prometheus.cognimail.yourdomain.com`

**Key Metrics to Monitor:**
- `email_processing_duration_seconds`
- `threat_detection_total`
- `database_connections_active`
- `redis_connected_clients`

### Grafana

Access: `https://grafana.cognimail.yourdomain.com`

**Default Credentials:**
- Username: `admin`
- Password: From `GF_SECURITY_ADMIN_PASSWORD` in .env

**Setup Dashboard:**
1. Add Prometheus data source: `http://prometheus:9090`
2. Import dashboard from `monitoring/grafana-dashboard.json`
3. Configure alerts for critical metrics

### Log Monitoring

```bash
# Real-time logs
docker compose logs -f

# Specific service
docker compose logs -f smtp_receiver

# Save logs to file
docker compose logs > /opt/cognimail/logs/services-$(date +%Y%m%d).log

# Setup log rotation
cat > /etc/logrotate.d/cognimail <<EOF
/opt/cognimail/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 $USER $USER
}
EOF
```

---

## Backup Strategy

### Database Backup

```bash
# Create backup script
cat > /opt/cognimail/scripts/backup-db.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/opt/cognimail/data/backups"
DATE=$(date +%Y%m%d_%H%M%S)
docker compose exec -T postgres pg_dump -U cogniuser cognimail | gzip > "${BACKUP_DIR}/cognimail_${DATE}.sql.gz"
find ${BACKUP_DIR} -name "cognimail_*.sql.gz" -mtime +30 -delete
EOF

chmod +x /opt/cognimail/scripts/backup-db.sh

# Schedule daily backups
echo "0 3 * * * /opt/cognimail/scripts/backup-db.sh" | crontab -
```

### Full System Backup

```bash
# Backup entire application
tar -czf /backup/cognimail-$(date +%Y%m%d).tar.gz \
  --exclude='node_modules' \
  --exclude='.venv' \
  --exclude='data/backups' \
  /opt/cognimail

# Sync to remote backup server (recommended)
rsync -avz /backup/ backup-server:/backups/cognimail/
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check service logs
docker compose logs service_name

# Common issues:
# 1. Port already in use
sudo lsof -i :25  # Find process using port
sudo kill -9 PID  # Kill the process

# 2. Permission denied
sudo chown -R $USER:$USER /opt/cognimail
chmod 600 .env

# 3. Certificate issues
ls -la /opt/cognimail/certs/live/*/
sudo certbot renew --dry-run
```

### Emails Not Receiving

```bash
# 1. Check SMTP service
docker compose logs smtp_receiver | grep ERROR

# 2. Verify DNS MX record
dig yourdomain.com MX +short

# 3. Test SMTP port
telnet cognimail.yourdomain.com 25

# 4. Check firewall
sudo ufw status | grep 25
```

### Database Connection Issues

```bash
# Check PostgreSQL status
docker compose exec postgres pg_isready

# Check connections
docker compose exec postgres psql -U cogniuser -d cognimail -c "SELECT count(*) FROM pg_stat_activity;"

# Reset database (CAUTION: Data loss!)
docker compose down -v
docker compose up -d
docker compose run --rm seed
```

### High CPU/Memory Usage

```bash
# Check resource usage
docker stats

# Identify problematic container
docker compose top

# Adjust resource limits in docker-compose.yml
# Add under each service:
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
```

### Performance Issues

```bash
# Check classifier processing time
docker compose exec classifier python -c "from classifier.predict import predict_email; import time; start=time.time(); predict_email('test email'); print(f'Time: {time.time()-start:.2f}s')"

# Monitor queue depth
docker compose exec redis redis-cli llen email_pipeline

# Check database query performance
docker compose exec postgres psql -U cogniuser -d cognimail -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

---

## Maintenance

### Regular Tasks

**Daily:**
- Monitor dashboard for anomalies
- Review threat detection logs
- Check service health endpoints

**Weekly:**
- Review audit logs
- Update threat intelligence feeds
- Backup verification

**Monthly:**
- Update dependencies: `docker compose pull && docker compose up -d`
- Review user accounts and permissions
- Security audit
- Performance optimization

**Quarterly:**
- Full security assessment
- Disaster recovery drill
- Capacity planning review

### Updates and Upgrades

```bash
# Backup before updating
/opt/cognimail/scripts/backup-db.sh

# Pull latest code
cd /opt/cognimail
git fetch origin
git checkout tags/v1.x.x  # Or specific version

# Rebuild and restart
docker compose build --no-cache
docker compose down
docker compose up -d

# Run migrations if needed
docker compose run --rm seed

# Verify deployment
curl http://localhost:8080/api/health
```

---

## Support and Resources

**Documentation:**
- [Security Policy](SECURITY.md)
- [API Documentation](API_DOCUMENTATION.md)
- [GitHub Repository](https://github.com/wi5nuu/ML-Powered-Anti-Phishing-and-Spam-Filtering)

**Community:**
- GitHub Issues: Report bugs and request features
- Email: support@yourcompany.com

**Professional Support:**
- Enterprise Support: Available for production deployments
- Security Audits: Professional security assessment services
- Custom Development: Feature customization and integration

---

## Success Metrics

Your deployment is successful when:

- ✅ All 9 services running and healthy
- ✅ SMTP receiving emails on port 25
- ✅ Dashboard accessible via HTTPS
- ✅ SSL/TLS grade A or higher
- ✅ All security headers present
- ✅ Threat detection working (test with known phishing email)
- ✅ Monitoring dashboards showing data
- ✅ Backups completing successfully
- ✅ 73/74 tests passing

**Congratulations!** 🎉 Your CogniMail system is now deployed and protecting your organization from phishing and spam threats.

---

**Last Updated:** 2026-07-29  
**Version:** 1.0  
**Deployment Status:** Production Ready
