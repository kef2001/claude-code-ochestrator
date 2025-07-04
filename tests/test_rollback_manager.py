"""Comprehensive unit tests for RollbackManager."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import time
from unittest.mock import patch, MagicMock

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
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def rollback_manager(self, temp_dir):
        """Create RollbackManager instance."""
        checkpoint_dir = Path(temp_dir) / "checkpoints"
        return RollbackManager(
            checkpoint_dir=str(checkpoint_dir),
            max_checkpoints=5,
            auto_checkpoint=False
        )
    
    @pytest.fixture
    def sample_files(self, temp_dir):
        """Create sample files for testing."""
        files = []
        
        # Create test files
        for i in range(3):
            file_path = Path(temp_dir) / f"test_file_{i}.txt"
            file_path.write_text(f"Original content {i}")
            files.append(str(file_path))
        
        # Create test directory
        test_dir = Path(temp_dir) / "test_dir"
        test_dir.mkdir()
        (test_dir / "nested.txt").write_text("Nested content")
        files.append(str(test_dir))
        
        return files
    
    def test_initialization(self, rollback_manager):
        """Test RollbackManager initialization."""
        assert rollback_manager.checkpoint_dir.exists()
        assert rollback_manager.max_checkpoints == 5
        assert not rollback_manager.auto_checkpoint
        assert rollback_manager._metadata_file.exists()
    
    def test_create_checkpoint(self, rollback_manager, sample_files):
        """Test checkpoint creation."""
        # Track files
        for file_path in sample_files:
            rollback_manager.track_file(file_path)
        
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Test checkpoint"
        )
        
        assert checkpoint_id.startswith("cp_")
        assert (rollback_manager.checkpoint_dir / checkpoint_id).exists()
        
        # Verify metadata
        metadata = rollback_manager.get_checkpoint(checkpoint_id)
        assert metadata is not None
        assert metadata.checkpoint_type == CheckpointType.MANUAL
        assert metadata.description == "Test checkpoint"
        assert len(metadata.file_snapshots) == len(sample_files)
    
    def test_rollback_full(self, rollback_manager, sample_files, temp_dir):
        """Test full rollback strategy."""
        # Track and modify files
        for file_path in sample_files[:3]:  # Only text files
            rollback_manager.track_file(file_path)
        
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint()
        
        # Modify files
        for i, file_path in enumerate(sample_files[:3]):
            Path(file_path).write_text(f"Modified content {i}")
        
        # Perform rollback
        result = rollback_manager.rollback(
            checkpoint_id,
            strategy=RollbackStrategy.FULL
        )
        
        assert result.success
        assert len(result.restored_files) == 3
        
        # Verify files restored
        for i, file_path in enumerate(sample_files[:3]):
            content = Path(file_path).read_text()
            assert content == f"Original content {i}"
    
    def test_rollback_partial(self, rollback_manager):
        """Test partial rollback strategy."""
        # Set up tasks
        rollback_manager.update_task_state("task1", {"status": "completed"})
        rollback_manager.update_task_state("task2", {"status": "in_progress"})
        rollback_manager.set_task_dependency("task2", ["task1"])
        
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint()
        
        # Modify task states
        rollback_manager.update_task_state("task1", {"status": "failed"})
        rollback_manager.update_task_state("task2", {"status": "failed"})
        
        # Perform partial rollback
        result = rollback_manager.rollback(
            checkpoint_id,
            strategy=RollbackStrategy.PARTIAL
        )
        
        assert result.success
        assert len(result.rolled_back_tasks) > 0
    
    def test_rollback_selective(self, rollback_manager):
        """Test selective rollback strategy."""
        # Set up tasks
        rollback_manager.update_task_state("task1", {"status": "completed"})
        rollback_manager.update_task_state("task2", {"status": "completed"})
        rollback_manager.update_task_state("task3", {"status": "completed"})
        
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint()
        
        # Modify task states
        rollback_manager.update_task_state("task1", {"status": "failed"})
        rollback_manager.update_task_state("task2", {"status": "failed"})
        rollback_manager.update_task_state("task3", {"status": "failed"})
        
        # Perform selective rollback
        result = rollback_manager.rollback(
            checkpoint_id,
            strategy=RollbackStrategy.SELECTIVE,
            target_tasks=["task2"]
        )
        
        assert result.success
        assert "task2" in result.rolled_back_tasks
    
    def test_checkpoint_metadata(self, rollback_manager):
        """Test checkpoint metadata operations."""
        # Create multiple checkpoints
        checkpoint_ids = []
        for i in range(3):
            time.sleep(0.01)  # Ensure different timestamps
            checkpoint_id = rollback_manager.create_checkpoint(
                description=f"Checkpoint {i}"
            )
            checkpoint_ids.append(checkpoint_id)
        
        # List checkpoints
        checkpoints = rollback_manager.list_checkpoints()
        assert len(checkpoints) == 3
        assert checkpoints[0].checkpoint_id == checkpoint_ids[-1]  # Newest first
        
        # Get specific checkpoint
        checkpoint = rollback_manager.get_checkpoint(checkpoint_ids[0])
        assert checkpoint is not None
        assert checkpoint.description == "Checkpoint 0"
    
    def test_checkpoint_cleanup(self, rollback_manager):
        """Test automatic checkpoint cleanup."""
        # Create more than max checkpoints
        checkpoint_ids = []
        for i in range(7):
            time.sleep(0.01)
            checkpoint_id = rollback_manager.create_checkpoint()
            checkpoint_ids.append(checkpoint_id)
        
        # Verify only max_checkpoints remain
        checkpoints = rollback_manager.list_checkpoints()
        assert len(checkpoints) == rollback_manager.max_checkpoints
        
        # Verify oldest were removed
        remaining_ids = [cp.checkpoint_id for cp in checkpoints]
        assert checkpoint_ids[0] not in remaining_ids
        assert checkpoint_ids[1] not in remaining_ids
    
    def test_file_tracking(self, rollback_manager, temp_dir):
        """Test file tracking operations."""
        file1 = Path(temp_dir) / "file1.txt"
        file2 = Path(temp_dir) / "file2.txt"
        file1.write_text("Content 1")
        file2.write_text("Content 2")
        
        # Track files
        rollback_manager.track_file(str(file1))
        rollback_manager.track_file(str(file2))
        
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint()
        metadata = rollback_manager.get_checkpoint(checkpoint_id)
        
        assert len(metadata.file_snapshots) == 2
        
        # Untrack one file
        rollback_manager.untrack_file(str(file2))
        
        # Create another checkpoint
        checkpoint_id2 = rollback_manager.create_checkpoint()
        metadata2 = rollback_manager.get_checkpoint(checkpoint_id2)
        
        assert len(metadata2.file_snapshots) == 1
    
    def test_task_dependencies(self, rollback_manager):
        """Test task dependency handling."""
        # Set up task graph
        rollback_manager.set_task_dependency("task1", [])
        rollback_manager.set_task_dependency("task2", ["task1"])
        rollback_manager.set_task_dependency("task3", ["task1"])
        rollback_manager.set_task_dependency("task4", ["task2", "task3"])
        
        # Get recursive dependencies
        deps = rollback_manager._get_task_dependencies_recursive(["task4"])
        
        assert len(deps) == 4
        assert all(f"task{i}" in deps for i in range(1, 5))
    
    def test_rollback_history(self, rollback_manager):
        """Test rollback history tracking."""
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint()
        
        # Perform multiple rollbacks
        for strategy in [RollbackStrategy.FULL, RollbackStrategy.PARTIAL]:
            rollback_manager.rollback(checkpoint_id, strategy=strategy)
        
        # Check history
        history = rollback_manager.get_rollback_history()
        assert len(history) == 2
        assert history[0].strategy == RollbackStrategy.FULL
        assert history[1].strategy == RollbackStrategy.PARTIAL
    
    def test_can_rollback_to(self, rollback_manager):
        """Test rollback possibility check."""
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint()
        assert rollback_manager.can_rollback_to(checkpoint_id)
        
        # Delete checkpoint
        rollback_manager.delete_checkpoint(checkpoint_id)
        assert not rollback_manager.can_rollback_to(checkpoint_id)
        
        # Non-existent checkpoint
        assert not rollback_manager.can_rollback_to("nonexistent")
    
    def test_auto_checkpoint(self, temp_dir):
        """Test automatic checkpointing."""
        checkpoint_dir = Path(temp_dir) / "auto_checkpoints"
        manager = RollbackManager(
            checkpoint_dir=str(checkpoint_dir),
            auto_checkpoint=True
        )
        
        # Update task to completed
        manager.update_task_state("task1", {"status": "in_progress"})
        checkpoints_before = len(manager.list_checkpoints())
        
        manager.update_task_state("task1", {"status": "completed"})
        checkpoints_after = len(manager.list_checkpoints())
        
        assert checkpoints_after == checkpoints_before + 1
    
    def test_export_import_checkpoint(self, rollback_manager, temp_dir):
        """Test checkpoint export and import."""
        # Create checkpoint
        checkpoint_id = rollback_manager.create_checkpoint(
            description="Export test"
        )
        
        # Export checkpoint
        export_path = Path(temp_dir) / "exported_checkpoint"
        success = rollback_manager.export_checkpoint(
            checkpoint_id,
            str(export_path)
        )
        assert success
        assert Path(f"{export_path}.zip").exists()
        
        # Import checkpoint
        imported_id = rollback_manager.import_checkpoint(
            f"{export_path}.zip"
        )
        assert imported_id is not None
        assert imported_id.startswith("imported_")
    
    def test_rollback_with_errors(self, rollback_manager):
        """Test rollback error handling."""
        # Rollback to non-existent checkpoint
        result = rollback_manager.rollback("nonexistent")
        assert not result.success
        assert len(result.errors) > 0
        
        # Create checkpoint and delete directory
        checkpoint_id = rollback_manager.create_checkpoint()
        checkpoint_path = rollback_manager.checkpoint_dir / checkpoint_id
        shutil.rmtree(checkpoint_path)
        
        # Try to rollback
        result = rollback_manager.rollback(checkpoint_id)
        assert not result.success
    
    def test_checkpoint_metadata_serialization(self):
        """Test CheckpointMetadata serialization."""
        metadata = CheckpointMetadata(
            checkpoint_id="test_id",
            timestamp=datetime.now(),
            checkpoint_type=CheckpointType.MANUAL,
            description="Test",
            task_states={"task1": "completed"},
            file_snapshots=["file1.txt"],
            custom_data={"key": "value"},
            parent_checkpoint="parent_id"
        )
        
        # To dict
        data = metadata.to_dict()
        assert data["checkpoint_id"] == "test_id"
        assert "timestamp" in data
        
        # From dict
        restored = CheckpointMetadata.from_dict(data)
        assert restored.checkpoint_id == metadata.checkpoint_id
        assert restored.checkpoint_type == metadata.checkpoint_type
    
    def test_rollback_result_serialization(self):
        """Test RollbackResult serialization."""
        result = RollbackResult(
            success=True,
            checkpoint_id="test_id",
            strategy=RollbackStrategy.FULL,
            rolled_back_tasks=["task1", "task2"],
            restored_files=["file1.txt"],
            errors=[],
            duration_seconds=1.5
        )
        
        data = result.to_dict()
        assert data["success"] is True
        assert data["strategy"] == "full"
        assert len(data["rolled_back_tasks"]) == 2
    
    def test_concurrent_operations(self, rollback_manager):
        """Test thread safety of concurrent operations."""
        import threading
        
        results = []
        
        def create_checkpoint(index):
            checkpoint_id = rollback_manager.create_checkpoint(
                description=f"Concurrent {index}"
            )
            results.append(checkpoint_id)
        
        # Create multiple checkpoints concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_checkpoint, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all checkpoints created
        assert len(results) == 5
        assert len(set(results)) == 5  # All unique
    
    def test_file_backup_on_restore(self, rollback_manager, temp_dir):
        """Test that files are backed up before restore."""
        file_path = Path(temp_dir) / "test.txt"
        file_path.write_text("Original")
        
        rollback_manager.track_file(str(file_path))
        checkpoint_id = rollback_manager.create_checkpoint()
        
        # Modify file
        file_path.write_text("Modified")
        
        # Rollback
        rollback_manager.rollback(checkpoint_id)
        
        # Check backup exists
        backup_path = file_path.with_suffix(".txt.rollback_backup")
        assert backup_path.exists()
        assert backup_path.read_text() == "Modified"
    
    def test_large_file_handling(self, rollback_manager, temp_dir):
        """Test handling of large files."""
        # Create a large file (1MB)
        large_file = Path(temp_dir) / "large.bin"
        large_file.write_bytes(b"x" * 1024 * 1024)
        
        rollback_manager.track_file(str(large_file))
        
        # Time checkpoint creation
        start = time.time()
        checkpoint_id = rollback_manager.create_checkpoint()
        duration = time.time() - start
        
        # Should complete reasonably fast
        assert duration < 5.0
        
        # Verify snapshot
        metadata = rollback_manager.get_checkpoint(checkpoint_id)
        assert str(large_file) in metadata.file_snapshots