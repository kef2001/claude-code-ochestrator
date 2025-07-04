"""Enhanced Progress Display for Claude Orchestrator

A clean, organized terminal UI that clearly shows:
- Overall progress with visual indicators
- Worker status in a table format
- Task queue status
- Real-time updates without visual clutter
"""

import sys
import time
import threading
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import shutil
from enum import Enum


class WorkerState(Enum):
    """Worker states with emojis"""
    IDLE = ("💤", "Idle")
    WORKING = ("🔨", "Working")
    REVIEWING = ("👁️", "Reviewing")
    ERROR = ("❌", "Error")
    COMPLETED = ("✅", "Done")


@dataclass
class WorkerInfo:
    """Information about a worker"""
    id: str
    state: WorkerState
    current_task: Optional[str] = None
    task_title: Optional[str] = None
    progress: Optional[Tuple[int, int]] = None  # (current, total)
    start_time: Optional[float] = None


class EnhancedProgressDisplay:
    """Enhanced progress display with clean, organized layout"""
    
    def __init__(self, total_tasks: int = 0):
        self.total_tasks = total_tasks
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.active_tasks = 0
        
        # Worker management
        self.workers: Dict[str, WorkerInfo] = {}
        self.max_workers = 0
        
        # Task queue info
        self.queued_tasks = 0
        self.pending_reviews = 0
        
        # Display control
        self.is_tty = sys.stdout.isatty()
        self.terminal_width = shutil.get_terminal_size().columns
        self.last_display_lines = 0
        self.start_time = time.time()
        
        # Animation
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_index = 0
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Messages log (kept separate from progress display)
        self.messages: List[Tuple[str, str, float]] = []  # (message, level, timestamp)
        self.max_messages = 5
        
    def register_worker(self, worker_id: str):
        """Register a new worker"""
        with self.lock:
            self.workers[worker_id] = WorkerInfo(
                id=worker_id,
                state=WorkerState.IDLE
            )
            self.max_workers = max(self.max_workers, len(self.workers))
    
    def update_worker(self, worker_id: str, state: WorkerState, 
                     task_id: Optional[str] = None,
                     task_title: Optional[str] = None,
                     progress: Optional[Tuple[int, int]] = None):
        """Update worker status"""
        with self.lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                worker.state = state
                worker.current_task = task_id
                worker.task_title = task_title
                worker.progress = progress
                
                if state == WorkerState.WORKING and worker.start_time is None:
                    worker.start_time = time.time()
                elif state != WorkerState.WORKING:
                    worker.start_time = None
    
    def task_completed(self, success: bool = True):
        """Mark a task as completed"""
        with self.lock:
            if success:
                self.completed_tasks += 1
            else:
                self.failed_tasks += 1
            self.active_tasks = max(0, self.active_tasks - 1)
    
    def task_started(self):
        """Mark a task as started"""
        with self.lock:
            self.active_tasks += 1
    
    def update_queue_status(self, queued: int, pending_reviews: int):
        """Update queue information"""
        with self.lock:
            self.queued_tasks = queued
            self.pending_reviews = pending_reviews
    
    def add_message(self, message: str, level: str = "INFO"):
        """Add a message to the log"""
        with self.lock:
            self.messages.append((message, level, time.time()))
            if len(self.messages) > self.max_messages:
                self.messages.pop(0)
    
    def render(self):
        """Render the complete display"""
        if not self.is_tty:
            return
        
        with self.lock:
            # Clear previous display
            self._clear_display()
            
            # Build display sections
            lines = []
            
            # Header (single line)
            lines.append(self._render_header())
            lines.append("")
            
            # Overall progress
            progress_lines = self._render_progress_section()
            lines.append(progress_lines)
            lines.append("")
            
            # Worker status table
            worker_lines = self._render_workers_section()
            lines.extend(worker_lines)
            lines.append("")
            
            # Queue status (only if there's something to show)
            queue_line = self._render_queue_section()
            if queue_line and "Empty" not in queue_line:
                lines.append(queue_line)
                lines.append("")
            
            # Recent messages (limit to avoid screen overflow)
            message_lines = self._render_messages_section()
            if message_lines:
                lines.extend(message_lines[:6])  # Limit messages
            
            # Filter out empty lines at the end
            while lines and lines[-1] == "":
                lines.pop()
            
            # Output all lines
            output = "\n".join(lines) + "\n"
            sys.stdout.write(output)
            sys.stdout.flush()
            
            self.last_display_lines = len(lines) + 1  # +1 for final newline
            self.spinner_index = (self.spinner_index + 1) % len(self.spinner_frames)
    
    def _clear_display(self):
        """Clear the previous display"""
        if self.last_display_lines > 0:
            # Move cursor up and clear lines
            for _ in range(self.last_display_lines):
                sys.stdout.write("\033[A\033[K")
    
    def _render_header(self) -> str:
        """Render the header section"""
        elapsed = time.time() - self.start_time
        elapsed_str = self._format_time(elapsed)
        
        title = "🤖 Claude Orchestrator"
        time_str = f"⏱️  {elapsed_str}"
        
        # Center the title and right-align the time
        padding = self.terminal_width - len(title) - len(time_str) - 2
        return f"{title}{' ' * padding}{time_str}"
    
    def _render_progress_section(self) -> str:
        """Render the overall progress section"""
        lines = []
        
        # Progress bar
        progress_pct = (self.completed_tasks / self.total_tasks * 100) if self.total_tasks > 0 else 0
        bar_width = min(40, self.terminal_width - 30)
        filled = int(bar_width * progress_pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        lines.append(f"📊 Overall Progress: [{bar}] {progress_pct:.1f}%")
        
        # Statistics
        stats = [
            f"✅ Completed: {self.completed_tasks}",
            f"🔄 Active: {self.active_tasks}",
            f"❌ Failed: {self.failed_tasks}",
            f"📋 Total: {self.total_tasks}"
        ]
        lines.append("   " + " | ".join(stats))
        
        return "\n".join(lines)
    
    def _render_workers_section(self) -> List[str]:
        """Render the workers status table"""
        lines = ["👷 Workers:"]
        
        if not self.workers:
            lines.append("   No workers registered")
            return lines
        
        # Table header
        lines.append("   ┌─────────┬──────────┬─────────────────────────────────────┬──────────┐")
        lines.append("   │ Worker  │ Status   │ Current Task                        │ Progress │")
        lines.append("   ├─────────┼──────────┼─────────────────────────────────────┼──────────┤")
        
        # Worker rows
        for worker_id, worker in sorted(self.workers.items()):
            emoji, status = worker.state.value
            
            # Format task title
            if worker.task_title:
                task_display = worker.task_title[:35]
                if len(worker.task_title) > 35:
                    task_display += "..."
            else:
                task_display = "-"
            
            # Format progress
            if worker.progress:
                current, total = worker.progress
                progress = f"{current}/{total}"
            else:
                progress = "-"
            
            # Format status with spinner for active workers
            if worker.state == WorkerState.WORKING:
                spinner = self.spinner_frames[self.spinner_index]
                status_display = f"{emoji} {spinner} {status}"
            else:
                status_display = f"{emoji} {status}"
            
            lines.append(f"   │ {worker_id:<7} │ {status_display:<8} │ {task_display:<35} │ {progress:<8} │")
        
        lines.append("   └─────────┴──────────┴─────────────────────────────────────┴──────────┘")
        
        return lines
    
    def _render_queue_section(self) -> str:
        """Render the queue status section"""
        items = []
        
        if self.queued_tasks > 0:
            items.append(f"📥 Queued: {self.queued_tasks}")
        
        if self.pending_reviews > 0:
            items.append(f"👁️  Reviews: {self.pending_reviews}")
        
        if not items:
            return ""  # Don't show empty queue
        
        return "📦 Queue: " + " | ".join(items)
    
    def _render_messages_section(self) -> List[str]:
        """Render recent messages section"""
        if not self.messages:
            return []
        
        lines = ["💬 Recent Activity:"]
        
        # Level emojis
        level_emojis = {
            "INFO": "ℹ️ ",
            "SUCCESS": "✅",
            "WARNING": "⚠️ ",
            "ERROR": "❌",
            "DEBUG": "🔍"
        }
        
        for message, level, timestamp in self.messages[-self.max_messages:]:
            emoji = level_emojis.get(level, "•")
            # Truncate message if too long
            max_msg_len = self.terminal_width - 10
            if len(message) > max_msg_len:
                message = message[:max_msg_len-3] + "..."
            lines.append(f"   {emoji} {message}")
        
        return lines
    
    def _format_time(self, seconds: float) -> str:
        """Format elapsed time"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            mins = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}h {mins}m"
    
    def clear(self):
        """Clear the entire display"""
        if self.is_tty and self.last_display_lines > 0:
            self._clear_display()
            self.last_display_lines = 0


# Example usage wrapper for easy integration
class ProgressDisplayAdapter:
    """Adapter to make the new display compatible with existing code"""
    
    def __init__(self, total_tasks: int = 0):
        self.display = EnhancedProgressDisplay(total_tasks)
        self.total_tasks = total_tasks
        self.completed = 0
        self.active = 0
        self.failed = 0
        
    def update(self, status: str = "", force: bool = False):
        """Update the display"""
        self.display.render()
    
    def set_worker_task(self, worker_id: str, task_id: str, task_title: str, progress: str = ""):
        """Set worker task"""
        # Parse progress if provided (e.g., "2/5" -> (2, 5))
        progress_tuple = None
        if "/" in progress:
            try:
                current, total = progress.split("/")
                progress_tuple = (int(current), int(total))
            except:
                pass
        
        self.display.update_worker(
            worker_id,
            WorkerState.WORKING,
            task_id,
            task_title,
            progress_tuple
        )
        self.display.render()
    
    def clear_worker_task(self, worker_id: str):
        """Clear worker task"""
        self.display.update_worker(worker_id, WorkerState.IDLE)
        self.display.render()
    
    def log_message(self, message: str, level: str = "INFO"):
        """Log a message"""
        self.display.add_message(message, level)
        self.display.render()
    
    def increment_completed(self):
        """Increment completed count"""
        self.completed += 1
        self.display.task_completed(True)
        self.display.render()
    
    def increment_failed(self):
        """Increment failed count"""
        self.failed += 1
        self.display.task_completed(False)
        self.display.render()