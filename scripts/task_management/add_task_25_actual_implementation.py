#!/usr/bin/env python3
"""
Create follow-up tasks for Task 25 actual implementation
"""

import sys
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from claude_orchestrator.task_master import TaskManager

def main():
    """Create follow-up tasks for Task 25"""
    task_master = TaskManager()
    
    # Task 1: Actual implementation of feedback_collector.py
    task1 = task_master.add_task(
        title="Implement feedback_collector.py module with complete code",
        description=(
            "Implement feedback_collector.py module with complete working code:\n"
            "1. Create claude_orchestrator/feedback_collector.py file\n"
            "2. Implement FeedbackCollector class with:\n"
            "   - collect_feedback(task_id, user_rating, comments) method\n"
            "   - analyze_feedback_patterns() method to identify common issues\n"
            "   - get_feedback_summary() method for reporting\n"
            "   - integrate_with_task_lifecycle() method\n"
            "3. Use JSON file storage in .taskmaster/feedback/ directory\n"
            "4. Add proper error handling, logging, and type hints\n"
            "5. Include methods for feedback categorization and sentiment analysis"
        ),
        priority="high"
    )
    task1_id = task1.id
    
    # Task 2: Create unit tests
    task2 = task_master.add_task(
        title="Create unit tests for feedback_collector.py",
        description=(
            "Create comprehensive unit tests for feedback_collector.py:\n"
            "1. Create tests/test_feedback_collector.py\n"
            "2. Test all FeedbackCollector methods\n"
            "3. Include edge cases and error conditions\n"
            "4. Test feedback storage and retrieval\n"
            "5. Test feedback analysis functions\n"
            "6. Ensure 90%+ code coverage"
        ),
        priority="medium"
    )
    task2_id = task2.id
    
    # Task 3: Integration with orchestrator
    task3 = task_master.add_task(
        title="Integrate FeedbackCollector with orchestrator",
        description=(
            "Integrate FeedbackCollector with main orchestrator:\n"
            "1. Add feedback collection hooks in task execution lifecycle\n"
            "2. Create CLI commands for feedback operations\n"
            "3. Add feedback prompts after task completion\n"
            "4. Implement feedback reporting in orchestrator summary\n"
            "5. Update orchestrator configuration for feedback settings"
        ),
        priority="medium"
    )
    task3_id = task3.id
    
    print("\n✅ Created follow-up tasks for Task 25 implementation:")
    print(f"  - Task {task1_id}: Implement feedback_collector.py (HIGH priority)")
    print(f"  - Task {task2_id}: Create unit tests (MEDIUM priority)")
    print(f"  - Task {task3_id}: Integration with orchestrator (MEDIUM priority)")

if __name__ == "__main__":
    main()