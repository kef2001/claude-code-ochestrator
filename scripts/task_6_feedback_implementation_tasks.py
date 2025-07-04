#!/usr/bin/env python3
"""
Script to create follow-up tasks for properly implementing feedback collection
in the task completion workflow.
"""

import subprocess
import json

def add_task(prompt, priority="medium", dependencies=None):
    """Add a task using the task-master CLI"""
    cmd = [
        "python3", "-m", "claude_orchestrator.main",
        "--task-master", "add-task",
        "--prompt", prompt,
        "--priority", priority
    ]
    
    if dependencies:
        cmd.extend(["--dependencies", ",".join(map(str, dependencies))])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✓ Added task: {prompt[:50]}...")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to add task: {e}")
        print(f"  Error: {e.stderr}")
        return None

# Core implementation tasks
tasks = [
    {
        "prompt": "Implement FeedbackCollector class with methods: collect_feedback(), store_feedback(), retrieve_feedback(), and aggregate_feedback() in claude_orchestrator/feedback_collector.py",
        "priority": "high"
    },
    {
        "prompt": "Create SQLite database schema and storage backend for feedback data including tables for: feedback entries, task associations, ratings, and metadata",
        "priority": "high"
    },
    {
        "prompt": "Integrate feedback collection into task completion workflow in main.py - add feedback prompt after task completion and before Opus review",
        "priority": "high"
    },
    {
        "prompt": "Add CLI commands for feedback operations: view-feedback, export-feedback, and feedback-stats to the task-master interface",
        "priority": "medium"
    },
    {
        "prompt": "Create unit tests for FeedbackCollector class covering all methods and edge cases",
        "priority": "medium"
    },
    {
        "prompt": "Add feedback configuration options to orchestrator_config.json including: feedback types, rating scales, and storage settings",
        "priority": "medium"
    },
    {
        "prompt": "Implement feedback analytics and reporting functionality to track feedback trends and task quality metrics",
        "priority": "low"
    },
    {
        "prompt": "Add feedback UI components for better user experience when providing feedback",
        "priority": "low"
    }
]

print("Creating follow-up tasks for feedback collection implementation...")
print("=" * 60)

for task in tasks:
    add_task(**task)

print("\nAll follow-up tasks created successfully!")
print("\nTo execute these tasks, run:")
print("python3 -m claude_orchestrator.main")