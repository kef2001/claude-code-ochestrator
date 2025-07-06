#!/usr/bin/env python3
"""
Add follow-up tasks for actual feedback storage implementation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import TaskMaster directly to avoid the requests dependency
import importlib.util
spec = importlib.util.spec_from_file_location("task_master", "claude_orchestrator/task_master.py")
task_master_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task_master_module)
TaskManager = task_master_module.TaskManager

def main():
    """Add tasks for implementing the feedback storage system"""
    task_master = TaskManager()
    
    # Task 1: Create feedback_storage.py module
    task_1 = task_master.add_task(
        title="Create feedback_storage.py module with SQLite implementation",
        description="""Create the core feedback storage module with the following components:
1. Database connection setup with connection pooling
2. Schema creation with feedback table containing:
   - id (primary key)
   - task_id (foreign key)
   - worker_id (string)
   - feedback_type (enum: SUCCESS, ERROR, WARNING, INFO)
   - content (JSON text)
   - timestamp (datetime)
   - metadata (JSON text)
3. CRUD operations:
   - store_feedback(task_id, worker_id, feedback_type, content, metadata)
   - get_feedback(feedback_id)
   - update_feedback(feedback_id, updates)
   - delete_feedback(feedback_id)
4. Query methods:
   - get_feedback_by_task(task_id)
   - get_feedback_by_worker(worker_id)
   - get_feedback_by_type(feedback_type)
5. Proper error handling and logging
6. Thread-safe operations for concurrent access""",
        priority="high"
    )
    
    # Task 2: Create unit tests
    task_2 = task_master.add_task(
        title="Create comprehensive unit tests for feedback_storage module",
        description="""Create test_feedback_storage.py with tests for:
1. Database connection and schema creation
2. All CRUD operations
3. Query methods with various filters
4. Error handling scenarios
5. Concurrent access tests
6. Data validation tests
7. Edge cases (empty data, invalid types, etc.)""",
        priority="high",
        subtasks=[
            {"title": "Test database operations", "description": "Test connection, schema creation, and basic operations"},
            {"title": "Test CRUD operations", "description": "Test all create, read, update, delete operations"},
            {"title": "Test query methods", "description": "Test filtering and retrieval methods"},
            {"title": "Test error handling", "description": "Test various error scenarios"},
            {"title": "Test concurrent access", "description": "Test thread safety"}
        ]
    )
    
    # Task 3: Create integration with main orchestrator
    task_3 = task_master.add_task(
        title="Integrate feedback storage with main orchestrator",
        description="""Modify claude_orchestrator/main.py to:
1. Import and initialize feedback_storage module
2. Store feedback after each task execution
3. Add API endpoints for feedback retrieval
4. Add feedback summary to task completion reports
5. Ensure proper error handling if storage fails""",
        priority="medium",
        dependencies=[task_1.id]
    )
    
    # Task 4: Create feedback analysis utilities
    task_4 = task_master.add_task(
        title="Create feedback analysis utilities",
        description="""Create feedback_analyzer.py with utilities for:
1. Aggregate feedback statistics by task/worker
2. Identify common error patterns
3. Generate feedback reports
4. Export feedback data to CSV/JSON
5. Performance metrics based on feedback""",
        priority="medium",
        dependencies=[task_1.id]
    )
    
    # Task 5: Documentation
    task_5 = task_master.add_task(
        title="Create documentation for feedback storage system",
        description="""Create comprehensive documentation including:
1. API documentation for all storage methods
2. Database schema documentation
3. Usage examples
4. Integration guide
5. Troubleshooting guide""",
        priority="low",
        dependencies=[task_1.id, task_2.id]
    )
    
    print(f"✅ Added 5 tasks for feedback storage implementation")
    print(f"Task IDs: {task_1.id}, {task_2.id}, {task_3.id}, {task_4.id}, {task_5.id}")

if __name__ == "__main__":
    main()