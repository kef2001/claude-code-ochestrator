#!/usr/bin/env python3

import json
import uuid
from datetime import datetime, timezone

# Load existing tasks
with open('.taskmaster/tasks/tasks.json', 'r') as f:
    tasks_data = json.load(f)

# Get next task ID (handling both int and UUID formats)
numeric_ids = []
for task in tasks_data["tasks"]:
    if isinstance(task["id"], int):
        numeric_ids.append(task["id"])
    elif isinstance(task["id"], str) and task["id"].isdigit():
        numeric_ids.append(int(task["id"]))
        
next_id = max(numeric_ids) + 1 if numeric_ids else 1

# Create new task
new_task = {
    "id": next_id,
    "title": "Setup TypeScript environment and create feedback interfaces",
    "description": "Since this is a Python project, either: 1) Create a separate TypeScript definitions package for feedback interfaces, OR 2) Document the intended TypeScript interfaces as Python type hints using typing module. Include FeedbackEntry, FeedbackType, FeedbackMetadata, RatingScale, and ValidationResult interfaces with full documentation.",
    "status": "pending",
    "dependencies": [],
    "priority": "high",
    "details": "Task 16 was marked complete without implementation. This follow-up ensures actual interface definitions are created, either as TypeScript files or as Python type hints that could be converted to TypeScript. Consider the project's Python nature when implementing.",
    "testStrategy": "Validate type definitions work correctly with either TypeScript compiler or Python type checkers (mypy)",
    "subtasks": [],
    "createdAt": datetime.now(timezone.utc).isoformat(),
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "tags": ["typescript", "interfaces", "feedback", "task-16-followup"]
}

# Add task to list
tasks_data["tasks"].append(new_task)

# Update metadata
tasks_data["meta"]["updatedAt"] = datetime.now(timezone.utc).isoformat()
tasks_data["meta"]["totalTasks"] = len(tasks_data["tasks"])
tasks_data["meta"]["pendingTasks"] = sum(1 for task in tasks_data["tasks"] if task.get("status") == "pending")

# Save updated tasks
with open('.taskmaster/tasks/tasks.json', 'w') as f:
    json.dump(tasks_data, f, indent=2)

print(f"Created follow-up task ID {new_task['id']} for Task 16")
print(f"Title: {new_task['title']}")
print(f"Priority: {new_task['priority']}")
print(f"Description: {new_task['description']}")