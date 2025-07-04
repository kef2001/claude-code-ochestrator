"""
Rollback Strategies for Claude Orchestrator

This module defines and implements different rollback strategies:
- Full rollback: Restore entire system state
- Partial rollback: Restore specific components
- Selective rollback: Restore specific tasks/operations
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import json
from pathlib import Path

from .rollback import RollbackManager, RollbackReason, RollbackStatus
from .checkpoint_system import CheckpointData, CheckpointState


logger = logging.getLogger(__name__)


class RollbackStrategyType(Enum):
    """Types of rollback strategies"""
    FULL = "full"  # Restore entire system state
    PARTIAL = "partial"  # Restore specific components
    SELECTIVE = "selective"  # Restore specific tasks
    CASCADE = "cascade"  # Rollback with dependency resolution
    POINT_IN_TIME = "point_in_time"  # Rollback to specific timestamp


class ComponentType(Enum):
    """Types of system components that can be rolled back"""
    TASK_STATE = "task_state"
    WORKER_STATE = "worker_state"
    CONFIGURATION = "configuration"
    FILE_SYSTEM = "file_system"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"


@dataclass
class RollbackScope:
    """Defines the scope of a rollback operation"""
    strategy_type: RollbackStrategyType
    components: Set[ComponentType] = field(default_factory=set)
    task_ids: Set[str] = field(default_factory=set)
    time_range: Optional[Tuple[datetime, datetime]] = None
    exclude_components: Set[ComponentType] = field(default_factory=set)
    preserve_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RollbackPlan:
    """Execution plan for a rollback operation"""
    plan_id: str
    scope: RollbackScope
    checkpoints: List[CheckpointData]
    estimated_impact: Dict[str, Any]
    validation_steps: List[str]
    execution_order: List[Tuple[str, str]]  # [(component, checkpoint_id)]
    warnings: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "plan_id": self.plan_id,
            "scope": {
                "strategy_type": self.scope.strategy_type.value,
                "components": [c.value for c in self.scope.components],
                "task_ids": list(self.scope.task_ids),
                "time_range": [dt.isoformat() for dt in self.scope.time_range] if self.scope.time_range else None,
                "exclude_components": [c.value for c in self.scope.exclude_components],
                "preserve_data": self.scope.preserve_data,
                "metadata": self.scope.metadata
            },
            "checkpoints": [cp.checkpoint_id for cp in self.checkpoints],
            "estimated_impact": self.estimated_impact,
            "validation_steps": self.validation_steps,
            "execution_order": self.execution_order,
            "warnings": self.warnings,
            "requires_confirmation": self.requires_confirmation,
            "metadata": self.metadata
        }


class RollbackStrategy(ABC):
    """Abstract base class for rollback strategies"""
    
    def __init__(self, rollback_manager: RollbackManager):
        self.rollback_manager = rollback_manager
        self.pre_rollback_hooks: List[Callable] = []
        self.post_rollback_hooks: List[Callable] = []
    
    @abstractmethod
    def create_rollback_plan(self, scope: RollbackScope) -> RollbackPlan:
        """Create a rollback plan based on the scope"""
        pass
    
    @abstractmethod
    def execute_rollback(self, plan: RollbackPlan) -> Tuple[bool, Dict[str, Any]]:
        """Execute the rollback plan"""
        pass
    
    @abstractmethod
    def validate_rollback_scope(self, scope: RollbackScope) -> Tuple[bool, List[str]]:
        """Validate if the rollback scope is valid"""
        pass
    
    def estimate_impact(self, scope: RollbackScope) -> Dict[str, Any]:
        """Estimate the impact of the rollback"""
        impact = {
            "affected_tasks": len(scope.task_ids),
            "affected_components": len(scope.components),
            "data_loss_risk": "low",
            "estimated_duration": "unknown",
            "warnings": []
        }
        
        # Check for data loss risk
        if ComponentType.DATABASE in scope.components:
            impact["data_loss_risk"] = "high"
            impact["warnings"].append("Database rollback may result in data loss")
        
        if ComponentType.FILE_SYSTEM in scope.components:
            impact["warnings"].append("File system changes will be reverted")
        
        return impact
    
    def add_pre_rollback_hook(self, hook: Callable):
        """Add a pre-rollback hook"""
        self.pre_rollback_hooks.append(hook)
    
    def add_post_rollback_hook(self, hook: Callable):
        """Add a post-rollback hook"""
        self.post_rollback_hooks.append(hook)
    
    def _execute_hooks(self, hooks: List[Callable], *args, **kwargs):
        """Execute a list of hooks"""
        for hook in hooks:
            try:
                hook(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook execution failed: {e}")


class FullRollbackStrategy(RollbackStrategy):
    """
    Full rollback strategy - restores entire system state
    """
    
    def create_rollback_plan(self, scope: RollbackScope) -> RollbackPlan:
        """Create a plan for full system rollback"""
        logger.info("Creating full rollback plan")
        
        # For full rollback, include all components
        scope.components = set(ComponentType)
        
        # Get all available checkpoints
        checkpoints = self.rollback_manager.list_checkpoints()
        if not checkpoints:
            raise ValueError("No checkpoints available for rollback")
        
        # Select the most recent valid checkpoint for each component
        selected_checkpoints = self._select_checkpoints_for_components(
            checkpoints, scope.components
        )
        
        # Create execution order (critical components first)
        execution_order = self._create_execution_order(selected_checkpoints)
        
        # Estimate impact
        impact = self.estimate_impact(scope)
        impact["affected_components"] = len(ComponentType)
        impact["data_loss_risk"] = "high"
        impact["warnings"].append("Full system rollback will revert ALL changes")
        
        # Create validation steps
        validation_steps = [
            "Verify all component checkpoints are available",
            "Check system dependencies",
            "Validate checkpoint integrity",
            "Ensure no active operations",
            "Backup current state"
        ]
        
        plan = RollbackPlan(
            plan_id=f"full_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            scope=scope,
            checkpoints=selected_checkpoints,
            estimated_impact=impact,
            validation_steps=validation_steps,
            execution_order=execution_order,
            warnings=impact["warnings"],
            requires_confirmation=True  # Full rollback always requires confirmation
        )
        
        return plan
    
    def execute_rollback(self, plan: RollbackPlan) -> Tuple[bool, Dict[str, Any]]:
        """Execute full system rollback"""
        logger.info(f"Executing full rollback plan: {plan.plan_id}")
        
        results = {
            "plan_id": plan.plan_id,
            "start_time": datetime.now().isoformat(),
            "components_rolled_back": [],
            "failures": [],
            "warnings": []
        }
        
        try:
            # Execute pre-rollback hooks
            self._execute_hooks(self.pre_rollback_hooks, plan)
            
            # Validate system state
            logger.info("Validating system state before rollback")
            is_valid, validation_errors = self._validate_system_state()
            if not is_valid:
                results["failures"].extend(validation_errors)
                return False, results
            
            # Execute rollback in order
            for component_type, checkpoint_id in plan.execution_order:
                logger.info(f"Rolling back component: {component_type}")
                
                try:
                    # Find checkpoint
                    checkpoint = next(
                        (cp for cp in plan.checkpoints if cp.checkpoint_id == checkpoint_id),
                        None
                    )
                    
                    if not checkpoint:
                        raise ValueError(f"Checkpoint {checkpoint_id} not found")
                    
                    # Perform component rollback
                    success = self._rollback_component(
                        ComponentType(component_type),
                        checkpoint
                    )
                    
                    if success:
                        results["components_rolled_back"].append(component_type)
                    else:
                        results["failures"].append(f"Failed to rollback {component_type}")
                        # Continue with other components
                        
                except Exception as e:
                    logger.error(f"Error rolling back {component_type}: {e}")
                    results["failures"].append(f"{component_type}: {str(e)}")
            
            # Execute post-rollback hooks
            self._execute_hooks(self.post_rollback_hooks, plan, results)
            
            results["end_time"] = datetime.now().isoformat()
            results["success"] = len(results["failures"]) == 0
            
            return results["success"], results
            
        except Exception as e:
            logger.error(f"Full rollback failed: {e}")
            results["failures"].append(f"Critical error: {str(e)}")
            results["success"] = False
            return False, results
    
    def validate_rollback_scope(self, scope: RollbackScope) -> Tuple[bool, List[str]]:
        """Validate full rollback scope"""
        errors = []
        
        # Check if system is in a state that allows full rollback
        if self._has_active_operations():
            errors.append("Cannot perform full rollback while operations are active")
        
        # Verify checkpoint availability
        checkpoints = self.rollback_manager.list_checkpoints()
        if not checkpoints:
            errors.append("No checkpoints available for full rollback")
        
        return len(errors) == 0, errors
    
    def _select_checkpoints_for_components(
        self,
        checkpoints: List[CheckpointData],
        components: Set[ComponentType]
    ) -> List[CheckpointData]:
        """Select appropriate checkpoints for each component"""
        selected = []
        
        # Group checkpoints by component type (simplified - uses metadata)
        for component in components:
            component_checkpoints = [
                cp for cp in checkpoints
                if cp.metadata.get("component_type") == component.value
            ]
            
            if component_checkpoints:
                # Select most recent valid checkpoint
                component_checkpoints.sort(key=lambda x: x.created_at, reverse=True)
                selected.append(component_checkpoints[0])
        
        return selected
    
    def _create_execution_order(
        self,
        checkpoints: List[CheckpointData]
    ) -> List[Tuple[str, str]]:
        """Create execution order for rollback"""
        # Define component priority (lower number = higher priority)
        priority_map = {
            ComponentType.DATABASE: 1,
            ComponentType.CONFIGURATION: 2,
            ComponentType.CACHE: 3,
            ComponentType.QUEUE: 4,
            ComponentType.TASK_STATE: 5,
            ComponentType.WORKER_STATE: 6,
            ComponentType.FILE_SYSTEM: 7
        }
        
        order = []
        for checkpoint in checkpoints:
            component_type = checkpoint.metadata.get("component_type", ComponentType.TASK_STATE.value)
            order.append((component_type, checkpoint.checkpoint_id))
        
        # Sort by priority
        order.sort(key=lambda x: priority_map.get(ComponentType(x[0]), 99))
        
        return order
    
    def _validate_system_state(self) -> Tuple[bool, List[str]]:
        """Validate system state before rollback"""
        errors = []
        
        # Check for active operations
        if self._has_active_operations():
            errors.append("Active operations detected")
        
        # Check for uncommitted changes
        if self._has_uncommitted_changes():
            errors.append("Uncommitted changes detected")
        
        return len(errors) == 0, errors
    
    def _rollback_component(
        self,
        component_type: ComponentType,
        checkpoint: CheckpointData
    ) -> bool:
        """Rollback a specific component"""
        try:
            # Use the rollback manager to restore the checkpoint
            success, _ = self.rollback_manager.restore_checkpoint(
                checkpoint_id=checkpoint.checkpoint_id,
                reason=RollbackReason.MANUAL
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to rollback component {component_type}: {e}")
            return False
    
    def _has_active_operations(self) -> bool:
        """Check if there are active operations"""
        # This would check for active tasks, workers, etc.
        # Simplified for this implementation
        return False
    
    def _has_uncommitted_changes(self) -> bool:
        """Check for uncommitted changes"""
        # This would check for pending changes
        # Simplified for this implementation
        return False


class PartialRollbackStrategy(RollbackStrategy):
    """
    Partial rollback strategy - restores specific components
    """
    
    def create_rollback_plan(self, scope: RollbackScope) -> RollbackPlan:
        """Create a plan for partial rollback"""
        logger.info(f"Creating partial rollback plan for components: {scope.components}")
        
        if not scope.components:
            raise ValueError("No components specified for partial rollback")
        
        # Get checkpoints for specified components
        all_checkpoints = self.rollback_manager.list_checkpoints()
        selected_checkpoints = []
        
        for component in scope.components:
            component_checkpoints = [
                cp for cp in all_checkpoints
                if cp.metadata.get("component_type") == component.value
            ]
            
            if component_checkpoints:
                # Select most recent
                component_checkpoints.sort(key=lambda x: x.created_at, reverse=True)
                selected_checkpoints.append(component_checkpoints[0])
            else:
                logger.warning(f"No checkpoint found for component: {component}")
        
        if not selected_checkpoints:
            raise ValueError("No valid checkpoints found for specified components")
        
        # Check dependencies
        dependencies = self._analyze_component_dependencies(scope.components)
        if dependencies - scope.components:
            logger.warning(f"Additional components required due to dependencies: {dependencies - scope.components}")
            scope.components.update(dependencies)
        
        # Create execution order
        execution_order = self._create_dependency_aware_order(selected_checkpoints, dependencies)
        
        # Estimate impact
        impact = self.estimate_impact(scope)
        impact["dependent_components"] = list(dependencies - scope.components)
        
        # Validation steps
        validation_steps = [
            f"Verify checkpoints for {len(scope.components)} components",
            "Check component dependencies",
            "Validate partial rollback compatibility",
            "Ensure component isolation"
        ]
        
        plan = RollbackPlan(
            plan_id=f"partial_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            scope=scope,
            checkpoints=selected_checkpoints,
            estimated_impact=impact,
            validation_steps=validation_steps,
            execution_order=execution_order,
            warnings=impact.get("warnings", [])
        )
        
        return plan
    
    def execute_rollback(self, plan: RollbackPlan) -> Tuple[bool, Dict[str, Any]]:
        """Execute partial rollback"""
        logger.info(f"Executing partial rollback plan: {plan.plan_id}")
        
        results = {
            "plan_id": plan.plan_id,
            "start_time": datetime.now().isoformat(),
            "components_rolled_back": [],
            "preserved_components": [],
            "failures": []
        }
        
        try:
            # Execute pre-rollback hooks
            self._execute_hooks(self.pre_rollback_hooks, plan)
            
            # Preserve data for excluded components
            preserved_data = self._preserve_component_data(plan.scope.exclude_components)
            results["preserved_components"] = list(plan.scope.exclude_components)
            
            # Execute rollback for selected components
            for component_type, checkpoint_id in plan.execution_order:
                if ComponentType(component_type) in plan.scope.exclude_components:
                    logger.info(f"Skipping excluded component: {component_type}")
                    continue
                
                logger.info(f"Rolling back component: {component_type}")
                
                checkpoint = next(
                    (cp for cp in plan.checkpoints if cp.checkpoint_id == checkpoint_id),
                    None
                )
                
                if checkpoint:
                    success = self._rollback_component_with_isolation(
                        ComponentType(component_type),
                        checkpoint,
                        preserved_data
                    )
                    
                    if success:
                        results["components_rolled_back"].append(component_type)
                    else:
                        results["failures"].append(f"Failed to rollback {component_type}")
            
            # Restore preserved data
            self._restore_preserved_data(preserved_data)
            
            # Execute post-rollback hooks
            self._execute_hooks(self.post_rollback_hooks, plan, results)
            
            results["end_time"] = datetime.now().isoformat()
            results["success"] = len(results["failures"]) == 0
            
            return results["success"], results
            
        except Exception as e:
            logger.error(f"Partial rollback failed: {e}")
            results["failures"].append(str(e))
            return False, results
    
    def validate_rollback_scope(self, scope: RollbackScope) -> Tuple[bool, List[str]]:
        """Validate partial rollback scope"""
        errors = []
        
        if not scope.components:
            errors.append("No components specified for partial rollback")
        
        # Check component compatibility
        incompatible = self._check_component_compatibility(scope.components)
        if incompatible:
            errors.append(f"Incompatible components: {incompatible}")
        
        # Verify checkpoint availability
        for component in scope.components:
            if not self._has_checkpoint_for_component(component):
                errors.append(f"No checkpoint available for component: {component}")
        
        return len(errors) == 0, errors
    
    def _analyze_component_dependencies(
        self,
        components: Set[ComponentType]
    ) -> Set[ComponentType]:
        """Analyze component dependencies"""
        dependencies = components.copy()
        
        # Define component dependencies
        dependency_map = {
            ComponentType.TASK_STATE: {ComponentType.WORKER_STATE},
            ComponentType.WORKER_STATE: {ComponentType.CONFIGURATION},
            ComponentType.QUEUE: {ComponentType.TASK_STATE},
            ComponentType.DATABASE: {ComponentType.CACHE}
        }
        
        # Add dependencies
        for component in components:
            if component in dependency_map:
                dependencies.update(dependency_map[component])
        
        return dependencies
    
    def _create_dependency_aware_order(
        self,
        checkpoints: List[CheckpointData],
        dependencies: Set[ComponentType]
    ) -> List[Tuple[str, str]]:
        """Create execution order considering dependencies"""
        # Topological sort based on dependencies
        order = []
        
        # Simple ordering for now
        priority_order = [
            ComponentType.CONFIGURATION,
            ComponentType.DATABASE,
            ComponentType.CACHE,
            ComponentType.WORKER_STATE,
            ComponentType.TASK_STATE,
            ComponentType.QUEUE,
            ComponentType.FILE_SYSTEM
        ]
        
        for component_type in priority_order:
            for checkpoint in checkpoints:
                if checkpoint.metadata.get("component_type") == component_type.value:
                    order.append((component_type.value, checkpoint.checkpoint_id))
        
        return order
    
    def _preserve_component_data(
        self,
        components: Set[ComponentType]
    ) -> Dict[str, Any]:
        """Preserve data for components that should not be rolled back"""
        preserved = {}
        
        for component in components:
            # This would actually save component state
            preserved[component.value] = {
                "preserved_at": datetime.now().isoformat(),
                "component_state": "mock_state"
            }
        
        return preserved
    
    def _rollback_component_with_isolation(
        self,
        component_type: ComponentType,
        checkpoint: CheckpointData,
        preserved_data: Dict[str, Any]
    ) -> bool:
        """Rollback component while preserving others"""
        try:
            # Ensure isolation
            logger.info(f"Isolating component {component_type} for rollback")
            
            # Perform rollback
            success, _ = self.rollback_manager.restore_checkpoint(
                checkpoint_id=checkpoint.checkpoint_id,
                reason=RollbackReason.MANUAL
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Isolated rollback failed for {component_type}: {e}")
            return False
    
    def _restore_preserved_data(self, preserved_data: Dict[str, Any]):
        """Restore preserved component data"""
        for component, data in preserved_data.items():
            logger.info(f"Restoring preserved data for component: {component}")
            # This would actually restore the preserved state
    
    def _check_component_compatibility(
        self,
        components: Set[ComponentType]
    ) -> List[str]:
        """Check if components can be rolled back together"""
        incompatible = []
        
        # Example: Can't rollback task state without worker state
        if ComponentType.TASK_STATE in components and ComponentType.WORKER_STATE not in components:
            incompatible.append("TASK_STATE requires WORKER_STATE")
        
        return incompatible
    
    def _has_checkpoint_for_component(self, component: ComponentType) -> bool:
        """Check if checkpoint exists for component"""
        checkpoints = self.rollback_manager.list_checkpoints()
        return any(
            cp.metadata.get("component_type") == component.value
            for cp in checkpoints
        )


class SelectiveRollbackStrategy(RollbackStrategy):
    """
    Selective rollback strategy - restores specific tasks/operations
    """
    
    def create_rollback_plan(self, scope: RollbackScope) -> RollbackPlan:
        """Create a plan for selective task rollback"""
        logger.info(f"Creating selective rollback plan for tasks: {scope.task_ids}")
        
        if not scope.task_ids:
            raise ValueError("No tasks specified for selective rollback")
        
        # Get checkpoints for specified tasks
        all_checkpoints = self.rollback_manager.list_checkpoints()
        task_checkpoints = {}
        
        for task_id in scope.task_ids:
            task_cps = [cp for cp in all_checkpoints if cp.task_id == task_id]
            if task_cps:
                # Sort by creation time, newest first
                task_cps.sort(key=lambda x: x.created_at, reverse=True)
                task_checkpoints[task_id] = task_cps[0]
        
        if not task_checkpoints:
            raise ValueError("No checkpoints found for specified tasks")
        
        # Analyze task dependencies
        dependency_graph = self._build_task_dependency_graph(scope.task_ids)
        affected_tasks = self._find_affected_tasks(scope.task_ids, dependency_graph)
        
        if affected_tasks - scope.task_ids:
            logger.warning(f"Additional tasks affected by dependencies: {affected_tasks - scope.task_ids}")
        
        # Create execution order
        execution_order = self._create_task_rollback_order(
            task_checkpoints,
            dependency_graph
        )
        
        # Estimate impact
        impact = self.estimate_impact(scope)
        impact["cascading_tasks"] = list(affected_tasks - scope.task_ids)
        impact["orphaned_data_risk"] = self._assess_orphaned_data_risk(affected_tasks)
        
        # Validation steps
        validation_steps = [
            f"Verify checkpoints for {len(scope.task_ids)} tasks",
            "Analyze task dependency graph",
            "Check for cascading effects",
            "Validate task isolation",
            "Identify orphaned data"
        ]
        
        plan = RollbackPlan(
            plan_id=f"selective_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            scope=scope,
            checkpoints=list(task_checkpoints.values()),
            estimated_impact=impact,
            validation_steps=validation_steps,
            execution_order=execution_order,
            warnings=impact.get("warnings", []),
            requires_confirmation=len(affected_tasks) > len(scope.task_ids)
        )
        
        return plan
    
    def execute_rollback(self, plan: RollbackPlan) -> Tuple[bool, Dict[str, Any]]:
        """Execute selective task rollback"""
        logger.info(f"Executing selective rollback plan: {plan.plan_id}")
        
        results = {
            "plan_id": plan.plan_id,
            "start_time": datetime.now().isoformat(),
            "tasks_rolled_back": [],
            "cascading_rollbacks": [],
            "orphaned_data_cleaned": False,
            "failures": []
        }
        
        try:
            # Execute pre-rollback hooks
            self._execute_hooks(self.pre_rollback_hooks, plan)
            
            # Validate task states
            invalid_tasks = self._validate_task_states(plan.scope.task_ids)
            if invalid_tasks:
                results["failures"].append(f"Invalid task states: {invalid_tasks}")
                return False, results
            
            # Execute rollback in dependency order
            for task_id, checkpoint_id in plan.execution_order:
                logger.info(f"Rolling back task: {task_id}")
                
                checkpoint = next(
                    (cp for cp in plan.checkpoints if cp.checkpoint_id == checkpoint_id),
                    None
                )
                
                if checkpoint:
                    success = self._rollback_task(task_id, checkpoint)
                    
                    if success:
                        results["tasks_rolled_back"].append(task_id)
                        
                        # Check for cascading rollbacks
                        cascading = self._handle_cascading_rollbacks(task_id)
                        results["cascading_rollbacks"].extend(cascading)
                    else:
                        results["failures"].append(f"Failed to rollback task {task_id}")
            
            # Clean up orphaned data
            if plan.estimated_impact.get("orphaned_data_risk", "low") != "low":
                cleaned = self._cleanup_orphaned_data(results["tasks_rolled_back"])
                results["orphaned_data_cleaned"] = cleaned
            
            # Execute post-rollback hooks
            self._execute_hooks(self.post_rollback_hooks, plan, results)
            
            results["end_time"] = datetime.now().isoformat()
            results["success"] = len(results["failures"]) == 0
            
            return results["success"], results
            
        except Exception as e:
            logger.error(f"Selective rollback failed: {e}")
            results["failures"].append(str(e))
            return False, results
    
    def validate_rollback_scope(self, scope: RollbackScope) -> Tuple[bool, List[str]]:
        """Validate selective rollback scope"""
        errors = []
        
        if not scope.task_ids:
            errors.append("No tasks specified for selective rollback")
        
        # Check task existence
        for task_id in scope.task_ids:
            if not self._task_exists(task_id):
                errors.append(f"Task not found: {task_id}")
        
        # Check for circular dependencies
        dependency_graph = self._build_task_dependency_graph(scope.task_ids)
        if self._has_circular_dependencies(dependency_graph):
            errors.append("Circular dependencies detected in task graph")
        
        return len(errors) == 0, errors
    
    def _build_task_dependency_graph(
        self,
        task_ids: Set[str]
    ) -> Dict[str, Set[str]]:
        """Build task dependency graph"""
        graph = {}
        
        # This would actually query task dependencies
        # Simplified mock implementation
        for task_id in task_ids:
            # Mock dependencies
            if task_id.endswith("1"):
                graph[task_id] = set()
            elif task_id.endswith("2"):
                graph[task_id] = {tid for tid in task_ids if tid.endswith("1")}
            else:
                graph[task_id] = {tid for tid in task_ids if tid < task_id}
        
        return graph
    
    def _find_affected_tasks(
        self,
        task_ids: Set[str],
        dependency_graph: Dict[str, Set[str]]
    ) -> Set[str]:
        """Find all tasks affected by rolling back the specified tasks"""
        affected = task_ids.copy()
        
        # Find tasks that depend on the tasks being rolled back
        all_tasks = set(dependency_graph.keys())
        
        for task in all_tasks:
            if task not in affected:
                dependencies = dependency_graph.get(task, set())
                if dependencies & affected:
                    affected.add(task)
        
        return affected
    
    def _create_task_rollback_order(
        self,
        task_checkpoints: Dict[str, CheckpointData],
        dependency_graph: Dict[str, Set[str]]
    ) -> List[Tuple[str, str]]:
        """Create execution order for task rollbacks"""
        # Topological sort to handle dependencies
        order = []
        visited = set()
        
        def visit(task_id):
            if task_id in visited:
                return
            visited.add(task_id)
            
            # Visit dependencies first
            for dep in dependency_graph.get(task_id, set()):
                if dep in task_checkpoints:
                    visit(dep)
            
            if task_id in task_checkpoints:
                order.append((task_id, task_checkpoints[task_id].checkpoint_id))
        
        for task_id in task_checkpoints:
            visit(task_id)
        
        # Reverse to rollback dependents first
        order.reverse()
        
        return order
    
    def _assess_orphaned_data_risk(self, affected_tasks: Set[str]) -> str:
        """Assess risk of orphaned data from selective rollback"""
        if len(affected_tasks) > 10:
            return "high"
        elif len(affected_tasks) > 5:
            return "medium"
        else:
            return "low"
    
    def _validate_task_states(self, task_ids: Set[str]) -> List[str]:
        """Validate that tasks are in a state that allows rollback"""
        invalid = []
        
        for task_id in task_ids:
            # This would check actual task state
            # Mock implementation
            if task_id.startswith("active_"):
                invalid.append(task_id)
        
        return invalid
    
    def _rollback_task(self, task_id: str, checkpoint: CheckpointData) -> bool:
        """Rollback a specific task"""
        try:
            success, _ = self.rollback_manager.restore_checkpoint(
                checkpoint_id=checkpoint.checkpoint_id,
                reason=RollbackReason.MANUAL
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to rollback task {task_id}: {e}")
            return False
    
    def _handle_cascading_rollbacks(self, task_id: str) -> List[str]:
        """Handle cascading rollbacks for dependent tasks"""
        cascading = []
        
        # This would identify and rollback dependent tasks
        # Mock implementation
        logger.info(f"Checking for cascading rollbacks from task {task_id}")
        
        return cascading
    
    def _cleanup_orphaned_data(self, rolled_back_tasks: List[str]) -> bool:
        """Clean up data orphaned by selective rollback"""
        try:
            logger.info(f"Cleaning up orphaned data for {len(rolled_back_tasks)} tasks")
            
            # This would actually clean up orphaned data
            # Mock implementation
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to clean up orphaned data: {e}")
            return False
    
    def _task_exists(self, task_id: str) -> bool:
        """Check if task exists"""
        # This would check actual task existence
        return True
    
    def _has_circular_dependencies(
        self,
        dependency_graph: Dict[str, Set[str]]
    ) -> bool:
        """Check for circular dependencies in task graph"""
        visited = set()
        rec_stack = set()
        
        def has_cycle(task_id):
            visited.add(task_id)
            rec_stack.add(task_id)
            
            for dep in dependency_graph.get(task_id, set()):
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True
            
            rec_stack.remove(task_id)
            return False
        
        for task_id in dependency_graph:
            if task_id not in visited:
                if has_cycle(task_id):
                    return True
        
        return False


class RollbackStrategyManager:
    """
    Manages different rollback strategies and selects appropriate strategy
    """
    
    def __init__(self, rollback_manager: RollbackManager):
        self.rollback_manager = rollback_manager
        self.strategies = {
            RollbackStrategyType.FULL: FullRollbackStrategy(rollback_manager),
            RollbackStrategyType.PARTIAL: PartialRollbackStrategy(rollback_manager),
            RollbackStrategyType.SELECTIVE: SelectiveRollbackStrategy(rollback_manager)
        }
        
        # Strategy selection rules
        self.selection_rules = []
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Setup default strategy selection rules"""
        # Rule: Use full rollback for system-wide failures
        self.add_selection_rule(
            lambda scope: len(scope.components) >= len(ComponentType) * 0.7,
            RollbackStrategyType.FULL,
            "System-wide failure detected"
        )
        
        # Rule: Use selective for task-specific rollbacks
        self.add_selection_rule(
            lambda scope: len(scope.task_ids) > 0 and len(scope.components) == 0,
            RollbackStrategyType.SELECTIVE,
            "Task-specific rollback requested"
        )
        
        # Rule: Use partial for component-specific rollbacks
        self.add_selection_rule(
            lambda scope: len(scope.components) > 0 and len(scope.components) < len(ComponentType) * 0.5,
            RollbackStrategyType.PARTIAL,
            "Component-specific rollback requested"
        )
    
    def add_selection_rule(
        self,
        condition: Callable[[RollbackScope], bool],
        strategy_type: RollbackStrategyType,
        reason: str
    ):
        """Add a strategy selection rule"""
        self.selection_rules.append((condition, strategy_type, reason))
    
    def select_strategy(self, scope: RollbackScope) -> Tuple[RollbackStrategyType, str]:
        """Select appropriate rollback strategy based on scope"""
        # Check rules in order
        for condition, strategy_type, reason in self.selection_rules:
            if condition(scope):
                logger.info(f"Selected {strategy_type.value} strategy: {reason}")
                return strategy_type, reason
        
        # Default to partial rollback
        return RollbackStrategyType.PARTIAL, "Default strategy"
    
    def create_rollback_plan(self, scope: RollbackScope) -> RollbackPlan:
        """Create rollback plan using appropriate strategy"""
        strategy_type, reason = self.select_strategy(scope)
        
        # Override if explicitly specified in scope
        if scope.strategy_type:
            strategy_type = scope.strategy_type
            logger.info(f"Using explicitly specified strategy: {strategy_type.value}")
        
        strategy = self.strategies.get(strategy_type)
        if not strategy:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        
        # Validate scope
        is_valid, errors = strategy.validate_rollback_scope(scope)
        if not is_valid:
            raise ValueError(f"Invalid rollback scope: {errors}")
        
        # Create plan
        plan = strategy.create_rollback_plan(scope)
        plan.metadata["strategy_selection_reason"] = reason
        
        return plan
    
    def execute_rollback(self, plan: RollbackPlan) -> Tuple[bool, Dict[str, Any]]:
        """Execute rollback plan using appropriate strategy"""
        strategy_type = plan.scope.strategy_type
        strategy = self.strategies.get(strategy_type)
        
        if not strategy:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        
        return strategy.execute_rollback(plan)
    
    def get_strategy(self, strategy_type: RollbackStrategyType) -> RollbackStrategy:
        """Get a specific rollback strategy"""
        return self.strategies.get(strategy_type)


# Convenience functions
def create_rollback_scope(
    strategy_type: Optional[RollbackStrategyType] = None,
    components: Optional[List[str]] = None,
    task_ids: Optional[List[str]] = None,
    exclude_components: Optional[List[str]] = None
) -> RollbackScope:
    """
    Create a rollback scope
    
    Args:
        strategy_type: Type of rollback strategy
        components: List of component names to rollback
        task_ids: List of task IDs to rollback
        exclude_components: List of components to exclude
        
    Returns:
        RollbackScope instance
    """
    scope = RollbackScope(
        strategy_type=strategy_type or RollbackStrategyType.PARTIAL
    )
    
    if components:
        scope.components = {ComponentType(c) for c in components}
    
    if task_ids:
        scope.task_ids = set(task_ids)
    
    if exclude_components:
        scope.exclude_components = {ComponentType(c) for c in exclude_components}
    
    return scope