#!/usr/bin/env python3
"""
Claude Orchestrator - Opus Manager with Sonnet Workers
Uses Task Master for task management and parallel processing
"""

import asyncio
import subprocess
import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
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
# Enhanced UI imports
from .enhanced_progress_display import EnhancedProgressDisplay, WorkerState
from .progress_display_integration import ProgressDisplay as EnhancedProgressWrapper

from datetime import timedelta

# Import native Task Master
from .task_master import TaskManager, Task as TMTask, TaskStatus as TMTaskStatus
from .task_master_ai import TaskMasterAI
from .review_applier import ReviewApplier, ReviewApplierIntegration

# Import direct Claude API
try:
    from .claude_direct_api import create_claude_client, ClaudeResponse
    DIRECT_API_AVAILABLE = True
except ImportError:
    DIRECT_API_AVAILABLE = False
    logger.warning("Direct Claude API not available, will use subprocess mode")

# Import the new configuration management system
try:
    from .config_manager import ConfigurationManager, EnhancedConfig, ConfigValidationResult
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False
    
# Import error handler if available
try:
    from .claude_error_handler import ClaudeErrorHandler
    ERROR_HANDLER_AVAILABLE = True
except ImportError:
    ERROR_HANDLER_AVAILABLE = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Original ProgressDisplay replaced with Enhanced UI
# To restore original, rename ProgressDisplay_Original back to ProgressDisplay
class ProgressDisplay_Original:
    """Handles real-time progress display with carriage return"""
    
    def __init__(self, total_tasks: int = 0):
        self.total_tasks = total_tasks
        self.completed = 0
        self.active = 0
        self.failed = 0
        self.start_time = time.time()
        self.current_status = ""
        self.last_update = 0
        self.update_interval = 0.1  # Update display every 100ms
        self.is_verbose = False
        self.last_line_length = 0
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_index = 0
        # Check if we're in a TTY (terminal) that supports carriage returns
        self.is_tty = sys.stdout.isatty() and os.environ.get('TERM', '') != 'dumb'
        
        # Track active tasks per worker
        self.active_tasks = {}  # worker_id -> (task_id, task_title, progress)
        self.task_subtasks = {}  # task_id -> (current_subtask, total_subtasks)
        self.last_display_lines = 0
        
    def _clear_line(self):
        """Clear the current line"""
        if self.is_tty:
            # Use simple approach for better compatibility
            sys.stdout.write('\r' + ' ' * self.last_line_length + '\r')
        sys.stdout.flush()
        
    def _format_time(self, seconds: float) -> str:
        """Format elapsed time"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds//60:.0f}m {seconds%60:.0f}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}h {minutes:.0f}m"
    
    def _get_progress_bar(self, width: int = 20) -> str:
        """Generate a progress bar"""
        if self.total_tasks == 0:
            return "[" + "?" * width + "]"
        
        progress = (self.completed + self.failed) / self.total_tasks
        filled = int(width * progress)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
    
    def set_worker_task(self, worker_id: int, task_id: str, task_title: str, progress: str = ""):
        """Set the current task for a worker"""
        self.active_tasks[worker_id] = (task_id, task_title, progress)
        
    def set_task_subtasks(self, task_id: str, current: int, total: int):
        """Set subtask progress for a task"""
        self.task_subtasks[task_id] = (current, total)
        
    def clear_worker_task(self, worker_id: int):
        """Clear the current task for a worker"""
        if worker_id in self.active_tasks:
            del self.active_tasks[worker_id]
    
    def _clear_multi_lines(self):
        """Clear multiple lines for multi-task display"""
        if self.is_tty and self.last_display_lines > 0:
            # Move cursor up and clear lines
            for i in range(self.last_display_lines):
                sys.stdout.write('\033[A')  # Move up one line
                sys.stdout.write('\033[K')   # Clear line
            sys.stdout.flush()
    
    def update(self, status: str = "", force: bool = False):
        """Update the progress display"""
        current_time = time.time()
        
        # Only update if enough time has passed or forced
        if not force and current_time - self.last_update < self.update_interval:
            return
            
        self.last_update = current_time
        elapsed = current_time - self.start_time
        
        # Update spinner
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_frames)
        spinner = self.spinner_frames[self.spinner_index]
        
        # Build status line
        progress_bar = self._get_progress_bar()
        percentage = ((self.completed + self.failed) / self.total_tasks * 100) if self.total_tasks > 0 else 0
        
        # Add spinner when tasks are active
        activity_indicator = spinner if self.active > 0 else "✨"
        
        if self.is_tty:
            # Clear previous multi-line display
            self._clear_multi_lines()
            
            # Main status line
            status_content = (
                f"{progress_bar} {percentage:3.0f}% | "
                f"✓ {self.completed} 📝 {self.active} ✗ {self.failed} / {self.total_tasks} | "
                f"⏱️  {self._format_time(elapsed)}"
            )
            print(status_content)
            
            lines_printed = 1
            
            # Show active tasks per worker
            if self.active_tasks:
                print("\n🔄 Active Tasks:")
                lines_printed += 2
                
                for worker_id, (task_id, task_title, progress) in sorted(self.active_tasks.items()):
                    worker_spinner = self.spinner_frames[(self.spinner_index + worker_id) % len(self.spinner_frames)]
                    task_line = f"   {worker_spinner} Worker {worker_id}: {task_title[:50]}"
                    
                    # Add subtask progress if available
                    if task_id in self.task_subtasks:
                        current, total = self.task_subtasks[task_id]
                        task_line += f" [{current}/{total}]"
                    
                    if progress:
                        task_line += f" - {progress[:30]}"
                    
                    print(task_line)
                    lines_printed += 1
            else:
                # Show overall status when no active tasks
                print(f"\n{activity_indicator} {status[:80] if status else 'Waiting for tasks...'}")
                lines_printed += 2
            
            self.last_display_lines = lines_printed
            
        else:
            # For non-TTY (pipe, redirect), print each update on a new line
            status_line = (
                f"{progress_bar} {percentage:3.0f}% | "
                f"✓ {self.completed} 📝 {self.active} ✗ {self.failed} / {self.total_tasks} | "
                f"⏱️  {self._format_time(elapsed)} | "
                f"{activity_indicator} {status[:50]}"
            )
            print(status_line)
        
    def log_message(self, message: str, level: str = "INFO"):
        """Log a message while preserving the progress display"""
        # Clear current multi-line display
        self._clear_multi_lines()
        
        # Print the message
        timestamp = datetime.now().strftime("%H:%M:%S")
        if level == "ERROR":
            print(f"[{timestamp}] ❌ {message}")
        elif level == "SUCCESS":
            print(f"[{timestamp}] ✅ {message}")
        elif level == "WARNING":
            print(f"[{timestamp}] ⚠️  {message}")
        else:
            print(f"[{timestamp}] ℹ️  {message}")
        
        # Restore progress display
        self.update(force=True)
        
    def finish(self):
        """Complete the progress display"""
        self.update(force=True)
        if self.is_tty:
            print()  # New line after progress only for TTY
        
        # Print summary
        elapsed = time.time() - self.start_time
        print(f"\n📊 Summary:")
        print(f"   Total tasks: {self.total_tasks}")
        print(f"   Completed: {self.completed} ✅")
        print(f"   Failed: {self.failed} ❌")
        print(f"   Time elapsed: {self._format_time(elapsed)}")
        
        if self.completed > 0:
            avg_time = elapsed / self.completed
            print(f"   Average time per task: {self._format_time(avg_time)}")


def create_config(config_path: Optional[str] = None) -> Any:
    """Create configuration instance using enhanced or legacy system"""
    if CONFIG_MANAGER_AVAILABLE:
        # Use enhanced configuration management system
        config_paths = [config_path] if config_path else None
        config_manager = ConfigurationManager(config_paths)
        config_manager.load_configuration()
        
        # Validate configuration and show any issues
        validation_result = config_manager.get_validation_result()
        if not validation_result.is_valid:
            logger.error("Configuration validation failed:")
            for error in validation_result.errors:
                logger.error(f"  - {error}")
        
        if validation_result.warnings:
            logger.warning("Configuration warnings:")
            for warning in validation_result.warnings:
                logger.warning(f"  - {warning}")
        
        return EnhancedConfig(config_manager)
    else:
        # Fallback to legacy configuration
        return LegacyConfig(config_path)


# Legacy configuration fallback
class LegacyConfig:
    """Legacy configuration system for compatibility"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "orchestrator_config.json"
        self.config = self._load_config()
        
        # Add config_manager attribute for compatibility
        self.config_manager = None
        
        # Expose common attributes
        self._expose_attributes()
    
    def _load_config(self) -> dict:
        """Load configuration from JSON file"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            # Return default configuration
            return {
                "models": {
                    "manager": {"model": "claude-3-opus-20240229"},
                    "worker": {"model": "claude-3-5-sonnet-20241022"}
                },
                "execution": {
                    "max_workers": 3,
                    "worker_timeout": 1800,
                    "manager_timeout": 300,
                    "default_working_dir": None
                },
                "monitoring": {
                    "progress_interval": 10,
                    "verbose_logging": False
                }
            }
    
    def _expose_attributes(self):
        """Expose configuration values as attributes"""
        # Model configurations
        self.manager_model = self.config.get("models", {}).get("manager", {}).get("model", "claude-3-opus-20240229")
        self.worker_model = self.config.get("models", {}).get("worker", {}).get("model", "claude-3-5-sonnet-20241022")
        
        # Execution configurations
        exec_config = self.config.get("execution", {})
        self.max_workers = exec_config.get("max_workers", 3)
        self.worker_timeout = exec_config.get("worker_timeout", 1800)
        self.manager_timeout = exec_config.get("manager_timeout", 300)
        self.task_queue_timeout = exec_config.get("task_queue_timeout", 1.0)
        self.default_working_dir = exec_config.get("default_working_dir")
        self.max_turns = exec_config.get("max_turns")
        
        # Retry configurations
        self.max_retries = exec_config.get("max_retries", 3)
        self.retry_base_delay = exec_config.get("retry_base_delay", 1.0)
        self.retry_max_delay = exec_config.get("retry_max_delay", 60.0)
        
        # Monitoring configurations
        monitor_config = self.config.get("monitoring", {})
        self.progress_interval = monitor_config.get("progress_interval", 10)
        self.verbose_logging = monitor_config.get("verbose_logging", False)
        self.show_progress_bar = monitor_config.get("show_progress_bar", True)
        self.enable_opus_review = monitor_config.get("enable_opus_review", True)
        
        # Claude CLI configurations
        claude_config = self.config.get("claude_cli", {})
        self.claude_command = claude_config.get("command", "claude")
        self.claude_flags = claude_config.get("flags", {})
        self.claude_settings = claude_config.get("settings", {})
        self.claude_environment = claude_config.get("environment", {})
        
        # Notification configurations
        notif_config = self.config.get("notifications", {})
        self.slack_webhook_url = notif_config.get("slack_webhook_url")
        self.notify_on_task_complete = notif_config.get("notify_on_task_complete", True)
        self.notify_on_task_failed = notif_config.get("notify_on_task_failed", True)
        self.notify_on_all_complete = notif_config.get("notify_on_all_complete", True)
        
        # Git configurations
        git_config = self.config.get("git", {})
        self.git_auto_commit = git_config.get("auto_commit", False)
        self.git_commit_prefix = git_config.get("commit_message_prefix", "🤖 Auto-commit by Claude Orchestrator")
        
        # Locale configurations
        locale_config = self.config.get("locale", {})
        self.locale_language = locale_config.get("language", "en")
        
        # Bash configurations
        self.bash_default_timeout_ms = exec_config.get("bash_default_timeout_ms", 120000)
        self.bash_max_timeout_ms = exec_config.get("bash_max_timeout_ms", 600000)
        self.bash_max_output_length = exec_config.get("bash_max_output_length", 30000)
        
        # Legacy compatibility attributes
        self.usage_warning_threshold = monitor_config.get("usage_warning_threshold", 0.8)
        self.usage_critical_threshold = monitor_config.get("usage_critical_threshold", 0.95)


# Use Enhanced UI as default
ProgressDisplay = EnhancedProgressWrapper

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    COMPLETED = "done"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class WorkerTask:
    """Task to be processed by a Sonnet worker"""
    task_id: str
    title: str
    description: str
    details: Optional[str] = None
    dependencies: List[str] = None
    status: TaskStatus = TaskStatus.PENDING
    assigned_worker: Optional[int] = None
    result: Optional[str] = None
    error: Optional[str] = None
    status_message: Optional[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


# import requests  # Temporarily disabled for task creation

class SlackNotificationManager:
    """Manages Slack notifications for the orchestrator"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url
        
    def send_notification(self, message: str, emoji: str = ":robot_face:", blocks: Optional[List[Dict]] = None) -> bool:
        """Send a notification to Slack"""
        if not self.webhook_url:
            return False
            
        try:
            payload = {
                "text": message,
                "icon_emoji": emoji
            }
            
            if blocks:
                payload["blocks"] = blocks
                
            response = requests.post(self.webhook_url, json=payload)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False
    
    def send_task_complete(self, task_id: str, task_title: str) -> bool:
        """Send notification when a task is completed"""
        message = f"✅ Task completed: {task_id} - {task_title}"
        return self.send_notification(message, ":white_check_mark:")
    
    def send_task_failed(self, task_id: str, task_title: str, error: str) -> bool:
        """Send notification when a task fails"""
        message = f"❌ Task failed: {task_id} - {task_title}\nError: {error}"
        return self.send_notification(message, ":x:")
    
    def send_all_complete(self, total_tasks: int, completed: int, failed: int, elapsed_time: str) -> bool:
        """Send notification when all tasks are complete"""
        message = (f"All tasks complete!\n"
                  f"Total: {total_tasks} | Completed: {completed} | Failed: {failed}\n"
                  f"Time: {elapsed_time}")
        emoji = ":tada:" if failed == 0 else ":warning:"
        return self.send_notification(message, emoji)
    
    def send_opus_review(self, review_summary: str, task_results: List[Dict[str, Any]], elapsed_time: str, follow_up_count: int = 0) -> bool:
        """Send Opus review notification with structured blocks"""
        if not self.webhook_url:
            return False
        
        # Build blocks for the notification
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🎭 Opus Review Complete",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Summary:*\n{review_summary[:500]}..."
                }
            },
            {
                "type": "divider"
            }
        ]
        
        # Add task results (limit to first 10 to avoid message too large)
        if task_results:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Task Results:*"
                }
            })
            
        for i, result in enumerate(task_results[:10]):
            status_emoji = "✅" if result.get('status') == 'completed' else "❌"
            task_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_emoji} *{result.get('title', 'Unknown Task')}*\n_{result.get('summary', 'No summary available')}_"
                }
            }
            blocks.append(task_block)
        
        if len(task_results) > 10:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_... and {len(task_results) - 10} more tasks_"
                }
            })
        
        # Add follow-up tasks info if any
        if follow_up_count > 0:
            blocks.extend([
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🔧 *Follow-up Tasks Created:* {follow_up_count}\n_Run orchestrator again to process improvements_"
                    }
                }
            ])
        
        # Add footer with stats
        blocks.extend([
            {
                "type": "divider"
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⏱️ Total time: {elapsed_time} | 📊 Tasks: {len(task_results)} | 🤖 Orchestrator: Claude"
                    }
                ]
            }
        ])
        
        return self.send_notification("Opus Review Complete", ":robot_face:", blocks)


class TaskMasterInterface:
    """Interface to interact with native Task Master"""
    
    def __init__(self):
        self.task_manager = TaskManager()
        self.task_ai = TaskMasterAI(self.task_manager)
        self._subtask_cache = {}  # Cache subtask info to reduce performance impact
    
    def _format_task_output(self, task: TMTask) -> str:
        """Format task for output similar to CLI"""
        status_emoji = {
            'done': '✓',
            'in-progress': '►',
            'pending': '○',
            'review': '👁',
            'deferred': '⏱',
            'cancelled': '✗'
        }.get(task.status, '?')
        
        return f"{status_emoji} Task {task.id}: {task.title} (Priority: {task.priority})"
    
    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """Get the next available task"""
        task = self.task_manager.get_next_task()
        if task:
            return {
                'id': str(task.id),
                'title': task.title,
                'description': task.description,
                'status': task.status,
                'priority': task.priority,
                'dependencies': task.dependencies,
                'details': task.details
            }
        return None
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific task"""
        task = self.task_manager.get_task(task_id)
        if task:
            return {
                'id': str(task.id),
                'title': task.title,
                'description': task.description,
                'status': task.status,
                'priority': task.priority,
                'dependencies': task.dependencies,
                'details': task.details,
                'subtasks': [{
                    'id': f"{task.id}.{st.id}",
                    'title': st.title,
                    'status': st.status
                } for st in task.subtasks] if hasattr(task, 'subtasks') else []
            }
        return None
    
    def set_task_status(self, task_id: str, status: str) -> bool:
        """Set the status of a task"""
        return self.task_manager.update_task_status(task_id, status)
    
    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all tasks, optionally filtered by status"""
        all_tasks = self.task_manager.get_all_tasks()
        
        # Filter by status if specified
        if status:
            tasks = [t for t in all_tasks if t.status == status]
        else:
            tasks = all_tasks
        
        # Convert to dict format
        return [{
            'id': str(task.id),
            'title': task.title,
            'description': task.description,
            'status': task.status,
            'priority': task.priority,
            'dependencies': task.dependencies,
            'details': task.details
        } for task in tasks]
    
    def update_subtask(self, task_id: str, notes: str) -> bool:
        """Update subtask with implementation notes"""
        # For now, just log the update
        logger.info(f"Subtask {task_id} update: {notes}")
        return True
    
    def get_task_subtask_progress(self, task_id: str) -> tuple[int, int]:
        """Get subtask progress for a task (completed, total)"""
        # Check cache first
        if task_id in self._subtask_cache:
            cache_time, data = self._subtask_cache[task_id]
            if time.time() - cache_time < 5:  # Cache for 5 seconds
                return data
        
        result = self.task_manager.get_task_subtask_progress(task_id)
        
        # Cache the result
        self._subtask_cache[task_id] = (time.time(), result)
        return result
    
    def add_task(self, title: str, description: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Add a new task"""
        task = self.task_manager.add_task(title, description, **kwargs)
        if task:
            return {
                'id': str(task.id),
                'title': task.title,
                'description': task.description,
                'status': task.status,
                'priority': task.priority
            }
        return None
    
    def expand_task(self, task_id: str, num_subtasks: int = 5, use_research: bool = False) -> List[Dict[str, Any]]:
        """Expand a task into subtasks using AI"""
        subtasks = self.task_ai.expand_task(task_id, num_subtasks, use_research)
        return [{
            'id': f"{task_id}.{st.id}",
            'title': st.title,
            'description': st.description,
            'status': st.status
        } for st in subtasks]
    
    def parse_prd(self, prd_content: str, auto_add: bool = True) -> List[Dict[str, Any]]:
        """Parse PRD and create tasks"""
        tasks = self.task_ai.parse_prd(prd_content, auto_add)
        return [{
            'id': str(task.id),
            'title': task.title,
            'description': task.description,
            'status': task.status,
            'priority': task.priority
        } for task in tasks]


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


class SonnetWorker:
    """Sonnet model acting as a worker"""
    
    def __init__(self, worker_id: int, working_dir: str, config):
        self.worker_id = worker_id
        self.working_dir = working_dir
        self.config = config
        # Add execution validation flag if not present
        if not hasattr(self.config, 'validate_execution'):
            self.config.validate_execution = True
        self.task_master = TaskMasterInterface()
        self.session_tokens_used = 0
        self.session_start_time = time.time()
        self.tasks_completed = 0
        self.current_task = None  # Track current task for progress updates
        self.orchestrator = None  # Will be set by orchestrator
        
        # Initialize error handler
        self.error_handler = None
        if ERROR_HANDLER_AVAILABLE:
            self.error_handler = ClaudeErrorHandler(
                max_retries=getattr(config, 'max_retries', 3),
                base_delay=getattr(config, 'retry_base_delay', 1.0),
                max_delay=getattr(config, 'retry_max_delay', 60.0)
            )
        
        # Initialize Claude client (prefer direct API over subprocess)
        self.use_direct_api = DIRECT_API_AVAILABLE and getattr(config, 'use_direct_api', True)
        if self.use_direct_api:
            self.claude_client = create_claude_client(
                use_subprocess=False,
                model=config.worker_model
            )
            logger.info(f"Worker {worker_id} using direct Claude API")
        else:
            self.claude_client = None
            logger.info(f"Worker {worker_id} using subprocess mode")
        
        logger.info(f"Worker {worker_id} initialized in {working_dir}")
    
    def process_task(self, task: WorkerTask) -> WorkerTask:
        """Process a single task using Claude CLI"""
        logger.info(f"Worker {self.worker_id}: Starting task {task.task_id} - {task.title}")
        
        try:
            # Update task status in Task Master
            self.task_master.set_task_status(task.task_id, "in-progress")
            task.status_message = "Updating task status..."
            
            # Create a prompt for Claude
            prompt = self._create_claude_prompt(task)
            
            # Execute Claude command (will use retry logic if error handler is available)
            result = self._execute_claude_command(prompt)
            
            if result['success']:
                task.status = TaskStatus.COMPLETED
                task.result = result['output']
                self.task_master.set_task_status(task.task_id, "done")
                
                # Track usage
                if 'usage' in result:
                    usage = result['usage']
                    self.session_tokens_used += usage.get('tokens_used', 0)
                    self.tasks_completed += 1
                    
                    # Log usage warning if present
                    if usage.get('warning'):
                        logger.warning(f"Worker {self.worker_id} - Usage Warning: {usage['warning']}")
                        logger.warning(f"Total tokens used this session: {self.session_tokens_used}")
                
                # Update subtask with completion notes
                completion_notes = f"Completed by Worker {self.worker_id}. Output: {result['output'][:200]}..."
                self.task_master.update_subtask(task.task_id, completion_notes)
                
                logger.info(f"Worker {self.worker_id}: Completed task {task.task_id}")
            else:
                task.status = TaskStatus.FAILED
                task.error = result['error']
                
                # Check if it's a usage limit error
                if "USAGE LIMIT" in result['error']:
                    logger.error(f"Worker {self.worker_id}: USAGE LIMIT REACHED - Cannot continue processing")
                    # Set a flag to stop this worker
                    task.error = "USAGE_LIMIT_REACHED"
                else:
                    logger.error(f"Worker {self.worker_id}: Failed task {task.task_id} - {result['error']}")
                
                # Log request ID if available
                if 'request_id' in result and result['request_id']:
                    logger.error(f"Request ID for debugging: {result['request_id']}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"Worker {self.worker_id}: Exception processing task {task.task_id} - {e}")
        
        return task
    
    def _create_claude_prompt(self, task: WorkerTask) -> str:
        """Create a prompt for Claude based on the task"""
        prompt_parts = [
            f"Task ID: {task.task_id}",
            f"Title: {task.title}",
            f"Description: {task.description}"
        ]
        
        if task.details:
            prompt_parts.append(f"Details: {task.details}")
        
        prompt_parts.append("\nPlease complete this task. Start by analyzing what needs to be done, then implement the solution.")
        prompt_parts.append("\nIMPORTANT: If this task requires creating files, make sure to actually create them using the Write or Edit tools.")
        
        return "\n".join(prompt_parts)
    
    def _execute_claude_direct(self, prompt: str) -> Dict[str, Any]:
        """Execute Claude using direct API"""
        try:
            # Get allowed tools from config
            allowed_tools = self.config.claude_flags.get("allowed_tools", [])
            
            # Use direct API
            response = self.claude_client.execute_with_tools(prompt, allowed_tools)
            
            if response.success:
                return {
                    'success': True,
                    'output': response.output,
                    'usage': response.usage or {},
                    'request_id': response.request_id
                }
            else:
                return {
                    'success': False,
                    'error': response.error or "Unknown error",
                    'request_id': response.request_id
                }
                
        except Exception as e:
            logger.error(f"Direct API execution error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _execute_claude_command(self, prompt: str) -> Dict[str, Any]:
        """Wrapper for executing Claude command - uses error handler if available"""
        # Use direct API if available
        if self.use_direct_api and self.claude_client:
            return self._execute_claude_direct(prompt)
        
        # Fall back to subprocess mode
        if self.error_handler:
            return self.error_handler.execute_with_retry(
                self._execute_claude_command_internal, prompt
            )
        else:
            return self._execute_claude_command_internal(prompt)
    
    def _execute_claude_command_internal(self, prompt: str) -> Dict[str, Any]:
        """Execute Claude CLI command with the given prompt"""
        try:
            # First check if Claude CLI is available and authenticated
            test_cmd = [self.config.claude_command, "--version"]
            test_result = subprocess.run(test_cmd, capture_output=True, text=True)
            if test_result.returncode != 0:
                return {
                    'success': False,
                    'error': f"Claude CLI not available or not authenticated: {test_result.stderr}"
                }
            
            # Save prompt to temporary file to avoid shell escaping issues
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                prompt_file = f.name
            
            # Construct Claude command
            cmd = [
                self.config.claude_command,
                "-p", f"@{prompt_file}",
                "--model", self.config.worker_model
            ]
            
            # Add additional flags from config
            if self.config.claude_flags.get("verbose"):
                cmd.append("--verbose")
            if self.config.claude_flags.get("dangerously_skip_permissions"):
                cmd.append("--dangerously-skip-permissions")
            
            # Add other CLI flags
            if self.config.claude_flags.get("add_dir"):
                for dir_path in self.config.claude_flags["add_dir"]:
                    cmd.extend(["--add-dir", dir_path])
            
            if self.config.claude_flags.get("allowed_tools"):
                for tool in self.config.claude_flags["allowed_tools"]:
                    cmd.extend(["--allowedTools", tool])
            
            if self.config.claude_flags.get("disallowed_tools"):
                for tool in self.config.claude_flags["disallowed_tools"]:
                    cmd.extend(["--disallowedTools", tool])
            
            if self.config.claude_flags.get("output_format") and self.config.claude_flags["output_format"] != "text":
                cmd.extend(["--output-format", self.config.claude_flags["output_format"]])
            
            if self.config.claude_flags.get("input_format") and self.config.claude_flags["input_format"] != "text":
                cmd.extend(["--input-format", self.config.claude_flags["input_format"]])
            
            if self.config.max_turns:
                cmd.extend(["--max-turns", str(self.config.max_turns)])
            
            if self.config.claude_flags.get("permission_mode"):
                cmd.extend(["--permission-mode", self.config.claude_flags["permission_mode"]])
            
            if self.config.claude_flags.get("permission_prompt_tool"):
                cmd.extend(["--permission-prompt-tool", self.config.claude_flags["permission_prompt_tool"]])
            
            logger.debug(f"Worker {self.worker_id}: Executing command: {' '.join(cmd)}")
            
            # Set up environment variables
            env = os.environ.copy()
            
            # First check if ANTHROPIC_API_KEY is already in environment
            if "ANTHROPIC_API_KEY" not in env:
                # Try to get it from .env file
                try:
                    from dotenv import load_dotenv
                    load_dotenv()
                except ImportError:
                    pass
                
                # Check again after loading .env
                if "ANTHROPIC_API_KEY" not in os.environ:
                    # Try to get from config
                    api_key = self.config.claude_environment.get("ANTHROPIC_API_KEY")
                    if api_key:
                        env["ANTHROPIC_API_KEY"] = api_key
                    else:
                        logger.error("ANTHROPIC_API_KEY not found in environment or config")
                        return {
                            'success': False,
                            'error': "ANTHROPIC_API_KEY not configured"
                        }
            
            # Add other environment variables from config
            for key, value in self.config.claude_environment.items():
                if value is not None:
                    env[key] = str(value)
            
            # Execute command with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.working_dir,
                timeout=self.config.worker_timeout,
                env=env
            )
            
            # Clean up temp file
            os.unlink(prompt_file)
            
            if result.returncode == 0:
                # Try to parse usage information from output
                usage_info = self._parse_usage_info(result.stdout)
                
                return {
                    'success': True,
                    'output': result.stdout,
                    'usage': usage_info
                }
            else:
                # Extract error details
                error_msg = result.stderr or result.stdout
                request_id = self._extract_request_id(error_msg)
                
                return {
                    'success': False,
                    'error': error_msg,
                    'request_id': request_id
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f"Task execution timed out after {self.config.worker_timeout} seconds"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Exception during execution: {str(e)}"
            }
    
    def _parse_usage_info(self, output: str) -> Dict[str, Any]:
        """Parse usage information from Claude output"""
        usage = {}
        
        # Look for usage patterns in the output
        # This is a simplified parser - adjust based on actual Claude output format
        if "Usage:" in output or "Tokens:" in output:
            lines = output.split('\n')
            for line in lines:
                if "tokens" in line.lower():
                    # Try to extract token count
                    import re
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        usage['tokens_used'] = int(numbers[0])
                
                if "warning" in line.lower() and ("usage" in line.lower() or "limit" in line.lower()):
                    usage['warning'] = line.strip()
        
        return usage
    
    def _extract_request_id(self, error_msg: str) -> Optional[str]:
        """Extract request ID from error message for debugging"""
        import re
        # Look for patterns like "request_id: xxx" or "Request ID: xxx"
        match = re.search(r'(?:request_id|Request ID):\s*([a-zA-Z0-9-]+)', error_msg, re.IGNORECASE)
        if match:
            return match.group(1)
        return None


class ClaudeOrchestrator:
    """Main orchestrator coordinating Opus manager and Sonnet workers"""
    
    def __init__(self, config, working_dir: Optional[str] = None):
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
            logger.info("Rollback system initialized")
        
        # Initialize review integration
        from .review_applier import ReviewApplierIntegration
        self.review_integration = ReviewApplierIntegration(self.working_dir)
        
        # Verify working directory exists
        if not os.path.exists(self.working_dir):
            raise ValueError(f"Working directory does not exist: {self.working_dir}")
        
        logger.info(f"Orchestrator initialized in {self.working_dir}")
    
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
                
                # Apply review changes to code
                if self.use_progress_display and self.progress:
                    self.progress.log_message(f"📝 Applying review feedback for task {task.task_id}", "INFO")
                
                apply_result = self.review_integration.process_review_and_apply(
                    review_result, 
                    {'task_id': task.task_id, 'title': task.title}
                )
                
                if apply_result['applied']:
                    changes_count = len(apply_result['changes'])
                    if self.use_progress_display and self.progress:
                        self.progress.log_message(
                            f"✅ Applied {changes_count} changes from review to task {task.task_id}", 
                            "SUCCESS"
                        )
                    logger.info(f"Applied {changes_count} review changes to task {task.task_id}")
                    
                    # If significant changes were made, might need re-review
                    if apply_result['needs_re_review'] and changes_count > 2:
                        logger.info(f"Task {task.task_id} needs re-review after changes")
                        # Could put back in review queue, but for now just log
                elif apply_result['errors']:
                    if self.use_progress_display and self.progress:
                        self.progress.log_message(
                            f"⚠️ Failed to apply some review changes for task {task.task_id}", 
                            "WARNING"
                        )
                    logger.warning(f"Errors applying review: {apply_result['errors']}")
                else:
                    logger.error(f"Opus review failed for task {task.task_id}: {review_result.get('error', 'Unknown error')}")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in review loop: {e}")
        
        logger.info("Review loop stopped")
    
    def worker_loop(self, worker: SonnetWorker):
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
                            completed, total = self.task_master.get_task_subtask_progress(task_id)
                            if total > 0:
                                self.progress.set_task_subtasks(task_id, completed, total)
                        
                        # Update display
                        self.progress.update()
                        last_progress_update = current_time
                
                # Check if all tasks are done
                # First check if there are any pending tasks in TaskMaster
                all_taskmaster_tasks = self.task_master.list_tasks()
                has_pending_tasks = any(
                    task.get('status') in ['pending', 'in-progress'] 
                    for task in all_taskmaster_tasks
                )
                
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


def opus_add_task(description: str, config, task_interface: Optional[TaskMasterInterface] = None) -> bool:
    """Use Opus to intelligently add a task to Task Master"""
    logger.info(f"Using Opus to add task: {description}")
    
    # Use provided interface or create new one
    if not task_interface:
        task_interface = TaskMasterInterface()
    
    # Create progress display
    progress = ProgressDisplay(total_tasks=1)
    progress.update("🤖 Starting Opus to analyze and add task...")
    
    try:
        # Use native Task Master AI to parse and add tasks
        progress.update("🔄 Analyzing task description...")
        
        # Create a PRD-like format for the task description
        prd_content = f"""Task Request: {description}

Please analyze this task and break it down into logical, independent components that can be worked on in parallel.

Requirements:
- Identify independent components that can be worked on simultaneously
- Create separate tasks for features that affect different files/modules
- Only add dependencies when absolutely necessary
- Make tasks specific and actionable
"""
        
        # Use native Task Master AI to parse and create tasks
        progress.update("🧠 Using AI to analyze and create tasks...")
        
        tasks = task_interface.parse_prd(prd_content, auto_add=True)
        
        if tasks:
            progress.completed = 1
            progress.update(f"✅ Successfully created {len(tasks)} tasks!", force=True)
            logger.info(f"Created {len(tasks)} tasks from description")
            
            # Show created tasks
            print("\nCreated tasks:")
            for task in tasks:
                print(f"  - Task {task['id']}: {task['title']} (Priority: {task['priority']})")
            
            print("")  # New line after list
            return True
        else:
            progress.failed = 1
            progress.update("❌ Failed to create tasks", force=True)
            logger.error("Failed to parse description into tasks")
            print("")  # New line after progress
            return False
            
    except Exception as e:
        progress.failed = 1
        progress.update(f"❌ Error: {str(e)}", force=True)
        logger.error(f"Error using Opus to add task: {e}")
        print("")  # New line after progress
        return False


def opus_parse_file(file_path: str, config, task_interface: Optional[TaskMasterInterface] = None) -> bool:
    """Use Opus to parse a PRD or prompt file and add tasks to Task Master"""
    logger.info(f"Using Opus to parse file: {file_path}")
    
    # Use provided interface or create new one
    if not task_interface:
        task_interface = TaskMasterInterface()
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
        
        # Read file contents
        with open(file_path, 'r', encoding='utf-8') as f:
            file_contents = f.read()
        
        # Create progress display
        progress = ProgressDisplay(total_tasks=1)
        progress.update("📄 Parsing PRD file...")
        
        # Use native Task Master AI to parse PRD
        progress.update("🧠 Using AI to analyze and create tasks...")
        
        tasks = task_interface.parse_prd(file_contents, auto_add=True)
        
        if tasks:
            progress.completed = 1
            progress.update(f"✅ Successfully created {len(tasks)} tasks from PRD!", force=True)
            logger.info(f"Created {len(tasks)} tasks from {file_path}")
            
            # Show created tasks
            print("\nCreated tasks:")
            for task in tasks:
                print(f"  - Task {task['id']}: {task['title']} (Priority: {task['priority']})")
            
            print("")  # New line after list
            return True
        else:
            progress.failed = 1
            progress.update("❌ Failed to parse PRD", force=True)
            logger.error("Failed to parse PRD file")
            print("")  # New line after progress
            return False
            
    except Exception as e:
        logger.error(f"Error using Opus to parse file: {e}")
        return False


def check_claude_session_status():
    """Check Claude session status and usage"""
    print("\n🔍 Checking Claude session status...")
    
    try:
        # Try to get session info with a minimal prompt
        result = subprocess.run(
            ["claude", "-p", "Return only: OK"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Look for usage information in output
            output_lines = result.stdout.strip().split('\n')
            
            # Check for any warnings or usage info
            for line in output_lines:
                if "usage" in line.lower() or "limit" in line.lower() or "%" in line:
                    print(f"   {line}")
            
            print("✅ Claude session is active")
            return True
        else:
            print("❌ Claude session check failed")
            if result.stderr:
                print(f"   Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏱️  Session check timed out")
        return False
    except Exception as e:
        print(f"❌ Error checking session: {e}")
        return False


def init_project():
    """Initialize a new Claude Orchestrator project"""
    print("🚀 Initializing Claude Orchestrator project...")
    
    # Create default configuration file
    default_config = {
        "models": {
            "manager": {
                "model": "claude-3-opus-20240229",
                "description": "Opus model for planning and orchestration"
            },
            "worker": {
                "model": "claude-3-5-sonnet-20241022",
                "description": "Sonnet model for task execution"
            }
        },
        "execution": {
            "max_workers": 3,
            "worker_timeout": 1800,
            "manager_timeout": 300,
            "task_queue_timeout": 1.0,
            "default_working_dir": None,
            "max_turns": None,
            "max_retries": 3,
            "retry_base_delay": 1.0,
            "retry_max_delay": 60.0,
            "bash_default_timeout_ms": 120000,
            "bash_max_timeout_ms": 600000,
            "bash_max_output_length": 30000
        },
        "monitoring": {
            "progress_interval": 10,
            "verbose_logging": False,
            "show_progress_bar": True,
            "enable_opus_review": True,
            "usage_warning_threshold": 80,
            "check_usage_before_start": True
        },
        "claude_cli": {
            "command": "claude",
            "flags": {
                "verbose": False,
                "dangerously_skip_permissions": False,
                "allowed_tools": [],
                "disallowed_tools": [],
                "output_format": "text",
                "input_format": "text"
            },
            "settings": {},
            "environment": {}
        },
        "notifications": {
            "slack_webhook_url": None,
            "notify_on_task_complete": True,
            "notify_on_task_failed": True,
            "notify_on_all_complete": True
        },
        "git": {
            "auto_commit": False,
            "commit_message_prefix": "🤖 Auto-commit by Claude Orchestrator"
        },
        "locale": {
            "language": "en"
        }
    }
    
    # Check if config already exists
    config_path = "orchestrator_config.json"
    if os.path.exists(config_path):
        response = input(f"⚠️  Configuration file '{config_path}' already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("❌ Initialization cancelled")
            return False
    
    # Write configuration file
    try:
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"✅ Created configuration file: {config_path}")
    except Exception as e:
        print(f"❌ Failed to create configuration file: {e}")
        return False
    
    # Create .env file template
    env_path = ".env"
    if not os.path.exists(env_path):
        with open(env_path, 'w') as f:
            f.write("""# Claude Orchestrator Environment Variables

# Required: Your Anthropic API key
ANTHROPIC_API_KEY=your_api_key_here

# Optional: Perplexity API key for Task Master AI research
# PERPLEXITY_API_KEY=your_perplexity_key_here

# Optional: Slack webhook URL for notifications
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
""")
        print(f"✅ Created environment file template: {env_path}")
        print("   ⚠️  Please add your ANTHROPIC_API_KEY to .env")
    else:
        print(f"ℹ️  Environment file already exists: {env_path}")
    
    # Create .gitignore if it doesn't exist
    gitignore_path = ".gitignore"
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, 'w') as f:
            f.write(""".env
*.pyc
__pycache__/
.taskmaster/
.DS_Store
*.log
.venv/
venv/
""")
        print(f"✅ Created .gitignore file: {gitignore_path}")
    
    # Initialize Task Master
    try:
        from .task_master import TaskManager
        tm = TaskManager()
        print("✅ Task Master initialized")
    except Exception as e:
        print(f"⚠️  Could not initialize Task Master: {e}")
    
    print("\n✨ Project initialized successfully!")
    print("\nNext steps:")
    print("1. Add your ANTHROPIC_API_KEY to .env")
    print("2. Install dependencies with: uv pip install -e .")
    print("3. Run 'claude-orchestrator check' to verify setup")
    print("4. Run 'claude-orchestrator add \"your task\"' to add tasks")
    print("5. Run 'claude-orchestrator run' to execute tasks")
    
    return True


def main():
    """Main entry point for the orchestrator"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Claude Orchestrator - Opus Manager with Sonnet Workers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Task Management
  co list                               # List all tasks
  co list --filter-status pending       # List only pending tasks
  co list --show-subtasks              # List tasks with subtasks
  co show 1                            # Show details of task 1
  co next                              # Get next available task
  co update 1 --status in-progress     # Update task status
  co expand 1 --research               # Expand task into subtasks with AI research
  co delete 1                          # Delete a task
  
  # Task Creation
  co add "Create a REST API with authentication"    # Add a new task
  co parse requirements.txt                         # Parse PRD file
  
  # Orchestration
  co run                               # Run the orchestrator
  co run --workers 5                   # Run with 5 parallel workers
  co run --id 123                      # Run only task with ID 123
  
  # Setup & Status
  co init                              # Initialize project
  co check                             # Check setup
  co status                            # Check session status
  
  # Feedback Analysis
  co analyze-feedback 123              # Analyze feedback for task 123
  co worker-performance worker1        # Show performance metrics for worker
  co feedback-report                   # Generate comprehensive feedback report
  co export-metrics report.json        # Export metrics to file
  
  # Rollback Management
  co checkpoint "Before deployment"    # Create manual checkpoint
  co list-checkpoints                  # List available checkpoints
  co rollback cp_20250104_120000       # Rollback to specific checkpoint
        """
    )
    
    parser.add_argument('command', nargs='?', default='run', 
                       choices=['run', 'add', 'parse', 'check', 'status', 'init', 'list', 'show', 'next', 'update', 'expand', 'delete',
                               'analyze-feedback', 'worker-performance', 'feedback-report', 'export-metrics',
                               'checkpoint', 'rollback', 'list-checkpoints'],
                       help='Command to execute (default: run)')
    
    parser.add_argument('--config', '-c', 
                       help='Path to configuration file')
    
    parser.add_argument('--workers', '-w', type=int,
                       help='Override number of workers')
    
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    parser.add_argument('--no-progress', action='store_true',
                       help='Disable progress bar')
    
    parser.add_argument('--working-dir', '-d',
                       help='Set working directory for task execution')
    
    parser.add_argument('--id', type=str,
                       help='Run only a specific task by ID (e.g., --id 123)')
    
    # Add command specific arguments (using arg2 as a generic second argument)
    parser.add_argument('arg2', nargs='?',
                       help='Command argument (task description, file path, or task ID)')
    
    parser.add_argument('--status', '-s',
                       choices=['pending', 'in-progress', 'done', 'review', 'deferred', 'cancelled'],
                       help='Task status (for update command)')
    
    parser.add_argument('--priority', '-p',
                       choices=['high', 'medium', 'low'],
                       help='Task priority (for update command)')
    
    parser.add_argument('--filter-status',
                       choices=['pending', 'in-progress', 'done', 'review', 'deferred', 'cancelled'],
                       help='Filter tasks by status (for list command)')
    
    parser.add_argument('--show-subtasks', action='store_true',
                       help='Show subtasks in list (for list command)')
    
    parser.add_argument('--research', action='store_true',
                       help='Use AI research when expanding task (for expand command)')
    
    args = parser.parse_args()
    
    # Set up logging based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle init command before loading config
    if args.command == 'init':
        # Handle init command
        success = init_project()
        sys.exit(0 if success else 1)
    
    # Create configuration
    config = create_config(args.config)
    
    # Override verbose logging if specified
    if args.verbose:
        config.verbose_logging = True
    
    # Override progress bar if specified
    if args.no_progress:
        config.show_progress_bar = False
    
    # Handle different commands
    if args.command == 'check':
        print("🔍 Checking Claude Orchestrator setup...")
        
        # Check Claude CLI
        try:
            result = subprocess.run(["claude", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Claude CLI is installed")
                print(f"   Version: {result.stdout.strip()}")
            else:
                print("❌ Claude CLI is not installed or not in PATH")
                return 1
        except FileNotFoundError:
            print("❌ Claude CLI is not installed")
            print("   Please install: pip install claude-cli")
            return 1
        
        # Check API key
        api_key = os.environ.get("ANTHROPIC_API_KEY") or config.claude_environment.get("ANTHROPIC_API_KEY")
        if api_key:
            print("✅ ANTHROPIC_API_KEY is configured")
        else:
            print("❌ ANTHROPIC_API_KEY is not set")
            print("   Please set the environment variable or add to config")
            return 1
        
        # Check working directory
        working_dir = args.working_dir or config.default_working_dir or os.getcwd()
        if os.path.exists(working_dir):
            print(f"✅ Working directory exists: {working_dir}")
        else:
            print(f"❌ Working directory does not exist: {working_dir}")
            return 1
        
        # Check configuration
        print(f"✅ Configuration loaded from: {getattr(config, 'config_path', 'default')}")
        print(f"   Manager model: {config.manager_model}")
        print(f"   Worker model: {config.worker_model}")
        print(f"   Max workers: {config.max_workers}")
        
        # Check if Task Master is available
        try:
            from task_master import TaskManager
            print("✅ Native Task Master is available")
        except ImportError:
            print("⚠️  Native Task Master not found, will use CLI fallback")
        
        print("\n✨ Setup check complete!")
        return 0
        
    elif args.command == 'status':
        # Check Claude session status
        check_claude_session_status()
        return 0
        
    elif args.command == 'add':
        if not args.arg2:
            parser.error("Description is required for add command")
        args.description = args.arg2
            
        # Change to working directory if specified
        working_dir = getattr(args, 'working_dir', None)
        if working_dir:
            original_dir = os.getcwd()
            os.chdir(working_dir)
            logger.info(f"Changed to working directory: {working_dir}")
        
        try:
            # Use Opus to add task
            success = opus_add_task(args.description, config)
            sys.exit(0 if success else 1)
        finally:
            if working_dir:
                os.chdir(original_dir)
                
    elif args.command == 'parse':
        if not args.arg2:
            parser.error("File path is required for parse command")
        args.file_path = args.arg2
        
        # Change to working directory if specified
        working_dir = getattr(args, 'working_dir', None)
        if working_dir:
            original_dir = os.getcwd()
            os.chdir(working_dir)
            logger.info(f"Changed to working directory: {working_dir}")
        
        try:
            # Use Opus to parse file
            success = opus_parse_file(args.file_path, config)
            sys.exit(0 if success else 1)
        finally:
            if working_dir:
                os.chdir(original_dir)
    
    elif args.command == 'list':
        # List all tasks with optional filtering
        task_interface = TaskMasterInterface()
        tasks = task_interface.list_tasks(status=args.filter_status)
        
        if not tasks:
            print("No tasks found.")
            sys.exit(0)
        
        # Group tasks by status
        status_groups = {}
        for task in tasks:
            status = task['status']
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(task)
        
        # Display tasks
        print("\n📋 Task List")
        print("=" * 80)
        
        status_emojis = {
            'pending': '○',
            'in-progress': '►',
            'done': '✓',
            'review': '👁',
            'deferred': '⏱',
            'cancelled': '✗'
        }
        
        priority_colors = {
            'high': '🔴',
            'medium': '🟡',
            'low': '🟢'
        }
        
        for status in ['in-progress', 'pending', 'review', 'done', 'deferred', 'cancelled']:
            if status in status_groups:
                print(f"\n{status_emojis.get(status, '?')} {status.upper()} ({len(status_groups[status])})")
                print("-" * 40)
                
                for task in status_groups[status]:
                    priority_emoji = priority_colors.get(task.get('priority', 'medium'), '⚪')
                    print(f"{priority_emoji} [{task['id']}] {task['title'][:60]}")
                    
                    if args.show_subtasks and 'subtasks' in task and task['subtasks']:
                        for subtask in task['subtasks']:
                            subtask_emoji = status_emojis.get(subtask.get('status', 'pending'), '?')
                            print(f"    {subtask_emoji} {subtask['id']}: {subtask['title'][:50]}")
        
        # Show summary
        total = len(tasks)
        completed = len([t for t in tasks if t['status'] == 'done'])
        in_progress = len([t for t in tasks if t['status'] == 'in-progress'])
        pending = len([t for t in tasks if t['status'] == 'pending'])
        
        print(f"\n📊 Summary: Total: {total} | ✓ Done: {completed} | ► In Progress: {in_progress} | ○ Pending: {pending}")
        sys.exit(0)
    
    elif args.command == 'show':
        # Show detailed information about a specific task
        if not args.arg2:
            print("Error: Task ID required for show command")
            print("Usage: co show <task_id>")
            sys.exit(1)
        
        task_interface = TaskMasterInterface()
        task = task_interface.get_task(args.arg2)
        
        if not task:
            print(f"Error: Task {args.arg2} not found")
            sys.exit(1)
        
        # Display task details
        status_emoji = {
            'pending': '○',
            'in-progress': '►',
            'done': '✓',
            'review': '👁',
            'deferred': '⏱',
            'cancelled': '✗'
        }.get(task['status'], '?')
        
        priority_color = {
            'high': '🔴',
            'medium': '🟡',
            'low': '🟢'
        }.get(task.get('priority', 'medium'), '⚪')
        
        print(f"\n📋 Task Details")
        print("=" * 80)
        print(f"ID:          {task['id']}")
        print(f"Title:       {task['title']}")
        print(f"Status:      {status_emoji} {task['status']}")
        print(f"Priority:    {priority_color} {task.get('priority', 'medium')}")
        print(f"\nDescription:")
        print(f"  {task.get('description', 'No description')}")
        
        if task.get('details'):
            print(f"\nDetails:")
            print(f"  {task['details']}")
        
        if task.get('dependencies'):
            print(f"\nDependencies: {', '.join(map(str, task['dependencies']))}")
        
        if task.get('subtasks'):
            print(f"\nSubtasks ({len(task['subtasks'])}):")
            for st in task['subtasks']:
                st_emoji = {
                    'pending': '○',
                    'in-progress': '►',
                    'done': '✓'
                }.get(st.get('status', 'pending'), '?')
                print(f"  {st_emoji} {st['id']}: {st['title']}")
        
        sys.exit(0)
    
    elif args.command == 'next':
        # Get the next available task
        task_interface = TaskMasterInterface()
        next_task = task_interface.get_next_task()
        
        if not next_task:
            print("No available tasks. All tasks are either completed or have unmet dependencies.")
            sys.exit(0)
        
        print(f"\n📋 Next Task")
        print("=" * 80)
        print(f"ID:       {next_task['id']}")
        print(f"Title:    {next_task['title']}")
        print(f"Priority: {next_task.get('priority', 'medium')}")
        print(f"\nDescription:")
        print(f"  {next_task.get('description', 'No description')}")
        
        if next_task.get('details'):
            print(f"\nDetails:")
            print(f"  {next_task['details']}")
        
        print(f"\nTo start working on this task, run:")
        print(f"  co update {next_task['id']} --status in-progress")
        sys.exit(0)
    
    elif args.command == 'update':
        # Update task status or priority
        if not args.arg2:
            print("Error: Task ID required for update command")
            print("Usage: co update <task_id> --status <status> --priority <priority>")
            sys.exit(1)
        
        if not args.status and not args.priority:
            print("Error: Either --status or --priority must be specified")
            sys.exit(1)
        
        task_interface = TaskMasterInterface()
        
        # Update status if provided
        if args.status:
            success = task_interface.set_task_status(args.arg2, args.status)
            if success:
                print(f"✅ Updated task {args.arg2} status to: {args.status}")
            else:
                print(f"❌ Failed to update task {args.arg2} status")
                sys.exit(1)
        
        # Update priority if provided
        if args.priority:
            # This would need to be implemented in TaskMasterInterface
            print(f"⚠️  Priority update not yet implemented")
        
        sys.exit(0)
    
    elif args.command == 'expand':
        # Expand a task into subtasks using AI
        if not args.arg2:
            print("Error: Task ID required for expand command")
            print("Usage: co expand <task_id> [--research]")
            sys.exit(1)
        
        task_interface = TaskMasterInterface()
        
        print(f"🤖 Expanding task {args.arg2} using AI...")
        subtasks = task_interface.expand_task(args.arg2, use_research=args.research)
        
        if subtasks:
            print(f"\n✅ Created {len(subtasks)} subtasks:")
            for st in subtasks:
                print(f"  - {st['id']}: {st['title']}")
        else:
            print(f"❌ Failed to expand task {args.arg2}")
            sys.exit(1)
        
        sys.exit(0)
    
    elif args.command == 'delete':
        # Delete a task
        if not args.arg2:
            print("Error: Task ID required for delete command")
            print("Usage: co delete <task_id>")
            sys.exit(1)
        
        # Confirm deletion
        response = input(f"Are you sure you want to delete task {args.arg2}? (y/N): ")
        if response.lower() != 'y':
            print("Deletion cancelled")
            sys.exit(0)
        
        task_interface = TaskMasterInterface()
        # This would need to be implemented in TaskMasterInterface
        print(f"⚠️  Delete command not yet implemented")
        sys.exit(0)
                
    elif args.command == 'check':
        # Check Claude CLI setup
        check_result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True
        )
        
        if check_result.returncode == 0:
            print("✅ Claude CLI is properly set up")
            print(f"Version: {check_result.stdout.strip()}")
            
            # Also check session status
            check_claude_session_status()
        else:
            print("❌ Claude CLI is not properly set up")
            print("Please run: claude auth")
            sys.exit(1)
            
    elif args.command == 'analyze-feedback':
        # Analyze feedback for a specific task
        if not args.arg2:
            print("Error: Task ID required for analyze-feedback command")
            print("Usage: co analyze-feedback <task_id>")
            sys.exit(1)
        
        from .storage_factory import create_feedback_storage
        from .feedback_analyzer import FeedbackAnalyzer
        
        # Load config to get feedback settings
        config = create_config(args.config)
        feedback_config = getattr(config, 'feedback', {})
        
        storage = create_feedback_storage(feedback_config)
        analyzer = FeedbackAnalyzer(storage)
        
        print(f"\n📊 Analyzing feedback for task {args.arg2}...")
        analysis = analyzer.analyze_task(args.arg2)
        
        print(f"\n📋 Task Analysis Results")
        print("=" * 80)
        print(f"Task ID:         {analysis.task_id}")
        print(f"Feedback Count:  {analysis.feedback_count}")
        print(f"Success:         {'✅ Yes' if analysis.success else '❌ No'}")
        
        if analysis.execution_time:
            print(f"Avg Exec Time:   {analysis.execution_time:.2f}s")
        
        if analysis.quality_score:
            print(f"Quality Score:   {analysis.quality_score:.2%}")
        
        if analysis.error_messages:
            print(f"\n🚨 Errors ({len(analysis.error_messages)}):")
            for error in analysis.error_messages[:5]:
                print(f"  - {error}")
        
        if analysis.warnings:
            print(f"\n⚠️  Warnings ({len(analysis.warnings)}):")
            for warning in analysis.warnings[:5]:
                print(f"  - {warning}")
        
        if analysis.resource_usage:
            print(f"\n💻 Resource Usage:")
            for resource, value in analysis.resource_usage.items():
                print(f"  - {resource}: {value}")
        
        sys.exit(0)
    
    elif args.command == 'worker-performance':
        # Show worker performance metrics
        if not args.arg2:
            print("Error: Worker ID required for worker-performance command")
            print("Usage: co worker-performance <worker_id>")
            sys.exit(1)
        
        from .storage_factory import create_feedback_storage
        from .feedback_analyzer import FeedbackAnalyzer
        
        # Load config to get feedback settings
        config = create_config(args.config)
        feedback_config = getattr(config, 'feedback', {})
        
        storage = create_feedback_storage(feedback_config)
        analyzer = FeedbackAnalyzer(storage)
        
        print(f"\n📊 Analyzing performance for worker {args.arg2}...")
        perf = analyzer.analyze_worker_performance(args.arg2)
        
        print(f"\n👷 Worker Performance Report")
        print("=" * 80)
        print(f"Worker ID:       {perf.worker_id}")
        print(f"Total Tasks:     {perf.total_tasks}")
        print(f"Successful:      {perf.successful_tasks} ({perf.success_rate:.1%})")
        print(f"Failed:          {perf.failed_tasks} ({perf.error_rate:.1%})")
        print(f"Avg Exec Time:   {perf.average_execution_time:.2f}s")
        print(f"Avg Quality:     {perf.average_quality_score:.2%}")
        print(f"Avg Tokens:      {perf.average_tokens_used}")
        print(f"Recent Trend:    {perf.recent_trend.title()}")
        
        if perf.severity_distribution:
            print(f"\n📊 Severity Distribution:")
            for severity, count in perf.severity_distribution.items():
                print(f"  - {severity}: {count}")
        
        if perf.category_distribution:
            print(f"\n📂 Category Distribution:")
            for category, count in perf.category_distribution.items():
                print(f"  - {category}: {count}")
        
        sys.exit(0)
    
    elif args.command == 'feedback-report':
        # Generate comprehensive feedback report
        from .feedback_storage import FeedbackStorage
        from .feedback_analyzer import FeedbackAnalyzer
        from datetime import datetime, timedelta
        
        storage = FeedbackStorage()
        analyzer = FeedbackAnalyzer(storage)
        
        # Get time range (last 7 days by default)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        print(f"\n📊 Generating feedback report...")
        insights = analyzer.get_comprehensive_insights((start_time, end_time))
        
        print(f"\n📈 Comprehensive Feedback Report")
        print("=" * 80)
        print(f"Period:          {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
        print(f"Total Feedback:  {insights.total_feedback}")
        print(f"Success Rate:    {insights.overall_success_rate:.1%}")
        print(f"Error Rate:      {insights.overall_error_rate:.1%}")
        print(f"Avg Exec Time:   {insights.average_execution_time:.2f}s")
        print(f"Avg Quality:     {insights.average_quality_score:.2%}")
        
        if insights.high_performing_workers:
            print(f"\n🌟 High Performing Workers:")
            for worker in insights.high_performing_workers[:5]:
                print(f"  - {worker}")
        
        if insights.problematic_workers:
            print(f"\n⚠️  Problematic Workers:")
            for worker in insights.problematic_workers[:5]:
                print(f"  - {worker}")
        
        if insights.bottleneck_tasks:
            print(f"\n🐌 Bottleneck Tasks:")
            for task in insights.bottleneck_tasks[:5]:
                print(f"  - {task}")
        
        if insights.most_common_errors:
            print(f"\n🚨 Most Common Errors:")
            for error, count in insights.most_common_errors[:5]:
                print(f"  - {error[:50]}... (occurred {count} times)")
        
        if insights.recommendations:
            print(f"\n💡 Recommendations:")
            for i, rec in enumerate(insights.recommendations[:5], 1):
                print(f"  {i}. {rec}")
        
        sys.exit(0)
    
    elif args.command == 'export-metrics':
        # Export metrics to file
        if not args.arg2:
            print("Error: Output file path required for export-metrics command")
            print("Usage: co export-metrics <output_file>")
            sys.exit(1)
        
        from .storage_factory import create_feedback_storage
        from .feedback_analyzer import FeedbackAnalyzer
        
        # Load config to get feedback settings
        config = create_config(args.config)
        feedback_config = getattr(config, 'feedback', {})
        
        storage = create_feedback_storage(feedback_config)
        analyzer = FeedbackAnalyzer(storage)
        
        print(f"📊 Exporting metrics to {args.arg2}...")
        
        try:
            analyzer.export_analysis_report(args.arg2)
            print(f"✅ Metrics exported successfully to: {args.arg2}")
        except Exception as e:
            print(f"❌ Failed to export metrics: {e}")
            sys.exit(1)
        
        sys.exit(0)
    
    elif args.command == 'checkpoint':
        # Create manual checkpoint
        from .rollback_manager import RollbackManager, CheckpointType
        
        description = args.arg2 or "Manual checkpoint"
        
        print(f"📸 Creating checkpoint: {description}")
        
        rollback_manager = RollbackManager()
        checkpoint_id = rollback_manager.create_checkpoint(
            checkpoint_type=CheckpointType.MANUAL,
            description=description
        )
        
        print(f"✅ Checkpoint created: {checkpoint_id}")
        sys.exit(0)
    
    elif args.command == 'list-checkpoints':
        # List available checkpoints
        from .rollback_manager import RollbackManager
        
        rollback_manager = RollbackManager()
        checkpoints = rollback_manager.list_checkpoints()
        
        print(f"\n📋 Available Checkpoints")
        print("=" * 80)
        
        if not checkpoints:
            print("No checkpoints available")
        else:
            for cp in checkpoints:
                print(f"\n🔹 {cp.checkpoint_id}")
                print(f"   Created:     {cp.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   Type:        {cp.checkpoint_type.value}")
                print(f"   Description: {cp.description}")
                print(f"   Tasks:       {len(cp.task_states)}")
                print(f"   Files:       {len(cp.file_snapshots)}")
        
        print(f"\n📊 Total checkpoints: {len(checkpoints)}")
        sys.exit(0)
    
    elif args.command == 'rollback':
        # Rollback to checkpoint
        if not args.arg2:
            print("Error: Checkpoint ID required for rollback command")
            print("Usage: co rollback <checkpoint_id>")
            sys.exit(1)
        
        from .rollback_manager import RollbackManager, RollbackStrategy
        
        # Confirm rollback
        response = input(f"⚠️  Are you sure you want to rollback to checkpoint {args.arg2}? (y/N): ")
        if response.lower() != 'y':
            print("Rollback cancelled")
            sys.exit(0)
        
        print(f"⏮️  Rolling back to checkpoint {args.arg2}...")
        
        rollback_manager = RollbackManager()
        result = rollback_manager.rollback(
            args.arg2,
            strategy=RollbackStrategy.FULL
        )
        
        if result.success:
            print(f"✅ Rollback completed successfully")
            print(f"   Duration:       {result.duration_seconds:.2f}s")
            print(f"   Restored files: {len(result.restored_files)}")
            print(f"   Rolled back tasks: {len(result.rolled_back_tasks)}")
        else:
            print(f"❌ Rollback failed")
            for error in result.errors:
                print(f"   - {error}")
            sys.exit(1)
        
        sys.exit(0)
    
    elif args.command == 'run' or args.command is None:
        # Default behavior - run orchestrator
        # Override config with command line args if provided
        if hasattr(args, 'workers') and args.workers:
            if hasattr(config, 'config_manager'):
                # Enhanced config system
                config.config_manager.config["execution"]["max_workers"] = args.workers
            else:
                # Legacy config system
                config.config["execution"]["max_workers"] = args.workers
        
        # Check if specific task ID is requested
        specific_task_id = getattr(args, 'id', None)
        if specific_task_id:
            logger.info(f"Running only task with ID: {specific_task_id}")
        
        # Get working directory from args or config
        working_dir = getattr(args, 'working_dir', None)
        if not working_dir:
            working_dir = config.default_working_dir
            if working_dir and working_dir != os.getcwd():
                logger.info(f"Using default working directory from config: {working_dir}")
        
        # Change to working directory to ensure Task Master operates there
        if working_dir:
            original_dir = os.getcwd()
            os.chdir(working_dir)
            logger.info(f"Changed to working directory: {working_dir}")
        
        try:
            orchestrator = ClaudeOrchestrator(config, working_dir)
            orchestrator.run()
        finally:
            # Restore original directory if changed
            if working_dir:
                os.chdir(original_dir)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()