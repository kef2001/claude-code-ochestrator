#!/usr/bin/env python3

import json
import uuid
from datetime import datetime
from pathlib import Path

def main():
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    
    # Read existing tasks
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Create new task
    new_task = {
        "id": str(uuid.uuid4()),
        "prompt": "Implement actual RollbackManager integration tests with TaskMaster - Create test_rollback_integration.py with comprehensive test suite including: setup/teardown methods, test cases for state capture and restoration, mock TaskMaster interactions, error handling scenarios, edge case testing, and proper assertions. The worker MUST actually create the test file, not just describe what would be done.",
        "priority": "high",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "dependencies": [],
        "result": None,
        "worker_output": None,
        "error": None,
        "attempts": 0,
        "last_attempt": None,
        "title": "Implement actual RollbackManager integration tests",
        "description": "Create comprehensive integration tests for RollbackManager with TaskMaster. Must create the actual test file tests/test_rollback_integration.py with full implementation."
    }
    
    # Add to tasks list
    data["tasks"].append(new_task)
    
    # Write back
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Added rollback integration test task with ID: {new_task['id']}")
    print(f"   Title: {new_task['title']}")
    print(f"   Priority: {new_task['priority']}")

if __name__ == "__main__":
    main()