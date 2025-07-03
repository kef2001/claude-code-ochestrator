# Project Structure

```
claude-code-orchestrator/
├── README.md                    # Project documentation
├── pyproject.toml              # Project metadata and dependencies (uv)
├── uv.lock                     # Locked dependencies
├── orchestrator_config.json    # Default configuration file
├── .gitignore                  # Git ignore patterns
└── claude_orchestrator/        # Main package
    ├── __init__.py            # Package initialization
    ├── main.py                # Main entry point and CLI
    ├── task_master.py         # Task management system
    ├── task_master_ai.py      # AI-powered task features
    ├── config_manager.py      # Configuration management
    └── claude_error_handler.py # Error handling utilities
```

## Files Description

### Root Files
- **README.md**: Complete project documentation with installation and usage instructions
- **pyproject.toml**: Python project configuration for uv package manager
- **uv.lock**: Dependency lock file ensuring reproducible installations
- **orchestrator_config.json**: Sample configuration file created during project setup
- **.gitignore**: Specifies which files Git should ignore

### Package Files (`claude_orchestrator/`)
- **__init__.py**: Makes the directory a Python package and exports main function
- **main.py**: Contains the CLI interface and orchestration logic
- **task_master.py**: Core task management functionality
- **task_master_ai.py**: AI features for task expansion and PRD parsing
- **config_manager.py**: Advanced configuration validation and management
- **claude_error_handler.py**: Robust error handling with retry logic

## Installation

```bash
# Install with uv
uv pip install -e .

# Or install dependencies only
uv pip sync
```

## Usage

```bash
# Initialize new project
claude-orchestrator init

# Check setup
claude-orchestrator check

# Add tasks
claude-orchestrator add "Your task description"

# Run orchestrator
claude-orchestrator run
```