#!/usr/bin/env python3
"""Add follow-up tasks for Task 30: Rollback Integration Tests"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_orchestrator.task_master import TaskManager, TaskStatus


def add_followup_tasks():
    """Add follow-up tasks for rollback integration tests"""
    tm = TaskManager()
    
    # Task 1: Implement RollbackManager
    task1 = tm.add_task(
        "Implement RollbackManager component in claude_orchestrator",
        """Create a comprehensive RollbackManager component with:
        - Full state management and tracking
        - Transaction logging for all operations
        - Rollback execution capabilities
        - Error recovery mechanisms
        - Integration with existing task system
        
        Implementation should include:
        1. RollbackManager class in claude_orchestrator/rollback_manager.py
        2. Transaction log storage and retrieval
        3. State snapshot capabilities
        4. Rollback strategy patterns (full, partial, selective)
        5. Integration with TaskMaster for task state management
        
        Tags: rollback, implementation, opus-manager-review, followup""",
        priority="high"
    )
    
    # Task 2: Create test infrastructure
    task2 = tm.add_task(
        "Set up test infrastructure for rollback testing",
        """Create the necessary test infrastructure:
        - Create tests/ directory structure
        - Set up pytest configuration
        - Create test fixtures and utilities
        - Configure test database/storage
        - Add test runner scripts
        
        Structure should include:
        - tests/integration/test_rollback_integration.py
        - tests/unit/test_rollback_manager.py
        - tests/fixtures/rollback_fixtures.py
        - tests/conftest.py for pytest configuration
        
        Tags: testing, infrastructure, rollback, followup""",
        priority="high"
    )
    
    # Task 3: Implement actual integration tests
    task3 = tm.add_task(
        "Create comprehensive rollback integration tests",
        """Implement the actual integration tests for rollback functionality:
        
        Test scenarios to cover:
        1. Single task rollback
        2. Multi-task transaction rollback
        3. Partial rollback with dependencies
        4. Rollback during task execution
        5. Rollback recovery from failures
        6. State consistency verification
        7. Concurrent rollback operations
        8. Rollback with worker pool coordination
        
        Each test should:
        - Set up initial state
        - Execute operations
        - Trigger rollback
        - Verify final state consistency
        - Check audit logs
        
        Tags: testing, integration, rollback, followup""",
        priority="high",
        dependencies=[task1.id, task2.id]
    )
    
    # Task 4: Add rollback CLI commands
    task4 = tm.add_task(
        "Add rollback CLI commands to task-master",
        """Extend task-master CLI with rollback commands:
        - rollback-task: Rollback a specific task
        - rollback-transaction: Rollback a transaction
        - rollback-status: Check rollback status
        - rollback-history: View rollback history
        
        Integration with existing CLI structure and help system
        
        Tags: cli, rollback, followup""",
        priority="medium",
        dependencies=[task1.id]
    )
    
    print(f"Added {len([task1, task2, task3, task4])} follow-up tasks for rollback integration tests")
    print(f"Task IDs: {task1.id}, {task2.id}, {task3.id}, {task4.id}")


if __name__ == "__main__":
    add_followup_tasks()