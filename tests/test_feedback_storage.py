"""
Unit tests for feedback storage layer

Tests SQLite-based storage backend for feedback data
"""

import tempfile
import os
from pathlib import Path
from datetime import datetime
import sqlite3

from claude_orchestrator.feedback_storage import (
    FeedbackStorage, FeedbackStorageError, FeedbackNotFoundError,
    create_feedback_storage
)
from claude_orchestrator.feedback_models import (
    FeedbackEntry, FeedbackType, RatingScale, FeedbackMetadata,
    create_feedback_entry
)


class TestFeedbackStorage:
    """Tests for FeedbackStorage class"""
    
    def setup_method(self):
        """Set up test environment before each test"""
        # Create temporary database for each test
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.storage = FeedbackStorage(self.temp_db.name)
    
    def teardown_method(self):
        """Clean up after each test"""
        self.storage.close()
        os.unlink(self.temp_db.name)
    
    def test_database_initialization(self):
        """Test that database and schema are created properly"""
        # Check that database file exists
        assert Path(self.temp_db.name).exists()
        
        # Check that tables are created
        conn = sqlite3.connect(self.temp_db.name)
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='feedback'
        """)
        assert cursor.fetchone() is not None
        conn.close()
    
    def test_create_feedback_entry(self):
        """Test creating a feedback entry"""
        entry = create_feedback_entry(
            task_id="test-task-1",
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Task completed successfully",
            rating=RatingScale.EXCELLENT,
            user_id="test-user"
        )
        
        feedback_id = self.storage.create_feedback(entry)
        assert feedback_id == entry.id
        
        # Verify it was stored correctly
        retrieved = self.storage.get_feedback(feedback_id)
        assert retrieved is not None
        assert retrieved.id == entry.id
        assert retrieved.task_id == entry.task_id
        assert retrieved.content == entry.content
        assert retrieved.rating == entry.rating
        assert retrieved.user_id == entry.user_id
    
    def test_create_feedback_without_rating(self):
        """Test creating feedback entry without rating"""
        entry = create_feedback_entry(
            task_id="test-task-2",
            feedback_type=FeedbackType.IMPROVEMENT_SUGGESTION,
            content="Could improve error handling",
            rating=None
        )
        
        feedback_id = self.storage.create_feedback(entry)
        retrieved = self.storage.get_feedback(feedback_id)
        
        assert retrieved is not None
        assert retrieved.rating is None
        assert retrieved.content == "Could improve error handling"
    
    def test_create_feedback_with_metadata(self):
        """Test creating feedback entry with metadata"""
        metadata = FeedbackMetadata(
            source="test-runner",
            version="1.0.0",
            context={"test_id": "abc123"},
            tags=["automated", "performance"]
        )
        
        entry = create_feedback_entry(
            task_id="test-task-3",
            feedback_type=FeedbackType.WORKER_PERFORMANCE,
            content="Worker performed well",
            rating=RatingScale.GOOD
        )
        entry.metadata = metadata
        
        feedback_id = self.storage.create_feedback(entry)
        retrieved = self.storage.get_feedback(feedback_id)
        
        assert retrieved is not None
        assert retrieved.metadata is not None
        assert retrieved.metadata.source == "test-runner"
        assert retrieved.metadata.version == "1.0.0"
        assert retrieved.metadata.context["test_id"] == "abc123"
        assert "automated" in retrieved.metadata.tags
    
    def test_get_feedback_not_found(self):
        """Test getting non-existent feedback"""
        result = self.storage.get_feedback("non-existent-id")
        assert result is None
    
    def test_get_feedback_by_task(self):
        """Test getting all feedback for a specific task"""
        task_id = "test-task-multi"
        
        # Create multiple feedback entries for the same task
        entries = []
        for i in range(3):
            entry = create_feedback_entry(
                task_id=task_id,
                feedback_type=FeedbackType.TASK_COMPLETION,
                content=f"Feedback {i+1}",
                rating=RatingScale(i+2)  # 2, 3, 4
            )
            entries.append(entry)
            self.storage.create_feedback(entry)
        
        # Get all feedback for the task
        feedback_list = self.storage.get_feedback_by_task(task_id)
        assert len(feedback_list) == 3
        
        # Check that they're ordered by creation time (DESC)
        for i, feedback in enumerate(feedback_list):
            assert feedback.content == f"Feedback {3-i}"  # Reversed order
    
    def test_update_feedback(self):
        """Test updating feedback entry"""
        entry = create_feedback_entry(
            task_id="test-task-update",
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Original content",
            rating=RatingScale.GOOD
        )
        
        self.storage.create_feedback(entry)
        
        # Update the feedback
        updates = {
            "content": "Updated content",
            "rating": RatingScale.EXCELLENT
        }
        
        success = self.storage.update_feedback(entry.id, updates)
        assert success is True
        
        # Verify updates
        updated = self.storage.get_feedback(entry.id)
        assert updated.content == "Updated content"
        assert updated.rating == RatingScale.EXCELLENT
    
    def test_update_feedback_not_found(self):
        """Test updating non-existent feedback"""
        success = self.storage.update_feedback("non-existent", {"content": "test"})
        assert success is False
    
    def test_update_feedback_invalid_fields(self):
        """Test updating with invalid fields"""
        entry = create_feedback_entry(
            task_id="test-task",
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Test content"
        )
        self.storage.create_feedback(entry)
        
        # Try to update with invalid field
        success = self.storage.update_feedback(entry.id, {"invalid_field": "value"})
        assert success is False
    
    def test_delete_feedback(self):
        """Test deleting feedback entry"""
        entry = create_feedback_entry(
            task_id="test-task-delete",
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="To be deleted"
        )
        
        self.storage.create_feedback(entry)
        
        # Verify it exists
        assert self.storage.get_feedback(entry.id) is not None
        
        # Delete it
        success = self.storage.delete_feedback(entry.id)
        assert success is True
        
        # Verify it's gone
        assert self.storage.get_feedback(entry.id) is None
    
    def test_delete_feedback_not_found(self):
        """Test deleting non-existent feedback"""
        success = self.storage.delete_feedback("non-existent-id")
        assert success is False
    
    def test_list_feedback_no_filters(self):
        """Test listing all feedback entries"""
        # Create several feedback entries
        for i in range(5):
            entry = create_feedback_entry(
                task_id=f"task-{i}",
                feedback_type=FeedbackType.TASK_COMPLETION,
                content=f"Feedback {i}"
            )
            self.storage.create_feedback(entry)
        
        feedback_list = self.storage.list_feedback()
        assert len(feedback_list) == 5
    
    def test_list_feedback_with_task_filter(self):
        """Test listing feedback filtered by task ID"""
        target_task = "target-task"
        
        # Create feedback for different tasks
        for i in range(3):
            # Target task feedback
            entry = create_feedback_entry(
                task_id=target_task,
                feedback_type=FeedbackType.TASK_COMPLETION,
                content=f"Target feedback {i}"
            )
            self.storage.create_feedback(entry)
            
            # Other task feedback
            entry = create_feedback_entry(
                task_id=f"other-task-{i}",
                feedback_type=FeedbackType.TASK_COMPLETION,
                content=f"Other feedback {i}"
            )
            self.storage.create_feedback(entry)
        
        # Filter by target task
        filtered = self.storage.list_feedback(task_id=target_task)
        assert len(filtered) == 3
        for feedback in filtered:
            assert feedback.task_id == target_task
    
    def test_list_feedback_with_type_filter(self):
        """Test listing feedback filtered by feedback type"""
        task_id = "filter-test-task"
        
        # Create feedback of different types
        types_and_counts = [
            (FeedbackType.TASK_COMPLETION, 2),
            (FeedbackType.WORKER_PERFORMANCE, 1),
            (FeedbackType.ERROR_REPORT, 3)
        ]
        
        for feedback_type, count in types_and_counts:
            for i in range(count):
                entry = create_feedback_entry(
                    task_id=task_id,
                    feedback_type=feedback_type,
                    content=f"{feedback_type.value} feedback {i}"
                )
                self.storage.create_feedback(entry)
        
        # Filter by error reports
        error_feedback = self.storage.list_feedback(
            feedback_type=FeedbackType.ERROR_REPORT
        )
        assert len(error_feedback) == 3
        for feedback in error_feedback:
            assert feedback.feedback_type == FeedbackType.ERROR_REPORT
    
    def test_list_feedback_with_pagination(self):
        """Test listing feedback with limit and offset"""
        # Create 10 feedback entries
        for i in range(10):
            entry = create_feedback_entry(
                task_id="pagination-test",
                feedback_type=FeedbackType.TASK_COMPLETION,
                content=f"Feedback {i}"
            )
            self.storage.create_feedback(entry)
        
        # Test pagination
        page1 = self.storage.list_feedback(limit=3, offset=0)
        page2 = self.storage.list_feedback(limit=3, offset=3)
        
        assert len(page1) == 3
        assert len(page2) == 3
        
        # Ensure no overlap
        page1_ids = {f.id for f in page1}
        page2_ids = {f.id for f in page2}
        assert len(page1_ids & page2_ids) == 0
    
    def test_get_feedback_summary(self):
        """Test getting feedback summary statistics"""
        task_id = "summary-test-task"
        
        # Create feedback with different ratings
        ratings = [
            RatingScale.POOR,
            RatingScale.GOOD,
            RatingScale.EXCELLENT,
            RatingScale.GOOD,
            None  # No rating
        ]
        
        for i, rating in enumerate(ratings):
            entry = create_feedback_entry(
                task_id=task_id,
                feedback_type=FeedbackType.TASK_COMPLETION,
                content=f"Summary feedback {i}",
                rating=rating
            )
            self.storage.create_feedback(entry)
        
        summary = self.storage.get_feedback_summary(task_id)
        
        assert summary.task_id == task_id
        assert summary.total_feedback_count == 5
        # Average of 1, 3, 5, 3 = 3.0
        assert summary.average_rating == 3.0
        assert summary.rating_distribution[1] == 1  # One POOR rating
        assert summary.rating_distribution[3] == 2  # Two GOOD ratings
        assert summary.rating_distribution[5] == 1  # One EXCELLENT rating
    
    def test_context_manager(self):
        """Test using FeedbackStorage as context manager"""
        with FeedbackStorage(self.temp_db.name) as storage:
            entry = create_feedback_entry(
                task_id="context-test",
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="Context manager test"
            )
            storage.create_feedback(entry)
            
            # Verify it was created
            retrieved = storage.get_feedback(entry.id)
            assert retrieved is not None
    
    def test_transaction_rollback_on_error(self):
        """Test that transactions are rolled back on errors"""
        # This test simulates a constraint violation
        entry = create_feedback_entry(
            task_id="rollback-test",
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Test"
        )
        
        # Create the entry first
        self.storage.create_feedback(entry)
        
        # Try to create duplicate with same ID (should fail)
        try:
            self.storage.create_feedback(entry)
            assert False, "Should have raised an exception"
        except FeedbackStorageError:
            pass  # Expected
        
        # Verify database is still consistent
        count = len(self.storage.list_feedback())
        assert count == 1  # Only one entry should exist
    
    def test_rating_constraint_validation(self):
        """Test that rating constraints are enforced at database level"""
        # Create entry with invalid rating directly in database
        conn = sqlite3.connect(self.temp_db.name)
        try:
            conn.execute("""
                INSERT INTO feedback (
                    id, task_id, feedback_type, content, rating, 
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                "test-id",
                "test-task",
                "task_completion",
                "test content",
                10,  # Invalid rating (should be 1-5)
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            conn.commit()
            assert False, "Should have failed due to constraint"
        except sqlite3.IntegrityError:
            pass  # Expected
        finally:
            conn.close()


class TestFactoryFunction:
    """Tests for factory function"""
    
    def test_create_feedback_storage_default(self):
        """Test creating storage with default parameters"""
        storage = create_feedback_storage()
        assert isinstance(storage, FeedbackStorage)
        storage.close()
        
        # Clean up default database
        if Path("feedback.db").exists():
            Path("feedback.db").unlink()
    
    def test_create_feedback_storage_custom_path(self):
        """Test creating storage with custom database path"""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            storage = create_feedback_storage(temp_db.name)
            assert isinstance(storage, FeedbackStorage)
            assert Path(temp_db.name).exists()
            storage.close()
        finally:
            os.unlink(temp_db.name)


class TestConcurrentAccess:
    """Tests for concurrent access handling"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
    
    def teardown_method(self):
        """Clean up after test"""
        os.unlink(self.temp_db.name)
    
    def test_multiple_storage_instances(self):
        """Test multiple storage instances accessing same database"""
        storage1 = FeedbackStorage(self.temp_db.name)
        storage2 = FeedbackStorage(self.temp_db.name)
        
        try:
            # Create entry with first instance
            entry1 = create_feedback_entry(
                task_id="concurrent-test-1",
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="From storage 1"
            )
            storage1.create_feedback(entry1)
            
            # Read with second instance
            retrieved = storage2.get_feedback(entry1.id)
            assert retrieved is not None
            assert retrieved.content == "From storage 1"
            
            # Create entry with second instance
            entry2 = create_feedback_entry(
                task_id="concurrent-test-2",
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="From storage 2"
            )
            storage2.create_feedback(entry2)
            
            # Read with first instance
            retrieved = storage1.get_feedback(entry2.id)
            assert retrieved is not None
            assert retrieved.content == "From storage 2"
            
        finally:
            storage1.close()
            storage2.close()