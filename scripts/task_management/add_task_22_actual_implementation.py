#!/usr/bin/env python3
"""Add follow-up tasks for Task 22 actual implementation"""

import json
import uuid
from datetime import datetime
from pathlib import Path

def add_tasks():
    """Add follow-up tasks for actual RollbackManager implementation"""
    
    # Load existing tasks
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Create follow-up tasks
    new_tasks = [
        {
            "id": str(uuid.uuid4()),
            "prompt": "Implement actual RollbackManager class with core rollback functionality including: state capture, rollback triggers, restoration logic, and error handling. Create claude_orchestrator/rollback_manager.py",
            "priority": "high",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "worker_id": None,
            "metadata": {
                "parent_task": "22",
                "type": "implementation",
                "description": "Create the actual RollbackManager class implementation"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "prompt": "Add rollback hooks to ClaudeOrchestrator class in claude_orchestrator/main.py. Integrate RollbackManager to capture state before task execution and enable rollback on failures",
            "priority": "high", 
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "worker_id": None,
            "metadata": {
                "parent_task": "22",
                "type": "integration",
                "description": "Add integration points in orchestrator"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "prompt": "Implement rollback configuration in orchestrator_config.json schema and ConfigurationManager to support rollback settings like max_rollback_depth, auto_rollback_on_failure, rollback_timeout",
            "priority": "medium",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "worker_id": None,
            "metadata": {
                "parent_task": "22",
                "type": "configuration",
                "description": "Add rollback configuration support"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "prompt": "Create unit tests for RollbackManager in tests/test_rollback_manager.py covering: state capture, rollback operations, error scenarios, and integration with orchestrator",
            "priority": "medium",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "worker_id": None,
            "metadata": {
                "parent_task": "22",
                "type": "testing",
                "description": "Create comprehensive tests for rollback functionality"
            }
        }
    ]
    
    # Add tasks to the list
    data["tasks"].extend(new_tasks)
    
    # Update metadata
    data["metadata"]["total_tasks"] = len(data["tasks"])
    data["metadata"]["last_updated"] = datetime.now().isoformat()
    
    # Create backup
    backup_file = tasks_file.with_suffix(f".json.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    with open(backup_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Write updated tasks
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Added {len(new_tasks)} follow-up tasks for Task 22 actual implementation")
    for task in new_tasks:
        print(f"  - [{task['priority']}] {task['prompt'][:80]}...")
    
    return new_tasks

if __name__ == "__main__":
    tasks = add_tasks()
    print(f"\nTotal tasks added: {len(tasks)}")