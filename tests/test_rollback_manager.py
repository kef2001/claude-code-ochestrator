#!/usr/bin/env python3
"""Unit tests for RollbackManager."""

import pytest
import json
import tempfile
import shutil
import pickle
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from claude_orchestrator.rollback_manager import (
    RollbackManager,
    RollbackStrategy,
    CheckpointType,
    CheckpointMetadata,
    RollbackResult
)


class TestRollbackManager:
    """Test suite for RollbackManager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def rollback_manager(self, temp_dir):
        """Create a RollbackManager instance for testing."""
        return RollbackManager(
            checkpoint_dir=temp_dir,
            max_checkpoints=10,
            auto_checkpoint=True
        )
    
    def test_initialization(self, rollback_manager, temp_dir):
        """Test RollbackManager initialization."""
        assert rollback_manager.checkpoint_dir == Path(temp_dir)
        assert rollback_manager.max_checkpoints == 10
        assert rollback_manager.auto_checkpoint is True
        assert (Path(temp_dir) / "metadata.json").exists()
    
    def test_create_checkpoint_manual(self, rollback_manager):
        """Test creating a manual checkpoint."""
        checkpoint_id = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Test checkpoint"
        )
        
        assert checkpoint_id.startswith("cp_")
        checkpoint_path = rollback_manager.checkpoint_dir / checkpoint_id
        assert checkpoint_path.exists()
        
        # Check metadata was saved
        metadata = rollback_manager._load_metadata()
        assert checkpoint_id in metadata
        assert metadata[checkpoint_id]["description"] == "Test checkpoint"
        assert metadata[checkpoint_id]["checkpoint_type"] == CheckpointType.MANUAL.value
    
    def test_create_checkpoint_with_files(self, rollback_manager, temp_dir):
        """Test creating checkpoint with file snapshots."""
        # Create test file
        test_file = Path(temp_dir) / "test_file.txt"
        test_file.write_text("Original content")
        
        # Track file and create checkpoint
        rollback_manager.track_file(str(test_file))
        checkpoint_id = rollback_manager.create_checkpoint(
            description="Test with files"
        )
        
        # Check file was snapshotted
        checkpoint_path = rollback_manager.checkpoint_dir / checkpoint_id
        snapshot_path = checkpoint_path / "files" / test_file.relative_to(Path.cwd())
        assert snapshot_path.exists()
        assert snapshot_path.read_text() == "Original content"
    
    def test_rollback_full_strategy(self, rollback_manager, temp_dir):
        """Test full rollback strategy."""
        # Create test file
        test_file = Path(temp_dir) / "test_file.txt"
        test_file.write_text("Original content")
        
        # Track file and create checkpoint
        rollback_manager.track_file(str(test_file))
        checkpoint_id = rollback_manager.create_checkpoint()
        
        # Modify file
        test_file.write_text("Modified content")
        
        # Rollback
        result = rollback_manager.rollback(
            checkpoint_id,
            strategy=RollbackStrategy.FULL
        )
        
        assert result.success is True
        assert result.checkpoint_id == checkpoint_id
        assert result.strategy == RollbackStrategy.FULL
        assert test_file.read_text() == "Original content"
    
    def test_rollback_selective_strategy(self, rollback_manager):
        """Test selective rollback strategy with specific tasks."""
        # Register some tasks
        rollback_manager.register_task("task1", {"status": "in_progress"})
        rollback_manager.register_task("task2", {"status": "in_progress"})
        
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint()
        
        # Update task states
        rollback_manager.update_task_state("task1", "completed")
        rollback_manager.update_task_state("task2", "failed")
        
        # Selective rollback of task2 only
        result = rollback_manager.rollback(
            checkpoint_id,
            strategy=RollbackStrategy.SELECTIVE,
            target_tasks=["task2"]
        )
        
        assert result.success is True
        assert "task2" in result.rolled_back_tasks
        assert "task1" not in result.rolled_back_tasks
    
    def test_checkpoint_metadata(self, rollback_manager):
        """Test checkpoint metadata creation and retrieval."""
        checkpoint_id = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.TASK_COMPLETION,
            description="Task completed checkpoint"
        )
        
        metadata = rollback_manager.get_checkpoint_metadata(checkpoint_id)
        assert metadata is not None
        assert metadata.checkpoint_id == checkpoint_id
        assert metadata.checkpoint_type == CheckpointType.TASK_COMPLETION
        assert metadata.description == "Task completed checkpoint"
    
    def test_list_checkpoints(self, rollback_manager):
        """Test listing available checkpoints."""
        # Create multiple checkpoints
        cp1 = rollback_manager.create_checkpoint(description="Checkpoint 1")
        cp2 = rollback_manager.create_checkpoint(description="Checkpoint 2")
        cp3 = rollback_manager.create_checkpoint(description="Checkpoint 3")
        
        checkpoints = rollback_manager.list_checkpoints()
        checkpoint_ids = [cp["checkpoint_id"] for cp in checkpoints]
        
        assert cp1 in checkpoint_ids
        assert cp2 in checkpoint_ids
        assert cp3 in checkpoint_ids
    
    def test_cleanup_old_checkpoints(self, rollback_manager):
        """Test automatic cleanup of old checkpoints."""
        # Set max checkpoints to 3
        rollback_manager.max_checkpoints = 3
        
        # Create 5 checkpoints
        checkpoints = []
        for i in range(5):
            cp_id = rollback_manager.create_checkpoint(
                description=f"Checkpoint {i}"
            )
            checkpoints.append(cp_id)
        
        # Only the last 3 should remain
        remaining = rollback_manager.list_checkpoints()
        remaining_ids = [cp["checkpoint_id"] for cp in remaining]
        
        assert len(remaining_ids) == 3
        assert checkpoints[0] not in remaining_ids  # Oldest removed
        assert checkpoints[1] not in remaining_ids  # Second oldest removed
        assert checkpoints[2] in remaining_ids
        assert checkpoints[3] in remaining_ids
        assert checkpoints[4] in remaining_ids
    
    def test_register_and_update_task(self, rollback_manager):
        """Test task registration and state updates."""
        # Register task
        rollback_manager.register_task("test_task", {
            "status": "pending",
            "description": "Test task"
        })
        
        # Update task state
        rollback_manager.update_task_state("test_task", "in_progress")
        
        # Create checkpoint to capture state
        checkpoint_id = rollback_manager.create_checkpoint()
        metadata = rollback_manager.get_checkpoint_metadata(checkpoint_id)
        
        assert "test_task" in metadata.task_states
        assert metadata.task_states["test_task"] == "in_progress"
    
    def test_track_file(self, rollback_manager, temp_dir):
        """Test file tracking functionality."""
        test_file = Path(temp_dir) / "tracked_file.txt"
        test_file.write_text("Test content")
        
        # Track file
        rollback_manager.track_file(str(test_file))
        
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint()
        metadata = rollback_manager.get_checkpoint_metadata(checkpoint_id)
        
        assert str(test_file) in metadata.file_snapshots
    
    def test_untrack_file(self, rollback_manager, temp_dir):
        """Test file untracking functionality."""
        test_file = Path(temp_dir) / "tracked_file.txt"
        test_file.write_text("Test content")
        
        # Track and then untrack file
        rollback_manager.track_file(str(test_file))
        rollback_manager.untrack_file(str(test_file))
        
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint()
        metadata = rollback_manager.get_checkpoint_metadata(checkpoint_id)
        
        assert str(test_file) not in metadata.file_snapshots
    
    def test_rollback_with_feedback(self, rollback_manager):
        """Test rollback with feedback generation."""
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint()
        
        # Rollback with simulated error
        with patch.object(rollback_manager, '_restore_files') as mock_restore:
            mock_restore.return_value = False
            result = rollback_manager.rollback(checkpoint_id)
            
            assert result.success is False
            assert len(result.errors) > 0
    
    def test_get_rollback_history(self, rollback_manager):
        """Test rollback history tracking."""
        # Create checkpoint and rollback
        checkpoint_id = rollback_manager.create_checkpoint()
        result = rollback_manager.rollback(checkpoint_id)
        
        history = rollback_manager.get_rollback_history()
        assert len(history) > 0
        assert history[0].checkpoint_id == checkpoint_id
    
    def test_validate_checkpoint(self, rollback_manager):
        """Test checkpoint validation."""
        checkpoint_id = rollback_manager.create_checkpoint()
        
        # Validate existing checkpoint
        is_valid = rollback_manager.validate_checkpoint(checkpoint_id)
        assert is_valid is True
        
        # Validate non-existent checkpoint
        is_valid = rollback_manager.validate_checkpoint("non_existent")
        assert is_valid is False
    
    def test_checkpoint_with_task_dependencies(self, rollback_manager):
        """Test checkpoint with task dependencies."""
        # Register tasks with dependencies
        rollback_manager.register_task("task1", {"status": "pending"})
        rollback_manager.register_task("task2", {"status": "pending"})
        rollback_manager.add_task_dependency("task2", "task1")
        
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint()
        
        # Verify dependencies are preserved
        checkpoint_path = rollback_manager.checkpoint_dir / checkpoint_id
        task_state_file = checkpoint_path / "task_state.pkl"
        
        with open(task_state_file, 'rb') as f:
            state = pickle.load(f)
            assert "task2" in state["task_dependencies"]
            assert "task1" in state["task_dependencies"]["task2"]
    
    def test_concurrent_checkpoint_creation(self, rollback_manager):
        """Test thread safety of checkpoint creation."""
        import threading
        
        checkpoint_ids = []
        
        def create_checkpoint(index):
            cp_id = rollback_manager.create_checkpoint(
                description=f"Concurrent checkpoint {index}"
            )
            checkpoint_ids.append(cp_id)
        
        # Create multiple checkpoints concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_checkpoint, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All checkpoints should be created successfully
        assert len(checkpoint_ids) == 5
        assert len(set(checkpoint_ids)) == 5  # All unique
    
    def test_rollback_nonexistent_checkpoint(self, rollback_manager):
        """Test rollback with non-existent checkpoint."""
        result = rollback_manager.rollback("non_existent_checkpoint")
        
        assert result.success is False
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()
    
    def test_checkpoint_auto_creation(self, rollback_manager):
        """Test automatic checkpoint creation."""
        # Enable auto checkpoint
        rollback_manager.auto_checkpoint = True
        
        # Simulate task completion which should trigger auto checkpoint
        rollback_manager.register_task("auto_task", {"status": "in_progress"})
        
        with patch.object(rollback_manager, 'create_checkpoint') as mock_create:
            rollback_manager.on_task_completion("auto_task")
            mock_create.assert_called_once()
    
    @pytest.mark.parametrize("checkpoint_type,expected_description", [
        (CheckpointType.MANUAL, "Manual checkpoint"),
        (CheckpointType.AUTOMATIC, "Automatic checkpoint"),
        (CheckpointType.TASK_COMPLETION, "Task completion checkpoint"),
        (CheckpointType.ERROR_RECOVERY, "Error recovery checkpoint"),
    ])
    def test_checkpoint_types(self, rollback_manager, checkpoint_type, expected_description):
        """Test different checkpoint types."""
        checkpoint_id = rollback_manager.create_checkpoint(
            checkpoint_type=checkpoint_type,
            description=expected_description
        )
        
        metadata = rollback_manager.get_checkpoint_metadata(checkpoint_id)
        assert metadata.checkpoint_type == checkpoint_type
        assert metadata.description == expected_description