# Rollback Configuration Guide

The Claude Orchestrator includes a comprehensive rollback system that allows you to create checkpoints and restore previous states. This guide explains how to configure and use the rollback features.

## Configuration Options

Add the following section to your `orchestrator_config.json`:

```json
{
  "rollback": {
    "enabled": true,
    "checkpoint_dir": ".checkpoints",
    "max_checkpoints": 50,
    "auto_checkpoint": true,
    "checkpoint_on_task_completion": true,
    "checkpoint_on_error": true,
    "checkpoint_interval_minutes": 30
  }
}
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable the rollback system |
| `checkpoint_dir` | string | `.checkpoints` | Directory to store checkpoint data |
| `max_checkpoints` | integer | `50` | Maximum number of checkpoints to keep (older ones are automatically deleted) |
| `auto_checkpoint` | boolean | `true` | Enable automatic checkpoint creation |
| `checkpoint_on_task_completion` | boolean | `true` | Create checkpoint after each task completes |
| `checkpoint_on_error` | boolean | `true` | Create checkpoint before error recovery |
| `checkpoint_interval_minutes` | integer | `30` | Create periodic checkpoints at this interval |

## CLI Commands

### Create Manual Checkpoint

```bash
# Create a checkpoint with default description
co checkpoint

# Create a checkpoint with custom description
co checkpoint "Before major refactoring"
```

### List Available Checkpoints

```bash
co list-checkpoints
```

Output example:
```
📋 Available Checkpoints
================================================================================

🔹 cp_20250105_143022
   Created:     2025-01-05 14:30:22
   Type:        manual
   Description: Before major refactoring
   Tasks:       15
   Files:       23

🔹 cp_20250105_140000
   Created:     2025-01-05 14:00:00
   Type:        automatic
   Description: Periodic checkpoint
   Tasks:       12
   Files:       20

📊 Total checkpoints: 2
```

### Rollback to Checkpoint

```bash
# Rollback to specific checkpoint
co rollback cp_20250105_143022
```

The system will ask for confirmation before performing the rollback.

## Checkpoint Types

1. **Manual Checkpoints**: Created explicitly using the `co checkpoint` command
2. **Automatic Checkpoints**: Created based on configuration settings
   - After task completion (if `checkpoint_on_task_completion` is true)
   - Before error recovery (if `checkpoint_on_error` is true)
   - Periodically (based on `checkpoint_interval_minutes`)

## What's Included in Checkpoints

Each checkpoint captures:
- Task states and metadata
- File snapshots (for tracked files)
- Rollback history
- Custom data specific to the checkpoint

## Rollback Strategies

The system supports three rollback strategies:

1. **FULL**: Complete rollback to checkpoint state
2. **PARTIAL**: Rollback specific components only
3. **SELECTIVE**: Rollback specific tasks only

Currently, the CLI uses FULL rollback by default.

## Best Practices

1. **Regular Manual Checkpoints**: Create manual checkpoints before major changes
2. **Descriptive Names**: Use clear descriptions for manual checkpoints
3. **Monitor Disk Usage**: Checkpoints can consume disk space; adjust `max_checkpoints` as needed
4. **Test Rollbacks**: Periodically test rollback functionality to ensure it works as expected

## Integration with Other Systems

The rollback system integrates with:
- **Feedback System**: Tracks rollback operations as feedback
- **Test Monitoring**: Can trigger checkpoints based on test results
- **Task Management**: Maintains task state consistency across rollbacks

## Troubleshooting

### Checkpoint Directory Not Found
Ensure the `checkpoint_dir` exists and has write permissions.

### Out of Disk Space
Reduce `max_checkpoints` or manually clean old checkpoints.

### Rollback Fails
Check the error messages and ensure:
- The checkpoint ID is valid
- Files haven't been manually deleted
- The checkpoint data isn't corrupted

## Advanced Configuration

For production environments, consider:
- Storing checkpoints on a separate disk/partition
- Implementing checkpoint archival for long-term storage
- Setting up automated checkpoint verification
- Integrating with backup systems