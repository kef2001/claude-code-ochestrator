# Claude Orchestrator

A powerful task orchestration system that uses Claude Opus as a manager and multiple Claude Sonnet instances as workers for parallel task processing.

## Features

- **Intelligent Task Management**: Opus manager analyzes and plans tasks while Sonnet workers execute them in parallel
- **Parallel Processing**: Execute multiple independent tasks simultaneously with configurable worker pools
- **Task Dependencies**: Automatically handles task dependencies and execution order
- **Real-time Progress Tracking**: Beautiful progress display with multi-task visualization
- **Error Handling & Retries**: Robust error handling with automatic retries for transient failures
- **Session Usage Monitoring**: Tracks API usage and prevents limit exceeded errors
- **Slack Notifications**: Optional Slack integration for task completion notifications
- **Git Integration**: Auto-commit changes after task completion (optional)
- **Task Master Integration**: Built-in task management system with AI-powered task expansion

## Architecture

The orchestrator follows a modular architecture:

- **Orchestrator** (`orchestrator.py`): Main coordination logic
- **OpusManager** (`manager.py`): Task planning and delegation using Claude Opus
- **SonnetWorker** (`worker.py`): Task execution using Claude Sonnet
- **Models** (`models.py`): Data models (TaskStatus, WorkerTask)
- **Configuration** (`config_manager.py`): Advanced configuration management
- **Progress Display** (`enhanced_progress_display.py`): Real-time UI

## Requirements

- Python 3.10+
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-cli) installed and authenticated
- Anthropic API key

## Quick Start

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone the repository

```bash
git clone https://github.com/yourusername/claude-code-orchestrator.git
cd claude-code-orchestrator
```

### 3. Set up virtual environment and install

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

### 4. Initialize a new project

```bash
claude-orchestrator init
```

This will create:
- `orchestrator_config.json` - Configuration file
- `.env` - Environment variables template
- `.gitignore` - Git ignore file
- `.taskmaster/` - Task Master database

### 5. Configure your API key

Edit `.env` and add your Anthropic API key:

```bash
ANTHROPIC_API_KEY=your_api_key_here
```

### 6. Verify setup

```bash
claude-orchestrator check
```

## Usage

### Adding Tasks

Add a single task:
```bash
claude-orchestrator add "Implement user authentication with JWT tokens"
```

Parse a PRD (Product Requirements Document) file:
```bash
claude-orchestrator parse requirements.txt
```

### Running Tasks

Execute all pending tasks:
```bash
claude-orchestrator run
```

Run with custom worker count:
```bash
claude-orchestrator run --workers 5
```

Run with verbose logging:
```bash
claude-orchestrator run --verbose
```

### Monitoring

Check session status and usage:
```bash
claude-orchestrator status
```

List all tasks:
```bash
task-master list
```

## Configuration

The `orchestrator_config.json` file contains all configuration options:

### Models Configuration
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
  }
}
```

### Execution Settings
- `max_workers`: Number of parallel Sonnet workers (default: 3)
- `worker_timeout`: Task timeout in seconds (default: 1800)
- `manager_timeout`: Manager timeout in seconds (default: 300)
- `max_retries`: Maximum retry attempts for failed tasks (default: 3)

### Monitoring Options
- `show_progress_bar`: Display real-time progress (default: true)
- `enable_opus_review`: Enable Opus review after task completion (default: true)
- `usage_warning_threshold`: Usage percentage to trigger warnings (default: 80)

### Notifications (Optional)
```json
{
  "notifications": {
    "slack_webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "notify_on_task_complete": true,
    "notify_on_task_failed": true,
    "notify_on_all_complete": true
  }
}
```

## Architecture

```
┌─────────────────┐
│   Opus Manager  │  ← Analyzes tasks, creates execution plan
└────────┬────────┘
         │
    ┌────┴────┐
    │ Delegates│
    └────┬────┘
         │
┌────────┴────────┬────────────────┬────────────────┐
│  Sonnet Worker 1│  Sonnet Worker 2│  Sonnet Worker 3│
└─────────────────┴────────────────┴────────────────┘
         ↓                 ↓                 ↓
    [Task Results]    [Task Results]    [Task Results]
```

### Components

1. **Opus Manager** (`claude-3-opus-20240229`)
   - Analyzes all pending tasks from Task Master
   - Creates optimal execution plan
   - Handles task dependencies
   - Performs final review of completed work

2. **Sonnet Workers** (`claude-3-5-sonnet-20241022`)
   - Execute individual tasks in parallel
   - Report progress and results
   - Handle file operations and code changes

3. **Task Master**
   - Persistent task storage
   - Task dependency management
   - AI-powered task expansion
   - Progress tracking

## Advanced Usage

### Task Master CLI

View all tasks:
```bash
task-master list
```

Get next task:
```bash
task-master next
```

Update task status:
```bash
task-master set-status --id=1 --status=done
```

Expand task into subtasks:
```bash
task-master expand --id=1 --research
```

### Working Directory

Set a custom working directory:
```bash
claude-orchestrator run --working-dir /path/to/project
```

Or configure in `orchestrator_config.json`:
```json
{
  "execution": {
    "default_working_dir": "/path/to/project"
  }
}
```

### Git Integration

Enable auto-commit in `orchestrator_config.json`:
```json
{
  "git": {
    "auto_commit": true,
    "commit_message_prefix": "Auto-commit by Claude Orchestrator"
  }
}
```

## Troubleshooting

### Common Issues

1. **"Claude CLI not found"**
   - Install Claude CLI: `pip install anthropic`
   - Run: `claude auth`

2. **"ANTHROPIC_API_KEY not set"**
   - Add your API key to `.env` file
   - Or export it: `export ANTHROPIC_API_KEY=your_key`

3. **"Usage limit reached"**
   - The orchestrator automatically pauses when approaching limits
   - Check usage with: `claude-orchestrator status`
   - Wait for limit reset or upgrade your plan

4. **"Task failed"**
   - Check the error message in the output
   - Failed tasks can be retried by running the orchestrator again
   - Review logs with `--verbose` flag

### Debug Mode

Run with verbose logging:
```bash
claude-orchestrator run --verbose
```

Disable progress bar for cleaner logs:
```bash
claude-orchestrator run --no-progress
```

## Examples

### Example 1: Building a Web Application

```bash
# Add the main task
claude-orchestrator add "Build a todo list web app with React frontend and FastAPI backend"

# Run the orchestrator
claude-orchestrator run
```

### Example 2: Refactoring Project

```bash
# Create a PRD file
echo "Refactor the authentication system to use OAuth2 with Google and GitHub providers" > refactor.txt

# Parse and create tasks
claude-orchestrator parse refactor.txt

# Execute with more workers
claude-orchestrator run --workers 5
```

### Example 3: Code Review and Testing

```bash
# Add review task
claude-orchestrator add "Review all Python files for security vulnerabilities and add unit tests"

# Run with Opus review enabled
claude-orchestrator run
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [Claude](https://claude.ai) by Anthropic
- Task management powered by Task Master
- Progress display using Rich library

---

**Note**: This tool requires active Claude API access and will consume API tokens based on task complexity and worker count. Monitor your usage with `claude-orchestrator status`.