"""Integration patch to use EnhancedProgressDisplay in the orchestrator

This module provides a drop-in replacement for the existing ProgressDisplay
that offers a cleaner, more organized terminal UI.
"""

import sys
import time
import threading
from typing import Optional, Dict, Any
from .enhanced_progress_display import EnhancedProgressDisplay, WorkerState


class ProgressDisplay:
    """Drop-in replacement for existing ProgressDisplay using the enhanced version"""
    
    def __init__(self, total_tasks: int = 0):
        self.display = EnhancedProgressDisplay(total_tasks)
        self.total_tasks = total_tasks
        self.completed = 0
        self.active = 0
        self.failed = 0
        
        # Compatibility attributes
        self.active_tasks: Dict[str, Any] = {}
        self.task_subtasks: Dict[str, tuple] = {}
        self.is_tty = sys.stdout.isatty()
        self.display_thread = None
        self.running = False
        
        # Start auto-refresh thread for smooth animations
        if self.is_tty:
            self._start_refresh_thread()
    
    def _start_refresh_thread(self):
        """Start background thread for smooth UI updates"""
        self.running = True
        self.display_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self.display_thread.start()
    
    def _refresh_loop(self):
        """Background refresh loop for smooth animations"""
        while self.running:
            self.display.render()
            time.sleep(0.1)  # 10 FPS refresh rate
    
    def update(self, status: str = "", force: bool = False):
        """Update the display (compatibility method)"""
        # Update queue status if provided
        if "tasks in queue" in status.lower():
            try:
                queued = int(status.split()[0])
                self.display.update_queue_status(queued, 0)
            except:
                pass
        
        # Update display counters to match current state
        self.display.completed_tasks = self.completed
        self.display.active_tasks = self.active
        self.display.failed_tasks = self.failed
        
        # Manual render if not using auto-refresh
        if not self.running:
            self.display.render()
    
    def set_worker_task(self, worker_id: str, task_id: str, task_title: str, progress: str = ""):
        """Set worker task with progress"""
        # Register worker if not exists
        if worker_id not in self.display.workers:
            self.display.register_worker(worker_id)
        
        # Parse progress
        progress_tuple = None
        if progress and "/" in progress:
            try:
                parts = progress.strip("[]").split("/")
                if len(parts) == 2:
                    progress_tuple = (int(parts[0]), int(parts[1]))
            except:
                pass
        
        # Update worker state
        self.display.update_worker(
            worker_id,
            WorkerState.WORKING,
            task_id,
            task_title,
            progress_tuple
        )
        
        # Track for compatibility
        self.active_tasks[worker_id] = (task_id, task_title, progress)
    
    def clear_worker_task(self, worker_id: str):
        """Clear worker task"""
        self.display.update_worker(worker_id, WorkerState.IDLE)
        if worker_id in self.active_tasks:
            del self.active_tasks[worker_id]
    
    def set_task_subtasks(self, task_id: str, current: int, total: int):
        """Set subtask progress for a task"""
        self.task_subtasks[task_id] = (current, total)
        
        # Update worker if this task is active
        for worker_id, (tid, _, _) in self.active_tasks.items():
            if tid == task_id:
                worker = self.display.workers.get(worker_id)
                if worker:
                    self.display.update_worker(
                        worker_id,
                        WorkerState.WORKING,
                        task_id,
                        worker.task_title,
                        (current, total)
                    )
    
    def log_message(self, message: str, level: str = "INFO"):
        """Log a message to the display"""
        self.display.add_message(message, level)
    
    def update_totals(self, completed: int, active: int, failed: int):
        """Update task totals"""
        self.completed = completed
        self.active = active
        self.failed = failed
        
        # Update display counters
        self.display.completed_tasks = completed
        self.display.active_tasks = active
        self.display.failed_tasks = failed
        
        # Force render to show updated counts
        if self.is_tty:
            self.display.render()
    
    def stop(self):
        """Stop the display and cleanup"""
        self.running = False
        if self.display_thread:
            self.display_thread.join(timeout=1)
        self.display.clear()
    
    def __del__(self):
        """Cleanup on deletion"""
        self.stop()


# Additional helper for monitoring task states
class TaskStateMonitor:
    """Monitors and displays task state changes clearly"""
    
    def __init__(self, progress_display: ProgressDisplay):
        self.display = progress_display
        self.task_states: Dict[str, str] = {}
        
    def update_task_state(self, task_id: str, old_state: str, new_state: str, title: str = ""):
        """Update task state and log the change"""
        if old_state != new_state:
            # Create clear state transition message
            state_emojis = {
                "pending": "⏳",
                "in-progress": "🔄",
                "done": "✅",
                "failed": "❌",
                "review": "👁️"
            }
            
            old_emoji = state_emojis.get(old_state, "❓")
            new_emoji = state_emojis.get(new_state, "❓")
            
            if title:
                message = f"Task {task_id}: {old_emoji} {old_state} → {new_emoji} {new_state} - {title[:30]}"
            else:
                message = f"Task {task_id}: {old_emoji} {old_state} → {new_emoji} {new_state}"
            
            # Log with appropriate level
            if new_state == "done":
                level = "SUCCESS"
            elif new_state == "failed":
                level = "ERROR"
            elif new_state == "in-progress":
                level = "INFO"
            else:
                level = "INFO"
            
            self.display.log_message(message, level)
            self.task_states[task_id] = new_state


# Usage example for the orchestrator
def integrate_enhanced_display(orchestrator):
    """
    Integrate the enhanced display into the orchestrator
    
    Example:
        orchestrator.progress = ProgressDisplay(total_tasks=len(tasks))
        orchestrator.task_monitor = TaskStateMonitor(orchestrator.progress)
    """
    pass