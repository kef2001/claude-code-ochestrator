#!/usr/bin/env python3
"""Script to add rollback test implementation task to the task queue."""

import json
import uuid
from datetime import datetime

# Define the task
task = {
    "id": str(uuid.uuid4()),
    "type": "coding",
    "description": "Actually implement comprehensive rollback tests for the orchestrator rollback mechanism. Create test files that verify: 1) Rollback state transitions, 2) File restoration after rollback, 3) Task state recovery, 4) Error handling during rollback, 5) Edge cases like partial failures. Use pytest framework.",
    "status": "pending",
    "priority": "high",
    "tags": ["testing", "rollback", "follow-up", "opus-manager-review"],
    "created_at": datetime.now().isoformat(),
    "dependencies": [],
    "complexity": 4,
    "estimated_hours": 3,
    "subtasks": [
        {
            "id": f"{uuid.uuid4()}_subtask_1",
            "description": "Create test_rollback_state_transitions.py to verify state changes",
            "status": "pending"
        },
        {
            "id": f"{uuid.uuid4()}_subtask_2",
            "description": "Create test_rollback_file_operations.py to verify file restoration",
            "status": "pending"
        },
        {
            "id": f"{uuid.uuid4()}_subtask_3",
            "description": "Create test_rollback_task_recovery.py to verify task state recovery",
            "status": "pending"
        },
        {
            "id": f"{uuid.uuid4()}_subtask_4",
            "description": "Create test_rollback_error_handling.py for error scenarios",
            "status": "pending"
        },
        {
            "id": f"{uuid.uuid4()}_subtask_5",
            "description": "Create test_rollback_edge_cases.py for partial failures and edge cases",
            "status": "pending"
        }
    ]
}

# Load existing tasks
try:
    with open('.taskmaster/tasks/tasks.json', 'r') as f:
        tasks_data = json.load(f)
except FileNotFoundError:
    tasks_data = {"tasks": []}

# Add the new task
tasks_data["tasks"].append(task)

# Save updated tasks
with open('.taskmaster/tasks/tasks.json', 'w') as f:
    json.dump(tasks_data, f, indent=2)

print(f"✅ Added rollback test implementation task with ID: {task['id']}")
print(f"   Priority: {task['priority']}")
print(f"   Complexity: {task['complexity']}")
print(f"   Estimated hours: {task['estimated_hours']}")
print(f"   Tags: {', '.join(task['tags'])}")
print(f"   Subtasks: {len(task['subtasks'])}")