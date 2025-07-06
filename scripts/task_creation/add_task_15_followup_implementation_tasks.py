#!/usr/bin/env python3
"""Add follow-up tasks for Task 15: Storage backend implementation"""

import json
import uuid
from pathlib import Path
from datetime import datetime

def add_task_15_followup_tasks():
    """Add specific implementation tasks for the feedback storage backend"""
    
    # Load existing tasks
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    
    if not tasks_file.exists():
        print(f"❌ Tasks file not found at {tasks_file}")
        return
    
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    existing_tasks = data.get('tasks', [])
    next_id = max([int(t.get('id', 0)) for t in existing_tasks if str(t.get('id', '')).isdigit()], default=0) + 1
    
    tasks_to_add = [
        {
            "prompt": "Implement feedback data models and schemas. Create Python dataclasses or Pydantic models for Feedback, FeedbackMetadata, and FeedbackQuery. Include validation, serialization methods, and type hints. Place in claude_orchestrator/feedback/models.py",
            "priority": "high",
            "tags": ["storage", "backend", "models", "feedback", "followup", "opus-manager-review"]
        },
        {
            "prompt": "Implement JSON file-based storage backend for feedback data. Create JSONFeedbackStorage class with CRUD operations (create, read, update, delete) and query methods. Include file locking for concurrent access safety. Place in claude_orchestrator/feedback/storage/json_storage.py",
            "priority": "high",
            "tags": ["storage", "backend", "json", "feedback", "followup", "opus-manager-review"]
        },
        {
            "prompt": "Create abstract base class for feedback storage backends. Define interface with abstract methods for CRUD operations and querying. This will allow easy swapping between JSON and future database implementations. Place in claude_orchestrator/feedback/storage/base.py",
            "priority": "high",
            "tags": ["storage", "backend", "interface", "feedback", "followup", "opus-manager-review"]
        },
        {
            "prompt": "Implement feedback query functionality. Create methods to query feedback by task_id, worker_id, timestamp range, rating, and custom criteria. Support sorting and pagination. Place query logic in claude_orchestrator/feedback/query.py",
            "priority": "medium",
            "tags": ["storage", "query", "feedback", "followup", "opus-manager-review"]
        },
        {
            "prompt": "Add comprehensive error handling to feedback storage. Create custom exceptions for storage errors, implement retry logic for file operations, and add proper logging. Place exceptions in claude_orchestrator/feedback/exceptions.py",
            "priority": "medium",
            "tags": ["storage", "error-handling", "feedback", "followup", "opus-manager-review"]
        },
        {
            "prompt": "Create unit tests for feedback storage backend. Test CRUD operations, concurrent access, query functionality, and error handling. Include fixtures for test data. Place in tests/test_feedback_storage.py",
            "priority": "high",
            "tags": ["storage", "testing", "feedback", "followup", "opus-manager-review"]
        },
        {
            "prompt": "Implement storage configuration system. Create configuration for storage paths, file formats, retention policies, and future database connection settings. Use environment variables and config files. Place in claude_orchestrator/feedback/config.py",
            "priority": "medium",
            "tags": ["storage", "configuration", "feedback", "followup", "opus-manager-review"]
        },
        {
            "prompt": "Create database storage backend stub. Implement SQLAlchemy models and basic structure for future database integration. This should follow the same interface as JSON storage. Place in claude_orchestrator/feedback/storage/db_storage.py",
            "priority": "low",
            "tags": ["storage", "database", "future", "feedback", "followup", "opus-manager-review"]
        }
    ]
    
    # Create new tasks
    created_tasks = []
    now = datetime.now().isoformat()
    
    for i, task_data in enumerate(tasks_to_add):
        task = {
            "id": str(next_id + i),
            "title": task_data["prompt"].split(".")[0][:80] + "...",
            "description": task_data["prompt"],
            "priority": task_data["priority"],
            "status": "pending",
            "tags": task_data["tags"],
            "createdAt": now,
            "updatedAt": now,
            "subtasks": [],
            "metadata": {
                "created_by": "opus-manager-review",
                "parent_task": 15
            }
        }
        created_tasks.append(task)
        print(f"Created task {task['id']}: {task['title']}")
    
    # Add new tasks to existing tasks
    existing_tasks.extend(created_tasks)
    
    # Save updated tasks
    data['tasks'] = existing_tasks
    
    # Write back to file
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nSuccessfully created {len(created_tasks)} follow-up tasks for Task 15 implementation")
    
    # Save task IDs for reference
    output_file = Path("scripts/task_management/task_15_followup_ids.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump({
            "parent_task": 15,
            "followup_task_ids": [t['id'] for t in created_tasks],
            "created_at": now
        }, f, indent=2)
    
    print(f"\nTask IDs saved to {output_file}")

if __name__ == "__main__":
    add_task_15_followup_tasks()