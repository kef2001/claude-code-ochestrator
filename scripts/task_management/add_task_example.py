#!/usr/bin/env python3
"""
Example of how to add a task using the claude-orchestrator CLI
"""

import subprocess
import sys

def add_task_example():
    """
    This script demonstrates how to add a new task to the orchestrator.
    
    The task-master functionality mentioned in the README is actually
    integrated into the claude-orchestrator command itself.
    """
    
    # The task description
    task_description = "Implement user authentication with JWT tokens"
    
    # Method 1: Using the full command name
    print("Method 1: Using claude-orchestrator add")
    cmd1 = ['claude-orchestrator', 'add', task_description]
    print(f"Command: {' '.join(cmd1)}")
    
    # Method 2: Using the short alias 'co'
    print("\nMethod 2: Using co add (short alias)")
    cmd2 = ['co', 'add', task_description]
    print(f"Command: {' '.join(cmd2)}")
    
    # Method 3: Adding a task with priority
    print("\nMethod 3: Adding with priority (using direct TaskManager)")
    print("This requires using the Python API directly:")
    print("""
from claude_orchestrator.task_master import TaskManager

# Initialize task manager
tm = TaskManager()

# Add a task with priority
task = tm.add_task(
    title="Implement user authentication with JWT tokens",
    description="Add JWT-based authentication to the API endpoints",
    priority="high",
    details="Use PyJWT library for token generation and validation"
)

print(f"Added task {task.id}: {task.title}")
""")
    
    print("\n" + "="*60)
    print("Available commands for task management:")
    print("="*60)
    print()
    print("# List all tasks")
    print("co list")
    print()
    print("# List only pending tasks")
    print("co list --filter-status pending")
    print()
    print("# Show details of a specific task")
    print("co show 1")
    print()
    print("# Get the next task to work on")
    print("co next")
    print()
    print("# Update task status")
    print("co update 1 --status in-progress")
    print()
    print("# Expand a task into subtasks with AI research")
    print("co expand 1 --research")
    print()
    print("# Delete a task")
    print("co delete 1")
    print()
    print("# Run the orchestrator to execute tasks")
    print("co run")
    print()
    print("# Parse a requirements file to create tasks")
    print("co parse requirements.txt")

if __name__ == "__main__":
    add_task_example()