#!/usr/bin/env python3
import json
import datetime
from pathlib import Path

tasks_file = Path(".taskmaster/tasks/tasks.json")

# Read existing tasks
with open(tasks_file, 'r') as f:
    data = json.load(f)

# Get the next task ID
next_id = max([task['id'] for task in data['tasks']]) + 1

# Define new tasks for test metrics reporting
new_tasks = [
    {
        "id": next_id,
        "title": "Implement test metrics collection module",
        "description": "Create test metrics collection module with methods to capture test counts by category (unit, integration, e2e), execution times, pass/fail rates, and memory usage during tests",
        "status": "pending",
        "dependencies": [],
        "priority": "high",
        "subtasks": [],
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "tags": ["testing", "metrics", "monitoring"]
    },
    {
        "id": next_id + 1,
        "title": "Integrate code coverage reporting",
        "description": "Integrate code coverage tools (coverage.py, jest coverage, etc.) to collect and report coverage percentages including line coverage, branch coverage, and function coverage",
        "status": "pending",
        "dependencies": [next_id],
        "priority": "high",
        "subtasks": [],
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "tags": ["testing", "coverage", "metrics"]
    },
    {
        "id": next_id + 2,
        "title": "Implement performance benchmarking framework",
        "description": "Create performance benchmarking framework to measure response times, throughput, latency percentiles (p50, p95, p99), and resource utilization during test execution",
        "status": "pending",
        "dependencies": [next_id],
        "priority": "high",
        "subtasks": [],
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "tags": ["testing", "performance", "benchmarking"]
    },
    {
        "id": next_id + 3,
        "title": "Integrate security scan results collection",
        "description": "Integrate with security scanning tools (SAST, dependency vulnerability scanners) to collect and report security findings, vulnerabilities by severity, and compliance status",
        "status": "pending",
        "dependencies": [next_id],
        "priority": "high",
        "subtasks": [],
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "tags": ["testing", "security", "scanning"]
    },
    {
        "id": next_id + 4,
        "title": "Create unified test metrics reporting dashboard",
        "description": "Build unified reporting dashboard that aggregates all test metrics (counts, coverage, performance, security) into comprehensive HTML/JSON reports with visualizations and trend analysis",
        "status": "pending",
        "dependencies": [next_id, next_id + 1, next_id + 2, next_id + 3],
        "priority": "medium",
        "subtasks": [],
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "tags": ["testing", "reporting", "visualization"]
    },
    {
        "id": next_id + 5,
        "title": "Implement test metrics storage and history",
        "description": "Create storage system for historical test metrics data to enable trend analysis, regression detection, and performance degradation alerts over time",
        "status": "pending",
        "dependencies": [next_id + 4],
        "priority": "medium",
        "subtasks": [],
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "tags": ["testing", "storage", "history"]
    }
]

# Add new tasks
data['tasks'].extend(new_tasks)
data['meta']['updatedAt'] = datetime.datetime.now().isoformat()

# Write back
with open(tasks_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"Successfully added {len(new_tasks)} follow-up tasks for test metrics reporting implementation")
print("\nNew tasks added:")
for task in new_tasks:
    print(f"  - Task {task['id']}: {task['title']} (Priority: {task['priority']})")