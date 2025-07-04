#!/usr/bin/env python3
"""Follow-up task for Task 24: Add rollback configuration options"""

import json

# Add the follow-up task to implement rollback configuration
task = {
    "prompt": "Add rollback configuration properties to EnhancedConfig class in config_manager.py, including: rollback_enabled, rollback_strategy (full/partial/selective), auto_rollback_on_error, max_rollback_history, and rollback_timeout. Also update CONFIG_SCHEMA to include the rollback section with proper validation.",
    "priority": "high"
}

print(f"Task 24 Follow-up: {task['prompt']}")
print(f"Priority: {task['priority']}")
print("\nPlease run this with task-master to create the follow-up task.")