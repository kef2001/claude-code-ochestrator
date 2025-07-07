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

# Import data models
from .models import TaskStatus, WorkerTask

# Import direct Claude API
try:
    from .claude_direct_api import create_claude_client, ClaudeResponse
    DIRECT_API_AVAILABLE = True
except ImportError:
    DIRECT_API_AVAILABLE = False
    logger.warning("Direct Claude API not available, will use subprocess mode")

# Import the configuration management system
from .config_manager import ConfigurationManager, EnhancedConfig, ConfigValidationResult
    
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


def create_config(config_path: Optional[str] = None) -> EnhancedConfig:
    """Create configuration instance using enhanced configuration management system"""
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

# Use Enhanced UI as default
ProgressDisplay = EnhancedProgressWrapper

from .slack_notifier import SlackNotificationManager

# Note: Removed orphaned class methods that were misplaced

from .manager import OpusManager
from .worker import SonnetWorker
from .orchestrator import ClaudeOrchestrator


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
    
    def parse_prd(self, prd_content: str, auto_add: bool = True) -> List[Dict[str, Any]]:
        """Parse PRD content and create tasks"""
        try:
            tasks = self.task_ai.parse_prd(prd_content, auto_add=auto_add)
            return [{
                'id': str(task.id),
                'title': task.title,
                'description': task.description,
                'status': task.status,
                'priority': task.priority,
                'dependencies': task.dependencies,
                'details': task.details
            } for task in tasks]
        except Exception as e:
            logger.error(f"Error parsing PRD: {e}")
            return []
    
    def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed"""
        return self.task_manager.update_task_status(task_id, 'done')


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
  
  # Test Monitoring
  co test-status                       # Show test monitoring status
  co test-report                       # Generate test report
  co run-tests                         # Manually run all tests
  co run-tests pytest                  # Run specific test suite
  
  # Security
  co security-audit                    # Run security audit for API keys
        """
    )
    
    parser.add_argument('command', nargs='?', default='run', 
                       choices=['run', 'add', 'parse', 'check', 'status', 'init', 'list', 'show', 'next', 'update', 'expand', 'delete',
                               'analyze-feedback', 'worker-performance', 'feedback-report', 'export-metrics',
                               'checkpoint', 'rollback', 'list-checkpoints',
                               'test-status', 'test-report', 'run-tests',
                               'feedback-shell', 'security-audit'],
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
            # Validate API key format
            from claude_orchestrator.security_utils import validate_api_key
            if validate_api_key(api_key):
                print("✅ ANTHROPIC_API_KEY is configured and valid")
            else:
                print("⚠️  ANTHROPIC_API_KEY format appears invalid")
                print("   API keys should start with 'sk-' and be at least 40 characters")
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
    
    elif args.command == 'test-status':
        # Show test monitoring status
        config = create_config(args.config)
        orchestrator = ClaudeOrchestrator(config, None)
        
        if orchestrator.test_monitor:
            status = orchestrator.test_monitor.get_test_summary()
            
            print("\n📊 Test Monitoring Status")
            print("=" * 80)
            print(f"Total Test Suites: {status['total_suites']}")
            print(f"Total Test Files: {status['total_test_files']}")
            
            if status['suites']:
                print("\n📋 Test Suites:")
                for suite_name, suite_info in status['suites'].items():
                    status_icon = "✅" if suite_info['last_status'] == 'passed' else "❌" if suite_info['last_status'] == 'failed' else "⏳"
                    print(f"\n{status_icon} {suite_name}")
                    print(f"   Files: {suite_info['test_files']}")
                    if suite_info['last_run']:
                        print(f"   Last Run: {suite_info['last_run']}")
                        print(f"   Results: {suite_info['passed_tests']}/{suite_info['total_tests']} passed")
                        print(f"   Avg Duration: {suite_info['average_duration']:.2f}s")
            
            if 'last_24h' in status:
                print(f"\n📈 Last 24 Hours:")
                stats = status['last_24h']
                print(f"   Total Runs: {stats['total_runs']}")
                print(f"   Passed: {stats['passed']} ({stats['passed']/stats['total_runs']*100:.1f}%)")
                print(f"   Failed: {stats['failed']}")
                print(f"   Avg Duration: {stats['average_duration']:.2f}s")
            
            # Show failing tests
            failing = orchestrator.test_monitor.get_failing_tests()
            if failing:
                print(f"\n❌ Failing Tests ({len(failing)}):")
                for test in failing[:5]:
                    print(f"   - {test.test_name}")
                    if test.error_message:
                        print(f"     Error: {test.error_message[:60]}...")
        else:
            print("❌ Test monitoring is not enabled")
            print("   Enable it in config: test_monitoring.enabled = true")
        
        sys.exit(0)
    
    elif args.command == 'test-report':
        # Generate test report
        config = create_config(args.config)
        orchestrator = ClaudeOrchestrator(config, None)
        
        if orchestrator.test_monitor:
            output_file = args.arg2 if args.arg2 else None
            report = orchestrator.test_monitor.generate_test_report(output_file)
            print(report)
        else:
            print("❌ Test monitoring is not enabled")
        
        sys.exit(0)
    
    elif args.command == 'run-tests':
        # Manually trigger test run
        config = create_config(args.config)
        orchestrator = ClaudeOrchestrator(config, None)
        
        if orchestrator.test_monitor:
            suite_name = args.arg2 if args.arg2 else None
            
            print("🧪 Running tests...")
            if suite_name:
                success = orchestrator.test_monitor.trigger_test_run(suite_name)
                if success:
                    print(f"✅ Triggered test suite: {suite_name}")
                else:
                    print(f"❌ Test suite not found: {suite_name}")
            else:
                # Run all tests
                orchestrator.test_monitor.discover_tests()
                results = orchestrator.test_monitor.run_tests()
                
                passed = sum(1 for r in results if r.status.value == 'passed')
                failed = sum(1 for r in results if r.status.value == 'failed')
                
                print(f"\n📊 Test Results:")
                print(f"   Total: {len(results)}")
                print(f"   Passed: {passed}")
                print(f"   Failed: {failed}")
                
                if failed > 0:
                    print(f"\n❌ Failed Tests:")
                    for result in results:
                        if result.status.value == 'failed':
                            print(f"   - {result.test_name}")
                            if result.error_message:
                                print(f"     {result.error_message[:100]}...")
        else:
            print("❌ Test monitoring is not enabled")
        
        sys.exit(0)
    
    elif args.command == 'security-audit':
        # Run security audit
        from claude_orchestrator.security_utils import perform_security_audit, check_file_permissions
        
        print("\n🔒 Running Security Audit...")
        print("=" * 80)
        
        # Run the audit
        findings = perform_security_audit()
        
        if findings:
            print("\n⚠️  Security Findings:")
            for finding in findings:
                print(f"  - {finding}")
        else:
            print("\n✅ No security issues found")
        
        # Check for common security files
        print("\n📋 Security File Checks:")
        security_files = ['.env', '.env.example', 'SECURITY.md', 'LICENSE']
        for file in security_files:
            if os.path.exists(file):
                perms = check_file_permissions(file)
                if perms['exists']:
                    status = "✅" if not perms['recommendations'] else "⚠️"
                    print(f"{status} {file}")
                    for rec in perms['recommendations']:
                        print(f"    - {rec}")
            else:
                print(f"❌ {file} (not found)")
        
        # Check for hardcoded secrets
        print("\n🔍 Scanning for potential secrets...")
        import subprocess
        try:
            # Use ripgrep to search for potential API keys
            result = subprocess.run(['rg', '-i', 'sk-[a-zA-Z0-9\\-]{40,}', '--type', 'py', '--glob', '!security_utils.py'],
                                  capture_output=True, text=True)
            if result.returncode == 0 and result.stdout:
                print("⚠️  Potential API keys found in code:")
                for line in result.stdout.strip().split('\n')[:5]:  # Show first 5 matches
                    print(f"    {line}")
            else:
                print("✅ No hardcoded API keys found")
        except FileNotFoundError:
            print("⚠️  ripgrep (rg) not found, skipping secret scanning")
        
        print("\n✨ Security audit complete!")
        sys.exit(0)
    
    elif args.command == 'feedback-shell':
        # Launch interactive feedback shell
        try:
            # Import here to avoid circular imports
            import cmd
            import readline
            from tabulate import tabulate
            
            # Create minimal cmd interface
            class FeedbackShell(cmd.Cmd):
                intro = '\n🔔 Interactive Feedback Shell\nType "help" for commands, "exit" to quit\n'
                prompt = 'feedback> '
                
                def __init__(self, storage):
                    super().__init__()
                    self.storage = storage
                
                def do_list(self, arg):
                    """List recent feedback entries"""
                    feedbacks = self.storage.query(limit=10)
                    if feedbacks:
                        data = [[f.feedback_id[:8], f.timestamp.strftime('%Y-%m-%d %H:%M'), 
                                f.feedback_type.value, f.message[:50]] for f in feedbacks]
                        print(tabulate(data, headers=['ID', 'Time', 'Type', 'Message']))
                    else:
                        print("No feedback entries found")
                
                def do_show(self, feedback_id):
                    """Show detailed feedback entry"""
                    if not feedback_id:
                        print("Usage: show <feedback_id>")
                        return
                    feedback = self.storage.load(feedback_id)
                    if feedback:
                        print(f"\nID: {feedback.feedback_id}")
                        print(f"Type: {feedback.feedback_type.value}")
                        print(f"Message: {feedback.message}")
                        print(f"Time: {feedback.timestamp}")
                    else:
                        print(f"Feedback {feedback_id} not found")
                
                def do_stats(self, arg):
                    """Show feedback statistics"""
                    stats = self.storage.get_statistics() if hasattr(self.storage, 'get_statistics') else {}
                    print(f"\n📊 Feedback Statistics")
                    print(f"Total: {self.storage.count()}")
                    if 'type_counts' in stats:
                        print("\nBy Type:")
                        for t, c in stats['type_counts'].items():
                            print(f"  {t}: {c}")
                
                def do_exit(self, arg):
                    """Exit the shell"""
                    return True
                
                def do_quit(self, arg):
                    """Exit the shell"""
                    return True
            
            # Create and run shell
            config = create_config(args.config)
            if hasattr(config, 'feedback') and config.feedback.get('enabled', True):
                from .storage_factory import create_feedback_storage
                storage = create_feedback_storage(config.feedback)
                shell = FeedbackShell(storage)
                shell.cmdloop()
            else:
                print("❌ Feedback system is not enabled")
                
        except ImportError as e:
            print(f"❌ Required module not available: {e}")
            print("   Install with: pip install tabulate")
        except KeyboardInterrupt:
            print("\nExiting...")
        except Exception as e:
            print(f"❌ Error: {e}")
        
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