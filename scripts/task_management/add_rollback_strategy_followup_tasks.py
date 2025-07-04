#!/usr/bin/env python3
"""Add follow-up tasks for implementing actual rollback strategies"""

import json
from datetime import datetime
from pathlib import Path

def add_rollback_strategy_tasks():
    """Add follow-up tasks for Task 38 rollback strategies implementation"""
    
    tasks_file = Path('.taskmaster/tasks/tasks.json')
    
    # Read existing tasks
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Get the next task ID
    next_id = max(task['id'] for task in data['tasks']) + 1
    
    # Define the rollback strategy implementation tasks
    rollback_tasks = [
        {
            "id": next_id,
            "title": "Implement FullSystemRollback strategy",
            "description": "Create FullSystemRollback class that restores all tasks to checkpoint state",
            "status": "pending",
            "dependencies": [],
            "priority": "high",
            "details": "Implement in claude_orchestrator/rollback_strategies.py:\n- Class FullSystemRollback(RollbackStrategy)\n- Methods: create_snapshot(), restore_snapshot(), validate_restoration()\n- Handle worker coordination during full system rollback\n- Include comprehensive error handling and logging",
            "testStrategy": "Unit tests for snapshot/restore functionality, integration tests with checkpoint system",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["rollback", "implementation", "follow-up-task-38"]
        },
        {
            "id": next_id + 1,
            "title": "Implement SelectiveRollback strategy",
            "description": "Create SelectiveRollback class for rolling back specific failed tasks only",
            "status": "pending",
            "dependencies": [],
            "priority": "high",
            "details": "Implement in claude_orchestrator/rollback_strategies.py:\n- Class SelectiveRollback(RollbackStrategy)\n- Methods: identify_failed_tasks(), rollback_task(), preserve_successful_tasks()\n- Maintain task isolation during selective rollback\n- Handle partial state restoration",
            "testStrategy": "Unit tests for selective rollback logic, tests for task isolation",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["rollback", "implementation", "follow-up-task-38"]
        },
        {
            "id": next_id + 2,
            "title": "Implement CascadingRollback strategy",
            "description": "Create CascadingRollback class that automatically rolls back dependent tasks",
            "status": "pending",
            "dependencies": [],
            "priority": "medium",
            "details": "Implement in claude_orchestrator/rollback_strategies.py:\n- Class CascadingRollback(RollbackStrategy)\n- Methods: analyze_dependencies(), cascade_rollback(), validate_cascade()\n- Handle dependency graph traversal\n- Ensure no orphaned tasks after rollback",
            "testStrategy": "Unit tests for dependency analysis, integration tests with task dependency system",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["rollback", "implementation", "follow-up-task-38"]
        },
        {
            "id": next_id + 3,
            "title": "Implement PartialRollback strategy",
            "description": "Create PartialRollback class for rolling back to intermediate checkpoints",
            "status": "pending",
            "dependencies": [],
            "priority": "medium",
            "details": "Implement in claude_orchestrator/rollback_strategies.py:\n- Class PartialRollback(RollbackStrategy)\n- Methods: find_intermediate_checkpoint(), partial_restore(), validate_partial_state()\n- Handle incremental rollback to specific points\n- Preserve work done after checkpoint",
            "testStrategy": "Unit tests for checkpoint selection, tests for partial state restoration",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["rollback", "implementation", "follow-up-task-38"]
        },
        {
            "id": next_id + 4,
            "title": "Create base RollbackStrategy interface",
            "description": "Implement abstract base class for all rollback strategies",
            "status": "pending",
            "dependencies": [],
            "priority": "high",
            "details": "Create in claude_orchestrator/rollback_strategies.py:\n- Abstract class RollbackStrategy\n- Define interface: execute_rollback(), validate_rollback(), get_rollback_report()\n- Common utilities for all strategies\n- Integration hooks with checkpoint system",
            "testStrategy": "Unit tests for base class, ensure proper inheritance in strategies",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["rollback", "implementation", "follow-up-task-38"]
        },
        {
            "id": next_id + 5,
            "title": "Integrate rollback strategies with orchestrator",
            "description": "Connect rollback strategies to main orchestrator workflow",
            "status": "pending",
            "dependencies": [next_id, next_id + 1, next_id + 2, next_id + 3, next_id + 4],
            "priority": "medium",
            "details": "Modify orchestrator to use rollback strategies:\n- Add rollback strategy selection logic\n- Hook into error handling flow\n- Add CLI commands for manual rollback\n- Update configuration for rollback preferences",
            "testStrategy": "Integration tests with full orchestrator flow, end-to-end rollback tests",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["rollback", "integration", "follow-up-task-38"]
        }
    ]
    
    # Add new tasks
    data['tasks'].extend(rollback_tasks)
    
    # Update metadata
    data['meta']['totalTasks'] = len(data['tasks'])
    data['meta']['pendingTasks'] = sum(1 for task in data['tasks'] if task['status'] == 'pending')
    data['meta']['completedTasks'] = sum(1 for task in data['tasks'] if task['status'] == 'done')
    data['meta']['updatedAt'] = datetime.now().isoformat()
    
    # Save updated tasks
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Successfully added {len(rollback_tasks)} rollback strategy implementation tasks")
    print(f"Task IDs: {next_id} through {next_id + len(rollback_tasks) - 1}")
    
    # Print task summaries
    print("\nAdded tasks:")
    for task in rollback_tasks:
        print(f"  - Task {task['id']}: {task['title']} (Priority: {task['priority']})")

if __name__ == "__main__":
    add_rollback_strategy_tasks()