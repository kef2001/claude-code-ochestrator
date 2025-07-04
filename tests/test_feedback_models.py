"""
Unit tests for feedback models

Tests the feedback data structures and validation logic
"""

import pytest
from datetime import datetime
from claude_orchestrator.feedback_models import (
    FeedbackEntry, FeedbackType, RatingScale, FeedbackMetadata,
    create_feedback_entry, validate_rating, calculate_feedback_summary
)


class TestFeedbackEntry:
    """Tests for FeedbackEntry class"""
    
    def test_create_valid_feedback_entry(self):
        """Test creating a valid feedback entry"""
        entry = FeedbackEntry(
            id="test-id",
            task_id="task-123",
            timestamp=datetime.now(),
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Task completed successfully",
            rating=RatingScale.EXCELLENT,
            user_id="user-456"
        )
        
        assert entry.id == "test-id"
        assert entry.task_id == "task-123"
        assert entry.feedback_type == FeedbackType.TASK_COMPLETION
        assert entry.content == "Task completed successfully"
        assert entry.rating == RatingScale.EXCELLENT
        assert entry.user_id == "user-456"
    
    def test_feedback_entry_validation_empty_content(self):
        """Test validation fails with empty content"""
        with pytest.raises(ValueError, match="Feedback content cannot be empty"):
            FeedbackEntry(
                id="test-id",
                task_id="task-123",
                timestamp=datetime.now(),
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="   ",  # Empty content
                rating=RatingScale.GOOD
            )
    
    def test_feedback_entry_validation_content_too_long(self):
        """Test validation fails with content too long"""
        long_content = "x" * 501  # 501 characters
        with pytest.raises(ValueError, match="Feedback content too long"):
            FeedbackEntry(
                id="test-id",
                task_id="task-123",
                timestamp=datetime.now(),
                feedback_type=FeedbackType.TASK_COMPLETION,
                content=long_content,
                rating=RatingScale.GOOD
            )
    
    def test_feedback_entry_validation_missing_id(self):
        """Test validation fails with missing ID"""
        with pytest.raises(ValueError, match="Feedback ID is required"):
            FeedbackEntry(
                id="",  # Empty ID
                task_id="task-123",
                timestamp=datetime.now(),
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="Valid content",
                rating=RatingScale.GOOD
            )
    
    def test_feedback_entry_validation_missing_task_id(self):
        """Test validation fails with missing task ID"""
        with pytest.raises(ValueError, match="Task ID is required"):
            FeedbackEntry(
                id="test-id",
                task_id="",  # Empty task ID
                timestamp=datetime.now(),
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="Valid content",
                rating=RatingScale.GOOD
            )
    
    def test_feedback_entry_to_dict(self):
        """Test converting feedback entry to dictionary"""
        timestamp = datetime.now()
        metadata = FeedbackMetadata(
            source="test",
            version="1.0.0",
            context={"key": "value"},
            tags=["test"]
        )
        
        entry = FeedbackEntry(
            id="test-id",
            task_id="task-123",
            timestamp=timestamp,
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Test content",
            rating=RatingScale.GOOD,
            user_id="user-456",
            metadata=metadata
        )
        
        result = entry.to_dict()
        
        assert result["id"] == "test-id"
        assert result["task_id"] == "task-123"
        assert result["timestamp"] == timestamp.isoformat()
        assert result["feedback_type"] == "task_completion"
        assert result["content"] == "Test content"
        assert result["rating"] == 3
        assert result["user_id"] == "user-456"
        assert result["metadata"] is not None
    
    def test_feedback_entry_from_dict(self):
        """Test creating feedback entry from dictionary"""
        timestamp = datetime.now()
        data = {
            "id": "test-id",
            "task_id": "task-123",
            "timestamp": timestamp.isoformat(),
            "feedback_type": "task_completion",
            "content": "Test content",
            "rating": 3,
            "user_id": "user-456",
            "metadata": {
                "source": "test",
                "version": "1.0.0",
                "context": {"key": "value"},
                "tags": ["test"]
            }
        }
        
        entry = FeedbackEntry.from_dict(data)
        
        assert entry.id == "test-id"
        assert entry.task_id == "task-123"
        assert entry.feedback_type == FeedbackType.TASK_COMPLETION
        assert entry.content == "Test content"
        assert entry.rating == RatingScale.GOOD
        assert entry.user_id == "user-456"
        assert entry.metadata.source == "test"
    
    def test_feedback_entry_json_serialization(self):
        """Test JSON serialization and deserialization"""
        entry = FeedbackEntry(
            id="test-id",
            task_id="task-123",
            timestamp=datetime.now(),
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Test content",
            rating=RatingScale.GOOD
        )
        
        json_str = entry.to_json()
        restored_entry = FeedbackEntry.from_json(json_str)
        
        assert restored_entry.id == entry.id
        assert restored_entry.task_id == entry.task_id
        assert restored_entry.feedback_type == entry.feedback_type
        assert restored_entry.content == entry.content
        assert restored_entry.rating == entry.rating


class TestFeedbackMetadata:
    """Tests for FeedbackMetadata class"""
    
    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary"""
        metadata = FeedbackMetadata(
            source="test",
            version="1.0.0",
            context={"key": "value"},
            tags=["tag1", "tag2"]
        )
        
        result = metadata.to_dict()
        
        assert result["source"] == "test"
        assert result["version"] == "1.0.0"
        assert result["context"] == {"key": "value"}
        assert result["tags"] == ["tag1", "tag2"]
    
    def test_metadata_from_dict(self):
        """Test creating metadata from dictionary"""
        data = {
            "source": "test",
            "version": "1.0.0",
            "context": {"key": "value"},
            "tags": ["tag1", "tag2"]
        }
        
        metadata = FeedbackMetadata.from_dict(data)
        
        assert metadata.source == "test"
        assert metadata.version == "1.0.0"
        assert metadata.context == {"key": "value"}
        assert metadata.tags == ["tag1", "tag2"]


class TestFactoryFunctions:
    """Tests for factory functions"""
    
    def test_create_feedback_entry(self):
        """Test creating feedback entry with factory function"""
        entry = create_feedback_entry(
            task_id="task-123",
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Test feedback",
            rating=RatingScale.GOOD,
            user_id="user-456"
        )
        
        assert entry.task_id == "task-123"
        assert entry.feedback_type == FeedbackType.TASK_COMPLETION
        assert entry.content == "Test feedback"
        assert entry.rating == RatingScale.GOOD
        assert entry.user_id == "user-456"
        assert entry.id is not None
        assert entry.timestamp is not None
        assert entry.metadata is not None
    
    def test_validate_rating_valid(self):
        """Test rating validation with valid values"""
        assert validate_rating(1) == RatingScale.POOR
        assert validate_rating(3) == RatingScale.GOOD
        assert validate_rating(5) == RatingScale.EXCELLENT
    
    def test_validate_rating_invalid(self):
        """Test rating validation with invalid values"""
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            validate_rating(0)
        
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            validate_rating(6)
    
    def test_calculate_feedback_summary_empty(self):
        """Test calculating summary with empty feedback list"""
        summary = calculate_feedback_summary([])
        
        assert summary.total_feedback_count == 0
        assert summary.average_rating is None
        assert summary.rating_distribution == {}
        assert summary.feedback_types == {}
        assert summary.latest_feedback is None
    
    def test_calculate_feedback_summary_with_data(self):
        """Test calculating summary with feedback data"""
        entries = [
            create_feedback_entry(
                task_id="task-123",
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="Good work",
                rating=RatingScale.GOOD
            ),
            create_feedback_entry(
                task_id="task-123",
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="Excellent work",
                rating=RatingScale.EXCELLENT
            ),
            create_feedback_entry(
                task_id="task-123",
                feedback_type=FeedbackType.WORKER_PERFORMANCE,
                content="Worker did well",
                rating=RatingScale.VERY_GOOD
            )
        ]
        
        summary = calculate_feedback_summary(entries)
        
        assert summary.task_id == "task-123"
        assert summary.total_feedback_count == 3
        assert summary.average_rating == 4.0  # (3 + 5 + 4) / 3
        assert summary.rating_distribution == {3: 1, 5: 1, 4: 1}
        assert summary.feedback_types == {
            "task_completion": 2,
            "worker_performance": 1
        }
        assert summary.latest_feedback is not None


class TestRatingScale:
    """Tests for RatingScale enum"""
    
    def test_rating_scale_values(self):
        """Test rating scale enum values"""
        assert RatingScale.POOR.value == 1
        assert RatingScale.FAIR.value == 2
        assert RatingScale.GOOD.value == 3
        assert RatingScale.VERY_GOOD.value == 4
        assert RatingScale.EXCELLENT.value == 5


class TestFeedbackType:
    """Tests for FeedbackType enum"""
    
    def test_feedback_type_values(self):
        """Test feedback type enum values"""
        assert FeedbackType.TASK_COMPLETION.value == "task_completion"
        assert FeedbackType.WORKER_PERFORMANCE.value == "worker_performance"
        assert FeedbackType.MANAGER_REVIEW.value == "manager_review"
        assert FeedbackType.USER_RATING.value == "user_rating"
        assert FeedbackType.ERROR_REPORT.value == "error_report"
        assert FeedbackType.IMPROVEMENT_SUGGESTION.value == "improvement_suggestion"