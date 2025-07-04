# Feedback Storage System Documentation

## Overview

The Feedback Storage System provides a comprehensive solution for collecting, storing, and analyzing feedback throughout the Claude Orchestrator workflow. It uses SQLite for persistent storage and integrates seamlessly with the orchestrator's task execution pipeline.

## Architecture

### Core Components

1. **FeedbackStorage** (`feedback_storage.py`)
   - SQLite-based persistent storage
   - Thread-safe connection pooling
   - CRUD operations with transaction support
   - Query filtering and pagination

2. **FeedbackModels** (`feedback_models.py`)
   - Data structures and validation
   - Type-safe feedback entries
   - Metadata handling
   - Summary statistics

3. **FeedbackCollector** (`feedback_collector.py`)
   - Integration layer for the orchestrator
   - Collection point management
   - Feedback prompts and validation

## Data Model

### FeedbackEntry

The core data structure for feedback:

```python
@dataclass
class FeedbackEntry:
    id: str                    # Unique identifier
    task_id: str              # Associated task ID
    feedback_type: FeedbackType  # Type of feedback
    content: str              # Feedback content
    rating: Optional[int]     # 1-5 rating scale
    user_id: Optional[str]    # User who provided feedback
    metadata: FeedbackMetadata  # Additional context
    created_at: datetime      # Creation timestamp
    updated_at: datetime      # Last update timestamp
```

### FeedbackType Enum

Available feedback types:

```python
class FeedbackType(Enum):
    TASK_COMPLETION = "task_completion"
    WORKER_PERFORMANCE = "worker_performance"
    TASK_QUALITY = "task_quality"
    DECOMPOSITION_EFFECTIVENESS = "decomposition_effectiveness"
    ERROR_REPORT = "error_report"
    GENERAL = "general"
    MANAGER_REVIEW = "manager_review"
    ALLOCATION_FEEDBACK = "allocation_feedback"
```

### Database Schema

```sql
CREATE TABLE feedback (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    feedback_type TEXT NOT NULL,
    content TEXT NOT NULL,
    rating INTEGER,
    user_id TEXT,
    metadata TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    CONSTRAINT rating_range CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5))
);

CREATE INDEX idx_task_id ON feedback(task_id);
CREATE INDEX idx_feedback_type ON feedback(feedback_type);
CREATE INDEX idx_created_at ON feedback(created_at);
```

## Usage Guide

### Basic Setup

```python
from claude_orchestrator.feedback_storage import FeedbackStorage
from claude_orchestrator.feedback_models import FeedbackEntry, FeedbackType

# Initialize storage (creates database if not exists)
storage = FeedbackStorage(db_path="feedback.db")
```

### Creating Feedback

```python
from datetime import datetime
import uuid

# Create a feedback entry
feedback = FeedbackEntry(
    id=str(uuid.uuid4()),
    task_id="task-123",
    feedback_type=FeedbackType.TASK_COMPLETION,
    content="Task completed successfully with high quality output",
    rating=5,
    user_id="user-456",
    metadata={
        "execution_time": 45.3,
        "resources_used": ["claude-3", "gpu-1"],
        "output_quality": "excellent"
    },
    created_at=datetime.now(),
    updated_at=datetime.now()
)

# Store feedback
storage.create(feedback)
```

### Querying Feedback

```python
# Get feedback by ID
feedback = storage.get("feedback-id-123")

# Get all feedback for a task
task_feedback = storage.get_by_task("task-123")

# Get feedback by type
performance_feedback = storage.get_by_type(FeedbackType.WORKER_PERFORMANCE)

# Advanced filtering with pagination
filtered_feedback = storage.get_filtered(
    task_id="task-123",
    feedback_type=FeedbackType.TASK_COMPLETION,
    limit=10,
    offset=0
)
```

### Updating Feedback

```python
# Update existing feedback
feedback.content = "Updated feedback content"
feedback.rating = 4
feedback.updated_at = datetime.now()

storage.update(feedback)
```

### Deleting Feedback

```python
# Delete by ID
storage.delete("feedback-id-123")

# Delete all feedback for a task
for feedback in storage.get_by_task("task-123"):
    storage.delete(feedback.id)
```

### Summary Statistics

```python
# Get summary statistics for a task
summary = storage.get_summary("task-123")

print(f"Total feedback: {summary.total_count}")
print(f"Average rating: {summary.average_rating}")
print(f"Rating distribution: {summary.rating_distribution}")
print(f"Feedback by type: {summary.feedback_by_type}")
```

## Integration with Orchestrator

### Using FeedbackCollector

The FeedbackCollector provides high-level integration:

```python
from claude_orchestrator.feedback_collector import FeedbackCollector

collector = FeedbackCollector()

# Collect task completion feedback
await collector.collect_task_completion_feedback(
    task_id="task-123",
    worker_id="worker-456",
    success=True,
    execution_time=45.3,
    output_quality="high"
)

# Collect worker performance feedback
await collector.collect_worker_performance_feedback(
    worker_id="worker-456",
    task_id="task-123",
    performance_metrics={
        "speed": 0.9,
        "accuracy": 0.95,
        "resource_efficiency": 0.85
    }
)
```

### Integration Points

The feedback system integrates at these key points:

1. **Task Completion**
   ```python
   # In task completion handler
   if task.status == TaskStatus.COMPLETED:
       await collector.collect_task_completion_feedback(
           task_id=task.id,
           worker_id=task.assigned_worker,
           success=True
       )
   ```

2. **Worker Allocation**
   ```python
   # After worker allocation
   await collector.collect_allocation_feedback(
       task_id=task.id,
       worker_id=selected_worker,
       allocation_score=score,
       allocation_reason=reason
   )
   ```

3. **Error Handling**
   ```python
   # On task failure
   except Exception as e:
       await collector.collect_error_feedback(
           task_id=task.id,
           error_type=type(e).__name__,
           error_message=str(e),
           stack_trace=traceback.format_exc()
       )
   ```

## Advanced Features

### Batch Operations

```python
# Batch insert for performance
feedback_entries = [
    FeedbackEntry(...),
    FeedbackEntry(...),
    FeedbackEntry(...)
]

with storage.transaction():
    for entry in feedback_entries:
        storage.create(entry)
```

### Custom Queries

```python
# Execute custom SQL queries
results = storage.execute_query(
    """
    SELECT task_id, AVG(rating) as avg_rating, COUNT(*) as count
    FROM feedback
    WHERE feedback_type = ?
    GROUP BY task_id
    HAVING avg_rating > 4
    ORDER BY avg_rating DESC
    """,
    (FeedbackType.TASK_QUALITY.value,)
)
```

### Export and Backup

```python
# Export feedback to JSON
import json

all_feedback = storage.get_all()
with open("feedback_backup.json", "w") as f:
    json.dump(
        [fb.to_dict() for fb in all_feedback],
        f,
        indent=2,
        default=str
    )

# Import from JSON
with open("feedback_backup.json", "r") as f:
    feedback_data = json.load(f)
    
for data in feedback_data:
    feedback = FeedbackEntry.from_dict(data)
    storage.create(feedback)
```

## Best Practices

### 1. Use Transactions for Consistency

```python
with storage.transaction():
    # Multiple operations in a single transaction
    storage.create(feedback1)
    storage.update(feedback2)
    storage.delete(feedback3.id)
    # All succeed or all fail
```

### 2. Regular Cleanup

```python
from datetime import datetime, timedelta

# Delete old feedback
cutoff_date = datetime.now() - timedelta(days=90)
old_feedback = storage.execute_query(
    "SELECT id FROM feedback WHERE created_at < ?",
    (cutoff_date,)
)

for row in old_feedback:
    storage.delete(row[0])
```

### 3. Index Optimization

```python
# Create additional indexes for common queries
storage.execute_query(
    "CREATE INDEX IF NOT EXISTS idx_user_rating ON feedback(user_id, rating)"
)
```

### 4. Connection Management

```python
# Use context manager for automatic cleanup
with FeedbackStorage() as storage:
    feedback = storage.get_by_task("task-123")
    # Connection automatically closed
```

## Monitoring and Analytics

### Feedback Trends

```python
# Analyze feedback trends over time
query = """
    SELECT 
        DATE(created_at) as date,
        AVG(rating) as avg_rating,
        COUNT(*) as count
    FROM feedback
    WHERE created_at > datetime('now', '-30 days')
    GROUP BY DATE(created_at)
    ORDER BY date
"""

trends = storage.execute_query(query)
```

### Worker Performance Analysis

```python
# Analyze worker performance
query = """
    SELECT 
        metadata->>'$.worker_id' as worker_id,
        AVG(rating) as avg_rating,
        COUNT(*) as task_count
    FROM feedback
    WHERE feedback_type = 'worker_performance'
    GROUP BY metadata->>'$.worker_id'
    ORDER BY avg_rating DESC
"""

worker_stats = storage.execute_query(query)
```

## Error Handling

### Common Errors and Solutions

1. **Database Locked**
   ```python
   try:
       storage.create(feedback)
   except sqlite3.OperationalError as e:
       if "database is locked" in str(e):
           # Retry with exponential backoff
           time.sleep(0.1)
           storage.create(feedback)
   ```

2. **Constraint Violations**
   ```python
   try:
       feedback.rating = 6  # Invalid rating
       storage.create(feedback)
   except ValueError as e:
       logger.error(f"Invalid feedback data: {e}")
   ```

3. **Connection Issues**
   ```python
   # Use connection pooling for reliability
   storage = FeedbackStorage(
       db_path="feedback.db",
       pool_size=5,
       timeout=30.0
   )
   ```

## Performance Considerations

### Optimization Tips

1. **Batch Operations**: Use transactions for multiple operations
2. **Indexing**: Create indexes on frequently queried columns
3. **Connection Pooling**: Reuse connections for better performance
4. **Query Optimization**: Use EXPLAIN QUERY PLAN to optimize queries
5. **Regular Maintenance**: Run VACUUM periodically

### Benchmarks

Typical performance metrics:
- Single insert: ~1-2ms
- Batch insert (100 records): ~10-15ms
- Query by task_id: ~0.5-1ms
- Complex aggregation: ~5-10ms

## Security Considerations

### Input Validation

All input is validated before storage:
- Rating must be between 1-5
- Task IDs must exist
- Content length limits enforced
- SQL injection prevention through parameterized queries

### Data Privacy

- User IDs can be anonymized
- Sensitive metadata can be encrypted
- Regular data purging for compliance

## Summary

The Feedback Storage System provides a robust, scalable solution for feedback management in the Claude Orchestrator. By following these guidelines and best practices, you can effectively collect, store, and analyze feedback to improve task execution and system performance.