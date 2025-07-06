#!/usr/bin/env python3

import json
import uuid
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_orchestrator.task_master import TaskManager

def main():
    task_master = TaskManager()
    
    title = "Implement actual RollbackManager integration tests"
    description = "Create comprehensive integration tests for RollbackManager with TaskMaster. This task must actually create the test file tests/test_rollback_integration.py with full implementation including: 1) Test class setup with proper imports and fixtures, 2) Test cases for state capture and restoration, 3) Mock TaskMaster interactions using unittest.mock, 4) Error handling scenarios (rollback failures, state corruption, etc.), 5) Edge case testing (empty states, concurrent rollbacks, etc.), 6) Proper assertions and test coverage. The implementation must use pytest framework and follow best practices."
    
    # Add the task
    task = task_master.add_task(
        title=title,
        description=description,
        priority="high",
        details="Implementation requirements:\n- Use pytest framework\n- Create tests/test_rollback_integration.py\n- Include mock TaskMaster interactions\n- Test error scenarios\n- Ensure proper test coverage"
    )
    print(f"✅ Added rollback integration test implementation task with ID: {task.id}")

if __name__ == "__main__":
    main()