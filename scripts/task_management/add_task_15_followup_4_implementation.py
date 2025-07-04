#!/usr/bin/env python3
"""Add follow-up tasks for Task 15 Follow-up 4 actual implementation"""

import json
import uuid
from datetime import datetime, timezone
import os

tasks_file = ".taskmaster/tasks/tasks.json"

# Create backup
backup_name = f"{tasks_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
with open(tasks_file, 'r') as f:
    original_data = f.read()
with open(backup_name, 'w') as f:
    f.write(original_data)

# Load tasks
with open(tasks_file, 'r') as f:
    data = json.load(f)

# Add follow-up tasks
new_tasks = [
    {
        "task_prompt": "Actually implement the plugin interface for extending feedback model. Create base plugin class with abstract methods, plugin loader with dynamic import capabilities, and plugin registry for managing loaded plugins. Include proper error handling and type hints.",
        "priority": "high",
        "metadata": {}
    },
    {
        "task_prompt": "Implement lifecycle hooks for feedback plugins: pre-save, post-save, pre-validate, and post-validate. Create hook decorators and ensure hooks can modify feedback data or abort operations.",
        "priority": "high",
        "metadata": {}
    },
    {
        "task_prompt": "Create custom field processors for feedback plugins. Allow plugins to register custom processors for specific field types, handle field validation, and transform field values.",
        "priority": "medium",
        "metadata": {}
    },
    {
        "task_prompt": "Write comprehensive tests for the plugin system including plugin loading, lifecycle hooks, field processors, error handling, and plugin isolation.",
        "priority": "medium",
        "metadata": {}
    },
    {
        "task_prompt": "Create example plugins demonstrating the plugin interface: sentiment analysis plugin, auto-tagging plugin, and notification plugin. Include documentation and setup instructions.",
        "priority": "low",
        "metadata": {}
    }
]

# Get next task ID
next_id = max([t["id"] for t in data["tasks"] if isinstance(t["id"], int)], default=0) + 1

# Add tasks to the data
for i, task_config in enumerate(new_tasks):
    task = {
        "id": next_id + i,
        "title": task_config["task_prompt"][:80] + "..." if len(task_config["task_prompt"]) > 80 else task_config["task_prompt"],
        "description": task_config["task_prompt"],
        "status": "pending",
        "dependencies": [],
        "priority": task_config["priority"],
        "details": "",
        "testStrategy": "",
        "subtasks": [],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "tags": ["plugin-system", "feedback-model", "implementation"]
    }
    data["tasks"].append(task)
    print(f"Added task {next_id + i}: {task['title'][:80]}...")

# Update meta
data["meta"]["total_tasks"] = len(data["tasks"])
data["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()

# Write back
with open(tasks_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"\nSuccessfully added {len(new_tasks)} follow-up tasks for Task 15 Follow-up 4")
print(f"Backup created at: {backup_name}")