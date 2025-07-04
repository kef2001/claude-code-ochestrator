#!/usr/bin/env python3
"""
Add follow-up tasks for Task 3: Core Feedback Collection Module
"""

import json
from pathlib import Path
from datetime import datetime

# Define follow-up tasks based on the review
followup_tasks = [
    {
        "title": "Implement Core Feedback Collection Module with actual code",
        "description": "Create the feedback_collector.py module with complete implementation",
        "priority": "high",
        "details": """Implementation requirements:
- Create claude_orchestrator/feedback_collector.py
- Implement FeedbackCollector class with core methods
- Add feedback collection at decision points
- Include structured feedback storage (JSON/SQLite)
- Implement feedback validation and sanitization
- Add error handling for collection failures"""
    },
    {
        "title": "Create feedback data models and storage schema",
        "description": "Define data structures for storing feedback efficiently",
        "priority": "high",
        "details": """Data model requirements:
- Define FeedbackEntry dataclass/model
- Create schema for feedback storage
- Include fields: timestamp, task_id, decision_point, feedback_type, content, metadata
- Add indexing for efficient retrieval
- Support both structured and unstructured feedback"""
    },
    {
        "title": "Write comprehensive unit tests for feedback module",
        "description": "Create tests/test_feedback_collector.py with full test coverage",
        "priority": "medium",
        "details": """Test requirements:
- Test feedback collection functionality
- Test storage and retrieval operations
- Test error handling scenarios
- Test feedback validation
- Test integration with orchestrator
- Aim for >90% code coverage"""
    },
    {
        "title": "Add feedback integration points in orchestrator",
        "description": "Integrate feedback collection into EnhancedOrchestrator decision points",
        "priority": "medium",
        "details": """Integration requirements:
- Add feedback hooks in task execution flow
- Collect feedback at key decision points
- Store feedback with appropriate context
- Make feedback available for analysis
- Add configuration for feedback collection"""
    }
]

# Load existing tasks
tasks_file = Path(".taskmaster/tasks/tasks.json")
with open(tasks_file, 'r') as f:
    tasks_data = json.load(f)

# Find next task ID
next_id = max([t.get('id', 0) for t in tasks_data['tasks']], default=0) + 1

# Add new tasks
for i, task in enumerate(followup_tasks):
    new_task = {
        "id": next_id + i,
        "title": task["title"],
        "description": task["description"],
        "status": "pending",
        "dependencies": [],
        "priority": task["priority"],
        "details": task["details"],
        "subtasks": [],
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "tags": ["feedback", "task-3-followup"]
    }
    tasks_data['tasks'].append(new_task)
    print(f"Created task {next_id + i}: {task['title']}")

# Update metadata
tasks_data['meta']['updatedAt'] = datetime.now().isoformat()

# Save updated tasks
with open(tasks_file, 'w') as f:
    json.dump(tasks_data, f, indent=2)

print(f"\nSuccessfully created {len(followup_tasks)} follow-up tasks for Task 3 review.")