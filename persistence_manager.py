# -*- coding: utf-8 -*-

"""
Persistence Manager for Telegram Bot Security Improvements
Handles temporary data storage, automatic cleanup, backup/recovery, and data sanitization
"""

import json
import os
import shutil
import asyncio
import re
import html
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from threading import Lock
import logging

logger = logging.getLogger(__name__)


@dataclass
class DataEntry:
    """Data entry with metadata for TTL and sanitization tracking."""
    user_id: int
    data: Dict[str, Any]
    created_at: datetime
    last_accessed: datetime
    ttl_hours: int = 24
    sanitized: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'user_id': self.user_id,
            'data': self.data,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'ttl_hours': self.ttl_hours,
            'sanitized': self.sanitized
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataEntry':
        """Create instance from dictionary."""
        return cls(
            user_id=data['user_id'],
            data=data['data'],
            created_at=datetime.fromisoformat(data['created_at']),
            last_accessed=datetime.fromisoformat(data['last_accessed']),
            ttl_hours=data.get('ttl_hours', 24),
            sanitized=data.get('sanitized', False)
        )
    
    def is_expired(self) -> bool:
        """Check if data entry has expired based on TTL."""
        expiry_time = self.created_at + timedelta(hours=self.ttl_hours)
        return datetime.now() > expiry_time
    
    def update_access_time(self) -> None:
        """Update last accessed timestamp."""
        self.last_accessed = datetime.now()


class DataSanitizer:
    """Handles data sanitization before storage."""
    
    # Patterns for potentially malicious content
    SCRIPT_PATTERN = re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL)
    HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
    SQL_INJECTION_PATTERNS = [
        re.compile(r'\b(union|select|insert|update|delete|drop|create|alter)\b', re.IGNORECASE),
        re.compile(r'[\'";].*(--)|(\/\*.*\*\/)', re.IGNORECASE),
        re.compile(r'\b(exec|execute|sp_|xp_)\b', re.IGNORECASE)
    ]
    
    @staticmethod
    def sanitize_string(text: str) -> str:
        """
        Sanitize a string by removing potentially malicious content.
        
        Args:
            text: Input string to sanitize
            
        Returns:
            Sanitized string
        """
        if not isinstance(text, str):
            return str(text)
        
        # Remove script tags first
        text = DataSanitizer.SCRIPT_PATTERN.sub('', text)
        
        # Remove HTML tags before escaping
        text = DataSanitizer.HTML_TAG_PATTERN.sub('', text)
        
        # Check for SQL injection patterns and log warnings
        for pattern in DataSanitizer.SQL_INJECTION_PATTERNS:
            if pattern.search(text):
                logger.warning(f"Potential SQL injection attempt detected: {text[:50]}...")
                # Replace suspicious content with safe placeholder
                text = pattern.sub('[FILTERED]', text)
        
        # Escape remaining HTML entities
        text = html.escape(text)
        
        # Limit length to prevent DoS attacks
        if len(text) > 1000:
            text = text[:1000] + "..."
            logger.warning(f"Text truncated due to excessive length")
        
        return text.strip()
    
    @staticmethod
    def sanitize_data(data: Any) -> Any:
        """
        Recursively sanitize data structure.
        
        Args:
            data: Data to sanitize (can be dict, list, string, etc.)
            
        Returns:
            Sanitized data
        """
        if isinstance(data, dict):
            return {key: DataSanitizer.sanitize_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [DataSanitizer.sanitize_data(item) for item in data]
        elif isinstance(data, str):
            return DataSanitizer.sanitize_string(data)
        elif isinstance(data, (int, float, bool)):
            return data
        else:
            # Convert other types to string and sanitize
            return DataSanitizer.sanitize_string(str(data))


class PersistenceManager:
    """
    Manages temporary data storage with automatic cleanup, backup/recovery, and sanitization.
    """
    
    def __init__(self, 
                 data_dir: str = "data",
                 backup_dir: str = "backups",
                 default_ttl_hours: int = 24,
                 cleanup_interval_minutes: int = 60,
                 max_backup_files: int = 10,
                 logging_system=None):
        """
        Initialize the persistence manager.
        
        Args:
            data_dir: Directory for data storage
            backup_dir: Directory for backup files
            default_ttl_hours: Default TTL for data entries
            cleanup_interval_minutes: Interval for automatic cleanup
            max_backup_files: Maximum number of backup files to keep
            logging_system: Optional logging system instance
        """
        self.data_dir = Path(data_dir)
        self.backup_dir = Path(backup_dir)
        self.default_ttl_hours = default_ttl_hours
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self.max_backup_files = max_backup_files
        self.logging_system = logging_system
        
        # Create directories
        self.data_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        
        # File paths
        self.data_file = self.data_dir / "persistence_data.json"
        self.metadata_file = self.data_dir / "metadata.json"
        
        # In-memory storage with thread safety
        self._data_entries: Dict[int, DataEntry] = {}
        self._lock = Lock()
        
        # Data sanitizer
        self.sanitizer = DataSanitizer()
        
        # Load existing data
        self._load_data()
        
        # Start cleanup task
        self._cleanup_task = None
        try:
            self._start_cleanup_task()
        except RuntimeError:
            # No event loop available (e.g., in tests)
            pass
    
    def _log_action(self, message: str, user_id: int = None, context: Dict[str, Any] = None):
        """Log action if logging system is available."""
        if self.logging_system:
            if user_id:
                self.logging_system.log_user_action(user_id, message, context)
            else:
                self.logging_system.log_info(message, context=context)
        else:
            logger.info(f"{message} - User: {user_id} - Context: {context}")    

    def save_user_data(self, user_id: int, data: Dict[str, Any], ttl_hours: Optional[int] = None) -> bool:
        """
        Save user data with sanitization and TTL.
        
        Args:
            user_id: User identifier
            data: Data to save
            ttl_hours: Time to live in hours (uses default if None)
            
        Returns:
            True if data was saved successfully, False otherwise
        """
        try:
            with self._lock:
                # Sanitize data before storage
                sanitized_data = self.sanitizer.sanitize_data(data)
                
                # Create or update data entry
                now = datetime.now()
                ttl = ttl_hours or self.default_ttl_hours
                
                if user_id in self._data_entries:
                    entry = self._data_entries[user_id]
                    entry.data = sanitized_data
                    entry.last_accessed = now
                    entry.ttl_hours = ttl
                    entry.sanitized = True
                else:
                    entry = DataEntry(
                        user_id=user_id,
                        data=sanitized_data,
                        created_at=now,
                        last_accessed=now,
                        ttl_hours=ttl,
                        sanitized=True
                    )
                    self._data_entries[user_id] = entry
                
                # Save to file
                self._save_data()
                
                self._log_action(
                    "data_saved",
                    user_id=user_id,
                    context={"data_size": len(str(sanitized_data)), "ttl_hours": ttl}
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving user data for {user_id}: {e}")
            self._log_action(f"Error saving data: {e}", user_id=user_id)
            return False
    
    def load_user_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Load user data if it exists and hasn't expired.
        
        Args:
            user_id: User identifier
            
        Returns:
            User data if found and valid, None otherwise
        """
        try:
            with self._lock:
                if user_id not in self._data_entries:
                    return None
                
                entry = self._data_entries[user_id]
                
                # Check if data has expired
                if entry.is_expired():
                    del self._data_entries[user_id]
                    self._save_data()
                    self._log_action("expired_data_removed", user_id=user_id)
                    return None
                
                # Update access time
                entry.update_access_time()
                self._save_data()
                
                self._log_action(
                    "data_loaded",
                    user_id=user_id,
                    context={"data_age_hours": (datetime.now() - entry.created_at).total_seconds() / 3600}
                )
                
                return entry.data.copy()
                
        except Exception as e:
            logger.error(f"Error loading user data for {user_id}: {e}")
            self._log_action(f"Error loading data: {e}", user_id=user_id)
            return None
    
    def delete_user_data(self, user_id: int) -> bool:
        """
        Delete user data.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if data was deleted, False if not found or error
        """
        try:
            with self._lock:
                if user_id in self._data_entries:
                    del self._data_entries[user_id]
                    self._save_data()
                    self._log_action("data_deleted", user_id=user_id)
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error deleting user data for {user_id}: {e}")
            self._log_action(f"Error deleting data: {e}", user_id=user_id)
            return False
    
    def cleanup_expired_data(self) -> int:
        """
        Clean up expired data entries.
        
        Returns:
            Number of entries cleaned up
        """
        try:
            with self._lock:
                expired_users = []
                for user_id, entry in self._data_entries.items():
                    if entry.is_expired():
                        expired_users.append(user_id)
                
                for user_id in expired_users:
                    del self._data_entries[user_id]
                
                if expired_users:
                    self._save_data()
                    self._log_action(
                        f"cleanup_completed",
                        context={"cleaned_entries": len(expired_users), "user_ids": expired_users}
                    )
                
                return len(expired_users)
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            self._log_action(f"Error during cleanup: {e}")
            return 0
    
    def get_user_progress(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user progress information including metadata.
        
        Args:
            user_id: User identifier
            
        Returns:
            Progress information with metadata
        """
        try:
            with self._lock:
                if user_id not in self._data_entries:
                    return None
                
                entry = self._data_entries[user_id]
                
                if entry.is_expired():
                    del self._data_entries[user_id]
                    self._save_data()
                    return None
                
                # Calculate progress metadata
                age_hours = (datetime.now() - entry.created_at).total_seconds() / 3600
                remaining_hours = entry.ttl_hours - age_hours
                
                return {
                    'data': entry.data.copy(),
                    'created_at': entry.created_at.isoformat(),
                    'last_accessed': entry.last_accessed.isoformat(),
                    'age_hours': round(age_hours, 2),
                    'remaining_hours': round(max(0, remaining_hours), 2),
                    'sanitized': entry.sanitized,
                    'ttl_hours': entry.ttl_hours
                }
                
        except Exception as e:
            logger.error(f"Error getting user progress for {user_id}: {e}")
            return None
    
    def create_backup(self) -> Optional[str]:
        """
        Create a backup of current data.
        
        Returns:
            Backup file path if successful, None otherwise
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"backup_{timestamp}.json"
            
            with self._lock:
                # Create backup data with metadata
                backup_data = {
                    'timestamp': timestamp,
                    'entries_count': len(self._data_entries),
                    'data': {str(user_id): entry.to_dict() for user_id, entry in self._data_entries.items()}
                }
                
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)
                
                # Clean up old backups
                self._cleanup_old_backups()
                
                self._log_action(
                    "backup_created",
                    context={"backup_file": str(backup_file), "entries_count": len(self._data_entries)}
                )
                
                return str(backup_file)
                
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            self._log_action(f"Error creating backup: {e}")
            return None
    
    def restore_from_backup(self, backup_file: str) -> bool:
        """
        Restore data from backup file.
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            True if restore was successful, False otherwise
        """
        try:
            backup_path = Path(backup_file)
            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_file}")
                return False
            
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            with self._lock:
                # Clear current data
                self._data_entries.clear()
                
                # Restore data entries
                if 'data' in backup_data:
                    for user_id_str, entry_data in backup_data['data'].items():
                        try:
                            user_id = int(user_id_str)
                            entry = DataEntry.from_dict(entry_data)
                            
                            # Only restore non-expired entries
                            if not entry.is_expired():
                                self._data_entries[user_id] = entry
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Error restoring entry for user {user_id_str}: {e}")
                
                # Save restored data
                self._save_data()
                
                self._log_action(
                    "backup_restored",
                    context={
                        "backup_file": backup_file,
                        "restored_entries": len(self._data_entries),
                        "backup_timestamp": backup_data.get('timestamp', 'unknown')
                    }
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
            self._log_action(f"Error restoring from backup: {e}")
            return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            with self._lock:
                total_entries = len(self._data_entries)
                expired_count = sum(1 for entry in self._data_entries.values() if entry.is_expired())
                
                # Calculate file sizes
                data_file_size = self.data_file.stat().st_size if self.data_file.exists() else 0
                
                # Get backup info
                backup_files = list(self.backup_dir.glob("backup_*.json"))
                backup_count = len(backup_files)
                total_backup_size = sum(f.stat().st_size for f in backup_files)
                
                return {
                    'total_entries': total_entries,
                    'expired_entries': expired_count,
                    'active_entries': total_entries - expired_count,
                    'data_file_size_bytes': data_file_size,
                    'backup_count': backup_count,
                    'total_backup_size_bytes': total_backup_size,
                    'data_directory': str(self.data_dir),
                    'backup_directory': str(self.backup_dir)
                }
                
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {}
    
    def _load_data(self) -> None:
        """Load data from file."""
        try:
            if not self.data_file.exists():
                return
            
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            loaded_count = 0
            for user_id_str, entry_data in data.items():
                try:
                    user_id = int(user_id_str)
                    entry = DataEntry.from_dict(entry_data)
                    
                    # Only load non-expired entries
                    if not entry.is_expired():
                        self._data_entries[user_id] = entry
                        loaded_count += 1
                        
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error loading entry for user {user_id_str}: {e}")
            
            self._log_action(
                "data_loaded_on_startup",
                context={"loaded_entries": loaded_count}
            )
            
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load persistence data: {e}")
        except Exception as e:
            logger.error(f"Error loading persistence data: {e}")
    
    def _save_data(self) -> None:
        """Save data to file with atomic operation."""
        try:
            # Prepare data for serialization
            data = {str(user_id): entry.to_dict() for user_id, entry in self._data_entries.items()}
            
            # Write to temporary file first
            temp_file = self.data_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic replacement
            temp_file.replace(self.data_file)
            
        except Exception as e:
            logger.error(f"Error saving persistence data: {e}")
            # Clean up temp file if it exists
            temp_file = self.data_file.with_suffix('.tmp')
            if temp_file.exists():
                temp_file.unlink()
    
    def _cleanup_old_backups(self) -> None:
        """Clean up old backup files."""
        try:
            backup_files = sorted(
                self.backup_dir.glob("backup_*.json"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            # Remove excess backup files
            for backup_file in backup_files[self.max_backup_files:]:
                backup_file.unlink()
                logger.info(f"Removed old backup: {backup_file}")
                
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
    
    def _start_cleanup_task(self) -> None:
        """Start the periodic cleanup task."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.cleanup_interval_minutes * 60)
                    cleaned_count = self.cleanup_expired_data()
                    if cleaned_count > 0:
                        logger.info(f"Automatic cleanup removed {cleaned_count} expired entries")
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}")
        
        try:
            # Check if there's an event loop
            loop = asyncio.get_running_loop()
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = loop.create_task(cleanup_loop())
        except RuntimeError:
            # No event loop running, skip cleanup task
            pass
    
    def cleanup(self) -> None:
        """Clean up resources and perform final data save."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        # Final cleanup and save
        self.cleanup_expired_data()
        self._save_data()
        
        self._log_action("persistence_manager_cleanup_completed")