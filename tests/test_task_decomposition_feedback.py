"""
Unit tests for task decomposition feedback integration

Tests the integration of feedback collection with task decomposition workflow
"""

import tempfile
import os
import time
from unittest.mock import Mock, patch

from claude_orchestrator.task_decomposition_feedback import (
    DecompositionFeedbackCollector, decompose_with_feedback
)
from claude_orchestrator.task_decomposer import (
    TaskDecomposer, DecompositionStrategy, TaskComplexityLevel
)
from claude_orchestrator.feedback_collector import FeedbackCollector, CollectionPoint
from claude_orchestrator.feedback_models import FeedbackType, RatingScale
from claude_orchestrator.feedback_storage import FeedbackStorage


class TestDecompositionFeedbackCollector:
    """Tests for DecompositionFeedbackCollector class"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.storage = FeedbackStorage(self.temp_db.name)
        self.feedback_collector = FeedbackCollector(self.storage)
        self.decomposer = TaskDecomposer()
        self.decomp_feedback = DecompositionFeedbackCollector(
            decomposer=self.decomposer,
            feedback_collector=self.feedback_collector,
            enable_async_collection=False  # Use sync for testing
        )
    
    def teardown_method(self):
        """Clean up after test"""
        self.decomp_feedback.close()
        os.unlink(self.temp_db.name)
    
    def test_decomposition_feedback_collector_initialization(self):
        """Test feedback collector initialization"""
        assert self.decomp_feedback.decomposer is not None
        assert self.decomp_feedback.feedback_collector is not None
        assert self.decomp_feedback.enable_async_collection is False
        assert self.decomp_feedback._feedback_enabled is True
    
    def test_decomposition_feedback_collector_with_defaults(self):
        """Test creating feedback collector with default components"""
        collector = DecompositionFeedbackCollector()
        assert collector.decomposer is not None
        assert collector.feedback_collector is not None
        collector.close()
        
        # Clean up any default database
        if os.path.exists("feedback.db"):
            os.unlink("feedback.db")
    
    def test_decompose_task_with_feedback_success(self):
        """Test successful task decomposition with feedback collection"""
        plan = self.decomp_feedback.decompose_task_with_feedback(
            task_id="test-task-123",
            title="Build a web application",
            description="Create a full-stack web application with user authentication",
            estimated_duration=480,  # 8 hours - should trigger decomposition
            user_id="test-user"
        )
        
        # Verify decomposition worked
        assert plan is not None
        assert plan.original_task_id == "test-task-123"
        assert len(plan.subtasks) > 0
        
        # Verify feedback was collected
        feedback_list = self.storage.get_feedback_by_task("test-task-123")
        assert len(feedback_list) > 0
        
        # Check the feedback content
        feedback = feedback_list[0]
        assert feedback.task_id == "test-task-123"
        assert feedback.feedback_type == FeedbackType.TASK_COMPLETION
        assert "decomposed successfully" in feedback.content
        assert feedback.rating is not None
        assert feedback.user_id == "test-user"
        assert feedback.metadata.context["auto_generated"] is True
    
    def test_decompose_simple_task_with_feedback(self):
        """Test decomposing a simple task that doesn't need decomposition"""
        plan = self.decomp_feedback.decompose_task_with_feedback(
            task_id="simple-task",
            title="Fix a small bug",
            description="Fix a simple typo in the code",
            estimated_duration=30,  # 30 minutes - should not decompose
            user_id="test-user"
        )
        
        # Verify simple plan was created
        assert plan is not None
        assert len(plan.subtasks) == 1  # Simple plan has just one task
        
        # Verify feedback was still collected
        feedback_list = self.storage.get_feedback_by_task("simple-task")
        assert len(feedback_list) > 0
    
    def test_decompose_task_with_feedback_error(self):
        """Test decomposition with error and error feedback collection"""
        # Mock the decomposer to raise an error
        with patch.object(self.decomposer, 'decompose_task') as mock_decompose:
            mock_decompose.side_effect = ValueError("Decomposition failed")
            
            try:
                self.decomp_feedback.decompose_task_with_feedback(
                    task_id="error-task",
                    title="This will fail",
                    description="Task that causes decomposition error",
                    user_id="test-user"
                )
                assert False, "Should have raised ValueError"
            except ValueError:
                pass  # Expected
            
            # Verify error feedback was collected
            feedback_list = self.storage.get_feedback_by_task("error-task")
            assert len(feedback_list) > 0
            
            error_feedback = feedback_list[0]
            assert error_feedback.feedback_type == FeedbackType.ERROR_REPORT
            assert "Decomposition failed" in error_feedback.content
    
    def test_feedback_rating_assessment(self):
        """Test that feedback ratings are assessed correctly"""
        # Test with a well-structured task that should get good rating
        plan = self.decomp_feedback.decompose_task_with_feedback(
            task_id="good-task",
            title="Implement user authentication system",
            description="Create a complete user authentication system with registration, login, and password reset",
            estimated_duration=360,
            user_id="test-user"
        )
        
        feedback_list = self.storage.get_feedback_by_task("good-task")
        assert len(feedback_list) > 0
        
        feedback = feedback_list[0]
        # Should get a decent rating for a well-structured decomposition
        assert feedback.rating.value >= 3  # At least Good
    
    def test_collect_manual_decomposition_feedback(self):
        """Test collecting manual feedback about decomposition"""
        feedback_entry = self.decomp_feedback.collect_manual_decomposition_feedback(
            task_id="manual-feedback-task",
            content="The decomposition was excellent, subtasks were well-defined",
            rating=5,
            user_id="manual-user"
        )
        
        assert feedback_entry is not None
        assert feedback_entry.task_id == "manual-feedback-task"
        assert feedback_entry.content == "The decomposition was excellent, subtasks were well-defined"
        assert feedback_entry.rating == RatingScale.EXCELLENT
        assert feedback_entry.user_id == "manual-user"
        
        # Verify it was stored
        stored_feedback = self.storage.get_feedback(feedback_entry.id)
        assert stored_feedback is not None
    
    def test_collect_manual_feedback_without_rating(self):
        """Test collecting manual feedback without rating"""
        feedback_entry = self.decomp_feedback.collect_manual_decomposition_feedback(
            task_id="no-rating-task",
            content="The subtasks could be better organized",
            user_id="critic-user"
        )
        
        assert feedback_entry is not None
        assert feedback_entry.rating is None
        assert feedback_entry.content == "The subtasks could be better organized"
    
    def test_collect_manual_feedback_invalid_rating(self):
        """Test handling invalid rating in manual feedback"""
        feedback_entry = self.decomp_feedback.collect_manual_decomposition_feedback(
            task_id="invalid-rating-task",
            content="Good decomposition",
            rating=10,  # Invalid rating
            user_id="test-user"
        )
        
        # Should return None due to invalid rating
        assert feedback_entry is None
    
    def test_get_decomposition_feedback_summary(self):
        """Test getting feedback summary for decomposed task"""
        # First decompose a task to generate feedback
        self.decomp_feedback.decompose_task_with_feedback(
            task_id="summary-task",
            title="Complex project",
            description="A complex project that needs decomposition",
            estimated_duration=600,
            user_id="test-user"
        )
        
        # Add some manual feedback
        self.decomp_feedback.collect_manual_decomposition_feedback(
            task_id="summary-task",
            content="Good decomposition strategy",
            rating=4,
            user_id="reviewer"
        )
        
        summary = self.decomp_feedback.get_decomposition_feedback_summary("summary-task")
        assert summary is not None
        assert summary.task_id == "summary-task"
        assert summary.total_feedback_count >= 2  # Auto + manual feedback
        assert summary.average_rating is not None
    
    def test_feedback_callback_registration(self):
        """Test registering and triggering feedback callbacks"""
        callback_calls = []
        
        def test_callback(task_id: str, feedback_entry):
            callback_calls.append((task_id, feedback_entry.id))
        
        self.decomp_feedback.register_feedback_callback(test_callback)
        
        # Decompose a task to trigger callback
        self.decomp_feedback.decompose_task_with_feedback(
            task_id="callback-test",
            title="Test callback functionality",
            description="Task to test callback system",
            estimated_duration=120,
            user_id="test-user"
        )
        
        # Verify callback was called
        assert len(callback_calls) >= 1
        assert callback_calls[0][0] == "callback-test"
    
    def test_enable_disable_feedback_collection(self):
        """Test enabling and disabling feedback collection"""
        # Disable feedback
        self.decomp_feedback.enable_feedback_collection(False)
        
        # Decompose a task
        plan = self.decomp_feedback.decompose_task_with_feedback(
            task_id="disabled-feedback",
            title="Task with disabled feedback",
            description="This should not generate feedback",
            estimated_duration=120
        )
        
        # Verify no feedback was collected
        feedback_list = self.storage.get_feedback_by_task("disabled-feedback")
        assert len(feedback_list) == 0
        
        # Re-enable feedback
        self.decomp_feedback.enable_feedback_collection(True)
        
        # Decompose another task
        plan = self.decomp_feedback.decompose_task_with_feedback(
            task_id="enabled-feedback",
            title="Task with enabled feedback",
            description="This should generate feedback",
            estimated_duration=120
        )
        
        # Verify feedback was collected
        feedback_list = self.storage.get_feedback_by_task("enabled-feedback")
        assert len(feedback_list) > 0
    
    def test_async_feedback_collection(self):
        """Test asynchronous feedback collection"""
        # Create collector with async enabled
        async_collector = DecompositionFeedbackCollector(
            decomposer=self.decomposer,
            feedback_collector=self.feedback_collector,
            enable_async_collection=True
        )
        
        try:
            # Decompose a task
            plan = async_collector.decompose_task_with_feedback(
                task_id="async-test",
                title="Async feedback test",
                description="Test asynchronous feedback collection",
                estimated_duration=120
            )
            
            # Wait a moment for async collection to complete
            time.sleep(0.5)
            
            # Verify feedback was collected
            feedback_list = self.storage.get_feedback_by_task("async-test")
            assert len(feedback_list) > 0
            
        finally:
            async_collector.close()
    
    def test_context_manager(self):
        """Test using DecompositionFeedbackCollector as context manager"""
        with DecompositionFeedbackCollector(
            decomposer=self.decomposer,
            feedback_collector=self.feedback_collector
        ) as collector:
            plan = collector.decompose_task_with_feedback(
                task_id="context-test",
                title="Context manager test",
                description="Test context manager functionality",
                estimated_duration=120
            )
            
            assert plan is not None
    
    def test_feedback_content_generation(self):
        """Test that feedback content contains useful information"""
        plan = self.decomp_feedback.decompose_task_with_feedback(
            task_id="content-test",
            title="API development project",
            description="Build a REST API with authentication and data persistence",
            estimated_duration=480,
            user_id="test-user"
        )
        
        feedback_list = self.storage.get_feedback_by_task("content-test")
        assert len(feedback_list) > 0
        
        feedback = feedback_list[0]
        content = feedback.content
        
        # Verify content contains key information
        assert "decomposed successfully" in content
        assert "Strategy:" in content
        assert "subtasks" in content
        assert "Confidence score:" in content
        
        # Verify context contains expected metrics
        context = feedback.metadata.context
        assert "strategy" in context
        assert "subtask_count" in context
        assert "confidence_score" in context
        assert "critical_path_duration" in context


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
    
    def test_decompose_with_feedback_convenience(self):
        """Test convenience function for decomposition with feedback"""
        plan = decompose_with_feedback(
            task_id="convenience-test",
            title="Test convenience function",
            description="Test the convenience function for decomposition with feedback",
            estimated_duration=240,
            strategy_hint=DecompositionStrategy.FEATURE_BASED,
            user_id="test-user",
            storage=self.storage
        )
        
        assert plan is not None
        assert plan.original_task_id == "convenience-test"
        assert plan.strategy == DecompositionStrategy.FEATURE_BASED
        
        # Verify feedback was collected
        feedback_list = self.storage.get_feedback_by_task("convenience-test")
        assert len(feedback_list) > 0
    
    def test_convenience_function_with_default_storage(self):
        """Test convenience function with default storage"""
        plan = decompose_with_feedback(
            task_id="default-storage-test",
            title="Test default storage",
            description="Test convenience function with default storage",
            estimated_duration=120
        )
        
        assert plan is not None
        
        # Clean up default database if created
        if os.path.exists("feedback.db"):
            os.unlink("feedback.db")