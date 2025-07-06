#!/usr/bin/env python3
"""
Add tasks for RollbackManager implementation
"""

import uuid
from claude_orchestrator.task_master import TaskManager

def main():
    tm = TaskManager()
    
    # Task 1: Implement RollbackManager class
    task1_id = tm.add_task(
        title="Implement RollbackManager class with state capture and restoration",
        description="Create the core RollbackManager class with methods for capturing and restoring system state during TaskMaster operations",
        priority="high",
        task_id=str(uuid.uuid4())
    )
    print(f"Created task {task1_id}: Implement RollbackManager class")
    
    # Task 2: Create integration tests
    task2_id = tm.add_task(
        title="Create integration tests for RollbackManager with TaskMaster",
        description="Write comprehensive integration tests that verify state capture and restoration works correctly during various TaskMaster operations",
        priority="high",
        task_id=str(uuid.uuid4())
    )
    print(f"Created task {task2_id}: Create integration tests")
    
    # Task 3: Create test directory structure
    task3_id = tm.add_task(
        title="Create test directory structure and pytest configuration",
        description="Set up proper test directory structure (tests/) with pytest configuration and test utilities for the project",
        priority="medium",
        task_id=str(uuid.uuid4())
    )
    print(f"Created task {task3_id}: Create test directory structure")
    
    # Task 4: Document RollbackManager usage
    task4_id = tm.add_task(
        title="Document RollbackManager API and usage patterns",
        description="Create comprehensive documentation for RollbackManager including API reference, usage examples, and integration guide",
        priority="medium",
        task_id=str(uuid.uuid4())
    )
    print(f"Created task {task4_id}: Document RollbackManager")
    
    print("\nAll tasks created successfully!")
    
if __name__ == "__main__":
    main()