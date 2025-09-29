# -*- coding: utf-8 -*-

"""
Error Handler for Telegram Bot Security Improvements
Provides robust error handling with retry mechanisms and user-friendly messages
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable, Union, Tuple
from enum import Enum
from dataclasses import dataclass
from functools import wraps

from telegram.error import NetworkError, TimedOut, BadRequest, Forbidden, ChatMigrated
from telegram import Update
from telegram.ext import ContextTypes

from logging_system import LoggingSystem


class ErrorType(Enum):
    """Types of errors that can occur"""
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    VALIDATION_ERROR = "validation_error"
    SYSTEM_ERROR = "system_error"
    SECURITY_ERROR = "security_error"
    USER_ERROR = "user_error"
    TELEGRAM_API_ERROR = "telegram_api_error"


class RecoveryAction(Enum):
    """Actions to take for error recovery"""
    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"
    FALLBACK = "fallback"
    USER_NOTIFICATION = "user_notification"


@dataclass
class ErrorContext:
    """Context information for error handling"""
    user_id: Optional[int] = None
    chat_id: Optional[int] = None
    message_id: Optional[int] = None
    function_name: Optional[str] = None
    attempt_number: int = 1
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class ErrorHandler:
    """
    Handles various types of errors with automatic retry mechanisms,
    user-friendly messages, and proper logging.
    """
    
    def __init__(self, logging_system: LoggingSystem, retry_config: Optional[RetryConfig] = None):
        """
        Initialize error handler.
        
        Args:
            logging_system: Logging system instance
            retry_config: Retry configuration (uses defaults if None)
        """
        self.logging_system = logging_system
        self.retry_config = retry_config or RetryConfig()
        self.logger = logging.getLogger(__name__)
        
        # User-friendly error messages in Spanish
        self.user_messages = {
            ErrorType.NETWORK_ERROR: {
                'message': '🌐 Problema de conexión. Reintentando...',
                'help': 'Si el problema persiste, verifica tu conexión a internet.'
            },
            ErrorType.TIMEOUT_ERROR: {
                'message': '⏱️ La operación tardó demasiado. Reintentando...',
                'help': 'Por favor, espera un momento mientras procesamos tu solicitud.'
            },
            ErrorType.RATE_LIMIT_ERROR: {
                'message': '🚦 Demasiadas solicitudes. Por favor, espera un momento.',
                'help': 'Intenta de nuevo en unos minutos.'
            },
            ErrorType.VALIDATION_ERROR: {
                'message': '❌ Entrada no válida.',
                'help': 'Por favor, revisa tu respuesta y vuelve a intentarlo.'
            },
            ErrorType.SYSTEM_ERROR: {
                'message': '⚠️ Error interno del sistema.',
                'help': 'El problema ha sido reportado. Por favor, intenta más tarde.'
            },
            ErrorType.SECURITY_ERROR: {
                'message': '🔒 Entrada no permitida por razones de seguridad.',
                'help': 'Por favor, introduce solo texto normal sin caracteres especiales.'
            },
            ErrorType.USER_ERROR: {
                'message': '🤔 Algo no está bien con tu entrada.',
                'help': 'Por favor, revisa las instrucciones y vuelve a intentarlo.'
            },
            ErrorType.TELEGRAM_API_ERROR: {
                'message': '📱 Error de comunicación con Telegram.',
                'help': 'Reintentando automáticamente...'
            }
        }
    
    async def handle_error(self, error: Exception, context: ErrorContext) -> Tuple[RecoveryAction, Optional[str]]:
        """
        Handle an error and determine recovery action.
        
        Args:
            error: Exception that occurred
            context: Error context information
            
        Returns:
            Tuple[RecoveryAction, Optional[str]]: Recovery action and user message
        """
        error_type = self._classify_error(error)
        
        # Log the error
        self.logging_system.log_error(
            error,
            context={
                'error_type': error_type.value,
                'user_id': context.user_id,
                'chat_id': context.chat_id,
                'function_name': context.function_name,
                'attempt_number': context.attempt_number,
                'additional_data': context.additional_data
            },
            user_id=context.user_id
        )
        
        # Determine recovery action
        recovery_action = self._determine_recovery_action(error_type, context)
        
        # Get user message
        user_message = self._get_user_message(error_type, context)
        
        return recovery_action, user_message
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """
        Classify error type based on exception.
        
        Args:
            error: Exception to classify
            
        Returns:
            ErrorType: Classified error type
        """
        # Check most specific Telegram errors first
        if isinstance(error, (TimedOut, asyncio.TimeoutError)):
            return ErrorType.TIMEOUT_ERROR
        elif isinstance(error, BadRequest):
            if "rate limit" in str(error).lower():
                return ErrorType.RATE_LIMIT_ERROR
            else:
                return ErrorType.TELEGRAM_API_ERROR
        elif isinstance(error, (Forbidden, ChatMigrated)):
            return ErrorType.TELEGRAM_API_ERROR
        elif isinstance(error, (NetworkError, ConnectionError)):
            return ErrorType.NETWORK_ERROR
        elif isinstance(error, ValueError):
            return ErrorType.VALIDATION_ERROR
        elif isinstance(error, PermissionError):
            return ErrorType.SECURITY_ERROR
        else:
            return ErrorType.SYSTEM_ERROR
    
    def _determine_recovery_action(self, error_type: ErrorType, context: ErrorContext) -> RecoveryAction:
        """
        Determine what recovery action to take.
        
        Args:
            error_type: Type of error
            context: Error context
            
        Returns:
            RecoveryAction: Action to take
        """
        # Check if we've exceeded max retries
        if context.attempt_number >= self.retry_config.max_retries:
            if error_type in [ErrorType.NETWORK_ERROR, ErrorType.TIMEOUT_ERROR, ErrorType.TELEGRAM_API_ERROR]:
                return RecoveryAction.FALLBACK
            else:
                return RecoveryAction.ABORT
        
        # Determine action based on error type
        if error_type in [ErrorType.NETWORK_ERROR, ErrorType.TIMEOUT_ERROR, ErrorType.TELEGRAM_API_ERROR]:
            return RecoveryAction.RETRY
        elif error_type == ErrorType.RATE_LIMIT_ERROR:
            return RecoveryAction.RETRY  # With longer delay
        elif error_type in [ErrorType.VALIDATION_ERROR, ErrorType.USER_ERROR]:
            return RecoveryAction.USER_NOTIFICATION
        elif error_type == ErrorType.SECURITY_ERROR:
            return RecoveryAction.USER_NOTIFICATION
        else:
            return RecoveryAction.ABORT
    
    def _get_user_message(self, error_type: ErrorType, context: ErrorContext) -> Optional[str]:
        """
        Get user-friendly error message.
        
        Args:
            error_type: Type of error
            context: Error context
            
        Returns:
            Optional[str]: User message or None
        """
        message_info = self.user_messages.get(error_type)
        if not message_info:
            return None
        
        message = message_info['message']
        
        # Add attempt information for retryable errors
        if context.attempt_number > 1 and error_type in [ErrorType.NETWORK_ERROR, ErrorType.TIMEOUT_ERROR]:
            message += f" (Intento {context.attempt_number}/{self.retry_config.max_retries})"
        
        return message
    
    def get_help_message(self, error_type: ErrorType) -> Optional[str]:
        """
        Get help message for error type.
        
        Args:
            error_type: Type of error
            
        Returns:
            Optional[str]: Help message or None
        """
        message_info = self.user_messages.get(error_type)
        return message_info['help'] if message_info else None
    
    async def calculate_retry_delay(self, attempt_number: int, error_type: ErrorType) -> float:
        """
        Calculate delay before retry using exponential backoff.
        
        Args:
            attempt_number: Current attempt number
            error_type: Type of error
            
        Returns:
            float: Delay in seconds
        """
        # Base delay calculation with exponential backoff
        delay = self.retry_config.base_delay * (self.retry_config.exponential_base ** (attempt_number - 1))
        
        # Apply maximum delay limit
        delay = min(delay, self.retry_config.max_delay)
        
        # Special handling for rate limit errors
        if error_type == ErrorType.RATE_LIMIT_ERROR:
            delay = max(delay, 30.0)  # Minimum 30 seconds for rate limits
        
        # Add jitter to prevent thundering herd
        if self.retry_config.jitter:
            import random
            jitter = random.uniform(0.1, 0.3) * delay
            delay += jitter
        
        return delay
    
    def with_retry(self, max_retries: Optional[int] = None):
        """
        Decorator for automatic retry with exponential backoff.
        
        Args:
            max_retries: Override default max retries
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                retries = max_retries or self.retry_config.max_retries
                last_error = None
                
                for attempt in range(1, retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_error = e
                        
                        # Create error context
                        context = ErrorContext(
                            function_name=func.__name__,
                            attempt_number=attempt,
                            additional_data={'args_count': len(args), 'kwargs_keys': list(kwargs.keys())}
                        )
                        
                        # Handle the error
                        recovery_action, user_message = await self.handle_error(e, context)
                        
                        # If this is the last attempt or we shouldn't retry, raise the error
                        if attempt == retries or recovery_action != RecoveryAction.RETRY:
                            raise e
                        
                        # Calculate delay and wait
                        error_type = self._classify_error(e)
                        delay = await self.calculate_retry_delay(attempt, error_type)
                        
                        self.logging_system.log_warning(
                            f"Retrying {func.__name__} in {delay:.2f} seconds (attempt {attempt}/{retries})",
                            context={'delay': delay, 'attempt': attempt, 'max_retries': retries}
                        )
                        
                        await asyncio.sleep(delay)
                
                # If we get here, all retries failed
                if last_error:
                    raise last_error
                    
            return wrapper
        return decorator
    
    async def safe_send_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               text: str, **kwargs) -> bool:
        """
        Safely send a message with error handling.
        
        Args:
            update: Telegram update
            context: Bot context
            text: Message text
            **kwargs: Additional arguments for send_message
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            if update.message:
                await update.message.reply_text(text, **kwargs)
            elif update.callback_query:
                await update.callback_query.message.reply_text(text, **kwargs)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text, **kwargs)
            return True
        except Exception as e:
            error_context = ErrorContext(
                user_id=update.effective_user.id if update.effective_user else None,
                chat_id=update.effective_chat.id if update.effective_chat else None,
                function_name='safe_send_message'
            )
            
            recovery_action, user_message = await self.handle_error(e, error_context)
            
            # Try fallback method if available
            if recovery_action == RecoveryAction.FALLBACK:
                try:
                    # Simple fallback - just send to chat
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
                    return True
                except Exception:
                    pass
            
            return False
    
    async def safe_edit_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                               text: str, **kwargs) -> bool:
        """
        Safely edit a message with error handling.
        
        Args:
            update: Telegram update
            context: Bot context
            text: New message text
            **kwargs: Additional arguments for edit_message_text
            
        Returns:
            bool: True if message edited successfully, False otherwise
        """
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(text, **kwargs)
                return True
        except Exception as e:
            error_context = ErrorContext(
                user_id=update.effective_user.id if update.effective_user else None,
                chat_id=update.effective_chat.id if update.effective_chat else None,
                message_id=update.callback_query.message.message_id if update.callback_query else None,
                function_name='safe_edit_message'
            )
            
            recovery_action, user_message = await self.handle_error(e, error_context)
            
            # Fallback to sending new message
            if recovery_action == RecoveryAction.FALLBACK:
                return await self.safe_send_message(update, context, text, **kwargs)
            
            return False