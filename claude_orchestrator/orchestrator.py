#!/usr/bin/env python3
"""
Claude Orchestrator - Main orchestrator coordinating Opus manager and Sonnet workers
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import asdict
import logging
from datetime import datetime
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import shlex
from pathlib import Path
import re
import time
import subprocess

from .models import TaskStatus, WorkerTask
from .progress_display_integration import ProgressDisplay as EnhancedProgressWrapper
from .task_master import TaskManager, Task as TMTask, TaskStatus as TMTaskStatus
from .config_manager import EnhancedConfig

# Import at module level to avoid circular imports and type annotation issues
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .main import OpusManager, SonnetWorker, SlackNotificationManager

# Use Enhanced UI as default
ProgressDisplay = EnhancedProgressWrapper

logger = logging.getLogger(__name__)


class TaskMasterInterface:
    """Interface for Task Master integration"""
    
    def __init__(self):
        self.task_manager = None
        self._initialize_task_manager()
    
    def _initialize_task_manager(self):
        """Initialize the Task Master if available"""
        try:
            self.task_manager = TaskManager(lazy_load=True)
            logger.info("Task Master integration initialized")
        except Exception as e:
            logger.warning(f"Task Master not available: {e}")
            self.task_manager = None
    
    def update_subtask_progress(self, task_id: str, current: int, total: int, status: str = None):
        """Update subtask progress in Task Master"""
        if not self.task_manager:
            return
        
        try:
            # Find the task in Task Master
            tasks = self.task_manager.list_tasks(filter_func=lambda t: str(t.id) == task_id)
            if tasks:
                task = tasks[0]
                # Update task metadata with progress
                if not task.metadata:
                    task.metadata = {}
                task.metadata['subtask_progress'] = {
                    'current': current,
                    'total': total,
                    'updated_at': datetime.now().isoformat()
                }
                if status:
                    task.metadata['subtask_status'] = status
                # Save the update
                self.task_manager._save_tasks()
        except Exception as e:
            logger.debug(f"Failed to update subtask progress: {e}")
    
    def get_subtask_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get subtask progress from Task Master"""
        if not self.task_manager:
            return None
        
        try:
            tasks = self.task_manager.list_tasks(filter_func=lambda t: str(t.id) == task_id)
            if tasks and tasks[0].metadata:
                return tasks[0].metadata.get('subtask_progress')
        except Exception as e:
            logger.debug(f"Failed to get subtask progress: {e}")
        return None


class ClaudeOrchestrator:
    """Main orchestrator coordinating Opus manager and Sonnet workers"""
    
    def __init__(self, config: EnhancedConfig, working_dir: Optional[str] = None):
        # Import here to avoid circular imports
        from .main import OpusManager, SonnetWorker, SlackNotificationManager
        
        self.config = config
        # Add execution validation flag if not present
        if not hasattr(self.config, 'validate_execution'):
            self.config.validate_execution = True
        self.working_dir = os.path.abspath(working_dir) if working_dir else os.getcwd()
        self.manager = OpusManager(config)
        self.workers: List[SonnetWorker] = []
        self.max_workers = config.max_workers
        self.executor = ThreadPoolExecutor(max_workers=config.max_workers)
        self.running = False
        self.progress = None
        # Use progress display if enabled and not in verbose mode
        self.use_progress_display = (
            config.show_progress_bar and 
            not config.verbose_logging
        )
        self.usage_warnings = []
        self.workers_at_limit = set()
        
        # Initialize Opus review system
        self.review_executor = ThreadPoolExecutor(max_workers=max(2, config.max_workers // 2))
        self.review_queue = queue.Queue()
        self.pending_reviews = {}  # task_id -> Future
        
        # Initialize Slack notification manager
        self.slack_notifier = SlackNotificationManager(config.slack_webhook_url)
        
        # Task Master interface for subtask progress
        self.task_master = TaskMasterInterface()
        
        # Initialize agent router (will be set later if needed)
        self.agent_router = None
        
        # Initialize feedback and rollback systems if enabled
        self.feedback_storage = None
        self.feedback_analyzer = None
        self.feedback_collector = None
        self.rollback_manager = None
        
        if hasattr(config, 'feedback') and config.feedback.get('enabled', True):
            from .storage_factory import create_feedback_storage
            from .feedback_analyzer import FeedbackAnalyzer
            from .feedback_api import FeedbackCollector
            self.feedback_storage = create_feedback_storage(config.feedback)
            self.feedback_analyzer = FeedbackAnalyzer(self.feedback_storage)
            self.feedback_collector = FeedbackCollector(storage=self.feedback_storage)
            logger.info("Feedback system initialized")
        
        if hasattr(config, 'rollback') and config.rollback.get('enabled', True):
            from .rollback_manager import RollbackManager
            rollback_config = config.rollback
            self.rollback_manager = RollbackManager(
                checkpoint_dir=rollback_config.get('checkpoint_dir', '.checkpoints'),
                max_checkpoints=rollback_config.get('max_checkpoints', 50),
                auto_checkpoint=rollback_config.get('auto_checkpoint', True)
            )
            # Store additional rollback settings for later use
            self.rollback_config = {
                'checkpoint_on_task_completion': rollback_config.get('checkpoint_on_task_completion', True),
                'checkpoint_on_error': rollback_config.get('checkpoint_on_error', True),
                'checkpoint_interval_minutes': rollback_config.get('checkpoint_interval_minutes', 30)
            }
            logger.info("Rollback system initialized with settings: %s", self.rollback_config)
        
        # Initialize test monitoring if configured
        self.test_monitor = None
        self.test_monitor_integration = None
        if hasattr(config, 'test_monitoring') and config.test_monitoring.get('enabled', False):
            try:
                # Try continuous test monitor first
                from .continuous_test_monitor import get_test_monitor
                
                test_config = config.test_monitoring
                self.test_monitor = get_test_monitor(test_config)
                
                # Start monitoring if auto-start is enabled
                if test_config.get('auto_start', True):
                    self.test_monitor.start()
                    logger.info(f"Continuous test monitoring started with {test_config.get('check_interval', 60)}s interval")
            except ImportError:
                # Fall back to original test monitor
                try:
                    from .test_monitor import TestMonitor, TestMonitorIntegration
                    
                    test_config = config.test_monitoring
                    self.test_monitor = TestMonitor(
                        test_dir=test_config.get('test_dir', 'tests'),
                        result_dir=test_config.get('result_dir', '.test_results'),
                        watch_patterns=test_config.get('watch_patterns', ['test_*.py'])
                    )
                    
                    # Create integration
                    self.test_monitor_integration = TestMonitorIntegration(self, self.test_monitor)
                    
                    # Start monitoring if auto-start is enabled
                    if test_config.get('auto_start', True):
                        interval = test_config.get('check_interval', 60)
                        self.test_monitor.start_monitoring(interval)
                        logger.info(f"Test monitoring started with {interval}s interval")
                except ImportError:
                    logger.info("Test monitoring not available")
            except Exception as e:
                logger.warning(f"Failed to initialize test monitoring: {e}")
                # System can still work without test monitoring
    
    def _initialize_workers(self, task_count: Optional[int] = None):
        """Initialize Sonnet workers based on task count and configuration"""
        # Calculate optimal worker count
        if task_count:
            # Use min of max_workers and task_count to avoid idle workers
            optimal_workers = min(self.max_workers, task_count)
            # But ensure at least 1 worker
            worker_count = max(1, optimal_workers)
        else:
            worker_count = self.max_workers
        
        # Update thread pool size
        self.executor = ThreadPoolExecutor(max_workers=worker_count)
        
        # Create workers
        for i in range(worker_count):
            worker = SonnetWorker(i, self.working_dir, self.config)
            worker.orchestrator = self  # Set reference to orchestrator
            self.workers.append(worker)
        
        logger.info(f"Created {worker_count} Sonnet workers for {task_count or 'unknown'} tasks")
        
        # Initialize specialized agents and dynamic routing after workers are created
        # NOTE: Specialized agents initialization removed - not implemented yet
    
    def _check_and_delegate_new_tasks(self):
        """Check for newly available tasks and delegate them"""
        try:
            # Get fresh task list from TaskMaster
            all_tasks = self.manager.analyze_and_plan()
            
            # Track current task IDs
            all_task_ids = (
                set(self.manager.completed_tasks.keys()) |
                set(self.manager.failed_tasks.keys()) |
                set(self.manager.active_tasks.keys()) |
                {t.task_id for t in list(self.manager.task_queue.queue)}
            )
            
            # Check each task
            for task in all_tasks:
                # Skip if already processed or in queue
                if task.task_id in all_task_ids:
                    continue
                
                # Check if dependencies are satisfied
                deps_completed = all(
                    dep in self.manager.completed_tasks 
                    for dep in task.dependencies
                )
                
                if deps_completed:
                    logger.info(f"New task available: {task.task_id} - {task.title}, delegating...")
                    self.manager.delegate_task(task)
                    if self.use_progress_display and self.progress:
                        self.progress.total_tasks += 1
                        self.progress.log_message(f"New task discovered: {task.task_id} - {task.title}", "INFO")
                        
        except Exception as e:
            logger.error(f"Error checking for new tasks: {e}")
    
    def review_loop(self):
        """Loop that processes Opus reviews in parallel"""
        logger.info("Review loop started")
        
        while self.running:
            try:
                # Get task from review queue with timeout
                task = self.review_queue.get(timeout=1.0)
                
                # Perform Opus review
                review_result = self._opus_review_task(task)
                
                # Collect feedback for review decision
                if hasattr(self.manager, 'feedback_collector') and self.manager.feedback_collector:
                    try:
                        from .feedback_model import FeedbackType, FeedbackCategory, FeedbackSeverity
                        
                        severity = FeedbackSeverity.INFO
                        if not review_result['success']:
                            severity = FeedbackSeverity.ERROR
                        elif review_result.get('follow_up_count', 0) > 0:
                            severity = FeedbackSeverity.WARNING
                            
                        feedback_id = self.manager.feedback_collector.collect_feedback(
                            feedback_type=FeedbackType.DECISION,
                            category=FeedbackCategory.REVIEW,
                            message=f"Opus review completed for task {task.task_id}",
                            context={
                                "task_id": str(task.task_id),
                                "success": review_result['success'],
                                "follow_up_count": review_result.get('follow_up_count', 0),
                                "phase": "review_decision"
                            },
                            severity=severity,
                            worker_id="opus_reviewer",
                            session_id=str(id(self))
                        )
                        logger.debug(f"Collected review feedback: {feedback_id}")
                    except Exception as e:
                        logger.debug(f"Failed to collect review feedback: {e}")
                
                if review_result['success']:
                    # Check if follow-up tasks were created
                    if review_result.get('follow_up_count', 0) > 0:
                        # Log that improvements are needed
                        if self.use_progress_display and self.progress:
                            self.progress.log_message(
                                f"🔍 Opus review for task {task.task_id}: {review_result['follow_up_count']} improvements needed",
                                "WARNING"
                            )
                        else:
                            logger.warning(f"Task {task.task_id} needs improvements ({review_result['follow_up_count']} follow-up tasks created)")
                        
                        # Update task status to indicate review found issues
                        task.status_message = f"Review complete - {review_result['follow_up_count']} improvements needed"
                    else:
                        # Task passed review
                        if self.use_progress_display and self.progress:
                            self.progress.log_message(f"✅ Task {task.task_id} passed Opus review", "SUCCESS")
                        else:
                            logger.info(f"✅ Task {task.task_id} passed Opus review")
                        
                        task.status_message = "Review complete - No issues found"
                    
                    # Log the review summary
                    logger.debug(f"Opus review for task {task.task_id}:\n{review_result['review']}")
                # Log review summary  
                logger.debug(f"Opus review for task {task.task_id}:\n{review_result['review']}")
                
                # NOTE: Review integration not implemented - skipping automatic application of review changes
                if self.use_progress_display and self.progress:
                    self.progress.log_message(f"📝 Review feedback recorded for task {task.task_id}", "INFO")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in review loop: {e}")
        
        logger.info("Review loop stopped")
    
    def periodic_checkpoint_loop(self, interval_minutes: int):
        """Create periodic checkpoints at specified intervals"""
        import time
        from .rollback_manager import CheckpointType
        
        interval_seconds = interval_minutes * 60
        last_checkpoint_time = time.time()
        
        while self.running:
            try:
                time.sleep(10)  # Check every 10 seconds
                
                current_time = time.time()
                if current_time - last_checkpoint_time >= interval_seconds:
                    # Create periodic checkpoint
                    if self.rollback_manager:
                        try:
                            checkpoint_id = self.rollback_manager.create_checkpoint(
                                checkpoint_type=CheckpointType.AUTOMATIC,
                                description=f"Periodic checkpoint (interval: {interval_minutes} minutes)"
                            )
                            logger.info(f"Created periodic checkpoint: {checkpoint_id}")
                            last_checkpoint_time = current_time
                        except Exception as e:
                            logger.error(f"Failed to create periodic checkpoint: {e}")
                
            except Exception as e:
                logger.error(f"Error in periodic checkpoint loop: {e}")
                time.sleep(60)  # Wait a minute before retrying
    
    def worker_loop(self, worker: 'SonnetWorker'):
        """Worker loop that processes tasks from the queue"""
        if self.use_progress_display and self.progress:
            self.progress.log_message(f"Worker {worker.worker_id} started", "INFO")
        else:
            logger.info(f"Worker {worker.worker_id} started")
            
        while self.running:
            try:
                # Get task from queue with timeout
                task = self.manager.task_queue.get(timeout=self.config.task_queue_timeout)
                
                # Mark task as active
                task.assigned_worker = worker.worker_id
                self.manager.active_tasks[task.task_id] = task
                

                # Update progress display
                if self.use_progress_display and self.progress:
                    # Update task counts first
                    self.progress.active = len(self.manager.active_tasks)
                    self.progress.update_totals(
                        completed=len(self.manager.completed_tasks),
                        active=len(self.manager.active_tasks),
                        failed=len(self.manager.failed_tasks)
                    )
                    
                    # Set worker task with proper formatting
                    task_display = task.title[:50] if len(task.title) > 50 else task.title
                    self.progress.set_worker_task(worker.worker_id, task.task_id, task_display)
                    
                    # Log task start
                    self.progress.log_message(f"Worker {worker.worker_id} started: {task_display}", "INFO")
                    
                    self.progress.update()
                
                # Track start time for performance feedback
                start_time = time.time()
                
                # Process task
                completed_task = worker.process_task(task)
                
                # Calculate execution time
                execution_time = time.time() - start_time

                # Move task to appropriate collection
                del self.manager.active_tasks[task.task_id]
                
                if completed_task.status == TaskStatus.COMPLETED:
                    # First mark as completed
                    self.manager.completed_tasks[task.task_id] = completed_task
                    
                    # Update TaskMaster state
                    try:
                        self.manager.task_master.complete_task(str(task.task_id))
                    except Exception as e:
                        logger.debug(f"Could not update TaskMaster: {e}")
                    
                    # Collect feedback if enabled
                    if hasattr(self.manager, 'feedback_collector') and self.manager.feedback_collector:
                        try:
                            # Collect success feedback with performance metrics
                            feedback_id = self.manager.feedback_collector.collect_task_feedback(
                                task_id=str(task.task_id),
                                success=True,
                                message=f"Task completed successfully by {worker.worker_id}",
                                worker_id=worker.worker_id,
                                execution_time=execution_time
                            )
                            logger.debug(f"Collected feedback {feedback_id} for completed task {task.task_id}")
                        except Exception as e:
                            logger.debug(f"Failed to collect feedback for task {task.task_id}: {e}")
                    
                    if self.use_progress_display and self.progress:
                        # Update counts
                        self.progress.completed += 1
                        self.progress.active = len(self.manager.active_tasks)
                        
                        # Clear worker task
                        self.progress.clear_worker_task(worker.worker_id)
                        
                        # Log completion
                        task_display = task.title[:40] if len(task.title) > 40 else task.title
                        self.progress.log_message(f"✅ Task {task.task_id} completed: {task_display}", "SUCCESS")
                    
                    # Submit task for Opus review
                    self.review_queue.put(completed_task)
                    if self.use_progress_display and self.progress:
                        self.progress.log_message(f"📋 Task {task.task_id} submitted for Opus review", "INFO")
                    
                    # Collect feedback for successful task
                    if self.feedback_storage:
                        try:
                            from .feedback_model import create_success_feedback, FeedbackMetrics
                            
                            # Calculate execution time if available
                            exec_time = getattr(completed_task, 'execution_time', None)
                            metrics = FeedbackMetrics(
                                execution_time=exec_time,
                                tokens_used=getattr(completed_task, 'tokens_used', None)
                            )
                            
                            feedback = create_success_feedback(
                                task_id=str(task.task_id),
                                message=f"Task completed successfully: {task.title}",
                                metrics=metrics,
                                worker_id=f"worker_{worker.worker_id}",
                                session_id=str(id(self))
                            )
                            self.feedback_storage.save(feedback)
                        except Exception as e:
                            logger.debug(f"Failed to save task success feedback: {e}")
                    
                    # Create checkpoint after task completion if enabled
                    if self.rollback_manager and self.rollback_manager.auto_checkpoint:
                        try:
                            from .rollback_manager import CheckpointType
                            self.rollback_manager.update_task_state(
                                str(task.task_id), 
                                {"status": "completed", "title": task.title}
                            )
                            # This will auto-create checkpoint due to task completion
                        except Exception as e:
                            logger.debug(f"Failed to update rollback state: {e}")
                    
                    # Send Slack notification for completed task
                    if self.config.notify_on_task_complete:
                        self.slack_notifier.send_task_complete(task.task_id, task.title)
                else:
                    self.manager.failed_tasks[task.task_id] = completed_task
                    if self.use_progress_display and self.progress:
                        # Update counts
                        self.progress.failed += 1
                        self.progress.active = len(self.manager.active_tasks)
                        
                        # Clear worker task
                        self.progress.clear_worker_task(worker.worker_id)
                        
                        # Log failure
                        task_display = task.title[:40] if len(task.title) > 40 else task.title
                        error_msg = completed_task.error[:50] if completed_task.error and len(completed_task.error) > 50 else completed_task.error
                        self.progress.log_message(f"❌ Task {task.task_id} failed: {task_display}", "ERROR")
                        if error_msg:
                            self.progress.log_message(f"   Error: {error_msg}", "ERROR")
                    
                    # Create checkpoint on error if configured
                    if self.rollback_manager and hasattr(self, 'rollback_config') and self.rollback_config.get('checkpoint_on_error', True):
                        try:
                            from .rollback_manager import CheckpointType
                            checkpoint_id = self.rollback_manager.create_checkpoint(
                                checkpoint_type=CheckpointType.ERROR_RECOVERY,
                                description=f"Error checkpoint for task {task.task_id}: {task.title[:50]}",
                                include_files=[]  # Include relevant files if needed
                            )
                            logger.info(f"Created error checkpoint {checkpoint_id} for failed task {task.task_id}")
                        except Exception as e:
                            logger.error(f"Failed to create error checkpoint: {e}")
                    
                    # Collect feedback for failed task
                    if self.feedback_storage:
                        try:
                            from .feedback_model import create_error_feedback, FeedbackSeverity
                            
                            error_msg = completed_task.error or "Unknown error"
                            severity = FeedbackSeverity.CRITICAL if completed_task.error == "USAGE_LIMIT_REACHED" else FeedbackSeverity.ERROR
                            
                            feedback = create_error_feedback(
                                task_id=str(task.task_id),
                                message=f"Task failed: {task.title}",
                                error_details={"error": error_msg, "status": "failed"},
                                severity=severity,
                                worker_id=f"worker_{worker.worker_id}",
                                session_id=str(id(self))
                            )
                            self.feedback_storage.save(feedback)
                        except Exception as e:
                            logger.debug(f"Failed to save task error feedback: {e}")
                    
                    # Send Slack notification for failed task
                    if self.config.notify_on_task_failed:
                        error_msg = completed_task.error or "Unknown error"
                        self.slack_notifier.send_task_failed(task.task_id, task.title, error_msg)
                    
                    # Check if worker hit usage limit
                    if completed_task.error == "USAGE_LIMIT_REACHED":
                        logger.error(f"Worker {worker.worker_id} has reached usage limit")
                        self.workers_at_limit.add(worker.worker_id)
                        # Stop this worker
                        break
                
                # Mark task queue item as done
                self.manager.task_queue.task_done()
                
                # Immediately check for new tasks that may have become available
                self._check_and_delegate_new_tasks()
                
            except queue.Empty:
                # No tasks available, continue waiting
                continue
            except Exception as e:
                logger.error(f"Worker {worker.worker_id} error: {e}")
                # Continue working despite errors
        
        if self.use_progress_display and self.progress:
            if worker.worker_id in self.workers_at_limit:
                self.progress.log_message(f"Worker {worker.worker_id} stopped - Usage limit reached", "WARNING")
            else:
                self.progress.log_message(f"Worker {worker.worker_id} stopped", "INFO")
        else:
            logger.info(f"Worker {worker.worker_id} stopped")
    
    def run(self):
        """Run the orchestrator"""
        self.start_time = time.time()
        logger.info("\n" + "="*50)
        logger.info("Starting Claude Orchestrator")
        logger.info("="*50 + "\n")
        
        # Step 1: Analyze and plan with Opus
        tasks = self.manager.analyze_and_plan()
        
        if not tasks:
            logger.warning("No tasks to process!")
            return
        
        # Initialize workers based on task count
        self._initialize_workers(len(tasks))
        
        # Initialize progress display
        if self.use_progress_display:
            self.progress = ProgressDisplay(total_tasks=len(tasks))
            self.progress.register_workers(len(self.workers))  # Register all workers
            self.progress.update("Starting task processing...")
        
        # Set running flag
        self.running = True
        
        try:
            # Log task execution plan
            logger.info(f"\n📋 Task Execution Plan:")
            logger.info(f"   Total tasks: {len(tasks)}")
            logger.info(f"   Workers: {len(self.workers)}")
            logger.info(f"   Parallel execution: {'Yes' if self.max_workers > 1 else 'No'}")
            
            if self.use_progress_display:
                self.progress.log_message(f"Opus Manager prepared {len(tasks)} tasks for processing", "INFO")
            
            # Start worker threads
            worker_futures = []
            for worker in self.workers:
                future = self.executor.submit(self.worker_loop, worker)
                worker_futures.append(future)
            
            # Start periodic checkpoint thread if configured
            checkpoint_future = None
            if self.rollback_manager and hasattr(self, 'rollback_config'):
                checkpoint_interval = self.rollback_config.get('checkpoint_interval_minutes', 30)
                if checkpoint_interval > 0:
                    checkpoint_future = self.executor.submit(self.periodic_checkpoint_loop, checkpoint_interval)
                    logger.info(f"Started periodic checkpoint thread (interval: {checkpoint_interval} minutes)")
            
            # Start review threads
            review_futures = []
            num_reviewers = max(2, len(self.workers) // 2)  # Half the workers, minimum 2
            for i in range(num_reviewers):
                future = self.review_executor.submit(self.review_loop)
                review_futures.append(future)
                if self.use_progress_display:
                    self.progress.log_message(f"Started Opus reviewer thread {i+1}", "INFO")
                else:
                    logger.info(f"Started Opus reviewer thread {i+1}")
            
            # Delegate tasks
            for task in tasks:
                # Check dependencies
                deps_completed = all(
                    dep in self.manager.completed_tasks 
                    for dep in task.dependencies
                )
                
                if deps_completed:
                    self.manager.delegate_task(task)
                else:
                    logger.debug(f"Task {task.task_id} waiting for dependencies: {task.dependencies}")
            
            # Monitor progress
            monitor_interval = min(5, self.config.progress_interval)  # Check at least every 5 seconds
            last_monitor = datetime.now()
            last_progress_update = time.time()
            
            while True:
                # Update progress display
                if self.use_progress_display and self.progress:
                    current_time = time.time()
                    if current_time - last_progress_update > 0.1:  # Update every 100ms
                        # Update task counts
                        completed_count = len(self.manager.completed_tasks)
                        active_count = len(self.manager.active_tasks)
                        failed_count = len(self.manager.failed_tasks)
                        
                        # Update progress totals
                        self.progress.update_totals(completed_count, active_count, failed_count)
                        
                        # Update queue status
                        queue_size = self.manager.task_queue.qsize()
                        review_queue_size = self.review_queue.qsize()
                        self.progress.display.update_queue_status(queue_size, review_queue_size)
                        
                        # Update subtask progress for active tasks
                        for task_id, task in self.manager.active_tasks.items():
                            # Get subtask progress if available
                            progress_data = self.task_master.get_subtask_progress(task_id)
                            if progress_data and progress_data.get('total', 0) > 0:
                                self.progress.set_task_subtasks(
                                    task_id, 
                                    progress_data.get('current', 0), 
                                    progress_data.get('total', 0)
                                )
                        
                        # Update display
                        self.progress.update()
                        last_progress_update = current_time
                
                # Check if all tasks are done
                # First check if there are any pending tasks in TaskMaster
                has_pending_tasks = False
                if self.task_master.task_manager:
                    try:
                        all_taskmaster_tasks = self.task_master.task_manager.list_tasks()
                        has_pending_tasks = any(
                            task.status in ['pending', 'in_progress'] 
                            for task in all_taskmaster_tasks
                        )
                    except Exception:
                        pass  # TaskMaster not available
                
                all_done = (
                    self.manager.task_queue.empty() and
                    len(self.manager.active_tasks) == 0 and
                    not has_pending_tasks
                )
                
                if all_done:
                    # Wait a bit more to ensure all reviews complete
                    logger.info("All tasks processed, waiting for reviews to complete...")
                    time.sleep(2)
                    break
                
                # Periodic monitoring
                if (datetime.now() - last_monitor).seconds >= monitor_interval:
                    if not self.use_progress_display:
                        self.manager.monitor_progress()
                    last_monitor = datetime.now()
                    
                    # Check for new tasks from TaskMaster
                    current_task_ids = {t.task_id for t in tasks}
                    all_task_ids = (
                        set(self.manager.completed_tasks.keys()) |
                        set(self.manager.failed_tasks.keys()) |
                        set(self.manager.active_tasks.keys()) |
                        {t.task_id for t in list(self.manager.task_queue.queue)}
                    )
                    
                    # Get fresh task list from TaskMaster
                    fresh_tasks = self.manager.analyze_and_plan()
                    for fresh_task in fresh_tasks:
                        if fresh_task.task_id not in current_task_ids:
                            # New task found, add it to our tracking
                            tasks.append(fresh_task)
                            if self.use_progress_display and self.progress:
                                self.progress.total_tasks += 1
                                self.progress.log_message(f"New task discovered: {fresh_task.task_id} - {fresh_task.title}", "INFO")
                            logger.info(f"Found new task: {fresh_task.task_id} - {fresh_task.title}")
                    
                    # Check for newly available tasks (dependencies satisfied)
                    for task in tasks:
                        if (task.task_id not in self.manager.completed_tasks and
                            task.task_id not in self.manager.failed_tasks and
                            task.task_id not in self.manager.active_tasks and
                            task.task_id not in [t.task_id for t in list(self.manager.task_queue.queue)]):
                            
                            deps_completed = all(
                                dep in self.manager.completed_tasks 
                                for dep in task.dependencies
                            )
                            
                            if deps_completed:
                                logger.info(f"Dependencies satisfied for task {task.task_id}, delegating...")
                                self.manager.delegate_task(task)
                
                # Small sleep to prevent busy waiting
                time.sleep(0.1)
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        finally:
            # Shutdown
            self.running = False
            
            # Wait for all reviews to complete
            if self.use_progress_display and self.progress:
                self.progress.log_message("Waiting for reviews to complete...", "INFO")
            else:
                logger.info("Waiting for reviews to complete...")
            
            # Shutdown executors
            self.executor.shutdown(wait=True)
            self.review_executor.shutdown(wait=True)
            
            # Final report
            self._generate_final_report()
    
    def _generate_final_report(self):
        """Generate final execution report"""
        logger.info("\n" + "="*50)
        logger.info("FINAL EXECUTION REPORT")
        logger.info("="*50)
        
        total_tasks = (
            len(self.manager.completed_tasks) + 
            len(self.manager.failed_tasks)
        )
        
        logger.info(f"Total tasks processed: {total_tasks}")
        logger.info(f"Successful: {len(self.manager.completed_tasks)}")
        logger.info(f"Failed: {len(self.manager.failed_tasks)}")
        
        # Calculate elapsed time
        if hasattr(self, 'start_time'):
            elapsed = time.time() - self.start_time
            elapsed_str = self._format_elapsed_time(elapsed)
        else:
            elapsed_str = "Unknown"
        
        # Send Slack notification for all tasks complete
        if self.config.notify_on_all_complete and total_tasks > 0:
            self.slack_notifier.send_all_complete(
                total_tasks,
                len(self.manager.completed_tasks),
                len(self.manager.failed_tasks),
                elapsed_str
            )
        
        # Report usage statistics
        if self.workers:
            logger.info("\nWorker Usage Statistics:")
            total_tokens = 0
            for worker in self.workers:
                logger.info(f"  Worker {worker.worker_id}:")
                logger.info(f"    Tasks completed: {worker.tasks_completed}")
                logger.info(f"    Tokens used: {worker.session_tokens_used:,}")
                total_tokens += worker.session_tokens_used
                
                if worker.worker_id in self.workers_at_limit:
                    logger.info(f"    ⚠️ Reached usage limit")
                    
            if total_tokens > 0:
                logger.info(f"\nTotal tokens used across all workers: {total_tokens:,}")
        
        if self.manager.completed_tasks:
            logger.info("\nCompleted tasks:")
            for task_id, task in self.manager.completed_tasks.items():
                logger.info(f"  ✓ {task_id}: {task.title}")
        
        if self.manager.failed_tasks:
            logger.info("\nFailed tasks:")
            for task_id, task in self.manager.failed_tasks.items():
                logger.info(f"  ✗ {task_id}: {task.title}")
                if task.error:
                    logger.info(f"    Error: {task.error}")
        
        # Final progress display if enabled
        if self.use_progress_display and self.progress:
            # ProgressDisplay doesn't have finish method, just update one last time
            self.progress.update()
        
        # Perform final Opus review if enabled
        if self.config.enable_opus_review and self.manager.completed_tasks:
            logger.info("\n🎭 Performing final Opus review...")
            summary = self._perform_final_opus_review()
            if summary:
                logger.info(f"\nOpus Review Summary:\n{summary}")
                
                # Count follow-up tasks
                total_follow_ups = 0
                tasks_passed_review = 0
                tasks_need_improvement = 0
                
                for task_id, task in self.manager.completed_tasks.items():
                    if task.status_message:
                        if "No issues found" in task.status_message:
                            tasks_passed_review += 1
                        elif "improvements needed" in task.status_message:
                            tasks_need_improvement += 1
                            # Extract follow-up count from message
                            import re
                            match = re.search(r'(\d+) improvements needed', task.status_message)
                            if match:
                                total_follow_ups += int(match.group(1))
                
                logger.info(f"Tasks passed review: {tasks_passed_review}")
                logger.info(f"Tasks needing improvement: {tasks_need_improvement}")
                
                if total_follow_ups > 0:
                    logger.info(f"\n🔧 Total Follow-up Tasks Created: {total_follow_ups}")
                    logger.info("Run 'python claude_orchestrator.py run' again to process the improvements")
                
                # Send summary to Slack if configured
                if self.slack_notifier.webhook_url and self.manager.completed_tasks:
                    summary = f"Completed {len(self.manager.completed_tasks)} tasks. "
                    summary += f"{tasks_passed_review} passed review, {tasks_need_improvement} need improvements."
                    
                    task_results = []
                    for task_id, task in self.manager.completed_tasks.items():
                        # Include both task result and review status
                        summary_parts = []
                        if task.result:
                            summary_parts.append(task.result)
                        if task.status_message:
                            summary_parts.append(f"[{task.status_message}]")
                        
                        task_results.append({
                            'status': 'completed',
                            'title': task.title,
                            'summary': " ".join(summary_parts) if summary_parts else "Task completed"
                        })
                    
                    elapsed_time = elapsed_str if 'elapsed_str' in locals() else "Unknown"
                    self.slack_notifier.send_opus_review(summary, task_results, elapsed_time, total_follow_ups)
        
        # Auto-commit changes if configured and git is available
        if self.config.git_auto_commit:
            self._auto_commit_changes()
    
    def _get_commit_message_template(self, language: str, completed_count: int, failed_count: int) -> dict:
        """Get commit message template based on language"""
        templates = {
            'ko': {
                'prefix': '🤖 Claude Orchestrator에 의한 자동 커밋',
                'summary': f'{completed_count}개 작업 완료, {failed_count}개 실패',
                'completed_header': '완료된 작업:',
                'failed_header': '실패한 작업:',
                'commit_success': '✅ 변경사항이 성공적으로 커밋되었습니다',
                'no_changes': '커밋할 변경사항이 없습니다',
                'not_git_repo': 'Git 저장소가 아니므로 자동 커밋을 건너뜁니다'
            },
            'en': {
                'prefix': '🤖 Auto-commit by Claude Orchestrator',
                'summary': f'Completed {completed_count} tasks, {failed_count} failed',
                'completed_header': 'Completed tasks:',
                'failed_header': 'Failed tasks:',
                'commit_success': '✅ Successfully committed changes',
                'no_changes': 'No changes to commit',
                'not_git_repo': 'Not in a git repository, skipping auto-commit'
            },
            'ja': {
                'prefix': '🤖 Claude Orchestratorによる自動コミット',
                'summary': f'{completed_count}個のタスク完了、{failed_count}個失敗',
                'completed_header': '完了したタスク:',
                'failed_header': '失敗したタスク:',
                'commit_success': '✅ 変更が正常にコミットされました',
                'no_changes': 'コミットする変更はありません',
                'not_git_repo': 'Gitリポジトリではないため、自動コミットをスキップします'
            },
            'zh': {
                'prefix': '🤖 Claude Orchestrator 自动提交',
                'summary': f'完成 {completed_count} 个任务，{failed_count} 个失败',
                'completed_header': '已完成的任务：',
                'failed_header': '失败的任务：',
                'commit_success': '✅ 成功提交更改',
                'no_changes': '没有要提交的更改',
                'not_git_repo': '不在 Git 仓库中，跳过自动提交'
            }
        }
        
        # Default to English if language not found
        return templates.get(language, templates['en'])
    
    def _auto_commit_changes(self):
        """Auto-commit changes to git if repository exists"""
        try:
            # Get language setting
            language = getattr(self.config, 'locale_language', 'en')
            
            # Generate commit message first to get counts
            completed_count = len(self.manager.completed_tasks)
            failed_count = len(self.manager.failed_tasks)
            
            # Get language-specific templates
            templates = self._get_commit_message_template(language, completed_count, failed_count)
            
            # Check if we're in a git repository
            git_check = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True
            )
            
            if git_check.returncode != 0:
                logger.info(templates['not_git_repo'])
                return
            
            # Check if there are changes to commit
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True
            )
            
            if not status_result.stdout.strip():
                logger.info(templates['no_changes'])
                return
            
            logger.info("\n" + "="*50)
            logger.info("AUTO-COMMITTING CHANGES")
            logger.info("="*50)
            
            # Add all changes
            add_result = subprocess.run(
                ["git", "add", "-A"],
                capture_output=True,
                text=True
            )
            
            if add_result.returncode != 0:
                logger.error(f"Failed to stage changes: {add_result.stderr}")
                return
            
            # Generate commit message using language template
            commit_message = f"{templates['prefix']}\n\n"
            commit_message += f"{templates['summary']}\n\n"
            
            if self.manager.completed_tasks:
                commit_message += f"{templates['completed_header']}\n"
                for task_id, task in self.manager.completed_tasks.items():
                    commit_message += f"- ✅ {task.title}\n"
            
            if self.manager.failed_tasks:
                commit_message += f"\n{templates['failed_header']}\n"
                for task_id, task in self.manager.failed_tasks.items():
                    commit_message += f"- ❌ {task.title}\n"
            
            # Commit changes
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                capture_output=True,
                text=True
            )
            
            if commit_result.returncode == 0:
                # Get commit hash
                hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True
                )
                commit_hash = hash_result.stdout.strip()[:7] if hash_result.returncode == 0 else "unknown"
                
                logger.info(f"{templates['commit_success']}: {commit_hash}")
                logger.info(f"   Message: {templates['prefix']}")
                
                # Also send to Slack if configured
                if self.slack_notifier.webhook_url:
                    self.slack_notifier.send_notification(
                        f"Auto-committed changes: {commit_hash}\n{completed_count} completed, {failed_count} failed",
                        ":floppy_disk:"
                    )
            else:
                logger.error(f"Failed to commit: {commit_result.stderr}")
                
        except Exception as e:
            logger.error(f"Error during auto-commit: {e}")
    
    def _perform_final_opus_review(self) -> Optional[str]:
        """Perform a final review of all completed tasks using Opus"""
        try:
            # Prepare review data
            completed_tasks = []
            for task_id, task in self.manager.completed_tasks.items():
                completed_tasks.append({
                    'id': task_id,
                    'title': task.title,
                    'description': task.description,
                    'result': task.result[:500] if task.result else "No output"  # Limit output length
                })
            
            # Create review prompt
            prompt = f"""You are the Opus Manager reviewing the work completed by Sonnet workers.

Please review the following completed tasks and provide:
1. Overall quality assessment
2. Any potential issues or concerns
3. Suggestions for improvements
4. Confirmation that all tasks meet the requirements

Completed Tasks:
{json.dumps(completed_tasks, indent=2)}

Additionally, review the current state of the codebase:
- Check for consistency across changes
- Verify that all changes follow best practices
- Ensure no breaking changes were introduced
- Confirm that the implementation matches the original requirements

IMPORTANT: Based on your review, if there are any improvements needed or follow-up work required:
1. Use the task-master CLI to create new tasks for these improvements
2. Be specific about what needs to be done
3. Set appropriate priorities based on importance
4. Add helpful context in the task descriptions

Example commands you can use:
- task-master add-task --prompt="Add unit tests for the new authentication module" --priority=high
- task-master add-task --prompt="Refactor error handling to use consistent patterns" --priority=medium
- task-master add-task --prompt="Add documentation for the API endpoints" --priority=low

First provide your review summary, then create any necessary follow-up tasks."""

            # Execute Opus review
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                prompt_file = f.name
            
            cmd = [
                self.config.claude_command,
                "-p", f"@{prompt_file}",
                "--model", self.config.manager_model
            ]
            
            # Add flags
            if self.config.claude_flags.get("verbose"):
                cmd.append("--verbose")
            if self.config.claude_flags.get("dangerously_skip_permissions"):
                cmd.append("--dangerously-skip-permissions")
            
            # Set up environment
            env = os.environ.copy()
            for key, value in self.config.claude_environment.items():
                if value is not None:
                    env[key] = str(value)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.working_dir,
                timeout=self.config.manager_timeout,
                env=env
            )
            
            # Clean up
            os.unlink(prompt_file)
            
            if result.returncode == 0:
                return result.stdout
            else:
                logger.error(f"Opus review failed: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error performing Opus review: {e}")
            return None
    
    def _opus_review_task(self, task: WorkerTask) -> Dict[str, Any]:
        """Have Opus review a single completed task"""
        try:
            # Create review prompt
            prompt = f"""As the Opus Manager, please review this completed task:

Task ID: {task.task_id}
Title: {task.title}
Description: {task.description}

Worker Output:
{task.result[:2000] if task.result else "No output"}

Please:
1. Assess if the task was completed successfully
2. Check if the implementation follows best practices
3. Identify any potential issues or improvements

If improvements are needed:
- Use task-master CLI to create specific follow-up tasks
- Be clear about what needs to be fixed or improved
- Set appropriate priorities

Based on your review, create any necessary follow-up tasks using:
- task-master add-task --prompt="[specific improvement]" --priority=[high/medium/low]

Provide your review summary."""

            # Execute Opus review
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                prompt_file = f.name
            
            cmd = [
                self.config.claude_command,
                "-p", f"@{prompt_file}",
                "--model", self.config.manager_model
            ]
            
            # Add flags
            if self.config.claude_flags.get("verbose"):
                cmd.append("--verbose")
            if self.config.claude_flags.get("dangerously_skip_permissions"):
                cmd.append("--dangerously-skip-permissions")
            
            # Set up environment
            env = os.environ.copy()
            for key, value in self.config.claude_environment.items():
                if value is not None:
                    env[key] = str(value)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.working_dir,
                timeout=300,  # 5 minute timeout for review
                env=env
            )
            
            # Clean up
            os.unlink(prompt_file)
            
            if result.returncode == 0:
                opus_output = result.stdout
                
                # Count follow-up tasks created
                follow_up_count = self._count_follow_up_tasks(opus_output)
                
                return {
                    'success': True,
                    'review': opus_output,
                    'follow_up_count': follow_up_count
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr or "Unknown error"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _count_follow_up_tasks(self, opus_output: str) -> int:
        """Count how many follow-up tasks were created by Opus"""
        count = 0
        
        # Look for task creation patterns
        lines = opus_output.split('\n')
        for line in lines:
            # Check for successful task creation messages
            if any(phrase in line.lower() for phrase in [
                "added task",
                "created task",
                "task added",
                "task created",
                "successfully added",
                "successfully created"
            ]):
                count += 1
        
        # Also check for task-master command executions
        task_master_commands = re.findall(r"task-master add-task", opus_output)
        
        # Use the larger count (in case output format varies)
        return max(count, len(task_master_commands))
    
    def _format_elapsed_time(self, elapsed: float) -> str:
        """Format elapsed time in human-readable format"""
        if elapsed < 60:
            return f"{elapsed:.1f}s"
        elif elapsed < 3600:
            minutes = int(elapsed / 60)
            seconds = int(elapsed % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(elapsed / 3600)
            minutes = int((elapsed % 3600) / 60)
            return f"{hours}h {minutes}m"

