"""Feedback data model with comprehensive validation."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
import uuid


class FeedbackType(Enum):
    """Types of feedback that can be collected."""
    TASK_SUCCESS = "task_success"
    TASK_FAILURE = "task_failure"
    PARTIAL_SUCCESS = "partial_success"
    WORKER_PERFORMANCE = "worker_performance"
    QUALITY_ASSESSMENT = "quality_assessment"
    ERROR_REPORT = "error_report"
    SUGGESTION = "suggestion"
    VALIDATION_FAILURE = "validation_failure"


class FeedbackSeverity(Enum):
    """Severity levels for feedback."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class FeedbackCategory(Enum):
    """Categories for organizing feedback."""
    EXECUTION = "execution"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    RESOURCE = "resource"
    COMMUNICATION = "communication"
    CONFIGURATION = "configuration"


@dataclass
class FeedbackMetrics:
    """Metrics associated with feedback."""
    execution_time: Optional[float] = None
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None
    tokens_used: Optional[int] = None
    quality_score: Optional[float] = None
    success_rate: Optional[float] = None
    custom_metrics: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate metrics values."""
        if self.execution_time is not None and self.execution_time < 0:
            raise ValueError("Execution time cannot be negative")
        
        if self.memory_usage is not None and self.memory_usage < 0:
            raise ValueError("Memory usage cannot be negative")
        
        if self.cpu_usage is not None and not 0 <= self.cpu_usage <= 100:
            raise ValueError("CPU usage must be between 0 and 100")
        
        if self.tokens_used is not None and self.tokens_used < 0:
            raise ValueError("Tokens used cannot be negative")
        
        if self.quality_score is not None and not 0 <= self.quality_score <= 1:
            raise ValueError("Quality score must be between 0 and 1")
        
        if self.success_rate is not None and not 0 <= self.success_rate <= 1:
            raise ValueError("Success rate must be between 0 and 1")


@dataclass
class FeedbackContext:
    """Context information for feedback."""
    task_id: str
    worker_id: Optional[str] = None
    session_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    environment: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def validate(self) -> None:
        """Validate context information."""
        if not self.task_id:
            raise ValueError("Task ID is required")
        
        if not isinstance(self.tags, list):
            raise ValueError("Tags must be a list")
        
        if not all(isinstance(tag, str) for tag in self.tags):
            raise ValueError("All tags must be strings")


@dataclass
class FeedbackModel:
    """Main feedback model with comprehensive validation."""
    feedback_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    feedback_type: FeedbackType = FeedbackType.TASK_SUCCESS
    severity: FeedbackSeverity = FeedbackSeverity.INFO
    category: FeedbackCategory = FeedbackCategory.EXECUTION
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    context: FeedbackContext = field(default_factory=lambda: FeedbackContext(task_id=""))
    metrics: FeedbackMetrics = field(default_factory=FeedbackMetrics)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"
    
    def __post_init__(self):
        """Validate the feedback model after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Comprehensive validation of the feedback model."""
        # Validate feedback_id
        if not self.feedback_id:
            raise ValueError("Feedback ID is required")
        
        # Validate enums
        if not isinstance(self.feedback_type, FeedbackType):
            raise ValueError(f"Invalid feedback type: {self.feedback_type}")
        
        if not isinstance(self.severity, FeedbackSeverity):
            raise ValueError(f"Invalid severity: {self.severity}")
        
        if not isinstance(self.category, FeedbackCategory):
            raise ValueError(f"Invalid category: {self.category}")
        
        # Validate message
        if not self.message or not isinstance(self.message, str):
            raise ValueError("Message must be a non-empty string")
        
        if len(self.message) > 10000:
            raise ValueError("Message too long (max 10000 characters)")
        
        # Validate details
        if not isinstance(self.details, dict):
            raise ValueError("Details must be a dictionary")
        
        # Validate context
        if not isinstance(self.context, FeedbackContext):
            raise ValueError("Context must be a FeedbackContext instance")
        self.context.validate()
        
        # Validate metrics
        if not isinstance(self.metrics, FeedbackMetrics):
            raise ValueError("Metrics must be a FeedbackMetrics instance")
        self.metrics.validate()
        
        # Validate timestamp
        if not isinstance(self.timestamp, datetime):
            raise ValueError("Timestamp must be a datetime instance")
        
        # Validate source
        if not self.source or not isinstance(self.source, str):
            raise ValueError("Source must be a non-empty string")
        
        # Business logic validation
        self._validate_business_logic()
    
    def _validate_business_logic(self) -> None:
        """Validate business logic rules."""
        # Critical severity should only be used for errors
        if self.severity == FeedbackSeverity.CRITICAL and self.feedback_type not in [
            FeedbackType.TASK_FAILURE,
            FeedbackType.ERROR_REPORT,
            FeedbackType.VALIDATION_FAILURE
        ]:
            raise ValueError("Critical severity should only be used for failures/errors")
        
        # Task success should not have error severity
        if self.feedback_type == FeedbackType.TASK_SUCCESS and self.severity in [
            FeedbackSeverity.ERROR,
            FeedbackSeverity.CRITICAL
        ]:
            raise ValueError("Task success should not have error/critical severity")
        
        # Performance feedback should include metrics
        if self.category == FeedbackCategory.PERFORMANCE and not any([
            self.metrics.execution_time,
            self.metrics.cpu_usage,
            self.metrics.memory_usage,
            self.metrics.custom_metrics
        ]):
            raise ValueError("Performance feedback should include metrics")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert feedback model to dictionary."""
        return {
            "feedback_id": self.feedback_id,
            "feedback_type": self.feedback_type.value,
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "details": self.details,
            "context": {
                "task_id": self.context.task_id,
                "worker_id": self.context.worker_id,
                "session_id": self.context.session_id,
                "parent_task_id": self.context.parent_task_id,
                "environment": self.context.environment,
                "tags": self.context.tags
            },
            "metrics": {
                "execution_time": self.metrics.execution_time,
                "memory_usage": self.metrics.memory_usage,
                "cpu_usage": self.metrics.cpu_usage,
                "tokens_used": self.metrics.tokens_used,
                "quality_score": self.metrics.quality_score,
                "success_rate": self.metrics.success_rate,
                "custom_metrics": self.metrics.custom_metrics
            },
            "timestamp": self.timestamp.isoformat(),
            "source": self.source
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackModel":
        """Create feedback model from dictionary."""
        # Convert string enums back to enum types
        feedback_type = FeedbackType(data.get("feedback_type", FeedbackType.TASK_SUCCESS.value))
        severity = FeedbackSeverity(data.get("severity", FeedbackSeverity.INFO.value))
        category = FeedbackCategory(data.get("category", FeedbackCategory.EXECUTION.value))
        
        # Build context
        context_data = data.get("context", {})
        context = FeedbackContext(
            task_id=context_data.get("task_id", ""),
            worker_id=context_data.get("worker_id"),
            session_id=context_data.get("session_id"),
            parent_task_id=context_data.get("parent_task_id"),
            environment=context_data.get("environment", {}),
            tags=context_data.get("tags", [])
        )
        
        # Build metrics
        metrics_data = data.get("metrics", {})
        metrics = FeedbackMetrics(
            execution_time=metrics_data.get("execution_time"),
            memory_usage=metrics_data.get("memory_usage"),
            cpu_usage=metrics_data.get("cpu_usage"),
            tokens_used=metrics_data.get("tokens_used"),
            quality_score=metrics_data.get("quality_score"),
            success_rate=metrics_data.get("success_rate"),
            custom_metrics=metrics_data.get("custom_metrics", {})
        )
        
        # Parse timestamp
        timestamp_str = data.get("timestamp", datetime.now().isoformat())
        timestamp = datetime.fromisoformat(timestamp_str)
        
        return cls(
            feedback_id=data.get("feedback_id", str(uuid.uuid4())),
            feedback_type=feedback_type,
            severity=severity,
            category=category,
            message=data.get("message", ""),
            details=data.get("details", {}),
            context=context,
            metrics=metrics,
            timestamp=timestamp,
            source=data.get("source", "system")
        )


def create_success_feedback(
    task_id: str,
    message: str,
    metrics: Optional[FeedbackMetrics] = None,
    **kwargs
) -> FeedbackModel:
    """Helper function to create success feedback."""
    context = FeedbackContext(task_id=task_id, **kwargs)
    return FeedbackModel(
        feedback_type=FeedbackType.TASK_SUCCESS,
        severity=FeedbackSeverity.INFO,
        category=FeedbackCategory.EXECUTION,
        message=message,
        context=context,
        metrics=metrics or FeedbackMetrics()
    )


def create_error_feedback(
    task_id: str,
    message: str,
    error_details: Dict[str, Any],
    severity: FeedbackSeverity = FeedbackSeverity.ERROR,
    **kwargs
) -> FeedbackModel:
    """Helper function to create error feedback."""
    context = FeedbackContext(task_id=task_id, **kwargs)
    return FeedbackModel(
        feedback_type=FeedbackType.ERROR_REPORT,
        severity=severity,
        category=FeedbackCategory.EXECUTION,
        message=message,
        details=error_details,
        context=context
    )


def create_performance_feedback(
    task_id: str,
    message: str,
    execution_time: float,
    cpu_usage: Optional[float] = None,
    memory_usage: Optional[float] = None,
    **kwargs
) -> FeedbackModel:
    """Helper function to create performance feedback."""
    context = FeedbackContext(task_id=task_id, **kwargs)
    metrics = FeedbackMetrics(
        execution_time=execution_time,
        cpu_usage=cpu_usage,
        memory_usage=memory_usage
    )
    return FeedbackModel(
        feedback_type=FeedbackType.WORKER_PERFORMANCE,
        severity=FeedbackSeverity.INFO,
        category=FeedbackCategory.PERFORMANCE,
        message=message,
        context=context,
        metrics=metrics
    )