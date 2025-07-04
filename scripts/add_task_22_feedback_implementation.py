#!/usr/bin/env python3
"""Add follow-up tasks for implementing feedback storage in allocation history."""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_orchestrator.task_master import TaskManager
from claude_orchestrator.models import Task, TaskType, TaskStatus, TaskPriority


def main():
    """Add follow-up tasks for feedback storage implementation."""
    tm = TaskManager()
    
    tasks = [
        {
            "title": "Implement feedback parameter in DynamicWorkerAllocator.release_worker()",
            "description": "Add feedback parameter to release_worker() method to accept and store feedback data with allocation history records",
            "priority": "high",
            "details": """Requirements:
- Modify release_worker() method signature to accept optional feedback parameter
- Add feedback field to allocation history record structure
- Store feedback data when provided during worker release
- Ensure backward compatibility for existing calls without feedback
- Add type hints for feedback structure (dict or dataclass)""",
            "complexity": 3,
            "estimated_hours": 2
        },
        {
            "type": TaskType.CODING,
            "title": "Add feedback field to allocation history records",
            "description": "Modify allocation history data structure to include feedback field and ensure proper storage",
            "priority": TaskPriority.HIGH,
            "tags": ["implementation", "feedback", "data-structure", "followup", "opus-manager-review"],
            "details": """Requirements:
- Add 'feedback' field to allocation history dictionary
- Define feedback data structure (quality score, issues, suggestions)
- Update all places where allocation records are created
- Ensure existing code continues to work with new field
- Add validation for feedback data format""",
            "complexity": 2,
            "estimated_hours": 1.5
        },
        {
            "type": TaskType.CODING,
            "title": "Create persistence mechanism for allocation history",
            "description": "Implement file-based or database persistence for allocation history including feedback data",
            "priority": TaskPriority.MEDIUM,
            "tags": ["implementation", "persistence", "storage", "followup"],
            "details": """Requirements:
- Design storage format (JSON, SQLite, or other)
- Implement save_history() method to persist data
- Implement load_history() method to restore data
- Add configuration for storage location
- Handle migration from in-memory to persistent storage
- Add periodic auto-save functionality""",
            "complexity": 4,
            "estimated_hours": 3
        },
        {
            "type": TaskType.CODING,
            "title": "Implement feedback-based worker scoring improvements",
            "description": "Use historical feedback data to improve worker suitability scoring and allocation decisions",
            "priority": TaskPriority.MEDIUM,
            "tags": ["implementation", "feedback", "scoring", "followup"],
            "details": """Requirements:
- Analyze historical feedback for worker performance patterns
- Update calculate_suitability_score() to consider feedback
- Weight recent feedback more heavily than old feedback
- Consider feedback quality metrics in scoring
- Add configuration for feedback influence on scoring
- Create feedback aggregation methods""",
            "complexity": 4,
            "estimated_hours": 3
        }
    ]
    
    # Add all tasks
    for task_data in tasks:
        task = Task(**task_data)
        tm.add_task(task)
        print(f"Added task: {task.title}")
    
    print(f"\nSuccessfully added {len(tasks)} follow-up tasks for feedback storage implementation")


if __name__ == "__main__":
    main()