# -*- coding: utf-8 -*-

"""
Security Manager for Telegram Bot Security Improvements
Handles input sanitization, validation, rate limiting, and security event logging
"""

import re
import html
import logging
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, Optional, List, Any
from enum import Enum

logger = logging.getLogger(__name__)


class InputType(Enum):
    """Types of input validation"""
    AGE = "age"
    BODY_FAT = "body_fat"
    SCALE_1_5 = "scale_1_5"
    YES_NO = "yes_no"
    EXERCISE_FREQUENCY = "exercise_frequency"
    FREE_TEXT = "free_text"


class SecurityEventType(Enum):
    """Types of security events"""
    MALICIOUS_INPUT = "malicious_input"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_INPUT_REPEATED = "invalid_input_repeated"
    SUSPICIOUS_PATTERN = "suspicious_pattern"


class SecuritySeverity(Enum):
    """Security event severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Result of input validation"""
    is_valid: bool
    error_message: Optional[str] = None
    help_message: Optional[str] = None
    suggested_format: Optional[str] = None


@dataclass
class SecurityEvent:
    """Security event data"""
    user_id: int
    event_type: SecurityEventType
    description: str
    timestamp: datetime
    severity: SecuritySeverity
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class RateLimitInfo:
    """Rate limiting information for a user"""
    user_id: int
    requests_count: int
    window_start: datetime
    is_blocked: bool = False
    block_until: Optional[datetime] = None


class SecurityManager:
    """
    Manages security aspects of the bot including input sanitization,
    validation, rate limiting, and security event logging.
    """
    
    def __init__(self, rate_limit_per_minute: int = 10):
        """
        Initialize SecurityManager.
        
        Args:
            rate_limit_per_minute: Maximum requests per minute per user
        """
        self.rate_limit_per_minute = rate_limit_per_minute
        self.rate_limit_data: Dict[int, RateLimitInfo] = {}
        self.security_events: List[SecurityEvent] = []
        self.user_error_counts: Dict[int, Dict[str, int]] = {}
        
        # Malicious patterns to detect
        self.malicious_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',  # JavaScript protocol
            r'on\w+\s*=',  # Event handlers
            r'<iframe[^>]*>',  # Iframe tags
            r'<object[^>]*>',  # Object tags
            r'<embed[^>]*>',  # Embed tags
            r'eval\s*\(',  # eval function
            r'document\.',  # DOM access
            r'window\.',  # Window object access
            r'\.innerHTML',  # innerHTML access
            r'SELECT.*FROM',  # SQL injection
            r'UNION.*SELECT',  # SQL injection
            r'DROP.*TABLE',  # SQL injection
            r'INSERT.*INTO',  # SQL injection
            r'UPDATE.*SET',  # SQL injection
            r'DELETE.*FROM',  # SQL injection
            r'\.\./.*',  # Path traversal
            r'\.\.\\.*',  # Path traversal (Windows)
            r'/etc/passwd',  # System file access
            r'/etc/shadow',  # System file access
            r'\.\./',  # Directory traversal
            r'\.\.\\',  # Directory traversal (Windows)
            r'\$\{jndi:',  # JNDI injection (Log4j)
            r'\{\{.*\}\}',  # Template injection
            r'<%.*%>',  # Server-side template injection
            r'<\?.*\?>'  # PHP/XML injection
        ]
        
        logger.info(f"SecurityManager initialized with rate limit: {rate_limit_per_minute}/min")
    
    def sanitize_input(self, text: str) -> str:
        """
        Sanitize user input to prevent XSS and other attacks.
        
        Args:
            text: Raw user input
            
        Returns:
            str: Sanitized input
        """
        if not isinstance(text, str):
            return str(text)
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # HTML escape
        text = html.escape(text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Limit length to prevent DoS
        if len(text) > 1000:
            text = text[:1000]
            logger.warning(f"Input truncated to 1000 characters")
        
        return text
    
    def validate_input(self, text: str, input_type: InputType, user_id: int) -> ValidationResult:
        """
        Validate user input based on the expected type.
        
        Args:
            text: User input to validate
            input_type: Expected input type
            user_id: User ID for tracking errors
            
        Returns:
            ValidationResult: Validation result with error messages if invalid
        """
        # Check for malicious patterns BEFORE sanitization
        if self._detect_malicious_input(text, user_id):
            return ValidationResult(
                is_valid=False,
                error_message="Entrada no válida detectada.",
                help_message="Por favor, introduce solo texto normal sin caracteres especiales."
            )
        
        # Then sanitize the input
        sanitized_text = self.sanitize_input(text)
        
        # Validate based on input type
        if input_type == InputType.AGE:
            return self._validate_age(sanitized_text, user_id)
        elif input_type == InputType.BODY_FAT:
            return self._validate_body_fat(sanitized_text, user_id)
        elif input_type == InputType.SCALE_1_5:
            return self._validate_scale_1_5(sanitized_text, user_id)
        elif input_type == InputType.YES_NO:
            return self._validate_yes_no(sanitized_text, user_id)
        elif input_type == InputType.EXERCISE_FREQUENCY:
            return self._validate_exercise_frequency(sanitized_text, user_id)
        elif input_type == InputType.FREE_TEXT:
            return self._validate_free_text(sanitized_text, user_id)
        else:
            return ValidationResult(
                is_valid=False,
                error_message="Tipo de entrada no reconocido."
            )
    
    def check_rate_limit(self, user_id: int) -> bool:
        """
        Check if user has exceeded rate limit.
        
        Args:
            user_id: User ID to check
            
        Returns:
            bool: True if user is within rate limit, False if exceeded
        """
        current_time = datetime.now()
        
        # Get or create rate limit info for user
        if user_id not in self.rate_limit_data:
            self.rate_limit_data[user_id] = RateLimitInfo(
                user_id=user_id,
                requests_count=0,
                window_start=current_time
            )
        
        rate_info = self.rate_limit_data[user_id]
        
        # Check if user is currently blocked
        if rate_info.is_blocked and rate_info.block_until:
            if current_time < rate_info.block_until:
                return False
            else:
                # Unblock user
                rate_info.is_blocked = False
                rate_info.block_until = None
                rate_info.requests_count = 1  # Count this request
                rate_info.window_start = current_time
                return True
        
        # Check if we need to reset the window (1 minute)
        if current_time - rate_info.window_start > timedelta(minutes=1):
            rate_info.requests_count = 0
            rate_info.window_start = current_time
            # Also reset blocking status if window has reset
            if rate_info.is_blocked:
                rate_info.is_blocked = False
                rate_info.block_until = None
        
        # Increment request count
        rate_info.requests_count += 1
        
        # Check if rate limit exceeded
        if rate_info.requests_count > self.rate_limit_per_minute:
            # Block user for progressive time based on violations
            block_minutes = min(rate_info.requests_count - self.rate_limit_per_minute, 60)
            rate_info.is_blocked = True
            rate_info.block_until = current_time + timedelta(minutes=block_minutes)
            
            # Log security event
            self.log_security_event(SecurityEvent(
                user_id=user_id,
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                description=f"Rate limit exceeded: {rate_info.requests_count} requests in 1 minute",
                timestamp=current_time,
                severity=SecuritySeverity.MEDIUM,
                additional_data={
                    "requests_count": rate_info.requests_count,
                    "block_minutes": block_minutes
                }
            ))
            
            return False
        
        return True
    
    def log_security_event(self, event: SecurityEvent) -> None:
        """
        Log a security event.
        
        Args:
            event: Security event to log
        """
        self.security_events.append(event)
        
        # Log to standard logger based on severity
        log_message = f"Security Event - User {event.user_id}: {event.event_type.value} - {event.description}"
        
        if event.severity == SecuritySeverity.CRITICAL:
            logger.critical(log_message)
        elif event.severity == SecuritySeverity.HIGH:
            logger.error(log_message)
        elif event.severity == SecuritySeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        # Keep only last 1000 events to prevent memory issues
        if len(self.security_events) > 1000:
            self.security_events = self.security_events[-1000:]
    
    def get_security_events(self, user_id: Optional[int] = None, 
                          event_type: Optional[SecurityEventType] = None,
                          severity: Optional[SecuritySeverity] = None,
                          limit: int = 100) -> List[SecurityEvent]:
        """
        Get security events with optional filtering.
        
        Args:
            user_id: Filter by user ID (optional)
            event_type: Filter by event type (optional)
            severity: Filter by severity (optional)
            limit: Maximum number of events to return
            
        Returns:
            List[SecurityEvent]: Filtered security events
        """
        events = self.security_events
        
        if user_id is not None:
            events = [e for e in events if e.user_id == user_id]
        
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]

        if severity is not None:
            events = [e for e in events if e.severity == severity]
        
        # Return most recent events first
        events.sort(key=lambda x: x.timestamp, reverse=True)
        return events[:limit]
    
    def _detect_malicious_input(self, text: str, user_id: int) -> bool:
        """
        Detect potentially malicious input patterns.
        
        Args:
            text: Input text to check
            user_id: User ID for logging
            
        Returns:
            bool: True if malicious pattern detected
        """
        text_lower = text.lower()
        
        for pattern in self.malicious_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                self.log_security_event(SecurityEvent(
                    user_id=user_id,
                    event_type=SecurityEventType.MALICIOUS_INPUT,
                    description=f"Malicious pattern detected: {pattern}",
                    timestamp=datetime.now(),
                    severity=SecuritySeverity.HIGH,
                    additional_data={"input": text[:100], "pattern": pattern}
                ))
                return True
        
        return False
    
    def _validate_age(self, text: str, user_id: int) -> ValidationResult:
        """Validate age input (18-120)."""
        try:
            age = int(text)
            if 18 <= age <= 120:
                return ValidationResult(is_valid=True)
            else:
                self._track_validation_error(user_id, "age")
                return ValidationResult(
                    is_valid=False,
                    error_message="La edad debe estar entre 18 y 120 años.",
                    help_message="Introduce tu edad como un número entero (ej: 25).",
                    suggested_format="Ejemplo: 30"
                )
        except ValueError:
            self._track_validation_error(user_id, "age")
            return ValidationResult(
                is_valid=False,
                error_message="Por favor, introduce un número válido para la edad.",
                help_message="La edad debe ser un número entero entre 18 y 120.",
                suggested_format="Ejemplo: 30"
            )
    
    def _validate_body_fat(self, text: str, user_id: int) -> ValidationResult:
        """Validate body fat percentage (0-50%)."""
        try:
            # Remove % symbol if present
            clean_text = text.replace('%', '').strip()
            fat = float(clean_text)
            if 0 <= fat <= 50:
                return ValidationResult(is_valid=True)
            else:
                self._track_validation_error(user_id, "body_fat")
                return ValidationResult(
                    is_valid=False,
                    error_message="El porcentaje de grasa corporal debe estar entre 0% y 50%.",
                    help_message="Introduce un número entre 0 y 50 (sin el símbolo %).",
                    suggested_format="Ejemplo: 15"
                )
        except ValueError:
            self._track_validation_error(user_id, "body_fat")
            return ValidationResult(
                is_valid=False,
                error_message="Por favor, introduce un número válido para el porcentaje de grasa corporal.",
                help_message="Debe ser un número entre 0 y 50.",
                suggested_format="Ejemplo: 15"
            )
    
    def _validate_scale_1_5(self, text: str, user_id: int) -> ValidationResult:
        """Validate 1-5 scale input."""
        try:
            score = int(text)
            if 1 <= score <= 5:
                return ValidationResult(is_valid=True)
            else:
                self._track_validation_error(user_id, "scale_1_5")
                return ValidationResult(
                    is_valid=False,
                    error_message="Por favor, introduce un número entre 1 y 5.",
                    help_message="1=Muy bajo/Ninguno, 2=Leve, 3=Moderado, 4=Severo, 5=Muy severo",
                    suggested_format="Ejemplo: 3"
                )
        except ValueError:
            self._track_validation_error(user_id, "scale_1_5")
            return ValidationResult(
                is_valid=False,
                error_message="Por favor, introduce solo un número del 1 al 5.",
                help_message="Debe ser un número entero entre 1 y 5.",
                suggested_format="Ejemplo: 3"
            )
    
    def _validate_yes_no(self, text: str, user_id: int) -> ValidationResult:
        """Validate yes/no input."""
        text_lower = text.lower().strip()
        valid_yes = ['sí', 'si', 'yes', 'y', 's']
        valid_no = ['no', 'n']
        
        if text_lower in valid_yes or text_lower in valid_no:
            return ValidationResult(is_valid=True)
        else:
            self._track_validation_error(user_id, "yes_no")
            return ValidationResult(
                is_valid=False,
                error_message="Por favor, responde 'Sí' o 'No'.",
                help_message="Respuestas válidas: Sí, Si, No, S, N",
                suggested_format="Ejemplo: Sí"
            )
    
    def _validate_exercise_frequency(self, text: str, user_id: int) -> ValidationResult:
        """Validate exercise frequency (0-7 times per week)."""
        try:
            frequency = int(text)
            if 0 <= frequency <= 7:
                return ValidationResult(is_valid=True)
            else:
                self._track_validation_error(user_id, "exercise_frequency")
                return ValidationResult(
                    is_valid=False,
                    error_message="La frecuencia de ejercicio debe estar entre 0 y 7 veces por semana.",
                    help_message="Introduce el número de veces que haces ejercicio por semana.",
                    suggested_format="Ejemplo: 3"
                )
        except ValueError:
            self._track_validation_error(user_id, "exercise_frequency")
            return ValidationResult(
                is_valid=False,
                error_message="Por favor, introduce un número válido para la frecuencia de ejercicio.",
                help_message="Debe ser un número entre 0 y 7.",
                suggested_format="Ejemplo: 3"
            )
    
    def _validate_free_text(self, text: str, user_id: int) -> ValidationResult:
        """Validate free text input."""
        if len(text) > 100:
            self._track_validation_error(user_id, "free_text")
            return ValidationResult(
                is_valid=False,
                error_message="El texto es demasiado largo. Máximo 100 caracteres.",
                help_message="Por favor, acorta tu respuesta.",
                suggested_format="Máximo 100 caracteres"
            )
        
        if len(text.strip()) == 0:
            self._track_validation_error(user_id, "free_text")
            return ValidationResult(
                is_valid=False,
                error_message="Por favor, introduce algún texto.",
                help_message="La respuesta no puede estar vacía."
            )
        
        return ValidationResult(is_valid=True)
    
    def _track_validation_error(self, user_id: int, error_type: str) -> None:
        """
        Track validation errors per user to detect suspicious patterns.
        
        Args:
            user_id: User ID
            error_type: Type of validation error
        """
        if user_id not in self.user_error_counts:
            self.user_error_counts[user_id] = {}
        
        if error_type not in self.user_error_counts[user_id]:
            self.user_error_counts[user_id][error_type] = 0
        
        self.user_error_counts[user_id][error_type] += 1
        
        # Log if user has exactly 5 errors of the same type (only once)
        if self.user_error_counts[user_id][error_type] == 5:
            self.log_security_event(SecurityEvent(
                user_id=user_id,
                event_type=SecurityEventType.INVALID_INPUT_REPEATED,
                description=f"Repeated validation errors for {error_type}: {self.user_error_counts[user_id][error_type]}",
                timestamp=datetime.now(),
                severity=SecuritySeverity.LOW,
                additional_data={"error_type": error_type, "count": self.user_error_counts[user_id][error_type]}
            ))
    
    def get_user_error_count(self, user_id: int, error_type: str) -> int:
        """
        Get the number of validation errors for a user and error type.
        
        Args:
            user_id: User ID
            error_type: Type of validation error
            
        Returns:
            int: Number of errors
        """
        return self.user_error_counts.get(user_id, {}).get(error_type, 0)
    
    def reset_user_errors(self, user_id: int, error_type: Optional[str] = None) -> None:
        """
        Reset validation error counts for a user.
        
        Args:
            user_id: User ID
            error_type: Specific error type to reset (optional, resets all if None)
        """
        if user_id in self.user_error_counts:
            if error_type:
                self.user_error_counts[user_id].pop(error_type, None)
            else:
                self.user_error_counts[user_id].clear()