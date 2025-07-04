"""
Feedback Data Models for Claude Orchestrator

This module defines the data structures for feedback collection and storage.
Based on requirements from task_1_feedback_review.md and add_feedback_model_tasks.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import json
import uuid


class FeedbackType(Enum):
    """Types of feedback that can be collected"""
    TASK_COMPLETION = "task_completion"
    WORKER_PERFORMANCE = "worker_performance"
    MANAGER_REVIEW = "manager_review"
    USER_RATING = "user_rating"
    ERROR_REPORT = "error_report"
    IMPROVEMENT_SUGGESTION = "improvement_suggestion"


class RatingScale(Enum):
    """Rating scale for feedback (1-5)"""
    POOR = 1
    FAIR = 2
    GOOD = 3
    VERY_GOOD = 4
    EXCELLENT = 5


@dataclass
class FeedbackMetadata:
    """Metadata associated with feedback"""
    source: str  # e.g., "orchestrator", "worker", "user"
    version: str  # system version when feedback was created
    context: Dict[str, Any] = field(default_factory=dict)  # additional context
    tags: List[str] = field(default_factory=list)  # categorization tags
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "source": self.source,
            "version": self.version,
            "context": self.context,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeedbackMetadata':
        """Create from dictionary"""
        return cls(
            source=data["source"],
            version=data["version"],
            context=data.get("context", {}),
            tags=data.get("tags", [])
        )


@dataclass
class FeedbackEntry:
    """
    Main feedback data structure
    
    Based on requirements:
    - id, timestamp, user_id, task_id (core fields)
    - rating system (1-5 numeric scale)
    - comment structure with length limits
    - metadata fields (source, version, context)
    """
    id: str
    task_id: str
    timestamp: datetime
    feedback_type: FeedbackType
    content: str
    rating: Optional[RatingScale] = None
    user_id: Optional[str] = None
    metadata: Optional[FeedbackMetadata] = None
    
    def __post_init__(self):
        """Validate feedback entry after creation"""
        self._validate()
    
    def _validate(self):
        """Validate feedback data"""
        # Content length validation (max 500 chars as per requirements)
        if len(self.content) > 500:
            raise ValueError(f"Feedback content too long: {len(self.content)} > 500 characters")
        
        # Required fields validation
        if not self.id:
            raise ValueError("Feedback ID is required")
        if not self.task_id:
            raise ValueError("Task ID is required")
        if not self.content.strip():
            raise ValueError("Feedback content cannot be empty")
        
        # Rating validation (must be 1-5 if provided)
        if self.rating is not None and not isinstance(self.rating, RatingScale):
            raise ValueError("Rating must be a RatingScale enum value")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            "feedback_type": self.feedback_type.value,
            "content": self.content,
            "rating": self.rating.value if self.rating else None,
            "user_id": self.user_id,
            "metadata": self.metadata.to_dict() if self.metadata else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeedbackEntry':
        """Create feedback entry from dictionary"""
        return cls(
            id=data["id"],
            task_id=data["task_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            feedback_type=FeedbackType(data["feedback_type"]),
            content=data["content"],
            rating=RatingScale(data["rating"]) if data["rating"] else None,
            user_id=data.get("user_id"),
            metadata=FeedbackMetadata.from_dict(data["metadata"]) if data["metadata"] else None
        )
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'FeedbackEntry':
        """Create from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class FeedbackSummary:
    """Summary statistics for feedback aggregation"""
    task_id: str
    total_feedback_count: int
    average_rating: Optional[float] = None
    rating_distribution: Dict[int, int] = field(default_factory=dict)
    feedback_types: Dict[str, int] = field(default_factory=dict)
    latest_feedback: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "total_feedback_count": self.total_feedback_count,
            "average_rating": self.average_rating,
            "rating_distribution": self.rating_distribution,
            "feedback_types": self.feedback_types,
            "latest_feedback": self.latest_feedback.isoformat() if self.latest_feedback else None
        }


def create_feedback_entry(
    task_id: str,
    feedback_type: FeedbackType,
    content: str,
    rating: Optional[RatingScale] = None,
    user_id: Optional[str] = None,
    source: str = "orchestrator",
    version: str = "1.0.0",
    context: Optional[Dict[str, Any]] = None
) -> FeedbackEntry:
    """
    Factory function to create a feedback entry with proper defaults
    
    Args:
        task_id: ID of the task this feedback relates to
        feedback_type: Type of feedback being provided
        content: Feedback content (max 500 chars)
        rating: Optional rating (1-5 scale)
        user_id: Optional user ID who provided feedback
        source: Source system providing feedback
        version: System version
        context: Additional context information
    
    Returns:
        FeedbackEntry: Validated feedback entry
    """
    feedback_id = str(uuid.uuid4())
    timestamp = datetime.now()
    
    metadata = FeedbackMetadata(
        source=source,
        version=version,
        context=context or {},
        tags=[]
    )
    
    return FeedbackEntry(
        id=feedback_id,
        task_id=task_id,
        timestamp=timestamp,
        feedback_type=feedback_type,
        content=content,
        rating=rating,
        user_id=user_id,
        metadata=metadata
    )


def validate_rating(rating: int) -> RatingScale:
    """
    Validate and convert integer rating to RatingScale enum
    
    Args:
        rating: Integer rating (1-5)
    
    Returns:
        RatingScale: Validated rating enum
    
    Raises:
        ValueError: If rating is not in valid range
    """
    if rating not in [1, 2, 3, 4, 5]:
        raise ValueError(f"Rating must be between 1 and 5, got {rating}")
    return RatingScale(rating)


def calculate_feedback_summary(feedback_entries: List[FeedbackEntry]) -> FeedbackSummary:
    """
    Calculate summary statistics for a list of feedback entries
    
    Args:
        feedback_entries: List of feedback entries for a task
    
    Returns:
        FeedbackSummary: Aggregated feedback statistics
    """
    if not feedback_entries:
        return FeedbackSummary(
            task_id="",
            total_feedback_count=0
        )
    
    task_id = feedback_entries[0].task_id
    ratings = [entry.rating.value for entry in feedback_entries if entry.rating]
    
    # Calculate rating statistics
    average_rating = sum(ratings) / len(ratings) if ratings else None
    rating_distribution = {}
    for rating in ratings:
        rating_distribution[rating] = rating_distribution.get(rating, 0) + 1
    
    # Calculate feedback type distribution
    feedback_types = {}
    for entry in feedback_entries:
        type_name = entry.feedback_type.value
        feedback_types[type_name] = feedback_types.get(type_name, 0) + 1
    
    # Find latest feedback timestamp
    latest_feedback = max(entry.timestamp for entry in feedback_entries)
    
    return FeedbackSummary(
        task_id=task_id,
        total_feedback_count=len(feedback_entries),
        average_rating=average_rating,
        rating_distribution=rating_distribution,
        feedback_types=feedback_types,
        latest_feedback=latest_feedback
    )