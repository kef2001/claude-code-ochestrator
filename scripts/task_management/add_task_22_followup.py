#!/usr/bin/env python3
"""Create follow-up tasks for Task 22: RollbackManager integration points"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# Load existing tasks
tasks_file = Path(".taskmaster/tasks/tasks.json")
with open(tasks_file, 'r') as f:
    data = json.load(f)

# Define follow-up tasks
followup_tasks = [
    {
        "prompt": "Implement RollbackManager class with state snapshot capabilities, rollback strategies (full/partial/selective), and integration with CheckpointManager in claude_orchestrator/rollback/rollback_manager.py",
        "priority": "high",
        "depends_on": []
    },
    {
        "prompt": "Add rollback integration hooks in EnhancedOrchestrator: pre-execution snapshots at line 371, failure rollback triggers at line 236, and retry rollback support at line 508",
        "priority": "high",
        "depends_on": []
    },
    {
        "prompt": "Create StateSnapshot and RecoveryPointManager classes for capturing and managing system state during task execution",
        "priority": "medium",
        "depends_on": []
    },
    {
        "prompt": "Implement RollbackTrigger system for automatic rollback based on error types and add rollback-aware error handling in ClaudeErrorHandler",
        "priority": "medium",
        "depends_on": []
    },
    {
        "prompt": "Create comprehensive unit tests for RollbackManager, including state capture, rollback execution, and recovery scenarios",
        "priority": "medium",
        "depends_on": []
    },
    {
        "prompt": "Add CLI commands for manual rollback operations and document RollbackManager usage and integration points",
        "priority": "low",
        "depends_on": []
    }
]

# Add tasks - handle both string and int IDs
task_ids = [int(task['id']) if isinstance(task['id'], str) and task['id'].isdigit() else task['id'] 
            for task in data['tasks'] if isinstance(task['id'], (str, int))]
numeric_ids = [id for id in task_ids if isinstance(id, int)]
next_id = max(numeric_ids) + 1 if numeric_ids else 1

for task_def in followup_tasks:
    new_task = {
        "id": next_id,
        "prompt": task_def["prompt"],
        "priority": task_def["priority"],
        "depends_on": task_def["depends_on"],
        "created_at": datetime.now().isoformat(),
        "status": "pending",
        "worker_id": None,
        "result": None,
        "completed_at": None,
        "execution_time": None
    }
    data['tasks'].append(new_task)
    print(f"Added Task {next_id}: {task_def['prompt'][:80]}...")
    next_id += 1

# Update meta
data['meta']['last_updated'] = datetime.now().isoformat()
data['meta']['total_tasks'] = len(data['tasks'])

# Save updated tasks
with open(tasks_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"\nSuccessfully added {len(followup_tasks)} follow-up tasks for Task 22")