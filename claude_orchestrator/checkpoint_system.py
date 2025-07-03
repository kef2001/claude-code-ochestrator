"""
Checkpoint System for Long-Running Tasks
Provides task state persistence and recovery capabilities
"""

import json
import os
import time
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import pickle
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class CheckpointState(Enum):
    """Checkpoint states"""
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    RESTORED = "restored"


@dataclass
class CheckpointData:
    """Checkpoint data structure"""
    checkpoint_id: str
    task_id: str
    task_title: str
    state: CheckpointState
    step_number: int
    total_steps: Optional[int] = None
    step_description: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    worker_id: Optional[str] = None
    parent_checkpoint_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['created_at'] = self.created_at.isoformat()
        result['updated_at'] = self.updated_at.isoformat()
        result['state'] = self.state.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckpointData':
        """Create from dictionary"""
        data = data.copy()
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        data['state'] = CheckpointState(data['state'])
        return cls(**data)


class CheckpointManager:
    """
    Manages checkpoints for long-running tasks
    """
    
    def __init__(self, storage_dir: str = ".taskmaster/checkpoints"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.active_checkpoints: Dict[str, CheckpointData] = {}
        self._lock = threading.Lock()
        
        # Load existing checkpoints
        self._load_checkpoints()
        
        logger.info(f"Checkpoint manager initialized with storage: {self.storage_dir}")
    
    def _load_checkpoints(self):
        """Load existing checkpoints from storage"""
        try:
            for checkpoint_file in self.storage_dir.glob("checkpoint_*.json"):
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        checkpoint_data = json.load(f)
                        checkpoint = CheckpointData.from_dict(checkpoint_data)
                        
                        # Only load active checkpoints
                        if checkpoint.state in [CheckpointState.ACTIVE, CheckpointState.CREATED]:
                            self.active_checkpoints[checkpoint.checkpoint_id] = checkpoint
                            
                except Exception as e:
                    logger.error(f"Error loading checkpoint {checkpoint_file}: {e}")
                    
            logger.info(f"Loaded {len(self.active_checkpoints)} active checkpoints")
            
        except Exception as e:
            logger.error(f"Error loading checkpoints: {e}")
    
    def create_checkpoint(self, task_id: str, task_title: str, 
                         step_number: int, step_description: str = "",
                         total_steps: Optional[int] = None,
                         data: Optional[Dict[str, Any]] = None,
                         metadata: Optional[Dict[str, Any]] = None,
                         worker_id: Optional[str] = None,
                         parent_checkpoint_id: Optional[str] = None) -> str:
        """
        Create a new checkpoint
        
        Args:
            task_id: Task identifier
            task_title: Task title
            step_number: Current step number
            step_description: Description of current step
            total_steps: Total number of steps (if known)
            data: Checkpoint data
            metadata: Additional metadata
            worker_id: Worker processing this task
            parent_checkpoint_id: Parent checkpoint ID for hierarchical checkpoints
            
        Returns:
            Checkpoint ID
        """
        with self._lock:
            checkpoint_id = f"cp_{task_id}_{step_number}_{int(time.time())}"
            
            checkpoint = CheckpointData(
                checkpoint_id=checkpoint_id,
                task_id=task_id,
                task_title=task_title,
                state=CheckpointState.CREATED,
                step_number=step_number,
                total_steps=total_steps,
                step_description=step_description,
                data=data or {},
                metadata=metadata or {},
                worker_id=worker_id,
                parent_checkpoint_id=parent_checkpoint_id
            )
            
            self.active_checkpoints[checkpoint_id] = checkpoint
            self._save_checkpoint(checkpoint)
            
            logger.info(f"Created checkpoint {checkpoint_id} for task {task_id} at step {step_number}")
            return checkpoint_id
    
    def update_checkpoint(self, checkpoint_id: str, 
                         step_number: Optional[int] = None,
                         step_description: Optional[str] = None,
                         data: Optional[Dict[str, Any]] = None,
                         metadata: Optional[Dict[str, Any]] = None,
                         state: Optional[CheckpointState] = None) -> bool:
        """
        Update an existing checkpoint
        
        Args:
            checkpoint_id: Checkpoint ID to update
            step_number: New step number
            step_description: New step description
            data: New data (will be merged with existing)
            metadata: New metadata (will be merged with existing)
            state: New state
            
        Returns:
            True if updated successfully
        """
        with self._lock:
            if checkpoint_id not in self.active_checkpoints:
                logger.error(f"Checkpoint {checkpoint_id} not found")
                return False
            
            checkpoint = self.active_checkpoints[checkpoint_id]
            
            if step_number is not None:
                checkpoint.step_number = step_number
            if step_description is not None:
                checkpoint.step_description = step_description
            if data is not None:
                checkpoint.data.update(data)
            if metadata is not None:
                checkpoint.metadata.update(metadata)
            if state is not None:
                checkpoint.state = state
            
            checkpoint.updated_at = datetime.now()
            self._save_checkpoint(checkpoint)
            
            logger.debug(f"Updated checkpoint {checkpoint_id}")
            return True
    
    def complete_checkpoint(self, checkpoint_id: str, 
                          final_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark checkpoint as completed
        
        Args:
            checkpoint_id: Checkpoint ID to complete
            final_data: Final data to store
            
        Returns:
            True if completed successfully
        """
        with self._lock:
            if checkpoint_id not in self.active_checkpoints:
                logger.error(f"Checkpoint {checkpoint_id} not found")
                return False
            
            checkpoint = self.active_checkpoints[checkpoint_id]
            checkpoint.state = CheckpointState.COMPLETED
            checkpoint.updated_at = datetime.now()
            
            if final_data:
                checkpoint.data.update(final_data)
            
            self._save_checkpoint(checkpoint)
            
            # Remove from active checkpoints
            del self.active_checkpoints[checkpoint_id]
            
            logger.info(f"Completed checkpoint {checkpoint_id}")
            return True
    
    def fail_checkpoint(self, checkpoint_id: str, 
                       error_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark checkpoint as failed
        
        Args:
            checkpoint_id: Checkpoint ID to fail
            error_info: Error information
            
        Returns:
            True if failed successfully
        """
        with self._lock:
            if checkpoint_id not in self.active_checkpoints:
                logger.error(f"Checkpoint {checkpoint_id} not found")
                return False
            
            checkpoint = self.active_checkpoints[checkpoint_id]
            checkpoint.state = CheckpointState.FAILED
            checkpoint.updated_at = datetime.now()
            
            if error_info:
                checkpoint.metadata['error_info'] = error_info
            
            self._save_checkpoint(checkpoint)
            
            # Remove from active checkpoints
            del self.active_checkpoints[checkpoint_id]
            
            logger.error(f"Failed checkpoint {checkpoint_id}")
            return True
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointData]:
        """Get checkpoint by ID"""
        with self._lock:
            return self.active_checkpoints.get(checkpoint_id)
    
    def get_task_checkpoints(self, task_id: str) -> List[CheckpointData]:
        """Get all checkpoints for a task"""
        with self._lock:
            return [cp for cp in self.active_checkpoints.values() if cp.task_id == task_id]
    
    def get_latest_checkpoint(self, task_id: str) -> Optional[CheckpointData]:
        """Get the latest checkpoint for a task"""
        task_checkpoints = self.get_task_checkpoints(task_id)
        if not task_checkpoints:
            return None
        
        return max(task_checkpoints, key=lambda cp: cp.step_number)
    
    def restore_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointData]:
        """
        Restore a checkpoint (load from storage if needed)
        
        Args:
            checkpoint_id: Checkpoint ID to restore
            
        Returns:
            Restored checkpoint data
        """
        with self._lock:
            # First check if it's already in active checkpoints
            if checkpoint_id in self.active_checkpoints:
                return self.active_checkpoints[checkpoint_id]
            
            # Try to load from storage
            checkpoint_file = self.storage_dir / f"checkpoint_{checkpoint_id}.json"
            if checkpoint_file.exists():
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        checkpoint_data = json.load(f)
                        checkpoint = CheckpointData.from_dict(checkpoint_data)
                        
                        # Mark as restored
                        checkpoint.state = CheckpointState.RESTORED
                        checkpoint.updated_at = datetime.now()
                        
                        # Add to active checkpoints
                        self.active_checkpoints[checkpoint_id] = checkpoint
                        self._save_checkpoint(checkpoint)
                        
                        logger.info(f"Restored checkpoint {checkpoint_id}")
                        return checkpoint
                        
                except Exception as e:
                    logger.error(f"Error restoring checkpoint {checkpoint_id}: {e}")
                    return None
            
            logger.warning(f"Checkpoint {checkpoint_id} not found in storage")
            return None
    
    def _save_checkpoint(self, checkpoint: CheckpointData):
        """Save checkpoint to storage"""
        try:
            checkpoint_file = self.storage_dir / f"checkpoint_{checkpoint.checkpoint_id}.json"
            
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving checkpoint {checkpoint.checkpoint_id}: {e}")
    
    def cleanup_old_checkpoints(self, max_age_days: int = 30):
        """
        Clean up old completed/failed checkpoints
        
        Args:
            max_age_days: Maximum age in days for checkpoints to keep
        """
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        deleted_count = 0
        
        try:
            for checkpoint_file in self.storage_dir.glob("checkpoint_*.json"):
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        checkpoint_data = json.load(f)
                        
                    updated_at = datetime.fromisoformat(checkpoint_data['updated_at'])
                    state = CheckpointState(checkpoint_data['state'])
                    
                    # Only delete completed/failed checkpoints older than cutoff
                    if (state in [CheckpointState.COMPLETED, CheckpointState.FAILED] and 
                        updated_at < cutoff_date):
                        checkpoint_file.unlink()
                        deleted_count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing checkpoint file {checkpoint_file}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old checkpoints")
            
        except Exception as e:
            logger.error(f"Error during checkpoint cleanup: {e}")
    
    def get_checkpoint_summary(self) -> Dict[str, Any]:
        """Get summary of all checkpoints"""
        with self._lock:
            active_count = len(self.active_checkpoints)
            
            # Count checkpoints by state
            state_counts = {}
            for checkpoint in self.active_checkpoints.values():
                state = checkpoint.state.value
                state_counts[state] = state_counts.get(state, 0) + 1
            
            # Get tasks with checkpoints
            task_ids = set(cp.task_id for cp in self.active_checkpoints.values())
            
            return {
                "active_checkpoints": active_count,
                "tasks_with_checkpoints": len(task_ids),
                "state_counts": state_counts,
                "storage_dir": str(self.storage_dir)
            }
    
    @contextmanager
    def checkpoint_context(self, task_id: str, task_title: str, 
                          step_number: int, step_description: str = "",
                          total_steps: Optional[int] = None,
                          worker_id: Optional[str] = None):
        """
        Context manager for automatic checkpoint management
        
        Usage:
            with checkpoint_manager.checkpoint_context(
                task_id="task_1", 
                task_title="Example Task",
                step_number=1,
                step_description="Processing data"
            ) as checkpoint_id:
                # Do work
                checkpoint_manager.update_checkpoint(
                    checkpoint_id, 
                    data={"progress": 50}
                )
                # Work completed automatically
        """
        checkpoint_id = self.create_checkpoint(
            task_id=task_id,
            task_title=task_title,
            step_number=step_number,
            step_description=step_description,
            total_steps=total_steps,
            worker_id=worker_id
        )
        
        try:
            # Mark as active
            self.update_checkpoint(checkpoint_id, state=CheckpointState.ACTIVE)
            yield checkpoint_id
            
            # Mark as completed if no exception
            self.complete_checkpoint(checkpoint_id)
            
        except Exception as e:
            # Mark as failed on exception
            self.fail_checkpoint(checkpoint_id, error_info={
                "exception": str(e),
                "exception_type": type(e).__name__
            })
            raise


class TaskCheckpointWrapper:
    """
    Wrapper for tasks to automatically create checkpoints
    """
    
    def __init__(self, checkpoint_manager: CheckpointManager, 
                 task_id: str, task_title: str, worker_id: str = None):
        self.checkpoint_manager = checkpoint_manager
        self.task_id = task_id
        self.task_title = task_title
        self.worker_id = worker_id
        self.current_step = 0
        self.total_steps = None
        self.current_checkpoint_id = None
    
    def set_total_steps(self, total_steps: int):
        """Set total number of steps for progress tracking"""
        self.total_steps = total_steps
    
    def checkpoint(self, step_description: str, data: Dict[str, Any] = None):
        """Create a checkpoint for the current step"""
        self.current_step += 1
        
        # Complete previous checkpoint if exists
        if self.current_checkpoint_id:
            self.checkpoint_manager.complete_checkpoint(self.current_checkpoint_id)
        
        # Create new checkpoint
        self.current_checkpoint_id = self.checkpoint_manager.create_checkpoint(
            task_id=self.task_id,
            task_title=self.task_title,
            step_number=self.current_step,
            step_description=step_description,
            total_steps=self.total_steps,
            data=data or {},
            worker_id=self.worker_id
        )
        
        # Mark as active
        self.checkpoint_manager.update_checkpoint(
            self.current_checkpoint_id, 
            state=CheckpointState.ACTIVE
        )
    
    def update_progress(self, data: Dict[str, Any] = None, 
                       step_description: str = None):
        """Update current checkpoint progress"""
        if self.current_checkpoint_id:
            self.checkpoint_manager.update_checkpoint(
                self.current_checkpoint_id,
                data=data,
                step_description=step_description
            )
    
    def complete_task(self, final_data: Dict[str, Any] = None):
        """Mark task as completed"""
        if self.current_checkpoint_id:
            self.checkpoint_manager.complete_checkpoint(
                self.current_checkpoint_id,
                final_data=final_data
            )
    
    def fail_task(self, error_info: Dict[str, Any] = None):
        """Mark task as failed"""
        if self.current_checkpoint_id:
            self.checkpoint_manager.fail_checkpoint(
                self.current_checkpoint_id,
                error_info=error_info
            )
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress information"""
        return {
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "progress_percentage": (self.current_step / self.total_steps * 100) if self.total_steps else None,
            "current_checkpoint_id": self.current_checkpoint_id
        }


# Global checkpoint manager instance
checkpoint_manager = CheckpointManager()