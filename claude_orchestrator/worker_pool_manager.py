"""
Worker Pool Management System
Manages worker pools with advanced state tracking, scaling, and resource management
"""

import logging
import time
import threading
from typing import Dict, List, Any, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import asyncio
import json
from .dynamic_worker_allocation import (
    DynamicWorkerAllocator, WorkerProfile, TaskRequirements, 
    WorkerCapability, TaskComplexity, dynamic_allocator
)

logger = logging.getLogger(__name__)


class WorkerState(Enum):
    """Worker state enumeration"""
    IDLE = "idle"
    BUSY = "busy"
    STARTING = "starting"
    STOPPING = "stopping"
    FAILED = "failed"
    OFFLINE = "offline"


class PoolScalingPolicy(Enum):
    """Pool scaling policies"""
    CONSERVATIVE = "conservative"  # Scale slowly, keep resources low
    BALANCED = "balanced"         # Balance between performance and resources
    AGGRESSIVE = "aggressive"     # Scale quickly for performance
    CUSTOM = "custom"            # Use custom scaling rules


@dataclass
class WorkerMetrics:
    """Detailed worker metrics"""
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    average_response_time: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    last_heartbeat: Optional[datetime] = None
    uptime: timedelta = timedelta()
    error_count: int = 0
    last_error: Optional[str] = None
    throughput_per_minute: float = 0.0


@dataclass
class PoolConfiguration:
    """Worker pool configuration"""
    min_workers: int = 1
    max_workers: int = 10
    target_utilization: float = 0.7
    scaling_policy: PoolScalingPolicy = PoolScalingPolicy.BALANCED
    scale_up_threshold: float = 0.8
    scale_down_threshold: float = 0.3
    scale_up_cooldown: int = 300  # seconds
    scale_down_cooldown: int = 600  # seconds
    health_check_interval: int = 60  # seconds
    max_idle_time: int = 1800  # seconds (30 minutes)
    failure_threshold: int = 3
    recovery_timeout: int = 900  # seconds (15 minutes)


@dataclass
class WorkerPoolStats:
    """Worker pool statistics"""
    total_workers: int = 0
    active_workers: int = 0
    idle_workers: int = 0
    failed_workers: int = 0
    total_tasks_processed: int = 0
    current_queue_size: int = 0
    average_queue_time: float = 0.0
    pool_utilization: float = 0.0
    scaling_events: int = 0
    last_scaling_event: Optional[datetime] = None


class WorkerPool:
    """
    Manages a pool of workers with advanced state tracking and scaling
    """
    
    def __init__(self, 
                 pool_name: str,
                 config: PoolConfiguration,
                 allocator: DynamicWorkerAllocator):
        self.pool_name = pool_name
        self.config = config
        self.allocator = allocator
        
        # Worker management
        self.workers: Dict[str, WorkerProfile] = {}
        self.worker_states: Dict[str, WorkerState] = {}
        self.worker_metrics: Dict[str, WorkerMetrics] = {}
        
        # Task management
        self.task_queue: deque = deque()
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.completed_tasks: List[Dict[str, Any]] = []
        
        # Scaling management
        self.last_scale_up: Optional[datetime] = None
        self.last_scale_down: Optional[datetime] = None
        self.scaling_history: List[Dict[str, Any]] = []
        
        # Statistics
        self.stats = WorkerPoolStats()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Background tasks
        self._monitoring_active = False
        self._monitoring_thread: Optional[threading.Thread] = None
        
        logger.info(f"Worker pool '{pool_name}' initialized with config: {config}")
    
    def start_monitoring(self):
        """Start background monitoring tasks"""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name=f"WorkerPool-{self.pool_name}-Monitor"
        )
        self._monitoring_thread.start()
        logger.info(f"Started monitoring for pool '{self.pool_name}'")
    
    def stop_monitoring(self):
        """Stop background monitoring tasks"""
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        logger.info(f"Stopped monitoring for pool '{self.pool_name}'")
    
    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self._monitoring_active:
            try:
                self._perform_health_checks()
                self._update_statistics()
                self._check_scaling_conditions()
                self._cleanup_idle_workers()
                time.sleep(self.config.health_check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop for pool '{self.pool_name}': {e}")
                time.sleep(5)
    
    def add_worker(self, worker_profile: WorkerProfile) -> bool:
        """Add a worker to the pool"""
        with self._lock:
            if worker_profile.worker_id in self.workers:
                logger.warning(f"Worker {worker_profile.worker_id} already exists in pool")
                return False
            
            self.workers[worker_profile.worker_id] = worker_profile
            self.worker_states[worker_profile.worker_id] = WorkerState.IDLE
            self.worker_metrics[worker_profile.worker_id] = WorkerMetrics(
                last_heartbeat=datetime.now()
            )
            
            # Register with allocator
            self.allocator.register_worker(
                worker_profile.worker_id,
                worker_profile.model_name,
                worker_profile.capabilities,
                worker_profile.max_complexity,
                worker_profile.max_concurrent_tasks
            )
            
            logger.info(f"Added worker {worker_profile.worker_id} to pool '{self.pool_name}'")
            return True
    
    def remove_worker(self, worker_id: str, force: bool = False) -> bool:
        """Remove a worker from the pool"""
        with self._lock:
            if worker_id not in self.workers:
                logger.warning(f"Worker {worker_id} not found in pool")
                return False
            
            worker_state = self.worker_states.get(worker_id)
            
            if worker_state == WorkerState.BUSY and not force:
                logger.warning(f"Cannot remove busy worker {worker_id} without force=True")
                return False
            
            # Cancel active tasks if forced
            if force:
                self._cancel_worker_tasks(worker_id)
            
            # Remove from all tracking structures
            del self.workers[worker_id]
            del self.worker_states[worker_id]
            del self.worker_metrics[worker_id]
            
            # Unregister from allocator
            self.allocator.unregister_worker(worker_id)
            
            logger.info(f"Removed worker {worker_id} from pool '{self.pool_name}'")
            return True
    
    def assign_task(self, task_id: str, task_title: str, 
                   task_description: str, 
                   task_requirements: Optional[TaskRequirements] = None,
                   priority: int = 5) -> Optional[str]:
        """Assign a task to an available worker"""
        with self._lock:
            # Try to allocate a worker
            worker_id = self.allocator.allocate_worker(
                task_id, task_title, task_description, task_requirements
            )
            
            if not worker_id:
                # Add to queue if no worker available
                self.task_queue.append({
                    'task_id': task_id,
                    'task_title': task_title,
                    'task_description': task_description,
                    'task_requirements': task_requirements,
                    'priority': priority,
                    'queued_at': datetime.now()
                })
                logger.info(f"Task {task_id} queued (no available workers)")
                return None
            
            # Update worker state
            self.worker_states[worker_id] = WorkerState.BUSY
            
            # Track active task
            self.active_tasks[task_id] = {
                'worker_id': worker_id,
                'task_title': task_title,
                'task_description': task_description,
                'started_at': datetime.now(),
                'priority': priority
            }
            
            logger.info(f"Assigned task {task_id} to worker {worker_id}")
            return worker_id
    
    def complete_task(self, task_id: str, worker_id: str, 
                     success: bool = True, 
                     actual_duration: float = None,
                     error_message: Optional[str] = None) -> bool:
        """Mark a task as completed"""
        with self._lock:
            if task_id not in self.active_tasks:
                logger.warning(f"Task {task_id} not found in active tasks")
                return False
            
            task_info = self.active_tasks[task_id]
            
            # Update worker metrics
            metrics = self.worker_metrics[worker_id]
            metrics.total_tasks += 1
            
            if success:
                metrics.successful_tasks += 1
                self.worker_states[worker_id] = WorkerState.IDLE
            else:
                metrics.failed_tasks += 1
                metrics.error_count += 1
                metrics.last_error = error_message
                
                # Check if worker should be marked as failed
                if metrics.error_count >= self.config.failure_threshold:
                    self.worker_states[worker_id] = WorkerState.FAILED
                    logger.warning(f"Worker {worker_id} marked as failed due to excessive errors")
            
            # Calculate duration and update metrics
            if actual_duration:
                alpha = 0.1  # Exponential moving average factor
                if metrics.average_response_time == 0:
                    metrics.average_response_time = actual_duration
                else:
                    metrics.average_response_time = (
                        alpha * actual_duration + 
                        (1 - alpha) * metrics.average_response_time
                    )
            
            # Update heartbeat
            metrics.last_heartbeat = datetime.now()
            
            # Release worker in allocator
            self.allocator.release_worker(worker_id, task_id, success, actual_duration)
            
            # Move task to completed
            completed_task = task_info.copy()
            completed_task.update({
                'completed_at': datetime.now(),
                'success': success,
                'duration': actual_duration,
                'error_message': error_message
            })
            self.completed_tasks.append(completed_task)
            
            # Remove from active tasks
            del self.active_tasks[task_id]
            
            # Try to assign queued tasks
            self._process_queue()
            
            logger.info(f"Completed task {task_id} on worker {worker_id} (success: {success})")
            return True
    
    def _process_queue(self):
        """Process queued tasks"""
        while self.task_queue:
            # Sort queue by priority (higher priority first)
            sorted_queue = sorted(
                self.task_queue, 
                key=lambda x: (x['priority'], x['queued_at']), 
                reverse=True
            )
            
            for task in sorted_queue:
                worker_id = self.allocator.allocate_worker(
                    task['task_id'],
                    task['task_title'],
                    task['task_description'],
                    task['task_requirements']
                )
                
                if worker_id:
                    # Remove from queue
                    self.task_queue.remove(task)
                    
                    # Update worker state
                    self.worker_states[worker_id] = WorkerState.BUSY
                    
                    # Track active task
                    self.active_tasks[task['task_id']] = {
                        'worker_id': worker_id,
                        'task_title': task['task_title'],
                        'task_description': task['task_description'],
                        'started_at': datetime.now(),
                        'priority': task['priority'],
                        'queue_time': (datetime.now() - task['queued_at']).total_seconds()
                    }
                    
                    logger.info(f"Assigned queued task {task['task_id']} to worker {worker_id}")
                    break
            else:
                # No workers available for any queued task
                break
    
    def _perform_health_checks(self):
        """Perform health checks on all workers"""
        with self._lock:
            now = datetime.now()
            
            for worker_id, metrics in self.worker_metrics.items():
                if metrics.last_heartbeat:
                    time_since_heartbeat = (now - metrics.last_heartbeat).total_seconds()
                    
                    # Check if worker is unresponsive
                    if time_since_heartbeat > self.config.health_check_interval * 2:
                        current_state = self.worker_states.get(worker_id)
                        if current_state not in [WorkerState.FAILED, WorkerState.OFFLINE]:
                            logger.warning(f"Worker {worker_id} appears unresponsive")
                            self.worker_states[worker_id] = WorkerState.OFFLINE
    
    def _update_statistics(self):
        """Update pool statistics"""
        with self._lock:
            active_count = sum(1 for state in self.worker_states.values() 
                             if state == WorkerState.BUSY)
            idle_count = sum(1 for state in self.worker_states.values() 
                           if state == WorkerState.IDLE)
            failed_count = sum(1 for state in self.worker_states.values() 
                             if state == WorkerState.FAILED)
            
            self.stats.total_workers = len(self.workers)
            self.stats.active_workers = active_count
            self.stats.idle_workers = idle_count
            self.stats.failed_workers = failed_count
            self.stats.current_queue_size = len(self.task_queue)
            
            # Calculate utilization
            if self.stats.total_workers > 0:
                self.stats.pool_utilization = active_count / self.stats.total_workers
            
            # Calculate average queue time
            if self.task_queue:
                now = datetime.now()
                total_queue_time = sum(
                    (now - task['queued_at']).total_seconds() 
                    for task in self.task_queue
                )
                self.stats.average_queue_time = total_queue_time / len(self.task_queue)
    
    def _check_scaling_conditions(self):
        """Check if scaling is needed"""
        with self._lock:
            now = datetime.now()
            utilization = self.stats.pool_utilization
            
            # Check scale up conditions
            should_scale_up = (
                utilization > self.config.scale_up_threshold and
                self.stats.total_workers < self.config.max_workers and
                (not self.last_scale_up or 
                 (now - self.last_scale_up).total_seconds() > self.config.scale_up_cooldown)
            )
            
            # Check scale down conditions
            should_scale_down = (
                utilization < self.config.scale_down_threshold and
                self.stats.total_workers > self.config.min_workers and
                (not self.last_scale_down or 
                 (now - self.last_scale_down).total_seconds() > self.config.scale_down_cooldown)
            )
            
            if should_scale_up:
                self._scale_up()
            elif should_scale_down:
                self._scale_down()
    
    def _scale_up(self):
        """Scale up the worker pool"""
        with self._lock:
            if self.stats.total_workers >= self.config.max_workers:
                return
            
            # Determine how many workers to add based on scaling policy
            workers_to_add = self._calculate_scale_up_count()
            
            for i in range(workers_to_add):
                if self.stats.total_workers >= self.config.max_workers:
                    break
                
                # Create new worker (this would typically involve spawning a new worker process)
                worker_id = f"{self.pool_name}-worker-{len(self.workers) + 1}"
                
                # Create a default worker profile
                new_worker = WorkerProfile(
                    worker_id=worker_id,
                    model_name="claude-3-5-sonnet-20241022",  # Default model
                    capabilities={WorkerCapability.CODE, WorkerCapability.RESEARCH},
                    max_complexity=TaskComplexity.HIGH
                )
                
                self.add_worker(new_worker)
            
            self.last_scale_up = datetime.now()
            self.stats.scaling_events += 1
            self.stats.last_scaling_event = datetime.now()
            
            scaling_event = {
                'timestamp': datetime.now().isoformat(),
                'action': 'scale_up',
                'workers_added': workers_to_add,
                'total_workers': self.stats.total_workers,
                'utilization': self.stats.pool_utilization
            }
            self.scaling_history.append(scaling_event)
            
            logger.info(f"Scaled up pool '{self.pool_name}' by {workers_to_add} workers")
    
    def _scale_down(self):
        """Scale down the worker pool"""
        with self._lock:
            if self.stats.total_workers <= self.config.min_workers:
                return
            
            # Determine how many workers to remove
            workers_to_remove = self._calculate_scale_down_count()
            
            # Find idle workers to remove
            idle_workers = [
                worker_id for worker_id, state in self.worker_states.items()
                if state == WorkerState.IDLE
            ]
            
            removed_count = 0
            for worker_id in idle_workers:
                if removed_count >= workers_to_remove:
                    break
                if self.stats.total_workers <= self.config.min_workers:
                    break
                
                self.remove_worker(worker_id)
                removed_count += 1
            
            if removed_count > 0:
                self.last_scale_down = datetime.now()
                self.stats.scaling_events += 1
                self.stats.last_scaling_event = datetime.now()
                
                scaling_event = {
                    'timestamp': datetime.now().isoformat(),
                    'action': 'scale_down',
                    'workers_removed': removed_count,
                    'total_workers': self.stats.total_workers,
                    'utilization': self.stats.pool_utilization
                }
                self.scaling_history.append(scaling_event)
                
                logger.info(f"Scaled down pool '{self.pool_name}' by {removed_count} workers")
    
    def _calculate_scale_up_count(self) -> int:
        """Calculate how many workers to add based on scaling policy"""
        if self.config.scaling_policy == PoolScalingPolicy.CONSERVATIVE:
            return 1
        elif self.config.scaling_policy == PoolScalingPolicy.BALANCED:
            return min(2, self.config.max_workers - self.stats.total_workers)
        elif self.config.scaling_policy == PoolScalingPolicy.AGGRESSIVE:
            queue_based = max(1, len(self.task_queue) // 2)
            return min(queue_based, self.config.max_workers - self.stats.total_workers)
        else:  # CUSTOM
            return 1
    
    def _calculate_scale_down_count(self) -> int:
        """Calculate how many workers to remove based on scaling policy"""
        if self.config.scaling_policy == PoolScalingPolicy.CONSERVATIVE:
            return min(1, self.stats.total_workers - self.config.min_workers)
        elif self.config.scaling_policy == PoolScalingPolicy.BALANCED:
            return min(1, self.stats.total_workers - self.config.min_workers)
        elif self.config.scaling_policy == PoolScalingPolicy.AGGRESSIVE:
            return min(2, self.stats.total_workers - self.config.min_workers)
        else:  # CUSTOM
            return 1
    
    def _cleanup_idle_workers(self):
        """Clean up workers that have been idle too long"""
        with self._lock:
            now = datetime.now()
            
            for worker_id, state in self.worker_states.items():
                if state == WorkerState.IDLE:
                    metrics = self.worker_metrics[worker_id]
                    if metrics.last_heartbeat:
                        idle_time = (now - metrics.last_heartbeat).total_seconds()
                        if idle_time > self.config.max_idle_time:
                            logger.info(f"Removing idle worker {worker_id} after {idle_time}s")
                            self.remove_worker(worker_id)
    
    def _cancel_worker_tasks(self, worker_id: str):
        """Cancel all tasks assigned to a worker"""
        tasks_to_cancel = [
            task_id for task_id, task_info in self.active_tasks.items()
            if task_info['worker_id'] == worker_id
        ]
        
        for task_id in tasks_to_cancel:
            self.complete_task(task_id, worker_id, success=False, 
                             error_message="Worker removed from pool")
    
    def get_pool_status(self) -> Dict[str, Any]:
        """Get comprehensive pool status"""
        with self._lock:
            worker_details = {}
            for worker_id, worker in self.workers.items():
                metrics = self.worker_metrics[worker_id]
                worker_details[worker_id] = {
                    'state': self.worker_states[worker_id].value,
                    'model': worker.model_name,
                    'capabilities': [cap.value for cap in worker.capabilities],
                    'current_tasks': len(worker.current_tasks),
                    'total_tasks': metrics.total_tasks,
                    'success_rate': metrics.successful_tasks / max(1, metrics.total_tasks),
                    'average_response_time': metrics.average_response_time,
                    'last_heartbeat': metrics.last_heartbeat.isoformat() if metrics.last_heartbeat else None
                }
            
            return {
                'pool_name': self.pool_name,
                'config': {
                    'min_workers': self.config.min_workers,
                    'max_workers': self.config.max_workers,
                    'scaling_policy': self.config.scaling_policy.value,
                    'target_utilization': self.config.target_utilization
                },
                'statistics': {
                    'total_workers': self.stats.total_workers,
                    'active_workers': self.stats.active_workers,
                    'idle_workers': self.stats.idle_workers,
                    'failed_workers': self.stats.failed_workers,
                    'queue_size': self.stats.current_queue_size,
                    'utilization': self.stats.pool_utilization,
                    'average_queue_time': self.stats.average_queue_time,
                    'scaling_events': self.stats.scaling_events
                },
                'workers': worker_details,
                'active_tasks': len(self.active_tasks),
                'completed_tasks': len(self.completed_tasks)
            }


class WorkerPoolManager:
    """
    Central manager for multiple worker pools
    """
    
    def __init__(self, allocator: Optional[DynamicWorkerAllocator] = None):
        self.allocator = allocator or dynamic_allocator
        self.pools: Dict[str, WorkerPool] = {}
        self._lock = threading.RLock()
        
        logger.info("Worker pool manager initialized")
    
    def create_pool(self, pool_name: str, config: PoolConfiguration) -> WorkerPool:
        """Create a new worker pool"""
        with self._lock:
            if pool_name in self.pools:
                raise ValueError(f"Pool '{pool_name}' already exists")
            
            pool = WorkerPool(pool_name, config, self.allocator)
            self.pools[pool_name] = pool
            
            # Start monitoring
            pool.start_monitoring()
            
            logger.info(f"Created worker pool '{pool_name}'")
            return pool
    
    def get_pool(self, pool_name: str) -> Optional[WorkerPool]:
        """Get a worker pool by name"""
        return self.pools.get(pool_name)
    
    def remove_pool(self, pool_name: str) -> bool:
        """Remove a worker pool"""
        with self._lock:
            if pool_name not in self.pools:
                return False
            
            pool = self.pools[pool_name]
            pool.stop_monitoring()
            
            # Remove all workers
            for worker_id in list(pool.workers.keys()):
                pool.remove_worker(worker_id, force=True)
            
            del self.pools[pool_name]
            logger.info(f"Removed worker pool '{pool_name}'")
            return True
    
    def get_all_pools_status(self) -> Dict[str, Any]:
        """Get status of all pools"""
        with self._lock:
            pools_status = {}
            for pool_name, pool in self.pools.items():
                pools_status[pool_name] = pool.get_pool_status()
            
            return {
                'total_pools': len(self.pools),
                'pools': pools_status
            }
    
    def shutdown(self):
        """Shutdown all pools"""
        with self._lock:
            for pool_name in list(self.pools.keys()):
                self.remove_pool(pool_name)
            logger.info("Worker pool manager shut down")


# Global worker pool manager instance
worker_pool_manager = WorkerPoolManager()