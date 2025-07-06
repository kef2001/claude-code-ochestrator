#!/usr/bin/env python3
"""
Add follow-up tasks for the incomplete Feedback Storage Layer implementation
"""

import json
import uuid
from pathlib import Path
from datetime import datetime

def main():
    # Load tasks directly from the JSON file
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    
    if not tasks_file.exists():
        print(f"❌ Tasks file not found at {tasks_file}")
        return
    
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    tasks = data.get('tasks', [])
    
    # Create new tasks
    new_tasks = []
    
    # Add high-priority task for actual storage implementation
    task1 = {
        "id": str(uuid.uuid4()),
        "title": "Implement actual feedback storage layer with SQLite",
        "description": "Create a complete feedback storage implementation with SQLite database",
        "status": "pending",
        "dependencies": [],
        "priority": "high",
        "details": """Requirements:
1. Create feedback_storage.py module in claude_orchestrator/
2. Define SQLite schema for feedback table with fields:
   - id (primary key)
   - task_id (foreign key)
   - feedback_type (string)
   - content (text)
   - rating (integer 1-5)
   - created_at (timestamp)
   - updated_at (timestamp)
3. Implement FeedbackStorage class with methods:
   - __init__(db_path): Initialize connection
   - create_feedback(task_id, type, content, rating): Create new feedback
   - get_feedback(feedback_id): Retrieve single feedback
   - get_feedback_by_task(task_id): Get all feedback for a task
   - update_feedback(feedback_id, updates): Update existing feedback
   - delete_feedback(feedback_id): Delete feedback
   - close(): Close database connection
4. Use context managers for proper connection handling
5. Add transaction support for data integrity
6. Include proper error handling and logging""",
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat()
    }
    new_tasks.append(task1)
    print(f"✓ Added task {task1['id']}: {task1['title']}")
    
    # Add task for unit tests
    task2 = {
        "id": str(uuid.uuid4()),
        "title": "Create comprehensive unit tests for feedback storage",
        "description": "Write pytest tests for all feedback storage functionality",
        "status": "pending",
        "dependencies": [],
        "priority": "high",
        "details": """Create tests/test_feedback_storage.py with:
1. Test database creation and schema
2. Test all CRUD operations
3. Test transaction rollback on errors
4. Test concurrent access handling
5. Test edge cases (invalid data, missing fields)
6. Test performance with large datasets
7. Use pytest fixtures for test database setup/teardown""",
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat()
    }
    new_tasks.append(task2)
    print(f"✓ Added task {task2['id']}: {task2['title']}")
    
    # Add task for integration
    task3 = {
        "id": str(uuid.uuid4()),
        "title": "Integrate feedback storage with orchestrator",
        "description": "Connect feedback storage to the main orchestrator workflow",
        "status": "pending",
        "dependencies": [],
        "priority": "medium",
        "details": """1. Add feedback configuration to orchestrator_config.json
2. Initialize FeedbackStorage in main orchestrator
3. Capture worker feedback after task completion
4. Store manager review feedback
5. Add CLI commands for feedback operations:
   - co feedback list [task-id]
   - co feedback show [feedback-id]
   - co feedback add [task-id] --type=review --content="..."
6. Update task status display to include feedback indicators""",
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat()
    }
    new_tasks.append(task3)
    print(f"✓ Added task {task3['id']}: {task3['title']}")
    
    # Add documentation task
    task4 = {
        "id": str(uuid.uuid4()),
        "title": "Document feedback storage system",
        "description": "Create comprehensive documentation for the feedback feature",
        "status": "pending",
        "dependencies": [],
        "priority": "low",
        "details": """1. Add feedback storage section to README.md
2. Create docs/feedback_storage.md with:
   - Architecture overview
   - Database schema documentation
   - API reference for FeedbackStorage class
   - Usage examples
   - Configuration options
3. Add inline code documentation (docstrings)
4. Update CLI help text for feedback commands""",
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat()
    }
    new_tasks.append(task4)
    print(f"✓ Added task {task4['id']}: {task4['title']}")
    
    # Add new tasks to the existing tasks list
    tasks.extend(new_tasks)
    
    # Update the data
    data['tasks'] = tasks
    data['meta']['updatedAt'] = datetime.now().isoformat()
    
    # Write back to file
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print("\n✅ Successfully added 4 follow-up tasks for feedback storage implementation")
    print("\nNext steps:")
    print("1. Run 'co list' to see all tasks")
    print("2. Run 'co run' to execute the tasks")

if __name__ == "__main__":
    main()