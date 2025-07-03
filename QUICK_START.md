# Quick Start Guide

## Activate Virtual Environment

Before using the commands, you need to activate the virtual environment:

```bash
source .venv/bin/activate
```

After activation, you'll see `(.venv)` in your terminal prompt.

## Available Commands

You can use any of these commands:
- `claude-orchestrator` (full name)
- `cco` (short version)
- `co` (shortest version)

## Verify Installation

```bash
co --help
# or
cco --help
# or
claude-orchestrator --help
```

## Common Commands

### Task Management
```bash
# List all tasks
co list

# List only pending tasks  
co list --filter-status pending

# List with subtasks
co list --show-subtasks

# Show task details
co show 1

# Get next available task
co next

# Update task status
co update 1 --status in-progress
co update 1 --status done

# Expand task into subtasks
co expand 1
co expand 1 --research  # With AI research

# Delete a task
co delete 1
```

### Task Creation
```bash
# Add a new task
co add "Your task description"

# Parse PRD file
co parse requirements.txt
```

### Orchestration
```bash
# Run the orchestrator
co run

# Run with more workers
co run --workers 5

# Run with verbose output
co run --verbose
```

### Setup & Status
```bash
# Initialize a new project
co init

# Check setup
co check

# Check session status
co status
```

## Deactivate Virtual Environment

When you're done:

```bash
deactivate
```

## Alternative: Use Without Activation

You can also run commands without activating the virtual environment:

```bash
.venv/bin/co --help
.venv/bin/cco --help
```

Or create aliases in your shell configuration (`~/.zshrc` or `~/.bashrc`):

```bash
alias co='/Users/deokwan/workspace/claude-code-orchestrator/.venv/bin/co'
alias cco='/Users/deokwan/workspace/claude-code-orchestrator/.venv/bin/cco'
```

Then reload your shell configuration:
```bash
source ~/.zshrc  # or source ~/.bashrc
```