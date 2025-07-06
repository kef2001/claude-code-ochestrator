#!/usr/bin/env python3
"""Opus Manager - Manager component using Claude Opus model.

This module contains the OpusManager class which uses the Claude Opus model
to analyze tasks, create execution plans, and delegate work to Sonnet workers.
The manager is responsible for understanding task dependencies and orchestrating
the parallel execution of independent tasks.

The OpusManager handles:
- Task analysis and dependency resolution
- Task prioritization and delegation
- Progress monitoring
- Task queue management

Typical usage example:
    manager = OpusManager(config)
    tasks = manager.analyze_and_plan()
    for task in tasks:
        manager.delegate_task(task)
"""

import sys
import queue
import logging
from typing import Dict, List, Optional
from datetime import datetime

from .models import TaskStatus, WorkerTask
from .orchestrator import TaskMasterInterface

logger = logging.getLogger(__name__)


class OpusManager:
    """Opus model acting as the manager/orchestrator"""
    
    def __init__(self, config):
        self.config = config
        # Add execution validation flag if not present
        if not hasattr(self.config, 'validate_execution'):
            self.config.validate_execution = True
        self.max_workers = config.max_workers
        self.task_master = TaskMasterInterface()
        self.task_queue: queue.Queue[WorkerTask] = queue.Queue()
        self.completed_tasks: Dict[str, WorkerTask] = {}
        self.failed_tasks: Dict[str, WorkerTask] = {}
        self.active_tasks: Dict[str, WorkerTask] = {}
        
    def analyze_and_plan(self) -> List[WorkerTask]:
        """Use Opus to analyze tasks and create execution plan"""
        logger.info("Opus Manager: Analyzing project tasks...")
        
        # Show loading indicator
        sys.stdout.write("⏳ Fetching tasks from Task Master...")
        sys.stdout.flush()
        
        # Get all tasks from Task Master
        all_tasks = self.task_master.list_tasks()
        
        sys.stdout.write("\r✅ Fetched tasks from Task Master" + " " * 20 + "\n")
        sys.stdout.flush()
        
        if not all_tasks:
            logger.warning("No tasks found in Task Master")
            return []
        
        # Convert Task Master tasks to WorkerTasks
        sys.stdout.write("🔍 Analyzing task dependencies and priorities...")
        sys.stdout.flush()
        
        worker_tasks = []
        for task in all_tasks:
            if task.get('status') in ['pending', 'in-progress']:
                worker_task = WorkerTask(
                    task_id=task.get('id', ''),
                    title=task.get('title', ''),
                    description=task.get('description', ''),
                    details=task.get('details'),
                    dependencies=[str(d) for d in task.get('dependencies', [])]
                )
                worker_tasks.append(worker_task)
        
        sys.stdout.write(f"\r✅ Found {len(worker_tasks)} tasks ready for processing" + " " * 30 + "\n")
        sys.stdout.flush()
        
        # Sort tasks by dependencies and priority
        sorted_tasks = self._sort_tasks_by_dependencies(worker_tasks)
        
        # Collect feedback for task planning decision
        if hasattr(self, 'feedback_collector') and self.feedback_collector:
            try:
                from .feedback_model import FeedbackType, FeedbackCategory
                feedback_id = self.feedback_collector.collect_feedback(
                    feedback_type=FeedbackType.DECISION,
                    category=FeedbackCategory.PLANNING,
                    message=f"Task planning completed: {len(sorted_tasks)} tasks prepared",
                    context={
                        "total_tasks": len(all_tasks),
                        "ready_tasks": len(worker_tasks),
                        "sorted_tasks": len(sorted_tasks),
                        "phase": "task_decomposition"
                    },
                    worker_id="opus_manager",
                    session_id=str(id(self))
                )
                logger.debug(f"Collected planning feedback: {feedback_id}")
            except Exception as e:
                logger.debug(f"Failed to collect planning feedback: {e}")
        
        logger.info(f"Opus Manager: Prepared {len(sorted_tasks)} tasks for parallel execution")
        return sorted_tasks
    
    def _sort_tasks_by_dependencies(self, tasks: List[WorkerTask]) -> List[WorkerTask]:
        """Sort tasks ensuring dependencies come first"""
        # Create a map of task_id to task
        task_map = {task.task_id: task for task in tasks}
        
        # Perform topological sort
        sorted_tasks = []
        visited = set()
        
        def visit(task_id: str):
            if task_id in visited:
                return
            visited.add(task_id)
            
            task = task_map.get(task_id)
            if not task:
                return
                
            # Visit dependencies first
            for dep_id in task.dependencies:
                if dep_id in task_map:
                    visit(dep_id)
            
            sorted_tasks.append(task)
        
        # Visit all tasks
        for task in tasks:
            visit(task.task_id)
        
        return sorted_tasks
    
    def delegate_task(self, task: WorkerTask):
        """Add task to the queue for workers to process"""
        logger.debug(f"Delegating task {task.task_id} to worker queue")
        
        # Collect feedback for worker allocation decision
        if hasattr(self, 'feedback_collector') and self.feedback_collector:
            try:
                from .feedback_model import FeedbackType, FeedbackCategory
                feedback_id = self.feedback_collector.collect_feedback(
                    feedback_type=FeedbackType.DECISION,
                    category=FeedbackCategory.EXECUTION,
                    message=f"Task {task.task_id} delegated to worker pool",
                    context={
                        "task_id": str(task.task_id),
                        "task_title": task.title,
                        "dependencies": task.dependencies,
                        "phase": "worker_allocation",
                        "queue_size": self.task_queue.qsize()
                    },
                    worker_id="task_manager",
                    session_id=str(id(self))
                )
                logger.debug(f"Collected delegation feedback: {feedback_id}")
            except Exception as e:
                logger.debug(f"Failed to collect delegation feedback: {e}")
        
        self.task_queue.put(task)
    
    def monitor_progress(self):
        """Monitor and report on worker progress"""
        active_count = len(self.active_tasks)
        completed_count = len(self.completed_tasks)
        failed_count = len(self.failed_tasks)
        
        logger.info(f"Progress: Active: {active_count}, Completed: {completed_count}, Failed: {failed_count}")
        
        if active_count > 0:
            logger.info("Active tasks:")
            for task_id, task in self.active_tasks.items():
                logger.info(f"  - {task_id}: {task.title} (Worker {task.assigned_worker})")


