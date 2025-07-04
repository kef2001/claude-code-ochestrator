#!/usr/bin/env python3

import json
import os
from datetime import datetime

# Load the tasks file
tasks_file = ".taskmaster/tasks/tasks.json"
with open(tasks_file, 'r') as f:
    data = json.load(f)

# Find the highest task ID
max_id = 0
for task in data['tasks']:
    max_id = max(max_id, int(task['id']))

# Create the follow-up task
new_task = {
    "id": max_id + 1,
    "prompt": "Create types/feedback.ts file with TypeScript interfaces for: UserFeedback (userId, timestamp, message, rating), SystemFeedback (component, level, metrics), ErrorFeedback (errorType, stackTrace, context), PerformanceMetrics (responseTime, memoryUsage, cpuUsage), and ResponseData (status, data, metadata). Include proper TypeScript types, optional fields, and JSDoc comments.",
    "priority": "high",
    "status": "pending",
    "created_at": datetime.now().isoformat(),
    "context": "Follow-up task for Task 40 which was not actually implemented. The worker only provided analysis but did not create any code.",
    "parent_task_id": 40
}

# Add the task
data['tasks'].append(new_task)

# Update metadata
data['metadata']['last_updated'] = datetime.now().isoformat()
data['metadata']['version'] = data['metadata'].get('version', '1.0.0')

# Write back to file
with open(tasks_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"Successfully added follow-up task {new_task['id']} for Task 40 implementation")