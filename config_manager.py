# -*- coding: utf-8 -*-

"""
Configuration Manager for Telegram Bot Security Improvements
Handles secure loading of configuration from environment variables and .env files
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    """Configuration data class for bot settings"""
    token: str
    debug_mode: bool = False
    max_retries: int = 3
    timeout_minutes: int = 30
    rate_limit_per_minute: int = 10


@dataclass
class DatabaseConfig:
    """Configuration for data persistence"""
    file_path: str = "bot_data.json"
    backup_interval: int = 3600  # seconds
    max_file_size: int = 10485760  # 10MB


@dataclass
class LoggingConfig:
    """Configuration for logging system"""
    level: str = "INFO"
    file_path: str = "bot.log"
    max_file_size: int = 5242880  # 5MB
    backup_count: int = 5


class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass


class ConfigManager:
    """
    Manages bot configuration with secure token loading and validation.
    Supports loading from environment variables and .env files with fallback mechanisms.
    """
    
    def __init__(self, env_file_path: str = ".env"):
        """
        Initialize configuration manager.
        
        Args:
            env_file_path: Path to .env file (default: ".env")
        """
        self.env_file_path = env_file_path
        self._config_loaded = False
        self._bot_config: Optional[BotConfig] = None
        self._database_config: Optional[DatabaseConfig] = None
        self._logging_config: Optional[LoggingConfig] = None
        
    def load_config(self) -> BotConfig:
        """
        Load and validate bot configuration from environment variables and .env file.
        
        Returns:
            BotConfig: Validated configuration object
            
        Raises:
            ConfigurationError: If configuration is invalid or token is missing
        """
        if self._config_loaded and self._bot_config:
            return self._bot_config
            
        # Load .env file if available and python-dotenv is installed
        self._load_env_file()
        
        # Load bot configuration
        token = self._get_token()
        debug_mode = self._get_bool_env("DEBUG_MODE", False)
        max_retries = self._get_int_env("MAX_RETRIES", 3)
        timeout_minutes = self._get_int_env("TIMEOUT_MINUTES", 30)
        rate_limit_per_minute = self._get_int_env("RATE_LIMIT_PER_MINUTE", 10)
        
        self._bot_config = BotConfig(
            token=token,
            debug_mode=debug_mode,
            max_retries=max_retries,
            timeout_minutes=timeout_minutes,
            rate_limit_per_minute=rate_limit_per_minute
        )
        
        # Validate configuration
        self.validate_config()
        
        self._config_loaded = True
        logger.info("Configuration loaded successfully")
        return self._bot_config
    
    def get_token(self) -> str:
        """
        Get bot token with secure loading and validation.
        
        Returns:
            str: Bot token
            
        Raises:
            ConfigurationError: If token is not found or invalid
        """
        if not self._config_loaded:
            self.load_config()
        return self._bot_config.token
    
    def get_database_config(self) -> DatabaseConfig:
        """
        Get database configuration.
        
        Returns:
            DatabaseConfig: Database configuration object
        """
        if not self._database_config:
            file_path = os.getenv("DATABASE_FILE_PATH", "bot_data.json")
            backup_interval = self._get_int_env("DATABASE_BACKUP_INTERVAL", 3600)
            max_file_size = self._get_int_env("DATABASE_MAX_FILE_SIZE", 10485760)
            
            self._database_config = DatabaseConfig(
                file_path=file_path,
                backup_interval=backup_interval,
                max_file_size=max_file_size
            )
        
        return self._database_config
    
    def get_logging_config(self) -> LoggingConfig:
        """
        Get logging configuration.
        
        Returns:
            LoggingConfig: Logging configuration object
        """
        if not self._logging_config:
            level = os.getenv("LOG_LEVEL", "INFO").upper()
            file_path = os.getenv("LOG_FILE_PATH", "bot.log")
            max_file_size = self._get_int_env("LOG_MAX_FILE_SIZE", 5242880)
            backup_count = self._get_int_env("LOG_BACKUP_COUNT", 5)
            
            self._logging_config = LoggingConfig(
                level=level,
                file_path=file_path,
                max_file_size=max_file_size,
                backup_count=backup_count
            )
        
        return self._logging_config
    
    def validate_config(self) -> bool:
        """
        Validate loaded configuration.
        
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        if not self._bot_config:
            raise ConfigurationError("Configuration not loaded")
        
        # Validate token format (basic check)
        if not self._bot_config.token or len(self._bot_config.token) < 10:
            raise ConfigurationError("Invalid bot token format")
        
        # Validate numeric ranges
        if self._bot_config.max_retries < 1 or self._bot_config.max_retries > 10:
            raise ConfigurationError("max_retries must be between 1 and 10")
        
        if self._bot_config.timeout_minutes < 1 or self._bot_config.timeout_minutes > 1440:
            raise ConfigurationError("timeout_minutes must be between 1 and 1440 (24 hours)")
        
        if self._bot_config.rate_limit_per_minute < 1 or self._bot_config.rate_limit_per_minute > 100:
            raise ConfigurationError("rate_limit_per_minute must be between 1 and 100")
        
        logger.info("Configuration validation passed")
        return True
    
    def _load_env_file(self) -> None:
        """Load environment variables from .env file if available."""
        env_path = Path(self.env_file_path)
        
        if env_path.exists():
            if load_dotenv is None:
                logger.warning("python-dotenv not installed. Install it to use .env files: pip install python-dotenv")
                return
            
            try:
                load_dotenv(env_path)
                logger.info(f"Loaded environment variables from {self.env_file_path}")
            except Exception as e:
                logger.warning(f"Failed to load .env file: {e}")
        else:
            logger.info(f"No .env file found at {self.env_file_path}")
    
    def _get_token(self) -> str:
        """
        Get bot token with fallback mechanisms.
        
        Priority:
        1. TELEGRAM_BOT_TOKEN environment variable
        2. BOT_TOKEN environment variable
        
        Returns:
            str: Bot token
            
        Raises:
            ConfigurationError: If token is not found
        """
        # Try primary environment variable
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if token:
            logger.info("Token loaded from TELEGRAM_BOT_TOKEN environment variable")
            return token.strip()
        
        # Try fallback environment variable
        token = os.getenv("BOT_TOKEN")
        if token:
            logger.info("Token loaded from BOT_TOKEN environment variable")
            return token.strip()
        
        # No token found
        raise ConfigurationError(
            "Bot token not found. Please set TELEGRAM_BOT_TOKEN or BOT_TOKEN environment variable, "
            "or add it to your .env file."
        )
    
    def _get_bool_env(self, key: str, default: bool) -> bool:
        """Get boolean value from environment variable."""
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes', 'on')
    
    def _get_int_env(self, key: str, default: int) -> int:
        """Get integer value from environment variable with validation."""
        value = os.getenv(key)
        if value is None:
            return default
        
        try:
            return int(value)
        except ValueError:
            logger.warning(f"Invalid integer value for {key}: {value}. Using default: {default}")
            return default
    
    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current configuration (excluding sensitive data).
        
        Returns:
            Dict[str, Any]: Configuration summary
        """
        if not self._config_loaded:
            self.load_config()
        
        return {
            "debug_mode": self._bot_config.debug_mode,
            "max_retries": self._bot_config.max_retries,
            "timeout_minutes": self._bot_config.timeout_minutes,
            "rate_limit_per_minute": self._bot_config.rate_limit_per_minute,
            "token_configured": bool(self._bot_config.token),
            "database_config": {
                "file_path": self.get_database_config().file_path,
                "backup_interval": self.get_database_config().backup_interval,
                "max_file_size": self.get_database_config().max_file_size
            },
            "logging_config": {
                "level": self.get_logging_config().level,
                "file_path": self.get_logging_config().file_path,
                "max_file_size": self.get_logging_config().max_file_size,
                "backup_count": self.get_logging_config().backup_count
            }
        }