"""Unit tests for FeedbackModel."""

import pytest
from datetime import datetime
import uuid

from claude_orchestrator.feedback_model import (
    FeedbackModel,
    FeedbackType,
    FeedbackSeverity,
    FeedbackCategory,
    FeedbackMetrics,
    FeedbackContext,
    create_success_feedback,
    create_error_feedback,
    create_performance_feedback
)


class TestFeedbackModel:
    """Test suite for FeedbackModel."""
    
    def test_feedback_model_creation(self):
        """Test basic FeedbackModel creation."""
        context = FeedbackContext(task_id="task123")
        feedback = FeedbackModel(
            feedback_type=FeedbackType.TASK_SUCCESS,
            severity=FeedbackSeverity.INFO,
            category=FeedbackCategory.EXECUTION,
            message="Task completed successfully",
            context=context
        )
        
        assert feedback.feedback_id
        assert feedback.feedback_type == FeedbackType.TASK_SUCCESS
        assert feedback.severity == FeedbackSeverity.INFO
        assert feedback.category == FeedbackCategory.EXECUTION
        assert feedback.message == "Task completed successfully"
        assert feedback.context.task_id == "task123"
        assert isinstance(feedback.timestamp, datetime)
    
    def test_feedback_validation_empty_message(self):
        """Test validation fails for empty message."""
        context = FeedbackContext(task_id="task123")
        
        with pytest.raises(ValueError, match="Message must be a non-empty string"):
            FeedbackModel(
                feedback_type=FeedbackType.TASK_SUCCESS,
                severity=FeedbackSeverity.INFO,
                category=FeedbackCategory.EXECUTION,
                message="",
                context=context
            )
    
    def test_feedback_validation_long_message(self):
        """Test validation fails for too long message."""
        context = FeedbackContext(task_id="task123")
        
        with pytest.raises(ValueError, match="Message too long"):
            FeedbackModel(
                feedback_type=FeedbackType.TASK_SUCCESS,
                severity=FeedbackSeverity.INFO,
                category=FeedbackCategory.EXECUTION,
                message="x" * 10001,
                context=context
            )
    
    def test_metrics_validation(self):
        """Test FeedbackMetrics validation."""
        # Valid metrics
        metrics = FeedbackMetrics(
            execution_time=10.5,
            memory_usage=512.0,
            cpu_usage=75.5,
            tokens_used=1000,
            quality_score=0.85,
            success_rate=0.9
        )
        metrics.validate()  # Should not raise
        
        # Invalid execution time
        with pytest.raises(ValueError, match="Execution time cannot be negative"):
            metrics = FeedbackMetrics(execution_time=-1)
            metrics.validate()
        
        # Invalid CPU usage
        with pytest.raises(ValueError, match="CPU usage must be between 0 and 100"):
            metrics = FeedbackMetrics(cpu_usage=150)
            metrics.validate()
        
        # Invalid quality score
        with pytest.raises(ValueError, match="Quality score must be between 0 and 1"):
            metrics = FeedbackMetrics(quality_score=1.5)
            metrics.validate()
    
    def test_context_validation(self):
        """Test FeedbackContext validation."""
        # Valid context
        context = FeedbackContext(
            task_id="task123",
            worker_id="worker456",
            tags=["tag1", "tag2"]
        )
        context.validate()  # Should not raise
        
        # Empty task_id
        with pytest.raises(ValueError, match="Task ID is required"):
            context = FeedbackContext(task_id="")
            context.validate()
        
        # Invalid tags type
        with pytest.raises(ValueError, match="Tags must be a list"):
            context = FeedbackContext(task_id="task123", tags="not_a_list")
            context.validate()
        
        # Invalid tag elements
        with pytest.raises(ValueError, match="All tags must be strings"):
            context = FeedbackContext(task_id="task123", tags=["tag1", 123])
            context.validate()
    
    def test_business_logic_validation(self):
        """Test business logic validation rules."""
        context = FeedbackContext(task_id="task123")
        
        # Critical severity with success - should fail
        with pytest.raises(ValueError, match="Critical severity should only be used"):
            FeedbackModel(
                feedback_type=FeedbackType.TASK_SUCCESS,
                severity=FeedbackSeverity.CRITICAL,
                category=FeedbackCategory.EXECUTION,
                message="Success",
                context=context
            )
        
        # Task success with error severity - should fail
        with pytest.raises(ValueError, match="Task success should not have error"):
            FeedbackModel(
                feedback_type=FeedbackType.TASK_SUCCESS,
                severity=FeedbackSeverity.ERROR,
                category=FeedbackCategory.EXECUTION,
                message="Success",
                context=context
            )
        
        # Performance feedback without metrics - should fail
        with pytest.raises(ValueError, match="Performance feedback should include metrics"):
            FeedbackModel(
                feedback_type=FeedbackType.WORKER_PERFORMANCE,
                severity=FeedbackSeverity.INFO,
                category=FeedbackCategory.PERFORMANCE,
                message="Performance report",
                context=context,
                metrics=FeedbackMetrics()  # No metrics set
            )
    
    def test_to_dict_conversion(self):
        """Test conversion to dictionary."""
        context = FeedbackContext(
            task_id="task123",
            worker_id="worker456",
            tags=["tag1", "tag2"]
        )
        metrics = FeedbackMetrics(
            execution_time=10.5,
            quality_score=0.85
        )
        
        feedback = FeedbackModel(
            feedback_id="test-id",
            feedback_type=FeedbackType.TASK_SUCCESS,
            severity=FeedbackSeverity.INFO,
            category=FeedbackCategory.EXECUTION,
            message="Test message",
            details={"key": "value"},
            context=context,
            metrics=metrics,
            source="test"
        )
        
        data = feedback.to_dict()
        
        assert data["feedback_id"] == "test-id"
        assert data["feedback_type"] == "task_success"
        assert data["severity"] == "info"
        assert data["category"] == "execution"
        assert data["message"] == "Test message"
        assert data["details"] == {"key": "value"}
        assert data["context"]["task_id"] == "task123"
        assert data["context"]["worker_id"] == "worker456"
        assert data["context"]["tags"] == ["tag1", "tag2"]
        assert data["metrics"]["execution_time"] == 10.5
        assert data["metrics"]["quality_score"] == 0.85
        assert data["source"] == "test"
        assert "timestamp" in data
    
    def test_from_dict_conversion(self):
        """Test creation from dictionary."""
        data = {
            "feedback_id": "test-id",
            "feedback_type": "task_success",
            "severity": "info",
            "category": "execution",
            "message": "Test message",
            "details": {"key": "value"},
            "context": {
                "task_id": "task123",
                "worker_id": "worker456",
                "tags": ["tag1", "tag2"]
            },
            "metrics": {
                "execution_time": 10.5,
                "quality_score": 0.85
            },
            "timestamp": datetime.now().isoformat(),
            "source": "test"
        }
        
        feedback = FeedbackModel.from_dict(data)
        
        assert feedback.feedback_id == "test-id"
        assert feedback.feedback_type == FeedbackType.TASK_SUCCESS
        assert feedback.severity == FeedbackSeverity.INFO
        assert feedback.category == FeedbackCategory.EXECUTION
        assert feedback.message == "Test message"
        assert feedback.details == {"key": "value"}
        assert feedback.context.task_id == "task123"
        assert feedback.context.worker_id == "worker456"
        assert feedback.context.tags == ["tag1", "tag2"]
        assert feedback.metrics.execution_time == 10.5
        assert feedback.metrics.quality_score == 0.85
        assert feedback.source == "test"
    
    def test_helper_create_success_feedback(self):
        """Test create_success_feedback helper."""
        metrics = FeedbackMetrics(execution_time=5.0)
        feedback = create_success_feedback(
            task_id="task123",
            message="Task completed",
            metrics=metrics,
            worker_id="worker456"
        )
        
        assert feedback.feedback_type == FeedbackType.TASK_SUCCESS
        assert feedback.severity == FeedbackSeverity.INFO
        assert feedback.category == FeedbackCategory.EXECUTION
        assert feedback.message == "Task completed"
        assert feedback.context.task_id == "task123"
        assert feedback.context.worker_id == "worker456"
        assert feedback.metrics.execution_time == 5.0
    
    def test_helper_create_error_feedback(self):
        """Test create_error_feedback helper."""
        error_details = {"error_code": "E001", "stack_trace": "..."}
        feedback = create_error_feedback(
            task_id="task123",
            message="Task failed",
            error_details=error_details,
            severity=FeedbackSeverity.CRITICAL,
            worker_id="worker456"
        )
        
        assert feedback.feedback_type == FeedbackType.ERROR_REPORT
        assert feedback.severity == FeedbackSeverity.CRITICAL
        assert feedback.category == FeedbackCategory.EXECUTION
        assert feedback.message == "Task failed"
        assert feedback.details == error_details
        assert feedback.context.task_id == "task123"
        assert feedback.context.worker_id == "worker456"
    
    def test_helper_create_performance_feedback(self):
        """Test create_performance_feedback helper."""
        feedback = create_performance_feedback(
            task_id="task123",
            message="Performance metrics",
            execution_time=10.5,
            cpu_usage=75.0,
            memory_usage=512.0,
            worker_id="worker456"
        )
        
        assert feedback.feedback_type == FeedbackType.WORKER_PERFORMANCE
        assert feedback.severity == FeedbackSeverity.INFO
        assert feedback.category == FeedbackCategory.PERFORMANCE
        assert feedback.message == "Performance metrics"
        assert feedback.context.task_id == "task123"
        assert feedback.context.worker_id == "worker456"
        assert feedback.metrics.execution_time == 10.5
        assert feedback.metrics.cpu_usage == 75.0
        assert feedback.metrics.memory_usage == 512.0
    
    def test_feedback_id_generation(self):
        """Test automatic feedback ID generation."""
        context = FeedbackContext(task_id="task123")
        feedback1 = FeedbackModel(
            feedback_type=FeedbackType.TASK_SUCCESS,
            severity=FeedbackSeverity.INFO,
            category=FeedbackCategory.EXECUTION,
            message="Test",
            context=context
        )
        
        feedback2 = FeedbackModel(
            feedback_type=FeedbackType.TASK_SUCCESS,
            severity=FeedbackSeverity.INFO,
            category=FeedbackCategory.EXECUTION,
            message="Test",
            context=context
        )
        
        # IDs should be unique
        assert feedback1.feedback_id != feedback2.feedback_id
        
        # IDs should be valid UUIDs
        uuid.UUID(feedback1.feedback_id)
        uuid.UUID(feedback2.feedback_id)
    
    def test_all_enum_values(self):
        """Test all enum values work correctly."""
        context = FeedbackContext(task_id="task123")
        
        # Test all feedback types
        for feedback_type in FeedbackType:
            feedback = FeedbackModel(
                feedback_type=feedback_type,
                severity=FeedbackSeverity.INFO,
                category=FeedbackCategory.EXECUTION,
                message="Test",
                context=context
            )
            assert feedback.feedback_type == feedback_type
        
        # Test all severities (except CRITICAL with SUCCESS)
        for severity in FeedbackSeverity:
            if severity == FeedbackSeverity.CRITICAL:
                feedback_type = FeedbackType.ERROR_REPORT
            else:
                feedback_type = FeedbackType.TASK_SUCCESS
            
            feedback = FeedbackModel(
                feedback_type=feedback_type,
                severity=severity,
                category=FeedbackCategory.EXECUTION,
                message="Test",
                context=context
            )
            assert feedback.severity == severity
        
        # Test all categories
        for category in FeedbackCategory:
            # Add metrics for performance category
            if category == FeedbackCategory.PERFORMANCE:
                metrics = FeedbackMetrics(execution_time=1.0)
            else:
                metrics = FeedbackMetrics()
            
            feedback = FeedbackModel(
                feedback_type=FeedbackType.TASK_SUCCESS,
                severity=FeedbackSeverity.INFO,
                category=category,
                message="Test",
                context=context,
                metrics=metrics
            )
            assert feedback.category == category