"""
Metrics Collection and Analytics System

This module implements anonymous usage tracking and analytics for the Telegram bot,
complying with privacy regulations while providing valuable insights.
"""

import json
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from collections import defaultdict, Counter
import threading
import os


@dataclass
class MetricsReport:
    """Report containing aggregated metrics data"""
    total_conversations_started: int
    total_conversations_completed: int
    completion_rate: float
    average_completion_time: float
    question_response_times: Dict[str, float]
    error_counts: Dict[str, int]
    abandonment_patterns: Dict[str, int]
    report_period: str
    generated_at: datetime


@dataclass
class ConversationMetric:
    """Individual conversation metrics"""
    conversation_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration: Optional[int]
    questions_answered: int
    errors_encountered: List[str]
    abandonment_point: Optional[str]


@dataclass
class QuestionResponseMetric:
    """Question response time metrics"""
    question_type: str
    response_time: float
    timestamp: datetime


@dataclass
class ErrorMetric:
    """Error tracking metrics"""
    error_type: str
    timestamp: datetime
    context: Optional[str]


class MetricsCollector:
    """
    Collects anonymous usage metrics for the Telegram bot.
    
    Implements privacy-compliant data collection that tracks:
    - Conversation completion rates
    - Response times
    - Error patterns
    - User engagement metrics
    
    All data is anonymized and aggregated to protect user privacy.
    """
    
    def __init__(self, storage_file: str = "data/metrics.json"):
        """
        Initialize the metrics collector.
        
        Args:
            storage_file: Path to the metrics storage file
        """
        self.storage_file = storage_file
        self._lock = threading.Lock()
        
        # In-memory metrics storage
        self.conversations: Dict[str, ConversationMetric] = {}
        self.question_responses: List[QuestionResponseMetric] = []
        self.errors: List[ErrorMetric] = []
        
        # Aggregated metrics cache
        self._last_report_generation = None
        self._cached_report = None
        
        # Ensure storage directory exists
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
        
        # Load existing metrics
        self._load_metrics()
    
    def record_conversation_start(self, conversation_id: str = None) -> str:
        """
        Record the start of a new conversation.
        
        Args:
            conversation_id: Optional conversation ID, generates one if not provided
            
        Returns:
            The conversation ID for tracking
        """
        if conversation_id is None:
            conversation_id = self._generate_conversation_id()
        
        with self._lock:
            metric = ConversationMetric(
                conversation_id=conversation_id,
                started_at=datetime.now(),
                completed_at=None,
                duration=None,
                questions_answered=0,
                errors_encountered=[],
                abandonment_point=None
            )
            self.conversations[conversation_id] = metric
            
        self._save_metrics()
        return conversation_id
    
    def record_conversation_complete(self, conversation_id: str, duration: int = None) -> None:
        """
        Record the completion of a conversation.
        
        Args:
            conversation_id: The conversation ID
            duration: Duration in seconds (calculated if not provided)
        """
        with self._lock:
            if conversation_id in self.conversations:
                conversation = self.conversations[conversation_id]
                conversation.completed_at = datetime.now()
                
                if duration is not None:
                    conversation.duration = duration
                else:
                    # Calculate duration from start time
                    time_diff = conversation.completed_at - conversation.started_at
                    conversation.duration = int(time_diff.total_seconds())
                    
        self._save_metrics()
    
    def record_question_response_time(self, question_type: str, response_time: float, 
                                    conversation_id: str = None) -> None:
        """
        Record response time for a specific question type.
        
        Args:
            question_type: Type of question (e.g., 'age', 'body_fat', 'adam_q1')
            response_time: Time taken to respond in seconds
            conversation_id: Optional conversation ID for tracking
        """
        with self._lock:
            metric = QuestionResponseMetric(
                question_type=question_type,
                response_time=response_time,
                timestamp=datetime.now()
            )
            self.question_responses.append(metric)
            
            # Update conversation metrics if ID provided
            if conversation_id and conversation_id in self.conversations:
                self.conversations[conversation_id].questions_answered += 1
                
        self._save_metrics()
    
    def record_error(self, error_type: str, context: str = None, 
                    conversation_id: str = None) -> None:
        """
        Record an error occurrence.
        
        Args:
            error_type: Type of error (e.g., 'validation_error', 'network_error')
            context: Additional context about the error
            conversation_id: Optional conversation ID for tracking
        """
        with self._lock:
            metric = ErrorMetric(
                error_type=error_type,
                timestamp=datetime.now(),
                context=context
            )
            self.errors.append(metric)
            
            # Update conversation metrics if ID provided
            if conversation_id and conversation_id in self.conversations:
                self.conversations[conversation_id].errors_encountered.append(error_type)
                
        self._save_metrics()
    
    def record_abandonment(self, conversation_id: str, abandonment_point: str) -> None:
        """
        Record when a user abandons a conversation.
        
        Args:
            conversation_id: The conversation ID
            abandonment_point: Where in the process the user abandoned
        """
        with self._lock:
            if conversation_id in self.conversations:
                self.conversations[conversation_id].abandonment_point = abandonment_point
                
        self._save_metrics()
    
    def generate_report(self, days_back: int = 7) -> MetricsReport:
        """
        Generate an aggregated metrics report.
        
        Args:
            days_back: Number of days to include in the report
            
        Returns:
            MetricsReport with aggregated data
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        with self._lock:
            # Filter data by date range
            recent_conversations = {
                cid: conv for cid, conv in self.conversations.items()
                if conv.started_at >= cutoff_date
            }
            
            recent_responses = [
                resp for resp in self.question_responses
                if resp.timestamp >= cutoff_date
            ]
            
            recent_errors = [
                err for err in self.errors
                if err.timestamp >= cutoff_date
            ]
            
            # Calculate metrics
            total_started = len(recent_conversations)
            total_completed = len([c for c in recent_conversations.values() if c.completed_at])
            completion_rate = (total_completed / total_started * 100) if total_started > 0 else 0
            
            # Average completion time
            completed_conversations = [c for c in recent_conversations.values() if c.duration]
            avg_completion_time = (
                sum(c.duration for c in completed_conversations) / len(completed_conversations)
                if completed_conversations else 0
            )
            
            # Question response times
            response_times = defaultdict(list)
            for resp in recent_responses:
                response_times[resp.question_type].append(resp.response_time)
            
            avg_response_times = {
                qtype: sum(times) / len(times)
                for qtype, times in response_times.items()
            }
            
            # Error counts
            error_counts = Counter(err.error_type for err in recent_errors)
            
            # Abandonment patterns
            abandonment_patterns = Counter(
                conv.abandonment_point for conv in recent_conversations.values()
                if conv.abandonment_point
            )
            
            report = MetricsReport(
                total_conversations_started=total_started,
                total_conversations_completed=total_completed,
                completion_rate=completion_rate,
                average_completion_time=avg_completion_time,
                question_response_times=avg_response_times,
                error_counts=dict(error_counts),
                abandonment_patterns=dict(abandonment_patterns),
                report_period=f"{days_back} days",
                generated_at=datetime.now()
            )
            
            # Cache the report
            self._cached_report = report
            self._last_report_generation = datetime.now()
            
            return report
    
    def get_usage_trends(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Get usage trends over time.
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            Dictionary with trend data
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        with self._lock:
            # Group conversations by day
            daily_stats = defaultdict(lambda: {'started': 0, 'completed': 0})
            
            for conv in self.conversations.values():
                if conv.started_at >= cutoff_date:
                    day_key = conv.started_at.strftime('%Y-%m-%d')
                    daily_stats[day_key]['started'] += 1
                    
                    if conv.completed_at:
                        daily_stats[day_key]['completed'] += 1
            
            return {
                'daily_stats': dict(daily_stats),
                'total_days': days_back,
                'analysis_period': f"{cutoff_date.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}"
            }
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """
        Clean up old metrics data to maintain privacy and storage efficiency.
        
        Args:
            days_to_keep: Number of days of data to retain
            
        Returns:
            Number of records cleaned up
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cleaned_count = 0
        
        with self._lock:
            # Clean old conversations
            old_conversations = [
                cid for cid, conv in self.conversations.items()
                if conv.started_at < cutoff_date
            ]
            for cid in old_conversations:
                del self.conversations[cid]
                cleaned_count += 1
            
            # Clean old question responses
            old_responses = [
                i for i, resp in enumerate(self.question_responses)
                if resp.timestamp < cutoff_date
            ]
            for i in reversed(old_responses):
                del self.question_responses[i]
                cleaned_count += 1
            
            # Clean old errors
            old_errors = [
                i for i, err in enumerate(self.errors)
                if err.timestamp < cutoff_date
            ]
            for i in reversed(old_errors):
                del self.errors[i]
                cleaned_count += 1
        
        if cleaned_count > 0:
            self._save_metrics()
            
        return cleaned_count
    
    def _generate_conversation_id(self) -> str:
        """Generate a unique conversation ID"""
        import uuid
        timestamp = int(time.time() * 1000)
        unique_id = str(uuid.uuid4())[:8]
        return f"conv_{timestamp}_{unique_id}"
    
    def _save_metrics(self) -> None:
        """Save metrics to persistent storage"""
        try:
            data = {
                'conversations': {
                    cid: asdict(conv) for cid, conv in self.conversations.items()
                },
                'question_responses': [asdict(resp) for resp in self.question_responses],
                'errors': [asdict(err) for err in self.errors],
                'last_updated': datetime.now().isoformat()
            }
            
            # Convert datetime objects to ISO strings for JSON serialization
            data = self._serialize_datetimes(data)
            
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            # Log error but don't crash the application
            print(f"Error saving metrics: {e}")
    
    def _load_metrics(self) -> None:
        """Load metrics from persistent storage"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                
                # Deserialize conversations
                for cid, conv_data in data.get('conversations', {}).items():
                    conv_data = self._deserialize_datetimes(conv_data)
                    self.conversations[cid] = ConversationMetric(**conv_data)
                
                # Deserialize question responses
                for resp_data in data.get('question_responses', []):
                    resp_data = self._deserialize_datetimes(resp_data)
                    self.question_responses.append(QuestionResponseMetric(**resp_data))
                
                # Deserialize errors
                for err_data in data.get('errors', []):
                    err_data = self._deserialize_datetimes(err_data)
                    self.errors.append(ErrorMetric(**err_data))
                    
        except Exception as e:
            # Log error but continue with empty metrics
            print(f"Error loading metrics: {e}")
    
    def _serialize_datetimes(self, obj: Any) -> Any:
        """Convert datetime objects to ISO strings for JSON serialization"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._serialize_datetimes(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetimes(item) for item in obj]
        return obj
    
    def _deserialize_datetimes(self, obj: Any) -> Any:
        """Convert ISO strings back to datetime objects"""
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k.endswith('_at') or k == 'timestamp':
                    try:
                        result[k] = datetime.fromisoformat(v) if v else None
                    except (ValueError, TypeError):
                        result[k] = v
                else:
                    result[k] = self._deserialize_datetimes(v)
            return result
        elif isinstance(obj, list):
            return [self._deserialize_datetimes(item) for item in obj]
        return obj


# Global metrics collector instance
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def initialize_metrics_collector(storage_file: str = None) -> MetricsCollector:
    """Initialize the global metrics collector with custom settings"""
    global _metrics_collector
    if storage_file:
        _metrics_collector = MetricsCollector(storage_file)
    else:
        _metrics_collector = MetricsCollector()
    return _metrics_collector