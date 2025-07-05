"""Comprehensive unit tests for RollbackManager"""

import unittest
import tempfile
import shutil
import json
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

from claude_orchestrator.rollback_manager import (
    RollbackManager, CheckpointMetadata, RollbackResult,
    RollbackStrategy, CheckpointType
)


class TestRollbackManager(unittest.TestCase):
    """Test cases for RollbackManager"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = str(Path(self.temp_dir) / "checkpoints")
        self.manager = RollbackManager(
            checkpoint_dir=self.checkpoint_dir,
            max_checkpoints=5,
            auto_checkpoint=True
        )
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)
        
    def test_initialization(self):
        """Test RollbackManager initialization"""
        self.assertIsNotNone(self.manager)
        self.assertEqual(str(self.manager.checkpoint_dir), self.checkpoint_dir)
        self.assertTrue(Path(self.checkpoint_dir).exists())
        self.assertEqual(self.manager.max_checkpoints, 5)
        self.assertTrue(self.manager.auto_checkpoint)
        
    def test_create_checkpoint(self):
        """Test checkpoint creation"""
        checkpoint_id = self.manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Test checkpoint"
        )
        
        self.assertIsNotNone(checkpoint_id)
        
        # Check metadata was saved
        metadata = self.manager._load_metadata()
        self.assertIn(checkpoint_id, metadata)
        self.assertEqual(metadata[checkpoint_id]['description'], "Test checkpoint")
        self.assertEqual(metadata[checkpoint_id]['checkpoint_type'], CheckpointType.MANUAL.value)
        
        # Check checkpoint directory exists
        checkpoint_path = self.manager.checkpoint_dir / checkpoint_id
        self.assertTrue(checkpoint_path.exists())
        
    def test_update_task_state(self):
        """Test updating task state"""
        task_id = "test-task-123"
        state = {"status": "in_progress", "worker": "worker-1"}
        
        self.manager.update_task_state(task_id, state)
        
        self.assertIn(task_id, self.manager._current_tasks)
        self.assertEqual(self.manager._current_tasks[task_id], state)
        
    def test_add_task_dependency(self):
        """Test adding task dependencies"""
        self.manager.add_task_dependency("task-2", "task-1")
        
        self.assertIn("task-2", self.manager._task_dependencies)
        self.assertIn("task-1", self.manager._task_dependencies["task-2"])
        
    def test_track_file(self):
        """Test file tracking"""
        file_path = "/path/to/file.py"
        self.manager.track_file(file_path)
        
        self.assertIn(file_path, self.manager._tracked_files)
        
    def test_list_checkpoints(self):
        """Test listing checkpoints"""
        # Create multiple checkpoints
        checkpoint_ids = []
        for i in range(3):
            checkpoint_id = self.manager.create_checkpoint(
                checkpoint_type=CheckpointType.AUTOMATIC,
                description=f"Checkpoint {i}"
            )
            checkpoint_ids.append(checkpoint_id)
            time.sleep(0.01)  # Ensure different timestamps
            
        checkpoints = self.manager.list_checkpoints()
        
        self.assertEqual(len(checkpoints), 3)
        # Should be sorted by timestamp (newest first)
        for checkpoint in checkpoints:
            self.assertIn(checkpoint['id'], checkpoint_ids)
            
    def test_rollback_to_checkpoint(self):
        """Test rolling back to a checkpoint"""
        # Set initial task state
        self.manager.update_task_state("task-1", {"status": "completed"})
        self.manager.update_task_state("task-2", {"status": "in_progress"})
        
        # Create checkpoint
        checkpoint_id = self.manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Before changes"
        )
        
        # Modify state after checkpoint
        self.manager.update_task_state("task-1", {"status": "failed"})
        self.manager.update_task_state("task-3", {"status": "pending"})
        
        # Rollback
        result = self.manager.rollback_to_checkpoint(checkpoint_id)
        
        self.assertIsInstance(result, RollbackResult)
        self.assertTrue(result.success)
        self.assertEqual(result.checkpoint_id, checkpoint_id)
        
    def test_checkpoint_metadata_creation(self):
        """Test CheckpointMetadata creation"""
        metadata = CheckpointMetadata(
            checkpoint_id="test-123",
            timestamp=datetime.now(),
            checkpoint_type=CheckpointType.MANUAL,
            description="Test metadata",
            task_states={"task-1": "completed"},
            file_snapshots=["file1.py", "file2.py"],
            custom_data={"key": "value"}
        )
        
        # Convert to dict
        metadata_dict = metadata.to_dict()
        
        self.assertEqual(metadata_dict["checkpoint_id"], "test-123")
        self.assertEqual(metadata_dict["checkpoint_type"], "manual")
        self.assertEqual(metadata_dict["description"], "Test metadata")
        
        # Create from dict
        restored_metadata = CheckpointMetadata.from_dict(metadata_dict)
        
        self.assertEqual(restored_metadata.checkpoint_id, metadata.checkpoint_id)
        self.assertEqual(restored_metadata.checkpoint_type, metadata.checkpoint_type)
        
    def test_max_checkpoints_limit(self):
        """Test that max checkpoints limit is enforced"""
        # Create more checkpoints than the limit
        checkpoint_ids = []
        for i in range(7):  # More than max_checkpoints (5)
            checkpoint_id = self.manager.create_checkpoint(
                checkpoint_type=CheckpointType.AUTOMATIC,
                description=f"Checkpoint {i}"
            )
            checkpoint_ids.append(checkpoint_id)
            time.sleep(0.01)
            
        # Check metadata only has max_checkpoints
        metadata = self.manager._load_metadata()
        self.assertLessEqual(len(metadata), self.manager.max_checkpoints)
        
        # Oldest checkpoints should be removed
        self.assertNotIn(checkpoint_ids[0], metadata)
        self.assertNotIn(checkpoint_ids[1], metadata)
        
        # Most recent should still exist
        self.assertIn(checkpoint_ids[-1], metadata)
        
    def test_selective_rollback(self):
        """Test selective rollback strategy"""
        # Set up initial state
        self.manager.update_task_state("task-1", {"status": "completed"})
        self.manager.update_task_state("task-2", {"status": "completed"})
        self.manager.update_task_state("task-3", {"status": "completed"})
        
        # Create checkpoint
        checkpoint_id = self.manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Test selective rollback"
        )
        
        # Modify states
        self.manager.update_task_state("task-1", {"status": "failed"})
        self.manager.update_task_state("task-2", {"status": "failed"})
        
        # Selective rollback for task-1 only
        result = self.manager.rollback_to_checkpoint(
            checkpoint_id,
            strategy=RollbackStrategy.SELECTIVE,
            target_tasks=["task-1"]
        )
        
        self.assertTrue(result.success)
        self.assertIn("task-1", result.rolled_back_tasks)
        
    def test_rollback_with_file_snapshots(self):
        """Test rollback with file snapshots"""
        # Create a test file
        test_file = Path(self.temp_dir) / "test.py"
        test_file.write_text("original content")
        
        # Track the file
        self.manager.track_file(str(test_file))
        
        # Create checkpoint with file
        checkpoint_id = self.manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="With file snapshot",
            include_files=[str(test_file)]
        )
        
        # Modify the file
        test_file.write_text("modified content")
        
        # Rollback
        result = self.manager.rollback_to_checkpoint(checkpoint_id)
        
        self.assertTrue(result.success)
        # File should be restored
        self.assertEqual(test_file.read_text(), "original content")
        
    def test_concurrent_checkpoint_creation(self):
        """Test thread-safe checkpoint creation"""
        import threading
        
        checkpoint_ids = []
        errors = []
        
        def create_checkpoint(index):
            try:
                checkpoint_id = self.manager.create_checkpoint(
                    checkpoint_type=CheckpointType.AUTOMATIC,
                    description=f"Concurrent {index}"
                )
                checkpoint_ids.append(checkpoint_id)
            except Exception as e:
                errors.append(e)
                
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_checkpoint, args=(i,))
            threads.append(thread)
            thread.start()
            
        # Wait for all threads
        for thread in threads:
            thread.join()
            
        # Should have created all checkpoints without errors
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(checkpoint_ids), 5)
        # All checkpoint IDs should be unique
        self.assertEqual(len(set(checkpoint_ids)), 5)
        
    def test_rollback_history(self):
        """Test rollback history tracking"""
        # Create checkpoint
        checkpoint_id = self.manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="History test"
        )
        
        # Perform rollback
        result = self.manager.rollback_to_checkpoint(checkpoint_id)
        
        # Check history
        self.assertEqual(len(self.manager._rollback_history), 1)
        self.assertEqual(self.manager._rollback_history[0], result)
        
    def test_get_task_dependencies_recursive(self):
        """Test recursive dependency resolution"""
        # Set up dependency chain: task-3 -> task-2 -> task-1
        self.manager.add_task_dependency("task-2", "task-1")
        self.manager.add_task_dependency("task-3", "task-2")
        
        # Get all dependencies for task-3
        deps = self.manager._get_task_dependencies_recursive({"task-3"})
        
        self.assertEqual(deps, {"task-1", "task-2", "task-3"})
        
    def test_cleanup_old_checkpoints(self):
        """Test cleanup of old checkpoints"""
        # Create checkpoints up to the limit
        for i in range(self.manager.max_checkpoints):
            self.manager.create_checkpoint(
                checkpoint_type=CheckpointType.AUTOMATIC,
                description=f"Checkpoint {i}"
            )
            time.sleep(0.01)
            
        # Verify count
        metadata = self.manager._load_metadata()
        self.assertEqual(len(metadata), self.manager.max_checkpoints)
        
        # Create one more - should trigger cleanup
        new_checkpoint_id = self.manager.create_checkpoint(
            checkpoint_type=CheckpointType.AUTOMATIC,
            description="Trigger cleanup"
        )
        
        # Should still have max_checkpoints
        metadata = self.manager._load_metadata()
        self.assertEqual(len(metadata), self.manager.max_checkpoints)
        self.assertIn(new_checkpoint_id, metadata)
        
    def test_error_handling(self):
        """Test error handling scenarios"""
        # Test rollback with non-existent checkpoint
        result = self.manager.rollback_to_checkpoint("non-existent-id")
        self.assertFalse(result.success)
        self.assertIn("not found", result.errors[0])
        
        # Test invalid checkpoint directory
        with self.assertRaises(Exception):
            invalid_manager = RollbackManager(
                checkpoint_dir="/invalid/path/that/cannot/be/created",
                max_checkpoints=5
            )


class TestCheckpointMetadata(unittest.TestCase):
    """Test cases for CheckpointMetadata class"""
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        metadata = CheckpointMetadata(
            checkpoint_id="test-123",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            checkpoint_type=CheckpointType.MANUAL,
            description="Test checkpoint",
            task_states={"task-1": "completed"},
            file_snapshots=["file1.py"],
            custom_data={"key": "value"},
            parent_checkpoint="parent-123"
        )
        
        result = metadata.to_dict()
        
        self.assertEqual(result["checkpoint_id"], "test-123")
        self.assertEqual(result["checkpoint_type"], "manual")
        self.assertEqual(result["description"], "Test checkpoint")
        self.assertEqual(result["task_states"], {"task-1": "completed"})
        self.assertEqual(result["file_snapshots"], ["file1.py"])
        self.assertEqual(result["custom_data"], {"key": "value"})
        self.assertEqual(result["parent_checkpoint"], "parent-123")
        
    def test_from_dict(self):
        """Test creation from dictionary"""
        data = {
            "checkpoint_id": "test-456",
            "timestamp": "2024-01-01T12:00:00",
            "checkpoint_type": "automatic",
            "description": "Auto checkpoint",
            "task_states": {"task-2": "in_progress"},
            "file_snapshots": ["file2.py", "file3.py"],
            "custom_data": {"number": 42},
            "parent_checkpoint": None
        }
        
        metadata = CheckpointMetadata.from_dict(data)
        
        self.assertEqual(metadata.checkpoint_id, "test-456")
        self.assertEqual(metadata.checkpoint_type, CheckpointType.AUTOMATIC)
        self.assertEqual(metadata.description, "Auto checkpoint")
        self.assertEqual(metadata.task_states, {"task-2": "in_progress"})
        self.assertEqual(metadata.file_snapshots, ["file2.py", "file3.py"])
        self.assertEqual(metadata.custom_data, {"number": 42})
        self.assertIsNone(metadata.parent_checkpoint)


class TestRollbackResult(unittest.TestCase):
    """Test cases for RollbackResult class"""
    
    def test_initialization(self):
        """Test RollbackResult initialization"""
        result = RollbackResult(
            success=True,
            checkpoint_id="test-123",
            strategy=RollbackStrategy.FULL,
            rolled_back_tasks=["task-1", "task-2"],
            restored_files=["file1.py"],
            errors=[]
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.checkpoint_id, "test-123")
        self.assertEqual(result.strategy, RollbackStrategy.FULL)
        self.assertEqual(result.rolled_back_tasks, ["task-1", "task-2"])
        self.assertEqual(result.restored_files, ["file1.py"])
        self.assertEqual(result.errors, [])
        self.assertIsNotNone(result.timestamp)
        
    def test_with_errors(self):
        """Test RollbackResult with errors"""
        result = RollbackResult(
            success=False,
            checkpoint_id="test-456",
            strategy=RollbackStrategy.PARTIAL,
            errors=["Error 1", "Error 2"]
        )
        
        self.assertFalse(result.success)
        self.assertEqual(len(result.errors), 2)
        self.assertEqual(result.rolled_back_tasks, [])
        self.assertEqual(result.restored_files, [])


if __name__ == "__main__":
    unittest.main()