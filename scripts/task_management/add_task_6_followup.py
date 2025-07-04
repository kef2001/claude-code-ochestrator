#!/usr/bin/env python3
"""Script to add follow-up task for Task 6: Task Completion Integration"""

import json
import os
from datetime import datetime
import uuid

# Task to add
new_task = {
    "id": str(uuid.uuid4()),
    "title": "Implement Feedback Collection in Task Completion",
    "description": "Add feedback collection mechanism to task completion workflow",
    "details": """Implement feedback collection mechanism in task completion workflow:

1. Add feedback collection to complete_task method in worker_pool_manager.py:
   - Add optional feedback parameter to complete_task method
   - Store feedback with task completion metrics
   - Track feedback for performance analysis

2. Add feedback collection to inline_executor.py:
   - Capture execution feedback after task completion
   - Include feedback in task result data structure
   - Support both automated and manual feedback

3. Create feedback storage structure:
   - Design feedback data model
   - Add feedback fields to task completion records
   - Support different feedback types (rating, text, metrics)

4. Integrate with evaluator_optimizer.py:
   - Use collected feedback in evaluation process
   - Feed feedback into optimization decisions
   - Track feedback trends over time

This will enable continuous improvement through systematic feedback collection.""",
    "status": "pending",
    "priority": "high",
    "created_at": datetime.now().isoformat(),
    "tags": ["feedback", "task-completion", "monitoring"],
    "dependencies": [],
    "complexity": 3,
    "assigned_to": None,
    "due_date": None,
    "subtasks": []
}

# Load existing tasks
tasks_file = ".taskmaster/tasks/tasks.json"
if os.path.exists(tasks_file):
    with open(tasks_file, 'r') as f:
        data = json.load(f)
        tasks = data.get('tasks', [])
else:
    tasks = []

# Add new task
tasks.append(new_task)

# Save updated tasks
os.makedirs(os.path.dirname(tasks_file), exist_ok=True)
with open(tasks_file, 'w') as f:
    json.dump({"tasks": tasks}, f, indent=2)

print(f"✅ Added follow-up task: {new_task['title']}")
print(f"   ID: {new_task['id']}")
print(f"   Priority: {new_task['priority']}")