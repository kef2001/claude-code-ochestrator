"""
Feedback Storage Layer for Claude Orchestrator

This module provides persistent storage for feedback data using SQLite database.
Based on requirements from add_feedback_storage_tasks.py and Task 2 specifications.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from contextlib import contextmanager
import threading
import json
from dataclasses import asdict

from .feedback_models import FeedbackEntry, FeedbackType, RatingScale, FeedbackSummary


logger = logging.getLogger(__name__)


class FeedbackStorageError(Exception):
    """Base exception for feedback storage operations"""
    pass


class FeedbackNotFoundError(FeedbackStorageError):
    """Raised when feedback entry is not found"""
    pass


class FeedbackStorage:
    """
    SQLite-based storage backend for feedback data
    
    Provides CRUD operations for feedback entries with proper transaction support,
    connection pooling, and error handling.
    """
    
    def __init__(self, db_path: Union[str, Path] = "feedback.db"):
        """
        Initialize feedback storage with SQLite database
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._local = threading.local()
        self._lock = threading.Lock()
        
        # Create database and tables if they don't exist
        self._initialize_database()
        
        logger.info(f"Initialized FeedbackStorage with database: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
            # Enable foreign key constraints
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection
    
    @contextmanager
    def _transaction(self):
        """Context manager for database transactions"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def _initialize_database(self):
        """Create database schema if it doesn't exist"""
        with self._transaction() as conn:
            # Create feedback table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
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
                )
            """)
            
            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_task_id ON feedback(task_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(feedback_type)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at)
            """)
            
            logger.info("Database schema initialized successfully")
    
    def create_feedback(self, feedback_entry: FeedbackEntry) -> str:
        """
        Create a new feedback entry
        
        Args:
            feedback_entry: FeedbackEntry instance to store
            
        Returns:
            str: The ID of the created feedback entry
            
        Raises:
            FeedbackStorageError: If creation fails
        """
        try:
            with self._transaction() as conn:
                # Convert metadata to JSON if present
                metadata_json = None
                if feedback_entry.metadata:
                    metadata_json = json.dumps(feedback_entry.metadata.to_dict())
                
                conn.execute("""
                    INSERT INTO feedback (
                        id, task_id, feedback_type, content, rating, 
                        user_id, metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    feedback_entry.id,
                    feedback_entry.task_id,
                    feedback_entry.feedback_type.value,
                    feedback_entry.content,
                    feedback_entry.rating.value if feedback_entry.rating else None,
                    feedback_entry.user_id,
                    metadata_json,
                    feedback_entry.timestamp.isoformat(),
                    feedback_entry.timestamp.isoformat()
                ))
                
                logger.info(f"Created feedback entry: {feedback_entry.id}")
                return feedback_entry.id
                
        except sqlite3.Error as e:
            logger.error(f"Failed to create feedback: {e}")
            raise FeedbackStorageError(f"Failed to create feedback: {e}")
    
    def get_feedback(self, feedback_id: str) -> Optional[FeedbackEntry]:
        """
        Retrieve a single feedback entry by ID
        
        Args:
            feedback_id: ID of the feedback entry
            
        Returns:
            FeedbackEntry or None if not found
            
        Raises:
            FeedbackStorageError: If retrieval fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT * FROM feedback WHERE id = ?
            """, (feedback_id,))
            
            row = cursor.fetchone()
            if row:
                return self._row_to_feedback_entry(row)
            return None
            
        except sqlite3.Error as e:
            logger.error(f"Failed to get feedback {feedback_id}: {e}")
            raise FeedbackStorageError(f"Failed to get feedback: {e}")
    
    def get_feedback_by_task(self, task_id: str) -> List[FeedbackEntry]:
        """
        Get all feedback entries for a specific task
        
        Args:
            task_id: ID of the task
            
        Returns:
            List of FeedbackEntry objects
            
        Raises:
            FeedbackStorageError: If retrieval fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT * FROM feedback 
                WHERE task_id = ? 
                ORDER BY created_at DESC
            """, (task_id,))
            
            return [self._row_to_feedback_entry(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"Failed to get feedback for task {task_id}: {e}")
            raise FeedbackStorageError(f"Failed to get feedback for task: {e}")
    
    def update_feedback(self, feedback_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing feedback entry
        
        Args:
            feedback_id: ID of the feedback entry to update
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if update was successful, False if entry not found
            
        Raises:
            FeedbackStorageError: If update fails
        """
        try:
            # Build dynamic update query
            set_clauses = []
            values = []
            
            allowed_fields = ['content', 'rating', 'feedback_type']
            for field, value in updates.items():
                if field in allowed_fields:
                    set_clauses.append(f"{field} = ?")
                    if field == 'rating' and value is not None:
                        values.append(value.value if isinstance(value, RatingScale) else value)
                    elif field == 'feedback_type':
                        values.append(value.value if isinstance(value, FeedbackType) else value)
                    else:
                        values.append(value)
            
            if not set_clauses:
                logger.warning(f"No valid fields to update for feedback {feedback_id}")
                return False
            
            # Add updated timestamp
            set_clauses.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(feedback_id)
            
            with self._transaction() as conn:
                cursor = conn.execute(f"""
                    UPDATE feedback 
                    SET {', '.join(set_clauses)}
                    WHERE id = ?
                """, values)
                
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"Updated feedback entry: {feedback_id}")
                else:
                    logger.warning(f"Feedback entry not found: {feedback_id}")
                return success
                
        except sqlite3.Error as e:
            logger.error(f"Failed to update feedback {feedback_id}: {e}")
            raise FeedbackStorageError(f"Failed to update feedback: {e}")
    
    def delete_feedback(self, feedback_id: str) -> bool:
        """
        Delete a feedback entry
        
        Args:
            feedback_id: ID of the feedback entry to delete
            
        Returns:
            bool: True if deletion was successful, False if entry not found
            
        Raises:
            FeedbackStorageError: If deletion fails
        """
        try:
            with self._transaction() as conn:
                cursor = conn.execute("""
                    DELETE FROM feedback WHERE id = ?
                """, (feedback_id,))
                
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"Deleted feedback entry: {feedback_id}")
                else:
                    logger.warning(f"Feedback entry not found: {feedback_id}")
                return success
                
        except sqlite3.Error as e:
            logger.error(f"Failed to delete feedback {feedback_id}: {e}")
            raise FeedbackStorageError(f"Failed to delete feedback: {e}")
    
    def list_feedback(
        self, 
        task_id: Optional[str] = None,
        feedback_type: Optional[FeedbackType] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[FeedbackEntry]:
        """
        List feedback entries with optional filtering
        
        Args:
            task_id: Filter by task ID
            feedback_type: Filter by feedback type
            limit: Maximum number of entries to return
            offset: Number of entries to skip
            
        Returns:
            List of FeedbackEntry objects
            
        Raises:
            FeedbackStorageError: If query fails
        """
        try:
            conditions = []
            values = []
            
            if task_id:
                conditions.append("task_id = ?")
                values.append(task_id)
            
            if feedback_type:
                conditions.append("feedback_type = ?")
                values.append(feedback_type.value)
            
            where_clause = ""
            if conditions:
                where_clause = f"WHERE {' AND '.join(conditions)}"
            
            limit_clause = ""
            if limit:
                limit_clause = f"LIMIT {limit} OFFSET {offset}"
            
            conn = self._get_connection()
            cursor = conn.execute(f"""
                SELECT * FROM feedback 
                {where_clause}
                ORDER BY created_at DESC
                {limit_clause}
            """, values)
            
            return [self._row_to_feedback_entry(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"Failed to list feedback: {e}")
            raise FeedbackStorageError(f"Failed to list feedback: {e}")
    
    def get_feedback_summary(self, task_id: str) -> FeedbackSummary:
        """
        Get summary statistics for feedback on a specific task
        
        Args:
            task_id: ID of the task
            
        Returns:
            FeedbackSummary with aggregated statistics
            
        Raises:
            FeedbackStorageError: If query fails
        """
        try:
            feedback_entries = self.get_feedback_by_task(task_id)
            
            # Use the existing function from feedback_models
            from .feedback_models import calculate_feedback_summary
            return calculate_feedback_summary(feedback_entries)
            
        except Exception as e:
            logger.error(f"Failed to calculate feedback summary for task {task_id}: {e}")
            raise FeedbackStorageError(f"Failed to calculate feedback summary: {e}")
    
    def _row_to_feedback_entry(self, row: sqlite3.Row) -> FeedbackEntry:
        """Convert database row to FeedbackEntry object"""
        from .feedback_models import FeedbackMetadata
        
        # Parse metadata if present
        metadata = None
        if row['metadata']:
            metadata_dict = json.loads(row['metadata'])
            metadata = FeedbackMetadata.from_dict(metadata_dict)
        
        return FeedbackEntry(
            id=row['id'],
            task_id=row['task_id'],
            timestamp=datetime.fromisoformat(row['created_at']),
            feedback_type=FeedbackType(row['feedback_type']),
            content=row['content'],
            rating=RatingScale(row['rating']) if row['rating'] else None,
            user_id=row['user_id'],
            metadata=metadata
        )
    
    def close(self):
        """Close database connections"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')
        logger.info("Closed feedback storage connections")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def create_feedback_storage(db_path: Optional[str] = None) -> FeedbackStorage:
    """
    Factory function to create a FeedbackStorage instance
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        FeedbackStorage instance
    """
    if db_path is None:
        db_path = "feedback.db"
    
    return FeedbackStorage(db_path)