#!/usr/bin/env python3
"""
Fix Enhanced UI display issues
"""

import sys
import os
from pathlib import Path

def fix_display_issues():
    """Fix the display rendering issues"""
    
    print("🔧 Fixing Enhanced UI display issues...")
    print("=" * 50)
    
    # Read the enhanced progress display file
    display_file = Path("claude_orchestrator/enhanced_progress_display.py")
    
    if not display_file.exists():
        print("❌ Enhanced progress display file not found!")
        return False
    
    with open(display_file, 'r') as f:
        content = f.read()
    
    # Fix 1: Improve render method to prevent duplicates
    old_render = '''    def render(self):
        """Render the complete display"""
        if not self.is_tty:
            return
        
        with self.lock:
            # Clear previous display
            self._clear_display()
            
            # Build display sections
            lines = []
            
            # Header
            lines.append(self._render_header())
            lines.append("")
            
            # Overall progress
            lines.append(self._render_progress_section())
            lines.append("")
            
            # Worker status table
            lines.extend(self._render_workers_section())
            lines.append("")
            
            # Queue status
            lines.append(self._render_queue_section())
            lines.append("")
            
            # Recent messages
            lines.extend(self._render_messages_section())
            
            # Output all lines
            output = "\\n".join(lines)
            sys.stdout.write(output)
            sys.stdout.flush()
            
            self.last_display_lines = len(lines)
            self.spinner_index = (self.spinner_index + 1) % len(self.spinner_frames)'''
    
    new_render = '''    def render(self):
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
            output = "\\n".join(lines) + "\\n"
            sys.stdout.write(output)
            sys.stdout.flush()
            
            self.last_display_lines = len(lines) + 1  # +1 for final newline
            self.spinner_index = (self.spinner_index + 1) % len(self.spinner_frames)'''
    
    # Fix 2: Improve worker status display
    old_workers = '''    def _render_workers_section(self) -> List[str]:
        """Render the workers status table"""
        lines = ["👷 Workers:"]
        
        if not self.workers:
            lines.append("   No workers registered")
            return lines
        
        # Table header
        lines.append("   ┌─────────┬────────┬─────────────────────────────────────┬──────────┐")
        lines.append("   │ Worker  │ Status │ Current Task                        │ Progress │")
        lines.append("   ├─────────┼────────┼─────────────────────────────────────┼──────────┤")
        
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
            
            # Add spinner for active workers
            if worker.state == WorkerState.WORKING:
                spinner = self.spinner_frames[self.spinner_index]
                status = f"{spinner} {status}"
            
            lines.append(f"   │ {worker_id:<7} │ {emoji} {status:<5} │ {task_display:<35} │ {progress:<8} │")
        
        lines.append("   └─────────┴────────┴─────────────────────────────────────┴──────────┘")
        
        return lines'''
    
    new_workers = '''    def _render_workers_section(self) -> List[str]:
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
        
        return lines'''
    
    # Apply fixes
    content = content.replace(old_render, new_render)
    content = content.replace(old_workers, new_workers)
    
    # Fix 3: Improve queue section to avoid "sed Opus review" text
    old_queue = '''    def _render_queue_section(self) -> str:
        """Render the queue status section"""
        items = []
        
        if self.queued_tasks > 0:
            items.append(f"📥 Queued: {self.queued_tasks}")
        
        if self.pending_reviews > 0:
            items.append(f"👁️  Pending Review: {self.pending_reviews}")
        
        if not items:
            return "📦 Queue: Empty"
        
        return "📦 Queue: " + " | ".join(items)'''
    
    new_queue = '''    def _render_queue_section(self) -> str:
        """Render the queue status section"""
        items = []
        
        if self.queued_tasks > 0:
            items.append(f"📥 Queued: {self.queued_tasks}")
        
        if self.pending_reviews > 0:
            items.append(f"👁️  Reviews: {self.pending_reviews}")
        
        if not items:
            return ""  # Don't show empty queue
        
        return "📦 Queue: " + " | ".join(items)'''
    
    content = content.replace(old_queue, new_queue)
    
    # Write the fixed content
    with open(display_file, 'w') as f:
        f.write(content)
    
    print("✅ Fixed Enhanced UI display issues:")
    print("  • Prevented duplicate headers")
    print("  • Fixed worker status table formatting")
    print("  • Improved queue status display")
    print("  • Limited message display to prevent overflow")
    
    return True

def create_display_test():
    """Create a test script to verify the fixes"""
    
    test_content = '''#!/usr/bin/env python3
"""Test the fixed Enhanced UI display"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from claude_orchestrator.enhanced_progress_display import EnhancedProgressDisplay, WorkerState

def test_display():
    """Test the enhanced display with realistic data"""
    
    print("Testing Enhanced UI fixes...")
    display = EnhancedProgressDisplay(total_tasks=29)
    
    # Register workers
    for i in range(3):
        display.register_worker(str(i))
    
    # Set some workers to working state
    display.update_worker("0", WorkerState.WORKING, "task_1", "Design Feedback Data Model", (2, 5))
    display.update_worker("1", WorkerState.IDLE)
    display.update_worker("2", WorkerState.IDLE)
    
    # Update counters
    display.completed_tasks = 27
    display.active_tasks = 1
    display.failed_tasks = 0
    
    # Add queue info
    display.update_queue_status(0, 5)
    
    # Add some messages
    display.add_message("Task 9 passed Opus review", "SUCCESS")
    display.add_message("Task 1 passed Opus review", "SUCCESS")
    display.add_message("Task 11 passed Opus review", "SUCCESS")
    
    # Render the display
    display.render()
    
    print("\\n✅ Display test completed")

if __name__ == "__main__":
    test_display()
'''
    
    with open("test_enhanced_ui_fixes.py", "w") as f:
        f.write(test_content)
    
    print("✅ Created test script: test_enhanced_ui_fixes.py")

if __name__ == "__main__":
    if fix_display_issues():
        create_display_test()
        print("\\n🚀 UI fixes applied successfully!")
        print("Test with: python test_enhanced_ui_fixes.py")
    else:
        print("\\n❌ Failed to apply UI fixes")