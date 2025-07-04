#!/usr/bin/env python3
"""
Add follow-up tasks for the Rollback Mechanism implementation
"""

import json
import os
from pathlib import Path
from datetime import datetime

# Define follow-up tasks
tasks = [
    {
        "title": "Implement RollbackManager class",
        "description": "Create rollback.py module with RollbackManager class that can restore system state from checkpoints",
        "priority": "high",
        "details": "Implement core rollback functionality:\n- Create RollbackManager class in claude_orchestrator/rollback.py\n- Integrate with CheckpointManager to restore state\n- Handle rollback triggers (errors, manual requests)\n- Implement rollback validation\n- Add logging and monitoring"
    },
    {
        "title": "Define rollback strategies",
        "description": "Design and implement different rollback strategies (full, partial, selective)",
        "priority": "high",
        "details": "Define rollback strategies:\n- Full rollback: restore entire system state\n- Partial rollback: restore specific components\n- Selective rollback: restore specific tasks/operations\n- Implement strategy selection logic"
    },
    {
        "title": "Integrate rollback with orchestrator",
        "description": "Add rollback hooks and error recovery to EnhancedOrchestrator",
        "priority": "medium",
        "details": "Integration points:\n- Add rollback triggers in error handlers\n- Implement automatic rollback on critical failures\n- Add manual rollback commands\n- Update orchestrator state management"
    },
    {
        "title": "Create rollback tests",
        "description": "Write comprehensive tests for rollback mechanism",
        "priority": "medium",
        "details": "Test coverage:\n- Unit tests for RollbackManager\n- Integration tests with CheckpointManager\n- End-to-end rollback scenarios\n- Error recovery tests\n- Performance tests for large state rollbacks"
    }
]

# Create .taskmaster directory if it doesn't exist
taskmaster_dir = Path(".taskmaster")
taskmaster_dir.mkdir(exist_ok=True)

# Load existing tasks file
tasks_file = taskmaster_dir / "tasks" / "tasks.json"
existing_tasks = {"tasks": []}
if tasks_file.exists():
    with open(tasks_file, 'r') as f:
        existing_tasks = json.load(f)

# Find next task ID
next_id = max([t.get('id', 0) for t in existing_tasks['tasks']], default=0) + 1

# Add new tasks
for i, task in enumerate(tasks):
    new_task = {
        "id": next_id + i,
        "title": task["title"],
        "description": task["description"],
        "status": "pending",
        "dependencies": [],
        "priority": task["priority"],
        "details": task["details"],
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat()
    }
    existing_tasks['tasks'].append(new_task)
    
    # Create individual task file
    task_file = taskmaster_dir / f"task_{next_id + i}.json"
    with open(task_file, 'w') as f:
        json.dump(new_task, f, indent=2)
    
    print(f"Created task {next_id + i}: {task['title']}")

# Save updated tasks file
with open(tasks_file, 'w') as f:
    json.dump(existing_tasks, f, indent=2)

print(f"\nSuccessfully created {len(tasks)} follow-up tasks for the Rollback Mechanism.")