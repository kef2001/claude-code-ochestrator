# RollbackManager Usage Guide

## Overview

The RollbackManager provides comprehensive rollback functionality for the Claude Orchestrator system, allowing restoration of system state from checkpoints in case of errors or manual intervention needs.

## Key Features

- **Checkpoint-based Recovery**: Integrates with CheckpointManager for state preservation
- **Multiple Rollback Strategies**: Full, partial, and selective rollback capabilities
- **Automatic Error Recovery**: Automatic rollback on task failures
- **Manual Rollback Support**: API for manual rollback operations
- **Rollback History Tracking**: Complete audit trail of rollback operations
- **Version Compatibility**: Ensures compatibility between checkpoint versions

## Basic Usage

### Initialization

```python
from claude_orchestrator.rollback import RollbackManager, create_rollback_manager
from claude_orchestrator.checkpoint_system import CheckpointManager

# Create with default settings
rollback_manager = create_rollback_manager()

# Or with custom configuration
checkpoint_manager = CheckpointManager()
rollback_manager = RollbackManager(
    checkpoint_manager=checkpoint_manager,
    storage_dir=".taskmaster/rollbacks",
    max_rollback_history=100
)
```

### Creating Checkpoints

Before you can rollback, you need checkpoints:

```python
# Create a checkpoint for a task
checkpoint_id = await rollback_manager.checkpoint_manager.create_checkpoint(
    task_id="task-123",
    phase="processing",
    state_data={
        "progress": 50,
        "intermediate_results": {...}
    }
)
```

### Performing Rollbacks

#### Automatic Rollback on Error

```python
from claude_orchestrator.rollback import RollbackReason

# Use context manager for automatic rollback on error
async with rollback_manager.rollback_on_error(
    task_id="task-123",
    checkpoint_id=checkpoint_id
):
    # Perform risky operations
    await process_task()
    # If an exception occurs, automatic rollback happens
```

#### Manual Rollback

```python
# Perform manual rollback
rollback_record = await rollback_manager.rollback_to_checkpoint(
    checkpoint_id=checkpoint_id,
    task_id="task-123",
    reason=RollbackReason.MANUAL,
    metadata={"user": "admin", "reason": "Incorrect results"}
)

print(f"Rollback completed: {rollback_record.rollback_id}")
```

### Rollback Strategies

The system supports three rollback strategies:

#### 1. Full Rollback

Restores the entire system state:

```python
from claude_orchestrator.rollback_strategies import (
    RollbackStrategyManager, 
    RollbackScope,
    RollbackStrategyType
)

strategy_manager = RollbackStrategyManager(rollback_manager)

# Create full rollback scope
scope = RollbackScope(
    strategy_type=RollbackStrategyType.FULL,
    checkpoint_ids=[checkpoint_id],
    affected_tasks=["task-123"]
)

# Execute rollback
result = await strategy_manager.execute_rollback(
    scope=scope,
    reason=RollbackReason.ERROR
)
```

#### 2. Partial Rollback

Restores specific components:

```python
from claude_orchestrator.rollback_strategies import ComponentType

# Create partial rollback scope
scope = RollbackScope(
    strategy_type=RollbackStrategyType.PARTIAL,
    checkpoint_ids=[checkpoint_id],
    affected_components=[
        ComponentType.TASK_STATE,
        ComponentType.WORKER_STATE
    ]
)

result = await strategy_manager.execute_rollback(scope, reason)
```

#### 3. Selective Rollback

Restores specific tasks:

```python
# Create selective rollback scope
scope = RollbackScope(
    strategy_type=RollbackStrategyType.SELECTIVE,
    checkpoint_ids=[checkpoint_id],
    affected_tasks=["task-123", "task-456"],
    preserve_tasks=["task-789"]  # Don't rollback these
)

result = await strategy_manager.execute_rollback(scope, reason)
```

## Integration with Enhanced Orchestrator

The RollbackManager is fully integrated with the EnhancedOrchestrator:

```python
from claude_orchestrator.enhanced_orchestrator import EnhancedClaudeOrchestrator

orchestrator = EnhancedClaudeOrchestrator()

# Automatic rollback is enabled by default for task failures
# Configure in orchestrator_config.json:
{
    "rollback_storage_dir": ".taskmaster/rollbacks",
    "rollback_on_failure": true,
    "max_rollback_history": 100
}
```

### Task Context Configuration

Control rollback behavior per task:

```python
# Process task with rollback enabled
await orchestrator.process_task_enhanced(
    task_id="task-123",
    rollback_enabled=True,
    rollback_on_failure=True
)

# Disable rollback for specific task
await orchestrator.process_task_enhanced(
    task_id="task-456",
    rollback_enabled=False
)
```

## Rollback History and Monitoring

### Viewing Rollback History

```python
# Get rollback history
history = rollback_manager.get_rollback_history(limit=10)

for record in history:
    print(f"Rollback {record.rollback_id}:")
    print(f"  Task: {record.task_id}")
    print(f"  Reason: {record.reason.value}")
    print(f"  Status: {record.status.value}")
    print(f"  Time: {record.initiated_at}")
```

### Rollback Callbacks

Register callbacks to monitor rollback events:

```python
def on_rollback_event(event_type, rollback_record, checkpoint_data):
    print(f"Rollback event: {event_type}")
    print(f"Task: {rollback_record.task_id}")
    # Log, alert, or take other actions

rollback_manager.register_callback(on_rollback_event)
```

## Best Practices

### 1. Checkpoint Frequency

Create checkpoints at critical stages:

```python
# Before major operations
checkpoint_id = await create_checkpoint("before_processing")
try:
    await heavy_processing()
except Exception:
    await rollback_to_checkpoint(checkpoint_id)
```

### 2. Checkpoint Validation

Always validate checkpoints before rollback:

```python
# Check if rollback is possible
if rollback_manager.can_rollback(checkpoint_id):
    await rollback_manager.rollback_to_checkpoint(checkpoint_id, task_id, reason)
else:
    # Handle invalid checkpoint
    logger.error(f"Cannot rollback to checkpoint {checkpoint_id}")
```

### 3. Cleanup Old Checkpoints

Regularly clean up old checkpoints:

```python
# Clean up checkpoints older than 7 days
from datetime import datetime, timedelta

cutoff_date = datetime.now() - timedelta(days=7)
deleted_count = rollback_manager.checkpoint_manager.cleanup_old_checkpoints(
    before_date=cutoff_date,
    keep_archived=True
)
```

### 4. Error Handling

Handle rollback failures gracefully:

```python
try:
    rollback_record = await rollback_manager.rollback_to_checkpoint(
        checkpoint_id, task_id, reason
    )
except Exception as e:
    logger.error(f"Rollback failed: {e}")
    # Implement fallback strategy
    await emergency_recovery()
```

## Advanced Features

### Cascading Rollbacks

Handle dependent task rollbacks:

```python
# Rollback with cascade handling
scope = RollbackScope(
    strategy_type=RollbackStrategyType.SELECTIVE,
    checkpoint_ids=[checkpoint_id],
    affected_tasks=["parent-task"],
    cascade_dependencies=True  # Also rollback dependent tasks
)
```

### Rollback Metadata

Store additional context with rollbacks:

```python
metadata = {
    "triggered_by": "monitoring_system",
    "error_details": str(exception),
    "system_metrics": current_metrics,
    "user_notes": "Performance degradation detected"
}

rollback_record = await rollback_manager.rollback_to_checkpoint(
    checkpoint_id=checkpoint_id,
    task_id=task_id,
    reason=RollbackReason.RESOURCE_LIMIT,
    metadata=metadata
)
```

### Version Compatibility

The system checks version compatibility:

```python
# Checkpoint version is automatically checked
# If incompatible, rollback will fail safely
try:
    await rollback_manager.rollback_to_checkpoint(old_checkpoint_id, task_id, reason)
except ValueError as e:
    if "version" in str(e):
        logger.error("Checkpoint version incompatible")
```

## Troubleshooting

### Common Issues

1. **Checkpoint Not Found**
   - Ensure checkpoint exists before rollback
   - Check if checkpoint wasn't cleaned up

2. **Version Mismatch**
   - Update system to compatible version
   - Or migrate checkpoints to new format

3. **Partial Rollback Failure**
   - Check component dependencies
   - Ensure all required components are available

4. **Storage Issues**
   - Verify storage directory permissions
   - Check available disk space

### Debug Mode

Enable debug logging for detailed information:

```python
import logging
logging.getLogger('claude_orchestrator.rollback').setLevel(logging.DEBUG)
```

## CLI Commands

The orchestrator CLI supports rollback operations:

```bash
# List checkpoints
co checkpoints list --task-id task-123

# Perform manual rollback
co rollback --checkpoint-id cp-456 --reason "Manual correction"

# View rollback history
co rollback history --limit 20
```

## Summary

The RollbackManager provides a robust recovery mechanism for the Claude Orchestrator system. By following these guidelines and best practices, you can ensure reliable error recovery and system stability. Always test rollback procedures in development before relying on them in production environments.