#!/usr/bin/env python3
"""Add follow-up tasks for Task 1: Design Feedback Data Model"""

import json
import os
from datetime import datetime

def add_followup_tasks():
    tasks_file = '.taskmaster/tasks/tasks.json'
    
    # Read existing tasks
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Get next task ID
    numeric_ids = []
    for task in data['tasks']:
        if isinstance(task['id'], int):
            numeric_ids.append(task['id'])
        elif isinstance(task['id'], str) and task['id'].isdigit():
            numeric_ids.append(int(task['id']))
    next_id = max(numeric_ids, default=0) + 1
    
    # Define follow-up tasks
    followup_tasks = [
        {
            "id": str(next_id),
            "prompt": "Create actual feedback data schema with fields for: feedback_id (UUID), user_id, target_id, target_type (enum: product/service/feature), rating (1-5 scale), comment (text), metadata (JSON for custom fields), created_at, updated_at. Define SQL schema, JSON validation schemas, and TypeScript interfaces.",
            "status": "pending",
            "priority": "high",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "parent_task_id": "1",
            "tags": ["data-model", "schema", "feedback"]
        },
        {
            "id": str(next_id + 1),
            "prompt": "Define rating scale configurations: numeric (1-5, 1-10), sentiment (positive/neutral/negative), NPS (0-10), custom scales. Create validation rules and conversion methods between scales.",
            "status": "pending",
            "priority": "high",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "parent_task_id": "1",
            "tags": ["rating-scales", "validation", "feedback"]
        },
        {
            "id": str(next_id + 2),
            "prompt": "Design extensible metadata structure for feedback: predefined fields (device_type, session_id, location), custom fields support, validation rules, indexing strategy for searchability.",
            "status": "pending",
            "priority": "medium",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "parent_task_id": "1",
            "tags": ["metadata", "extensibility", "feedback"]
        }
    ]
    
    # Add tasks to the list
    data['tasks'].extend(followup_tasks)
    
    # Update metadata
    if 'metadata' not in data:
        data['metadata'] = {}
    data['metadata']['last_updated'] = datetime.utcnow().isoformat() + "Z"
    data['metadata']['total_tasks'] = len(data['tasks'])
    
    # Write back to file
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Added {len(followup_tasks)} follow-up tasks for Task 1")
    for task in followup_tasks:
        print(f"  - Task {task['id']}: {task['prompt'][:60]}... [Priority: {task['priority']}]")

if __name__ == "__main__":
    add_followup_tasks()