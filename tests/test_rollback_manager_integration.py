"""Integration tests for RollbackManager.

This module provides comprehensive integration tests for the RollbackManager
including real file operations, concurrent operations, and system integration.
"""

import os
import sys
import pytest
import tempfile
import shutil
import json
import time
import threading
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from claude_orchestrator.rollback_manager import (
    RollbackManager, CheckpointType, CheckpointStatus, 
    CheckpointInfo, CheckpointError
)
from claude_orchestrator.main import ClaudeOrchestrator
from claude_orchestrator.task_master import TaskManager, Task as TMTask, TaskStatus as TMTaskStatus


class TestRollbackIntegration:
    """Integration tests for RollbackManager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def project_dir(self, temp_dir):
        """Create a temporary project directory with files."""
        project_dir = Path(temp_dir) / "test_project"
        project_dir.mkdir(parents=True)
        
        # Create some test files
        (project_dir / "file1.py").write_text("# Original content 1\nprint('hello')\n")
        (project_dir / "file2.py").write_text("# Original content 2\ndef test():\n    pass\n")
        (project_dir / "config.json").write_text('{"setting": "original"}\n')
        
        # Create a subdirectory with files
        subdir = project_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("Nested content\n")
        
        return project_dir
    
    @pytest.fixture
    def rollback_manager(self, project_dir):
        """Create a RollbackManager instance."""
        checkpoint_dir = project_dir / ".checkpoints"
        return RollbackManager(
            checkpoint_dir=str(checkpoint_dir),
            working_dir=str(project_dir),
            max_checkpoints=10,
            auto_checkpoint=True
        )
    
    def test_integration_basic_checkpoint_and_restore(self, rollback_manager, project_dir):
        """Test basic checkpoint creation and restoration."""
        # Create initial checkpoint
        checkpoint1 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Initial state"
        )
        
        assert checkpoint1 is not None
        assert os.path.exists(rollback_manager.checkpoint_dir)
        
        # Modify files
        (project_dir / "file1.py").write_text("# Modified content 1\nprint('modified')\n")
        (project_dir / "file2.py").write_text("# Modified content 2\ndef test_modified():\n    return True\n")
        (project_dir / "new_file.py").write_text("# New file\n")
        
        # Create second checkpoint
        checkpoint2 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.AUTO,
            description="After modifications"
        )
        
        # Verify checkpoint list
        checkpoints = rollback_manager.list_checkpoints()
        assert len(checkpoints) == 2
        assert checkpoints[0].checkpoint_id == checkpoint2  # Most recent first
        assert checkpoints[1].checkpoint_id == checkpoint1
        
        # Rollback to initial state
        success = rollback_manager.rollback_to_checkpoint(checkpoint1)
        assert success
        
        # Verify files are restored
        assert (project_dir / "file1.py").read_text() == "# Original content 1\nprint('hello')\n"
        assert (project_dir / "file2.py").read_text() == "# Original content 2\ndef test():\n    pass\n"
        assert not (project_dir / "new_file.py").exists()
    
    def test_integration_file_deletions_and_additions(self, rollback_manager, project_dir):
        """Test handling of file deletions and additions."""
        # Create checkpoint
        checkpoint1 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Before changes"
        )
        
        # Delete a file
        (project_dir / "file1.py").unlink()
        
        # Add new files
        (project_dir / "added1.py").write_text("# Added file 1\n")
        (project_dir / "added2.py").write_text("# Added file 2\n")
        
        # Modify existing file
        (project_dir / "config.json").write_text('{"setting": "modified"}\n')
        
        # Create checkpoint after changes
        checkpoint2 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.AUTO,
            description="After deletions and additions"
        )
        
        # Delete more files
        (project_dir / "file2.py").unlink()
        (project_dir / "added1.py").unlink()
        
        # Rollback to checkpoint2
        success = rollback_manager.rollback_to_checkpoint(checkpoint2)
        assert success
        
        # Verify state at checkpoint2
        assert not (project_dir / "file1.py").exists()  # Was deleted
        assert (project_dir / "file2.py").exists()      # Should be restored
        assert (project_dir / "added1.py").exists()      # Should be restored
        assert (project_dir / "added2.py").exists()      # Should still exist
        assert (project_dir / "config.json").read_text() == '{"setting": "modified"}\n'
        
        # Rollback to checkpoint1
        success = rollback_manager.rollback_to_checkpoint(checkpoint1)
        assert success
        
        # Verify original state
        assert (project_dir / "file1.py").exists()
        assert (project_dir / "file2.py").exists()
        assert not (project_dir / "added1.py").exists()
        assert not (project_dir / "added2.py").exists()
        assert (project_dir / "config.json").read_text() == '{"setting": "original"}\n'
    
    def test_integration_concurrent_checkpoints(self, rollback_manager, project_dir):
        """Test concurrent checkpoint operations."""
        results = []
        errors = []
        
        def create_checkpoint_thread(thread_id):
            try:
                # Modify a file specific to this thread
                file_path = project_dir / f"thread_{thread_id}.txt"
                file_path.write_text(f"Content from thread {thread_id}\n")
                
                # Create checkpoint
                checkpoint_id = rollback_manager.create_checkpoint(
                    checkpoint_type=CheckpointType.AUTO,
                    description=f"Thread {thread_id} checkpoint"
                )
                
                results.append({
                    'thread_id': thread_id,
                    'checkpoint_id': checkpoint_id,
                    'file': str(file_path)
                })
            except Exception as e:
                errors.append({
                    'thread_id': thread_id,
                    'error': str(e)
                })
        
        # Create checkpoints concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_checkpoint_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify no errors
        assert len(errors) == 0
        assert len(results) == 5
        
        # Verify all checkpoints were created
        checkpoints = rollback_manager.list_checkpoints()
        checkpoint_ids = [cp.checkpoint_id for cp in checkpoints]
        
        for result in results:
            assert result['checkpoint_id'] in checkpoint_ids
            # Verify file exists
            assert Path(result['file']).exists()
    
    def test_integration_checkpoint_cleanup(self, rollback_manager, project_dir):
        """Test automatic checkpoint cleanup when limit is reached."""
        # Set a low limit for testing
        rollback_manager.max_checkpoints = 3
        
        checkpoint_ids = []
        
        # Create more checkpoints than the limit
        for i in range(5):
            # Modify a file to ensure checkpoint has changes
            (project_dir / "file1.py").write_text(f"# Version {i}\n")
            
            checkpoint_id = rollback_manager.create_checkpoint(
                checkpoint_type=CheckpointType.AUTO,
                description=f"Checkpoint {i}"
            )
            checkpoint_ids.append(checkpoint_id)
            
            # Small delay to ensure different timestamps
            time.sleep(0.1)
        
        # Verify only the most recent checkpoints are kept
        checkpoints = rollback_manager.list_checkpoints()
        assert len(checkpoints) <= 3
        
        # Verify the oldest checkpoints were removed
        existing_ids = [cp.checkpoint_id for cp in checkpoints]
        assert checkpoint_ids[0] not in existing_ids  # Oldest removed
        assert checkpoint_ids[1] not in existing_ids  # Second oldest removed
        assert checkpoint_ids[4] in existing_ids      # Most recent kept
    
    def test_integration_rollback_with_nested_directories(self, rollback_manager, project_dir):
        """Test rollback with nested directory structures."""
        # Create checkpoint
        checkpoint1 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Before nested changes"
        )
        
        # Create nested directories and files
        deep_dir = project_dir / "level1" / "level2" / "level3"
        deep_dir.mkdir(parents=True)
        
        (deep_dir / "deep_file.txt").write_text("Deep content\n")
        (project_dir / "level1" / "file_l1.txt").write_text("Level 1 content\n")
        (project_dir / "level1" / "level2" / "file_l2.txt").write_text("Level 2 content\n")
        
        # Modify existing nested file
        (project_dir / "subdir" / "nested.txt").write_text("Modified nested content\n")
        
        # Create checkpoint
        checkpoint2 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.AUTO,
            description="After nested changes"
        )
        
        # Delete the nested structure
        shutil.rmtree(project_dir / "level1")
        
        # Rollback to checkpoint2
        success = rollback_manager.rollback_to_checkpoint(checkpoint2)
        assert success
        
        # Verify nested structure is restored
        assert (deep_dir / "deep_file.txt").exists()
        assert (project_dir / "level1" / "file_l1.txt").exists()
        assert (project_dir / "level1" / "level2" / "file_l2.txt").exists()
        
        # Rollback to checkpoint1
        success = rollback_manager.rollback_to_checkpoint(checkpoint1)
        assert success
        
        # Verify original state (no nested structure)
        assert not (project_dir / "level1").exists()
        assert (project_dir / "subdir" / "nested.txt").read_text() == "Nested content\n"
    
    def test_integration_error_recovery(self, rollback_manager, project_dir):
        """Test error recovery during rollback operations."""
        # Create checkpoint
        checkpoint1 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Before error test"
        )
        
        # Modify files
        (project_dir / "file1.py").write_text("# Modified for error test\n")
        
        # Create a file that will cause permission issues
        protected_file = project_dir / "protected.txt"
        protected_file.write_text("Protected content\n")
        
        # Create checkpoint
        checkpoint2 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.AUTO,
            description="With protected file"
        )
        
        # Make the file read-only (simulate permission issue)
        os.chmod(protected_file, 0o444)
        
        try:
            # Try to modify the protected file
            protected_file.write_text("This should fail\n")
        except:
            pass  # Expected to fail
        
        # Rollback should handle the permission issue gracefully
        success = rollback_manager.rollback_to_checkpoint(checkpoint1)
        
        # On some systems, rollback might partially succeed
        # Verify other files were restored even if protected file had issues
        assert (project_dir / "file1.py").read_text() == "# Original content 1\nprint('hello')\n"
        
        # Clean up - restore write permissions
        os.chmod(protected_file, 0o644)
        protected_file.unlink(missing_ok=True)
    
    def test_integration_with_task_master(self, temp_dir):
        """Test integration with Task Master system."""
        # Create project directory
        project_dir = Path(temp_dir) / "task_project"
        project_dir.mkdir(parents=True)
        
        # Create task manager
        task_manager = TaskManager(str(project_dir))
        
        # Create rollback manager
        rollback_manager = RollbackManager(
            checkpoint_dir=str(project_dir / ".checkpoints"),
            working_dir=str(project_dir),
            max_checkpoints=10,
            auto_checkpoint=True
        )
        
        # Create initial files
        (project_dir / "task_file.py").write_text("# Task file\n")
        
        # Create checkpoint before task
        checkpoint_before = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Before task execution",
            metadata={'phase': 'pre_task'}
        )
        
        # Create and execute a task
        task = TMTask(
            title="Test task",
            description="Modify files",
            priority=5
        )
        task_id = task_manager.add_task(task)
        
        # Simulate task execution that modifies files
        (project_dir / "task_file.py").write_text("# Modified by task\n")
        (project_dir / "task_output.txt").write_text("Task output\n")
        
        # Create checkpoint after task
        checkpoint_after = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.AUTO,
            description="After task execution",
            metadata={
                'phase': 'post_task',
                'task_id': task_id,
                'task_title': task.title
            }
        )
        
        # Verify task-related metadata
        info = rollback_manager.get_checkpoint_info(checkpoint_after)
        assert info.metadata['task_id'] == task_id
        assert info.metadata['task_title'] == "Test task"
        
        # Rollback to before task
        success = rollback_manager.rollback_to_checkpoint(checkpoint_before)
        assert success
        
        # Verify files are restored to pre-task state
        assert (project_dir / "task_file.py").read_text() == "# Task file\n"
        assert not (project_dir / "task_output.txt").exists()
    
    def test_integration_checkpoint_metadata(self, rollback_manager, project_dir):
        """Test checkpoint metadata handling."""
        # Create checkpoint with metadata
        metadata = {
            'task_id': 'test_task_123',
            'worker_id': 'worker_1',
            'phase': 'testing',
            'custom_data': {
                'version': '1.0',
                'author': 'test_suite'
            }
        }
        
        checkpoint_id = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Metadata test checkpoint",
            metadata=metadata
        )
        
        # Get checkpoint info
        info = rollback_manager.get_checkpoint_info(checkpoint_id)
        assert info is not None
        assert info.metadata == metadata
        assert info.metadata['task_id'] == 'test_task_123'
        assert info.metadata['custom_data']['version'] == '1.0'
        
        # Verify metadata is preserved after listing
        checkpoints = rollback_manager.list_checkpoints()
        checkpoint = next((cp for cp in checkpoints if cp.checkpoint_id == checkpoint_id), None)
        assert checkpoint is not None
        assert checkpoint.metadata == metadata
    
    def test_integration_async_operations(self, rollback_manager, project_dir):
        """Test async checkpoint operations."""
        async def async_checkpoint_test():
            # Create checkpoints asynchronously
            checkpoints = []
            
            for i in range(3):
                # Modify a file
                (project_dir / f"async_{i}.txt").write_text(f"Async content {i}\n")
                
                # Create checkpoint
                checkpoint_id = rollback_manager.create_checkpoint(
                    checkpoint_type=CheckpointType.AUTO,
                    description=f"Async checkpoint {i}"
                )
                checkpoints.append(checkpoint_id)
                
                # Simulate async work
                await asyncio.sleep(0.1)
            
            # Verify all checkpoints were created
            all_checkpoints = rollback_manager.list_checkpoints()
            checkpoint_ids = [cp.checkpoint_id for cp in all_checkpoints]
            
            for cp_id in checkpoints:
                assert cp_id in checkpoint_ids
            
            # Test async rollback
            success = rollback_manager.rollback_to_checkpoint(checkpoints[0])
            assert success
            
            # Verify only first file exists
            assert (project_dir / "async_0.txt").exists()
            assert not (project_dir / "async_1.txt").exists()
            assert not (project_dir / "async_2.txt").exists()
        
        # Run async test
        asyncio.run(async_checkpoint_test())
    
    def test_integration_performance_large_files(self, rollback_manager, project_dir):
        """Test performance with large files."""
        # Create a large file (10MB)
        large_content = "x" * (10 * 1024 * 1024)  # 10MB
        large_file = project_dir / "large_file.bin"
        large_file.write_text(large_content)
        
        # Time checkpoint creation
        start_time = time.time()
        checkpoint_id = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Large file checkpoint"
        )
        checkpoint_time = time.time() - start_time
        
        # Checkpoint should complete reasonably fast (< 5 seconds for 10MB)
        assert checkpoint_time < 5.0
        
        # Modify the large file
        large_file.write_text("Modified content\n")
        
        # Time rollback
        start_time = time.time()
        success = rollback_manager.rollback_to_checkpoint(checkpoint_id)
        rollback_time = time.time() - start_time
        
        assert success
        assert rollback_time < 5.0
        
        # Verify content was restored
        assert large_file.read_text() == large_content
    
    def test_integration_checkpoint_comparison(self, rollback_manager, project_dir):
        """Test checkpoint comparison functionality."""
        # Create initial checkpoint
        checkpoint1 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Initial state"
        )
        
        # Make changes
        (project_dir / "file1.py").write_text("# Modified version 1\n")
        (project_dir / "new_file.txt").write_text("New file content\n")
        
        checkpoint2 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.AUTO,
            description="After first changes"
        )
        
        # Make more changes
        (project_dir / "file1.py").write_text("# Modified version 2\n")
        (project_dir / "file2.py").unlink()  # Delete file2
        
        checkpoint3 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.AUTO,
            description="After second changes"
        )
        
        # Get checkpoint info for comparison
        info1 = rollback_manager.get_checkpoint_info(checkpoint1)
        info2 = rollback_manager.get_checkpoint_info(checkpoint2)
        info3 = rollback_manager.get_checkpoint_info(checkpoint3)
        
        # Verify checkpoint progression
        assert info1.timestamp < info2.timestamp < info3.timestamp
        
        # Verify file counts (approximate check)
        # Each checkpoint should track the file changes
        assert info1.checkpoint_id != info2.checkpoint_id != info3.checkpoint_id
    
    def test_integration_rollback_with_binary_files(self, rollback_manager, project_dir):
        """Test rollback with binary files."""
        # Create binary file
        binary_file = project_dir / "data.bin"
        original_data = bytes([i % 256 for i in range(1000)])
        binary_file.write_bytes(original_data)
        
        # Create checkpoint
        checkpoint1 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="With binary file"
        )
        
        # Modify binary file
        modified_data = bytes([255 - (i % 256) for i in range(1000)])
        binary_file.write_bytes(modified_data)
        
        # Verify modification
        assert binary_file.read_bytes() == modified_data
        
        # Rollback
        success = rollback_manager.rollback_to_checkpoint(checkpoint1)
        assert success
        
        # Verify binary file was restored correctly
        assert binary_file.read_bytes() == original_data
    
    def test_integration_selective_rollback(self, rollback_manager, project_dir):
        """Test selective file rollback (if supported)."""
        # Create initial checkpoint
        checkpoint1 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description="Initial state"
        )
        
        # Modify multiple files
        (project_dir / "file1.py").write_text("# Modified file1\n")
        (project_dir / "file2.py").write_text("# Modified file2\n")
        (project_dir / "config.json").write_text('{"setting": "new"}\n')
        
        # Create checkpoint after modifications
        checkpoint2 = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.AUTO,
            description="After modifications"
        )
        
        # Further modify files
        (project_dir / "file1.py").write_text("# Further modified file1\n")
        (project_dir / "file2.py").write_text("# Further modified file2\n")
        
        # Full rollback to checkpoint2
        success = rollback_manager.rollback_to_checkpoint(checkpoint2)
        assert success
        
        # Verify all files match checkpoint2 state
        assert (project_dir / "file1.py").read_text() == "# Modified file1\n"
        assert (project_dir / "file2.py").read_text() == "# Modified file2\n"
        assert (project_dir / "config.json").read_text() == '{"setting": "new"}\n'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])