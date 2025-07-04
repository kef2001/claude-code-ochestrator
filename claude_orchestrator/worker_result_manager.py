"""
Worker Result Manager - Centralized result storage and retrieval system
"""
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ResultStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class WorkerResult:
    """Structured worker result with metadata"""
    task_id: str
    worker_id: str
    status: ResultStatus
    output: str
    created_files: List[str]
    modified_files: List[str]
    execution_time: float
    tokens_used: int
    timestamp: str
    error_message: Optional[str] = None
    validation_passed: bool = False
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkerResult':
        data['status'] = ResultStatus(data['status'])
        return cls(**data)


class WorkerResultManager:
    """Manages worker results with persistent storage and validation"""
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path(".taskmaster/results.db")
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database for result storage"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS worker_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output TEXT,
                    created_files TEXT,
                    modified_files TEXT,
                    execution_time REAL,
                    tokens_used INTEGER,
                    timestamp TEXT NOT NULL,
                    error_message TEXT,
                    validation_passed BOOLEAN DEFAULT 0,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(task_id, timestamp)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_id ON worker_results(task_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_worker_id ON worker_results(worker_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON worker_results(status)
            """)
            
    def store_result(self, result: WorkerResult) -> int:
        """Store a worker result and return the result ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO worker_results (
                    task_id, worker_id, status, output, created_files,
                    modified_files, execution_time, tokens_used, timestamp,
                    error_message, validation_passed, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.task_id,
                result.worker_id,
                result.status.value,
                result.output,
                json.dumps(result.created_files),
                json.dumps(result.modified_files),
                result.execution_time,
                result.tokens_used,
                result.timestamp,
                result.error_message,
                result.validation_passed,
                json.dumps(result.metadata) if result.metadata else None
            ))
            
            result_id = cursor.lastrowid
            logger.info(f"Stored result {result_id} for task {result.task_id}")
            return result_id
            
    def get_latest_result(self, task_id: str) -> Optional[WorkerResult]:
        """Get the most recent result for a task"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM worker_results 
                WHERE task_id = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (task_id,))
            
            row = cursor.fetchone()
            if row:
                return self._row_to_result(row)
            return None
            
    def get_all_results(self, task_id: str) -> List[WorkerResult]:
        """Get all results for a task (history)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM worker_results 
                WHERE task_id = ? 
                ORDER BY created_at DESC
            """, (task_id,))
            
            return [self._row_to_result(row) for row in cursor]
            
    def get_results_by_status(self, status: ResultStatus) -> List[WorkerResult]:
        """Get all results with a specific status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM worker_results 
                WHERE status = ? 
                ORDER BY created_at DESC
            """, (status.value,))
            
            return [self._row_to_result(row) for row in cursor]
            
    def validate_result(self, task_id: str) -> Tuple[bool, str]:
        """Validate that a task result meets requirements"""
        result = self.get_latest_result(task_id)
        if not result:
            return False, "No result found for task"
            
        # Check basic success
        if result.status != ResultStatus.SUCCESS:
            return False, f"Task failed with status: {result.status.value}"
            
        # Check if files were created when expected
        if not result.created_files and not result.modified_files:
            # Check if the output mentions creating files
            output_lower = result.output.lower()
            if any(word in output_lower for word in ['created', 'wrote', 'generated', 'implemented']):
                return False, "Worker claimed to create files but no files were recorded"
                
        # Check for generic responses
        generic_phrases = [
            "i have successfully completed",
            "the task has been completed",
            "i've completed the task",
            "task completed successfully"
        ]
        
        output_lower = result.output.lower()
        if any(phrase in output_lower for phrase in generic_phrases) and len(result.output) < 200:
            return False, "Worker provided generic response without implementation details"
            
        return True, "Validation passed"
        
    def mark_validated(self, task_id: str, validated: bool = True):
        """Mark a result as validated"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE worker_results 
                SET validation_passed = ? 
                WHERE task_id = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (validated, task_id))
            
    def _row_to_result(self, row: sqlite3.Row) -> WorkerResult:
        """Convert database row to WorkerResult"""
        return WorkerResult(
            task_id=row['task_id'],
            worker_id=row['worker_id'],
            status=ResultStatus(row['status']),
            output=row['output'],
            created_files=json.loads(row['created_files']),
            modified_files=json.loads(row['modified_files']),
            execution_time=row['execution_time'],
            tokens_used=row['tokens_used'],
            timestamp=row['timestamp'],
            error_message=row['error_message'],
            validation_passed=bool(row['validation_passed']),
            metadata=json.loads(row['metadata']) if row['metadata'] else None
        )
        
    def get_worker_stats(self, worker_id: str) -> Dict[str, Any]:
        """Get statistics for a specific worker"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_tasks,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_tasks,
                    AVG(execution_time) as avg_execution_time,
                    SUM(tokens_used) as total_tokens_used,
                    SUM(CASE WHEN validation_passed THEN 1 ELSE 0 END) as validated_tasks
                FROM worker_results
                WHERE worker_id = ?
            """, (worker_id,))
            
            row = cursor.fetchone()
            return {
                'total_tasks': row[0] or 0,
                'successful_tasks': row[1] or 0,
                'failed_tasks': row[2] or 0,
                'avg_execution_time': row[3] or 0,
                'total_tokens_used': row[4] or 0,
                'validated_tasks': row[5] or 0
            }
            
    def cleanup_old_results(self, days: int = 30):
        """Remove results older than specified days"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM worker_results
                WHERE created_at < datetime('now', '-' || ? || ' days')
            """, (days,))