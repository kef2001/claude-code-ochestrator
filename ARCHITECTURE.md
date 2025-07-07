# Claude Orchestrator Architecture

## Overview

Claude Orchestrator is a distributed task orchestration system that leverages Claude AI models in a manager-worker pattern. The system uses Claude Opus as an intelligent task manager and multiple Claude Sonnet instances as parallel workers to efficiently process complex tasks.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User Interface                              │
│                    (CLI Commands / Task Master)                      │
└─────────────────────────────────────────┬───────────────────────────┘
                                         │
┌─────────────────────────────────────────┴───────────────────────────┐
│                        Main Orchestrator                             │
│                   (claude_orchestrator.main)                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    ClaudeOrchestrator                        │   │
│  │  - Coordination Logic                                        │   │
│  │  - Worker Pool Management                                    │   │
│  │  - Progress Tracking                                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────┬───────────────────────┘
                     │                         │
        ┌────────────┴──────────┐   ┌─────────┴────────────┐
        │    Opus Manager       │   │   Sonnet Workers     │
        │  (manager.py)         │   │   (worker.py)        │
        │                       │   │                       │
        │  - Task Analysis      │   │  - Task Execution    │
        │  - Planning           │   │  - Parallel Process  │
        │  - Delegation         │   │  - Error Handling    │
        │  - Review             │   │  - Progress Report   │
        └───────────────────────┘   └───────────────────────┘
                     │                         │
        ┌────────────┴──────────────────────────┴─────────────┐
        │              Task Management System                  │
        │                (Task Master)                         │
        │  - Task Storage                                      │
        │  - Status Tracking                                   │
        │  - Dependency Management                             │
        └──────────────────────────────────────────────────────┘
```

## Core Components

### 1. Main Entry Point (`main.py`)

The main module serves as the entry point and CLI interface for the orchestrator.

**Key Responsibilities:**
- Command-line argument parsing
- Configuration loading and validation
- Component initialization
- Command routing

**Key Functions:**
- `main()`: Entry point, handles CLI commands
- `create_config()`: Loads and validates configuration
- `run_orchestrator()`: Initializes and runs the orchestration system

### 2. Orchestrator (`orchestrator.py`)

The central coordination component that manages the entire task execution lifecycle.

**Key Class: `ClaudeOrchestrator`**

**Responsibilities:**
- Initialize and manage Opus Manager and Sonnet Workers
- Coordinate task distribution and execution
- Monitor progress and handle failures
- Manage checkpoints and rollbacks

**Key Methods:**
- `run()`: Main orchestration loop
- `_process_initial_analysis()`: Initial task analysis phase
- `_run_parallel_execution()`: Parallel task execution
- `_handle_worker_result()`: Process worker results
- `_run_final_review()`: Final review by Opus

### 3. Opus Manager (`manager.py`)

The intelligent task manager that uses Claude Opus for planning and oversight.

**Key Class: `OpusManager`**

**Responsibilities:**
- Analyze project requirements
- Create task execution plans
- Resolve task dependencies
- Delegate tasks to workers
- Review completed work

**Key Methods:**
- `analyze_and_plan()`: Analyze tasks and create execution plan
- `_sort_tasks_by_dependencies()`: Topological sort for dependencies
- `delegate_task()`: Assign task to worker queue
- `review_results()`: Review completed tasks

### 4. Sonnet Workers (`worker.py`)

Worker instances that use Claude Sonnet to execute individual tasks.

**Key Class: `SonnetWorker`**

**Responsibilities:**
- Execute assigned tasks
- Handle errors with retry logic
- Report progress and results
- Track token usage

**Key Methods:**
- `process_task()`: Main task execution method
- `_create_claude_prompt()`: Generate prompts for Claude
- `_execute_claude_command()`: Execute via CLI or API
- `_parse_claude_output()`: Parse and validate results

### 5. Data Models (`models.py`)

Core data structures used throughout the system.

**Key Classes:**
- `TaskStatus`: Enum for task states (PENDING, IN_PROGRESS, COMPLETED, FAILED, BLOCKED)
- `WorkerTask`: Data class representing a task to be executed

### 6. Configuration Manager (`config_manager.py`)

Advanced configuration system with validation and environment support.

**Key Class: `ConfigurationManager`**

**Features:**
- JSON schema validation
- Environment variable support
- Hierarchical configuration
- Default value management
- Configuration merging

### 7. Progress Display (`enhanced_progress_display.py`)

Real-time progress visualization system.

**Key Class: `EnhancedProgressDisplay`**

**Features:**
- Multi-worker progress tracking
- Real-time status updates
- Token usage monitoring
- Error display
- Beautiful terminal UI

## Supporting Systems

### 1. Task Master Integration

The system integrates with Task Master for persistent task storage and management.

**Interface: `TaskMasterInterface`**

**Key Methods:**
- `list_tasks()`: Retrieve all tasks
- `set_task_status()`: Update task status
- `update_subtask()`: Update subtask details
- `add_task()`: Create new task

### 2. Feedback System

Comprehensive feedback collection for continuous improvement.

**Components:**
- `FeedbackCollector`: Collects feedback during execution
- `FeedbackStorage`: Persists feedback data
- `FeedbackAnalyzer`: Analyzes feedback patterns

### 3. Rollback System

Checkpoint and rollback functionality for safe task execution.

**Key Class: `RollbackManager`**

**Features:**
- Checkpoint creation (manual/automatic)
- File snapshot management
- Task state preservation
- Rollback strategies (FULL, PARTIAL, SELECTIVE)

### 4. Security System

Security utilities for API key validation and error sanitization.

**Module: `security_utils.py`**

**Key Functions:**
- `validate_api_key()`: Validate API key format
- `sanitize_error_message()`: Remove sensitive data
- `check_file_permissions()`: Security audit
- `perform_security_audit()`: Comprehensive audit

## Communication Flow

### 1. Task Analysis Phase
```
User → CLI → Orchestrator → OpusManager → TaskMaster
                                ↓
                         Task Analysis
                                ↓
                         Execution Plan
```

### 2. Parallel Execution Phase
```
OpusManager → Task Queue → SonnetWorker[1]
                    ↓
                    → SonnetWorker[2]
                    ↓
                    → SonnetWorker[N]
                    
Workers → Claude API → Task Execution → Results
```

### 3. Review Phase
```
Workers → Completed Tasks → OpusManager
                               ↓
                         Final Review
                               ↓
                         User Results
```

## Configuration Structure

```json
{
  "models": {
    "manager": {
      "model": "claude-3-opus-20240229",
      "description": "Opus model for planning"
    },
    "worker": {
      "model": "claude-3-5-sonnet-20241022",
      "description": "Sonnet model for execution"
    }
  },
  "execution": {
    "max_workers": 3,
    "worker_timeout": 1800,
    "manager_timeout": 300,
    "max_retries": 3
  },
  "monitoring": {
    "progress_interval": 10,
    "verbose_logging": false,
    "show_progress_bar": true
  }
}
```

## Error Handling Strategy

### 1. Retry Logic
- Exponential backoff for transient failures
- Maximum retry attempts configurable
- Different strategies for different error types

### 2. Error Categories
- **Transient**: Network issues, rate limits
- **Permanent**: Invalid tasks, configuration errors
- **Recoverable**: Token limits, timeouts

### 3. Fallback Mechanisms
- Graceful degradation
- Task rescheduling
- Manual intervention requests

## Performance Considerations

### 1. Parallelization
- Worker pool size based on API limits
- Task dependency resolution
- Queue-based distribution

### 2. Resource Management
- Token usage tracking
- Memory-efficient task queuing
- Checkpoint size management

### 3. Optimization Strategies
- Batch similar tasks
- Reuse conversation context
- Progressive task refinement

## Security Architecture

### 1. API Key Management
- Environment variable storage
- Validation on startup
- No hardcoded credentials

### 2. Error Sanitization
- Remove sensitive data from logs
- Sanitize file paths
- Mask API keys in errors

### 3. File Permissions
- Secure .env file (600 permissions)
- Audit on startup
- Regular security checks

## Extension Points

### 1. Custom Workers
- Implement `BaseWorker` interface
- Register with orchestrator
- Custom execution strategies

### 2. Storage Backends
- Implement `StorageInterface`
- Support for databases
- Cloud storage integration

### 3. Notification Systems
- Implement `NotificationInterface`
- Multiple channel support
- Custom formatting

## Deployment Architecture

### 1. Single Instance
```
┌─────────────────┐
│   Orchestrator  │
│   + Workers     │
│   + Storage     │
└─────────────────┘
```

### 2. Distributed (Future)
```
┌─────────────┐     ┌─────────────┐
│ Orchestrator│────▶│  Worker[1]  │
└──────┬──────┘     └─────────────┘
       │            ┌─────────────┐
       ├───────────▶│  Worker[2]  │
       │            └─────────────┘
       │            ┌─────────────┐
       └───────────▶│  Worker[N]  │
                    └─────────────┘
```

## Monitoring and Observability

### 1. Logging
- Structured logging with levels
- Component-specific loggers
- Rotation and retention

### 2. Metrics
- Task completion rates
- Worker utilization
- Token usage tracking
- Error rates

### 3. Health Checks
- API connectivity
- Worker status
- Queue depth
- Resource usage

## Best Practices

### 1. Task Design
- Keep tasks atomic and focused
- Clear success criteria
- Proper dependency declaration

### 2. Configuration
- Use environment variables for secrets
- Version control config files
- Document all settings

### 3. Error Handling
- Always provide context
- Log before raising
- Clean up resources

### 4. Testing
- Unit tests for components
- Integration tests for workflows
- Load tests for scalability

---

**Version**: 1.0
**Last Updated**: 2025-01-07