# Claude Orchestrator API Reference

## Table of Contents

1. [CLI Commands](#cli-commands)
2. [Core Classes](#core-classes)
3. [Configuration](#configuration)
4. [Extensions](#extensions)

## CLI Commands

### Main Commands

#### `co run`
Run the orchestrator to execute all pending tasks.

```bash
co run [options]
```

**Options:**
- `--workers, -w`: Number of parallel workers (default: from config)
- `--verbose, -v`: Enable verbose logging
- `--no-progress`: Disable progress bar
- `--working-dir, -d`: Set working directory
- `--id`: Run only a specific task by ID

**Examples:**
```bash
co run                    # Run with default settings
co run --workers 5        # Run with 5 parallel workers
co run --id 123          # Run only task 123
co run -v -d /project    # Verbose mode in specific directory
```

#### `co add`
Add a new task to the task queue.

```bash
co add "description"
```

**Examples:**
```bash
co add "Implement user authentication"
co add "Fix bug in payment processing"
```

#### `co parse`
Parse a requirements document and create tasks.

```bash
co parse <file_path>
```

**Examples:**
```bash
co parse requirements.txt
co parse docs/PRD.md
```

### Task Management Commands

#### `co list`
List all tasks with optional filtering.

```bash
co list [--filter-status STATUS] [--show-subtasks]
```

**Options:**
- `--filter-status`: Filter by status (pending, in-progress, done, etc.)
- `--show-subtasks`: Show subtasks in output

#### `co show`
Show detailed information about a specific task.

```bash
co show <task_id>
```

#### `co update`
Update task properties.

```bash
co update <task_id> [--status STATUS] [--priority PRIORITY]
```

**Options:**
- `--status`: New status (pending, in-progress, done, etc.)
- `--priority`: New priority (high, medium, low)

#### `co delete`
Delete a task.

```bash
co delete <task_id>
```

### Testing & Quality Commands

#### `co coverage`
Run tests with coverage report.

```bash
co coverage
```

**Output:**
- Terminal coverage summary
- HTML report in `htmlcov/`
- JSON report for CI/CD

#### `co security-audit`
Run security audit for API keys and configuration.

```bash
co security-audit
```

**Checks:**
- API key validation
- File permissions
- Hardcoded secrets scan
- Environment configuration

#### `co test-status`
Show test monitoring status.

```bash
co test-status
```

### Rollback Commands

#### `co checkpoint`
Create a manual checkpoint.

```bash
co checkpoint "description"
```

#### `co list-checkpoints`
List all available checkpoints.

```bash
co list-checkpoints
```

#### `co rollback`
Rollback to a specific checkpoint.

```bash
co rollback <checkpoint_id>
```

### Utility Commands

#### `co init`
Initialize a new project.

```bash
co init
```

**Creates:**
- Default configuration file
- .env template
- Required directories

#### `co check`
Check setup and configuration.

```bash
co check
```

**Validates:**
- Python version
- Claude CLI installation
- API key configuration
- Working directory

#### `co status`
Check Claude session status.

```bash
co status
```

## Core Classes

### ClaudeOrchestrator

Main orchestration class that coordinates all components.

```python
from claude_orchestrator.orchestrator import ClaudeOrchestrator

orchestrator = ClaudeOrchestrator(config, working_dir)
orchestrator.run()
```

**Methods:**

#### `__init__(config: EnhancedConfig, working_dir: str)`
Initialize the orchestrator.

**Parameters:**
- `config`: Configuration object
- `working_dir`: Working directory path

#### `run() -> bool`
Run the orchestration process.

**Returns:**
- `bool`: Success status

#### `shutdown()`
Gracefully shutdown all components.

### OpusManager

Manager component using Claude Opus for planning.

```python
from claude_orchestrator.manager import OpusManager

manager = OpusManager(config)
tasks = manager.analyze_and_plan()
```

**Methods:**

#### `analyze_and_plan() -> List[WorkerTask]`
Analyze tasks and create execution plan.

**Returns:**
- `List[WorkerTask]`: Sorted list of tasks

#### `delegate_task(task: WorkerTask)`
Add task to the execution queue.

**Parameters:**
- `task`: Task to delegate

#### `review_results() -> bool`
Review completed tasks.

**Returns:**
- `bool`: Review success status

### SonnetWorker

Worker component using Claude Sonnet for execution.

```python
from claude_orchestrator.worker import SonnetWorker

worker = SonnetWorker(worker_id=0, working_dir="/project", config=config)
result = worker.process_task(task)
```

**Methods:**

#### `process_task(task: WorkerTask) -> WorkerTask`
Process a single task.

**Parameters:**
- `task`: Task to process

**Returns:**
- `WorkerTask`: Task with updated status and results

### ConfigurationManager

Advanced configuration management system.

```python
from claude_orchestrator.config_manager import ConfigurationManager

config_manager = ConfigurationManager()
config = config_manager.load_config("config.json")
```

**Methods:**

#### `load_config(config_path: str) -> EnhancedConfig`
Load and validate configuration.

**Parameters:**
- `config_path`: Path to config file

**Returns:**
- `EnhancedConfig`: Validated configuration object

#### `validate_config(config_dict: dict) -> ConfigValidationResult`
Validate configuration dictionary.

**Parameters:**
- `config_dict`: Configuration dictionary

**Returns:**
- `ConfigValidationResult`: Validation result with errors/warnings

### RollbackManager

Checkpoint and rollback functionality.

```python
from claude_orchestrator.rollback_manager import RollbackManager

rollback_manager = RollbackManager(checkpoint_dir=".checkpoints")
checkpoint_id = rollback_manager.create_checkpoint()
```

**Methods:**

#### `create_checkpoint(checkpoint_type, description, include_files) -> str`
Create a new checkpoint.

**Parameters:**
- `checkpoint_type`: Type of checkpoint (MANUAL, AUTOMATIC, etc.)
- `description`: Checkpoint description
- `include_files`: Specific files to include

**Returns:**
- `str`: Checkpoint ID

#### `rollback(checkpoint_id, strategy, target_tasks) -> RollbackResult`
Rollback to a checkpoint.

**Parameters:**
- `checkpoint_id`: ID of checkpoint to rollback to
- `strategy`: Rollback strategy (FULL, PARTIAL, SELECTIVE)
- `target_tasks`: Specific tasks to rollback (for SELECTIVE)

**Returns:**
- `RollbackResult`: Result of rollback operation

## Configuration

### Configuration File Structure

```json
{
  "models": {
    "manager": {
      "model": "claude-3-opus-20240229",
      "description": "Opus model for planning and orchestration"
    },
    "worker": {
      "model": "claude-3-5-sonnet-20241022",
      "description": "Sonnet model for task execution"
    }
  },
  "execution": {
    "max_workers": 3,
    "worker_timeout": 1800,
    "manager_timeout": 300,
    "task_queue_timeout": 1.0,
    "default_working_dir": null,
    "max_turns": null,
    "max_retries": 3,
    "retry_base_delay": 1.0,
    "retry_max_delay": 60.0
  },
  "monitoring": {
    "progress_interval": 10,
    "verbose_logging": false,
    "show_progress_bar": true,
    "enable_opus_review": true,
    "usage_warning_threshold": 80,
    "check_usage_before_start": true
  },
  "claude_cli": {
    "command": "claude",
    "flags": {
      "verbose": false,
      "dangerously_skip_permissions": false
    }
  },
  "notifications": {
    "slack": {
      "enabled": false,
      "webhook_url": null,
      "notify_on_completion": true,
      "notify_on_error": true
    }
  }
}
```

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional
ORCHESTRATOR_CONFIG=/path/to/config.json
ORCHESTRATOR_LOG_LEVEL=INFO
ORCHESTRATOR_WORKING_DIR=/path/to/projects
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

## Extensions

### Creating a Custom Worker

```python
from claude_orchestrator.worker import BaseWorker

class CustomWorker(BaseWorker):
    def process_task(self, task):
        # Custom implementation
        pass
```

### Creating a Storage Backend

```python
from claude_orchestrator.storage import StorageInterface

class DatabaseStorage(StorageInterface):
    def save(self, key, value):
        # Database implementation
        pass
    
    def load(self, key):
        # Database implementation
        pass
```

### Creating a Notification Provider

```python
from claude_orchestrator.notifications import NotificationInterface

class EmailNotifier(NotificationInterface):
    def send_notification(self, message, level):
        # Email implementation
        pass
```

## Error Handling

### Exception Types

#### `OrchestrationError`
Base exception for orchestration errors.

```python
from claude_orchestrator.exceptions import OrchestrationError

try:
    orchestrator.run()
except OrchestrationError as e:
    print(f"Orchestration failed: {e}")
```

#### `ConfigurationError`
Configuration-related errors.

```python
from claude_orchestrator.exceptions import ConfigurationError

try:
    config = load_config("config.json")
except ConfigurationError as e:
    print(f"Config error: {e}")
```

#### `WorkerError`
Worker execution errors.

```python
from claude_orchestrator.exceptions import WorkerError

try:
    worker.process_task(task)
except WorkerError as e:
    print(f"Worker error: {e}")
```

## Best Practices

### 1. Configuration Management
- Use environment variables for sensitive data
- Validate configuration before running
- Keep separate configs for dev/prod

### 2. Error Handling
- Always handle `OrchestrationError`
- Log errors before re-raising
- Use retry logic for transient failures

### 3. Resource Management
- Monitor token usage regularly
- Set appropriate timeouts
- Clean up checkpoints periodically

### 4. Testing
- Write unit tests for custom components
- Test with different configurations
- Simulate error conditions

---

**Version**: 1.0
**Last Updated**: 2025-01-07