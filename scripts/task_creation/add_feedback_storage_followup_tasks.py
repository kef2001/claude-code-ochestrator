#!/usr/bin/env python3
"""Add follow-up tasks for implementing feedback storage module and tests."""

import json
import os
from datetime import datetime
from pathlib import Path

def add_tasks():
    """Add follow-up tasks for feedback storage implementation."""
    
    # Load existing tasks
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Get the next task ID - handle both integer and UUID formats
    import uuid
    existing_ids = []
    for task in data['tasks']:
        if isinstance(task['id'], int):
            existing_ids.append(task['id'])
        elif isinstance(task['id'], str) and task['id'].isdigit():
            existing_ids.append(int(task['id']))
    
    # Use UUID for new tasks to avoid conflicts
    task_ids = []
    for i in range(4):
        task_ids.append(str(uuid.uuid4()))
    
    # Define new tasks
    new_tasks = [
        {
            "id": task_ids[0],
            "title": "Implement feedback storage module core",
            "description": "Create the core feedback storage module with SQLite backend for storing task feedback and reviews",
            "status": "pending",
            "dependencies": [],
            "priority": "high",
            "details": "Implement FeedbackStorage class with SQLite backend, including schema creation, CRUD operations for feedback entries, and proper error handling",
            "testStrategy": "Unit tests for all database operations, schema validation, and error cases",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["followup", "opus-manager-review", "feedback-storage"]
        },
        {
            "id": task_ids[1],
            "title": "Create feedback storage database schema",
            "description": "Design and implement the SQLite database schema for feedback storage",
            "status": "pending",
            "dependencies": [],
            "priority": "high",
            "details": "Create tables for feedback entries, review history, task associations, and metadata. Include proper indexes and constraints",
            "testStrategy": "Schema validation tests, constraint tests",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["followup", "opus-manager-review", "feedback-storage"]
        },
        {
            "id": task_ids[2],
            "title": "Write comprehensive unit tests for feedback storage",
            "description": "Create pytest tests covering all feedback storage functionality",
            "status": "pending",
            "dependencies": [task_ids[0], task_ids[1]],
            "priority": "high",
            "details": "Write tests for: database connection management, CRUD operations, error handling, concurrent access, data validation, and edge cases",
            "testStrategy": "Use pytest with fixtures, mock database for isolation, test coverage > 90%",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["followup", "opus-manager-review", "testing"]
        },
        {
            "id": task_ids[3],
            "title": "Implement feedback retrieval and query methods",
            "description": "Add methods for querying and retrieving feedback data with filtering",
            "status": "pending",
            "dependencies": [task_ids[0]],
            "priority": "medium",
            "details": "Implement methods for: getting feedback by task ID, filtering by date range, aggregating ratings, exporting feedback data",
            "testStrategy": "Unit tests for all query methods with various filter combinations",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["followup", "opus-manager-review", "feedback-storage"]
        }
    ]
    
    # Add new tasks to the data
    data['tasks'].extend(new_tasks)
    
    # Update metadata
    data['meta']['totalTasks'] = len(data['tasks'])
    data['meta']['pendingTasks'] = len([t for t in data['tasks'] if t['status'] == 'pending'])
    data['meta']['completedTasks'] = len([t for t in data['tasks'] if t['status'] == 'done'])
    data['meta']['updatedAt'] = datetime.now().isoformat()
    
    # Save updated tasks
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Successfully added {len(new_tasks)} follow-up tasks for feedback storage implementation")
    print("\nAdded tasks:")
    for task in new_tasks:
        print(f"  - Task {task['id']}: {task['title']} (Priority: {task['priority']})")

if __name__ == "__main__":
    add_tasks()