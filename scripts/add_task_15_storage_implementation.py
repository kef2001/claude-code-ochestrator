#!/usr/bin/env python3
"""Create implementation tasks for Task 15: Feedback Storage Backend"""

import json
from datetime import datetime
from pathlib import Path

def add_storage_implementation_tasks():
    """Add implementation tasks for the feedback storage backend"""
    
    # Load existing tasks
    tasks_file = Path('.taskmaster/tasks/tasks.json')
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Find the highest numeric ID
    max_id = 0
    for task in data['tasks']:
        if isinstance(task.get('id'), int):
            max_id = max(max_id, task['id'])
    
    # Tasks to add
    new_tasks = [
        {
            "title": "Implement FeedbackModel with validation",
            "description": "Create feedback_model.py with FeedbackModel dataclass including validation, serialization, and type hints",
            "priority": "high",
            "tags": ["feedback-storage", "implementation", "opus-manager-review"]
        },
        {
            "title": "Create FeedbackStorageInterface",
            "description": "Create abstract interface for feedback storage with CRUD operations and query methods",
            "priority": "high",
            "tags": ["feedback-storage", "interface", "opus-manager-review"]
        },
        {
            "title": "Implement JSON file storage backend",
            "description": "Create JSON-based storage backend with file locking, indexing, and atomic operations",
            "priority": "high",
            "tags": ["feedback-storage", "json-backend", "opus-manager-review"]
        },
        {
            "title": "Implement SQLite storage backend",
            "description": "Create SQLite storage backend with proper schema, migrations, and connection pooling",
            "priority": "high",
            "tags": ["feedback-storage", "sqlite-backend", "opus-manager-review"]
        },
        {
            "title": "Create storage factory and configuration",
            "description": "Implement factory pattern for storage backend selection and configuration management",
            "priority": "medium",
            "tags": ["feedback-storage", "configuration", "opus-manager-review"]
        },
        {
            "title": "Write comprehensive storage tests",
            "description": "Create unit and integration tests for all storage components",
            "priority": "high",
            "tags": ["feedback-storage", "testing", "opus-manager-review"]
        }
    ]
    
    # Add tasks
    added_count = 0
    for i, task_def in enumerate(new_tasks):
        new_id = max_id + i + 1
        new_task = {
            "id": new_id,
            "title": task_def["title"],
            "description": task_def["description"],
            "status": "pending",
            "dependencies": [],
            "priority": task_def["priority"],
            "details": f"Implementation task for feedback storage backend (Task 15 follow-up)",
            "testStrategy": "Unit tests and integration tests",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": task_def["tags"]
        }
        data['tasks'].append(new_task)
        added_count += 1
        print(f"✅ Added task {new_id}: {task_def['title']}")
    
    # Update metadata
    data['meta']['totalTasks'] = len(data['tasks'])
    data['meta']['pendingTasks'] = sum(1 for t in data['tasks'] if t.get('status') == 'pending')
    data['meta']['completedTasks'] = sum(1 for t in data['tasks'] if t.get('status') in ['done', 'completed'])
    data['meta']['updatedAt'] = datetime.now().isoformat()
    
    # Save updated tasks
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n📋 Successfully added {added_count} implementation tasks for feedback storage backend")

if __name__ == "__main__":
    add_storage_implementation_tasks()