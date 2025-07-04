#!/usr/bin/env python3
"""Create follow-up tasks for Task 27 - Unit tests for feedback module"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# Read current tasks
tasks_file = Path('.taskmaster/tasks/tasks.json')
with open(tasks_file, 'r') as f:
    data = json.load(f)

# Create follow-up tasks
new_tasks = [
    {
        "id": str(uuid.uuid4()),
        "prompt": "Implement Core Feedback Collection Module - Create claude_orchestrator/feedback_collector.py with FeedbackCollector class implementing: 1) collect_feedback() method to gather task execution feedback, 2) store_feedback() to persist data, 3) get_feedback_summary() for reporting, 4) Integration with TaskMaster for automatic feedback collection",
        "priority": "high",
        "status": "pending",
        "created": datetime.now().isoformat(),
        "worker": None,
        "result": None,
        "error": None,
        "retries": 0,
        "dependencies": ["26"]  # Depends on feedback data models
    },
    {
        "id": str(uuid.uuid4()),
        "prompt": "Re-execute Task 27: Write comprehensive unit tests for feedback module - After feedback_collector.py is implemented, create tests/test_feedback_collector.py with full test coverage including: test collection, storage, retrieval, error handling, validation, and integration tests. Must achieve >90% code coverage.",
        "priority": "high",
        "status": "pending",
        "created": datetime.now().isoformat(),
        "worker": None,
        "result": None,
        "error": None,
        "retries": 0,
        "dependencies": []  # Will add dependency on first task after creation
    }
]

# Add tasks to the list
data['tasks'].extend(new_tasks)

# Update dependency for second task
new_tasks[1]['dependencies'] = [new_tasks[0]['id']]

# Update task 27 status to indicate it needs re-execution
for task in data['tasks']:
    if task['id'] == '27':
        task['error'] = "Task not completed - worker only provided planning output without creating actual test files. Prerequisite feedback module doesn't exist."
        break

# Write updated tasks
with open(tasks_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"Created follow-up tasks:")
print(f"1. Task {new_tasks[0]['id']}: Implement Core Feedback Collection Module (high priority)")
print(f"2. Task {new_tasks[1]['id']}: Re-execute unit tests creation (high priority, depends on feedback module)")
print(f"\nTask 27 has been marked with error status indicating incomplete execution.")