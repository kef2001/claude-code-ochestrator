#!/usr/bin/env python3
"""Add follow-up tasks for Task 38: Implement rollback strategies"""

import json
import uuid
from datetime import datetime
from pathlib import Path

def main():
    # Load existing tasks
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Get the next task ID
    existing_ids = []
    for task in data["tasks"]:
        if isinstance(task.get("id"), int):
            existing_ids.append(task["id"])
    next_id = max(existing_ids) + 1 if existing_ids else 100
    
    # Follow-up tasks for implementing rollback strategies
    tasks = [
        {
            "prompt": "Implement FullSystemRollback strategy class in claude_orchestrator/rollback/strategies.py. This class should: 1) Inherit from base RollbackStrategy class, 2) Implement execute() method to restore complete system state from checkpoint, 3) Include worker coordination to stop all active tasks, 4) Validate checkpoint integrity before rollback, 5) Provide rollback progress tracking",
            "priority": "high",
            "tags": ["rollback", "strategy", "task-38-followup"]
        },
        {
            "prompt": "Implement SelectiveRollback strategy class in claude_orchestrator/rollback/strategies.py. This class should: 1) Allow rollback of specific failed tasks only, 2) Maintain state of successful tasks, 3) Handle task dependency chains properly, 4) Provide task selection interface, 5) Include validation to ensure selective rollback won't break system consistency",
            "priority": "high", 
            "tags": ["rollback", "strategy", "task-38-followup"]
        },
        {
            "prompt": "Implement CascadingRollback strategy class in claude_orchestrator/rollback/strategies.py. This class should: 1) Automatically identify and rollback dependent tasks, 2) Build dependency graph for affected tasks, 3) Execute rollbacks in correct order, 4) Handle circular dependencies, 5) Provide dry-run mode to preview cascade effects",
            "priority": "high",
            "tags": ["rollback", "strategy", "task-38-followup"]
        },
        {
            "prompt": "Implement PartialRollback strategy class in claude_orchestrator/rollback/strategies.py. This class should: 1) Support rollback to intermediate checkpoints, 2) Allow component-specific rollback (workers, config, tasks), 3) Maintain partial system state consistency, 4) Provide granular control over rollback scope, 5) Include state merging capabilities",
            "priority": "medium",
            "tags": ["rollback", "strategy", "task-38-followup"]
        },
        {
            "prompt": "Create base RollbackStrategy abstract class in claude_orchestrator/rollback/strategies.py with: 1) Abstract execute() method, 2) Common validation methods, 3) Worker coordination interface, 4) Progress tracking capabilities, 5) Error handling framework. All strategy classes should inherit from this base.",
            "priority": "high",
            "tags": ["rollback", "strategy", "task-38-followup", "base-class"]
        },
        {
            "prompt": "Write comprehensive unit tests for all rollback strategies in tests/test_rollback_strategies.py. Include: 1) Test each strategy's execute() method, 2) Test validation and error handling, 3) Test worker coordination, 4) Mock checkpoint data for testing, 5) Ensure >90% code coverage",
            "priority": "medium",
            "tags": ["rollback", "strategy", "testing", "task-38-followup"]
        }
    ]
    
    print("Adding Task 38 rollback strategy follow-up tasks...")
    
    # Add new tasks to the data
    new_tasks = []
    for i, task in enumerate(tasks):
        new_task = {
            "id": next_id + i,
            "title": task["prompt"][:80] + "...",
            "description": task["prompt"],
            "status": "pending",
            "dependencies": [],
            "priority": task.get("priority", "medium"),
            "details": task["prompt"],
            "testStrategy": "Unit tests and integration tests",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": task.get("tags", [])
        }
        new_tasks.append(new_task)
        print(f"✓ Added task {new_task['id']}: {task['prompt'][:60]}...")
    
    # Add tasks to the data structure
    data["tasks"].extend(new_tasks)
    data["meta"]["totalTasks"] = len(data["tasks"])
    data["meta"]["updatedAt"] = datetime.now().isoformat()
    
    # Save updated tasks
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nSuccessfully added {len(new_tasks)} Task 38 follow-up tasks!")

if __name__ == "__main__":
    main()