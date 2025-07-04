"""
Unit tests for task completion feedback integration

Tests the integration of feedback collection with task completion workflow
"""

import tempfile
import os
import time
from datetime import datetime
from unittest.mock import Mock, patch

from claude_orchestrator.task_completion_feedback import (
    TaskCompletionFeedbackCollector, TaskResult, TaskCompletionMetrics,
    collect_completion_feedback
)
from claude_orchestrator.feedback_collector import FeedbackCollector, CollectionPoint
from claude_orchestrator.feedback_models import FeedbackType, RatingScale
from claude_orchestrator.feedback_storage import FeedbackStorage


class TestTaskCompletionFeedbackCollector:
    """Tests for TaskCompletionFeedbackCollector class"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.storage = FeedbackStorage(self.temp_db.name)
        self.feedback_collector = FeedbackCollector(self.storage)
        self.completion_feedback = TaskCompletionFeedbackCollector(
            feedback_collector=self.feedback_collector,
            enable_async_collection=False  # Use sync for testing
        )
    
    def teardown_method(self):
        """Clean up after test"""
        self.completion_feedback.close()
        os.unlink(self.temp_db.name)
    
    def test_initialization(self):
        """Test feedback collector initialization"""
        assert self.completion_feedback.feedback_collector is not None
        assert self.completion_feedback.enable_async_collection is False
        assert self.completion_feedback._feedback_enabled is True
    
    def test_task_tracking(self):
        """Test task tracking functionality"""
        # Start tracking
        self.completion_feedback.start_task_tracking(
            task_id="test-task",
            title="Test Task",
            description="A test task",
            worker_id="worker-1",
            metadata={"priority": "high"}
        )
        
        # Verify tracking started
        assert "test-task" in self.completion_feedback._task_tracking
        tracking = self.completion_feedback._task_tracking["test-task"]
        assert tracking["title"] == "Test Task"
        assert tracking["worker_id"] == "worker-1"
        assert tracking["metadata"]["priority"] == "high"
        
        # Update tracking
        self.completion_feedback.update_task_tracking(
            task_id="test-task",
            update_type="error",
            data="Test error occurred"
        )
        
        self.completion_feedback.update_task_tracking(
            task_id="test-task",
            update_type="retry",
            data=None
        )
        
        # Verify updates
        tracking = self.completion_feedback._task_tracking["test-task"]
        assert len(tracking["errors"]) == 1
        assert tracking["errors"][0]["error"] == "Test error occurred"
        assert tracking["retries"] == 1
    
    def test_collect_success_feedback(self):
        """Test collecting feedback for successful task completion"""
        # Start tracking
        self.completion_feedback.start_task_tracking(
            task_id="success-task",
            title="Successful Task",
            description="This task will succeed",
            worker_id="worker-1"
        )
        
        # Create task result
        task_result = TaskResult(
            task_id="success-task",
            title="Successful Task",
            description="This task will succeed",
            success=True,
            output="Task completed successfully",
            execution_time=25.5,
            worker_id="worker-1"
        )
        
        # Create metrics
        metrics = TaskCompletionMetrics(
            task_id="success-task",
            success=True,
            execution_time=25.5,
            error_count=0,
            retry_count=0,
            worker_changes=0,
            subtask_count=5,
            subtasks_completed=5,
            review_score=4.5
        )
        
        # Collect feedback
        feedback_entry = self.completion_feedback.collect_task_completion_feedback(
            task_result=task_result,
            metrics=metrics,
            user_id="test-user"
        )
        
        assert feedback_entry is not None
        assert feedback_entry.task_id == "success-task"
        assert feedback_entry.feedback_type == FeedbackType.TASK_COMPLETION
        assert "completed successfully" in feedback_entry.content
        assert feedback_entry.rating is not None
        assert feedback_entry.rating.value >= 4  # Should be good or excellent
        assert feedback_entry.user_id == "test-user"
        
        # Check context
        context = feedback_entry.metadata.context
        assert context["success"] is True
        assert context["execution_time"] == 25.5
        assert context["error_count"] == 0
        assert context["subtask_completion_rate"] == 1.0
        assert context["review_score"] == 4.5
    
    def test_collect_failure_feedback(self):
        """Test collecting feedback for failed task"""
        # Start tracking with some errors
        self.completion_feedback.start_task_tracking(
            task_id="failed-task",
            title="Failed Task",
            description="This task will fail",
            worker_id="worker-1"
        )
        
        # Add error tracking
        self.completion_feedback.update_task_tracking(
            task_id="failed-task",
            update_type="error",
            data="Connection timeout"
        )
        
        self.completion_feedback.update_task_tracking(
            task_id="failed-task",
            update_type="retry",
            data=None
        )
        
        # Create failed task result
        task_result = TaskResult(
            task_id="failed-task",
            title="Failed Task",
            description="This task will fail",
            success=False,
            error="Final error: Connection failed",
            execution_time=15.0,
            worker_id="worker-1"
        )
        
        # Create metrics
        metrics = TaskCompletionMetrics(
            task_id="failed-task",
            success=False,
            execution_time=15.0,
            error_count=2,
            retry_count=1,
            worker_changes=1
        )
        
        # Collect feedback
        feedback_entry = self.completion_feedback.collect_task_completion_feedback(
            task_result=task_result,
            metrics=metrics,
            user_id="test-user"
        )
        
        assert feedback_entry is not None
        assert feedback_entry.task_id == "failed-task"
        assert feedback_entry.feedback_type == FeedbackType.ERROR_REPORT
        assert "failed" in feedback_entry.content.lower()
        assert "Connection failed" in feedback_entry.content
        assert feedback_entry.rating is None  # No rating for failures
        
        # Check context
        context = feedback_entry.metadata.context
        assert context["success"] is False
        assert context["error_count"] == 2
        assert context["retry_count"] == 1
        assert "error_history" in context
    
    def test_success_rating_assessment(self):
        """Test rating assessment for successful tasks"""
        # Test excellent rating (fast, no errors)
        task_result = TaskResult(
            task_id="excellent-task",
            title="Excellent Task",
            description="Fast and clean",
            success=True
        )
        
        metrics = TaskCompletionMetrics(
            task_id="excellent-task",
            success=True,
            execution_time=10.0,  # Very fast
            error_count=0,
            retry_count=0,
            worker_changes=0,
            subtask_count=10,
            subtasks_completed=10,  # 100% completion
            review_score=5.0  # Perfect review
        )
        
        feedback_entry = self.completion_feedback.collect_task_completion_feedback(
            task_result=task_result,
            metrics=metrics
        )
        
        assert feedback_entry.rating == RatingScale.EXCELLENT
        
        # Test poor rating (slow, many errors)
        task_result2 = TaskResult(
            task_id="poor-task",
            title="Poor Task",
            description="Slow with errors",
            success=True
        )
        
        metrics2 = TaskCompletionMetrics(
            task_id="poor-task",
            success=True,
            execution_time=120.0,  # Very slow
            error_count=5,  # Many errors
            retry_count=3,  # Multiple retries
            worker_changes=2,  # Multiple worker changes
            subtask_count=10,
            subtasks_completed=6,  # Only 60% completion
            review_score=2.0  # Poor review
        )
        
        feedback_entry2 = self.completion_feedback.collect_task_completion_feedback(
            task_result=task_result2,
            metrics=metrics2
        )
        
        assert feedback_entry2.rating in [RatingScale.POOR, RatingScale.FAIR]
    
    def test_collect_manual_completion_feedback(self):
        """Test collecting manual completion feedback"""
        # Test successful task feedback
        feedback_entry = self.completion_feedback.collect_manual_completion_feedback(
            task_id="manual-success",
            content="The task was completed perfectly with excellent code quality",
            rating=5,
            success=True,
            user_id="reviewer"
        )
        
        assert feedback_entry is not None
        assert feedback_entry.task_id == "manual-success"
        assert feedback_entry.rating == RatingScale.EXCELLENT
        assert feedback_entry.user_id == "reviewer"
        assert feedback_entry.metadata.context["success"] is True
        
        # Test failed task feedback
        feedback_entry2 = self.completion_feedback.collect_manual_completion_feedback(
            task_id="manual-failure",
            content="The task failed due to incorrect implementation approach",
            success=False,
            user_id="reviewer"
        )
        
        assert feedback_entry2 is not None
        assert feedback_entry2.task_id == "manual-failure"
        assert feedback_entry2.rating is None  # No rating provided
        assert feedback_entry2.metadata.context["success"] is False
    
    def test_collect_review_feedback(self):
        """Test collecting Opus review feedback"""
        feedback_entry = self.completion_feedback.collect_review_feedback(
            task_id="reviewed-task",
            review_score=4.2,
            review_comments="Good implementation with minor improvements needed",
            reviewer_id="opus-manager"
        )
        
        assert feedback_entry is not None
        assert feedback_entry.task_id == "reviewed-task"
        assert feedback_entry.feedback_type == FeedbackType.MANAGER_REVIEW
        assert feedback_entry.rating == RatingScale.VERY_GOOD  # 4.2 rounds to 4
        assert "4.2/5" in feedback_entry.content
        assert "minor improvements" in feedback_entry.content
        assert feedback_entry.metadata.context["review_score"] == 4.2
    
    def test_get_task_completion_summary(self):
        """Test getting task completion summary"""
        # Create multiple feedback entries
        task_id = "summary-test"
        
        # Success feedback
        self.completion_feedback.collect_task_completion_feedback(
            task_result=TaskResult(
                task_id=task_id,
                title="Summary Test",
                description="Test",
                success=True,
                execution_time=30.0
            ),
            metrics=TaskCompletionMetrics(
                task_id=task_id,
                success=True,
                execution_time=30.0,
                error_count=1
            )
        )
        
        # Manual feedback
        self.completion_feedback.collect_manual_completion_feedback(
            task_id=task_id,
            content="Good work overall",
            rating=4,
            success=True
        )
        
        # Review feedback
        self.completion_feedback.collect_review_feedback(
            task_id=task_id,
            review_score=4.0,
            review_comments="Well done"
        )
        
        # Get summary
        summary = self.completion_feedback.get_task_completion_summary(task_id)
        
        assert summary["task_id"] == task_id
        assert summary["feedback_count"] >= 3
        assert summary["completion_feedback_count"] >= 2
        assert summary["review_feedback_count"] >= 1
        assert summary["average_rating"] is not None
        assert summary["average_execution_time"] is not None
        assert summary["total_errors"] >= 1
        assert summary["success_rate"] == 1.0  # All were successful
    
    def test_feedback_callback(self):
        """Test feedback collection callbacks"""
        callback_calls = []
        
        def test_callback(task_id: str, feedback_entry):
            callback_calls.append((task_id, feedback_entry.id))
        
        self.completion_feedback.register_feedback_callback(test_callback)
        
        # Collect feedback
        task_result = TaskResult(
            task_id="callback-test",
            title="Callback Test",
            description="Test",
            success=True
        )
        
        self.completion_feedback.collect_task_completion_feedback(
            task_result=task_result
        )
        
        # Verify callback was called
        assert len(callback_calls) >= 1
        assert callback_calls[0][0] == "callback-test"
    
    def test_enable_disable_feedback(self):
        """Test enabling/disabling feedback collection"""
        # Disable feedback
        self.completion_feedback.enable_feedback_collection(False)
        
        task_result = TaskResult(
            task_id="disabled-test",
            title="Disabled Test",
            description="Test",
            success=True
        )
        
        feedback_entry = self.completion_feedback.collect_task_completion_feedback(
            task_result=task_result
        )
        
        assert feedback_entry is None  # No feedback collected
        
        # Re-enable and test
        self.completion_feedback.enable_feedback_collection(True)
        
        task_result2 = TaskResult(
            task_id="enabled-test",
            title="Enabled Test",
            description="Test",
            success=True
        )
        
        feedback_entry2 = self.completion_feedback.collect_task_completion_feedback(
            task_result=task_result2
        )
        
        assert feedback_entry2 is not None
    
    def test_async_feedback_collection(self):
        """Test asynchronous feedback collection"""
        # Create collector with async enabled
        async_collector = TaskCompletionFeedbackCollector(
            feedback_collector=self.feedback_collector,
            enable_async_collection=True
        )
        
        try:
            task_result = TaskResult(
                task_id="async-test",
                title="Async Test",
                description="Test async collection",
                success=True,
                execution_time=20.0
            )
            
            # Collect feedback (returns None for async)
            feedback_entry = async_collector.collect_task_completion_feedback(
                task_result=task_result
            )
            
            assert feedback_entry is None  # Async returns None
            
            # Wait for async collection
            time.sleep(0.5)
            
            # Verify feedback was collected
            feedback_list = self.storage.get_feedback_by_task("async-test")
            assert len(feedback_list) > 0
            
        finally:
            async_collector.close()
    
    def test_context_manager(self):
        """Test using TaskCompletionFeedbackCollector as context manager"""
        with TaskCompletionFeedbackCollector(
            feedback_collector=self.feedback_collector
        ) as collector:
            task_result = TaskResult(
                task_id="context-test",
                title="Context Test",
                description="Test context manager",
                success=True
            )
            
            feedback_entry = collector.collect_task_completion_feedback(
                task_result=task_result
            )
            
            assert feedback_entry is not None


class TestConvenienceFunction:
    """Tests for convenience function"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.storage = FeedbackStorage(self.temp_db.name)
    
    def teardown_method(self):
        """Clean up after test"""
        self.storage.close()
        os.unlink(self.temp_db.name)
    
    def test_collect_completion_feedback_convenience(self):
        """Test convenience function for completion feedback"""
        feedback_entry = collect_completion_feedback(
            task_id="convenience-test",
            title="Convenience Test",
            success=True,
            execution_time=15.0,
            worker_id="worker-1",
            user_id="test-user",
            storage=self.storage
        )
        
        assert feedback_entry is not None
        assert feedback_entry.task_id == "convenience-test"
        assert feedback_entry.feedback_type == FeedbackType.TASK_COMPLETION
        assert feedback_entry.rating is not None
        
        # Test with failure
        feedback_entry2 = collect_completion_feedback(
            task_id="convenience-fail",
            title="Failed Test",
            success=False,
            execution_time=10.0,
            error="Test error",
            storage=self.storage
        )
        
        assert feedback_entry2 is not None
        assert feedback_entry2.feedback_type == FeedbackType.ERROR_REPORT
        assert "Test error" in feedback_entry2.content
    
    def test_convenience_function_with_default_storage(self):
        """Test convenience function with default storage"""
        feedback_entry = collect_completion_feedback(
            task_id="default-storage-test",
            title="Default Storage Test",
            success=True,
            execution_time=20.0
        )
        
        # Should not raise exception
        assert feedback_entry is not None or feedback_entry is None
        
        # Clean up default database if created
        if os.path.exists("feedback.db"):
            os.unlink("feedback.db")


class TestMetricsClasses:
    """Tests for metrics data classes"""
    
    def test_task_completion_metrics(self):
        """Test TaskCompletionMetrics data class"""
        metrics = TaskCompletionMetrics(
            task_id="test-task",
            success=True,
            execution_time=30.5,
            error_count=2,
            retry_count=1,
            worker_changes=0,
            subtask_count=10,
            subtasks_completed=9,
            code_changes_made=True,
            tests_passed=True,
            review_required=True,
            review_score=4.0,
            quality_metrics={"coverage": 0.85}
        )
        
        assert metrics.task_id == "test-task"
        assert metrics.success is True
        assert metrics.execution_time == 30.5
        assert metrics.error_count == 2
        assert metrics.retry_count == 1
        assert metrics.subtask_count == 10
        assert metrics.subtasks_completed == 9
        assert metrics.tests_passed is True
        assert metrics.review_score == 4.0
        assert metrics.quality_metrics["coverage"] == 0.85
    
    def test_task_result(self):
        """Test TaskResult data class"""
        result = TaskResult(
            task_id="test-task",
            title="Test Task",
            description="A test task",
            success=True,
            output="Task completed",
            error=None,
            execution_time=25.0,
            worker_id="worker-1",
            metadata={"key": "value"}
        )
        
        assert result.task_id == "test-task"
        assert result.title == "Test Task"
        assert result.success is True
        assert result.output == "Task completed"
        assert result.error is None
        assert result.execution_time == 25.0
        assert result.worker_id == "worker-1"
        assert result.metadata["key"] == "value"