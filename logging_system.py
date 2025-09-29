# -*- coding: utf-8 -*-

"""
Enhanced Logging System for Telegram Bot Security Improvements
Provides structured logging with file rotation, different levels, and security event tracking
"""

import logging
import logging.handlers
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

from config_manager import LoggingConfig


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: str
    level: str
    logger_name: str
    message: str
    user_id: Optional[int] = None
    action: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def format(self, record):
        # Create base log entry
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created).isoformat(),
            level=record.levelname,
            logger_name=record.name,
            message=record.getMessage()
        )
        
        # Add additional fields if present
        if hasattr(record, 'user_id'):
            log_entry.user_id = record.user_id
        if hasattr(record, 'action'):
            log_entry.action = record.action
        if hasattr(record, 'context'):
            log_entry.context = record.context
        if hasattr(record, 'error_type'):
            log_entry.error_type = record.error_type
        if hasattr(record, 'stack_trace'):
            log_entry.stack_trace = record.stack_trace
        
        # Return JSON formatted log entry
        return json.dumps(asdict(log_entry), ensure_ascii=False, separators=(',', ':'))


class LoggingSystem:
    """
    Enhanced logging system with structured logging, file rotation, and security event tracking.
    """
    
    def __init__(self, config: LoggingConfig):
        """
        Initialize logging system.
        
        Args:
            config: Logging configuration
        """
        self.config = config
        self.loggers: Dict[str, logging.Logger] = {}
        self._setup_loggers()
    
    def _setup_loggers(self) -> None:
        """Setup all loggers with appropriate handlers and formatters."""
        # Ensure log directory exists
        log_dir = Path(self.config.file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup main application logger
        self._setup_main_logger()
        
        # Setup security logger
        self._setup_security_logger()
        
        # Setup error logger
        self._setup_error_logger()
        
        # Setup user action logger
        self._setup_user_action_logger()
    
    def _setup_main_logger(self) -> None:
        """Setup main application logger."""
        logger = logging.getLogger('bot.main')
        logger.setLevel(getattr(logging, self.config.level))
        
        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            filename=self.config.file_path,
            maxBytes=self.config.max_file_size,
            backupCount=self.config.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)
        
        # Console handler for development
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        self.loggers['main'] = logger
    
    def _setup_security_logger(self) -> None:
        """Setup security events logger."""
        logger = logging.getLogger('bot.security')
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        logger.handlers.clear()
        
        # Separate file for security events
        security_log_path = Path(self.config.file_path).parent / 'security.log'
        file_handler = logging.handlers.RotatingFileHandler(
            filename=security_log_path,
            maxBytes=self.config.max_file_size,
            backupCount=self.config.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)
        
        self.loggers['security'] = logger
    
    def _setup_error_logger(self) -> None:
        """Setup error logger."""
        logger = logging.getLogger('bot.errors')
        logger.setLevel(logging.WARNING)
        
        # Remove existing handlers
        logger.handlers.clear()
        
        # Separate file for errors
        error_log_path = Path(self.config.file_path).parent / 'errors.log'
        file_handler = logging.handlers.RotatingFileHandler(
            filename=error_log_path,
            maxBytes=self.config.max_file_size,
            backupCount=self.config.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)
        
        self.loggers['errors'] = logger
    
    def _setup_user_action_logger(self) -> None:
        """Setup user actions logger."""
        logger = logging.getLogger('bot.user_actions')
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        logger.handlers.clear()
        
        # Separate file for user actions
        user_log_path = Path(self.config.file_path).parent / 'user_actions.log'
        file_handler = logging.handlers.RotatingFileHandler(
            filename=user_log_path,
            maxBytes=self.config.max_file_size,
            backupCount=self.config.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)
        
        self.loggers['user_actions'] = logger
    
    def log_user_action(self, user_id: int, action: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log user action.
        
        Args:
            user_id: User ID
            action: Action performed
            context: Additional context data
        """
        logger = self.loggers.get('user_actions')
        if logger:
            logger.info(
                f"User {user_id} performed action: {action}",
                extra={
                    'user_id': user_id,
                    'action': action,
                    'context': context or {}
                }
            )
    
    def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None, 
                  user_id: Optional[int] = None) -> None:
        """
        Log error with full context.
        
        Args:
            error: Exception that occurred
            context: Additional context data
            user_id: User ID if error is user-related
        """
        import traceback
        
        logger = self.loggers.get('errors')
        if logger:
            logger.error(
                f"Error occurred: {str(error)}",
                extra={
                    'user_id': user_id,
                    'error_type': type(error).__name__,
                    'context': context or {},
                    'stack_trace': traceback.format_exc()
                }
            )
    
    def log_security_event(self, event_type: str, description: str, user_id: int,
                          severity: str = 'medium', additional_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log security event.
        
        Args:
            event_type: Type of security event
            description: Event description
            user_id: User ID involved
            severity: Event severity (low, medium, high, critical)
            additional_data: Additional event data
        """
        logger = self.loggers.get('security')
        if logger:
            log_level = {
                'low': logging.INFO,
                'medium': logging.WARNING,
                'high': logging.ERROR,
                'critical': logging.CRITICAL
            }.get(severity.lower(), logging.WARNING)
            
            logger.log(
                log_level,
                f"Security event: {event_type} - {description}",
                extra={
                    'user_id': user_id,
                    'action': event_type,
                    'context': {
                        'severity': severity,
                        'additional_data': additional_data or {}
                    }
                }
            )
    
    def log_info(self, message: str, user_id: Optional[int] = None, 
                 context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log informational message.
        
        Args:
            message: Log message
            user_id: User ID if applicable
            context: Additional context
        """
        logger = self.loggers.get('main')
        if logger:
            logger.info(
                message,
                extra={
                    'user_id': user_id,
                    'context': context or {}
                }
            )
    
    def log_warning(self, message: str, user_id: Optional[int] = None,
                   context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log warning message.
        
        Args:
            message: Log message
            user_id: User ID if applicable
            context: Additional context
        """
        logger = self.loggers.get('main')
        if logger:
            logger.warning(
                message,
                extra={
                    'user_id': user_id,
                    'context': context or {}
                }
            )
    
    def rotate_logs(self) -> None:
        """Manually trigger log rotation for all handlers."""
        for logger in self.loggers.values():
            for handler in logger.handlers:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.doRollover()
    
    def get_logger(self, name: str) -> Optional[logging.Logger]:
        """
        Get logger by name.
        
        Args:
            name: Logger name (main, security, errors, user_actions)
            
        Returns:
            Optional[logging.Logger]: Logger instance or None if not found
        """
        return self.loggers.get(name)
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> None:
        """
        Clean up old log files.
        
        Args:
            days_to_keep: Number of days to keep log files
        """
        import glob
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        log_dir = Path(self.config.file_path).parent
        
        # Find all log files with backup extensions
        for log_file in glob.glob(str(log_dir / "*.log*")):
            try:
                file_path = Path(log_file)
                if file_path.stat().st_mtime < cutoff_date.timestamp():
                    file_path.unlink()
                    self.log_info(f"Deleted old log file: {log_file}")
            except Exception as e:
                self.log_error(e, context={'action': 'cleanup_old_logs', 'file': log_file})