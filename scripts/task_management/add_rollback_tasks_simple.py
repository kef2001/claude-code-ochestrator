#!/usr/bin/env python3
"""Add follow-up tasks for rollback implementation"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claude_orchestrator.task_master import TaskManager

def main():
    task_manager = TaskManager()
    
    # Add the implementation task
    task = task_manager.add_task(
        title="Implement rollback hooks in OpusManager",
        description="Implement rollback hooks in OpusManager to handle task failures. Include: 1) Hook registration, 2) Auto rollback on failure, 3) Manual rollback, 4) State snapshots, 5) Error handling integration",
        priority="high"
    )
    
    print(f"✅ Created task {task.id}: {task.title}")

if __name__ == "__main__":
    main()