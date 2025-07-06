#!/usr/bin/env python3
"""Add follow-up tasks for complete RollbackManager implementation"""

import json
from uuid import uuid4
from datetime import datetime

def create_task(title, description, priority="high", tags=None):
    """Create a task dictionary"""
    return {
        "id": str(uuid4()),
        "title": title,
        "type": "implementation",
        "description": description,
        "status": "pending",
        "priority": priority,
        "worker_id": None,
        "started_at": None,
        "output": None,
        "execution_time": None,
        "requires_tools": True,
        "tags": tags or [],
        "parent_task_id": "0fa10385-11eb-4c03-8e20-6873eeea8194",
        "review_status": "pending",
        "createdAt": datetime.now().isoformat() + "Z"
    }

# Load existing tasks
with open('.taskmaster/tasks/tasks.json', 'r') as f:
    data = json.load(f)

# Create follow-up tasks for missing RollbackManager implementation
tasks_to_add = [
    create_task(
        "Create RollbackManager class with core checkpoint functionality",
        "Implement RollbackManager in claude_orchestrator/rollback_manager.py with: 1) RollbackManager class definition, 2) create_checkpoint(task_id, metadata) method, 3) restore_checkpoint(checkpoint_id) method, 4) list_checkpoints() method, 5) delete_checkpoint(checkpoint_id) method, 6) File-based storage in .taskmaster/checkpoints/, 7) JSON serialization for checkpoint data",
        "high",
        ["rollback", "implementation", "followup", "opus-manager-review"]
    ),
    create_task(
        "Integrate RollbackManager with TaskMaster for automatic checkpoints",
        "Modify TaskMaster to integrate RollbackManager: 1) Import and initialize RollbackManager in TaskMaster.__init__, 2) Add create_checkpoint before task execution in execute_task(), 3) Add rollback_on_failure method to restore checkpoint on task failure, 4) Update task execution flow to handle checkpoint creation/restoration, 5) Add checkpoint_enabled config option",
        "high",
        ["rollback", "integration", "followup", "opus-manager-review"]
    ),
    create_task(
        "Add CLI commands for manual checkpoint operations",
        "Add checkpoint-related CLI commands to main.py: 1) 'checkpoint create <task_id>' command, 2) 'checkpoint list' command, 3) 'checkpoint restore <checkpoint_id>' command, 4) 'checkpoint delete <checkpoint_id>' command, 5) Add --no-checkpoint flag to disable checkpoint creation, 6) Update help documentation",
        "medium",
        ["rollback", "cli", "followup", "opus-manager-review"]
    ),
    create_task(
        "Update configuration for rollback settings",
        "Add rollback configuration options: 1) Add 'rollback' section to orchestrator_config.json, 2) Include checkpoint_enabled (bool), checkpoint_dir (str), max_checkpoints_per_task (int), auto_cleanup_days (int) settings, 3) Update ConfigManager to load rollback settings, 4) Add validation for rollback configuration",
        "medium",
        ["rollback", "configuration", "followup", "opus-manager-review"]
    ),
    create_task(
        "Write comprehensive tests for RollbackManager",
        "Create test_rollback_manager.py with tests for: 1) Checkpoint creation and storage, 2) Checkpoint restoration, 3) Checkpoint listing and filtering, 4) Checkpoint deletion, 5) Error handling for corrupt checkpoints, 6) Integration tests with TaskMaster, 7) CLI command tests",
        "high",
        ["rollback", "testing", "followup", "opus-manager-review"]
    )
]

# Add tasks to the list
data['tasks'].extend(tasks_to_add)

# Save updated tasks
with open('.taskmaster/tasks/tasks.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"✅ Added {len(tasks_to_add)} follow-up tasks for RollbackManager implementation")
for task in tasks_to_add:
    print(f"  - {task['title']} (Priority: {task['priority']})")