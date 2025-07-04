#!/usr/bin/env python3
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
    
    print("\n✅ Display test completed")

if __name__ == "__main__":
    test_display()
