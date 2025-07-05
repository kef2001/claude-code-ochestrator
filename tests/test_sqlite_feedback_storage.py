"""Tests for SQLite feedback storage implementation"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from claude_orchestrator.feedback_model import (
    FeedbackModel, FeedbackType, FeedbackSeverity, FeedbackCategory,
    FeedbackContext, FeedbackMetrics
)
from claude_orchestrator.sqlite_feedback_storage import SQLiteFeedbackStorage


class TestSQLiteFeedbackStorage:
    """Test cases for SQLite feedback storage"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test database"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def storage(self, temp_dir):
        """Create SQLite storage instance"""
        db_path = Path(temp_dir) / "test_feedback.db"
        return SQLiteFeedbackStorage(str(db_path))
    
    @pytest.fixture
    def sample_feedback(self):
        """Create sample feedback"""
        context = FeedbackContext(
            task_id="test-task-123",
            worker_id="worker-1",
            session_id="session-abc",
            tags=["test", "sample"]
        )
        
        metrics = FeedbackMetrics(
            execution_time=5.5,
            tokens_used=100,
            memory_usage_mb=50.0
        )
        
        return FeedbackModel(
            feedback_id="feedback-456",
            feedback_type=FeedbackType.TASK_COMPLETED,
            severity=FeedbackSeverity.INFO,
            category=FeedbackCategory.PERFORMANCE,
            timestamp=datetime.now(),
            message="Task completed successfully",
            context=context,
            metrics=metrics
        )
    
    def test_save_and_load(self, storage, sample_feedback):
        """Test saving and loading feedback"""
        # Save feedback
        storage.save(sample_feedback)
        
        # Load feedback
        loaded = storage.load(sample_feedback.feedback_id)
        
        assert loaded is not None
        assert loaded.feedback_id == sample_feedback.feedback_id
        assert loaded.feedback_type == sample_feedback.feedback_type
        assert loaded.severity == sample_feedback.severity
        assert loaded.category == sample_feedback.category
        assert loaded.message == sample_feedback.message
        assert loaded.context.task_id == sample_feedback.context.task_id
        assert loaded.context.worker_id == sample_feedback.context.worker_id
        assert loaded.metrics.execution_time == sample_feedback.metrics.execution_time
    
    def test_query_by_task_id(self, storage, sample_feedback):
        """Test querying feedback by task ID"""
        # Save multiple feedbacks
        storage.save(sample_feedback)
        
        # Create another feedback for different task
        other_feedback = FeedbackModel(
            feedback_id="feedback-789",
            feedback_type=FeedbackType.ERROR,
            severity=FeedbackSeverity.ERROR,
            category=FeedbackCategory.EXECUTION,
            timestamp=datetime.now(),
            message="Task failed",
            context=FeedbackContext(
                task_id="other-task-456",
                worker_id="worker-2"
            )
        )
        storage.save(other_feedback)
        
        # Query by task ID
        results = storage.query(task_id="test-task-123")
        
        assert len(results) == 1
        assert results[0].feedback_id == sample_feedback.feedback_id
    
    def test_query_by_feedback_type(self, storage):
        """Test querying feedback by type"""
        # Save feedbacks of different types
        for i, fb_type in enumerate([FeedbackType.TASK_COMPLETED, FeedbackType.ERROR, FeedbackType.WARNING]):
            feedback = FeedbackModel(
                feedback_id=f"feedback-{i}",
                feedback_type=fb_type,
                severity=FeedbackSeverity.INFO,
                category=FeedbackCategory.GENERAL,
                timestamp=datetime.now(),
                message=f"Feedback {i}",
                context=FeedbackContext(task_id=f"task-{i}")
            )
            storage.save(feedback)
        
        # Query by type
        results = storage.query(feedback_type=FeedbackType.ERROR)
        
        assert len(results) == 1
        assert results[0].feedback_type == FeedbackType.ERROR
    
    def test_query_by_time_range(self, storage):
        """Test querying feedback by time range"""
        now = datetime.now()
        
        # Save feedbacks at different times
        old_feedback = FeedbackModel(
            feedback_id="old-feedback",
            feedback_type=FeedbackType.INFO,
            severity=FeedbackSeverity.INFO,
            category=FeedbackCategory.GENERAL,
            timestamp=now - timedelta(hours=2),
            message="Old feedback",
            context=FeedbackContext(task_id="old-task")
        )
        storage.save(old_feedback)
        
        recent_feedback = FeedbackModel(
            feedback_id="recent-feedback",
            feedback_type=FeedbackType.INFO,
            severity=FeedbackSeverity.INFO,
            category=FeedbackCategory.GENERAL,
            timestamp=now - timedelta(minutes=30),
            message="Recent feedback",
            context=FeedbackContext(task_id="recent-task")
        )
        storage.save(recent_feedback)
        
        # Query by time range
        results = storage.query(
            start_time=now - timedelta(hours=1),
            end_time=now
        )
        
        assert len(results) == 1
        assert results[0].feedback_id == "recent-feedback"
    
    def test_delete(self, storage, sample_feedback):
        """Test deleting feedback"""
        # Save feedback
        storage.save(sample_feedback)
        
        # Verify it exists
        assert storage.load(sample_feedback.feedback_id) is not None
        
        # Delete feedback
        deleted = storage.delete(sample_feedback.feedback_id)
        assert deleted is True
        
        # Verify it's gone
        assert storage.load(sample_feedback.feedback_id) is None
        
        # Try deleting non-existent feedback
        deleted = storage.delete("non-existent")
        assert deleted is False
    
    def test_clear(self, storage):
        """Test clearing all feedback"""
        # Save multiple feedbacks
        for i in range(5):
            feedback = FeedbackModel(
                feedback_id=f"feedback-{i}",
                feedback_type=FeedbackType.INFO,
                severity=FeedbackSeverity.INFO,
                category=FeedbackCategory.GENERAL,
                timestamp=datetime.now(),
                message=f"Feedback {i}",
                context=FeedbackContext(task_id=f"task-{i}")
            )
            storage.save(feedback)
        
        # Verify count
        assert storage.count() == 5
        
        # Clear all
        storage.clear()
        
        # Verify empty
        assert storage.count() == 0
    
    def test_count(self, storage):
        """Test counting feedback entries"""
        assert storage.count() == 0
        
        # Save feedbacks
        for i in range(3):
            feedback = FeedbackModel(
                feedback_id=f"feedback-{i}",
                feedback_type=FeedbackType.INFO,
                severity=FeedbackSeverity.INFO,
                category=FeedbackCategory.GENERAL,
                timestamp=datetime.now(),
                message=f"Feedback {i}",
                context=FeedbackContext(task_id=f"task-{i}")
            )
            storage.save(feedback)
        
        assert storage.count() == 3
    
    def test_query_with_limit(self, storage):
        """Test querying with limit"""
        # Save multiple feedbacks
        for i in range(10):
            feedback = FeedbackModel(
                feedback_id=f"feedback-{i}",
                feedback_type=FeedbackType.INFO,
                severity=FeedbackSeverity.INFO,
                category=FeedbackCategory.GENERAL,
                timestamp=datetime.now() - timedelta(minutes=i),
                message=f"Feedback {i}",
                context=FeedbackContext(task_id=f"task-{i}")
            )
            storage.save(feedback)
        
        # Query with limit
        results = storage.query(limit=5)
        
        assert len(results) == 5
        # Should be ordered by timestamp DESC
        assert results[0].feedback_id == "feedback-0"
        assert results[4].feedback_id == "feedback-4"
    
    def test_concurrent_access(self, storage):
        """Test concurrent access to the database"""
        import threading
        
        def save_feedback(thread_id):
            for i in range(10):
                feedback = FeedbackModel(
                    feedback_id=f"feedback-{thread_id}-{i}",
                    feedback_type=FeedbackType.INFO,
                    severity=FeedbackSeverity.INFO,
                    category=FeedbackCategory.GENERAL,
                    timestamp=datetime.now(),
                    message=f"Feedback from thread {thread_id}",
                    context=FeedbackContext(task_id=f"task-{thread_id}-{i}")
                )
                storage.save(feedback)
        
        # Create threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=save_feedback, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify all feedbacks were saved
        assert storage.count() == 50