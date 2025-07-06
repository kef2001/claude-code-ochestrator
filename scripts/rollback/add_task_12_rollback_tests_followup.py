#!/usr/bin/env python3
"""
Add follow-up tasks for Task 12: Create rollback tests
"""

import json
from datetime import datetime
from pathlib import Path

def main():
    """Add follow-up tasks for implementing actual rollback tests"""
    
    # Path to tasks file
    tasks_file = Path(__file__).parent / ".taskmaster" / "tasks" / "tasks.json"
    
    # Load existing tasks
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Get next task ID - handle mixed int/string IDs
    existing_ids = [task["id"] for task in data["tasks"]]
    int_ids = [id for id in existing_ids if isinstance(id, int)]
    next_id = max(int_ids) + 1 if int_ids else 1
    
    # Follow-up tasks for rollback test implementation
    tasks_to_add = [
        {
            "title": "Implement rollback mechanism unit tests",
            "description": "Create comprehensive unit tests for the rollback mechanism including tests for successful rollbacks, partial rollbacks, and rollback failures",
            "priority": "high",
            "details": """Create unit tests that cover:
- Basic rollback functionality
- Rollback with dependencies
- Partial rollback scenarios
- Rollback failure handling
- State persistence during rollback
- Rollback event notifications"""
        },
        {
            "title": "Create rollback integration tests",
            "description": "Develop integration tests that verify rollback behavior across the entire system",
            "priority": "high",
            "details": """Integration tests should include:
- End-to-end rollback scenarios
- Multi-task rollback sequences
- Rollback with active workers
- Database state verification after rollback
- API endpoint testing for rollback operations"""
        },
        {
            "title": "Add rollback stress tests",
            "description": "Implement stress tests to ensure rollback mechanism handles high load and edge cases",
            "priority": "medium",
            "details": """Stress tests should cover:
- Concurrent rollback requests
- Large-scale rollbacks (100+ tasks)
- Memory usage during rollback
- Performance benchmarks
- Resource cleanup verification"""
        },
        {
            "title": "Create rollback test fixtures and mocks",
            "description": "Develop reusable test fixtures and mocks for rollback testing",
            "priority": "medium",
            "details": """Create:
- Mock task states for testing
- Test data generators
- Rollback scenario builders
- State verification helpers
- Error injection utilities"""
        }
    ]
    
    # Add tasks to the data
    created_tasks = []
    current_time = datetime.now().isoformat()
    
    for i, task_data in enumerate(tasks_to_add):
        new_task = {
            "id": next_id + i,
            "title": task_data["title"],
            "description": task_data["description"],
            "status": "pending",
            "dependencies": [],
            "priority": task_data["priority"],
            "details": task_data["details"],
            "testStrategy": "",
            "subtasks": [],
            "createdAt": current_time,
            "updatedAt": current_time,
            "tags": ["rollback", "testing", "task-12-followup"]
        }
        data["tasks"].append(new_task)
        created_tasks.append({
            "id": new_task["id"],
            "title": new_task["title"],
            "priority": new_task["priority"]
        })
        print(f"✓ Created task {new_task['id']}: {new_task['title']}")
    
    # Update metadata
    data["meta"]["totalTasks"] = len(data["tasks"])
    data["meta"]["pendingTasks"] = sum(1 for t in data["tasks"] if t["status"] == "pending")
    data["meta"]["completedTasks"] = sum(1 for t in data["tasks"] if t["status"] == "done")
    data["meta"]["updatedAt"] = current_time
    
    # Save updated tasks file
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Save task IDs for reference
    output_file = Path(__file__).parent / "task_12_rollback_tests_followup.json"
    with open(output_file, 'w') as f:
        json.dump({
            "parent_task": "12",
            "parent_title": "Create rollback tests",
            "followup_tasks": created_tasks,
            "total_tasks": len(created_tasks)
        }, f, indent=2)
    
    print(f"\nCreated {len(created_tasks)} follow-up tasks for Task 12")
    print(f"Task IDs saved to: {output_file}")

if __name__ == "__main__":
    main()