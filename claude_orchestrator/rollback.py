"""
Rollback Manager for Claude Orchestrator

This module provides rollback functionality to restore system state from checkpoints.
It integrates with the CheckpointManager to handle error recovery and manual rollbacks.
"""

import json
import logging
import os
import shutil
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import threading
from contextlib import contextmanager

from .checkpoint_system import CheckpointManager, CheckpointData, CheckpointState


logger = logging.getLogger(__name__)


class RollbackReason(Enum):
    """Reasons for initiating a rollback"""
    ERROR = "error"
    MANUAL = "manual"
    VALIDATION_FAILED = "validation_failed"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    DEPENDENCY_FAILED = "dependency_failed"


class RollbackStatus(Enum):
    """Status of a rollback operation"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class RollbackRecord:
    """Record of a rollback operation"""
    rollback_id: str
    checkpoint_id: str
    task_id: str
    reason: RollbackReason
    status: RollbackStatus
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    restored_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "rollback_id": self.rollback_id,
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "reason": self.reason.value,
            "status": self.status.value,
            "initiated_at": self.initiated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "restored_data": self.restored_data,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RollbackRecord':
        """Create from dictionary"""
        data = data.copy()
        data['reason'] = RollbackReason(data['reason'])
        data['status'] = RollbackStatus(data['status'])
        data['initiated_at'] = datetime.fromisoformat(data['initiated_at'])
        if data.get('completed_at'):
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        return cls(**data)


class RollbackManager:
    """
    Manages rollback operations for the orchestrator system
    
    Integrates with CheckpointManager to restore task state and handle
    error recovery scenarios.
    """
    
    # Version for compatibility checking
    ROLLBACK_VERSION = "1.0.0"
    
    def __init__(
        self,
        checkpoint_manager: Optional[CheckpointManager] = None,
        storage_dir: str = ".taskmaster/rollbacks",
        max_rollback_history: int = 100
    ):
        """
        Initialize the RollbackManager
        
        Args:
            checkpoint_manager: CheckpointManager instance
            storage_dir: Directory for rollback records
            max_rollback_history: Maximum number of rollback records to keep
        """
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_rollback_history = max_rollback_history
        
        # Rollback history
        self.rollback_history: List[RollbackRecord] = []
        self.active_rollbacks: Dict[str, RollbackRecord] = {}
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Rollback callbacks
        self.rollback_callbacks: List[callable] = []
        
        # Load existing rollback history
        self._load_rollback_history()
        
        logger.info(f"RollbackManager initialized with storage: {self.storage_dir}")
    
    def _load_rollback_history(self):
        """Load rollback history from storage"""
        history_file = self.storage_dir / "rollback_history.json"
        
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                    
                for record_data in history_data.get('records', []):
                    try:
                        record = RollbackRecord.from_dict(record_data)
                        self.rollback_history.append(record)
                    except Exception as e:
                        logger.error(f"Error loading rollback record: {e}")
                
                logger.info(f"Loaded {len(self.rollback_history)} rollback records")
                
            except Exception as e:
                logger.error(f"Error loading rollback history: {e}")
    
    def _save_rollback_history(self):
        """Save rollback history to storage"""
        history_file = self.storage_dir / "rollback_history.json"
        
        try:
            # Keep only the most recent records
            if len(self.rollback_history) > self.max_rollback_history:
                self.rollback_history = self.rollback_history[-self.max_rollback_history:]
            
            history_data = {
                "version": self.ROLLBACK_VERSION,
                "updated_at": datetime.now().isoformat(),
                "records": [record.to_dict() for record in self.rollback_history]
            }
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving rollback history: {e}")
    
    def create_checkpoint(
        self,
        task_id: str,
        task_title: str,
        step_number: int,
        step_description: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Create a checkpoint that can be rolled back to
        
        Args:
            task_id: Task identifier
            task_title: Task title
            step_number: Current step number
            step_description: Description of current step
            data: State data to checkpoint
            metadata: Additional metadata
            
        Returns:
            Checkpoint ID if successful, None otherwise
        """
        try:
            # Delegate to checkpoint manager
            checkpoint_id = self.checkpoint_manager.create_checkpoint(
                task_id=task_id,
                task_title=task_title,
                step_number=step_number,
                step_description=step_description,
                data=data,
                metadata=metadata
            )
            
            if checkpoint_id:
                logger.info(f"Created checkpoint {checkpoint_id} for task {task_id}")
                
                # Add rollback metadata
                checkpoint = self.checkpoint_manager.get_checkpoint(checkpoint_id)
                if checkpoint:
                    checkpoint.metadata['rollback_enabled'] = True
                    checkpoint.metadata['rollback_version'] = self.ROLLBACK_VERSION
                    self.checkpoint_manager.update_checkpoint(checkpoint_id, checkpoint.data, checkpoint.metadata)
            
            return checkpoint_id
            
        except Exception as e:
            logger.error(f"Error creating checkpoint for rollback: {e}")
            return None
    
    def list_checkpoints(self, task_id: Optional[str] = None) -> List[CheckpointData]:
        """
        List available checkpoints for rollback
        
        Args:
            task_id: Optional task ID to filter checkpoints
            
        Returns:
            List of checkpoint data
        """
        try:
            # Get all checkpoints from checkpoint manager
            all_checkpoints = []
            
            # Get active checkpoints
            for checkpoint in self.checkpoint_manager.active_checkpoints.values():
                if task_id is None or checkpoint.task_id == task_id:
                    all_checkpoints.append(checkpoint)
            
            # Get completed checkpoints from storage
            for checkpoint_file in self.checkpoint_manager.storage_dir.glob("checkpoint_*.json"):
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        checkpoint_data = json.load(f)
                        checkpoint = CheckpointData.from_dict(checkpoint_data)
                        
                        if (task_id is None or checkpoint.task_id == task_id) and \
                           checkpoint.checkpoint_id not in self.checkpoint_manager.active_checkpoints:
                            all_checkpoints.append(checkpoint)
                            
                except Exception as e:
                    logger.warning(f"Error loading checkpoint file {checkpoint_file}: {e}")
            
            # Sort by creation time (newest first)
            all_checkpoints.sort(key=lambda x: x.created_at, reverse=True)
            
            return all_checkpoints
            
        except Exception as e:
            logger.error(f"Error listing checkpoints: {e}")
            return []
    
    def restore_checkpoint(
        self,
        checkpoint_id: str,
        reason: RollbackReason = RollbackReason.MANUAL,
        validate: bool = True
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Restore system state from a checkpoint
        
        Args:
            checkpoint_id: ID of checkpoint to restore
            reason: Reason for rollback
            validate: Whether to validate checkpoint before restoring
            
        Returns:
            Tuple of (success, restored_data)
        """
        rollback_id = f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{checkpoint_id[:8]}"
        
        # Create rollback record
        rollback_record = RollbackRecord(
            rollback_id=rollback_id,
            checkpoint_id=checkpoint_id,
            task_id="",  # Will be filled from checkpoint
            reason=reason,
            status=RollbackStatus.PENDING,
            initiated_at=datetime.now()
        )
        
        with self._lock:
            self.active_rollbacks[rollback_id] = rollback_record
        
        try:
            # Get checkpoint data
            checkpoint = self.checkpoint_manager.get_checkpoint(checkpoint_id)
            if not checkpoint:
                # Try loading from file
                checkpoint_file = self.checkpoint_manager.storage_dir / f"checkpoint_{checkpoint_id}.json"
                if checkpoint_file.exists():
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        checkpoint_data = json.load(f)
                        checkpoint = CheckpointData.from_dict(checkpoint_data)
                else:
                    raise ValueError(f"Checkpoint {checkpoint_id} not found")
            
            rollback_record.task_id = checkpoint.task_id
            rollback_record.status = RollbackStatus.IN_PROGRESS
            
            # Validate checkpoint if requested
            if validate:
                is_valid, validation_msg = self.validate_checkpoint(checkpoint)
                if not is_valid:
                    raise ValueError(f"Checkpoint validation failed: {validation_msg}")
            
            # Notify callbacks before rollback
            for callback in self.rollback_callbacks:
                try:
                    callback('before_rollback', rollback_record, checkpoint)
                except Exception as e:
                    logger.error(f"Rollback callback error: {e}")
            
            # Perform the actual rollback
            logger.info(f"Starting rollback {rollback_id} to checkpoint {checkpoint_id}")
            
            # Save current state before rollback (for recovery)
            self._save_pre_rollback_state(rollback_id, checkpoint.task_id)
            
            # Restore checkpoint data
            restored_data = {
                "task_id": checkpoint.task_id,
                "task_title": checkpoint.task_title,
                "step_number": checkpoint.step_number,
                "step_description": checkpoint.step_description,
                "data": checkpoint.data.copy(),
                "metadata": checkpoint.metadata.copy(),
                "checkpoint_created_at": checkpoint.created_at.isoformat()
            }
            
            # Update checkpoint state
            checkpoint.state = CheckpointState.RESTORED
            checkpoint.metadata['restored_at'] = datetime.now().isoformat()
            checkpoint.metadata['rollback_id'] = rollback_id
            
            # Save updated checkpoint
            self.checkpoint_manager.update_checkpoint(
                checkpoint_id,
                checkpoint.data,
                checkpoint.metadata
            )
            
            # Complete rollback
            rollback_record.status = RollbackStatus.SUCCESS
            rollback_record.completed_at = datetime.now()
            rollback_record.restored_data = restored_data
            
            # Notify callbacks after rollback
            for callback in self.rollback_callbacks:
                try:
                    callback('after_rollback', rollback_record, checkpoint)
                except Exception as e:
                    logger.error(f"Rollback callback error: {e}")
            
            logger.info(f"Rollback {rollback_id} completed successfully")
            
            return True, restored_data
            
        except Exception as e:
            logger.error(f"Rollback {rollback_id} failed: {e}")
            rollback_record.status = RollbackStatus.FAILED
            rollback_record.completed_at = datetime.now()
            rollback_record.error_message = str(e)
            
            return False, None
            
        finally:
            # Update history
            with self._lock:
                self.rollback_history.append(rollback_record)
                self.active_rollbacks.pop(rollback_id, None)
                self._save_rollback_history()
    
    def _save_pre_rollback_state(self, rollback_id: str, task_id: str):
        """Save current state before performing rollback"""
        try:
            pre_rollback_dir = self.storage_dir / "pre_rollback_states"
            pre_rollback_dir.mkdir(exist_ok=True)
            
            state_file = pre_rollback_dir / f"{rollback_id}_state.json"
            
            # Get current task state (simplified for this implementation)
            current_state = {
                "rollback_id": rollback_id,
                "task_id": task_id,
                "saved_at": datetime.now().isoformat(),
                "active_checkpoints": list(self.checkpoint_manager.active_checkpoints.keys())
            }
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(current_state, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Failed to save pre-rollback state: {e}")
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint
        
        Args:
            checkpoint_id: ID of checkpoint to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if checkpoint has been used in rollbacks
            checkpoint_used = any(
                record.checkpoint_id == checkpoint_id 
                for record in self.rollback_history
            )
            
            if checkpoint_used:
                logger.warning(f"Checkpoint {checkpoint_id} has been used in rollbacks, archiving instead")
                return self._archive_checkpoint(checkpoint_id)
            
            # Delete checkpoint file
            checkpoint_file = self.checkpoint_manager.storage_dir / f"checkpoint_{checkpoint_id}.json"
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            
            # Remove from active checkpoints
            if checkpoint_id in self.checkpoint_manager.active_checkpoints:
                del self.checkpoint_manager.active_checkpoints[checkpoint_id]
            
            logger.info(f"Deleted checkpoint {checkpoint_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting checkpoint {checkpoint_id}: {e}")
            return False
    
    def _archive_checkpoint(self, checkpoint_id: str) -> bool:
        """Archive a checkpoint instead of deleting it"""
        try:
            archive_dir = self.checkpoint_manager.storage_dir / "archived"
            archive_dir.mkdir(exist_ok=True)
            
            checkpoint_file = self.checkpoint_manager.storage_dir / f"checkpoint_{checkpoint_id}.json"
            if checkpoint_file.exists():
                archive_file = archive_dir / f"checkpoint_{checkpoint_id}.json"
                shutil.move(str(checkpoint_file), str(archive_file))
                
                # Add archive metadata
                with open(archive_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                data['archived_at'] = datetime.now().isoformat()
                
                with open(archive_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error archiving checkpoint {checkpoint_id}: {e}")
            return False
    
    def validate_checkpoint(self, checkpoint_data: CheckpointData) -> Tuple[bool, str]:
        """
        Validate a checkpoint for compatibility and integrity
        
        Args:
            checkpoint_data: Checkpoint to validate
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            # Check checkpoint state
            if checkpoint_data.state == CheckpointState.FAILED:
                return False, "Cannot restore from failed checkpoint"
            
            # Check version compatibility
            checkpoint_version = checkpoint_data.metadata.get('rollback_version', '0.0.0')
            if not self._is_version_compatible(checkpoint_version):
                return False, f"Incompatible checkpoint version: {checkpoint_version}"
            
            # Check data integrity
            required_fields = ['task_id', 'step_number', 'data']
            for field in required_fields:
                if not hasattr(checkpoint_data, field) or getattr(checkpoint_data, field) is None:
                    return False, f"Missing required field: {field}"
            
            # Check data corruption
            if not isinstance(checkpoint_data.data, dict):
                return False, "Checkpoint data is corrupted"
            
            # Check age (optional - warn if too old)
            age = datetime.now() - checkpoint_data.created_at
            if age > timedelta(days=30):
                logger.warning(f"Checkpoint {checkpoint_data.checkpoint_id} is {age.days} days old")
            
            return True, "Checkpoint is valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def _is_version_compatible(self, checkpoint_version: str) -> bool:
        """Check if checkpoint version is compatible"""
        try:
            # Simple major version compatibility check
            current_major = int(self.ROLLBACK_VERSION.split('.')[0])
            checkpoint_major = int(checkpoint_version.split('.')[0])
            
            return current_major == checkpoint_major
            
        except:
            return False
    
    def get_rollback_history(
        self,
        task_id: Optional[str] = None,
        limit: int = 50
    ) -> List[RollbackRecord]:
        """
        Get rollback history
        
        Args:
            task_id: Optional task ID to filter by
            limit: Maximum number of records to return
            
        Returns:
            List of rollback records
        """
        history = self.rollback_history.copy()
        
        if task_id:
            history = [r for r in history if r.task_id == task_id]
        
        # Sort by initiated time (newest first)
        history.sort(key=lambda x: x.initiated_at, reverse=True)
        
        return history[:limit]
    
    def can_rollback(self, task_id: str) -> Tuple[bool, str]:
        """
        Check if a task can be rolled back
        
        Args:
            task_id: Task ID to check
            
        Returns:
            Tuple of (can_rollback, reason)
        """
        # Check if task has any checkpoints
        checkpoints = self.list_checkpoints(task_id)
        if not checkpoints:
            return False, "No checkpoints available for rollback"
        
        # Check if rollback is already in progress
        active_rollback = any(
            r.task_id == task_id and r.status == RollbackStatus.IN_PROGRESS
            for r in self.active_rollbacks.values()
        )
        
        if active_rollback:
            return False, "Rollback already in progress for this task"
        
        # Check latest checkpoint validity
        latest_checkpoint = checkpoints[0]
        is_valid, msg = self.validate_checkpoint(latest_checkpoint)
        
        if not is_valid:
            return False, f"Latest checkpoint invalid: {msg}"
        
        return True, "Task can be rolled back"
    
    def register_rollback_callback(self, callback: callable):
        """
        Register a callback for rollback events
        
        Args:
            callback: Function to call on rollback events
                     Signature: callback(event_type, rollback_record, checkpoint_data)
        """
        self.rollback_callbacks.append(callback)
        logger.info(f"Registered rollback callback: {callback.__name__}")
    
    def cleanup_old_checkpoints(self, days: int = 30):
        """
        Clean up old checkpoints
        
        Args:
            days: Age threshold in days
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0
            
            checkpoints = self.list_checkpoints()
            for checkpoint in checkpoints:
                if checkpoint.created_at < cutoff_date:
                    if self.delete_checkpoint(checkpoint.checkpoint_id):
                        deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old checkpoints")
            
        except Exception as e:
            logger.error(f"Error cleaning up old checkpoints: {e}")
    
    @contextmanager
    def rollback_on_error(self, task_id: str, checkpoint_id: str):
        """
        Context manager that automatically rolls back on error
        
        Args:
            task_id: Task ID
            checkpoint_id: Checkpoint to rollback to on error
        """
        try:
            yield
        except Exception as e:
            logger.error(f"Error in task {task_id}, initiating rollback: {e}")
            success, _ = self.restore_checkpoint(
                checkpoint_id,
                reason=RollbackReason.ERROR
            )
            if not success:
                logger.error(f"Rollback failed for task {task_id}")
            raise


# Convenience function
def create_rollback_manager(
    checkpoint_manager: Optional[CheckpointManager] = None,
    storage_dir: str = ".taskmaster/rollbacks"
) -> RollbackManager:
    """
    Create a RollbackManager instance
    
    Args:
        checkpoint_manager: Optional CheckpointManager instance
        storage_dir: Storage directory for rollback data
        
    Returns:
        RollbackManager instance
    """
    return RollbackManager(
        checkpoint_manager=checkpoint_manager,
        storage_dir=storage_dir
    )