#!/usr/bin/env python3
"""Add follow-up task for implementing rollback hooks"""

from claude_orchestrator.task_master import TaskManager

def main():
    task_manager = TaskManager()
    
    # Add the implementation task
    task = task_manager.add_task(
        title="Implement rollback hooks in OpusManager",
        description="""Implement rollback hooks in OpusManager (not EnhancedOrchestrator) to handle task failures gracefully. 

Requirements:
1. Rollback hook registration system - Allow registering cleanup functions
2. Automatic rollback triggers on task failure - Execute hooks when tasks fail
3. Manual rollback capability - API to trigger rollbacks manually
4. State snapshots before task execution - Capture state for restoration
5. Integration with existing error handling - Work with current error flows

Implementation should include:
- RollbackManager class to manage hooks and state
- Hook registration/deregistration methods
- State snapshot and restore functionality
- Integration points in OpusManager.execute_task()
- Unit tests for rollback functionality
- Documentation and examples""",
        priority="high",
        details="""Technical Details:
- Create claude_orchestrator/rollback_manager.py
- Add rollback hooks to OpusManager class
- Implement state snapshot mechanism
- Add rollback triggers in error handling paths
- Create comprehensive unit tests
- Update documentation with rollback examples"""
    )
    
    print(f"✅ Created follow-up task {task.id}: {task.title}")
    
    # Add a design task
    design_task = task_manager.add_task(
        title="Design rollback architecture for OpusManager",
        description="""Create detailed design document for rollback functionality in OpusManager.

Design should cover:
1. Rollback hook interface and lifecycle
2. State management strategy
3. Integration with existing error handling
4. Performance considerations
5. Edge cases and failure scenarios""",
        priority="high",
        dependencies=[task.id]
    )
    
    print(f"✅ Created design task {design_task.id}: {design_task.title}")

if __name__ == "__main__":
    main()