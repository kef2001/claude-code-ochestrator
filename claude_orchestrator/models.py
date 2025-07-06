"""Data models for Claude Orchestrator.

This module contains all data classes, enums, and type definitions
used throughout the orchestrator system.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class TaskStatus(Enum):
    """Status of a task in the orchestration system."""
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    COMPLETED = "done"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class WorkerTask:
    """Task to be processed by a Sonnet worker.
    
    Attributes:
        task_id: Unique identifier for the task
        title: Short title describing the task
        description: Detailed description of what needs to be done
        details: Optional additional details or requirements
        dependencies: List of task IDs this task depends on
        status: Current status of the task
        assigned_worker: ID of the worker assigned to this task
        result: Result output from task execution
        error: Error message if task failed
        status_message: Additional status information
    """
    task_id: str
    title: str
    description: str
    details: Optional[str] = None
    dependencies: List[str] = None
    status: TaskStatus = TaskStatus.PENDING
    assigned_worker: Optional[int] = None
    result: Optional[str] = None
    error: Optional[str] = None
    status_message: Optional[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []