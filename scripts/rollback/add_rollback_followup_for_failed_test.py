#!/usr/bin/env python3
"""
Add follow-up tasks for the failed RollbackManager test task
"""

import json
import uuid
from datetime import datetime

# Read existing tasks
with open('.taskmaster/tasks/tasks.json', 'r') as f:
    data = json.load(f)
    tasks = data['tasks']

# Generate unique IDs
import uuid
task_ids = [str(uuid.uuid4()) for _ in range(3)]

# Create follow-up tasks
new_tasks = [
    {
        "id": task_ids[0],
        "title": "Implement RollbackManager class in claude_orchestrator/rollback.py",
        "description": "Create the RollbackManager class with core rollback functionality including:\n- Checkpoint restoration methods\n- State management for rollback operations\n- Error recovery mechanisms\n- Integration with CheckpointManager\n- Support for full, partial, and selective rollbacks",
        "status": "pending",
        "priority": "high",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "tags": ["rollback", "implementation", "core-feature", "opus-manager-review"],
        "complexity": "high",
        "dependencies": [],
        "metadata": {
            "created_by": "opus-manager",
            "reason": "RollbackManager class does not exist - needed before tests can be written"
        }
    },
    {
        "id": task_ids[1],
        "title": "Create tests directory and test_rollback.py with comprehensive unit tests",
        "description": "After RollbackManager is implemented:\n- Create tests directory if it doesn't exist\n- Create tests/test_rollback.py with comprehensive unit tests\n- Test all RollbackManager methods\n- Test edge cases and error scenarios\n- Test checkpoint integrity validation\n- Test rollback strategies",
        "status": "pending",
        "priority": "high",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "tags": ["testing", "rollback", "unit-tests", "opus-manager-review"],
        "complexity": "medium",
        "dependencies": [task_ids[0]],
        "metadata": {
            "created_by": "opus-manager",
            "reason": "Original test task failed - no tests were created despite claiming success"
        }
    },
    {
        "id": task_ids[2],
        "title": "Fix worker test execution reporting false positives",
        "description": "Investigate why the worker reported successful test execution when no tests were created. Fix the issue to prevent false positive test results.",
        "status": "pending",
        "priority": "high",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "tags": ["bug-fix", "testing", "worker", "opus-manager-review"],
        "complexity": "medium",
        "dependencies": [],
        "metadata": {
            "created_by": "opus-manager",
            "reason": "Worker reported tests passed when no tests existed"
        }
    }
]

# Add new tasks
tasks.extend(new_tasks)

# Save updated tasks
data['tasks'] = tasks
with open('.taskmaster/tasks/tasks.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Successfully added {len(new_tasks)} follow-up tasks:")
for task in new_tasks:
    print(f"  - Task {task['id']}: {task['title']} (Priority: {task['priority']})")