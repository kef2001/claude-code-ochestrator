"""
Enhanced Claude Orchestrator with Agent Building Best Practices
Integrates all improvements: circuit breakers, validation, checkpoints, 
dynamic allocation, evaluation-optimization, tracing, and decomposition
"""

import logging
import asyncio
import threading
import time
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path

# Import all the new components
from .circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, circuit_breaker_manager,
    CircuitBreakerOpenException, CircuitBreakerTimeoutException
)
from .task_validator import (
    TaskValidator, ValidationLevel, ValidationResult, ValidationReportManager
)
from .checkpoint_system import (
    CheckpointManager, TaskCheckpointWrapper, checkpoint_manager
)
from .dynamic_worker_allocation import (
    DynamicWorkerAllocator, TaskComplexityAnalyzer, WorkerCapability,
    TaskComplexity, dynamic_allocator
)
from .evaluator_optimizer import (
    EvaluatorOptimizer, EvaluationCriteria, evaluator_optimizer
)
from .execution_tracer import (
    ExecutionTracer, TraceEventType, TraceLevel, execution_tracer
)
from .task_decomposer import (
    TaskDecomposer, DecompositionStrategy, task_decomposer
)

# Import existing components
from .task_master import TaskManager, Task as TMTask, TaskStatus as TMTaskStatus
from .config_manager import ConfigurationManager, EnhancedConfig

logger = logging.getLogger(__name__)


class EnhancedTaskStatus(Enum):
    """Enhanced task status with more granular states"""
    PENDING = "pending"
    ANALYZING = "analyzing"
    DECOMPOSING = "decomposing"
    ALLOCATED = "allocated"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    OPTIMIZING = "optimizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class EnhancedTaskContext:
    """Enhanced context for task execution"""
    task_id: str
    original_task: TMTask
    worker_id: Optional[str] = None
    trace_id: Optional[str] = None
    checkpoint_wrapper: Optional[TaskCheckpointWrapper] = None
    circuit_breaker: Optional[CircuitBreaker] = None
    decomposition_plan: Optional[Any] = None  # DecompositionPlan
    evaluation_cycles: List[Any] = field(default_factory=list)  # IterationCycle
    retry_count: int = 0
    max_retries: int = 3
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: EnhancedTaskStatus = EnhancedTaskStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)


class EnhancedClaudeOrchestrator:
    """
    Enhanced orchestrator with all agent building best practices
    """
    
    def __init__(self, config_manager: ConfigurationManager = None):
        self.config_manager = config_manager or ConfigurationManager()
        self.config = EnhancedConfig(self.config_manager)
        
        # Initialize all components
        self.task_manager = TaskManager()
        self.validator = TaskValidator(ValidationLevel.STANDARD)
        self.validation_report_manager = ValidationReportManager()
        
        # Enhanced components
        self.dynamic_allocator = dynamic_allocator
        self.evaluator_optimizer = evaluator_optimizer
        self.execution_tracer = execution_tracer
        self.task_decomposer = task_decomposer
        self.checkpoint_manager = checkpoint_manager
        self.circuit_breaker_manager = circuit_breaker_manager
        
        # Task tracking
        self.active_tasks: Dict[str, EnhancedTaskContext] = {}
        self.completed_tasks: List[EnhancedTaskContext] = []
        
        # Performance metrics
        self.metrics = {
            "tasks_processed": 0,
            "tasks_successful": 0,
            "tasks_failed": 0,
            "total_processing_time_ms": 0,
            "average_processing_time_ms": 0,
            "circuit_breaker_activations": 0,
            "optimizations_performed": 0,
            "decompositions_created": 0
        }
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Initialize worker profiles
        self._initialize_workers()
        
        logger.info("Enhanced Claude Orchestrator initialized with all improvements")
    
    def _initialize_workers(self):
        """Initialize worker profiles with capabilities"""
        # Register Opus manager
        self.dynamic_allocator.register_worker(
            worker_id="opus_manager",
            model_name="claude-3-opus-20240229",
            capabilities={
                WorkerCapability.DESIGN,
                WorkerCapability.RESEARCH,
                WorkerCapability.REVIEW
            },
            max_complexity=TaskComplexity.CRITICAL,
            max_concurrent_tasks=2
        )
        
        # Register Sonnet workers
        for i in range(self.config.max_workers):
            worker_id = f"sonnet_worker_{i+1}"
            self.dynamic_allocator.register_worker(
                worker_id=worker_id,
                model_name="claude-3-5-sonnet-20241022",
                capabilities={
                    WorkerCapability.CODE,
                    WorkerCapability.REFACTORING,
                    WorkerCapability.DEBUGGING,
                    WorkerCapability.TESTING,
                    WorkerCapability.DOCUMENTATION
                },
                max_complexity=TaskComplexity.HIGH,
                max_concurrent_tasks=1
            )
            
            # Create circuit breaker for each worker
            circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(
                worker_id,
                CircuitBreakerConfig(
                    failure_threshold=3,
                    recovery_timeout=60,
                    timeout=self.config.worker_timeout
                )
            )
    
    async def process_task_enhanced(self, task_id: str, 
                                  auto_decompose: bool = True,
                                  auto_optimize: bool = True,
                                  validation_level: ValidationLevel = ValidationLevel.STANDARD) -> EnhancedTaskContext:
        """
        Process a task with all enhancements
        
        Args:
            task_id: Task identifier
            auto_decompose: Whether to automatically decompose complex tasks
            auto_optimize: Whether to use evaluation-optimization cycles
            validation_level: Level of result validation
            
        Returns:
            EnhancedTaskContext with execution results
        """
        with self._lock:
            # Get original task
            original_task = self.task_manager.get_task(task_id)
            if not original_task:
                raise ValueError(f"Task {task_id} not found")
            
            # Create enhanced context
            context = EnhancedTaskContext(
                task_id=task_id,
                original_task=original_task,
                started_at=datetime.now()
            )
            
            self.active_tasks[task_id] = context
        
        try:
            # Start execution trace
            context.trace_id = self.execution_tracer.start_trace(
                task_id, 
                original_task.title
            )
            
            # Step 1: Analyze task complexity
            await self._analyze_task_complexity(context)
            
            # Step 2: Decompose if needed
            if auto_decompose:
                await self._handle_task_decomposition(context)
            
            # Step 3: Allocate worker
            await self._allocate_worker_enhanced(context)
            
            # Step 4: Execute with monitoring
            await self._execute_task_enhanced(context)
            
            # Step 5: Validate results
            await self._validate_task_results(context, validation_level)
            
            # Step 6: Optimize if needed
            if auto_optimize and not context.evaluation_cycles:
                await self._optimize_task_results(context)
            
            # Mark as completed
            context.status = EnhancedTaskStatus.COMPLETED
            context.completed_at = datetime.now()
            
            self._update_metrics(context, success=True)
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            context.status = EnhancedTaskStatus.FAILED
            context.metadata["error"] = str(e)
            
            self._update_metrics(context, success=False)
            
            # Try recovery strategies
            if context.retry_count < context.max_retries:
                return await self._retry_task_enhanced(context, e)
            
            raise
        
        finally:
            # Complete trace
            self.execution_tracer.complete_trace(
                context.trace_id,
                success=(context.status == EnhancedTaskStatus.COMPLETED)
            )
            
            # Release worker
            if context.worker_id:
                self.dynamic_allocator.release_worker(
                    context.worker_id,
                    task_id,
                    success=(context.status == EnhancedTaskStatus.COMPLETED)
                )
            
            # Move to completed tasks
            with self._lock:
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
                self.completed_tasks.append(context)
        
        return context
    
    async def _analyze_task_complexity(self, context: EnhancedTaskContext):
        """Analyze task complexity and requirements"""
        context.status = EnhancedTaskStatus.ANALYZING
        
        self.execution_tracer.add_event(
            trace_id=context.trace_id,
            task_id=context.task_id,
            event_type=TraceEventType.CUSTOM_EVENT,
            details={"step": "analyzing_complexity"}
        )
        
        # Use the task complexity analyzer from dynamic allocation
        complexity_analyzer = TaskComplexityAnalyzer()
        task_requirements = complexity_analyzer.analyze_task(
            context.original_task.description,
            context.original_task.title
        )
        
        context.metadata["task_requirements"] = {
            "complexity": task_requirements.complexity.value,
            "estimated_duration": task_requirements.estimated_duration,
            "required_capabilities": [cap.value for cap in task_requirements.required_capabilities],
            "resource_score": task_requirements.get_resource_score()
        }
        
        logger.info(f"Task {context.task_id} analyzed: complexity={task_requirements.complexity.value}")
    
    async def _handle_task_decomposition(self, context: EnhancedTaskContext):
        """Handle automatic task decomposition"""
        context.status = EnhancedTaskStatus.DECOMPOSING
        
        self.execution_tracer.add_event(
            trace_id=context.trace_id,
            task_id=context.task_id,
            event_type=TraceEventType.CUSTOM_EVENT,
            details={"step": "decomposing_task"}
        )
        
        # Check if task should be decomposed
        task_requirements = context.metadata.get("task_requirements", {})
        complexity = task_requirements.get("complexity", "medium")
        estimated_duration = task_requirements.get("estimated_duration", 30)
        
        # Decompose if complex or long-running
        if complexity in ["high", "critical"] or estimated_duration > 90:
            decomposition_plan = self.task_decomposer.decompose_task(
                context.task_id,
                context.original_task.title,
                context.original_task.description,
                estimated_duration
            )
            
            context.decomposition_plan = decomposition_plan
            context.metadata["decomposed"] = True
            context.metadata["subtask_count"] = len(decomposition_plan.subtasks)
            
            self.metrics["decompositions_created"] += 1
            
            logger.info(f"Task {context.task_id} decomposed into {len(decomposition_plan.subtasks)} subtasks")
        else:
            context.metadata["decomposed"] = False
            logger.info(f"Task {context.task_id} does not need decomposition")
    
    async def _allocate_worker_enhanced(self, context: EnhancedTaskContext):
        """Allocate worker using dynamic allocation"""
        context.status = EnhancedTaskStatus.ALLOCATED
        
        self.execution_tracer.add_event(
            trace_id=context.trace_id,
            task_id=context.task_id,
            event_type=TraceEventType.WORKER_ASSIGNED,
            details={"step": "allocating_worker"}
        )
        
        # Get worker from dynamic allocator
        worker_id = self.dynamic_allocator.allocate_worker(
            context.task_id,
            context.original_task.title,
            context.original_task.description
        )
        
        if not worker_id:
            raise RuntimeError(f"No suitable worker available for task {context.task_id}")
        
        context.worker_id = worker_id
        
        # Get circuit breaker for worker
        context.circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(worker_id)
        
        # Create checkpoint wrapper
        context.checkpoint_wrapper = TaskCheckpointWrapper(
            self.checkpoint_manager,
            context.task_id,
            context.original_task.title,
            worker_id
        )
        
        logger.info(f"Allocated worker {worker_id} to task {context.task_id}")
    
    async def _execute_task_enhanced(self, context: EnhancedTaskContext):
        """Execute task with enhanced monitoring and resilience"""
        context.status = EnhancedTaskStatus.IN_PROGRESS
        
        self.execution_tracer.add_event(
            trace_id=context.trace_id,
            task_id=context.task_id,
            event_type=TraceEventType.TASK_STARTED,
            worker_id=context.worker_id
        )
        
        try:
            # Execute with circuit breaker protection
            result = await self._execute_with_circuit_breaker(context)
            context.metadata["execution_result"] = result
            
        except CircuitBreakerOpenException as e:
            logger.warning(f"Circuit breaker open for worker {context.worker_id}: {e}")
            self.metrics["circuit_breaker_activations"] += 1
            raise
        
        except Exception as e:
            self.execution_tracer.add_event(
                trace_id=context.trace_id,
                task_id=context.task_id,
                event_type=TraceEventType.ERROR_OCCURRED,
                worker_id=context.worker_id,
                details={"error": str(e), "error_type": type(e).__name__}
            )
            raise
    
    async def _execute_with_circuit_breaker(self, context: EnhancedTaskContext):
        """Execute task with circuit breaker protection"""
        def execute_task():
            # Simulate task execution (in real implementation, this would call Claude CLI)
            # For now, we'll create a mock result
            return {
                "success": True,
                "files_changed": ["example.py", "test_example.py"],
                "output": "Task completed successfully",
                "execution_time_minutes": 45
            }
        
        # Use circuit breaker to execute
        result = context.circuit_breaker.call(execute_task)
        
        # Create checkpoints during execution
        if context.checkpoint_wrapper:
            context.checkpoint_wrapper.checkpoint(
                "Task execution completed",
                {"result": result}
            )
        
        return result
    
    async def _validate_task_results(self, context: EnhancedTaskContext, 
                                   validation_level: ValidationLevel):
        """Validate task results"""
        context.status = EnhancedTaskStatus.VALIDATING
        
        self.execution_tracer.add_event(
            trace_id=context.trace_id,
            task_id=context.task_id,
            event_type=TraceEventType.VALIDATION_PERFORMED,
            worker_id=context.worker_id
        )
        
        # Set validation level
        self.validator.validation_level = validation_level
        
        # Validate results
        execution_result = context.metadata.get("execution_result", {})
        validation_report = self.validator.validate_task_result(
            context.task_id,
            context.original_task.title,
            context.original_task.description,
            execution_result
        )
        
        # Save validation report
        report_path = self.validation_report_manager.save_report(validation_report)
        
        context.metadata["validation_report"] = {
            "overall_result": validation_report.overall_result.value,
            "is_valid": validation_report.is_valid(),
            "error_count": len(validation_report.errors),
            "warning_count": len(validation_report.warnings),
            "report_path": report_path
        }
        
        if not validation_report.is_valid():
            logger.warning(f"Task {context.task_id} failed validation: {validation_report.get_summary()}")
            context.metadata["validation_failed"] = True
        else:
            logger.info(f"Task {context.task_id} passed validation")
    
    async def _optimize_task_results(self, context: EnhancedTaskContext):
        """Optimize task results using evaluation-optimization cycle"""
        context.status = EnhancedTaskStatus.OPTIMIZING
        
        # Only optimize if validation failed or quality is below threshold
        validation_report = context.metadata.get("validation_report", {})
        if validation_report.get("is_valid", True) and validation_report.get("error_count", 0) == 0:
            logger.info(f"Task {context.task_id} passed validation, skipping optimization")
            return
        
        self.execution_tracer.add_event(
            trace_id=context.trace_id,
            task_id=context.task_id,
            event_type=TraceEventType.CUSTOM_EVENT,
            details={"step": "optimizing_results"}
        )
        
        # Run evaluation-optimization cycle
        execution_result = context.metadata.get("execution_result", {})
        iteration_cycle = self.evaluator_optimizer.run_evaluation_cycle(
            context.task_id,
            context.original_task.description,
            execution_result,
            evaluator_id="system",
            optimizer_id="system"
        )
        
        context.evaluation_cycles.append(iteration_cycle)
        
        # Check if optimization is needed
        if iteration_cycle.optimization_plan:
            self.metrics["optimizations_performed"] += 1
            logger.info(f"Created optimization plan for task {context.task_id}")
            
            # In a real implementation, we would re-execute the task with optimizations
            # For now, we'll just record that optimization was planned
            context.metadata["optimization_planned"] = True
            context.metadata["optimization_strategies"] = [
                strategy.value for strategy in iteration_cycle.optimization_plan.strategies
            ]
    
    async def _retry_task_enhanced(self, context: EnhancedTaskContext, 
                                 original_error: Exception) -> EnhancedTaskContext:
        """Retry task with enhanced strategies"""
        context.retry_count += 1
        context.status = EnhancedTaskStatus.RETRYING
        
        self.execution_tracer.add_event(
            trace_id=context.trace_id,
            task_id=context.task_id,
            event_type=TraceEventType.RETRY_ATTEMPT,
            details={
                "retry_count": context.retry_count,
                "original_error": str(original_error)
            }
        )
        
        # Implement progressive retry strategies
        if isinstance(original_error, CircuitBreakerOpenException):
            # Wait for circuit breaker to recover
            await asyncio.sleep(60)
            
        elif context.retry_count == 1:
            # First retry: try different worker
            if context.worker_id:
                self.dynamic_allocator.release_worker(
                    context.worker_id, 
                    context.task_id, 
                    success=False
                )
            await self._allocate_worker_enhanced(context)
            
        elif context.retry_count == 2:
            # Second retry: decompose if not already done
            if not context.metadata.get("decomposed", False):
                await self._handle_task_decomposition(context)
        
        # Reset status and retry
        context.status = EnhancedTaskStatus.PENDING
        return await self.process_task_enhanced(
            context.task_id,
            auto_decompose=False,  # Don't decompose again
            auto_optimize=True
        )
    
    def _update_metrics(self, context: EnhancedTaskContext, success: bool):
        """Update performance metrics"""
        with self._lock:
            self.metrics["tasks_processed"] += 1
            
            if success:
                self.metrics["tasks_successful"] += 1
            else:
                self.metrics["tasks_failed"] += 1
            
            # Calculate processing time
            if context.started_at and context.completed_at:
                processing_time = (context.completed_at - context.started_at).total_seconds() * 1000
                self.metrics["total_processing_time_ms"] += processing_time
                
                if self.metrics["tasks_processed"] > 0:
                    self.metrics["average_processing_time_ms"] = (
                        self.metrics["total_processing_time_ms"] / self.metrics["tasks_processed"]
                    )
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        with self._lock:
            # Get status from all components
            worker_status = self.dynamic_allocator.get_worker_status()
            circuit_breaker_status = self.circuit_breaker_manager.get_all_health_status()
            checkpoint_status = self.checkpoint_manager.get_checkpoint_summary()
            trace_analytics = self.execution_tracer.get_trace_analytics()
            evaluation_analytics = self.evaluator_optimizer.get_system_analytics()
            
            return {
                "orchestrator_metrics": self.metrics,
                "active_tasks": len(self.active_tasks),
                "completed_tasks": len(self.completed_tasks),
                "worker_status": worker_status,
                "circuit_breakers": circuit_breaker_status,
                "checkpoints": checkpoint_status,
                "execution_traces": trace_analytics,
                "evaluation_system": evaluation_analytics,
                "configuration": {
                    "max_workers": self.config.max_workers,
                    "worker_timeout": self.config.worker_timeout,
                    "validation_enabled": True,
                    "optimization_enabled": True,
                    "decomposition_enabled": True
                }
            }
    
    def get_task_analytics(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Get analytics for tasks within time window"""
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        relevant_tasks = [
            task for task in self.completed_tasks
            if task.started_at and task.started_at >= cutoff_time
        ]
        
        if not relevant_tasks:
            return {"message": "No tasks found in time window"}
        
        # Calculate analytics
        total_tasks = len(relevant_tasks)
        successful_tasks = sum(1 for t in relevant_tasks if t.status == EnhancedTaskStatus.COMPLETED)
        failed_tasks = sum(1 for t in relevant_tasks if t.status == EnhancedTaskStatus.FAILED)
        
        # Decomposition analytics
        decomposed_tasks = sum(1 for t in relevant_tasks if t.metadata.get("decomposed", False))
        
        # Optimization analytics
        optimized_tasks = sum(1 for t in relevant_tasks if t.evaluation_cycles)
        
        # Retry analytics
        retried_tasks = sum(1 for t in relevant_tasks if t.retry_count > 0)
        
        return {
            "time_window_hours": time_window_hours,
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0,
            "decomposed_tasks": decomposed_tasks,
            "decomposition_rate": decomposed_tasks / total_tasks if total_tasks > 0 else 0,
            "optimized_tasks": optimized_tasks,
            "optimization_rate": optimized_tasks / total_tasks if total_tasks > 0 else 0,
            "retried_tasks": retried_tasks,
            "retry_rate": retried_tasks / total_tasks if total_tasks > 0 else 0,
            "average_retry_count": sum(t.retry_count for t in relevant_tasks) / total_tasks if total_tasks > 0 else 0
        }
    
    async def process_multiple_tasks(self, task_ids: List[str],
                                   max_concurrent: int = None) -> List[EnhancedTaskContext]:
        """Process multiple tasks concurrently"""
        max_concurrent = max_concurrent or self.config.max_workers
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_single_task(task_id: str):
            async with semaphore:
                return await self.process_task_enhanced(task_id)
        
        # Process tasks concurrently
        tasks = [process_single_task(task_id) for task_id in task_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Separate successful results from exceptions
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {task_ids[i]} failed: {result}")
            else:
                successful_results.append(result)
        
        return successful_results


# Global enhanced orchestrator instance
enhanced_orchestrator = EnhancedClaudeOrchestrator()