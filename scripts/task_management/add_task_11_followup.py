#!/usr/bin/env python3
"""
Add follow-up tasks for Task 11: Integrate rollback with orchestrator
"""

import json
from pathlib import Path
from datetime import datetime

# Define follow-up tasks based on the review
followup_tasks = [
    {
        "title": "Create RollbackManager class",
        "description": "Create RollbackManager that integrates with CheckpointManager to coordinate rollback operations",
        "priority": "high",
        "details": """Implement core rollback functionality:
- Create RollbackManager class in claude_orchestrator/rollback_manager.py
- Integrate with CheckpointManager for state restoration
- Add methods: initiate_rollback(), select_strategy(), coordinate_workers(), track_status()
- Support rollback strategies: full, partial, selective, cascading
- Include rollback validation and verification
- Add comprehensive logging and metrics"""
    },
    {
        "title": "Add rollback hooks to EnhancedOrchestrator",
        "description": "Implement rollback hooks and triggers in the orchestrator",
        "priority": "high",
        "details": """Add rollback integration points:
- on_task_failure() - automatic rollback on task failure
- on_critical_error() - system-wide rollback trigger
- on_validation_failure() - post-execution rollback
- manual_rollback() - user-initiated rollback command
- Integrate with RollbackManager for execution
- Update task context to include rollback status"""
    },
    {
        "title": "Implement rollback strategies",
        "description": "Create different rollback strategy implementations",
        "priority": "medium",
        "details": """Implement strategy classes:
- FullSystemRollback: restore all tasks to checkpoint
- SelectiveRollback: rollback specific failed tasks only
- CascadingRollback: rollback dependent tasks automatically
- PartialRollback: rollback to intermediate checkpoint
- Each strategy should handle worker coordination
- Include validation and recovery verification"""
    },
    {
        "title": "Add rollback configuration",
        "description": "Extend configuration system for rollback settings",
        "priority": "medium",
        "details": """Configuration additions:
- Update orchestrator_config.json schema
- Add: enable_auto_rollback, rollback_trigger_threshold
- Add: default_rollback_strategy, max_rollback_attempts
- Add: rollback_timeout, rollback_validation_enabled
- Create RollbackConfig class
- Update EnhancedConfig to include rollback settings"""
    }
]

# Load existing tasks
tasks_file = Path(".taskmaster/tasks/tasks.json")
with open(tasks_file, 'r') as f:
    tasks_data = json.load(f)

# Find next task ID (handle both int and string IDs)
numeric_ids = []
for t in tasks_data['tasks']:
    try:
        numeric_ids.append(int(t.get('id', 0)))
    except (ValueError, TypeError):
        continue

next_id = max(numeric_ids, default=0) + 1 if numeric_ids else 1

# Add new tasks
for i, task in enumerate(followup_tasks):
    new_task = {
        "id": next_id + i,
        "title": task["title"],
        "description": task["description"],
        "status": "pending",
        "dependencies": [],
        "priority": task["priority"],
        "details": task["details"],
        "subtasks": [],
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "tags": ["rollback", "task-11-followup", "core-feature"]
    }
    tasks_data['tasks'].append(new_task)
    print(f"Created task {next_id + i}: {task['title']}")

# Update metadata
tasks_data['meta']['updatedAt'] = datetime.now().isoformat()
tasks_data['meta']['totalTasks'] = len(tasks_data['tasks'])
tasks_data['meta']['pendingTasks'] = len([t for t in tasks_data['tasks'] if t['status'] == 'pending'])

# Save updated tasks
with open(tasks_file, 'w') as f:
    json.dump(tasks_data, f, indent=2)

print(f"\nSuccessfully created {len(followup_tasks)} follow-up tasks for Task 11 review.")
print("\nThese tasks address the missing rollback implementation that was not completed in Task 11.")