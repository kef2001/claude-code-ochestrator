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
    "title": "Implement TypeScript Interfaces for Feedback",
    "description": "Actually implement TypeScript interfaces for feedback data structures including: User feedback interface, System feedback interface, Error feedback interface, Performance metrics interface, and Response data interface. Create a types/feedback.ts file with proper TypeScript definitions.",
    "status": "pending",
    "dependencies": [],
    "priority": "high",
    "details": "Create comprehensive TypeScript interfaces for all feedback-related data structures. Include proper type definitions, optional fields, and documentation.",
    "testStrategy": "Type checking with TypeScript compiler, unit tests for type guards",
    "subtasks": [],
    "createdAt": datetime.now(timezone.utc).isoformat(),
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "tags": ["typescript", "interfaces", "feedback"]
}

# Add task to list
tasks_data["tasks"].append(new_task)

# Update metadata
tasks_data["meta"]["updatedAt"] = datetime.now(timezone.utc).isoformat()
tasks_data["meta"]["totalTasks"] = len(tasks_data["tasks"])

# Save updated tasks
with open('.taskmaster/tasks/tasks.json', 'w') as f:
    json.dump(tasks_data, f, indent=2)

print(f"Created follow-up task ID {new_task['id']} for Task 16")
print(f"Title: {new_task['title']}")
print(f"Priority: {new_task['priority']}")