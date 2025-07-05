"""SQLite-based feedback storage implementation"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import contextmanager

from .feedback_model import FeedbackModel, FeedbackType, FeedbackSeverity, FeedbackCategory
from .feedback_storage import FeedbackStorageInterface

logger = logging.getLogger(__name__)


class SQLiteFeedbackStorage(FeedbackStorageInterface):
    """SQLite implementation of feedback storage"""
    
    def __init__(self, db_path: str = ".feedback/feedback.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        
    def _init_database(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create feedback table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    worker_id TEXT,
                    session_id TEXT,
                    feedback_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    message TEXT,
                    context TEXT,
                    metrics TEXT,
                    tags TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_id ON feedback(task_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_worker_id ON feedback(worker_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON feedback(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(feedback_type)")
            
            conn.commit()
            
        logger.info(f"SQLite database initialized at {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def save(self, feedback: FeedbackModel) -> None:
        """Save feedback to database"""
        feedback.validate()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Serialize complex fields
            context = json.dumps(feedback.context.__dict__)
            metrics = json.dumps(feedback.metrics.__dict__ if feedback.metrics else {})
            tags = json.dumps(feedback.context.tags)
            
            cursor.execute("""
                INSERT OR REPLACE INTO feedback (
                    feedback_id, task_id, worker_id, session_id,
                    feedback_type, severity, category, timestamp,
                    message, context, metrics, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback.feedback_id,
                feedback.context.task_id,
                feedback.context.worker_id,
                feedback.context.session_id,
                feedback.feedback_type.value,
                feedback.severity.value,
                feedback.category.value,
                feedback.timestamp.isoformat(),
                feedback.message,
                context,
                metrics,
                tags
            ))
            
            conn.commit()
            
        logger.debug(f"Saved feedback {feedback.feedback_id} to SQLite")
    
    def load(self, feedback_id: str) -> Optional[FeedbackModel]:
        """Load feedback by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM feedback WHERE feedback_id = ?",
                (feedback_id,)
            )
            
            row = cursor.fetchone()
            if not row:
                return None
                
            return self._row_to_feedback(row)
    
    def query(self, **kwargs) -> List[FeedbackModel]:
        """Query feedback with filters"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query
            conditions = []
            params = []
            
            if kwargs.get('task_id'):
                conditions.append("task_id = ?")
                params.append(kwargs['task_id'])
                
            if kwargs.get('worker_id'):
                conditions.append("worker_id = ?")
                params.append(kwargs['worker_id'])
                
            if kwargs.get('feedback_type'):
                conditions.append("feedback_type = ?")
                params.append(kwargs['feedback_type'].value)
                
            if kwargs.get('severity'):
                conditions.append("severity = ?")
                params.append(kwargs['severity'].value)
                
            if kwargs.get('start_time'):
                conditions.append("timestamp >= ?")
                params.append(kwargs['start_time'].isoformat())
                
            if kwargs.get('end_time'):
                conditions.append("timestamp <= ?")
                params.append(kwargs['end_time'].isoformat())
            
            # Build final query
            query = "SELECT * FROM feedback"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY timestamp DESC"
            
            if kwargs.get('limit'):
                query += f" LIMIT {kwargs['limit']}"
            
            cursor.execute(query, params)
            
            return [self._row_to_feedback(row) for row in cursor.fetchall()]
    
    def delete(self, feedback_id: str) -> bool:
        """Delete feedback by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM feedback WHERE feedback_id = ?", (feedback_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def clear(self) -> None:
        """Clear all feedback"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM feedback")
            conn.commit()
            
    def count(self) -> int:
        """Count total feedback entries"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM feedback")
            return cursor.fetchone()[0]
    
    def _row_to_feedback(self, row: sqlite3.Row) -> FeedbackModel:
        """Convert database row to FeedbackModel"""
        # Parse JSON fields
        context_dict = json.loads(row['context'])
        metrics_dict = json.loads(row['metrics']) if row['metrics'] else None
        
        # Import FeedbackContext to properly reconstruct it
        from .feedback_model import FeedbackContext, FeedbackMetrics
        
        # Reconstruct context
        context = FeedbackContext(
            task_id=context_dict.get('task_id'),
            worker_id=context_dict.get('worker_id'),
            session_id=context_dict.get('session_id'),
            parent_task_id=context_dict.get('parent_task_id'),
            tags=context_dict.get('tags', []),
            environment=context_dict.get('environment', {})
        )
        
        # Reconstruct metrics if present
        metrics = None
        if metrics_dict:
            metrics = FeedbackMetrics(
                execution_time=metrics_dict.get('execution_time'),
                memory_usage=metrics_dict.get('memory_usage'),
                cpu_usage=metrics_dict.get('cpu_usage'),
                tokens_used=metrics_dict.get('tokens_used'),
                quality_score=metrics_dict.get('quality_score'),
                success_rate=metrics_dict.get('success_rate'),
                custom_metrics=metrics_dict.get('custom_metrics', {})
            )
        
        # Reconstruct FeedbackModel
        return FeedbackModel(
            feedback_id=row['feedback_id'],
            feedback_type=FeedbackType(row['feedback_type']),
            severity=FeedbackSeverity(row['severity']),
            category=FeedbackCategory(row['category']),
            timestamp=datetime.fromisoformat(row['timestamp']),
            message=row['message'],
            context=context,
            metrics=metrics
        )