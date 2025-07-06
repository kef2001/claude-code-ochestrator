#!/usr/bin/env python3
"""Add follow-up tasks for properly implementing rollback strategies."""

import json
import uuid
from datetime import datetime
from pathlib import Path

def add_task(tasks, prompt, priority="medium", dependencies=None):
    """Add a new task to the tasks list."""
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "prompt": prompt,
        "priority": priority,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "dependencies": dependencies or [],
        "result": None,
        "worker_output": None,
        "error": None,
        "attempts": 0,
        "last_attempt": None
    }
    tasks.append(task)
    return task_id

def main():
    # Load existing tasks
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    if tasks_file.exists():
        with open(tasks_file, 'r') as f:
            data = json.load(f)
            tasks = data.get("tasks", [])
    else:
        tasks = []
    
    # Add rollback strategy implementation tasks
    task1_id = add_task(
        tasks,
        "Implement full rollback strategy for the Claude Code Orchestrator: Design and implement a complete rollback mechanism that can revert all task executions, state changes, and outputs to a previous checkpoint. Include transaction boundaries, state snapshots, and recovery procedures. The implementation should handle: 1) Complete system state reversion, 2) Task execution history rollback, 3) File system changes reversion, 4) Database/persistent state rollback",
        priority="high"
    )
    
    task2_id = add_task(
        tasks,
        "Implement partial rollback strategy: Design and implement a mechanism to rollback specific components or subsystems while keeping others intact. This should include: 1) Component isolation boundaries, 2) Selective state reversion, 3) Dependency analysis for safe partial rollbacks, 4) Conflict resolution when partial rollback affects shared resources",
        priority="high",
        dependencies=[task1_id]
    )
    
    task3_id = add_task(
        tasks,
        "Implement selective task rollback strategy: Create a mechanism to rollback individual task executions based on criteria like task ID, time range, or task type. Include: 1) Task dependency graph analysis, 2) Cascading rollback detection, 3) Orphaned state cleanup, 4) Rollback validation and verification",
        priority="high",
        dependencies=[task1_id]
    )
    
    task4_id = add_task(
        tasks,
        "Create rollback strategy integration tests: Develop comprehensive test suite for all rollback strategies including: 1) Full system rollback scenarios, 2) Partial rollback with various component combinations, 3) Selective task rollback with complex dependencies, 4) Rollback failure recovery, 5) Performance testing for large-scale rollbacks",
        priority="medium",
        dependencies=[task1_id, task2_id, task3_id]
    )
    
    # Save updated tasks
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    with open(tasks_file, 'w') as f:
        json.dump({"tasks": tasks}, f, indent=2)
    
    print(f"Successfully added 4 follow-up tasks for rollback strategy implementation")
    print(f"Task IDs:")
    print(f"  - Full rollback: {task1_id}")
    print(f"  - Partial rollback: {task2_id}")
    print(f"  - Selective rollback: {task3_id}")
    print(f"  - Integration tests: {task4_id}")

if __name__ == "__main__":
    main()