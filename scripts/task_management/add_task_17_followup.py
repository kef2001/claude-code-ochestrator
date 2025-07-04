#!/usr/bin/env python3
"""
Script to add follow-up task for Task 17 SQL Schema Design
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path


def add_task():
    # Load existing tasks
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    
    if not tasks_file.exists():
        print(f"Tasks file not found: {tasks_file}")
        return
    
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Generate a new UUID for the task
    new_id = str(uuid.uuid4())
    
    # Create new task
    new_task = {
        "id": new_id,
        "title": "Create SQL Schema for Feedback Storage",
        "description": "Create SQL schema for feedback storage system with the following tables: 1) feedback table with columns: id (primary key), user_id, feedback_type, message, rating, created_at, updated_at, status. 2) feedback_categories table with columns: id, name, description. 3) feedback_responses table with columns: id, feedback_id (foreign key), responder_id, response_text, created_at. Include proper data types, constraints, indexes, and foreign key relationships.",
        "status": "pending",
        "priority": "high",
        "tags": ["database", "sql", "schema", "feedback"],
        "subtasks": [],
        "dependencies": ["17"],  # Depends on the failed design task
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "prompt": "Create SQL schema for feedback storage system with the following tables: 1) feedback table with columns: id (primary key), user_id, feedback_type, message, rating, created_at, updated_at, status. 2) feedback_categories table with columns: id, name, description. 3) feedback_responses table with columns: id, feedback_id (foreign key), responder_id, response_text, created_at. Include proper data types, constraints, indexes, and foreign key relationships."
    }
    
    # Add to tasks list
    data['tasks'].append(new_task)
    
    # Update metadata
    data['metadata']['lastUpdated'] = datetime.now().isoformat()
    data['metadata']['totalTasks'] = len(data['tasks'])
    
    # Save back to file
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Successfully added follow-up task ID: {new_task['id']}")
    print(f"Title: {new_task['title']}")
    print(f"Priority: {new_task['priority']}")


if __name__ == "__main__":
    add_task()