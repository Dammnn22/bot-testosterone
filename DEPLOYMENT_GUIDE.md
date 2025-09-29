# Deployment Guide - Telegram Bot Security Improvements

## Overview

This guide provides comprehensive instructions for deploying the enhanced Telegram bot with security improvements, including environment-specific configurations, security best practices, and monitoring setup.

## Prerequisites

- Python 3.8 or higher
- Telegram Bot Token (obtained from @BotFather)
- Server with at least 512MB RAM and 1GB storage
- SSL certificate (for webhook deployment)

## Installation

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd telegram-bot-security-improvements

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Create environment-specific configuration files:

```bash
# Copy example environment file
cp .env.example .env

# Edit with your configuration
nano .env
```

## Environment-Specific Configurations

### Development Environment

Create `.env.dev`:

```env
# Bot Configuration
TELEGRAM_BOT_TOKEN=your_development_bot_token_here
DEBUG_MODE=true
LOG_LEVEL=DEBUG

# Rate Limiting (more lenient for development)
RATE_LIMIT_PER_MINUTE=20
MAX_RETRIES=5
TIMEOUT_MINUTES=60

# Storage Configuration
DATABASE_FILE_PATH=data/bot_data_dev.json
LOG_FILE_PATH=logs/bot_dev.log

# Cleanup Configuration
DATABASE_BACKUP_INTERVAL=7200
LOG_BACKUP_COUNT=10
```

### Staging Environment

Create `.env.staging`:

```env
# Bot Configuration
TELEGRAM_BOT_TOKEN=your_staging_bot_token_here
DEBUG_MODE=false
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT_PER_MINUTE=15
MAX_RETRIES=3
TIMEOUT_MINUTES=30

# Storage Configuration
DATABASE_FILE_PATH=data/bot_data_staging.json
LOG_FILE_PATH=logs/bot_staging.log

# Security Configuration
DATABASE_BACKUP_INTERVAL=3600
LOG_BACKUP_COUNT=7
LOG_MAX_FILE_SIZE=10485760
```

### Production Environment

Create `.env.prod`:

```env
# Bot Configuration
TELEGRAM_BOT_TOKEN=your_production_bot_token_here
DEBUG_MODE=false
LOG_LEVEL=WARNING

# Rate Limiting (strict for production)
RATE_LIMIT_PER_MINUTE=10
MAX_RETRIES=3
TIMEOUT_MINUTES=30

# Storage Configuration
DATABASE_FILE_PATH=/var/lib/telegram-bot/bot_data.json
LOG_FILE_PATH=/var/log/telegram-bot/bot.log

# Security Configuration
DATABASE_BACKUP_INTERVAL=3600
LOG_BACKUP_COUNT=5
LOG_MAX_FILE_SIZE=5242880
DATABASE_MAX_FILE_SIZE=10485760
```

## Security Best Practices

### 1. Token Security

**Never commit tokens to version control:**

```bash
# Ensure .env files are in .gitignore
echo ".env*" >> .gitignore
echo "*.log" >> .gitignore
echo "data/" >> .gitignore
echo "backups/" >> .gitignore
```

**Use environment variables in production:**

```bash
# Set environment variables on server
export TELEGRAM_BOT_TOKEN="your_production_token"
export LOG_LEVEL="WARNING"
export DEBUG_MODE="false"
```

### 2. File Permissions

Set appropriate file permissions:

```bash
# Make directories
sudo mkdir -p /var/lib/telegram-bot
sudo mkdir -p /var/log/telegram-bot
sudo mkdir -p /etc/telegram-bot

# Set ownership
sudo chown -R telegram-bot:telegram-bot /var/lib/telegram-bot
sudo chown -R telegram-bot:telegram-bot /var/log/telegram-bot

# Set permissions
sudo chmod 750 /var/lib/telegram-bot
sudo chmod 750 /var/log/telegram-bot
sudo chmod 600 /var/lib/telegram-bot/*
sudo chmod 644 /var/log/telegram-bot/*
```

### 3. Network Security

**Firewall Configuration:**

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 443/tcp   # HTTPS (for webhooks)
sudo ufw deny 80/tcp     # Block HTTP
sudo ufw enable
```

**SSL/TLS Configuration:**

For webhook deployment, ensure SSL certificate is properly configured:

```bash
# Generate self-signed certificate for testing
openssl req -newkey rsa:2048 -sha256 -nodes -keyout private.key -x509 -days 365 -out cert.pem

# For production, use Let's Encrypt
sudo certbot --nginx -d your-domain.com
```

### 4. User Management

Create dedicated user for the bot:

```bash
# Create system user
sudo useradd -r -s /bin/false telegram-bot

# Create service directories
sudo mkdir -p /opt/telegram-bot
sudo chown telegram-bot:telegram-bot /opt/telegram-bot
```

## Deployment Methods

### Method 1: Systemd Service (Recommended for Production)

Create systemd service file:

```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

```ini
[Unit]
Description=Telegram Bot Security Improvements
After=network.target

[Service]
Type=simple
User=telegram-bot
Group=telegram-bot
WorkingDirectory=/opt/telegram-bot
Environment=PYTHONPATH=/opt/telegram-bot
EnvironmentFile=/etc/telegram-bot/.env
ExecStart=/opt/telegram-bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/telegram-bot /var/log/telegram-bot

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

### Method 2: Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Create app user
RUN useradd -r -s /bin/false appuser

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data logs backups && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port (if using webhooks)
EXPOSE 8443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

# Run the application
CMD ["python", "main.py"]
```

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  telegram-bot:
    build: .
    container_name: telegram-bot
    restart: unless-stopped
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - DEBUG_MODE=${DEBUG_MODE:-false}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./backups:/app/backups
    networks:
      - bot-network
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp

networks:
  bot-network:
    driver: bridge
```

Deploy with Docker:

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f telegram-bot

# Stop
docker-compose down
```

## Monitoring and Maintenance

### 1. Log Monitoring

Set up log rotation:

```bash
sudo nano /etc/logrotate.d/telegram-bot
```

```
/var/log/telegram-bot/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 telegram-bot telegram-bot
    postrotate
        systemctl reload telegram-bot
    endscript
}
```

### 2. Health Monitoring

Create health check script:

```bash
#!/bin/bash
# /opt/telegram-bot/health-check.sh

LOG_FILE="/var/log/telegram-bot/bot.log"
PID_FILE="/var/run/telegram-bot.pid"

# Check if process is running
if [ ! -f "$PID_FILE" ] || ! kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "ERROR: Bot process not running"
    exit 1
fi

# Check for recent errors in logs
if tail -n 100 "$LOG_FILE" | grep -q "CRITICAL\|ERROR" 2>/dev/null; then
    echo "WARNING: Recent errors found in logs"
    exit 2
fi

echo "OK: Bot is healthy"
exit 0
```

Set up cron job for health checks:

```bash
# Add to crontab
*/5 * * * * /opt/telegram-bot/health-check.sh >> /var/log/telegram-bot/health.log 2>&1
```

### 3. Backup Strategy

Create backup script:

```bash
#!/bin/bash
# /opt/telegram-bot/backup.sh

BACKUP_DIR="/var/backups/telegram-bot"
DATA_DIR="/var/lib/telegram-bot"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup data files
tar -czf "$BACKUP_DIR/data_backup_$DATE.tar.gz" -C "$DATA_DIR" .

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "data_backup_*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/data_backup_$DATE.tar.gz"
```

Schedule daily backups:

```bash
# Add to crontab
0 2 * * * /opt/telegram-bot/backup.sh >> /var/log/telegram-bot/backup.log 2>&1
```

### 4. Performance Monitoring

Monitor system resources:

```bash
# Install monitoring tools
sudo apt install htop iotop nethogs

# Monitor bot performance
htop -p $(pgrep -f "python main.py")

# Monitor disk usage
df -h /var/lib/telegram-bot
du -sh /var/log/telegram-bot/*
```

## Troubleshooting

### Common Issues

1. **Bot not responding:**
   ```bash
   # Check service status
   sudo systemctl status telegram-bot
   
   # Check logs
   sudo journalctl -u telegram-bot -f
   
   # Check network connectivity
   curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"
   ```

2. **Permission errors:**
   ```bash
   # Fix file permissions
   sudo chown -R telegram-bot:telegram-bot /var/lib/telegram-bot
   sudo chmod 750 /var/lib/telegram-bot
   ```

3. **Memory issues:**
   ```bash
   # Check memory usage
   free -h
   ps aux | grep python
   
   # Restart service if needed
   sudo systemctl restart telegram-bot
   ```

### Log Analysis

Analyze security events:

```bash
# Check for security events
grep "Security event" /var/log/telegram-bot/security.log

# Check rate limiting
grep "rate_limit_exceeded" /var/log/telegram-bot/security.log

# Check validation errors
grep "validation_error" /var/log/telegram-bot/errors.log
```

## Security Checklist

- [ ] Bot token stored securely (environment variables)
- [ ] .env files not committed to version control
- [ ] Appropriate file permissions set
- [ ] Firewall configured
- [ ] SSL/TLS enabled for webhooks
- [ ] Dedicated user account created
- [ ] Log rotation configured
- [ ] Backup strategy implemented
- [ ] Health monitoring set up
- [ ] Security logs monitored
- [ ] Rate limiting configured
- [ ] Input validation enabled
- [ ] Error handling implemented

## Support and Maintenance

### Regular Maintenance Tasks

1. **Weekly:**
   - Review security logs
   - Check disk usage
   - Verify backups

2. **Monthly:**
   - Update dependencies
   - Review performance metrics
   - Clean old logs

3. **Quarterly:**
   - Security audit
   - Performance optimization
   - Documentation updates

### Emergency Procedures

1. **Security Incident:**
   - Stop the bot service
   - Review security logs
   - Change bot token if compromised
   - Notify stakeholders

2. **Service Outage:**
   - Check system resources
   - Review error logs
   - Restart service if needed
   - Monitor recovery

For additional support, refer to the project documentation or contact the development team.