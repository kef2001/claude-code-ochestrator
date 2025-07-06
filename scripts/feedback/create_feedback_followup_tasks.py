#!/usr/bin/env python3
"""
Create follow-up tasks for the missing Core Feedback Collection Module implementation
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

# Define minimal Task structure for creating tasks
TASKS_FILE = ".taskmaster/tasks/tasks.json"

def add_task_directly(prompt, priority="medium", metadata=None):
    """Add a task directly to the tasks.json file"""
    # Ensure tasks file exists
    tasks_path = Path(TASKS_FILE)
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing tasks
    if tasks_path.exists():
        with open(tasks_path, 'r') as f:
            data = json.load(f)
            tasks = data.get('tasks', [])
    else:
        tasks = []
    
    # Find next ID (handle both string and int IDs)
    task_ids = []
    for t in tasks:
        task_id = t.get('id', 0)
        if isinstance(task_id, str) and task_id.isdigit():
            task_ids.append(int(task_id))
        elif isinstance(task_id, int):
            task_ids.append(task_id)
    next_id = max(task_ids, default=0) + 1
    
    # Create new task
    new_task = {
        "id": next_id,
        "title": prompt.split('.')[0][:100],  # First sentence as title
        "description": prompt,
        "status": "pending",
        "priority": priority,
        "dependencies": [],
        "subtasks": [],
        "metadata": metadata or {},
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat()
    }
    
    tasks.append(new_task)
    
    # Save tasks
    with open(tasks_path, 'w') as f:
        json.dump({"tasks": tasks}, f, indent=2)
    
    return new_task

def main():
    # Follow-up tasks for the Core Feedback Collection Module
    tasks = [
        {
            "title": "Implement Core FeedbackCollector Module",
            "prompt": "Create claude_orchestrator/feedback_collector.py with FeedbackCollector class that handles feedback collection at decision points. Include methods for: collect_feedback(), store_feedback(), retrieve_feedback(), and aggregate_feedback(). Ensure proper error handling and logging.",
            "priority": "high",
            "tags": ["followup-task-3", "feedback-system", "core-implementation"]
        },
        {
            "title": "Create Feedback Data Models",
            "prompt": "Design and implement data models for feedback storage. Create FeedbackEntry dataclass with fields: id, task_id, timestamp, feedback_type, content, metadata, and user_id. Add validation and serialization methods.",
            "priority": "high",
            "tags": ["followup-task-3", "feedback-system", "data-models"]
        },
        {
            "title": "Implement Feedback Storage Backend",
            "prompt": "Create a storage backend for feedback data. Implement both JSON file-based storage and preparation for database integration. Include methods for CRUD operations and querying feedback by various criteria.",
            "priority": "medium",
            "tags": ["followup-task-3", "feedback-system", "storage"]
        },
        {
            "title": "Add Feedback Integration Points",
            "prompt": "Integrate feedback collection into existing decision points in the orchestrator. Add hooks in task execution, evaluation, and review processes to collect structured feedback.",
            "priority": "medium",
            "tags": ["followup-task-3", "feedback-system", "integration"]
        },
        {
            "title": "Create Unit Tests for Feedback Module",
            "prompt": "Write comprehensive unit tests for the FeedbackCollector module. Test all CRUD operations, error handling, data validation, and integration points. Ensure 90%+ code coverage.",
            "priority": "medium",
            "tags": ["followup-task-3", "feedback-system", "testing"]
        }
    ]
    
    created_tasks = []
    for task_data in tasks:
        task = add_task_directly(
            prompt=task_data["prompt"],
            priority=task_data["priority"],
            metadata={
                "created_by": "opus-manager-review",
                "parent_task": "task-3-feedback-collection",
                "tags": task_data["tags"]
            }
        )
        created_tasks.append(task)
        print(f"Created task {task['id']}: {task_data['title']}")
    
    print(f"\nCreated {len(created_tasks)} follow-up tasks for Core Feedback Collection Module implementation")
    print("These tasks address the missing implementation noted in the review.")

if __name__ == "__main__":
    main()