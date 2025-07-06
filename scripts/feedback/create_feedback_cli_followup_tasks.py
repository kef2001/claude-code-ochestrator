#!/usr/bin/env python3
"""Create follow-up tasks for implementing feedback analysis CLI commands."""

import json
import uuid
from datetime import datetime
from pathlib import Path

# Tasks to create
tasks = [
    {
        "prompt": "Implement 'analyze-feedback <task-id>' CLI command in main.py to analyze specific task feedback with detailed metrics and insights. The command should parse task ID argument, fetch task data from .taskmaster/tasks/tasks.json, analyze feedback if present, and display comprehensive metrics.",
        "priority": "high",
        "tags": ["cli", "feedback", "analysis", "followup"]
    },
    {
        "prompt": "Implement 'worker-performance' CLI command in main.py to show worker performance metrics. The command should aggregate all task data, calculate per-worker statistics (success rate, avg completion time, task count), and display results in a formatted table.",
        "priority": "high", 
        "tags": ["cli", "feedback", "metrics", "followup"]
    },
    {
        "prompt": "Implement 'feedback-report' CLI command in main.py for comprehensive feedback analysis report. The command should analyze all tasks with feedback, identify patterns and trends, generate summary statistics, and output a detailed report.",
        "priority": "medium",
        "tags": ["cli", "feedback", "report", "followup"]
    },
    {
        "prompt": "Implement 'export-metrics' CLI command in main.py to export feedback analysis data. The command should support multiple formats (JSON, CSV), include all relevant metrics and analysis, and save to specified output file.",
        "priority": "medium",
        "tags": ["cli", "feedback", "export", "followup"]
    }
]

# Load existing tasks
tasks_file = Path(__file__).parent.parent / ".taskmaster" / "tasks" / "tasks.json"
with open(tasks_file, 'r') as f:
    data = json.load(f)

# Add new tasks
next_id = len(data["tasks"]) + 1
for task in tasks:
    task_data = {
        "id": next_id,
        "title": task["prompt"][:80] + "..." if len(task["prompt"]) > 80 else task["prompt"],
        "description": task["prompt"],
        "status": "pending",
        "dependencies": [],
        "priority": task["priority"],
        "tags": task["tags"],
        "parent_task_id": "558bddab-449a-4186-8641-4a913de4ed88",  # Original task ID
        "created_by": "opus-manager-review",
        "estimated_time": 30,
        "actual_time": None,
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "completed_at": None,
        "assigned_to": None,
        "output": None
    }
    data["tasks"].append(task_data)
    print(f"Created task {next_id}: {task['prompt'][:80]}...")
    next_id += 1

# Update meta
data["meta"]["totalTasks"] = len(data["tasks"])
data["meta"]["pendingTasks"] = sum(1 for t in data["tasks"] if t["status"] == "pending")
data["meta"]["completedTasks"] = sum(1 for t in data["tasks"] if t["status"] == "done")
data["meta"]["updatedAt"] = datetime.now().isoformat()

# Save updated tasks
with open(tasks_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"\nSuccessfully created {len(tasks)} follow-up tasks for feedback CLI implementation.")