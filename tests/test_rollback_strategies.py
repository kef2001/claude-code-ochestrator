"""
Unit tests for Rollback Strategies

Tests different rollback strategies including full, partial, and selective rollbacks.
"""

import tempfile
import os
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import uuid

from claude_orchestrator.rollback_strategies import (
    RollbackStrategyManager, RollbackScope, RollbackPlan,
    RollbackStrategyType, ComponentType, FullRollbackStrategy,
    PartialRollbackStrategy, SelectiveRollbackStrategy,
    create_rollback_scope
)
from claude_orchestrator.rollback import RollbackManager, RollbackReason
from claude_orchestrator.checkpoint_system import (
    CheckpointManager, CheckpointData, CheckpointState
)


class TestRollbackScope:
    """Tests for RollbackScope data class"""
    
    def test_create_rollback_scope(self):
        """Test creating a rollback scope"""
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.PARTIAL,
            components={ComponentType.TASK_STATE, ComponentType.WORKER_STATE},
            task_ids={"task-1", "task-2"},
            exclude_components={ComponentType.FILE_SYSTEM}
        )
        
        assert scope.strategy_type == RollbackStrategyType.PARTIAL
        assert ComponentType.TASK_STATE in scope.components
        assert "task-1" in scope.task_ids
        assert ComponentType.FILE_SYSTEM in scope.exclude_components
    
    def test_create_rollback_scope_convenience(self):
        """Test convenience function for creating rollback scope"""
        scope = create_rollback_scope(
            strategy_type=RollbackStrategyType.SELECTIVE,
            components=["task_state", "worker_state"],
            task_ids=["task-1", "task-2"],
            exclude_components=["file_system"]
        )
        
        assert scope.strategy_type == RollbackStrategyType.SELECTIVE
        assert ComponentType.TASK_STATE in scope.components
        assert "task-1" in scope.task_ids
        assert ComponentType.FILE_SYSTEM in scope.exclude_components


class TestRollbackPlan:
    """Tests for RollbackPlan data class"""
    
    def test_rollback_plan_serialization(self):
        """Test RollbackPlan to_dict"""
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.FULL,
            components={ComponentType.TASK_STATE}
        )
        
        checkpoint = CheckpointData(
            checkpoint_id="cp-001",
            task_id="task-001",
            task_title="Test Task",
            state=CheckpointState.COMPLETED,
            step_number=1,
            data={}
        )
        
        plan = RollbackPlan(
            plan_id="plan-001",
            scope=scope,
            checkpoints=[checkpoint],
            estimated_impact={"affected_tasks": 5},
            validation_steps=["Step 1", "Step 2"],
            execution_order=[("task_state", "cp-001")],
            warnings=["Warning 1"],
            requires_confirmation=True
        )
        
        plan_dict = plan.to_dict()
        
        assert plan_dict["plan_id"] == "plan-001"
        assert plan_dict["scope"]["strategy_type"] == "full"
        assert "task_state" in plan_dict["scope"]["components"]
        assert plan_dict["checkpoints"] == ["cp-001"]
        assert plan_dict["requires_confirmation"] is True


class TestFullRollbackStrategy:
    """Tests for FullRollbackStrategy"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_manager = CheckpointManager(
            storage_dir=os.path.join(self.temp_dir, "checkpoints")
        )
        self.rollback_manager = RollbackManager(
            checkpoint_manager=self.checkpoint_manager,
            storage_dir=os.path.join(self.temp_dir, "rollbacks")
        )
        self.strategy = FullRollbackStrategy(self.rollback_manager)
    
    def teardown_method(self):
        """Clean up after test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_create_full_rollback_plan(self):
        """Test creating a full rollback plan"""
        # Create checkpoints for different components
        checkpoint_ids = []
        for component in [ComponentType.TASK_STATE, ComponentType.WORKER_STATE]:
            cp_id = self.rollback_manager.create_checkpoint(
                task_id=f"task-{component.value}",
                task_title=f"Test {component.value}",
                step_number=1,
                step_description="Test",
                data={"component": component.value},
                metadata={"component_type": component.value}
            )
            checkpoint_ids.append(cp_id)
        
        # Create rollback scope
        scope = RollbackScope(strategy_type=RollbackStrategyType.FULL)
        
        # Create plan
        plan = self.strategy.create_rollback_plan(scope)
        
        assert plan is not None
        assert plan.scope.strategy_type == RollbackStrategyType.FULL
        assert len(plan.scope.components) == len(ComponentType)  # All components
        assert plan.requires_confirmation is True
        assert "Full system rollback will revert ALL changes" in plan.warnings
        assert len(plan.validation_steps) > 0
    
    def test_execute_full_rollback_success(self):
        """Test successful full rollback execution"""
        # Create checkpoint
        checkpoint_id = self.rollback_manager.create_checkpoint(
            task_id="test-task",
            task_title="Test Task",
            step_number=1,
            step_description="Test",
            data={"test": "data"},
            metadata={"component_type": ComponentType.TASK_STATE.value}
        )
        
        # Create plan
        scope = RollbackScope(strategy_type=RollbackStrategyType.FULL)
        plan = self.strategy.create_rollback_plan(scope)
        
        # Mock system state validation
        with patch.object(self.strategy, '_validate_system_state', return_value=(True, [])):
            # Execute rollback
            success, results = self.strategy.execute_rollback(plan)
        
        assert success is True
        assert results["plan_id"] == plan.plan_id
        assert "start_time" in results
        assert "end_time" in results
        assert len(results["failures"]) == 0
    
    def test_execute_full_rollback_with_hooks(self):
        """Test full rollback with pre/post hooks"""
        hook_calls = []
        
        def pre_hook(plan):
            hook_calls.append(("pre", plan.plan_id))
        
        def post_hook(plan, results):
            hook_calls.append(("post", plan.plan_id))
        
        self.strategy.add_pre_rollback_hook(pre_hook)
        self.strategy.add_post_rollback_hook(post_hook)
        
        # Create checkpoint
        self.rollback_manager.create_checkpoint(
            task_id="test-task",
            task_title="Test Task",
            step_number=1,
            step_description="Test",
            data={"test": "data"},
            metadata={"component_type": ComponentType.TASK_STATE.value}
        )
        
        # Create and execute plan
        scope = RollbackScope(strategy_type=RollbackStrategyType.FULL)
        plan = self.strategy.create_rollback_plan(scope)
        
        with patch.object(self.strategy, '_validate_system_state', return_value=(True, [])):
            self.strategy.execute_rollback(plan)
        
        assert len(hook_calls) == 2
        assert hook_calls[0][0] == "pre"
        assert hook_calls[1][0] == "post"
    
    def test_validate_full_rollback_scope(self):
        """Test validating full rollback scope"""
        scope = RollbackScope(strategy_type=RollbackStrategyType.FULL)
        
        # No checkpoints - should fail
        is_valid, errors = self.strategy.validate_rollback_scope(scope)
        assert is_valid is False
        assert "No checkpoints available" in errors[0]
        
        # Create checkpoint
        self.rollback_manager.create_checkpoint(
            task_id="test-task",
            task_title="Test Task",
            step_number=1,
            step_description="Test",
            data={"test": "data"}
        )
        
        # Now should be valid
        is_valid, errors = self.strategy.validate_rollback_scope(scope)
        assert is_valid is True
        assert len(errors) == 0


class TestPartialRollbackStrategy:
    """Tests for PartialRollbackStrategy"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_manager = CheckpointManager(
            storage_dir=os.path.join(self.temp_dir, "checkpoints")
        )
        self.rollback_manager = RollbackManager(
            checkpoint_manager=self.checkpoint_manager,
            storage_dir=os.path.join(self.temp_dir, "rollbacks")
        )
        self.strategy = PartialRollbackStrategy(self.rollback_manager)
    
    def teardown_method(self):
        """Clean up after test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_create_partial_rollback_plan(self):
        """Test creating a partial rollback plan"""
        # Create checkpoints for specific components
        components = [ComponentType.TASK_STATE, ComponentType.WORKER_STATE]
        
        for component in components:
            self.rollback_manager.create_checkpoint(
                task_id=f"task-{component.value}",
                task_title=f"Test {component.value}",
                step_number=1,
                step_description="Test",
                data={"component": component.value},
                metadata={"component_type": component.value}
            )
        
        # Create scope for partial rollback
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.PARTIAL,
            components={ComponentType.TASK_STATE}
        )
        
        # Create plan
        plan = self.strategy.create_rollback_plan(scope)
        
        assert plan is not None
        assert plan.scope.strategy_type == RollbackStrategyType.PARTIAL
        assert ComponentType.TASK_STATE in plan.scope.components
        assert len(plan.checkpoints) >= 1
        assert len(plan.execution_order) >= 1
    
    def test_partial_rollback_with_dependencies(self):
        """Test partial rollback with component dependencies"""
        # Create checkpoints
        for component in ComponentType:
            self.rollback_manager.create_checkpoint(
                task_id=f"task-{component.value}",
                task_title=f"Test {component.value}",
                step_number=1,
                step_description="Test",
                data={"component": component.value},
                metadata={"component_type": component.value}
            )
        
        # Request rollback of TASK_STATE (which depends on WORKER_STATE)
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.PARTIAL,
            components={ComponentType.TASK_STATE}
        )
        
        # Create plan
        plan = self.strategy.create_rollback_plan(scope)
        
        # Should include WORKER_STATE due to dependency
        assert ComponentType.WORKER_STATE in plan.scope.components
    
    def test_execute_partial_rollback_with_exclusions(self):
        """Test partial rollback with excluded components"""
        # Create checkpoints
        for component in [ComponentType.TASK_STATE, ComponentType.WORKER_STATE, ComponentType.FILE_SYSTEM]:
            self.rollback_manager.create_checkpoint(
                task_id=f"task-{component.value}",
                task_title=f"Test {component.value}",
                step_number=1,
                step_description="Test",
                data={"component": component.value},
                metadata={"component_type": component.value}
            )
        
        # Create scope with exclusions
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.PARTIAL,
            components={ComponentType.TASK_STATE, ComponentType.WORKER_STATE},
            exclude_components={ComponentType.FILE_SYSTEM}
        )
        
        # Create and execute plan
        plan = self.strategy.create_rollback_plan(scope)
        
        # Mock preservation methods
        with patch.object(self.strategy, '_preserve_component_data', return_value={}):
            with patch.object(self.strategy, '_restore_preserved_data'):
                success, results = self.strategy.execute_rollback(plan)
        
        assert ComponentType.FILE_SYSTEM.value in results["preserved_components"]
    
    def test_validate_partial_rollback_scope(self):
        """Test validating partial rollback scope"""
        # Empty components - should fail
        scope = RollbackScope(strategy_type=RollbackStrategyType.PARTIAL)
        is_valid, errors = self.strategy.validate_rollback_scope(scope)
        assert is_valid is False
        assert "No components specified" in errors[0]
        
        # Valid scope
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.PARTIAL,
            components={ComponentType.TASK_STATE}
        )
        
        # Create checkpoint for the component
        self.rollback_manager.create_checkpoint(
            task_id="test-task",
            task_title="Test Task",
            step_number=1,
            step_description="Test",
            data={"test": "data"},
            metadata={"component_type": ComponentType.TASK_STATE.value}
        )
        
        is_valid, errors = self.strategy.validate_rollback_scope(scope)
        assert is_valid is True


class TestSelectiveRollbackStrategy:
    """Tests for SelectiveRollbackStrategy"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_manager = CheckpointManager(
            storage_dir=os.path.join(self.temp_dir, "checkpoints")
        )
        self.rollback_manager = RollbackManager(
            checkpoint_manager=self.checkpoint_manager,
            storage_dir=os.path.join(self.temp_dir, "rollbacks")
        )
        self.strategy = SelectiveRollbackStrategy(self.rollback_manager)
    
    def teardown_method(self):
        """Clean up after test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_create_selective_rollback_plan(self):
        """Test creating a selective rollback plan"""
        # Create checkpoints for specific tasks
        task_ids = ["task-001", "task-002", "task-003"]
        
        for task_id in task_ids:
            self.rollback_manager.create_checkpoint(
                task_id=task_id,
                task_title=f"Test {task_id}",
                step_number=1,
                step_description="Test",
                data={"task": task_id}
            )
        
        # Create scope for selective rollback
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.SELECTIVE,
            task_ids={"task-001", "task-002"}
        )
        
        # Create plan
        plan = self.strategy.create_rollback_plan(scope)
        
        assert plan is not None
        assert plan.scope.strategy_type == RollbackStrategyType.SELECTIVE
        assert "task-001" in plan.scope.task_ids
        assert "task-002" in plan.scope.task_ids
        assert len(plan.checkpoints) == 2
    
    def test_selective_rollback_with_dependencies(self):
        """Test selective rollback with task dependencies"""
        # Create checkpoints
        task_ids = ["task-001", "task-002", "task-003"]
        for task_id in task_ids:
            self.rollback_manager.create_checkpoint(
                task_id=task_id,
                task_title=f"Test {task_id}",
                step_number=1,
                step_description="Test",
                data={"task": task_id}
            )
        
        # Mock dependency graph
        with patch.object(self.strategy, '_build_task_dependency_graph') as mock_graph:
            # task-003 depends on task-002
            mock_graph.return_value = {
                "task-001": set(),
                "task-002": {"task-001"},
                "task-003": {"task-002"}
            }
            
            # Request rollback of task-002 only
            scope = RollbackScope(
                strategy_type=RollbackStrategyType.SELECTIVE,
                task_ids={"task-002"}
            )
            
            # Create plan
            plan = self.strategy.create_rollback_plan(scope)
            
            # Should warn about cascading effects
            assert "cascading_tasks" in plan.estimated_impact
    
    def test_execute_selective_rollback(self):
        """Test executing selective rollback"""
        # Create checkpoints
        task_ids = ["task-001", "task-002"]
        for task_id in task_ids:
            self.rollback_manager.create_checkpoint(
                task_id=task_id,
                task_title=f"Test {task_id}",
                step_number=1,
                step_description="Test",
                data={"task": task_id}
            )
        
        # Create scope
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.SELECTIVE,
            task_ids=set(task_ids)
        )
        
        # Create and execute plan
        plan = self.strategy.create_rollback_plan(scope)
        
        with patch.object(self.strategy, '_validate_task_states', return_value=[]):
            with patch.object(self.strategy, '_handle_cascading_rollbacks', return_value=[]):
                success, results = self.strategy.execute_rollback(plan)
        
        assert success is True
        assert len(results["tasks_rolled_back"]) > 0
    
    def test_validate_selective_rollback_scope(self):
        """Test validating selective rollback scope"""
        # Empty tasks - should fail
        scope = RollbackScope(strategy_type=RollbackStrategyType.SELECTIVE)
        is_valid, errors = self.strategy.validate_rollback_scope(scope)
        assert is_valid is False
        assert "No tasks specified" in errors[0]
        
        # Valid scope
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.SELECTIVE,
            task_ids={"task-001"}
        )
        
        with patch.object(self.strategy, '_task_exists', return_value=True):
            is_valid, errors = self.strategy.validate_rollback_scope(scope)
            assert is_valid is True
    
    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies"""
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.SELECTIVE,
            task_ids={"task-001", "task-002"}
        )
        
        # Create circular dependency
        circular_graph = {
            "task-001": {"task-002"},
            "task-002": {"task-001"}
        }
        
        with patch.object(self.strategy, '_build_task_dependency_graph', return_value=circular_graph):
            with patch.object(self.strategy, '_task_exists', return_value=True):
                is_valid, errors = self.strategy.validate_rollback_scope(scope)
                assert is_valid is False
                assert "Circular dependencies" in errors[0]


class TestRollbackStrategyManager:
    """Tests for RollbackStrategyManager"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_manager = CheckpointManager(
            storage_dir=os.path.join(self.temp_dir, "checkpoints")
        )
        self.rollback_manager = RollbackManager(
            checkpoint_manager=self.checkpoint_manager,
            storage_dir=os.path.join(self.temp_dir, "rollbacks")
        )
        self.manager = RollbackStrategyManager(self.rollback_manager)
    
    def teardown_method(self):
        """Clean up after test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_strategy_selection(self):
        """Test automatic strategy selection"""
        # System-wide scope - should select FULL
        scope = RollbackScope(
            strategy_type=None,  # Let manager decide
            components=set(ComponentType)  # All components
        )
        strategy_type, reason = self.manager.select_strategy(scope)
        assert strategy_type == RollbackStrategyType.FULL
        
        # Task-specific scope - should select SELECTIVE
        scope = RollbackScope(
            strategy_type=None,
            task_ids={"task-001", "task-002"}
        )
        strategy_type, reason = self.manager.select_strategy(scope)
        assert strategy_type == RollbackStrategyType.SELECTIVE
        
        # Component-specific scope - should select PARTIAL
        scope = RollbackScope(
            strategy_type=None,
            components={ComponentType.TASK_STATE}
        )
        strategy_type, reason = self.manager.select_strategy(scope)
        assert strategy_type == RollbackStrategyType.PARTIAL
    
    def test_create_rollback_plan_with_manager(self):
        """Test creating rollback plan through manager"""
        # Create checkpoint
        self.rollback_manager.create_checkpoint(
            task_id="test-task",
            task_title="Test Task",
            step_number=1,
            step_description="Test",
            data={"test": "data"},
            metadata={"component_type": ComponentType.TASK_STATE.value}
        )
        
        # Create scope
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.PARTIAL,
            components={ComponentType.TASK_STATE}
        )
        
        # Create plan through manager
        plan = self.manager.create_rollback_plan(scope)
        
        assert plan is not None
        assert plan.scope.strategy_type == RollbackStrategyType.PARTIAL
        assert "strategy_selection_reason" in plan.metadata
    
    def test_execute_rollback_with_manager(self):
        """Test executing rollback through manager"""
        # Create checkpoint
        self.rollback_manager.create_checkpoint(
            task_id="test-task",
            task_title="Test Task",
            step_number=1,
            step_description="Test",
            data={"test": "data"},
            metadata={"component_type": ComponentType.TASK_STATE.value}
        )
        
        # Create scope and plan
        scope = RollbackScope(
            strategy_type=RollbackStrategyType.PARTIAL,
            components={ComponentType.TASK_STATE}
        )
        plan = self.manager.create_rollback_plan(scope)
        
        # Execute through manager
        with patch.object(PartialRollbackStrategy, '_preserve_component_data', return_value={}):
            with patch.object(PartialRollbackStrategy, '_restore_preserved_data'):
                success, results = self.manager.execute_rollback(plan)
        
        assert isinstance(success, bool)
        assert "plan_id" in results
    
    def test_custom_selection_rules(self):
        """Test adding custom strategy selection rules"""
        # Add custom rule
        self.manager.add_selection_rule(
            lambda scope: "critical" in scope.metadata.get("tags", []),
            RollbackStrategyType.FULL,
            "Critical failure requires full rollback"
        )
        
        # Test with matching scope
        scope = RollbackScope(
            strategy_type=None,
            components={ComponentType.TASK_STATE},
            metadata={"tags": ["critical", "urgent"]}
        )
        
        strategy_type, reason = self.manager.select_strategy(scope)
        assert strategy_type == RollbackStrategyType.FULL
        assert "Critical failure" in reason
    
    def test_get_specific_strategy(self):
        """Test getting specific strategy instance"""
        full_strategy = self.manager.get_strategy(RollbackStrategyType.FULL)
        assert isinstance(full_strategy, FullRollbackStrategy)
        
        partial_strategy = self.manager.get_strategy(RollbackStrategyType.PARTIAL)
        assert isinstance(partial_strategy, PartialRollbackStrategy)
        
        selective_strategy = self.manager.get_strategy(RollbackStrategyType.SELECTIVE)
        assert isinstance(selective_strategy, SelectiveRollbackStrategy)