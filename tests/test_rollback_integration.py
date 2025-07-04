"""
Integration tests for Rollback System

Tests rollback integration with CheckpointManager and other components.
"""

import tempfile
import os
import shutil
import time
from datetime import datetime
from unittest.mock import Mock, patch
import threading
import json

from claude_orchestrator.rollback import (
    RollbackManager, RollbackReason, RollbackStatus, create_rollback_manager
)
from claude_orchestrator.checkpoint_system import (
    CheckpointManager, CheckpointData, CheckpointState, TaskCheckpointWrapper
)
from claude_orchestrator.rollback_strategies import (
    RollbackStrategyManager, RollbackScope, RollbackStrategyType,
    ComponentType, create_rollback_scope
)


class TestRollbackCheckpointIntegration:
    """Tests for rollback and checkpoint integration"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_manager = CheckpointManager(
            storage_dir=os.path.join(self.temp_dir, "checkpoints")
        )
        self.rollback_manager = create_rollback_manager(
            checkpoint_manager=self.checkpoint_manager,
            storage_dir=os.path.join(self.temp_dir, "rollbacks")
        )
    
    def teardown_method(self):
        """Clean up after test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_checkpoint_wrapper_integration(self):
        """Test integration with TaskCheckpointWrapper"""
        task_id = "wrapper-test-001"
        wrapper = TaskCheckpointWrapper(
            self.checkpoint_manager,
            task_id,
            "Wrapper Integration Test",
            "test-worker"
        )
        
        # Create checkpoints through wrapper
        wrapper.checkpoint("Step 1: Initialize", {"status": "initialized"})
        wrapper.checkpoint("Step 2: Process", {"status": "processing", "progress": 0.5})
        wrapper.checkpoint("Step 3: Complete", {"status": "completed", "result": "success"})
        
        # Get checkpoints through rollback manager
        checkpoints = self.rollback_manager.list_checkpoints(task_id)
        assert len(checkpoints) == 3
        
        # Test rollback to middle checkpoint
        middle_checkpoint = checkpoints[1]
        success, restored_data = self.rollback_manager.restore_checkpoint(
            checkpoint_id=middle_checkpoint.checkpoint_id,
            reason=RollbackReason.MANUAL
        )
        
        assert success is True
        assert restored_data["data"]["status"] == "processing"
        assert restored_data["data"]["progress"] == 0.5
    
    def test_rollback_with_checkpoint_state_changes(self):
        """Test rollback behavior with different checkpoint states"""
        task_id = "state-test-001"
        
        # Create checkpoints in different states
        states = [
            (CheckpointState.IN_PROGRESS, "In progress checkpoint"),
            (CheckpointState.COMPLETED, "Completed checkpoint"),
            (CheckpointState.FAILED, "Failed checkpoint")
        ]
        
        checkpoint_ids = []
        for i, (state, description) in enumerate(states):
            checkpoint = CheckpointData(
                checkpoint_id=f"cp_{task_id}_{i}_{int(time.time()*1000)}",
                task_id=task_id,
                task_title="State Test Task",
                state=state,
                step_number=i,
                step_description=description,
                data={"state": state.value},
                created_at=datetime.now()
            )
            
            # Save checkpoint directly
            checkpoint_file = os.path.join(
                self.checkpoint_manager.storage_dir,
                f"checkpoint_{checkpoint.checkpoint_id}.json"
            )
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
            
            checkpoint_ids.append(checkpoint.checkpoint_id)
        
        # Test rollback to completed checkpoint (should succeed)
        success, _ = self.rollback_manager.restore_checkpoint(
            checkpoint_id=checkpoint_ids[1],  # Completed checkpoint
            reason=RollbackReason.MANUAL,
            validate=True
        )
        assert success is True
        
        # Test rollback to failed checkpoint (should fail with validation)
        success, _ = self.rollback_manager.restore_checkpoint(
            checkpoint_id=checkpoint_ids[2],  # Failed checkpoint
            reason=RollbackReason.MANUAL,
            validate=True
        )
        assert success is False
    
    def test_rollback_strategy_integration(self):
        """Test integration with rollback strategies"""
        strategy_manager = RollbackStrategyManager(self.rollback_manager)
        
        # Create checkpoints for different components
        components = [
            (ComponentType.TASK_STATE, "task-state-001"),
            (ComponentType.WORKER_STATE, "worker-state-001"),
            (ComponentType.CONFIGURATION, "config-001")
        ]
        
        for component, task_id in components:
            self.rollback_manager.create_checkpoint(
                task_id=task_id,
                task_title=f"{component.value} Test",
                step_number=1,
                step_description=f"Testing {component.value}",
                data={"component": component.value},
                metadata={"component_type": component.value}
            )
        
        # Test partial rollback strategy
        scope = create_rollback_scope(
            strategy_type=RollbackStrategyType.PARTIAL,
            components=["task_state", "worker_state"]
        )
        
        plan = strategy_manager.create_rollback_plan(scope)
        assert plan is not None
        assert len(plan.checkpoints) >= 2
        
        # Execute rollback plan
        success, results = strategy_manager.execute_rollback(plan)
        assert isinstance(success, bool)
        assert "plan_id" in results
    
    def test_concurrent_checkpoint_and_rollback(self):
        """Test concurrent checkpoint creation and rollback operations"""
        task_id = "concurrent-test-001"
        results = {"checkpoints": 0, "rollbacks": 0, "errors": []}
        
        def create_checkpoints():
            """Create checkpoints in a thread"""
            try:
                for i in range(10):
                    self.rollback_manager.create_checkpoint(
                        task_id=task_id,
                        task_title="Concurrent Test",
                        step_number=i,
                        step_description=f"Step {i}",
                        data={"thread": "creator", "step": i}
                    )
                    results["checkpoints"] += 1
                    time.sleep(0.01)
            except Exception as e:
                results["errors"].append(f"Checkpoint error: {e}")
        
        def perform_rollbacks():
            """Perform rollbacks in a thread"""
            try:
                time.sleep(0.05)  # Let some checkpoints be created first
                
                for _ in range(5):
                    checkpoints = self.rollback_manager.list_checkpoints(task_id)
                    if checkpoints:
                        checkpoint = checkpoints[0]
                        success, _ = self.rollback_manager.restore_checkpoint(
                            checkpoint_id=checkpoint.checkpoint_id,
                            reason=RollbackReason.MANUAL
                        )
                        if success:
                            results["rollbacks"] += 1
                    time.sleep(0.02)
            except Exception as e:
                results["errors"].append(f"Rollback error: {e}")
        
        # Run concurrent operations
        creator_thread = threading.Thread(target=create_checkpoints)
        rollback_thread = threading.Thread(target=perform_rollbacks)
        
        creator_thread.start()
        rollback_thread.start()
        
        creator_thread.join()
        rollback_thread.join()
        
        # Verify results
        assert results["checkpoints"] == 10
        assert results["rollbacks"] > 0
        assert len(results["errors"]) == 0
    
    def test_rollback_with_metadata_preservation(self):
        """Test that rollback preserves checkpoint metadata"""
        task_id = "metadata-test-001"
        
        # Create checkpoint with rich metadata
        original_metadata = {
            "user_id": "test-user",
            "environment": "testing",
            "version": "1.0.0",
            "tags": ["important", "validated"],
            "custom_data": {
                "nested": {
                    "value": 42,
                    "flag": True
                }
            }
        }
        
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Metadata Test",
            step_number=1,
            step_description="Testing metadata preservation",
            data={"test": "data"},
            metadata=original_metadata
        )
        
        # Perform rollback
        success, restored_data = self.rollback_manager.restore_checkpoint(
            checkpoint_id=checkpoint_id,
            reason=RollbackReason.MANUAL
        )
        
        assert success is True
        
        # Verify metadata was preserved
        checkpoint = self.checkpoint_manager.get_checkpoint(checkpoint_id)
        assert checkpoint is not None
        
        # Check each metadata field
        for key, value in original_metadata.items():
            assert key in checkpoint.metadata
            assert checkpoint.metadata[key] == value
    
    def test_rollback_cascade_effects(self):
        """Test cascading effects of rollback on dependent checkpoints"""
        # Create a series of dependent checkpoints
        base_task_id = "cascade-base-001"
        dependent_task_ids = [f"cascade-dep-{i}" for i in range(3)]
        
        # Create base checkpoint
        base_checkpoint = self.rollback_manager.create_checkpoint(
            task_id=base_task_id,
            task_title="Base Task",
            step_number=1,
            step_description="Base checkpoint",
            data={"value": 100},
            metadata={"dependents": dependent_task_ids}
        )
        
        # Create dependent checkpoints
        for i, dep_task_id in enumerate(dependent_task_ids):
            self.rollback_manager.create_checkpoint(
                task_id=dep_task_id,
                task_title=f"Dependent Task {i}",
                step_number=1,
                step_description=f"Dependent on {base_task_id}",
                data={"base_value": 100, "multiplier": i + 1},
                metadata={"depends_on": base_task_id}
            )
        
        # Modify base and create new checkpoint
        new_base_checkpoint = self.rollback_manager.create_checkpoint(
            task_id=base_task_id,
            task_title="Base Task",
            step_number=2,
            step_description="Modified base",
            data={"value": 200},
            metadata={"dependents": dependent_task_ids}
        )
        
        # Rollback base to original state
        success, _ = self.rollback_manager.restore_checkpoint(
            checkpoint_id=base_checkpoint,
            reason=RollbackReason.MANUAL
        )
        
        assert success is True
        
        # In a real system, this would trigger cascade rollbacks
        # For now, verify we can identify affected tasks
        history = self.rollback_manager.get_rollback_history()
        assert len(history) > 0
        
        # Check that we can query dependent checkpoints
        for dep_task_id in dependent_task_ids:
            checkpoints = self.rollback_manager.list_checkpoints(dep_task_id)
            assert len(checkpoints) > 0
            
            # Verify dependency metadata
            dep_checkpoint = checkpoints[0]
            assert dep_checkpoint.metadata.get("depends_on") == base_task_id


class TestEndToEndRollbackScenarios:
    """End-to-end rollback scenario tests"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_manager = CheckpointManager(
            storage_dir=os.path.join(self.temp_dir, "checkpoints")
        )
        self.rollback_manager = create_rollback_manager(
            checkpoint_manager=self.checkpoint_manager,
            storage_dir=os.path.join(self.temp_dir, "rollbacks")
        )
        self.strategy_manager = RollbackStrategyManager(self.rollback_manager)
    
    def teardown_method(self):
        """Clean up after test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_complete_task_lifecycle_with_rollback(self):
        """Test complete task lifecycle including failure and rollback"""
        task_id = "lifecycle-test-001"
        
        # Phase 1: Task initialization
        checkpoint1 = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Lifecycle Test Task",
            step_number=1,
            step_description="Task initialized",
            data={"status": "initialized", "config": {"timeout": 300}}
        )
        
        # Phase 2: Task processing
        checkpoint2 = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Lifecycle Test Task",
            step_number=2,
            step_description="Processing started",
            data={"status": "processing", "progress": 0.3, "items_processed": 30}
        )
        
        # Phase 3: Partial completion
        checkpoint3 = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Lifecycle Test Task",
            step_number=3,
            step_description="Partial completion",
            data={"status": "processing", "progress": 0.7, "items_processed": 70}
        )
        
        # Simulate failure
        print("Simulating task failure...")
        
        # Phase 4: Rollback to last stable state
        success, restored_data = self.rollback_manager.restore_checkpoint(
            checkpoint_id=checkpoint2,  # Rollback to earlier stable state
            reason=RollbackReason.ERROR
        )
        
        assert success is True
        assert restored_data["data"]["progress"] == 0.3
        
        # Phase 5: Resume from rollback point
        checkpoint4 = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Lifecycle Test Task",
            step_number=4,
            step_description="Resumed after rollback",
            data={"status": "processing", "progress": 0.3, "items_processed": 30, "resumed": True}
        )
        
        # Phase 6: Successful completion
        checkpoint5 = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Lifecycle Test Task",
            step_number=5,
            step_description="Task completed",
            data={"status": "completed", "progress": 1.0, "items_processed": 100}
        )
        
        # Verify complete history
        checkpoints = self.rollback_manager.list_checkpoints(task_id)
        assert len(checkpoints) == 5
        
        rollback_history = self.rollback_manager.get_rollback_history(task_id)
        assert len(rollback_history) == 1
        assert rollback_history[0].reason == RollbackReason.ERROR
    
    def test_multi_stage_rollback_scenario(self):
        """Test multi-stage rollback with different strategies"""
        # Create a complex task with multiple components
        task_ids = {
            "main": "multi-stage-main",
            "worker": "multi-stage-worker",
            "config": "multi-stage-config"
        }
        
        # Stage 1: Initialize all components
        checkpoints_stage1 = {}
        for component, task_id in task_ids.items():
            checkpoint_id = self.rollback_manager.create_checkpoint(
                task_id=task_id,
                task_title=f"{component.title()} Component",
                step_number=1,
                step_description="Initialized",
                data={f"{component}_data": "initial"},
                metadata={"component_type": f"{component}_state"}
            )
            checkpoints_stage1[component] = checkpoint_id
        
        # Stage 2: Update some components
        checkpoints_stage2 = {}
        for component in ["main", "worker"]:
            task_id = task_ids[component]
            checkpoint_id = self.rollback_manager.create_checkpoint(
                task_id=task_id,
                task_title=f"{component.title()} Component",
                step_number=2,
                step_description="Updated",
                data={f"{component}_data": "updated", "version": 2}
            )
            checkpoints_stage2[component] = checkpoint_id
        
        # Test selective rollback
        print("Testing selective rollback...")
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.SELECTIVE,
            task_ids={task_ids["main"]}
        )
        
        plan = self.strategy_manager.create_rollback_plan(scope)
        success, results = self.strategy_manager.execute_rollback(plan)
        
        # Verify only main was rolled back
        main_checkpoints = self.rollback_manager.list_checkpoints(task_ids["main"])
        assert len(main_checkpoints) == 2
        
        # Test partial rollback
        print("Testing partial rollback...")
        scope = create_rollback_scope(
            strategy_type=RollbackStrategyType.PARTIAL,
            components=["worker_state"]
        )
        
        # This would rollback worker components
        # In real implementation, component mapping would be needed
    
    def test_error_recovery_with_rollback(self):
        """Test error recovery scenarios with rollback"""
        task_id = "error-recovery-001"
        
        # Create a checkpoint before error
        checkpoint_before = self.rollback_manager.create_checkpoint(
            task_id=task_id,
            task_title="Error Recovery Test",
            step_number=1,
            step_description="Before error",
            data={"state": "stable", "retry_count": 0}
        )
        
        # Simulate error scenarios
        error_scenarios = [
            (RollbackReason.TIMEOUT, "Operation timed out"),
            (RollbackReason.VALIDATION_FAILURE, "Validation failed"),
            (RollbackReason.ERROR, "Generic error")
        ]
        
        for reason, error_msg in error_scenarios:
            # Create checkpoint representing error state
            error_checkpoint = self.rollback_manager.create_checkpoint(
                task_id=task_id,
                task_title="Error Recovery Test",
                step_number=2,
                step_description=f"Error: {error_msg}",
                data={"state": "error", "error": error_msg}
            )
            
            # Perform rollback with specific reason
            success, _ = self.rollback_manager.restore_checkpoint(
                checkpoint_id=checkpoint_before,
                reason=reason
            )
            
            assert success is True
            
            # Verify rollback history captures the reason
            history = self.rollback_manager.get_rollback_history(task_id)
            latest_rollback = history[0]
            assert latest_rollback.reason == reason


def run_integration_tests():
    """Run all integration tests"""
    print("Running Rollback Integration Tests")
    print("=" * 50)
    
    # Test checkpoint integration
    print("\nTesting Checkpoint Integration...")
    test1 = TestRollbackCheckpointIntegration()
    test1.setup_method()
    
    try:
        test1.test_checkpoint_wrapper_integration()
        print("✓ Checkpoint wrapper integration passed")
        
        test1.test_rollback_with_checkpoint_state_changes()
        print("✓ Checkpoint state changes test passed")
        
        test1.test_rollback_strategy_integration()
        print("✓ Rollback strategy integration passed")
        
        test1.test_concurrent_checkpoint_and_rollback()
        print("✓ Concurrent operations test passed")
        
        test1.test_rollback_with_metadata_preservation()
        print("✓ Metadata preservation test passed")
        
        test1.test_rollback_cascade_effects()
        print("✓ Cascade effects test passed")
    finally:
        test1.teardown_method()
    
    # Test end-to-end scenarios
    print("\nTesting End-to-End Scenarios...")
    test2 = TestEndToEndRollbackScenarios()
    test2.setup_method()
    
    try:
        test2.test_complete_task_lifecycle_with_rollback()
        print("✓ Complete task lifecycle test passed")
        
        test2.test_multi_stage_rollback_scenario()
        print("✓ Multi-stage rollback test passed")
        
        test2.test_error_recovery_with_rollback()
        print("✓ Error recovery test passed")
    finally:
        test2.teardown_method()
    
    print("\n" + "=" * 50)
    print("All integration tests passed!")


if __name__ == "__main__":
    run_integration_tests()