#!/usr/bin/env python3
"""Add follow-up tasks for worker allocation feedback integration"""

import json
import os
from datetime import datetime
from pathlib import Path

def add_tasks():
    """Add follow-up tasks for worker allocation feedback integration"""
    
    # Load existing tasks
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Get the highest task ID (handle both int and string IDs)
    task_ids = []
    for task in data['tasks']:
        task_id = task['id']
        if isinstance(task_id, str):
            # Try to extract numeric part from string IDs
            try:
                task_ids.append(int(task_id))
            except ValueError:
                # Skip non-numeric IDs
                continue
        else:
            task_ids.append(task_id)
    
    max_id = max(task_ids) if task_ids else 18
    
    # Define new tasks
    new_tasks = [
        {
            "id": max_id + 1,
            "title": "Implement Feedback Collection in release_worker()",
            "description": "Add feedback collection to worker allocation release_worker() method to capture task completion feedback",
            "status": "pending",
            "dependencies": [],
            "priority": "high",
            "details": "Modify the release_worker() method in dynamic_worker_allocation.py to:\n- Accept feedback parameter with quality metrics, issues, suggestions\n- Store feedback with allocation history\n- Update worker performance metrics with feedback data\n- Ensure backward compatibility",
            "testStrategy": "Unit tests for feedback parameter handling, integration tests for feedback storage",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["feedback", "worker-allocation"]
        },
        {
            "id": max_id + 2,
            "title": "Create Feedback Data Model for Worker Allocation",
            "description": "Define structured feedback model specific to worker allocation performance",
            "status": "pending",
            "dependencies": [],
            "priority": "high",
            "details": "Create data classes/models for:\n- Task completion feedback (quality score, issues encountered)\n- Worker performance feedback\n- Allocation effectiveness metrics\n- Integration with existing WorkerPerformance tracking",
            "testStrategy": "Unit tests for data model validation and serialization",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["feedback", "data-model", "worker-allocation"]
        },
        {
            "id": max_id + 3,
            "title": "Integrate Feedback into Worker Suitability Scoring",
            "description": "Use historical feedback to improve worker allocation decisions",
            "status": "pending",
            "dependencies": [max_id + 1, max_id + 2],
            "priority": "medium",
            "details": "Enhance calculate_suitability_score() to:\n- Consider historical feedback for similar tasks\n- Adjust specialization bonuses based on feedback\n- Implement learning mechanism from feedback patterns\n- Add feedback-based worker reputation scoring",
            "testStrategy": "Unit tests with mock feedback data, A/B testing allocation improvements",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["feedback", "machine-learning", "worker-allocation"]
        },
        {
            "id": max_id + 4,
            "title": "Add Feedback Storage to Allocation History",
            "description": "Persist feedback data with allocation history for analysis",
            "status": "pending",
            "dependencies": [max_id + 2],
            "priority": "medium",
            "details": "Modify allocation_history in dynamic_worker_allocation.py to:\n- Include feedback field in AllocationRecord\n- Implement feedback retrieval methods\n- Add feedback aggregation utilities\n- Ensure efficient storage and retrieval",
            "testStrategy": "Integration tests for feedback persistence and retrieval",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["feedback", "storage", "worker-allocation"]
        },
        {
            "id": max_id + 5,
            "title": "Create Feedback Collection UI/API for Worker Tasks",
            "description": "Implement interface for collecting feedback after task completion",
            "status": "pending",
            "dependencies": [max_id + 1],
            "priority": "medium",
            "details": "Create mechanisms to:\n- Prompt for feedback after task completion\n- Validate feedback input\n- Handle async feedback submission\n- Integrate with worker pool manager's complete_task()",
            "testStrategy": "API tests for feedback endpoints, UI tests for feedback forms",
            "subtasks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "tags": ["feedback", "api", "ui", "worker-allocation"]
        }
    ]
    
    # Add new tasks
    data['tasks'].extend(new_tasks)
    
    # Write back to file
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Added {len(new_tasks)} follow-up tasks for worker allocation feedback integration")
    for task in new_tasks:
        print(f"  - Task {task['id']}: {task['title']} [Priority: {task['priority']}]")

if __name__ == "__main__":
    add_tasks()