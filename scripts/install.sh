#!/bin/bash

# Telegram Bot Security Improvements - Installation Script
# This script automates the installation and setup process

set -e  # Exit on any error

# Configuration
BOT_USER="telegram-bot"
BOT_GROUP="telegram-bot"
INSTALL_DIR="/opt/telegram-bot"
DATA_DIR="/var/lib/telegram-bot"
LOG_DIR="/var/log/telegram-bot"
CONFIG_DIR="/etc/telegram-bot"
BACKUP_DIR="/var/backups/telegram-bot"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}

# Check system requirements
check_requirements() {
    log "Checking system requirements..."
    
    # Check OS
    if ! command -v apt-get &> /dev/null; then
        error "This script requires a Debian/Ubuntu system with apt-get"
    fi
    
    # Check Python version
    if ! python3 --version | grep -E "Python 3\.[8-9]|Python 3\.1[0-9]" &> /dev/null; then
        error "Python 3.8 or higher is required"
    fi
    
    # Check available disk space (at least 1GB)
    AVAILABLE_SPACE=$(df / | awk 'NR==2 {print $4}')
    if [[ $AVAILABLE_SPACE -lt 1048576 ]]; then
        error "At least 1GB of free disk space is required"
    fi
    
    log "System requirements check passed"
}

# Install system dependencies
install_dependencies() {
    log "Installing system dependencies..."
    
    apt-get update
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        curl \
        wget \
        git \
        logrotate \
        mailutils \
        htop \
        iotop \
        nethogs \
        ufw
    
    log "System dependencies installed"
}

# Create system user
create_user() {
    log "Creating system user and group..."
    
    if ! getent group "$BOT_GROUP" > /dev/null 2>&1; then
        groupadd -r "$BOT_GROUP"
        log "Created group: $BOT_GROUP"
    fi
    
    if ! getent passwd "$BOT_USER" > /dev/null 2>&1; then
        useradd -r -g "$BOT_GROUP" -d "$DATA_DIR" -s /bin/false "$BOT_USER"
        log "Created user: $BOT_USER"
    fi
}

# Create directories
create_directories() {
    log "Creating directories..."
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # Set ownership and permissions
    chown -R "$BOT_USER:$BOT_GROUP" "$DATA_DIR"
    chown -R "$BOT_USER:$BOT_GROUP" "$LOG_DIR"
    chown -R "$BOT_USER:$BOT_GROUP" "$BACKUP_DIR"
    chown -R root:root "$INSTALL_DIR"
    chown -R root:root "$CONFIG_DIR"
    
    chmod 750 "$DATA_DIR"
    chmod 750 "$LOG_DIR"
    chmod 750 "$BACKUP_DIR"
    chmod 755 "$INSTALL_DIR"
    chmod 755 "$CONFIG_DIR"
    
    log "Directories created and configured"
}

# Install application
install_application() {
    log "Installing application..."
    
    # Copy application files
    cp -r . "$INSTALL_DIR/"
    
    # Create virtual environment
    cd "$INSTALL_DIR"
    python3 -m venv venv
    
    # Install Python dependencies
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Set permissions
    chown -R root:root "$INSTALL_DIR"
    chmod -R 755 "$INSTALL_DIR"
    chmod +x "$INSTALL_DIR"/scripts/*.sh
    
    log "Application installed"
}

# Configure systemd service
configure_service() {
    log "Configuring systemd service..."
    
    # Copy service file
    cp "$INSTALL_DIR/config/telegram-bot.service" /etc/systemd/system/
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service (but don't start yet)
    systemctl enable telegram-bot
    
    log "Systemd service configured"
}

# Configure log rotation
configure_logrotate() {
    log "Configuring log rotation..."
    
    cat > /etc/logrotate.d/telegram-bot << EOF
$LOG_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $BOT_USER $BOT_GROUP
    postrotate
        systemctl reload telegram-bot || true
    endscript
}
EOF
    
    log "Log rotation configured"
}

# Configure firewall
configure_firewall() {
    log "Configuring firewall..."
    
    # Enable UFW if not already enabled
    if ! ufw status | grep -q "Status: active"; then
        ufw --force enable
    fi
    
    # Allow SSH (be careful not to lock yourself out)
    ufw allow 22/tcp
    
    # Allow HTTPS for webhooks (if needed)
    ufw allow 443/tcp
    
    log "Firewall configured"
}

# Create configuration template
create_config_template() {
    log "Creating configuration template..."
    
    cat > "$CONFIG_DIR/.env.template" << EOF
# Telegram Bot Configuration
# Copy this file to .env and fill in your values

# Bot Token (required)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Environment settings
DEBUG_MODE=false
LOG_LEVEL=INFO

# Rate limiting
RATE_LIMIT_PER_MINUTE=10
MAX_RETRIES=3
TIMEOUT_MINUTES=30

# File paths
DATABASE_FILE_PATH=$DATA_DIR/bot_data.json
LOG_FILE_PATH=$LOG_DIR/bot.log

# Logging configuration
LOG_MAX_FILE_SIZE=5242880
LOG_BACKUP_COUNT=5

# Cleanup configuration
DATABASE_BACKUP_INTERVAL=3600
DATABASE_MAX_FILE_SIZE=10485760
EOF
    
    chmod 600 "$CONFIG_DIR/.env.template"
    
    log "Configuration template created at $CONFIG_DIR/.env.template"
}

# Create maintenance scripts
create_maintenance_scripts() {
    log "Creating maintenance scripts..."
    
    # Daily maintenance script
    cat > "$INSTALL_DIR/daily-maintenance.sh" << 'EOF'
#!/bin/bash
# Daily maintenance script

LOG_FILE="/var/log/telegram-bot/maintenance.log"
echo "$(date): Starting daily maintenance" >> "$LOG_FILE"

# Clean up expired data
cd /opt/telegram-bot
source venv/bin/activate
python3 -c "
from persistence_manager import PersistenceManager
pm = PersistenceManager()
cleaned = pm.cleanup_expired_data()
print(f'$(date): Cleaned up {cleaned} expired entries')
" >> "$LOG_FILE"

# Create backup
/opt/telegram-bot/scripts/backup.sh >> "$LOG_FILE"

echo "$(date): Daily maintenance completed" >> "$LOG_FILE"
EOF
    
    # Backup script
    cat > "$INSTALL_DIR/scripts/backup.sh" << 'EOF'
#!/bin/bash
# Backup script

BACKUP_DIR="/var/backups/telegram-bot"
DATA_DIR="/var/lib/telegram-bot"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup data files
tar -czf "$BACKUP_DIR/data_backup_$DATE.tar.gz" -C "$DATA_DIR" .

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "data_backup_*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/data_backup_$DATE.tar.gz"
EOF
    
    # Health check script
    cat > "$INSTALL_DIR/scripts/health-check.sh" << 'EOF'
#!/bin/bash
# Health check script

LOG_FILE="/var/log/telegram-bot/bot.log"

# Check if service is running
if ! systemctl is-active --quiet telegram-bot; then
    echo "ERROR: Bot service is not running"
    exit 1
fi

# Check for recent errors in logs
if tail -n 100 "$LOG_FILE" | grep -q "CRITICAL\|ERROR" 2>/dev/null; then
    echo "WARNING: Recent errors found in logs"
    exit 2
fi

echo "OK: Bot is healthy"
exit 0
EOF
    
    # Make scripts executable
    chmod +x "$INSTALL_DIR"/*.sh
    chmod +x "$INSTALL_DIR/scripts"/*.sh
    
    log "Maintenance scripts created"
}

# Setup cron jobs
setup_cron() {
    log "Setting up cron jobs..."
    
    # Create cron file for telegram-bot user
    cat > /tmp/telegram-bot-cron << EOF
# Daily maintenance at 2 AM
0 2 * * * $INSTALL_DIR/daily-maintenance.sh

# Health check every 5 minutes
*/5 * * * * $INSTALL_DIR/scripts/health-check.sh >> $LOG_DIR/health.log 2>&1
EOF
    
    # Install cron jobs
    crontab -u "$BOT_USER" /tmp/telegram-bot-cron
    rm /tmp/telegram-bot-cron
    
    log "Cron jobs configured"
}

# Final setup instructions
show_final_instructions() {
    log "Installation completed successfully!"
    echo
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Configure your bot token:"
    echo "   sudo cp $CONFIG_DIR/.env.template $CONFIG_DIR/.env"
    echo "   sudo nano $CONFIG_DIR/.env"
    echo
    echo "2. Start the bot service:"
    echo "   sudo systemctl start telegram-bot"
    echo
    echo "3. Check service status:"
    echo "   sudo systemctl status telegram-bot"
    echo
    echo "4. View logs:"
    echo "   sudo journalctl -u telegram-bot -f"
    echo "   tail -f $LOG_DIR/bot.log"
    echo
    echo -e "${BLUE}Important files and directories:${NC}"
    echo "- Application: $INSTALL_DIR"
    echo "- Configuration: $CONFIG_DIR"
    echo "- Data: $DATA_DIR"
    echo "- Logs: $LOG_DIR"
    echo "- Backups: $BACKUP_DIR"
    echo
    echo -e "${YELLOW}Remember to:${NC}"
    echo "- Set a strong bot token"
    echo "- Configure firewall rules as needed"
    echo "- Set up monitoring and alerting"
    echo "- Test the backup and restore procedures"
}

# Main installation function
main() {
    log "Starting Telegram Bot Security Improvements installation..."
    
    check_root
    check_requirements
    install_dependencies
    create_user
    create_directories
    install_application
    configure_service
    configure_logrotate
    configure_firewall
    create_config_template
    create_maintenance_scripts
    setup_cron
    
    show_final_instructions
}

# Run main function
main "$@"