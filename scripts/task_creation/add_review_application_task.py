#!/usr/bin/env python3
"""
Add task for improving review application system
"""

import json
from datetime import datetime

def main():
    # Load current tasks
    with open('.taskmaster/tasks/tasks.json', 'r') as f:
        data = json.load(f)
    
    # Create new task
    new_task = {
        "id": 48,  # Next ID after Anthropic tasks
        "title": "Enhance Review Application System",
        "description": "Improve the review application system to handle complex code changes and validate applications",
        "status": "pending", 
        "dependencies": [],
        "priority": "high",
        "details": """Enhance the ReviewApplier to:
1. Support more code change patterns:
   - Multi-file changes
   - Import additions/removals
   - Class/function refactoring
   - Test file updates
2. Validate changes after application:
   - Run syntax checking
   - Execute affected tests
   - Check for breaking changes
3. Create rollback capability:
   - Save original state before changes
   - Allow reverting if issues detected
4. Better pattern matching:
   - Handle different code block formats
   - Support partial code snippets
   - Fuzzy matching for code location
5. Integration improvements:
   - Queue for re-review if major changes
   - Batch multiple review applications
   - Track review application metrics""",
        "testStrategy": "Unit tests for pattern matching, integration tests for application flow",
        "subtasks": [],
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "tags": ["review-application", "feedback-loop", "code-quality", "followup", "opus-manager-review"]
    }
    
    # Add the task
    data['tasks'].append(new_task)
    
    # Update meta
    data['meta']['totalTasks'] = len(data['tasks'])
    data['meta']['updatedAt'] = datetime.now().isoformat()
    
    # Save
    with open('.taskmaster/tasks/tasks.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("✅ Added task for enhancing review application system")
    print(f"📋 Task 48: {new_task['title']}")
    print("\nThis task will ensure that Opus review feedback is properly:")
    print("- Extracted from review text")
    print("- Applied to the correct files")
    print("- Validated after application")
    print("- Rolled back if issues occur")

if __name__ == "__main__":
    main()