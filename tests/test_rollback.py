"""
Unit tests for RollbackManager

Tests rollback functionality, checkpoint integration, error handling,
and recovery scenarios.
"""

import tempfile
import os
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import uuid
import time

from claude_orchestrator.rollback import (
    RollbackManager, RollbackReason, RollbackStatus, RollbackRecord,
    create_rollback_manager
)
from claude_orchestrator.checkpoint_system import (
    CheckpointManager, CheckpointData, CheckpointState
)


class TestRollbackManager:
    """Tests for RollbackManager class"""
    
    def setup_method(self):
        """Set up test environment"""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = os.path.join(self.temp_dir, "checkpoints")
        self.rollback_dir = os.path.join(self.temp_dir, "rollbacks")
        
        # Initialize managers
        self.checkpoint_manager = CheckpointManager(storage_dir=self.checkpoint_dir)
        self.rollback_manager = RollbackManager(
            checkpoint_manager=self.checkpoint_manager,
            storage_dir=self.rollback_dir
        )
    
    def teardown_method(self):
        """Clean up after test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test RollbackManager initialization"""
        assert self.rollback_manager.checkpoint_manager is not None
        assert os.path.exists(self.rollback_dir)
        assert self.rollback_manager.max_rollback_history == 100
        assert len(self.rollback_manager.rollback_history) == 0
        assert len(self.rollback_manager.active_rollbacks) == 0
    
    def test_create_checkpoint(self):
        """Test creating a checkpoint through RollbackManager"""
        task_id = "test-task-001"
        task_title = "Test Task"
        
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title=task_title,
            step_number=1,
            step_description="Step 1: Initialize",
            data={"progress": 0.25, "state": "initializing"},
            metadata={"user": "test-user"}
        )
        
        assert checkpoint_id is not None
        
        # Verify checkpoint was created with rollback metadata
        checkpoint = self.checkpoint_manager.get_checkpoint(checkpoint_id)
        assert checkpoint is not None
        assert checkpoint.metadata.get('rollback_enabled') is True
        assert checkpoint.metadata.get('rollback_version') == RollbackManager.ROLLBACK_VERSION
    
    def test_list_checkpoints(self):
        """Test listing available checkpoints"""
        # Create multiple checkpoints
        task_id = "test-task-002"
        checkpoint_ids = []
        
        for i in range(5):
            checkpoint_id = self.rollback_manager.create_checkpoint(
                task_id=task_id,
                task_title=f"Task {i}",
                step_number=i,
                step_description=f"Step {i}",
                data={"step": i}
            )
            checkpoint_ids.append(checkpoint_id)
            time.sleep(0.01)  # Ensure different timestamps
        
        # List all checkpoints
        all_checkpoints = self.rollback_manager.list_checkpoints()
        assert len(all_checkpoints) >= 5
        
        # List checkpoints for specific task
        task_checkpoints = self.rollback_manager.list_checkpoints(task_id)
        assert len(task_checkpoints) == 5
        
        # Verify ordering (newest first)
        assert task_checkpoints[0].step_number == 4
        assert task_checkpoints[-1].step_number == 0
    
    def test_restore_checkpoint_success(self):
        """Test successful checkpoint restoration"""
        task_id = "test-task-003"
        
        # Create checkpoint
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Rollback Test Task",
            step_number=5,
            step_description="Step 5: Processing",
            data={
                "processed_items": 100,
                "total_items": 200,
                "state": "processing"
            },
            metadata={"version": "1.0"}
        )
        
        # Restore checkpoint
        success, restored_data = self.rollback_manager.restore_checkpoint(
            checkpoint_id=checkpoint_id,
            reason=RollbackReason.MANUAL
        )
        
        assert success is True
        assert restored_data is not None
        assert restored_data["task_id"] == task_id
        assert restored_data["step_number"] == 5
        assert restored_data["data"]["processed_items"] == 100
        
        # Verify rollback record was created
        history = self.rollback_manager.get_rollback_history()
        assert len(history) == 1
        assert history[0].status == RollbackStatus.SUCCESS
        assert history[0].checkpoint_id == checkpoint_id
        assert history[0].reason == RollbackReason.MANUAL
    
    def test_restore_checkpoint_with_validation(self):
        """Test checkpoint restoration with validation"""
        task_id = "test-task-004"
        
        # Create checkpoint
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Validation Test",
            step_number=1,
            step_description="Test step",
            data={"test": "data"}
        )
        
        # Mock validation to fail
        with patch.object(self.rollback_manager, 'validate_checkpoint') as mock_validate:
            mock_validate.return_value = (False, "Validation failed")
            
            success, restored_data = self.rollback_manager.restore_checkpoint(
                checkpoint_id=checkpoint_id,
                validate=True
            )
            
            assert success is False
            assert restored_data is None
            
            # Check rollback history
            history = self.rollback_manager.get_rollback_history()
            assert len(history) == 1
            assert history[0].status == RollbackStatus.FAILED
    
    def test_restore_nonexistent_checkpoint(self):
        """Test restoring a checkpoint that doesn't exist"""
        fake_checkpoint_id = "nonexistent-checkpoint"
        
        success, restored_data = self.rollback_manager.restore_checkpoint(
            checkpoint_id=fake_checkpoint_id
        )
        
        assert success is False
        assert restored_data is None
        
        # Check rollback history
        history = self.rollback_manager.get_rollback_history()
        assert len(history) == 1
        assert history[0].status == RollbackStatus.FAILED
        assert "not found" in history[0].error_message
    
    def test_delete_checkpoint(self):
        """Test deleting checkpoints"""
        task_id = "test-task-005"
        
        # Create checkpoint
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Delete Test",
            step_number=1,
            step_description="Test",
            data={"test": "data"}
        )
        
        # Verify checkpoint exists
        checkpoints = self.rollback_manager.list_checkpoints(task_id)
        assert len(checkpoints) == 1
        
        # Delete checkpoint
        success = self.rollback_manager.delete_checkpoint(checkpoint_id)
        assert success is True
        
        # Verify checkpoint is gone
        checkpoints = self.rollback_manager.list_checkpoints(task_id)
        assert len(checkpoints) == 0
    
    def test_archive_used_checkpoint(self):
        """Test that used checkpoints are archived instead of deleted"""
        task_id = "test-task-006"
        
        # Create and use checkpoint
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Archive Test",
            step_number=1,
            step_description="Test",
            data={"test": "data"}
        )
        
        # Perform rollback
        success, _ = self.rollback_manager.restore_checkpoint(checkpoint_id)
        assert success is True
        
        # Try to delete used checkpoint
        delete_success = self.rollback_manager.delete_checkpoint(checkpoint_id)
        assert delete_success is True
        
        # Verify checkpoint was archived
        archive_dir = Path(self.checkpoint_dir) / "archived"
        assert archive_dir.exists()
        archived_file = archive_dir / f"checkpoint_{checkpoint_id}.json"
        assert archived_file.exists()
    
    def test_validate_checkpoint(self):
        """Test checkpoint validation"""
        # Create valid checkpoint
        valid_checkpoint = CheckpointData(
            checkpoint_id="valid-001",
            task_id="test-task",
            task_title="Test Task",
            state=CheckpointState.COMPLETED,
            step_number=1,
            data={"test": "data"},
            metadata={"rollback_version": RollbackManager.ROLLBACK_VERSION}
        )
        
        is_valid, msg = self.rollback_manager.validate_checkpoint(valid_checkpoint)
        assert is_valid is True
        assert "valid" in msg.lower()
        
        # Test failed checkpoint
        failed_checkpoint = CheckpointData(
            checkpoint_id="failed-001",
            task_id="test-task",
            task_title="Test Task",
            state=CheckpointState.FAILED,
            step_number=1,
            data={"test": "data"}
        )
        
        is_valid, msg = self.rollback_manager.validate_checkpoint(failed_checkpoint)
        assert is_valid is False
        assert "failed" in msg.lower()
        
        # Test incompatible version
        old_checkpoint = CheckpointData(
            checkpoint_id="old-001",
            task_id="test-task",
            task_title="Test Task",
            state=CheckpointState.COMPLETED,
            step_number=1,
            data={"test": "data"},
            metadata={"rollback_version": "0.0.1"}
        )
        
        is_valid, msg = self.rollback_manager.validate_checkpoint(old_checkpoint)
        assert is_valid is False
        assert "version" in msg.lower()
        
        # Test corrupted data
        corrupted_checkpoint = CheckpointData(
            checkpoint_id="corrupted-001",
            task_id="test-task",
            task_title="Test Task",
            state=CheckpointState.COMPLETED,
            step_number=1,
            data="not a dict",  # Should be dict
            metadata={}
        )
        
        is_valid, msg = self.rollback_manager.validate_checkpoint(corrupted_checkpoint)
        assert is_valid is False
        assert "corrupted" in msg.lower()
    
    def test_rollback_history_persistence(self):
        """Test that rollback history is persisted"""
        task_id = "test-task-007"
        
        # Create checkpoint
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="History Test",
            step_number=1,
            step_description="Test",
            data={"test": "data"}
        )
        
        # Perform rollback
        self.rollback_manager.restore_checkpoint(checkpoint_id)
        
        # Create new manager instance
        new_manager = RollbackManager(
            checkpoint_manager=self.checkpoint_manager,
            storage_dir=self.rollback_dir
        )
        
        # Verify history was loaded
        history = new_manager.get_rollback_history()
        assert len(history) == 1
        assert history[0].checkpoint_id == checkpoint_id
    
    def test_rollback_callbacks(self):
        """Test rollback callback functionality"""
        callback_events = []
        
        def test_callback(event_type, rollback_record, checkpoint_data):
            callback_events.append({
                "event": event_type,
                "rollback_id": rollback_record.rollback_id,
                "checkpoint_id": rollback_record.checkpoint_id
            })
        
        self.rollback_manager.register_rollback_callback(test_callback)
        
        # Create and restore checkpoint
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id="test-task-008",
            task_title="Callback Test",
            step_number=1,
            step_description="Test",
            data={"test": "data"}
        )
        
        self.rollback_manager.restore_checkpoint(checkpoint_id)
        
        # Verify callbacks were called
        assert len(callback_events) == 2
        assert callback_events[0]["event"] == "before_rollback"
        assert callback_events[1]["event"] == "after_rollback"
        assert callback_events[0]["checkpoint_id"] == checkpoint_id
    
    def test_can_rollback(self):
        """Test checking if task can be rolled back"""
        task_id = "test-task-009"
        
        # No checkpoints - cannot rollback
        can_rollback, reason = self.rollback_manager.can_rollback(task_id)
        assert can_rollback is False
        assert "No checkpoints" in reason
        
        # Create checkpoint
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Can Rollback Test",
            step_number=1,
            step_description="Test",
            data={"test": "data"}
        )
        
        # Now should be able to rollback
        can_rollback, reason = self.rollback_manager.can_rollback(task_id)
        assert can_rollback is True
        
        # Start a rollback (mock in-progress)
        with self.rollback_manager._lock:
            self.rollback_manager.active_rollbacks["test-rollback"] = RollbackRecord(
                rollback_id="test-rollback",
                checkpoint_id=checkpoint_id,
                task_id=task_id,
                reason=RollbackReason.MANUAL,
                status=RollbackStatus.IN_PROGRESS,
                initiated_at=datetime.now()
            )
        
        # Should not be able to rollback while one is in progress
        can_rollback, reason = self.rollback_manager.can_rollback(task_id)
        assert can_rollback is False
        assert "in progress" in reason
    
    def test_rollback_on_error_context_manager(self):
        """Test rollback_on_error context manager"""
        task_id = "test-task-010"
        
        # Create checkpoint
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Context Manager Test",
            step_number=1,
            step_description="Before error",
            data={"state": "before"}
        )
        
        # Test successful execution (no rollback)
        with self.rollback_manager.rollback_on_error(task_id, checkpoint_id):
            # Simulate work
            pass
        
        history = self.rollback_manager.get_rollback_history()
        assert len(history) == 0  # No rollback should have occurred
        
        # Test with error (should trigger rollback)
        try:
            with self.rollback_manager.rollback_on_error(task_id, checkpoint_id):
                # Simulate error
                raise ValueError("Test error")
        except ValueError:
            pass
        
        history = self.rollback_manager.get_rollback_history()
        assert len(history) == 1
        assert history[0].reason == RollbackReason.ERROR
        assert history[0].status == RollbackStatus.SUCCESS
    
    def test_cleanup_old_checkpoints(self):
        """Test cleaning up old checkpoints"""
        task_id = "test-task-011"
        
        # Create old checkpoint
        old_checkpoint_id = str(uuid.uuid4())
        old_checkpoint = CheckpointData(
            checkpoint_id=old_checkpoint_id,
            task_id=task_id,
            task_title="Old Task",
            state=CheckpointState.COMPLETED,
            step_number=1,
            data={"test": "data"},
            created_at=datetime.now() - timedelta(days=40)  # 40 days old
        )
        
        # Save old checkpoint manually
        checkpoint_file = Path(self.checkpoint_dir) / f"checkpoint_{old_checkpoint_id}.json"
        with open(checkpoint_file, 'w') as f:
            json.dump(old_checkpoint.to_dict(), f)
        
        # Create recent checkpoint
        recent_checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Recent Task",
            step_number=2,
            step_description="Recent",
            data={"test": "data"}
        )
        
        # Run cleanup
        self.rollback_manager.cleanup_old_checkpoints(days=30)
        
        # Verify old checkpoint was deleted
        checkpoints = self.rollback_manager.list_checkpoints(task_id)
        checkpoint_ids = [c.checkpoint_id for c in checkpoints]
        
        assert old_checkpoint_id not in checkpoint_ids
        assert recent_checkpoint_id in checkpoint_ids
    
    def test_max_rollback_history(self):
        """Test that rollback history respects max limit"""
        # Set a small limit for testing
        self.rollback_manager.max_rollback_history = 5
        
        # Create and rollback multiple checkpoints
        for i in range(10):
            checkpoint_id = self.rollback_manager.create_checkpoint(
                task_id=f"task-{i}",
                task_title=f"Task {i}",
                step_number=1,
                step_description="Test",
                data={"index": i}
            )
            
            self.rollback_manager.restore_checkpoint(checkpoint_id)
        
        # Reload history
        self.rollback_manager._save_rollback_history()
        self.rollback_manager._load_rollback_history()
        
        # Verify only the most recent records are kept
        assert len(self.rollback_manager.rollback_history) <= 5
        
        # Verify they are the most recent ones
        history = self.rollback_manager.get_rollback_history()
        assert all(int(r.task_id.split('-')[1]) >= 5 for r in history)
    
    def test_concurrent_rollbacks(self):
        """Test handling concurrent rollback attempts"""
        import threading
        
        task_id = "test-task-012"
        results = []
        
        # Create checkpoint
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Concurrent Test",
            step_number=1,
            step_description="Test",
            data={"test": "data"}
        )
        
        def perform_rollback():
            success, data = self.rollback_manager.restore_checkpoint(checkpoint_id)
            results.append(success)
        
        # Start multiple rollback threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=perform_rollback)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Only one should succeed
        assert sum(results) == 1
        
        # Check history
        history = self.rollback_manager.get_rollback_history()
        successful_rollbacks = [r for r in history if r.status == RollbackStatus.SUCCESS]
        assert len(successful_rollbacks) == 1


class TestRollbackRecord:
    """Tests for RollbackRecord data class"""
    
    def test_rollback_record_serialization(self):
        """Test RollbackRecord to_dict and from_dict"""
        record = RollbackRecord(
            rollback_id="test-rollback-001",
            checkpoint_id="checkpoint-001",
            task_id="task-001",
            reason=RollbackReason.ERROR,
            status=RollbackStatus.SUCCESS,
            initiated_at=datetime.now(),
            completed_at=datetime.now(),
            error_message=None,
            restored_data={"test": "data"},
            metadata={"user": "test"}
        )
        
        # Convert to dict
        record_dict = record.to_dict()
        
        # Verify fields
        assert record_dict["rollback_id"] == "test-rollback-001"
        assert record_dict["reason"] == "error"
        assert record_dict["status"] == "success"
        assert "initiated_at" in record_dict
        assert "completed_at" in record_dict
        
        # Convert back from dict
        restored_record = RollbackRecord.from_dict(record_dict)
        
        assert restored_record.rollback_id == record.rollback_id
        assert restored_record.reason == record.reason
        assert restored_record.status == record.status
        assert restored_record.restored_data == record.restored_data


class TestConvenienceFunctions:
    """Tests for convenience functions"""
    
    def test_create_rollback_manager(self):
        """Test create_rollback_manager convenience function"""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = create_rollback_manager(storage_dir=temp_dir)
            
            assert isinstance(manager, RollbackManager)
            assert manager.checkpoint_manager is not None
            assert os.path.exists(temp_dir)