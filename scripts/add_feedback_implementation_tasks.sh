#!/bin/bash
# Add follow-up tasks for SQLite feedback storage implementation

echo "Creating follow-up tasks for SQLite feedback storage implementation..."

# Task 1: SQLite database setup
python3 -m claude_orchestrator.task_master add \
  --title "Create SQLite database schema and connection manager" \
  --description "Create feedback_storage.py in claude_orchestrator/ with: SQLiteConnection class for managing database connections, Database initialization with feedback table schema (id, task_id, feedback_type, content, metadata, created_at, updated_at), Schema migration support, Connection pooling, Proper error handling and logging" \
  --priority high \
  --details "Tags: feedback-storage, sqlite, database, followup, opus-manager-review"

# Task 2: Feedback model
python3 -m claude_orchestrator.task_master add \
  --title "Implement Feedback model and CRUD operations" \
  --description "Create feedback_model.py in claude_orchestrator/ with: Feedback dataclass with proper typing, CRUD operations (create, get, update, delete), Query methods (by task_id, by type, by date range), Batch operations support, Input validation and sanitization" \
  --priority high \
  --details "Tags: feedback-storage, model, crud, followup, opus-manager-review"

# Task 3: Integration layer
python3 -m claude_orchestrator.task_master add \
  --title "Create feedback storage integration layer" \
  --description "Integrate feedback storage with orchestrator: Add feedback hooks to task completion, Create feedback submission methods for workers and managers, Add API endpoints for feedback operations, Implement async operation support, Add feedback retrieval to task context, Update task_master.py to include feedback references" \
  --priority high \
  --details "Tags: feedback-storage, integration, followup, opus-manager-review"

# Task 4: Testing
python3 -m claude_orchestrator.task_master add \
  --title "Write comprehensive tests for feedback storage" \
  --description "Create test_feedback_storage.py in tests/ with: Unit tests for SQLite connection and schema, Tests for all CRUD operations, Edge case testing, Integration tests with orchestrator, Performance tests for large datasets, Concurrent access tests, Migration tests, Mock database for testing" \
  --priority medium \
  --details "Tags: feedback-storage, testing, followup"

# Task 5: CLI commands
python3 -m claude_orchestrator.task_master add \
  --title "Add feedback CLI commands" \
  --description "Extend task_master.py with feedback commands: feedback add, feedback list, feedback get, feedback update, feedback delete, Add feedback display to task show command" \
  --priority medium \
  --details "Tags: feedback-storage, cli, followup"

echo "✅ Follow-up tasks created for SQLite feedback storage implementation"