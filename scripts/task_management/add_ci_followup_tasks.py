#!/usr/bin/env python3
import json
import os
from datetime import datetime

# Follow-up tasks for CI/CD implementation
followup_tasks = [
    {
        "prompt": "Create GitHub Actions workflow file (.github/workflows/test.yml) that runs tests on every pull request and push to main branch",
        "priority": "high"
    },
    {
        "prompt": "Implement test failure notification system using GitHub Actions notifications or integrate with Slack/email for immediate alerts",
        "priority": "high"
    },
    {
        "prompt": "Set up test result trend tracking using GitHub Actions artifacts or integrate with a test reporting service like Allure or Jest coverage reports",
        "priority": "medium"
    },
    {
        "prompt": "Configure parallel test execution in CI pipeline to optimize build times",
        "priority": "medium"
    },
    {
        "prompt": "Add pre-commit hooks configuration to run linting and basic tests before allowing commits",
        "priority": "low"
    }
]

# Read existing tasks
tasks_file = '.taskmaster/tasks/tasks.json'
with open(tasks_file, 'r') as f:
    data = json.load(f)

# Get next task ID (handle both numeric and UUID IDs)
numeric_ids = []
for task in data['tasks']:
    try:
        numeric_ids.append(int(task['id']))
    except (ValueError, TypeError):
        # Skip non-numeric IDs
        pass
next_id = max(numeric_ids, default=0) + 1

# Add new tasks
for i, task_info in enumerate(followup_tasks):
    task = {
        "id": next_id + i,
        "prompt": task_info["prompt"],
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "priority": task_info["priority"],
        "worker_output": None,
        "review_status": None,
        "review_notes": None,
        "opus_review": None
    }
    data['tasks'].append(task)
    print(f"Added task {task['id']}: {task['prompt'][:80]}...")

# Write back
with open(tasks_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"\nSuccessfully added {len(followup_tasks)} follow-up tasks for CI/CD implementation")