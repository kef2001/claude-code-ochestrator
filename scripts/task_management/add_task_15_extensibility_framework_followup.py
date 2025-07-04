#!/usr/bin/env python3

import json
import os
import uuid
from datetime import datetime

def add_task(tasks, prompt, priority="medium", dependencies=None):
    """Add a new task to the tasks list"""
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "prompt": prompt,
        "status": "pending",
        "worker_id": None,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "priority": priority,
        "dependencies": dependencies or [],
        "result": None,
        "error": None,
        "design_document": None,
        "followup": False,
        "parent_task_id": "15"
    }
    tasks.append(task)
    return task_id

def main():
    # Load existing tasks
    tasks_file = ".taskmaster/tasks/tasks.json"
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    tasks = data.get("tasks", [])
    
    # Create follow-up tasks for the extensibility framework
    print("Adding follow-up tasks for Task 15: Extensibility Framework...")
    
    # Core framework components (can be done in parallel)
    registry_id = add_task(tasks, 
        "Create base ExtensionRegistry class for managing custom field definitions and validation rules in the feedback model",
        priority="high"
    )
    
    field_def_id = add_task(tasks,
        "Implement CustomFieldDefinition class with support for field types, validation rules, and metadata",
        priority="high"
    )
    
    validator_id = add_task(tasks,
        "Create ValidationRule interface and built-in validators (required, min/max length, regex, custom functions)",
        priority="high"
    )
    
    # Integration components (depend on core)
    model_integration_id = add_task(tasks,
        "Integrate ExtensionRegistry with existing feedback model to support dynamic field addition",
        priority="high",
        dependencies=[registry_id, field_def_id]
    )
    
    serialization_id = add_task(tasks,
        "Implement serialization/deserialization for custom fields in feedback model",
        priority="medium",
        dependencies=[field_def_id]
    )
    
    # Testing and documentation
    test_suite_id = add_task(tasks,
        "Create comprehensive test suite for extensibility framework including unit and integration tests",
        priority="medium",
        dependencies=[registry_id, field_def_id, validator_id]
    )
    
    docs_id = add_task(tasks,
        "Write documentation and examples for using the extensibility framework",
        priority="medium",
        dependencies=[model_integration_id]
    )
    
    # Advanced features
    plugin_system_id = add_task(tasks,
        "Design and implement plugin system for loading extensions from external modules",
        priority="low",
        dependencies=[registry_id]
    )
    
    migration_tool_id = add_task(tasks,
        "Create migration utilities for updating existing feedback data when field definitions change",
        priority="low",
        dependencies=[model_integration_id, serialization_id]
    )
    
    # Save updated tasks
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nSuccessfully added {len(tasks) - len(data.get('tasks', []))} follow-up tasks for the extensibility framework.")
    print("\nCore components (can be done in parallel):")
    print(f"  - Extension Registry (ID: {registry_id[:8]}...)")
    print(f"  - Field Definition (ID: {field_def_id[:8]}...)")
    print(f"  - Validation Rules (ID: {validator_id[:8]}...)")
    print("\nIntegration components:")
    print(f"  - Model Integration (ID: {model_integration_id[:8]}...)")
    print(f"  - Serialization Support (ID: {serialization_id[:8]}...)")
    print("\nQuality and documentation:")
    print(f"  - Test Suite (ID: {test_suite_id[:8]}...)")
    print(f"  - Documentation (ID: {docs_id[:8]}...)")
    print("\nAdvanced features:")
    print(f"  - Plugin System (ID: {plugin_system_id[:8]}...)")
    print(f"  - Migration Tools (ID: {migration_tool_id[:8]}...)")

if __name__ == "__main__":
    main()