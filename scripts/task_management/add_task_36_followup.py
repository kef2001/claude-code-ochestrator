#!/usr/bin/env python3
import json
import os
import uuid
from datetime import datetime

TASKS_FILE = '.taskmaster/tasks/tasks.json'

def add_task(prompt, priority='medium'):
    """Add a new task to the tasks.json file"""
    
    # Load existing tasks
    with open(TASKS_FILE, 'r') as f:
        data = json.load(f)
    
    # Generate new UUID
    task_id = str(uuid.uuid4())
    
    # Create new task
    new_task = {
        "id": task_id,
        "prompt": prompt,
        "priority": priority,
        "status": "pending",
        "worker_id": None,
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
        "retry_count": 0
    }
    
    # Add to tasks list
    data['tasks'].append(new_task)
    
    # Write back to file
    with open(TASKS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Added task {task_id}: {prompt[:50]}...")
    return task_id

# Add follow-up tasks for Task 36
print("Adding follow-up tasks for Task 36 (RollbackManager)...")

# Task 1: Implement actual RollbackManager class
add_task(
    "Implement RollbackManager class with proper integration to CheckpointManager including: "
    "1) Create claude_orchestrator/rollback_manager.py with RollbackManager class, "
    "2) Methods for initiating rollback, validating checkpoints, and executing rollback operations, "
    "3) Error handling for rollback failures, "
    "4) Integration hooks for CheckpointManager",
    priority="high"
)

# Task 2: Create unit tests
add_task(
    "Create comprehensive unit tests for RollbackManager in tests/test_rollback_manager.py including: "
    "1) Test rollback initiation and validation, "
    "2) Test checkpoint integration, "
    "3) Test error handling scenarios, "
    "4) Test rollback execution with mock data",
    priority="high"
)

# Task 3: Add rollback documentation
add_task(
    "Document RollbackManager usage and integration: "
    "1) Add detailed docstrings to all RollbackManager methods, "
    "2) Create docs/rollback_management.md with usage examples, "
    "3) Document rollback strategies and best practices",
    priority="medium"
)

print("Follow-up tasks added successfully!")