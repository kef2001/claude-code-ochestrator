"""Unit tests for FeedbackStorage."""

import pytest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime, timedelta
import time

from claude_orchestrator.feedback_storage import (
    FeedbackStorage,
    JSONFeedbackStorage,
    FeedbackStorageInterface
)
from claude_orchestrator.feedback_model import (
    FeedbackModel,
    FeedbackType,
    FeedbackSeverity,
    FeedbackCategory,
    FeedbackContext,
    FeedbackMetrics,
    create_success_feedback,
    create_error_feedback
)


class TestJSONFeedbackStorage:
    """Test suite for JSONFeedbackStorage."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def storage(self, temp_dir):
        """Create JSONFeedbackStorage instance."""
        storage_path = Path(temp_dir) / "feedback_storage"
        return JSONFeedbackStorage(str(storage_path))
    
    @pytest.fixture
    def sample_feedback(self):
        """Create sample feedback."""
        return create_success_feedback(
            task_id="task123",
            message="Task completed successfully",
            worker_id="worker456",
            session_id="session789"
        )
    
    def test_initialization(self, storage):
        """Test storage initialization."""
        assert storage.storage_path.exists()
        assert storage._index_file.exists()
        
        # Check empty index
        with open(storage._index_file, 'r') as f:
            index = json.load(f)
        assert index == {}
    
    def test_save_and_load_feedback(self, storage, sample_feedback):
        """Test saving and loading feedback."""
        # Save feedback
        storage.save(sample_feedback)
        
        # Load feedback
        loaded = storage.load(sample_feedback.feedback_id)
        
        assert loaded is not None
        assert loaded.feedback_id == sample_feedback.feedback_id
        assert loaded.message == sample_feedback.message
        assert loaded.context.task_id == sample_feedback.context.task_id
    
    def test_save_invalid_feedback(self, storage):
        """Test saving invalid feedback fails."""
        invalid_feedback = FeedbackModel(
            feedback_type=FeedbackType.TASK_SUCCESS,
            severity=FeedbackSeverity.INFO,
            category=FeedbackCategory.EXECUTION,
            message="",  # Invalid: empty message
            context=FeedbackContext(task_id="task123")
        )
        
        # Should not save due to validation
        with pytest.raises(ValueError):
            storage.save(invalid_feedback)
    
    def test_load_nonexistent_feedback(self, storage):
        """Test loading non-existent feedback returns None."""
        result = storage.load("nonexistent-id")
        assert result is None
    
    def test_query_by_task_id(self, storage):
        """Test querying feedback by task ID."""
        # Save multiple feedbacks
        feedback1 = create_success_feedback(task_id="task1", message="Success 1")
        feedback2 = create_error_feedback(
            task_id="task1", 
            message="Error 1",
            error_details={"code": "E001"}
        )
        feedback3 = create_success_feedback(task_id="task2", message="Success 2")
        
        storage.save(feedback1)
        storage.save(feedback2)
        storage.save(feedback3)
        
        # Query by task_id
        results = storage.query(task_id="task1")
        
        assert len(results) == 2
        assert all(f.context.task_id == "task1" for f in results)
    
    def test_query_by_worker_id(self, storage):
        """Test querying feedback by worker ID."""
        # Save feedbacks with different workers
        feedback1 = create_success_feedback(
            task_id="task1",
            message="Success",
            worker_id="worker1"
        )
        feedback2 = create_success_feedback(
            task_id="task2",
            message="Success",
            worker_id="worker2"
        )
        
        storage.save(feedback1)
        storage.save(feedback2)
        
        # Query by worker_id
        results = storage.query(worker_id="worker1")
        
        assert len(results) == 1
        assert results[0].context.worker_id == "worker1"
    
    def test_query_by_feedback_type(self, storage):
        """Test querying by feedback type."""
        # Save different types
        success = create_success_feedback(task_id="task1", message="Success")
        error = create_error_feedback(
            task_id="task2",
            message="Error",
            error_details={}
        )
        
        storage.save(success)
        storage.save(error)
        
        # Query successes
        results = storage.query(feedback_type=FeedbackType.TASK_SUCCESS)
        assert len(results) == 1
        assert results[0].feedback_type == FeedbackType.TASK_SUCCESS
        
        # Query errors
        results = storage.query(feedback_type=FeedbackType.ERROR_REPORT)
        assert len(results) == 1
        assert results[0].feedback_type == FeedbackType.ERROR_REPORT
    
    def test_query_by_time_range(self, storage):
        """Test querying by time range."""
        now = datetime.now()
        
        # Create feedbacks with different timestamps
        old_feedback = create_success_feedback(task_id="old", message="Old")
        old_feedback.timestamp = now - timedelta(days=2)
        
        recent_feedback = create_success_feedback(task_id="recent", message="Recent")
        recent_feedback.timestamp = now - timedelta(hours=1)
        
        storage.save(old_feedback)
        storage.save(recent_feedback)
        
        # Query last 24 hours
        results = storage.query(
            start_time=now - timedelta(days=1),
            end_time=now
        )
        
        assert len(results) == 1
        assert results[0].context.task_id == "recent"
    
    def test_query_by_tags(self, storage):
        """Test querying by tags."""
        # Create feedbacks with tags
        feedback1 = create_success_feedback(
            task_id="task1",
            message="Success",
            tags=["urgent", "production"]
        )
        feedback2 = create_success_feedback(
            task_id="task2",
            message="Success",
            tags=["test", "development"]
        )
        
        storage.save(feedback1)
        storage.save(feedback2)
        
        # Query by tags
        results = storage.query(tags=["urgent"])
        assert len(results) == 1
        assert "urgent" in results[0].context.tags
        
        # Query by multiple tags
        results = storage.query(tags=["urgent", "production"])
        assert len(results) == 1
    
    def test_query_with_limit(self, storage):
        """Test query with limit."""
        # Save multiple feedbacks
        for i in range(10):
            feedback = create_success_feedback(
                task_id=f"task{i}",
                message=f"Success {i}"
            )
            storage.save(feedback)
        
        # Query with limit
        results = storage.query(limit=5)
        assert len(results) == 5
    
    def test_delete_feedback(self, storage, sample_feedback):
        """Test deleting feedback."""
        # Save feedback
        storage.save(sample_feedback)
        assert storage.count() == 1
        
        # Delete feedback
        success = storage.delete(sample_feedback.feedback_id)
        assert success
        assert storage.count() == 0
        
        # Verify can't load deleted feedback
        loaded = storage.load(sample_feedback.feedback_id)
        assert loaded is None
    
    def test_delete_nonexistent_feedback(self, storage):
        """Test deleting non-existent feedback."""
        success = storage.delete("nonexistent-id")
        assert not success
    
    def test_clear_storage(self, storage):
        """Test clearing all feedback."""
        # Save multiple feedbacks
        for i in range(5):
            feedback = create_success_feedback(
                task_id=f"task{i}",
                message=f"Success {i}"
            )
            storage.save(feedback)
        
        assert storage.count() == 5
        
        # Clear storage
        storage.clear()
        assert storage.count() == 0
        
        # Verify index is empty
        with open(storage._index_file, 'r') as f:
            index = json.load(f)
        assert index == {}
    
    def test_get_statistics(self, storage):
        """Test getting storage statistics."""
        # Save various feedbacks
        feedbacks = [
            create_success_feedback(task_id="task1", message="Success"),
            create_error_feedback(
                task_id="task2",
                message="Error",
                error_details={},
                severity=FeedbackSeverity.ERROR
            ),
            FeedbackModel(
                feedback_type=FeedbackType.WORKER_PERFORMANCE,
                severity=FeedbackSeverity.INFO,
                category=FeedbackCategory.PERFORMANCE,
                message="Performance",
                context=FeedbackContext(task_id="task3"),
                metrics=FeedbackMetrics(execution_time=10.0)
            )
        ]
        
        for feedback in feedbacks:
            storage.save(feedback)
        
        # Get statistics
        stats = storage.get_statistics()
        
        assert stats["total_count"] == 3
        assert stats["type_counts"]["task_success"] == 1
        assert stats["type_counts"]["error_report"] == 1
        assert stats["type_counts"]["worker_performance"] == 1
        assert stats["severity_counts"]["info"] == 2
        assert stats["severity_counts"]["error"] == 1
        assert stats["category_counts"]["execution"] == 2
        assert stats["category_counts"]["performance"] == 1
        assert "storage_size_mb" in stats
    
    def test_file_sharding(self, storage):
        """Test file sharding by ID prefix."""
        # Create feedbacks with specific IDs
        feedback1 = create_success_feedback(task_id="task1", message="Test")
        feedback1.feedback_id = "aa" + feedback1.feedback_id[2:]
        
        feedback2 = create_success_feedback(task_id="task2", message="Test")
        feedback2.feedback_id = "bb" + feedback2.feedback_id[2:]
        
        storage.save(feedback1)
        storage.save(feedback2)
        
        # Check shard directories exist
        assert (storage.storage_path / "aa").exists()
        assert (storage.storage_path / "bb").exists()
        
        # Check files are in correct shards
        assert (storage.storage_path / "aa" / f"{feedback1.feedback_id}.json").exists()
        assert (storage.storage_path / "bb" / f"{feedback2.feedback_id}.json").exists()


class TestFeedbackStorage:
    """Test suite for FeedbackStorage with caching."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def storage(self, temp_dir):
        """Create FeedbackStorage instance."""
        backend = JSONFeedbackStorage(str(Path(temp_dir) / "feedback"))
        return FeedbackStorage(backend=backend)
    
    def test_save_with_caching(self, storage):
        """Test save updates cache."""
        feedback = create_success_feedback(task_id="task1", message="Success")
        
        # Save feedback
        storage.save(feedback)
        
        # Check cache
        assert feedback.feedback_id in storage._cache
        assert storage._cache[feedback.feedback_id] == feedback
    
    def test_load_with_caching(self, storage):
        """Test load uses cache."""
        feedback = create_success_feedback(task_id="task1", message="Success")
        storage.save(feedback)
        
        # Clear backend to ensure cache is used
        storage._cache[feedback.feedback_id] = feedback
        
        # Load should use cache
        loaded = storage.load(feedback.feedback_id)
        assert loaded == feedback
    
    def test_cache_size_limit(self, storage):
        """Test cache size limiting."""
        storage._cache_size = 10  # Small cache for testing
        
        # Save more than cache size
        feedbacks = []
        for i in range(15):
            time.sleep(0.01)  # Ensure different timestamps
            feedback = create_success_feedback(
                task_id=f"task{i}",
                message=f"Success {i}"
            )
            feedbacks.append(feedback)
            storage.save(feedback)
        
        # Cache should be limited
        assert len(storage._cache) <= storage._cache_size
        
        # Newest should be in cache
        assert feedbacks[-1].feedback_id in storage._cache
    
    def test_batch_save(self, storage):
        """Test batch saving feedbacks."""
        feedbacks = [
            create_success_feedback(task_id=f"task{i}", message=f"Success {i}")
            for i in range(5)
        ]
        
        storage.batch_save(feedbacks)
        
        # All should be saved
        assert storage.count() == 5
        
        # All should be loadable
        for feedback in feedbacks:
            loaded = storage.load(feedback.feedback_id)
            assert loaded is not None
    
    def test_export_to_file(self, storage, temp_dir):
        """Test exporting feedbacks to file."""
        # Save feedbacks
        feedbacks = []
        for i in range(3):
            feedback = create_success_feedback(
                task_id=f"task{i}",
                message=f"Success {i}"
            )
            feedbacks.append(feedback)
            storage.save(feedback)
        
        # Export
        export_path = Path(temp_dir) / "export.json"
        count = storage.export_to_file(str(export_path))
        
        assert count == 3
        assert export_path.exists()
        
        # Verify export content
        with open(export_path, 'r') as f:
            data = json.load(f)
        
        assert data["count"] == 3
        assert len(data["feedbacks"]) == 3
        assert "export_time" in data
    
    def test_import_from_file(self, storage, temp_dir):
        """Test importing feedbacks from file."""
        # Create export file
        feedbacks_data = []
        for i in range(3):
            feedback = create_success_feedback(
                task_id=f"task{i}",
                message=f"Success {i}"
            )
            feedbacks_data.append(feedback.to_dict())
        
        export_data = {
            "export_time": datetime.now().isoformat(),
            "count": 3,
            "feedbacks": feedbacks_data
        }
        
        export_path = Path(temp_dir) / "import.json"
        with open(export_path, 'w') as f:
            json.dump(export_data, f)
        
        # Import
        count = storage.import_from_file(str(export_path))
        
        assert count == 3
        assert storage.count() == 3
    
    def test_delete_removes_from_cache(self, storage):
        """Test delete removes from cache."""
        feedback = create_success_feedback(task_id="task1", message="Success")
        storage.save(feedback)
        
        assert feedback.feedback_id in storage._cache
        
        # Delete
        storage.delete(feedback.feedback_id)
        
        assert feedback.feedback_id not in storage._cache
    
    def test_clear_clears_cache(self, storage):
        """Test clear also clears cache."""
        # Save feedbacks
        for i in range(3):
            feedback = create_success_feedback(
                task_id=f"task{i}",
                message=f"Success {i}"
            )
            storage.save(feedback)
        
        assert len(storage._cache) > 0
        
        # Clear
        storage.clear()
        
        assert len(storage._cache) == 0
    
    def test_concurrent_access(self, storage):
        """Test thread-safe concurrent access."""
        import threading
        
        results = []
        errors = []
        
        def save_feedback(index):
            try:
                feedback = create_success_feedback(
                    task_id=f"task{index}",
                    message=f"Concurrent {index}"
                )
                storage.save(feedback)
                results.append(feedback.feedback_id)
            except Exception as e:
                errors.append(e)
        
        # Save concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(target=save_feedback, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all saved
        assert len(errors) == 0
        assert len(results) == 10
        assert storage.count() == 10