#!/usr/bin/env python3
"""Add follow-up tasks for actual RollbackManager implementation"""

import json
import uuid
from datetime import datetime

def create_task(task_id, title, description, priority="high", tags=None):
    """Create a task dictionary with proper structure"""
    if tags is None:
        tags = ["rollback", "implementation", "followup", "opus-manager-review"]
    
    return {
        "id": task_id,
        "title": title,
        "description": description,
        "status": "pending",
        "dependencies": [],
        "priority": priority,
        "details": "Follow-up task created after review of incomplete RollbackManager implementation",
        "testStrategy": "Create comprehensive unit and integration tests",
        "subtasks": [],
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "tags": tags
    }

def main():
    # Load existing tasks
    tasks_file = ".taskmaster/tasks/tasks.json"
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Get the next task ID - handle both numeric and string IDs
    numeric_ids = []
    for t in data['tasks']:
        task_id = t.get('id', 0)
        if isinstance(task_id, int):
            numeric_ids.append(task_id)
    
    next_id = max(numeric_ids + [47]) + 1  # Use 47 as minimum if no numeric IDs
    
    # Define the follow-up tasks
    tasks = [
        create_task(
            task_id=next_id,
            title="Implement RollbackManager core class",
            description="Create RollbackManager class in claude_orchestrator/rollback_manager.py with: 1) __init__ method to initialize checkpoint directory, 2) create_checkpoint(task_id, data) method to save task state, 3) rollback_to_checkpoint(checkpoint_id) method to restore state, 4) list_checkpoints() method to show available checkpoints, 5) delete_checkpoint(checkpoint_id) method for cleanup. Include proper error handling and logging throughout.",
            priority="high"
        ),
        create_task(
            task_id=next_id + 1,
            title="Integrate RollbackManager with TaskMaster",
            description="Modify TaskMaster to use RollbackManager: 1) Import and initialize RollbackManager in TaskMaster.__init__, 2) Add checkpoint creation before task execution in run_worker_task, 3) Add rollback capability on task failure, 4) Update task state management to support rollback operations, 5) Ensure thread-safe checkpoint operations.",
            priority="high"
        ),
        create_task(
            task_id=next_id + 2,
            title="Add CLI commands for rollback operations",
            description="Add new CLI commands to main.py: 1) 'co checkpoint list' - List all checkpoints, 2) 'co checkpoint create <task_id>' - Manually create checkpoint, 3) 'co checkpoint rollback <checkpoint_id>' - Rollback to checkpoint, 4) 'co checkpoint delete <checkpoint_id>' - Delete checkpoint. Update argument parser and command handling.",
            priority="medium"
        ),
        create_task(
            task_id=next_id + 3,
            title="Update configuration for rollback settings",
            description="Add rollback configuration to orchestrator_config.json: 1) checkpoint_dir: Directory to store checkpoints, 2) auto_checkpoint: Enable/disable automatic checkpointing, 3) checkpoint_retention_days: How long to keep checkpoints, 4) max_checkpoints_per_task: Limit checkpoints per task. Update ConfigManager to handle these settings.",
            priority="medium"
        ),
        create_task(
            task_id=next_id + 4,
            title="Create comprehensive tests for RollbackManager",
            description="Create test suite in tests/test_rollback_manager.py: 1) Test checkpoint creation and storage, 2) Test rollback functionality, 3) Test checkpoint listing and deletion, 4) Test error handling for invalid operations, 5) Test thread safety and concurrent operations, 6) Integration tests with TaskMaster.",
            priority="high"
        )
    ]
    
    # Add new tasks
    for task in tasks:
        data['tasks'].append(task)
        print(f"✅ Added task {task['id']}: {task['title']}")
    
    # Update metadata
    data['meta']['totalTasks'] = len(data['tasks'])
    data['meta']['pendingTasks'] = len([t for t in data['tasks'] if t['status'] == 'pending'])
    data['meta']['completedTasks'] = len([t for t in data['tasks'] if t['status'] in ['completed', 'done']])
    data['meta']['updatedAt'] = datetime.now().isoformat()
    
    # Save updated tasks
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n🎯 Successfully added {len(tasks)} follow-up tasks for RollbackManager implementation")
    print("\nUse 'co list --filter-status pending' to see the new tasks")

if __name__ == "__main__":
    main()