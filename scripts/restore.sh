#!/bin/bash

# Restore Script for Telegram Bot Security Improvements
# Restores data, configuration, and logs from backups

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/telegram-bot}"
DATA_DIR="${DATA_DIR:-/var/lib/telegram-bot}"
LOG_DIR="${LOG_DIR:-/var/log/telegram-bot}"
CONFIG_DIR="${CONFIG_DIR:-/etc/telegram-bot}"
INSTALL_DIR="${INSTALL_DIR:-/opt/telegram-bot}"

# Bot user and group
BOT_USER="${BOT_USER:-telegram-bot}"
BOT_GROUP="${BOT_GROUP:-telegram-bot}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

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

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}

# List available backups
list_backups() {
    log "Available backups in $BACKUP_DIR:"
    echo
    
    if [[ ! -d "$BACKUP_DIR" ]]; then
        error "Backup directory not found: $BACKUP_DIR"
    fi
    
    # List comprehensive backups
    echo "Comprehensive Backups:"
    echo "====================="
    find "$BACKUP_DIR" -name "comprehensive_backup_*.tar.gz" -printf '%T+ %p %s bytes\n' 2>/dev/null | \
    sort -r | head -10 | while read -r line; do
        echo "  $line"
    done
    
    echo
    echo "Individual Backups:"
    echo "=================="
    
    # List data backups
    echo "Data backups:"
    find "$BACKUP_DIR" -name "data_backup_*.tar.gz" -printf '%T+ %p %s bytes\n' 2>/dev/null | \
    sort -r | head -5 | while read -r line; do
        echo "  $line"
    done
    
    # List config backups
    echo "Config backups:"
    find "$BACKUP_DIR" -name "config_backup_*.tar.gz" -printf '%T+ %p %s bytes\n' 2>/dev/null | \
    sort -r | head -5 | while read -r line; do
        echo "  $line"
    done
    
    # List log backups
    echo "Log backups:"
    find "$BACKUP_DIR" -name "logs_backup_*.tar.gz" -printf '%T+ %p %s bytes\n' 2>/dev/null | \
    sort -r | head -5 | while read -r line; do
        echo "  $line"
    done
}

# Verify backup file
verify_backup() {
    local backup_file="$1"
    
    if [[ ! -f "$backup_file" ]]; then
        error "Backup file not found: $backup_file"
    fi
    
    log "Verifying backup file: $(basename "$backup_file")"
    
    if ! tar -tzf "$backup_file" >/dev/null 2>&1; then
        error "Backup file is corrupted: $backup_file"
    fi
    
    log "Backup file verification passed"
}

# Stop bot service
stop_bot_service() {
    log "Stopping bot service..."
    
    if systemctl is-active --quiet telegram-bot; then
        systemctl stop telegram-bot
        log "Bot service stopped"
    else
        info "Bot service is not running"
    fi
}

# Start bot service
start_bot_service() {
    log "Starting bot service..."
    
    systemctl start telegram-bot
    
    # Wait a moment and check status
    sleep 3
    if systemctl is-active --quiet telegram-bot; then
        log "Bot service started successfully"
    else
        error "Failed to start bot service. Check logs: journalctl -u telegram-bot"
    fi
}

# Create backup of current state
backup_current_state() {
    log "Creating backup of current state before restore..."
    
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local pre_restore_backup="$BACKUP_DIR/pre_restore_backup_$timestamp.tar.gz"
    
    # Create temporary directory
    local temp_dir=$(mktemp -d)
    
    # Backup current data
    if [[ -d "$DATA_DIR" ]]; then
        mkdir -p "$temp_dir/data"
        cp -r "$DATA_DIR"/* "$temp_dir/data/" 2>/dev/null || true
    fi
    
    # Backup current config
    if [[ -d "$CONFIG_DIR" ]]; then
        mkdir -p "$temp_dir/config"
        cp -r "$CONFIG_DIR"/* "$temp_dir/config/" 2>/dev/null || true
    fi
    
    # Create backup archive
    tar -czf "$pre_restore_backup" -C "$temp_dir" .
    
    # Clean up
    rm -rf "$temp_dir"
    
    log "Current state backed up to: $(basename "$pre_restore_backup")"
}

# Restore data files
restore_data() {
    local backup_file="$1"
    
    log "Restoring data files from: $(basename "$backup_file")"
    
    verify_backup "$backup_file"
    
    # Create data directory if it doesn't exist
    mkdir -p "$DATA_DIR"
    
    # Clear existing data (with confirmation)
    if [[ -n "$(ls -A "$DATA_DIR" 2>/dev/null)" ]]; then
        warn "Data directory is not empty. Contents will be replaced."
        if [[ "$FORCE_RESTORE" != "true" ]]; then
            read -p "Continue? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                error "Restore cancelled by user"
            fi
        fi
        rm -rf "$DATA_DIR"/*
    fi
    
    # Extract backup
    tar -xzf "$backup_file" -C "$DATA_DIR"
    
    # Set correct permissions
    chown -R "$BOT_USER:$BOT_GROUP" "$DATA_DIR"
    chmod -R 750 "$DATA_DIR"
    
    log "Data files restored successfully"
}

# Restore configuration files
restore_config() {
    local backup_file="$1"
    
    log "Restoring configuration files from: $(basename "$backup_file")"
    
    verify_backup "$backup_file"
    
    # Create config directory if it doesn't exist
    mkdir -p "$CONFIG_DIR"
    
    # Clear existing config (with confirmation)
    if [[ -n "$(ls -A "$CONFIG_DIR" 2>/dev/null)" ]]; then
        warn "Configuration directory is not empty. Contents will be replaced."
        if [[ "$FORCE_RESTORE" != "true" ]]; then
            read -p "Continue? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                error "Restore cancelled by user"
            fi
        fi
        rm -rf "$CONFIG_DIR"/*
    fi
    
    # Extract backup
    tar -xzf "$backup_file" -C "$CONFIG_DIR"
    
    # Set correct permissions
    chown -R root:root "$CONFIG_DIR"
    chmod -R 755 "$CONFIG_DIR"
    chmod 600 "$CONFIG_DIR"/.env* 2>/dev/null || true
    
    log "Configuration files restored successfully"
}

# Restore log files
restore_logs() {
    local backup_file="$1"
    
    log "Restoring log files from: $(basename "$backup_file")"
    
    verify_backup "$backup_file"
    
    # Create log directory if it doesn't exist
    mkdir -p "$LOG_DIR"
    
    # Extract backup
    tar -xzf "$backup_file" -C "$LOG_DIR"
    
    # Set correct permissions
    chown -R "$BOT_USER:$BOT_GROUP" "$LOG_DIR"
    chmod -R 750 "$LOG_DIR"
    
    log "Log files restored successfully"
}

# Restore comprehensive backup
restore_comprehensive() {
    local backup_file="$1"
    
    log "Restoring comprehensive backup from: $(basename "$backup_file")"
    
    verify_backup "$backup_file"
    
    # Create temporary directory for extraction
    local temp_dir=$(mktemp -d)
    
    # Extract backup
    tar -xzf "$backup_file" -C "$temp_dir"
    
    # Restore data
    if [[ -d "$temp_dir/data" ]]; then
        log "Restoring data from comprehensive backup..."
        mkdir -p "$DATA_DIR"
        rm -rf "$DATA_DIR"/*
        cp -r "$temp_dir/data"/* "$DATA_DIR/" 2>/dev/null || true
        chown -R "$BOT_USER:$BOT_GROUP" "$DATA_DIR"
        chmod -R 750 "$DATA_DIR"
    fi
    
    # Restore configuration
    if [[ -d "$temp_dir/config" ]]; then
        log "Restoring configuration from comprehensive backup..."
        mkdir -p "$CONFIG_DIR"
        rm -rf "$CONFIG_DIR"/*
        cp -r "$temp_dir/config"/* "$CONFIG_DIR/" 2>/dev/null || true
        chown -R root:root "$CONFIG_DIR"
        chmod -R 755 "$CONFIG_DIR"
        chmod 600 "$CONFIG_DIR"/.env* 2>/dev/null || true
    fi
    
    # Restore application files (optional)
    if [[ -d "$temp_dir/application" && "$RESTORE_APPLICATION" == "true" ]]; then
        warn "Restoring application files from backup..."
        warn "This will overwrite the current application installation!"
        if [[ "$FORCE_RESTORE" != "true" ]]; then
            read -p "Continue? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                cp -r "$temp_dir/application"/* "$INSTALL_DIR/" 2>/dev/null || true
                chown -R root:root "$INSTALL_DIR"
                chmod -R 755 "$INSTALL_DIR"
            fi
        fi
    fi
    
    # Clean up
    rm -rf "$temp_dir"
    
    log "Comprehensive backup restored successfully"
}

# Validate restore
validate_restore() {
    log "Validating restore..."
    
    # Check data directory
    if [[ -d "$DATA_DIR" ]]; then
        log "✓ Data directory exists"
        if [[ -n "$(ls -A "$DATA_DIR" 2>/dev/null)" ]]; then
            log "✓ Data directory contains files"
        else
            warn "Data directory is empty"
        fi
    else
        warn "Data directory not found"
    fi
    
    # Check configuration directory
    if [[ -d "$CONFIG_DIR" ]]; then
        log "✓ Configuration directory exists"
        if [[ -f "$CONFIG_DIR/.env" ]]; then
            log "✓ Environment configuration found"
        else
            warn "Environment configuration not found"
        fi
    else
        warn "Configuration directory not found"
    fi
    
    # Check permissions
    if [[ -d "$DATA_DIR" ]]; then
        local data_owner=$(stat -c '%U:%G' "$DATA_DIR")
        if [[ "$data_owner" == "$BOT_USER:$BOT_GROUP" ]]; then
            log "✓ Data directory permissions correct"
        else
            warn "Data directory permissions incorrect: $data_owner (expected: $BOT_USER:$BOT_GROUP)"
        fi
    fi
    
    log "Validation completed"
}

# Show usage information
usage() {
    echo "Usage: $0 [OPTIONS] COMMAND [BACKUP_FILE]"
    echo
    echo "Commands:"
    echo "  list                    List available backups"
    echo "  restore-data FILE       Restore data files from backup"
    echo "  restore-config FILE     Restore configuration files from backup"
    echo "  restore-logs FILE       Restore log files from backup"
    echo "  restore-comprehensive FILE  Restore comprehensive backup"
    echo "  restore-latest          Restore from latest comprehensive backup"
    echo
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -f, --force             Force restore without confirmation"
    echo "  --no-backup             Skip backing up current state"
    echo "  --no-service-restart    Don't restart the bot service"
    echo "  --restore-application   Include application files in comprehensive restore"
    echo
    echo "Environment Variables:"
    echo "  BACKUP_DIR              Backup directory (default: /var/backups/telegram-bot)"
    echo "  DATA_DIR                Data directory (default: /var/lib/telegram-bot)"
    echo "  CONFIG_DIR              Config directory (default: /etc/telegram-bot)"
    echo "  BOT_USER                Bot user (default: telegram-bot)"
    echo "  BOT_GROUP               Bot group (default: telegram-bot)"
    echo
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 restore-comprehensive /var/backups/telegram-bot/comprehensive_backup_20231201_120000.tar.gz"
    echo "  $0 restore-latest"
    echo "  $0 restore-data /var/backups/telegram-bot/data_backup_20231201_120000.tar.gz"
}

# Parse command line arguments
FORCE_RESTORE=false
SKIP_BACKUP=false
SKIP_SERVICE_RESTART=false
RESTORE_APPLICATION=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -f|--force)
            FORCE_RESTORE=true
            shift
            ;;
        --no-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --no-service-restart)
            SKIP_SERVICE_RESTART=true
            shift
            ;;
        --restore-application)
            RESTORE_APPLICATION=true
            shift
            ;;
        list)
            list_backups
            exit 0
            ;;
        restore-data)
            COMMAND="restore-data"
            BACKUP_FILE="$2"
            shift 2
            ;;
        restore-config)
            COMMAND="restore-config"
            BACKUP_FILE="$2"
            shift 2
            ;;
        restore-logs)
            COMMAND="restore-logs"
            BACKUP_FILE="$2"
            shift 2
            ;;
        restore-comprehensive)
            COMMAND="restore-comprehensive"
            BACKUP_FILE="$2"
            shift 2
            ;;
        restore-latest)
            COMMAND="restore-latest"
            shift
            ;;
        *)
            error "Unknown option or command: $1"
            ;;
    esac
done

# Check if command was provided
if [[ -z "$COMMAND" ]]; then
    error "No command provided. Use --help for usage information."
fi

# Check root privileges
check_root

# Execute command
case $COMMAND in
    "restore-data")
        if [[ -z "$BACKUP_FILE" ]]; then
            error "Backup file not specified"
        fi
        
        if [[ "$SKIP_SERVICE_RESTART" != true ]]; then
            stop_bot_service
        fi
        
        if [[ "$SKIP_BACKUP" != true ]]; then
            backup_current_state
        fi
        
        restore_data "$BACKUP_FILE"
        validate_restore
        
        if [[ "$SKIP_SERVICE_RESTART" != true ]]; then
            start_bot_service
        fi
        ;;
        
    "restore-config")
        if [[ -z "$BACKUP_FILE" ]]; then
            error "Backup file not specified"
        fi
        
        if [[ "$SKIP_SERVICE_RESTART" != true ]]; then
            stop_bot_service
        fi
        
        if [[ "$SKIP_BACKUP" != true ]]; then
            backup_current_state
        fi
        
        restore_config "$BACKUP_FILE"
        validate_restore
        
        if [[ "$SKIP_SERVICE_RESTART" != true ]]; then
            start_bot_service
        fi
        ;;
        
    "restore-logs")
        if [[ -z "$BACKUP_FILE" ]]; then
            error "Backup file not specified"
        fi
        
        restore_logs "$BACKUP_FILE"
        ;;
        
    "restore-comprehensive")
        if [[ -z "$BACKUP_FILE" ]]; then
            error "Backup file not specified"
        fi
        
        if [[ "$SKIP_SERVICE_RESTART" != true ]]; then
            stop_bot_service
        fi
        
        if [[ "$SKIP_BACKUP" != true ]]; then
            backup_current_state
        fi
        
        restore_comprehensive "$BACKUP_FILE"
        validate_restore
        
        if [[ "$SKIP_SERVICE_RESTART" != true ]]; then
            start_bot_service
        fi
        ;;
        
    "restore-latest")
        # Find latest comprehensive backup
        LATEST_BACKUP=$(find "$BACKUP_DIR" -name "comprehensive_backup_*.tar.gz" -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
        
        if [[ -z "$LATEST_BACKUP" ]]; then
            error "No comprehensive backups found in $BACKUP_DIR"
        fi
        
        log "Latest backup found: $(basename "$LATEST_BACKUP")"
        
        if [[ "$SKIP_SERVICE_RESTART" != true ]]; then
            stop_bot_service
        fi
        
        if [[ "$SKIP_BACKUP" != true ]]; then
            backup_current_state
        fi
        
        restore_comprehensive "$LATEST_BACKUP"
        validate_restore
        
        if [[ "$SKIP_SERVICE_RESTART" != true ]]; then
            start_bot_service
        fi
        ;;
        
    *)
        error "Unknown command: $COMMAND"
        ;;
esac

log "Restore operation completed successfully"