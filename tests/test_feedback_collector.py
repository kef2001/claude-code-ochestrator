"""
Unit tests for feedback collector module

Tests the feedback collection functionality and integration with storage
"""

import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch

from claude_orchestrator.feedback_collector import (
    FeedbackCollector, FeedbackPrompt, FeedbackRequest, CollectionPoint,
    FeedbackValidationError, collect_task_feedback, collect_worker_feedback,
    collect_error_feedback
)
from claude_orchestrator.feedback_models import (
    FeedbackType, RatingScale, create_feedback_entry
)
from claude_orchestrator.feedback_storage import FeedbackStorage


class TestFeedbackPrompt:
    """Tests for FeedbackPrompt class"""
    
    def test_create_feedback_prompt(self):
        """Test creating a feedback prompt"""
        prompt = FeedbackPrompt(
            prompt_text="How was the task?",
            feedback_type=FeedbackType.TASK_COMPLETION,
            requires_rating=True,
            max_content_length=200
        )
        
        assert prompt.prompt_text == "How was the task?"
        assert prompt.feedback_type == FeedbackType.TASK_COMPLETION
        assert prompt.requires_rating is True
        assert prompt.max_content_length == 200
        assert prompt.validation_rules == {}
    
    def test_feedback_prompt_with_validation_rules(self):
        """Test feedback prompt with custom validation rules"""
        validation_rules = {
            "min_length": 10,
            "required_keywords": ["quality", "performance"]
        }
        
        prompt = FeedbackPrompt(
            prompt_text="Detailed feedback please",
            feedback_type=FeedbackType.MANAGER_REVIEW,
            validation_rules=validation_rules
        )
        
        assert prompt.validation_rules == validation_rules


class TestFeedbackRequest:
    """Tests for FeedbackRequest dataclass"""
    
    def test_create_feedback_request(self):
        """Test creating a feedback request"""
        prompt = FeedbackPrompt(
            prompt_text="Test prompt",
            feedback_type=FeedbackType.TASK_COMPLETION
        )
        
        request = FeedbackRequest(
            task_id="test-task",
            collection_point=CollectionPoint.TASK_COMPLETION,
            prompt=prompt,
            context={"key": "value"},
            user_id="test-user",
            timeout_seconds=120
        )
        
        assert request.task_id == "test-task"
        assert request.collection_point == CollectionPoint.TASK_COMPLETION
        assert request.prompt == prompt
        assert request.context == {"key": "value"}
        assert request.user_id == "test-user"
        assert request.timeout_seconds == 120


class TestFeedbackCollector:
    """Tests for FeedbackCollector class"""
    
    def setup_method(self):
        """Set up test environment"""
        # Create temporary database for each test
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.storage = FeedbackStorage(self.temp_db.name)
        self.collector = FeedbackCollector(self.storage)
    
    def teardown_method(self):
        """Clean up after each test"""
        self.collector.close()
        os.unlink(self.temp_db.name)
    
    def test_collector_initialization(self):
        """Test feedback collector initialization"""
        assert self.collector.storage is not None
        assert len(self.collector._prompts) > 0
        assert CollectionPoint.TASK_COMPLETION in self.collector._prompts
    
    def test_collector_with_default_storage(self):
        """Test creating collector with default storage"""
        collector = FeedbackCollector()
        assert collector.storage is not None
        collector.close()
        
        # Clean up default database if it exists
        if os.path.exists("feedback.db"):
            os.unlink("feedback.db")
    
    def test_register_collection_handler(self):
        """Test registering collection handlers"""
        called_requests = []
        called_entries = []
        
        def test_handler(request: FeedbackRequest, entry):
            called_requests.append(request)
            called_entries.append(entry)
        
        self.collector.register_collection_handler(
            CollectionPoint.TASK_COMPLETION,
            test_handler
        )
        
        # Collect feedback to trigger handler
        entry = self.collector.collect_feedback(
            task_id="test-task",
            collection_point=CollectionPoint.TASK_COMPLETION,
            content="Test feedback",
            rating=RatingScale.GOOD
        )
        
        assert len(called_requests) == 1
        assert len(called_entries) == 1
        assert called_requests[0].task_id == "test-task"
        assert called_entries[0] == entry
    
    def test_set_custom_prompt(self):
        """Test setting custom prompt"""
        custom_prompt = FeedbackPrompt(
            prompt_text="Custom prompt text",
            feedback_type=FeedbackType.USER_RATING,
            requires_rating=False
        )
        
        self.collector.set_prompt(CollectionPoint.MANUAL_FEEDBACK, custom_prompt)
        
        retrieved = self.collector.get_feedback_prompt(CollectionPoint.MANUAL_FEEDBACK)
        assert retrieved == custom_prompt
        assert retrieved.prompt_text == "Custom prompt text"
    
    def test_collect_basic_feedback(self):
        """Test collecting basic feedback"""
        entry = self.collector.collect_feedback(
            task_id="test-task-123",
            collection_point=CollectionPoint.TASK_COMPLETION,
            content="Task completed well",
            rating=RatingScale.VERY_GOOD,
            user_id="test-user"
        )
        
        assert entry.task_id == "test-task-123"
        assert entry.content == "Task completed well"
        assert entry.rating == RatingScale.VERY_GOOD
        assert entry.user_id == "test-user"
        assert entry.feedback_type == FeedbackType.TASK_COMPLETION
        
        # Verify it was stored
        stored = self.storage.get_feedback(entry.id)
        assert stored is not None
        assert stored.id == entry.id
    
    def test_collect_feedback_with_integer_rating(self):
        """Test collecting feedback with integer rating"""
        entry = self.collector.collect_feedback(
            task_id="test-task",
            collection_point=CollectionPoint.TASK_COMPLETION,
            content="Good work",
            rating=4  # Integer rating
        )
        
        assert entry.rating == RatingScale.VERY_GOOD
    
    def test_collect_feedback_validation_error_empty_content(self):
        """Test validation error for empty content"""
        try:
            self.collector.collect_feedback(
                task_id="test-task",
                collection_point=CollectionPoint.TASK_COMPLETION,
                content="",  # Empty content
                rating=RatingScale.GOOD
            )
            assert False, "Should have raised validation error"
        except FeedbackValidationError as e:
            assert "cannot be empty" in str(e)
    
    def test_collect_feedback_validation_error_content_too_long(self):
        """Test validation error for content too long"""
        long_content = "x" * 1000  # Much longer than default 500 char limit
        
        try:
            self.collector.collect_feedback(
                task_id="test-task",
                collection_point=CollectionPoint.TASK_COMPLETION,
                content=long_content,
                rating=RatingScale.GOOD
            )
            assert False, "Should have raised validation error"
        except FeedbackValidationError as e:
            assert "too long" in str(e)
    
    def test_collect_feedback_validation_error_missing_required_rating(self):
        """Test validation error for missing required rating"""
        try:
            self.collector.collect_feedback(
                task_id="test-task",
                collection_point=CollectionPoint.TASK_COMPLETION,  # Requires rating
                content="Good feedback",
                rating=None  # Missing rating
            )
            assert False, "Should have raised validation error"
        except FeedbackValidationError as e:
            assert "required" in str(e)
    
    def test_collect_feedback_validation_error_invalid_rating_type(self):
        """Test validation error for invalid rating type"""
        try:
            self.collector.collect_feedback(
                task_id="test-task",
                collection_point=CollectionPoint.TASK_COMPLETION,
                content="Good feedback",
                rating="invalid"  # Invalid type
            )
            assert False, "Should have raised validation error"
        except FeedbackValidationError as e:
            assert "Invalid rating type" in str(e)
    
    def test_collect_feedback_no_prompt_configured(self):
        """Test error when no prompt is configured"""
        # Remove a prompt
        del self.collector._prompts[CollectionPoint.TASK_COMPLETION]
        
        try:
            self.collector.collect_feedback(
                task_id="test-task",
                collection_point=CollectionPoint.TASK_COMPLETION,
                content="Test feedback"
            )
            assert False, "Should have raised validation error"
        except FeedbackValidationError as e:
            assert "No prompt configured" in str(e)
    
    def test_collect_task_completion_feedback_success(self):
        """Test collecting automatic task completion feedback for success"""
        entry = self.collector.collect_task_completion_feedback(
            task_id="test-task",
            success=True,
            execution_time=25.5,
            worker_id="worker-123",
            user_id="test-user"
        )
        
        assert entry.task_id == "test-task"
        assert "successfully" in entry.content
        assert "25.50 seconds" in entry.content
        assert "worker-123" in entry.content
        assert entry.rating == RatingScale.EXCELLENT  # Fast execution
        assert entry.metadata.context["success"] is True
        assert entry.metadata.context["execution_time"] == 25.5
        assert entry.metadata.context["worker_id"] == "worker-123"
        assert entry.metadata.context["auto_generated"] is True
    
    def test_collect_task_completion_feedback_failure(self):
        """Test collecting automatic task completion feedback for failure"""
        errors = ["Network timeout", "Invalid response"]
        
        entry = self.collector.collect_task_completion_feedback(
            task_id="test-task",
            success=False,
            execution_time=120.0,
            errors=errors
        )
        
        assert "with failures" in entry.content
        assert "Network timeout; Invalid response" in entry.content
        assert entry.rating == RatingScale.POOR
        assert entry.metadata.context["success"] is False
        assert entry.metadata.context["errors"] == errors
    
    def test_collect_worker_performance_feedback(self):
        """Test collecting worker performance feedback"""
        issues = ["Slow response", "Memory usage"]
        
        entry = self.collector.collect_worker_performance_feedback(
            task_id="test-task",
            worker_id="worker-456",
            performance_score=0.75,
            issues=issues
        )
        
        assert entry.task_id == "test-task"
        assert "worker-456" in entry.content
        assert "0.75" in entry.content
        assert "Slow response; Memory usage" in entry.content
        assert entry.rating == RatingScale.VERY_GOOD  # 0.75 score
        assert entry.metadata.context["worker_id"] == "worker-456"
        assert entry.metadata.context["performance_score"] == 0.75
        assert entry.metadata.context["issues"] == issues
    
    def test_collect_error_feedback(self):
        """Test collecting error feedback"""
        stack_trace = "Traceback (most recent call last):\n  File..."
        
        entry = self.collector.collect_error_feedback(
            task_id="test-task",
            error_message="Connection failed",
            error_type="NetworkError",
            stack_trace=stack_trace
        )
        
        assert entry.task_id == "test-task"
        assert "NetworkError" in entry.content
        assert "Connection failed" in entry.content
        assert stack_trace in entry.content
        assert entry.rating is None  # Error feedback doesn't have rating
        assert entry.feedback_type == FeedbackType.ERROR_REPORT
        assert entry.metadata.context["error_type"] == "NetworkError"
        assert entry.metadata.context["error_message"] == "Connection failed"
    
    def test_get_task_feedback(self):
        """Test getting all feedback for a task"""
        task_id = "multi-feedback-task"
        
        # Create multiple feedback entries
        entries = []
        for i in range(3):
            entry = self.collector.collect_feedback(
                task_id=task_id,
                collection_point=CollectionPoint.TASK_COMPLETION,
                content=f"Feedback {i}",
                rating=RatingScale.GOOD
            )
            entries.append(entry)
        
        # Get all feedback for the task
        task_feedback = self.collector.get_task_feedback(task_id)
        assert len(task_feedback) == 3
        
        # Check that all entries are present
        stored_ids = {f.id for f in task_feedback}
        created_ids = {e.id for e in entries}
        assert stored_ids == created_ids
    
    def test_get_feedback_summary(self):
        """Test getting feedback summary for a task"""
        task_id = "summary-task"
        
        # Create feedback with different ratings
        ratings = [RatingScale.POOR, RatingScale.GOOD, RatingScale.EXCELLENT]
        for rating in ratings:
            self.collector.collect_feedback(
                task_id=task_id,
                collection_point=CollectionPoint.TASK_COMPLETION,
                content=f"Feedback with rating {rating.value}",
                rating=rating
            )
        
        summary = self.collector.get_feedback_summary(task_id)
        assert summary.task_id == task_id
        assert summary.total_feedback_count == 3
        assert summary.average_rating == 3.0  # (1 + 3 + 5) / 3
    
    def test_context_manager(self):
        """Test using FeedbackCollector as context manager"""
        with FeedbackCollector(self.storage) as collector:
            entry = collector.collect_feedback(
                task_id="context-test",
                collection_point=CollectionPoint.TASK_COMPLETION,
                content="Context manager test",
                rating=RatingScale.GOOD
            )
            
            assert entry is not None
    
    def test_custom_validation_rules(self):
        """Test custom validation rules in prompts"""
        # Set prompt with custom validation
        custom_prompt = FeedbackPrompt(
            prompt_text="Detailed feedback required",
            feedback_type=FeedbackType.MANAGER_REVIEW,
            validation_rules={
                "min_length": 20,
                "required_keywords": ["quality", "performance"]
            }
        )
        
        self.collector.set_prompt(CollectionPoint.REVIEW_COMPLETION, custom_prompt)
        
        # Test validation failure - too short
        try:
            self.collector.collect_feedback(
                task_id="test-task",
                collection_point=CollectionPoint.REVIEW_COMPLETION,
                content="Too short"  # Less than 20 chars
            )
            assert False, "Should have failed validation"
        except FeedbackValidationError as e:
            assert "too short" in str(e)
        
        # Test validation failure - missing keywords
        try:
            self.collector.collect_feedback(
                task_id="test-task",
                collection_point=CollectionPoint.REVIEW_COMPLETION,
                content="This is a long enough feedback but missing required words"
            )
            assert False, "Should have failed validation"
        except FeedbackValidationError as e:
            assert "Missing required keywords" in str(e)
        
        # Test validation success
        entry = self.collector.collect_feedback(
            task_id="test-task",
            collection_point=CollectionPoint.REVIEW_COMPLETION,
            content="This feedback discusses quality and performance in detail, meeting all requirements"
        )
        assert entry is not None


class TestConvenienceFunctions:
    """Tests for convenience functions"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.storage = FeedbackStorage(self.temp_db.name)
    
    def teardown_method(self):
        """Clean up after test"""
        self.storage.close()
        os.unlink(self.temp_db.name)
    
    def test_collect_task_feedback_convenience(self):
        """Test convenience function for task feedback"""
        entry = collect_task_feedback(
            task_id="conv-test-task",
            success=True,
            execution_time=30.0,
            worker_id="worker-123",
            storage=self.storage
        )
        
        assert entry.task_id == "conv-test-task"
        assert "successfully" in entry.content
        assert "worker-123" in entry.content
        assert entry.rating == RatingScale.EXCELLENT
    
    def test_collect_worker_feedback_convenience(self):
        """Test convenience function for worker feedback"""
        entry = collect_worker_feedback(
            task_id="conv-test-task",
            worker_id="worker-456",
            performance_score=0.8,
            issues=["Minor delay"],
            storage=self.storage
        )
        
        assert entry.task_id == "conv-test-task"
        assert "worker-456" in entry.content
        assert "0.8" in entry.content
        assert entry.rating == RatingScale.VERY_GOOD
    
    def test_collect_error_feedback_convenience(self):
        """Test convenience function for error feedback"""
        entry = collect_error_feedback(
            task_id="conv-test-task",
            error_message="Test error",
            error_type="TestError",
            storage=self.storage
        )
        
        assert entry.task_id == "conv-test-task"
        assert "TestError" in entry.content
        assert "Test error" in entry.content
        assert entry.feedback_type == FeedbackType.ERROR_REPORT
    
    def test_convenience_functions_with_default_storage(self):
        """Test convenience functions with default storage"""
        # Test that functions work without explicit storage
        entry = collect_task_feedback(
            task_id="default-storage-test",
            success=True,
            execution_time=15.0
        )
        
        assert entry is not None
        assert entry.task_id == "default-storage-test"
        
        # Clean up default database if created
        if os.path.exists("feedback.db"):
            os.unlink("feedback.db")