#!/usr/bin/env python3
"""Add critical follow-up task for actual rollback test implementation."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

def add_rollback_test_task():
    """Add task for implementing comprehensive rollback tests."""
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    
    # Read existing tasks
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Create new task
    new_task = {
        "id": str(uuid.uuid4()),
        "title": "CRITICAL: Implement comprehensive rollback tests",
        "description": """Actually implement comprehensive rollback tests in tests/test_rollback.py. 

MUST include:
1) Test rollback state transitions (pending->rolling_back->rolled_back)
2) Test file restoration after rollback
3) Test task state recovery
4) Test error handling during rollback operations
5) Test edge cases like partial rollback failures

Use pytest framework with proper fixtures and assertions. This is the actual implementation, not planning.

Previous task only produced planning documentation - no actual tests were created.""",
        "status": "pending",
        "priority": "high",
        "tags": ["rollback", "testing", "implementation", "critical", "opus-manager-review"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "worker": None,
        "started_at": None,
        "completed_at": None,
        "output": None,
        "error": None,
        "review_status": None,
        "review_comments": None,
        "parent_task_id": "fe1bd532-b40e-4628-a164-714350a89676"
    }
    
    # Add to tasks
    data["tasks"].append(new_task)
    
    # Save
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Added critical rollback test implementation task: {new_task['id']}")
    print(f"Title: {new_task['title']}")
    print(f"Priority: HIGH")
    print(f"Tags: {', '.join(new_task['tags'])}")

if __name__ == "__main__":
    add_rollback_test_task()