#!/usr/bin/env python3
import json
import datetime
from pathlib import Path

tasks_file = Path(".taskmaster/tasks/tasks.json")

# Read existing tasks
with open(tasks_file, 'r') as f:
    data = json.load(f)

# Get the next task ID (handle both string and int IDs)
task_ids = []
for task in data['tasks']:
    if isinstance(task['id'], int):
        task_ids.append(task['id'])
    elif isinstance(task['id'], str) and task['id'].isdigit():
        task_ids.append(int(task['id']))
next_id = max(task_ids) + 1 if task_ids else 1

# Define follow-up tasks for Task 8 improvements
new_tasks = [
    {
        "id": next_id,
        "title": "Add detailed test coverage reporting",
        "description": "Enhance end-to-end tests to include detailed coverage metrics: line coverage percentage, branch coverage, statement coverage, and identify uncovered code paths. Generate coverage reports in HTML and JSON formats.",
        "status": "pending",
        "dependencies": [8],  # Depends on Task 8
        "priority": "high",
        "subtasks": [],
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "tags": ["testing", "coverage", "metrics", "feedback-system"]
    },
    {
        "id": next_id + 1,
        "title": "Document test scenarios and test cases",
        "description": "Create comprehensive documentation of all test scenarios covered in end-to-end testing including: happy paths, error cases, edge cases, performance scenarios, and security test cases.",
        "status": "pending",
        "dependencies": [8],
        "priority": "high",
        "subtasks": [],
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "tags": ["testing", "documentation", "feedback-system"]
    },
    {
        "id": next_id + 2,
        "title": "Add performance benchmarks and metrics",
        "description": "Define specific performance benchmarks for the feedback system including: response time targets (p50, p95, p99), throughput requirements, memory usage limits, and CPU utilization thresholds.",
        "status": "pending",
        "dependencies": [8],
        "priority": "high",
        "subtasks": [],
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "tags": ["testing", "performance", "benchmarks", "feedback-system"]
    },
    {
        "id": next_id + 3,
        "title": "Implement error handling test suite",
        "description": "Create dedicated test suite for error handling scenarios including: network failures, invalid inputs, timeout conditions, resource exhaustion, and graceful degradation testing.",
        "status": "pending",
        "dependencies": [8],
        "priority": "medium",
        "subtasks": [],
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "tags": ["testing", "error-handling", "resilience", "feedback-system"]
    },
    {
        "id": next_id + 4,
        "title": "Add continuous test monitoring",
        "description": "Implement continuous monitoring of test execution with real-time alerts for test failures, performance regressions, and coverage drops. Include test trend analysis and failure pattern detection.",
        "status": "pending",
        "dependencies": [next_id, next_id + 2],
        "priority": "medium",
        "subtasks": [],
        "createdAt": datetime.datetime.now().isoformat(),
        "updatedAt": datetime.datetime.now().isoformat(),
        "tags": ["testing", "monitoring", "alerts", "feedback-system"]
    }
]

# Add new tasks
data['tasks'].extend(new_tasks)
if 'meta' in data:
    data['meta']['updatedAt'] = datetime.datetime.now().isoformat()

# Write back
with open(tasks_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"Successfully added {len(new_tasks)} follow-up tasks for Task 8 improvements")
print("\nNew tasks added:")
for task in new_tasks:
    print(f"  - Task {task['id']}: {task['title']} (Priority: {task['priority']})")