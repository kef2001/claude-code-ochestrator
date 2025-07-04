#!/usr/bin/env python3
import json
import os
from datetime import datetime
import uuid

def add_task():
    tasks_file = ".taskmaster/tasks/tasks.json"
    
    # Load existing tasks
    with open(tasks_file, 'r') as f:
        tasks_data = json.load(f)
    
    # Create new task
    new_task = {
        "id": str(uuid.uuid4()),
        "title": "Implement extensible validation framework with rule registry",
        "description": "Create validation module with BaseValidator class, built-in validators (RequiredValidator, MinLengthValidator, MaxLengthValidator, PatternValidator, RangeValidator), ValidationRegistry for rule management, and ValidationError class for error messaging. Include comprehensive unit tests.",
        "status": "pending",
        "priority": "high",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "worker_output": None,
        "error_output": None,
        "retries": 0
    }
    
    # Add to tasks list
    tasks_data["tasks"].append(new_task)
    
    # Backup current file
    backup_file = f"{tasks_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.rename(tasks_file, backup_file)
    
    # Write updated tasks
    with open(tasks_file, 'w') as f:
        json.dump(tasks_data, f, indent=2)
    
    print(f"✓ Added task: {new_task['title']}")
    print(f"  ID: {new_task['id']}")
    print(f"  Priority: {new_task['priority']}")

if __name__ == "__main__":
    add_task()