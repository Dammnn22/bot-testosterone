#!/bin/bash

# Backup Script for Telegram Bot Security Improvements
# Creates backups of data, configuration, and logs

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/telegram-bot}"
DATA_DIR="${DATA_DIR:-/var/lib/telegram-bot}"
LOG_DIR="${LOG_DIR:-/var/log/telegram-bot}"
CONFIG_DIR="${CONFIG_DIR:-/etc/telegram-bot}"
INSTALL_DIR="${INSTALL_DIR:-/opt/telegram-bot}"

# Backup retention (days)
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# Date format for backup files
DATE=$(date +%Y%m%d_%H%M%S)

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

# Create backup directory
create_backup_dir() {
    if [[ ! -d "$BACKUP_DIR" ]]; then
        mkdir -p "$BACKUP_DIR"
        log "Created backup directory: $BACKUP_DIR"
    fi
}

# Backup data files
backup_data() {
    log "Backing up data files..."
    
    if [[ -d "$DATA_DIR" ]]; then
        tar -czf "$BACKUP_DIR/data_backup_$DATE.tar.gz" -C "$DATA_DIR" . 2>/dev/null || {
            warn "No data files found to backup"
            touch "$BACKUP_DIR/data_backup_$DATE.tar.gz"
        }
        log "Data backup completed: data_backup_$DATE.tar.gz"
    else
        warn "Data directory not found: $DATA_DIR"
    fi
}

# Backup configuration files
backup_config() {
    log "Backing up configuration files..."
    
    if [[ -d "$CONFIG_DIR" ]]; then
        tar -czf "$BACKUP_DIR/config_backup_$DATE.tar.gz" -C "$CONFIG_DIR" . 2>/dev/null || {
            warn "No configuration files found to backup"
            touch "$BACKUP_DIR/config_backup_$DATE.tar.gz"
        }
        log "Configuration backup completed: config_backup_$DATE.tar.gz"
    else
        warn "Configuration directory not found: $CONFIG_DIR"
    fi
}

# Backup recent logs
backup_logs() {
    log "Backing up recent logs..."
    
    if [[ -d "$LOG_DIR" ]]; then
        # Only backup logs from the last 7 days to save space
        find "$LOG_DIR" -name "*.log*" -mtime -7 -type f | \
        tar -czf "$BACKUP_DIR/logs_backup_$DATE.tar.gz" -T - 2>/dev/null || {
            warn "No recent log files found to backup"
            touch "$BACKUP_DIR/logs_backup_$DATE.tar.gz"
        }
        log "Logs backup completed: logs_backup_$DATE.tar.gz"
    else
        warn "Log directory not found: $LOG_DIR"
    fi
}

# Create comprehensive backup
create_comprehensive_backup() {
    log "Creating comprehensive backup..."
    
    COMPREHENSIVE_BACKUP="$BACKUP_DIR/comprehensive_backup_$DATE.tar.gz"
    
    # Create temporary directory for comprehensive backup
    TEMP_DIR=$(mktemp -d)
    
    # Copy data
    if [[ -d "$DATA_DIR" ]]; then
        mkdir -p "$TEMP_DIR/data"
        cp -r "$DATA_DIR"/* "$TEMP_DIR/data/" 2>/dev/null || true
    fi
    
    # Copy configuration (excluding sensitive files)
    if [[ -d "$CONFIG_DIR" ]]; then
        mkdir -p "$TEMP_DIR/config"
        cp -r "$CONFIG_DIR"/* "$TEMP_DIR/config/" 2>/dev/null || true
        # Remove sensitive files from backup
        rm -f "$TEMP_DIR/config/.env" 2>/dev/null || true
    fi
    
    # Copy application files (excluding venv and cache)
    if [[ -d "$INSTALL_DIR" ]]; then
        mkdir -p "$TEMP_DIR/application"
        rsync -av --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
              "$INSTALL_DIR"/ "$TEMP_DIR/application/" 2>/dev/null || true
    fi
    
    # Create backup metadata
    cat > "$TEMP_DIR/backup_info.txt" << EOF
Backup Information
==================
Date: $(date)
Hostname: $(hostname)
Bot Version: $(cd "$INSTALL_DIR" && git describe --tags 2>/dev/null || echo "unknown")
Python Version: $(python3 --version)
System: $(uname -a)

Backup Contents:
- Data directory: $DATA_DIR
- Configuration directory: $CONFIG_DIR
- Application directory: $INSTALL_DIR (excluding venv)

Restore Instructions:
1. Stop the bot service: sudo systemctl stop telegram-bot
2. Extract backup: tar -xzf comprehensive_backup_$DATE.tar.gz
3. Restore files to appropriate locations
4. Set correct permissions
5. Start the bot service: sudo systemctl start telegram-bot
EOF
    
    # Create comprehensive backup archive
    tar -czf "$COMPREHENSIVE_BACKUP" -C "$TEMP_DIR" .
    
    # Clean up temporary directory
    rm -rf "$TEMP_DIR"
    
    log "Comprehensive backup completed: comprehensive_backup_$DATE.tar.gz"
}

# Clean up old backups
cleanup_old_backups() {
    log "Cleaning up old backups (keeping last $RETENTION_DAYS days)..."
    
    # Clean up individual backups
    find "$BACKUP_DIR" -name "*_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    
    # Count remaining backups
    BACKUP_COUNT=$(find "$BACKUP_DIR" -name "*_backup_*.tar.gz" | wc -l)
    log "Cleanup completed. $BACKUP_COUNT backup files remaining."
}

# Generate backup report
generate_report() {
    log "Generating backup report..."
    
    REPORT_FILE="$BACKUP_DIR/backup_report_$DATE.txt"
    
    cat > "$REPORT_FILE" << EOF
Backup Report - $(date)
=======================

Backup Location: $BACKUP_DIR
Backup Date: $DATE

Files Created:
$(ls -lh "$BACKUP_DIR"/*_$DATE.tar.gz 2>/dev/null || echo "No backup files created")

Disk Usage:
$(du -sh "$BACKUP_DIR" 2>/dev/null || echo "Unable to calculate disk usage")

Available Space:
$(df -h "$BACKUP_DIR" 2>/dev/null || echo "Unable to check available space")

Total Backups:
$(find "$BACKUP_DIR" -name "*_backup_*.tar.gz" | wc -l) backup files

Oldest Backup:
$(find "$BACKUP_DIR" -name "*_backup_*.tar.gz" -printf '%T+ %p\n' 2>/dev/null | sort | head -1 || echo "No backups found")

Newest Backup:
$(find "$BACKUP_DIR" -name "*_backup_*.tar.gz" -printf '%T+ %p\n' 2>/dev/null | sort | tail -1 || echo "No backups found")
EOF
    
    log "Backup report generated: $REPORT_FILE"
}

# Verify backup integrity
verify_backups() {
    log "Verifying backup integrity..."
    
    FAILED_BACKUPS=0
    
    for backup_file in "$BACKUP_DIR"/*_$DATE.tar.gz; do
        if [[ -f "$backup_file" ]]; then
            if tar -tzf "$backup_file" >/dev/null 2>&1; then
                log "✓ $(basename "$backup_file") - OK"
            else
                error "✗ $(basename "$backup_file") - CORRUPTED"
                FAILED_BACKUPS=$((FAILED_BACKUPS + 1))
            fi
        fi
    done
    
    if [[ $FAILED_BACKUPS -eq 0 ]]; then
        log "All backups verified successfully"
    else
        error "$FAILED_BACKUPS backup(s) failed verification"
    fi
}

# Main backup function
main() {
    log "Starting backup process..."
    
    create_backup_dir
    backup_data
    backup_config
    backup_logs
    create_comprehensive_backup
    cleanup_old_backups
    generate_report
    verify_backups
    
    log "Backup process completed successfully"
    
    # Show summary
    echo
    echo "Backup Summary:"
    echo "==============="
    ls -lh "$BACKUP_DIR"/*_$DATE.tar.gz 2>/dev/null || echo "No backup files created"
    echo
    echo "Total backup size: $(du -sh "$BACKUP_DIR" | cut -f1)"
    echo "Available space: $(df -h "$BACKUP_DIR" | awk 'NR==2 {print $4}')"
}

# Show usage information
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -d, --data-only         Backup only data files"
    echo "  -c, --config-only       Backup only configuration files"
    echo "  -l, --logs-only         Backup only log files"
    echo "  -r, --retention DAYS    Set backup retention period (default: 7)"
    echo "  --no-cleanup            Skip cleanup of old backups"
    echo "  --no-verify             Skip backup verification"
    echo
    echo "Environment Variables:"
    echo "  BACKUP_DIR              Backup directory (default: /var/backups/telegram-bot)"
    echo "  DATA_DIR                Data directory (default: /var/lib/telegram-bot)"
    echo "  LOG_DIR                 Log directory (default: /var/log/telegram-bot)"
    echo "  CONFIG_DIR              Config directory (default: /etc/telegram-bot)"
    echo "  RETENTION_DAYS          Backup retention in days (default: 7)"
}

# Parse command line arguments
BACKUP_TYPE="all"
SKIP_CLEANUP=false
SKIP_VERIFY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -d|--data-only)
            BACKUP_TYPE="data"
            shift
            ;;
        -c|--config-only)
            BACKUP_TYPE="config"
            shift
            ;;
        -l|--logs-only)
            BACKUP_TYPE="logs"
            shift
            ;;
        -r|--retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --no-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        --no-verify)
            SKIP_VERIFY=true
            shift
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Execute based on backup type
case $BACKUP_TYPE in
    "data")
        log "Performing data-only backup..."
        create_backup_dir
        backup_data
        ;;
    "config")
        log "Performing config-only backup..."
        create_backup_dir
        backup_config
        ;;
    "logs")
        log "Performing logs-only backup..."
        create_backup_dir
        backup_logs
        ;;
    "all")
        main
        ;;
esac

# Optional cleanup and verification
if [[ "$SKIP_CLEANUP" != true && "$BACKUP_TYPE" == "all" ]]; then
    cleanup_old_backups
fi

if [[ "$SKIP_VERIFY" != true ]]; then
    verify_backups
fi