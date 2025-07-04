#!/usr/bin/env python3
"""
Add task to audit all "done" tasks and verify actual implementation.
"""

import json
import uuid
from datetime import datetime

# Load current tasks
with open('.taskmaster/tasks/tasks.json', 'r') as f:
    data = json.load(f)

# Create audit task
new_task = {
    "id": str(uuid.uuid4()),
    "title": "Audit completed tasks for actual implementation",
    "description": """Review all tasks marked as "done" to verify they were actually implemented:

1. Check each "done" task for:
   - Actual code/file creation (not just analysis)
   - Worker output that confirms implementation
   - Existence of deliverables mentioned in task description

2. Create a report identifying:
   - Tasks marked done but only analyzed/simulated
   - Tasks missing actual implementation
   - Tasks requiring follow-up work

3. For each incomplete task, determine:
   - What was supposed to be created
   - What is actually missing
   - Priority for completion

4. Update task statuses:
   - Change improperly marked "done" tasks back to "pending"
   - Add notes about what still needs to be done

This audit ensures all completed work represents actual implementation, not just planning or analysis.""",
    "status": "pending",
    "dependencies": [],
    "priority": "high",
    "details": "Critical task to ensure task completion integrity and identify gaps in implementation",
    "testStrategy": "Verify audit report is comprehensive and all task statuses accurately reflect implementation state",
    "subtasks": [],
    "createdAt": datetime.now().isoformat(),
    "updatedAt": datetime.now().isoformat(),
    "tags": ["audit", "quality-assurance", "task-management", "implementation-verification"]
}

# Add the task
data['tasks'].append(new_task)

# Save updated tasks
with open('.taskmaster/tasks/tasks.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Added task: {new_task['id']}")
print(f"Title: {new_task['title']}")
print(f"Priority: {new_task['priority']}")
print("\nThis task will audit all completed tasks to ensure actual implementation.")