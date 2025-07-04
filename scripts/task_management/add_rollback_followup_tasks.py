#!/usr/bin/env python3
"""Add follow-up tasks for incomplete Task 9 implementation."""

import json
import uuid
from datetime import datetime
from pathlib import Path

# Load existing tasks
tasks_file = Path(".taskmaster/tasks/tasks.json")
with open(tasks_file, "r") as f:
    data = json.load(f)

# Define new follow-up tasks
new_tasks = [
    {
        "id": str(uuid.uuid4()),
        "prompt": "Create rollback.py module with RollbackManager class implementation including checkpoint creation, state restoration, and rollback operations",
        "status": "pending",
        "priority": "high",
        "parent_id": "9",
        "created_at": datetime.now().isoformat(),
        "tags": ["implementation", "rollback", "core-feature"]
    },
    {
        "id": str(uuid.uuid4()),
        "prompt": "Implement unit tests for RollbackManager class covering checkpoint creation, restoration, error handling, and edge cases",
        "status": "pending",
        "priority": "high",
        "parent_id": "9",
        "created_at": datetime.now().isoformat(),
        "tags": ["testing", "rollback"]
    },
    {
        "id": str(uuid.uuid4()),
        "prompt": "Add comprehensive error handling to RollbackManager for invalid checkpoints, missing data, and rollback failures",
        "status": "pending",
        "priority": "medium",
        "parent_id": "9",
        "created_at": datetime.now().isoformat(),
        "tags": ["error-handling", "rollback"]
    },
    {
        "id": str(uuid.uuid4()),
        "prompt": "Create documentation for RollbackManager API including usage examples and integration guide",
        "status": "pending",
        "priority": "medium",
        "parent_id": "9",
        "created_at": datetime.now().isoformat(),
        "tags": ["documentation", "rollback"]
    }
]

# Add new tasks
data["tasks"].extend(new_tasks)

# Update metadata
data["metadata"]["total_tasks"] = len(data["tasks"])
data["metadata"]["last_updated"] = datetime.now().isoformat()

# Write updated tasks
with open(tasks_file, "w") as f:
    json.dump(data, f, indent=2)

print(f"Successfully added {len(new_tasks)} follow-up tasks for Task 9 implementation")
for task in new_tasks:
    print(f"  - [{task['priority']}] {task['prompt']}")