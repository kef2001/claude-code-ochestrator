#!/usr/bin/env python3
"""
Create follow-up task for incomplete Task 25 implementation
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from claude_orchestrator.task_master import TaskMaster

def main():
    """Create follow-up task for Task 25"""
    task_master = TaskMaster()
    
    # Create urgent follow-up task
    task_id = task_master.add_task(
        prompt=(
            "URGENT: Actually implement feedback_collector.py module with complete working code:\n"
            "1. Create claude_orchestrator/feedback_collector.py file\n"
            "2. Implement FeedbackCollector class with:\n"
            "   - collect_feedback(context, decision, outcome) method\n"
            "   - store_feedback(feedback_data) method with JSON storage\n"
            "   - get_feedback_history(limit=100) method\n"
            "   - validate_feedback(data) method for input validation\n"
            "3. Add proper error handling and logging\n"
            "4. Include docstrings and type hints\n"
            "5. Create unit tests in tests/test_feedback_collector.py\n"
            "This task requires creating actual Python code files, not just documentation."
        ),
        priority="high"
    )
    
    print(f"\n✅ Created follow-up task {task_id} for incomplete Task 25 implementation")
    
    # Also create a task to fix the design document
    design_task_id = task_master.add_task(
        prompt=(
            "Fix task_25_design.md which contains wrong content about Feature Flags. "
            "Update it to contain the actual design for the Core Feedback Collection Module "
            "including architecture, data flow, storage schema, and integration points."
        ),
        priority="medium"
    )
    
    print(f"✅ Created task {design_task_id} to fix the design document")
    
    # Create task to update task 25 status
    status_task_id = task_master.add_task(
        prompt=(
            "Update task 25 status from 'pending' to 'failed' or 'incomplete' "
            "to reflect that it was not properly implemented. Add notes about "
            "what went wrong and reference the new follow-up tasks created."
        ),
        priority="low"
    )
    
    print(f"✅ Created task {status_task_id} to update task 25 status")
    
    print("\n📋 Summary of created follow-up tasks:")
    print(f"  - Task {task_id}: Implement feedback_collector.py (HIGH priority)")
    print(f"  - Task {design_task_id}: Fix design document (MEDIUM priority)")
    print(f"  - Task {status_task_id}: Update task 25 status (LOW priority)")

if __name__ == "__main__":
    main()