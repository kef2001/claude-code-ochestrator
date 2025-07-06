#!/usr/bin/env python3
"""Add high-priority task to create comprehensive feedback system documentation."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_orchestrator.task_manager import TaskManager

def main():
    manager = TaskManager()
    
    task_prompt = """Create comprehensive documentation for the feedback storage system. The documentation should include:

1. **Architecture Overview** (docs/feedback/architecture.md)
   - System design and components
   - Data flow diagrams
   - Integration points with orchestrator

2. **API Reference** (docs/feedback/api_reference.md)
   - FeedbackCollector class documentation
   - Method signatures and parameters
   - Return types and exceptions
   - Usage examples for each method

3. **Database Schema** (docs/feedback/schema.md)
   - Feedback data model
   - Storage schema with field descriptions
   - Indexes and relationships
   - Migration guidelines

4. **Integration Guide** (docs/feedback/integration_guide.md)
   - Step-by-step integration instructions
   - Code examples for common use cases
   - Configuration options
   - Best practices

5. **Configuration Reference** (docs/feedback/configuration.md)
   - All configuration options
   - Environment variables
   - Default values and recommendations

Use the existing technical specifications from docs/task_4_feedback_integration_followup.md as a starting point."""
    
    task = manager.create_task(
        prompt=task_prompt,
        priority='high',
        tags=['documentation', 'feedback-system', 'followup', 'opus-manager-review']
    )
    
    print(f"Created task {task.id}: {task.title}")
    print(f"Priority: {task.priority}")
    print("This task will create comprehensive documentation for the feedback storage system.")

if __name__ == "__main__":
    main()