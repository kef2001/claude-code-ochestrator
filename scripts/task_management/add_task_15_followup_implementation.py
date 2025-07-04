#!/usr/bin/env python3
"""Add follow-up tasks for Task 15 Follow-up 1 implementation"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# Define follow-up tasks for the incomplete implementation
tasks = [
    {
        "id": str(uuid.uuid4()),
        "title": "Implement base feedback model class with dynamic fields",
        "description": "Actually implement the base feedback model class with dynamic custom fields support. Create a Python class that includes: 1) Standard fields (rating, comment, timestamp), 2) Dynamic custom fields support with field metadata (type, required, default values), 3) Validation methods, 4) Serialization/deserialization methods. The class should be in claude_orchestrator/feedback_model.py",
        "priority": "high",
        "tags": ["implementation", "feedback-system", "core"],
        "estimated_minutes": 60,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "context": "The original task was not implemented - only analyzed. This task requires actual code implementation."
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Create unit tests for feedback model class",
        "description": "Write comprehensive unit tests for the feedback model class including: 1) Standard field validation tests, 2) Custom field addition/removal tests, 3) Field metadata validation tests, 4) Serialization/deserialization tests, 5) Edge case handling. Tests should be in tests/test_feedback_model.py",
        "priority": "high",
        "tags": ["testing", "feedback-system"],
        "estimated_minutes": 45,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "dependencies": ["Implement base feedback model class with dynamic fields"]
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Add field type validators for custom fields",
        "description": "Implement validators for different field types (string, number, boolean, date, email, url, etc.) that can be used with custom fields. Include validation rules, error messages, and type conversion utilities.",
        "priority": "medium",
        "tags": ["validation", "feedback-system"],
        "estimated_minutes": 30,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "dependencies": ["Implement base feedback model class with dynamic fields"]
    }
]

# Load existing tasks
tasks_file = Path(".taskmaster/tasks/tasks.json")
if tasks_file.exists():
    with open(tasks_file, 'r') as f:
        existing_data = json.load(f)
else:
    existing_data = {
        "tasks": [],
        "meta": {
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
    }

# Add new tasks
existing_data["tasks"].extend(tasks)
existing_data["meta"]["last_updated"] = datetime.now().isoformat()

# Save updated tasks
tasks_file.parent.mkdir(parents=True, exist_ok=True)
with open(tasks_file, 'w') as f:
    json.dump(existing_data, f, indent=2)

print(f"Successfully added {len(tasks)} follow-up tasks for Task 15 Follow-up 1")
for task in tasks:
    print(f"- {task['title']} (Priority: {task['priority']})")