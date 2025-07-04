#!/usr/bin/env python3
"""
Example of adding a task using the TaskManager Python API directly
"""

from claude_orchestrator.task_master import TaskManager

def main():
    # Initialize the task manager
    tm = TaskManager()
    
    # Example 1: Add a simple task
    print("Adding a simple task...")
    task1 = tm.add_task(
        title="Implement user authentication with JWT tokens",
        description="Add JWT-based authentication to secure API endpoints"
    )
    print(f"✅ Added task {task1.id}: {task1.title}")
    
    # Example 2: Add a task with more details
    print("\nAdding a detailed task...")
    task2 = tm.add_task(
        title="Create database migration system",
        description="Implement a database migration system for schema version control",
        priority="high",
        details="Use Alembic for migrations, support both upgrade and downgrade operations",
        testStrategy="Unit tests for migration scripts, integration tests with test database"
    )
    print(f"✅ Added task {task2.id}: {task2.title}")
    print(f"   Priority: {task2.priority}")
    print(f"   Details: {task2.details}")
    
    # Example 3: Add a task with dependencies
    print("\nAdding a task with dependencies...")
    task3 = tm.add_task(
        title="Add user profile endpoints",
        description="Create REST endpoints for user profile management",
        dependencies=[task1.id],  # Depends on authentication being implemented first
        priority="medium"
    )
    print(f"✅ Added task {task3.id}: {task3.title}")
    print(f"   Depends on task: {task3.dependencies}")
    
    # Show current task list
    print("\n" + "="*60)
    print("Current task list:")
    print("="*60)
    
    tasks = tm.get_all_tasks()
    for task in tasks[-3:]:  # Show last 3 tasks added
        print(f"\nTask {task.id}: {task.title}")
        print(f"  Status: {task.status}")
        print(f"  Priority: {task.priority}")
        if task.dependencies:
            print(f"  Dependencies: {task.dependencies}")
    
    # Get next task to work on
    print("\n" + "="*60)
    print("Next task to work on:")
    print("="*60)
    
    next_task = tm.get_next_task()
    if next_task:
        print(f"\nTask {next_task.id}: {next_task.title}")
        print(f"  Priority: {next_task.priority}")
        print(f"  Description: {next_task.description}")
    else:
        print("\nNo tasks available (all might have unmet dependencies)")

if __name__ == "__main__":
    main()