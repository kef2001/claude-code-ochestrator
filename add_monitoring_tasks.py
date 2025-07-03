#!/usr/bin/env python3
"""Script to add monitoring follow-up tasks"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# Define the follow-up tasks
tasks = [
    {
        "title": "Create Monitoring Module",
        "description": "Create a dedicated monitoring module (monitoring_system.py) that collects metrics for feature usage tracking. Should include: 1) MetricsCollector class to track feature flag usage, 2) Integration with FeatureFlags to record when flags are checked, 3) Counters for how many times each feature is accessed",
        "priority": "high",
        "status": "pending"
    },
    {
        "title": "Add Error Metrics Collection",
        "description": "Extend the monitoring module to collect error metrics. Should include: 1) ErrorMetrics class to track different types of errors, 2) Integration with claude_error_handler.py to automatically record errors, 3) Error categorization (validation, execution, timeout, etc.), 4) Error frequency tracking",
        "priority": "high",
        "status": "pending"
    },
    {
        "title": "Create Metrics Dashboard",
        "description": "Create a simple metrics dashboard or reporting functionality that displays: 1) Feature usage statistics, 2) Error rates and trends, 3) Task execution metrics from ExecutionTracer, 4) Export functionality to JSON/CSV for analysis",
        "priority": "medium",
        "status": "pending"
    },
    {
        "title": "Add Metrics Persistence",
        "description": "Implement metrics persistence to store historical data. Should include: 1) SQLite storage for metrics data, 2) Automatic rollup/aggregation for older data, 3) Configurable retention policies, 4) Migration from in-memory to persistent storage",
        "priority": "medium",
        "status": "pending"
    }
]

# Create task files
taskmaster_dir = Path(".taskmaster")
taskmaster_dir.mkdir(exist_ok=True)

# Add tasks
for i, task in enumerate(tasks, start=29):
    task_data = {
        "id": str(i),
        "title": task["title"],
        "description": task["description"],
        "status": task["status"],
        "priority": task["priority"],
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "tags": ["monitoring", "metrics", "follow-up"],
        "subtasks": []
    }
    
    task_file = taskmaster_dir / f"task_{i}.json"
    with open(task_file, 'w') as f:
        json.dump(task_data, f, indent=2)
    
    print(f"Created task {i}: {task['title']}")

print(f"\nSuccessfully created {len(tasks)} follow-up tasks for monitoring system implementation.")