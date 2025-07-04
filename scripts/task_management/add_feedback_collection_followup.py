#!/usr/bin/env python3
"""Add follow-up tasks for Feedback Collection Implementation"""

import json
import os
from datetime import datetime
import uuid

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
            "prompt": "Implement feedback collection database schema with tables for feedback entries, rating configurations, and metadata storage. Include proper indexes and constraints.",
            "status": "pending",
            "priority": "high",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "parent_task_id": "0c77f3d2-c5a8-4c88-88e6-3b8f95c571d8",
            "tags": ["feedback", "database", "implementation"]
        },
        {
            "id": str(next_id + 1),
            "prompt": "Create REST API endpoints for feedback collection: POST /feedback, GET /feedback/{id}, GET /feedback/list with filtering, PATCH /feedback/{id} for updates",
            "status": "pending",
            "priority": "high",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "parent_task_id": "0c77f3d2-c5a8-4c88-88e6-3b8f95c571d8",
            "tags": ["feedback", "api", "implementation"]
        },
        {
            "id": str(next_id + 2),
            "prompt": "Build feedback UI components: FeedbackForm component with rating selector, comment textarea, metadata fields; FeedbackList component with sorting/filtering; FeedbackSummary dashboard widget",
            "status": "pending",
            "priority": "high",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "parent_task_id": "0c77f3d2-c5a8-4c88-88e6-3b8f95c571d8",
            "tags": ["feedback", "ui", "components"]
        },
        {
            "id": str(next_id + 3),
            "prompt": "Integrate feedback collection into task completion workflow: add feedback prompt after task completion, store feedback with task association, update task statistics based on feedback",
            "status": "pending",
            "priority": "high",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "parent_task_id": "0c77f3d2-c5a8-4c88-88e6-3b8f95c571d8",
            "tags": ["feedback", "integration", "workflow"]
        },
        {
            "id": str(next_id + 4),
            "prompt": "Write comprehensive unit tests for feedback collection: test database operations, API endpoint validation, UI component behavior, workflow integration",
            "status": "pending",
            "priority": "medium",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "parent_task_id": "0c77f3d2-c5a8-4c88-88e6-3b8f95c571d8",
            "tags": ["feedback", "testing", "quality"]
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
    
    print(f"Added {len(followup_tasks)} follow-up tasks for Feedback Collection Implementation")
    for task in followup_tasks:
        print(f"  - Task {task['id']}: {task['prompt'][:60]}... [Priority: {task['priority']}]")

if __name__ == "__main__":
    add_followup_tasks()