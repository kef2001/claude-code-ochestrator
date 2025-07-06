#!/usr/bin/env python3
"""Create follow-up tasks for SQLite feedback storage implementation"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_orchestrator.task_master import TaskManager

def create_feedback_storage_tasks():
    """Create tasks for implementing SQLite feedback storage"""
    
    # Initialize task manager
    task_manager = TaskManager()
    
    tasks = [
        {
            "title": "Create SQLite database schema and connection manager",
            "description": """Create feedback_storage.py in claude_orchestrator/ with:
- SQLiteConnection class for managing database connections
- Database initialization with feedback table schema:
  - id (INTEGER PRIMARY KEY)
  - task_id (TEXT NOT NULL)
  - feedback_type (TEXT NOT NULL)
  - content (TEXT NOT NULL)
  - metadata (JSON)
  - created_at (TIMESTAMP)
  - updated_at (TIMESTAMP)
- Schema migration support
- Connection pooling
- Proper error handling and logging""",
            "priority": "high",
            "details": "Tags: feedback-storage, sqlite, database, followup, opus-manager-review"
        },
        {
            "title": "Implement Feedback model and CRUD operations",
            "description": """Create feedback_model.py in claude_orchestrator/ with:
- Feedback dataclass with proper typing
- CRUD operations:
  - create_feedback(task_id, type, content, metadata)
  - get_feedback(feedback_id)
  - update_feedback(feedback_id, updates)
  - delete_feedback(feedback_id)
- Query methods:
  - get_feedback_by_task(task_id)
  - get_feedback_by_type(feedback_type)
  - get_feedback_by_date_range(start, end)
- Batch operations support
- Input validation and sanitization""",
            "priority": "high",
            "details": "Tags: feedback-storage, model, crud, followup, opus-manager-review"
        },
        {
            "title": "Create feedback storage integration layer",
            "description": """Integrate feedback storage with orchestrator:
- Add feedback hooks to task completion in enhanced_orchestrator.py
- Create feedback submission methods for workers and managers
- Add API endpoints for feedback operations
- Implement async operation support
- Add feedback retrieval to task context
- Update task_master.py to include feedback references""",
            "priority": "high",
            "details": "Tags: feedback-storage, integration, followup, opus-manager-review"
        },
        {
            "title": "Write comprehensive tests for feedback storage",
            "description": """Create test_feedback_storage.py in tests/ with:
- Unit tests for SQLite connection and schema
- Tests for all CRUD operations
- Edge case testing (invalid data, SQL injection attempts)
- Integration tests with orchestrator
- Performance tests for large datasets
- Concurrent access tests
- Migration tests
- Mock database for testing""",
            "priority": "medium",
            "details": "Tags: feedback-storage, testing, followup"
        },
        {
            "title": "Add feedback CLI commands",
            "description": """Extend task_master.py with feedback commands:
- feedback add --task-id ID --type TYPE --content CONTENT
- feedback list [--task-id ID] [--type TYPE]
- feedback get FEEDBACK_ID
- feedback update FEEDBACK_ID --content CONTENT
- feedback delete FEEDBACK_ID
- Add feedback display to task show command""",
            "priority": "medium",
            "details": "Tags: feedback-storage, cli, followup"
        }
    ]
    
    created_task_ids = []
    
    for task in tasks:
        try:
            task = task_manager.add_task(
                title=task["title"],
                description=task["description"],
                priority=task["priority"],
                details=task.get("details")
            )
            task_id = task.id
            created_task_ids.append(task_id)
            print(f"✅ Created task: {task['title']} (ID: {task_id})")
        except Exception as e:
            print(f"❌ Failed to create task '{task['title']}': {e}")
    
    print(f"\n📋 Created {len(created_task_ids)} follow-up tasks for SQLite feedback storage implementation")
    return created_task_ids

if __name__ == "__main__":
    create_feedback_storage_tasks()