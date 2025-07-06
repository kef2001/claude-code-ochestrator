#!/usr/bin/env python3
"""
Create follow-up tasks for Task 16: Feedback Collection Integration
Based on review findings that the feedback system is completely missing
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from claude_orchestrator.task_master import TaskManager

def main():
    """Create follow-up tasks for feedback collection implementation"""
    try:
        task_master = TaskManager()
        
        # Define the follow-up tasks based on review findings
        tasks = [
            {
                "prompt": "Implement core FeedbackCollector class with collect_feedback(), store_feedback(), and retrieve_feedback() methods in claude_orchestrator/feedback_collector.py",
                "priority": "high",
                "tags": ["feedback", "implementation", "core"],
                "parent_task_id": 16
            },
            {
                "prompt": "Create SQLite storage backend for feedback persistence with schema: task_id, worker_id, feedback_type, content (JSON), rating, timestamps, metadata",
                "priority": "high",
                "tags": ["feedback", "storage", "database"],
                "parent_task_id": 16
            },
            {
                "prompt": "Add feedback collection hooks to task execution flow in main.py - integrate at pre-task, post-task, and error handling points",
                "priority": "high",
                "tags": ["feedback", "integration", "execution"],
                "parent_task_id": 16
            },
            {
                "prompt": "Integrate feedback collection with EvaluatorOptimizer - persist evaluation feedback and add retrieval methods for optimization cycles",
                "priority": "medium",
                "tags": ["feedback", "evaluation", "optimization"],
                "parent_task_id": 16
            },
            {
                "prompt": "Add feedback collection to task review processes - implement hooks in task completion, validation, and checkpoint creation",
                "priority": "medium",
                "tags": ["feedback", "review", "validation"],
                "parent_task_id": 16
            },
            {
                "prompt": "Create feedback configuration in orchestrator_config.json - add feedback_enabled flag, storage_type, collection_points, and rating_scale options",
                "priority": "medium",
                "tags": ["feedback", "configuration"],
                "parent_task_id": 16
            },
            {
                "prompt": "Implement CLI commands for feedback management: list-feedback, export-feedback, analyze-feedback, and clear-feedback",
                "priority": "low",
                "tags": ["feedback", "cli", "tools"],
                "parent_task_id": 16
            },
            {
                "prompt": "Create comprehensive test suite for feedback system - unit tests for FeedbackCollector, integration tests for hooks, and storage tests",
                "priority": "medium",
                "tags": ["feedback", "testing"],
                "parent_task_id": 16
            }
        ]
        
        created_tasks = []
        
        for task_config in tasks:
            try:
                # Extract title from prompt (first 80 chars)
                title = task_config["prompt"][:80]
                if len(task_config["prompt"]) > 80:
                    title += "..."
                
                task = task_master.add_task(
                    title=title,
                    description=task_config["prompt"],
                    priority=task_config["priority"],
                    details=json.dumps({
                        "tags": task_config.get("tags", []),
                        "parent_task_id": task_config.get("parent_task_id"),
                        "created_by": "task_16_review",
                        "category": "feedback_implementation"
                    })
                )
                task_id = task.id
                created_tasks.append({
                    "id": task_id,
                    "title": task_config["prompt"][:80] + "...",
                    "priority": task_config["priority"]
                })
                print(f"✓ Created task {task_id}: {task_config['prompt'][:60]}...")
            except Exception as e:
                print(f"✗ Failed to create task: {e}")
        
        print(f"\n✅ Successfully created {len(created_tasks)} follow-up tasks for feedback implementation")
        
        # Summary
        print("\nTask Summary:")
        print("-" * 80)
        for task in created_tasks:
            print(f"Task {task['id']} [{task['priority']}]: {task['title']}")
        
    except Exception as e:
        print(f"Error creating follow-up tasks: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()