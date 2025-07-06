#!/usr/bin/env python3
"""Create implementation tasks for Task 15: Feedback Storage Backend"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_orchestrator.task_master import TaskManager

def create_storage_implementation_tasks():
    """Create tasks for implementing the feedback storage backend"""
    
    # Initialize task manager
    task_manager = TaskManager()
    
    tasks = [
        {
            "title": "Implement FeedbackModel with validation and serialization",
            "description": """Create feedback_model.py in claude_orchestrator/ with:
- FeedbackModel dataclass with fields:
  - id: str (UUID)
  - task_id: str
  - feedback_type: str (enum: rating, comment, suggestion, error)
  - content: Dict[str, Any]
  - metadata: Dict[str, Any]
  - created_at: datetime
  - updated_at: datetime
- Validation methods for each field
- to_dict() and from_dict() serialization methods
- JSON schema validation
- Type hints and documentation""",
            "priority": "high",
            "details": "Tags: feedback-storage, model, implementation, opus-manager-review"
        },
        {
            "title": "Create abstract FeedbackStorageInterface",
            "description": """Create feedback_storage_interface.py in claude_orchestrator/ with:
- Abstract base class FeedbackStorageInterface
- Abstract methods:
  - create(feedback: FeedbackModel) -> str
  - read(feedback_id: str) -> Optional[FeedbackModel]
  - update(feedback_id: str, updates: Dict) -> bool
  - delete(feedback_id: str) -> bool
  - query_by_task(task_id: str) -> List[FeedbackModel]
  - query_by_type(feedback_type: str) -> List[FeedbackModel]
  - query_by_date_range(start: datetime, end: datetime) -> List[FeedbackModel]
- Error handling specifications
- Transaction support interface""",
            "priority": "high",
            "details": "Tags: feedback-storage, interface, implementation, opus-manager-review"
        },
        {
            "title": "Implement JSON file storage backend",
            "description": """Create storage_backends/json_backend.py with:
- JSONFeedbackStorage implementing FeedbackStorageInterface
- File-based storage in .taskmaster/feedback/ directory
- Atomic write operations with file locking
- Index files for efficient querying:
  - task_index.json (task_id -> feedback_ids mapping)
  - type_index.json (type -> feedback_ids mapping)
  - date_index.json (date -> feedback_ids mapping)
- Backup and recovery mechanisms
- Thread-safe operations
- Configurable storage path""",
            "priority": "high",
            "details": "Tags: feedback-storage, json-backend, implementation, opus-manager-review"
        },
        {
            "title": "Implement SQLite storage backend",
            "description": """Create storage_backends/sqlite_backend.py with:
- SQLiteFeedbackStorage implementing FeedbackStorageInterface
- Database schema:
  CREATE TABLE feedback (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    feedback_type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_type (feedback_type),
    INDEX idx_created (created_at)
  )
- Connection pooling
- Migration support
- Transaction management
- Prepared statements for security""",
            "priority": "high",
            "details": "Tags: feedback-storage, sqlite-backend, implementation, opus-manager-review"
        },
        {
            "title": "Create storage factory and configuration",
            "description": """Create feedback_storage_factory.py with:
- StorageFactory class with get_storage(backend_type: str) method
- Configuration loading from orchestrator_config.json:
  {
    'feedback_storage': {
      'backend': 'json' | 'sqlite',
      'json_path': '.taskmaster/feedback/',
      'sqlite_path': '.taskmaster/feedback.db'
    }
  }
- Singleton pattern for storage instances
- Backend switching without data loss
- Migration utilities between backends""",
            "priority": "medium",
            "details": "Tags: feedback-storage, factory, configuration, opus-manager-review"
        },
        {
            "title": "Integrate storage with existing feedback collection",
            "description": """Update existing feedback collection code to use storage:
- Modify feedback collection points to persist data
- Add storage calls to task completion workflow
- Update worker feedback submission
- Add feedback retrieval to task context
- Ensure non-blocking storage operations
- Add error handling and retry logic""",
            "priority": "high",
            "details": "Tags: feedback-storage, integration, opus-manager-review"
        },
        {
            "title": "Create comprehensive storage tests",
            "description": """Create test_feedback_storage.py in tests/ with:
- Unit tests for FeedbackModel validation
- Interface compliance tests for both backends
- CRUD operation tests
- Query method tests
- Concurrent access tests
- Performance benchmarks
- Error handling tests
- Migration tests
- Mock implementations for testing""",
            "priority": "high",
            "details": "Tags: feedback-storage, testing, opus-manager-review"
        },
        {
            "title": "Add CLI commands for feedback management",
            "description": """Extend task_master.py with feedback commands:
- feedback add --task-id ID --type TYPE --content JSON
- feedback list [--task-id ID] [--type TYPE] [--since DATE]
- feedback get FEEDBACK_ID
- feedback update FEEDBACK_ID --content JSON
- feedback delete FEEDBACK_ID
- feedback export --format json|csv
- feedback import FILE
- Add feedback summary to task show command""",
            "priority": "medium",
            "details": "Tags: feedback-storage, cli, opus-manager-review"
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
    
    print(f"\n📋 Created {len(created_task_ids)} implementation tasks for Task 15 feedback storage backend")
    return created_task_ids

if __name__ == "__main__":
    create_storage_implementation_tasks()