#!/usr/bin/env python3
"""Script to add RollbackManager implementation task."""

import json
import uuid
from pathlib import Path
from datetime import datetime

def add_task():
    """Add the RollbackManager implementation task."""
    tasks_path = Path(".taskmaster/tasks/tasks.json")
    
    # Load existing tasks
    with open(tasks_path, "r") as f:
        data = json.load(f)
    
    # Create new task
    new_task = {
        "id": str(uuid.uuid4()),
        "type": "implementation",
        "description": (
            "Implement RollbackManager class in claude_orchestrator/rollback.py with ALL required features: "
            "1) Create RollbackManager class (not CheckpointManager), "
            "2) Implement all 5 required methods: create_checkpoint(), list_checkpoints(), "
            "restore_checkpoint(checkpoint_id), delete_checkpoint(checkpoint_id), validate_checkpoint(checkpoint_data), "
            "3) Add checkpoint serialization using JSON format, "
            "4) Implement versioning and compatibility checks, "
            "5) Add comprehensive error handling for corrupt or incompatible checkpoints, "
            "6) Write unit tests for all functionality"
        ),
        "status": "pending",
        "priority": "high",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "worker_id": None,
        "started_at": None,
        "output": None,
        "execution_time": None,
        "requires_tools": True,
        "tags": ["rollback", "implementation", "followup"],
        "parent_task_id": "29d44a3c-2234-4946-a270-b63d69e62651",
        "review_status": "pending"
    }
    
    # Add to tasks
    if "tasks" not in data:
        data["tasks"] = []
    data["tasks"].append(new_task)
    
    # Update metadata
    if "meta" not in data:
        data["meta"] = {}
    data["meta"]["last_updated"] = datetime.utcnow().isoformat() + "Z"
    data["meta"]["total_tasks"] = len(data["tasks"])
    
    # Write back
    with open(tasks_path, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"Added RollbackManager implementation task with ID: {new_task['id']}")
    print(f"Priority: {new_task['priority']}")
    print(f"Tags: {', '.join(new_task['tags'])}")

if __name__ == "__main__":
    add_task()