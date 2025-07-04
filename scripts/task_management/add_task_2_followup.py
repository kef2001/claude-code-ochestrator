#!/usr/bin/env python3
"""Add follow-up tasks for Task 2: Implement Feedback Storage Layer"""

import json
import os
from datetime import datetime

def add_task(tasks, prompt, priority="medium"):
    """Add a new task to the tasks list"""
    # Convert IDs to int for comparison, handle both int and string IDs
    task_ids = []
    for task in tasks:
        try:
            task_ids.append(int(task["id"]))
        except (ValueError, TypeError):
            continue
    max_id = max(task_ids, default=0)
    new_task = {
        "id": max_id + 1,
        "prompt": prompt,
        "priority": priority,
        "status": "ready",
        "is_followup": True,
        "parent_task_id": 2,
        "created_at": datetime.now().isoformat(),
        "dependencies": []
    }
    tasks.append(new_task)
    return new_task

def main():
    # Load existing tasks
    tasks_file = ".taskmaster/tasks/tasks.json"
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    tasks = data["tasks"]
    
    # Add follow-up tasks for Task 2
    followup_tasks = [
        {
            "prompt": "Implement actual feedback storage models and database schema for feedback persistence layer including tables for feedback entries, metadata, and relationships",
            "priority": "high"
        },
        {
            "prompt": "Create CRUD operations for feedback storage layer with proper error handling and validation",
            "priority": "high"
        },
        {
            "prompt": "Write comprehensive unit tests for feedback storage layer covering all CRUD operations and edge cases",
            "priority": "high"
        },
        {
            "prompt": "Add feedback storage configuration and migration scripts for database setup",
            "priority": "medium"
        }
    ]
    
    # Add each follow-up task
    for task_data in followup_tasks:
        task = add_task(tasks, task_data["prompt"], task_data["priority"])
        print(f"Added task {task['id']}: {task['prompt'][:60]}...")
    
    # Save updated tasks
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nSuccessfully added {len(followup_tasks)} follow-up tasks for Task 2")

if __name__ == "__main__":
    main()