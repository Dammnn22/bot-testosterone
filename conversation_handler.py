# -*- coding: utf-8 -*-

"""
Enhanced Conversation Handler with persistence and recovery mechanisms.
Implements conversation state persistence with TTL, progress tracking, and timeout handling.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
import os
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes


class ConversationState(Enum):
    """Enumeration of conversation states."""
    START = "start"
    ADAM = "adam"
    AMS = "ams"
    LIFESTYLE = "lifestyle"
    RESULTS = "results"
    COMPLETED = "completed"


@dataclass
class UserProgress:
    """Data model for user conversation progress."""
    user_id: int
    current_state: ConversationState
    adam_answers: List[bool]
    ams_score: int
    ams_question_index: int
    lifestyle_answers: Dict[str, Any]
    lifestyle_question_index: int
    start_time: datetime
    last_activity: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['current_state'] = self.current_state.value
        data['start_time'] = self.start_time.isoformat()
        data['last_activity'] = self.last_activity.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserProgress':
        """Create instance from dictionary."""
        data['current_state'] = ConversationState(data['current_state'])
        data['start_time'] = datetime.fromisoformat(data['start_time'])
        data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        return cls(**data)


@dataclass
class ProgressInfo:
    """Information about user's progress in the questionnaire."""
    current_section: str
    current_question: int
    total_questions: int
    percentage_complete: float
    time_elapsed: timedelta
    
    def get_progress_message(self) -> str:
        """Generate user-friendly progress message."""
        percentage = int(self.percentage_complete)
        elapsed_minutes = int(self.time_elapsed.total_seconds() / 60)
        
        return (
            f"📊 **Progreso actual:**\n"
            f"Sección: {self.current_section}\n"
            f"Pregunta {self.current_question} de {self.total_questions}\n"
            f"Completado: {percentage}%\n"
            f"Tiempo transcurrido: {elapsed_minutes} minutos"
        )


class EnhancedConversationHandler:
    """Enhanced conversation handler with persistence and recovery mechanisms."""
    
    def __init__(self, logging_system=None, data_dir: str = "data"):
        """
        Initialize the enhanced conversation handler.
        
        Args:
            logging_system: Logging system instance
            data_dir: Directory to store persistence data
        """
        self.logging_system = logging_system
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # In-memory storage with TTL
        self._user_data: Dict[int, UserProgress] = {}
        self._data_file = self.data_dir / "conversation_data.json"
        
        # Configuration
        self.ttl_hours = 24
        self.timeout_minutes = 30
        self.cleanup_interval_minutes = 60
        
        # Question counts for progress calculation
        self.question_counts = {
            ConversationState.ADAM: 10,
            ConversationState.AMS: 17,
            ConversationState.LIFESTYLE: 6
        }
        
        # Load existing data
        self._load_data()
        
        # Start cleanup task (only if event loop is available)
        self._cleanup_task = None
        try:
            self._start_cleanup_task()
        except RuntimeError:
            # No event loop available (e.g., in tests), skip cleanup task
            pass
    
    def _log_action(self, message: str, user_id: int = None, context: Dict[str, Any] = None):
        """Log action if logging system is available."""
        if self.logging_system:
            if user_id:
                self.logging_system.log_user_action(user_id, message, context)
            else:
                self.logging_system.log_info(message, context=context)
    
    def _load_data(self) -> None:
        """Load conversation data from file."""
        try:
            if self._data_file.exists():
                with open(self._data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for user_id_str, user_data in data.items():
                    try:
                        user_id = int(user_id_str)
                        progress = UserProgress.from_dict(user_data)
                        
                        # Check if data is still valid (within TTL)
                        if self._is_data_valid(progress):
                            self._user_data[user_id] = progress
                        
                    except (ValueError, KeyError, TypeError) as e:
                        self._log_action(f"Error loading user data for {user_id_str}: {e}")
                        
                self._log_action(f"Loaded conversation data for {len(self._user_data)} users")
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self._log_action(f"Could not load conversation data: {e}")
    
    def _save_data(self) -> None:
        """Save conversation data to file."""
        try:
            # Clean expired data before saving
            self._cleanup_expired_data()
            
            data = {}
            for user_id, progress in self._user_data.items():
                data[str(user_id)] = progress.to_dict()
            
            # Write to temporary file first, then rename for atomic operation
            temp_file = self._data_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            temp_file.replace(self._data_file)
            self._log_action(f"Saved conversation data for {len(self._user_data)} users")
            
        except Exception as e:
            self._log_action(f"Error saving conversation data: {e}")
    
    def _is_data_valid(self, progress: UserProgress) -> bool:
        """Check if user progress data is still valid (within TTL)."""
        ttl_threshold = datetime.now() - timedelta(hours=self.ttl_hours)
        return progress.last_activity > ttl_threshold
    
    def _cleanup_expired_data(self) -> None:
        """Remove expired user data."""
        expired_users = []
        for user_id, progress in self._user_data.items():
            if not self._is_data_valid(progress):
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self._user_data[user_id]
            self._log_action(f"Cleaned up expired data for user {user_id}")
        
        if expired_users:
            self._log_action(f"Cleaned up {len(expired_users)} expired user sessions")
    
    def _start_cleanup_task(self) -> None:
        """Start the periodic cleanup task."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.cleanup_interval_minutes * 60)
                    self._cleanup_expired_data()
                    self._save_data()
                except Exception as e:
                    self._log_action(f"Error in cleanup task: {e}")
        
        try:
            # Check if there's an event loop
            loop = asyncio.get_running_loop()
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = loop.create_task(cleanup_loop())
        except RuntimeError:
            # No event loop running, skip cleanup task
            pass
    
    def save_progress(self, user_id: int, state: ConversationState, context_data: Dict[str, Any]) -> None:
        """
        Save user progress to persistent storage.
        
        Args:
            user_id: Telegram user ID
            state: Current conversation state
            context_data: User data from telegram context
        """
        now = datetime.now()
        
        # Get existing progress or create new
        if user_id in self._user_data:
            progress = self._user_data[user_id]
            progress.current_state = state
            progress.last_activity = now
        else:
            progress = UserProgress(
                user_id=user_id,
                current_state=state,
                adam_answers=[],
                ams_score=0,
                ams_question_index=0,
                lifestyle_answers={},
                lifestyle_question_index=0,
                start_time=now,
                last_activity=now
            )
        
        # Update progress with context data
        if "adam_answers" in context_data:
            progress.adam_answers = context_data["adam_answers"]
        
        if "ams_score" in context_data:
            progress.ams_score = context_data["ams_score"]
        
        if "ams_question_index" in context_data:
            progress.ams_question_index = context_data["ams_question_index"]
        
        if "lifestyle_answers" in context_data:
            progress.lifestyle_answers = context_data["lifestyle_answers"]
        
        if "lifestyle_question_index" in context_data:
            progress.lifestyle_question_index = context_data["lifestyle_question_index"]
        
        # Save to memory and file
        self._user_data[user_id] = progress
        self._save_data()
        
        self._log_action(
            "progress_saved",
            user_id=user_id,
            context={"state": state.value, "questions_answered": self._count_answered_questions(progress)}
        )
    
    def load_progress(self, user_id: int) -> Optional[UserProgress]:
        """
        Load user progress from persistent storage.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            UserProgress if found and valid, None otherwise
        """
        if user_id not in self._user_data:
            return None
        
        progress = self._user_data[user_id]
        
        # Check if data is still valid
        if not self._is_data_valid(progress):
            del self._user_data[user_id]
            self._save_data()
            self._log_action(f"Expired progress data removed for user {user_id}")
            return None
        
        self._log_action(
            "progress_loaded",
            user_id=user_id,
            context={"state": progress.current_state.value}
        )
        
        return progress
    
    def get_user_progress(self, user_id: int) -> Optional[ProgressInfo]:
        """
        Get detailed progress information for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            ProgressInfo if user has active session, None otherwise
        """
        progress = self.load_progress(user_id)
        if not progress:
            return None
        
        # Calculate current section and question
        current_section = ""
        current_question = 0
        total_questions = 0
        
        if progress.current_state == ConversationState.ADAM:
            current_section = "Cuestionario ADAM"
            current_question = len(progress.adam_answers) + 1
            total_questions = self.question_counts[ConversationState.ADAM]
        elif progress.current_state == ConversationState.AMS:
            current_section = "Cuestionario AMS"
            current_question = progress.ams_question_index + 1
            total_questions = self.question_counts[ConversationState.AMS]
        elif progress.current_state == ConversationState.LIFESTYLE:
            current_section = "Preguntas de Estilo de Vida"
            current_question = progress.lifestyle_question_index + 1
            total_questions = self.question_counts[ConversationState.LIFESTYLE]
        else:
            current_section = "Iniciando"
            current_question = 1
            total_questions = sum(self.question_counts.values())
        
        # Calculate percentage complete
        total_answered = self._count_answered_questions(progress)
        total_possible = sum(self.question_counts.values())
        percentage_complete = (total_answered / total_possible) * 100
        
        # Calculate time elapsed
        time_elapsed = datetime.now() - progress.start_time
        
        return ProgressInfo(
            current_section=current_section,
            current_question=current_question,
            total_questions=total_questions,
            percentage_complete=percentage_complete,
            time_elapsed=time_elapsed
        )
    
    def _count_answered_questions(self, progress: UserProgress) -> int:
        """Count total number of questions answered by user."""
        count = 0
        count += len(progress.adam_answers)
        count += progress.ams_question_index
        count += progress.lifestyle_question_index
        return count
    
    def show_progress(self, user_id: int) -> Optional[str]:
        """
        Generate progress message for user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Progress message string or None if no active session
        """
        progress_info = self.get_user_progress(user_id)
        if not progress_info:
            return None
        
        return progress_info.get_progress_message()
    
    def handle_timeout(self, user_id: int) -> Optional[str]:
        """
        Handle user timeout and generate reminder message.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Timeout reminder message or None if no active session
        """
        progress = self.load_progress(user_id)
        if not progress:
            return None
        
        # Check if user has been inactive for timeout period
        timeout_threshold = datetime.now() - timedelta(minutes=self.timeout_minutes)
        
        if progress.last_activity < timeout_threshold:
            self._log_action(
                "timeout_reminder_sent",
                user_id=user_id,
                context={"inactive_minutes": self.timeout_minutes}
            )
            
            return (
                f"⏰ Hola! Veo que has estado inactivo por un tiempo.\n\n"
                f"Tienes un cuestionario en progreso. ¿Te gustaría continuar donde lo dejaste?\n\n"
                f"Usa /status para ver tu progreso actual o /start para continuar."
            )
        
        return None
    
    def clear_user_data(self, user_id: int) -> None:
        """
        Clear all data for a specific user.
        
        Args:
            user_id: Telegram user ID
        """
        if user_id in self._user_data:
            del self._user_data[user_id]
            self._save_data()
            self._log_action(f"Cleared data for user {user_id}")
    
    def restore_context_from_progress(self, context: ContextTypes.DEFAULT_TYPE, progress: UserProgress) -> None:
        """
        Restore telegram context from saved progress.
        
        Args:
            context: Telegram context to restore
            progress: Saved user progress
        """
        context.user_data["adam_answers"] = progress.adam_answers.copy()
        context.user_data["ams_score"] = progress.ams_score
        context.user_data["ams_question_index"] = progress.ams_question_index
        context.user_data["lifestyle_answers"] = progress.lifestyle_answers.copy()
        context.user_data["lifestyle_question_index"] = progress.lifestyle_question_index
        
        self._log_action(
            "context_restored",
            user_id=progress.user_id,
            context={"state": progress.current_state.value}
        )
    
    def has_active_session(self, user_id: int) -> bool:
        """
        Check if user has an active conversation session.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user has active session, False otherwise
        """
        return self.load_progress(user_id) is not None
    
    def get_recovery_message(self, user_id: int) -> Optional[str]:
        """
        Generate recovery message for returning users.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Recovery message or None if no session to recover
        """
        progress_info = self.get_user_progress(user_id)
        if not progress_info:
            return None
        
        return (
            f"👋 ¡Bienvenido de vuelta!\n\n"
            f"Tienes un cuestionario en progreso:\n"
            f"{progress_info.get_progress_message()}\n\n"
            f"¿Te gustaría continuar donde lo dejaste?"
        )
    
    def cleanup(self) -> None:
        """Clean up resources and save data."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        self._cleanup_expired_data()
        self._save_data()
        self._log_action("Conversation handler cleanup completed")