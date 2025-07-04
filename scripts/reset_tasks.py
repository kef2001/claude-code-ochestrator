#!/usr/bin/env python3
"""
Reset all tasks to pending status for comprehensive review
"""

import json
import sys
from pathlib import Path

def reset_all_tasks():
    """Reset all tasks to pending status"""
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    
    if not tasks_file.exists():
        print("❌ tasks.json not found")
        sys.exit(1)
    
    # Read current tasks
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Reset all tasks to pending
    tasks_reset = 0
    for task in data['tasks']:
        if task['status'] != 'pending':
            task['status'] = 'pending'
            tasks_reset += 1
    
    # Update meta info
    data['meta']['pendingTasks'] = len(data['tasks'])
    data['meta']['completedTasks'] = 0
    data['meta']['updatedAt'] = "2025-07-04T17:25:00.000000"
    
    # Write back
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Reset {tasks_reset} tasks to pending status")
    print(f"📊 Total tasks: {len(data['tasks'])}")

if __name__ == "__main__":
    reset_all_tasks()