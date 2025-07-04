#!/usr/bin/env python3
"""Add follow-up tasks for Task 15: Extensibility Framework"""

import json
import os
from datetime import datetime
import uuid

# Load existing tasks
tasks_file = '.taskmaster/tasks/tasks.json'
with open(tasks_file, 'r') as f:
    data = json.load(f)

# Define follow-up tasks - comprehensive implementation plan
follow_up_tasks = [
    {
        "prompt": "Create custom field schema definition system with support for field types (text, number, date, select, etc.), required/optional flags, and metadata storage",
        "priority": "high",
        "dependencies": []
    },
    {
        "prompt": "Implement validation rule engine that supports built-in validators (required, min/max length, regex, custom functions) and can be extended with custom validation logic",
        "priority": "high",
        "dependencies": []
    },
    {
        "prompt": "Build field type registry system to register and manage different field types with their rendering, validation, and serialization logic",
        "priority": "high",
        "dependencies": []
    },
    {
        "prompt": "Create plugin registration and lifecycle management system for extending feedback model with custom behaviors and hooks",
        "priority": "medium",
        "dependencies": []
    },
    {
        "prompt": "Implement configuration management for storing and retrieving custom field definitions and validation rules per feedback type",
        "priority": "medium",
        "dependencies": []
    },
    {
        "prompt": "Create API layer for dynamic field management including CRUD operations for custom fields and validation rules",
        "priority": "medium",
        "dependencies": []
    },
    {
        "prompt": "Build runtime validation execution framework that applies validation rules to feedback data during creation and updates",
        "priority": "high",
        "dependencies": []
    },
    {
        "prompt": "Implement field serialization/deserialization system for storing custom field data in database",
        "priority": "high",
        "dependencies": []
    },
    {
        "prompt": "Create migration system for evolving custom field schemas over time without data loss",
        "priority": "medium",
        "dependencies": []
    },
    {
        "prompt": "Write comprehensive unit tests for extensibility framework covering all components",
        "priority": "high",
        "dependencies": []
    },
    {
        "prompt": "Create developer documentation and examples for extending the feedback model",
        "priority": "medium",
        "dependencies": []
    }
]

# Add follow-up tasks
for i, task_def in enumerate(follow_up_tasks):
    new_task = {
        "id": str(uuid.uuid4()),
        "title": f"Task 15 Follow-up {i+1}: {task_def['prompt'][:60]}...",
        "description": task_def['prompt'],
        "status": "pending",
        "priority": task_def['priority'],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "worker_id": None,
        "result": None,
        "error": None,
        "started_at": None,
        "completed_at": None,
        "dependencies": task_def['dependencies'],
        "tags": ["extensibility", "feedback-model", "task-15-followup"],
        "metadata": {
            "parent_task": 15,
            "created_by": "opus-manager-review"
        }
    }
    data['tasks'].append(new_task)

# Update metadata if it exists
if 'metadata' in data:
    data['metadata']['last_updated'] = datetime.now().isoformat()
    data['metadata']['total_tasks'] = len(data['tasks'])

# Create backup
import shutil
shutil.copy(tasks_file, f"{tasks_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

# Save updated tasks
with open(tasks_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"Successfully added {len(follow_up_tasks)} follow-up tasks for Task 15")
print("\nAdded tasks:")
for i, task_def in enumerate(follow_up_tasks):
    print(f"  - Task {i + 1} ({task_def['priority']}): {task_def['prompt'][:80]}...")