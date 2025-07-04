"""
Unit tests for worker allocation feedback integration

Tests the integration of feedback collection with worker allocation workflow
"""

import tempfile
import os
import time
from unittest.mock import Mock, patch

from claude_orchestrator.worker_allocation_feedback import (
    WorkerAllocationFeedbackCollector, allocate_worker_with_feedback,
    AllocationFeedbackMetrics, CompletionFeedbackMetrics
)
from claude_orchestrator.dynamic_worker_allocation import (
    DynamicWorkerAllocator, TaskRequirements, TaskComplexity, WorkerCapability
)
from claude_orchestrator.feedback_collector import FeedbackCollector, CollectionPoint
from claude_orchestrator.feedback_models import FeedbackType, RatingScale
from claude_orchestrator.feedback_storage import FeedbackStorage


class TestWorkerAllocationFeedbackCollector:
    """Tests for WorkerAllocationFeedbackCollector class"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.storage = FeedbackStorage(self.temp_db.name)
        self.feedback_collector = FeedbackCollector(self.storage)
        self.allocator = DynamicWorkerAllocator()
        
        # Register some test workers
        self.allocator.register_worker(
            worker_id="worker-1",
            model_name="claude-3-5-sonnet-20241022",
            capabilities={WorkerCapability.CODE, WorkerCapability.DEBUGGING},
            max_complexity=TaskComplexity.HIGH
        )
        
        self.allocator.register_worker(
            worker_id="worker-2",
            model_name="claude-3-opus-20240229",
            capabilities={WorkerCapability.RESEARCH, WorkerCapability.DESIGN},
            max_complexity=TaskComplexity.CRITICAL
        )
        
        self.alloc_feedback = WorkerAllocationFeedbackCollector(
            allocator=self.allocator,
            feedback_collector=self.feedback_collector,
            enable_async_collection=False  # Use sync for testing
        )
    
    def teardown_method(self):
        """Clean up after test"""
        self.alloc_feedback.close()
        os.unlink(self.temp_db.name)
    
    def test_worker_allocation_feedback_collector_initialization(self):
        """Test feedback collector initialization"""
        assert self.alloc_feedback.allocator is not None
        assert self.alloc_feedback.feedback_collector is not None
        assert self.alloc_feedback.enable_async_collection is False
        assert self.alloc_feedback._feedback_enabled is True
    
    def test_allocate_worker_with_feedback_success(self):
        """Test successful worker allocation with feedback collection"""
        task_requirements = TaskRequirements(
            complexity=TaskComplexity.MEDIUM,
            estimated_duration=60,
            required_capabilities={WorkerCapability.CODE}
        )
        
        worker_id = self.alloc_feedback.allocate_worker_with_feedback(
            task_id="test-task-allocation",
            task_title="Implement feature X",
            task_description="Implement a new feature in the codebase",
            task_requirements=task_requirements,
            user_id="test-user"
        )
        
        # Verify allocation worked
        assert worker_id is not None
        assert worker_id in ["worker-1", "worker-2"]
        
        # Verify feedback was collected
        feedback_list = self.storage.get_feedback_by_task("test-task-allocation")
        assert len(feedback_list) > 0
        
        # Check allocation feedback
        allocation_feedback = next(
            (f for f in feedback_list if f.feedback_type == FeedbackType.WORKER_PERFORMANCE), 
            None
        )
        assert allocation_feedback is not None
        assert allocation_feedback.task_id == "test-task-allocation"
        assert "Allocated worker" in allocation_feedback.content
        assert allocation_feedback.rating is not None
        assert allocation_feedback.user_id == "test-user"
        assert allocation_feedback.metadata.context["auto_generated"] is True
        assert allocation_feedback.metadata.context["worker_id"] == worker_id
    
    def test_allocate_worker_with_feedback_failure(self):
        """Test worker allocation failure with feedback collection"""
        # Create impossible task requirements
        task_requirements = TaskRequirements(
            complexity=TaskComplexity.CRITICAL,
            estimated_duration=60,
            required_capabilities={WorkerCapability.TESTING}  # No worker has this capability
        )
        
        worker_id = self.alloc_feedback.allocate_worker_with_feedback(
            task_id="impossible-task",
            task_title="Impossible task",
            task_description="Task that no worker can handle",
            task_requirements=task_requirements,
            user_id="test-user"
        )
        
        # Verify allocation failed
        assert worker_id is None
        
        # Verify failure feedback was collected
        feedback_list = self.storage.get_feedback_by_task("impossible-task")
        assert len(feedback_list) > 0
        
        failure_feedback = feedback_list[0]
        assert failure_feedback.feedback_type == FeedbackType.ERROR_REPORT
        assert "allocation failed" in failure_feedback.content.lower()
        assert failure_feedback.rating == RatingScale.POOR
    
    def test_release_worker_with_feedback_success(self):
        """Test successful worker release with feedback collection"""
        # First allocate a worker
        worker_id = self.alloc_feedback.allocate_worker_with_feedback(
            task_id="test-release-task",
            task_title="Test release",
            task_description="Task for testing worker release",
            user_id="test-user"
        )
        
        assert worker_id is not None
        
        # Now release the worker with feedback
        release_success = self.alloc_feedback.release_worker_with_feedback(
            worker_id=worker_id,
            task_id="test-release-task",
            success=True,
            actual_duration=45.0,
            error_count=1,
            quality_indicators={"code_quality": 0.9, "test_coverage": 0.85},
            user_id="test-user"
        )
        
        assert release_success is True
        
        # Verify feedback was collected
        feedback_list = self.storage.get_feedback_by_task("test-release-task")
        
        # Should have allocation feedback + completion feedback + performance feedback
        assert len(feedback_list) >= 3
        
        # Check completion feedback
        completion_feedback = next(
            (f for f in feedback_list if f.feedback_type == FeedbackType.TASK_COMPLETION),
            None
        )
        assert completion_feedback is not None
        assert "completed successfully" in completion_feedback.content
        assert completion_feedback.metadata.context["success"] is True
        assert completion_feedback.metadata.context["error_count"] == 1
        
        # Check worker performance feedback
        performance_feedback = next(
            (f for f in feedback_list if f.feedback_type == FeedbackType.WORKER_PERFORMANCE and "performance" in f.content),
            None
        )
        assert performance_feedback is not None
        assert worker_id in performance_feedback.content
    
    def test_release_worker_with_feedback_failure(self):
        """Test worker release with task failure feedback"""
        # Allocate and then release with failure
        worker_id = self.alloc_feedback.allocate_worker_with_feedback(
            task_id="failed-task",
            task_title="Failed task",
            task_description="Task that will fail",
            user_id="test-user"
        )
        
        assert worker_id is not None
        
        release_success = self.alloc_feedback.release_worker_with_feedback(
            worker_id=worker_id,
            task_id="failed-task",
            success=False,
            actual_duration=30.0,
            error_count=5,
            user_id="test-user"
        )
        
        assert release_success is True
        
        # Check failure feedback
        feedback_list = self.storage.get_feedback_by_task("failed-task")
        completion_feedback = next(
            (f for f in feedback_list if f.feedback_type == FeedbackType.TASK_COMPLETION),
            None
        )
        
        assert completion_feedback is not None
        assert "with failures" in completion_feedback.content
        assert completion_feedback.metadata.context["success"] is False
        assert completion_feedback.metadata.context["error_count"] == 5
    
    def test_collect_manual_allocation_feedback(self):
        """Test collecting manual feedback about allocation"""
        feedback_entry = self.alloc_feedback.collect_manual_allocation_feedback(
            task_id="manual-feedback-task",
            content="The worker allocation was excellent, perfect match for the task requirements",
            rating=5,
            feedback_type="allocation",
            user_id="manual-user"
        )
        
        assert feedback_entry is not None
        assert feedback_entry.task_id == "manual-feedback-task"
        assert feedback_entry.content == "The worker allocation was excellent, perfect match for the task requirements"
        assert feedback_entry.rating == RatingScale.EXCELLENT
        assert feedback_entry.user_id == "manual-user"
        
        # Verify it was stored
        stored_feedback = self.storage.get_feedback(feedback_entry.id)
        assert stored_feedback is not None
    
    def test_collect_manual_performance_feedback(self):
        """Test collecting manual worker performance feedback"""
        feedback_entry = self.alloc_feedback.collect_manual_allocation_feedback(
            task_id="performance-task",
            content="Worker performance was good but could be faster",
            rating=3,
            feedback_type="performance",
            user_id="reviewer"
        )
        
        assert feedback_entry is not None
        assert feedback_entry.rating == RatingScale.GOOD
        assert "performance was good" in feedback_entry.content
    
    def test_get_worker_feedback_summary(self):
        """Test getting feedback summary for a specific worker"""
        # First create some feedback for a worker
        worker_id = self.alloc_feedback.allocate_worker_with_feedback(
            task_id="summary-test-1",
            task_title="Summary test 1",
            task_description="First task for summary testing",
            user_id="test-user"
        )
        
        self.alloc_feedback.release_worker_with_feedback(
            worker_id=worker_id,
            task_id="summary-test-1",
            success=True,
            actual_duration=30.0,
            user_id="test-user"
        )
        
        # Add manual feedback
        self.alloc_feedback.collect_manual_allocation_feedback(
            task_id="summary-test-1",
            content="Great performance on this task",
            rating=5,
            feedback_type="performance",
            user_id="reviewer"
        )
        
        # Get summary
        summary = self.alloc_feedback.get_worker_feedback_summary(worker_id)
        
        assert summary["worker_id"] == worker_id
        assert summary["feedback_count"] > 0
        assert "average_rating" in summary
        assert summary["average_rating"] is not None
        assert "feedback_by_type" in summary
        assert "recent_feedback" in summary
        assert len(summary["recent_feedback"]) > 0
    
    def test_feedback_callback_registration(self):
        """Test registering and triggering feedback callbacks"""
        callback_calls = []
        
        def test_callback(task_id: str, feedback_entry):
            callback_calls.append((task_id, feedback_entry.id))
        
        self.alloc_feedback.register_feedback_callback(test_callback)
        
        # Allocate a worker to trigger callback
        worker_id = self.alloc_feedback.allocate_worker_with_feedback(
            task_id="callback-test",
            task_title="Callback test",
            task_description="Test callback functionality",
            user_id="test-user"
        )
        
        # Verify callback was called
        assert len(callback_calls) >= 1
        assert callback_calls[0][0] == "callback-test"
    
    def test_enable_disable_feedback_collection(self):
        """Test enabling and disabling feedback collection"""
        # Disable feedback
        self.alloc_feedback.enable_feedback_collection(False)
        
        # Allocate a worker
        worker_id = self.alloc_feedback.allocate_worker_with_feedback(
            task_id="disabled-feedback",
            task_title="Disabled feedback test",
            task_description="This should not generate feedback",
            user_id="test-user"
        )
        
        # Verify no feedback was collected
        feedback_list = self.storage.get_feedback_by_task("disabled-feedback")
        assert len(feedback_list) == 0
        
        # Re-enable feedback
        self.alloc_feedback.enable_feedback_collection(True)
        
        # Allocate another worker
        worker_id2 = self.alloc_feedback.allocate_worker_with_feedback(
            task_id="enabled-feedback",
            task_title="Enabled feedback test",
            task_description="This should generate feedback",
            user_id="test-user"
        )
        
        # Verify feedback was collected
        feedback_list = self.storage.get_feedback_by_task("enabled-feedback")
        assert len(feedback_list) > 0
    
    def test_allocation_rating_assessment(self):
        """Test that allocation ratings are assessed correctly"""
        # Test with good allocation scenario
        task_requirements = TaskRequirements(
            complexity=TaskComplexity.MEDIUM,
            estimated_duration=60,
            required_capabilities={WorkerCapability.CODE}
        )
        
        worker_id = self.alloc_feedback.allocate_worker_with_feedback(
            task_id="rating-test",
            task_title="Rating test",
            task_description="Test rating assessment",
            task_requirements=task_requirements,
            user_id="test-user"
        )
        
        assert worker_id is not None
        
        feedback_list = self.storage.get_feedback_by_task("rating-test")
        allocation_feedback = next(
            (f for f in feedback_list if f.feedback_type == FeedbackType.WORKER_PERFORMANCE),
            None
        )
        
        assert allocation_feedback is not None
        # Should get a decent rating for successful allocation
        assert allocation_feedback.rating.value >= 3
    
    def test_async_feedback_collection(self):
        """Test asynchronous feedback collection"""
        # Create collector with async enabled
        async_collector = WorkerAllocationFeedbackCollector(
            allocator=self.allocator,
            feedback_collector=self.feedback_collector,
            enable_async_collection=True
        )
        
        try:
            # Allocate a worker
            worker_id = async_collector.allocate_worker_with_feedback(
                task_id="async-test",
                task_title="Async feedback test",
                task_description="Test asynchronous feedback collection",
                user_id="test-user"
            )
            
            assert worker_id is not None
            
            # Wait a moment for async collection to complete
            time.sleep(0.5)
            
            # Verify feedback was collected
            feedback_list = self.storage.get_feedback_by_task("async-test")
            assert len(feedback_list) > 0
            
        finally:
            async_collector.close()
    
    def test_context_manager(self):
        """Test using WorkerAllocationFeedbackCollector as context manager"""
        with WorkerAllocationFeedbackCollector(
            allocator=self.allocator,
            feedback_collector=self.feedback_collector
        ) as collector:
            worker_id = collector.allocate_worker_with_feedback(
                task_id="context-test",
                task_title="Context manager test",
                task_description="Test context manager functionality",
                user_id="test-user"
            )
            
            assert worker_id is not None
    
    def test_allocation_with_error(self):
        """Test allocation error handling and feedback"""
        # Mock allocator to raise an error
        with patch.object(self.allocator, 'allocate_worker') as mock_allocate:
            mock_allocate.side_effect = ValueError("Allocation system error")
            
            try:
                self.alloc_feedback.allocate_worker_with_feedback(
                    task_id="error-allocation",
                    task_title="Error allocation",
                    task_description="This will cause an error",
                    user_id="test-user"
                )
                assert False, "Should have raised ValueError"
            except ValueError:
                pass  # Expected
            
            # Verify error feedback was collected
            feedback_list = self.storage.get_feedback_by_task("error-allocation")
            assert len(feedback_list) > 0
            
            error_feedback = feedback_list[0]
            assert error_feedback.feedback_type == FeedbackType.ERROR_REPORT
            assert "Allocation system error" in error_feedback.content


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
    
    def test_allocate_worker_with_feedback_convenience(self):
        """Test convenience function for worker allocation with feedback"""
        worker_id = allocate_worker_with_feedback(
            task_id="convenience-test",
            task_title="Test convenience function",
            task_description="Test the convenience function for allocation with feedback",
            user_id="test-user",
            storage=self.storage
        )
        
        # May succeed or fail depending on whether workers are registered
        # But should not raise an exception
        assert worker_id is None or isinstance(worker_id, str)
        
        # Check if feedback was collected (if allocation occurred)
        feedback_list = self.storage.get_feedback_by_task("convenience-test")
        # May have feedback if allocation succeeded, no feedback if it failed
    
    def test_convenience_function_with_default_storage(self):
        """Test convenience function with default storage"""
        worker_id = allocate_worker_with_feedback(
            task_id="default-storage-test",
            task_title="Test default storage",
            task_description="Test convenience function with default storage"
        )
        
        # Should not raise an exception
        assert worker_id is None or isinstance(worker_id, str)
        
        # Clean up default database if created
        if os.path.exists("feedback.db"):
            os.unlink("feedback.db")


class TestFeedbackMetrics:
    """Tests for feedback metrics data classes"""
    
    def test_allocation_feedback_metrics(self):
        """Test AllocationFeedbackMetrics data class"""
        metrics = AllocationFeedbackMetrics(
            allocation_time=1.5,
            suitability_score=0.85,
            task_complexity=TaskComplexity.MEDIUM,
            worker_availability=0.3,
            alternative_workers_count=2,
            worker_specialization_match=0.9
        )
        
        assert metrics.allocation_time == 1.5
        assert metrics.suitability_score == 0.85
        assert metrics.task_complexity == TaskComplexity.MEDIUM
        assert metrics.worker_availability == 0.3
        assert metrics.alternative_workers_count == 2
        assert metrics.worker_specialization_match == 0.9
    
    def test_completion_feedback_metrics(self):
        """Test CompletionFeedbackMetrics data class"""
        metrics = CompletionFeedbackMetrics(
            execution_time=45.0,
            estimated_duration=60.0,
            success=True,
            worker_efficiency=1.33,
            error_count=1,
            quality_indicators={"code_quality": 0.9}
        )
        
        assert metrics.execution_time == 45.0
        assert metrics.estimated_duration == 60.0
        assert metrics.success is True
        assert metrics.worker_efficiency == 1.33
        assert metrics.error_count == 1
        assert metrics.quality_indicators["code_quality"] == 0.9