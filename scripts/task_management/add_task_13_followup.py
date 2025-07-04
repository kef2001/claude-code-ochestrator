#!/usr/bin/env python3
"""Create follow-up tasks for Task 13: Rollback Strategies"""

import json
import os
from datetime import datetime
import uuid

TASKS_FILE = ".taskmaster/tasks/tasks.json"

def load_tasks():
    """Load existing tasks"""
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, 'r') as f:
            return json.load(f)
    return {"tasks": [], "meta": {"totalTasks": 0}}

def save_tasks(data):
    """Save tasks to file"""
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def add_task(prompt, priority="medium", dependencies=None):
    """Add a new task"""
    data = load_tasks()
    
    # Generate a UUID for the task ID to match the current system
    next_id = str(uuid.uuid4())
    
    # Create task matching the existing format
    task = {
        "id": next_id,
        "title": prompt[:50] + "..." if len(prompt) > 50 else prompt,
        "description": prompt,
        "status": "pending",
        "dependencies": dependencies or [],
        "priority": priority,
        "details": prompt,
        "testStrategy": "Verify implementation works correctly with integration tests",
        "subtasks": [],
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "tags": ["rollback", "recovery"]
    }
    
    data["tasks"].append(task)
    
    # Update meta
    data["meta"]["totalTasks"] = len(data["tasks"])
    data["meta"]["pendingTasks"] = len([t for t in data["tasks"] if t["status"] == "pending"])
    data["meta"]["completedTasks"] = len([t for t in data["tasks"] if t["status"] == "done"])
    data["meta"]["updatedAt"] = datetime.now().isoformat()
    
    save_tasks(data)
    print(f"Added task {next_id}: {prompt[:80]}...")
    return next_id

# Create follow-up tasks for rollback strategies
tasks_to_add = [
    {
        "prompt": "Design and implement a StateSnapshot class for capturing complete system state before operations. Include: 1) Methods to capture current state of all orchestrator components (task queue, worker states, configuration), 2) Serialization to disk for persistence, 3) Validation of snapshot integrity, 4) Timestamp and metadata tracking. Save to claude_orchestrator/rollback/state_snapshot.py",
        "priority": "high"
    },
    {
        "prompt": "Implement a RollbackManager class that provides three rollback modes: 1) Full rollback - restore complete system state from snapshot, 2) Partial rollback - rollback specific components (workers, tasks, or config), 3) Selective rollback - undo specific operations by ID. Include proper error handling and rollback confirmation. Save to claude_orchestrator/rollback/rollback_manager.py",
        "priority": "high"
    },
    {
        "prompt": "Create a RecoveryPointManager class to manage rollback recovery points. Include: 1) Automatic recovery point creation before critical operations, 2) Manual recovery point creation API, 3) Recovery point retention policies (max count, age-based cleanup), 4) Recovery point metadata (description, tags, size). Save to claude_orchestrator/rollback/recovery_points.py",
        "priority": "high"
    },
    {
        "prompt": "Implement rollback triggers and monitoring. Create a RollbackTrigger class that: 1) Monitors system health metrics, 2) Detects anomalies or failures, 3) Automatically triggers appropriate rollback type based on failure severity, 4) Provides manual trigger interface. Include configurable thresholds and trigger rules. Save to claude_orchestrator/rollback/triggers.py",
        "priority": "medium"
    },
    {
        "prompt": "Add comprehensive error handling for rollback operations. Create a RollbackErrorHandler that: 1) Handles rollback failures gracefully, 2) Implements rollback retry logic, 3) Provides fallback strategies when rollback fails, 4) Logs all rollback attempts and outcomes. Save to claude_orchestrator/rollback/error_handler.py",
        "priority": "medium"
    },
    {
        "prompt": "Create integration tests for the rollback system. Test: 1) Full system rollback after task failure, 2) Partial rollback of specific workers, 3) Selective rollback of individual operations, 4) Recovery point creation and restoration, 5) Rollback trigger activation. Save to tests/test_rollback_system.py",
        "priority": "medium"
    },
    {
        "prompt": "Integrate rollback functionality into the main orchestrator. Update claude_orchestrator/main.py to: 1) Create recovery points before task execution, 2) Handle rollback commands via CLI, 3) Show rollback status in UI, 4) Provide rollback history and logs",
        "priority": "medium"
    }
]

# Add all tasks
task_ids = []
for task_data in tasks_to_add:
    task_id = add_task(
        prompt=task_data["prompt"],
        priority=task_data["priority"],
        dependencies=task_data.get("dependencies", [])
    )
    task_ids.append(task_id)

print(f"\nSuccessfully added {len(task_ids)} follow-up tasks for rollback strategy implementation")
print("Task IDs:", task_ids)