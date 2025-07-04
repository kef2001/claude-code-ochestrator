#!/usr/bin/env python3
"""Script to add follow-up tasks for Task 35 RollbackManager implementation."""

import json
import uuid
from datetime import datetime, timezone

def create_task(prompt, priority="medium"):
    """Create a task dictionary."""
    return {
        "id": str(uuid.uuid4()),
        "prompt": prompt,
        "status": "pending",
        "priority": priority,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

def main():
    # Load existing tasks
    try:
        with open('.taskmaster/tasks/tasks.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Tasks file not found!")
        return
    
    # Create new tasks for proper RollbackManager implementation
    new_tasks = [
        create_task(
            "Implement the actual RollbackManager class in claude_orchestrator/rollback.py with full checkpoint functionality including: "
            "create_checkpoint(), restore_checkpoint(), list_checkpoints(), delete_checkpoint(), and validate_checkpoint() methods. "
            "Include proper error handling and state validation.",
            priority="high"
        ),
        create_task(
            "Add comprehensive unit tests for RollbackManager in tests/test_rollback.py covering all methods, "
            "edge cases, error scenarios, and checkpoint integrity validation",
            priority="high"
        ),
        create_task(
            "Create integration tests for RollbackManager with TaskMaster to ensure proper system state capture "
            "and restoration during rollback operations",
            priority="medium"
        ),
        create_task(
            "Add documentation for RollbackManager usage in docs/rollback.md including examples, "
            "best practices, and checkpoint management strategies",
            priority="low"
        )
    ]
    
    # Add tasks to the data
    data['tasks'].extend(new_tasks)
    
    # Write back to file
    with open('.taskmaster/tasks/tasks.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Added {len(new_tasks)} follow-up tasks for RollbackManager implementation:")
    for task in new_tasks:
        print(f"  - [{task['priority']}] {task['prompt'][:80]}...")

if __name__ == "__main__":
    main()