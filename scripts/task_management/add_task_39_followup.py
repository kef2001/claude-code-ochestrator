#!/usr/bin/env python3
import json
import os
from datetime import datetime

def add_task(task_data):
    tasks_file = ".taskmaster/tasks/tasks.json"
    
    # Read existing tasks
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Generate UUID for task ID
    import uuid
    next_id = str(uuid.uuid4())
    
    # Create new task
    new_task = {
        "id": str(next_id),
        "prompt": task_data["prompt"],
        "status": "pending",
        "priority": task_data["priority"],
        "created_at": datetime.now().isoformat(),
        "dependencies": [],
        "metadata": {}
    }
    
    # Add task
    data['tasks'].append(new_task)
    
    # Write back
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Added task {next_id}: {task_data['prompt'][:50]}...")

# Add the follow-up task
add_task({
    "prompt": "Implement rollback configuration in orchestrator_config.json. Add a new 'rollback' section with settings for: enabled (bool), max_snapshots (int), snapshot_interval (seconds), rollback_on_failure (bool), and snapshot_directory (path). Also add corresponding code in task_master.py to read and use these settings.",
    "priority": "high"
})