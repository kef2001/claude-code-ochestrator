"""Rollback manager for handling task rollbacks and state recovery."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
from threading import Lock
import pickle

from .feedback_model import FeedbackModel, create_error_feedback


logger = logging.getLogger(__name__)


class RollbackStrategy(Enum):
    """Rollback strategies."""
    FULL = "full"  # Complete rollback to checkpoint
    PARTIAL = "partial"  # Rollback specific components
    SELECTIVE = "selective"  # Rollback specific tasks only


class CheckpointType(Enum):
    """Types of checkpoints."""
    MANUAL = "manual"  # User-initiated checkpoint
    AUTOMATIC = "automatic"  # System-created checkpoint
    TASK_COMPLETION = "task_completion"  # After task completion
    ERROR_RECOVERY = "error_recovery"  # Before error recovery


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint."""
    checkpoint_id: str
    timestamp: datetime
    checkpoint_type: CheckpointType
    description: str
    task_states: Dict[str, str] = field(default_factory=dict)
    file_snapshots: List[str] = field(default_factory=list)
    custom_data: Dict[str, Any] = field(default_factory=dict)
    parent_checkpoint: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "timestamp": self.timestamp.isoformat(),
            "checkpoint_type": self.checkpoint_type.value,
            "description": self.description,
            "task_states": self.task_states,
            "file_snapshots": self.file_snapshots,
            "custom_data": self.custom_data,
            "parent_checkpoint": self.parent_checkpoint
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointMetadata":
        """Create from dictionary."""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            checkpoint_type=CheckpointType(data["checkpoint_type"]),
            description=data["description"],
            task_states=data.get("task_states", {}),
            file_snapshots=data.get("file_snapshots", []),
            custom_data=data.get("custom_data", {}),
            parent_checkpoint=data.get("parent_checkpoint")
        )


@dataclass
class RollbackResult:
    """Result of a rollback operation."""
    success: bool
    checkpoint_id: str
    strategy: RollbackStrategy
    rolled_back_tasks: List[str] = field(default_factory=list)
    restored_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "checkpoint_id": self.checkpoint_id,
            "strategy": self.strategy.value,
            "rolled_back_tasks": self.rolled_back_tasks,
            "restored_files": self.restored_files,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds
        }


class RollbackManager:
    """Manages rollback operations and checkpoints."""
    
    def __init__(self, 
                 checkpoint_dir: str = ".checkpoints",
                 max_checkpoints: int = 50,
                 auto_checkpoint: bool = True):
        """Initialize rollback manager.
        
        Args:
            checkpoint_dir: Directory for storing checkpoints
            max_checkpoints: Maximum number of checkpoints to keep
            auto_checkpoint: Enable automatic checkpointing
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max_checkpoints
        self.auto_checkpoint = auto_checkpoint
        self._lock = Lock()
        self._metadata_file = self.checkpoint_dir / "metadata.json"
        self._ensure_metadata()
        
        # Task state tracking
        self._current_tasks: Dict[str, Any] = {}
        self._task_dependencies: Dict[str, Set[str]] = {}
        
        # File tracking
        self._tracked_files: Set[str] = set()
        
        # Rollback history
        self._rollback_history: List[RollbackResult] = []
    
    def _ensure_metadata(self) -> None:
        """Ensure metadata file exists."""
        if not self._metadata_file.exists():
            self._save_metadata({})
    
    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Load checkpoint metadata."""
        try:
            with open(self._metadata_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return {}
    
    def _save_metadata(self, metadata: Dict[str, Dict[str, Any]]) -> None:
        """Save checkpoint metadata."""
        try:
            with open(self._metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
    
    def create_checkpoint(self,
                         checkpoint_type: CheckpointType = CheckpointType.MANUAL,
                         description: str = "",
                         include_files: Optional[List[str]] = None) -> str:
        """Create a new checkpoint.
        
        Creates a snapshot of current system state including task states,
        file contents, and metadata. Automatically manages checkpoint
        retention based on max_checkpoints setting.
        
        Args:
            checkpoint_type: Type of checkpoint (MANUAL, AUTOMATIC, etc).
            description: Human-readable description of the checkpoint.
            include_files: Specific files to include in snapshot. If None,
                all tracked files will be included.
            
        Returns:
            str: Unique checkpoint ID in format 'cp_YYYYMMDD_HHMMSS_ffffff'.
            
        Raises:
            OSError: If checkpoint directory cannot be created.
            PermissionError: If insufficient permissions to create checkpoint.
        """
        with self._lock:
            checkpoint_id = f"cp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            checkpoint_path = self.checkpoint_dir / checkpoint_id
            checkpoint_path.mkdir(exist_ok=True)
            
            # Create metadata
            metadata = CheckpointMetadata(
                checkpoint_id=checkpoint_id,
                timestamp=datetime.now(),
                checkpoint_type=checkpoint_type,
                description=description or f"Checkpoint created at {datetime.now()}",
                task_states=self._capture_task_states(),
                file_snapshots=[]
            )
            
            # Snapshot files
            files_to_snapshot = include_files or list(self._tracked_files)
            for file_path in files_to_snapshot:
                if self._snapshot_file(file_path, checkpoint_path):
                    metadata.file_snapshots.append(file_path)
            
            # Save task state
            task_state_file = checkpoint_path / "task_state.pkl"
            with open(task_state_file, 'wb') as f:
                pickle.dump({
                    "current_tasks": self._current_tasks,
                    "task_dependencies": self._task_dependencies
                }, f)
            
            # Update metadata
            all_metadata = self._load_metadata()
            all_metadata[checkpoint_id] = metadata.to_dict()
            self._save_metadata(all_metadata)
            
            # Cleanup old checkpoints
            self._cleanup_old_checkpoints()
            
            logger.info(f"Created checkpoint {checkpoint_id}")
            return checkpoint_id
    
    def _capture_task_states(self) -> Dict[str, str]:
        """Capture current task states."""
        return {
            task_id: task.get("status", "unknown")
            for task_id, task in self._current_tasks.items()
        }
    
    def _snapshot_file(self, file_path: str, checkpoint_path: Path) -> bool:
        """Create a snapshot of a file.
        
        Args:
            file_path: Path to file
            checkpoint_path: Checkpoint directory
            
        Returns:
            Success status
        """
        try:
            source = Path(file_path)
            if not source.exists():
                return False
            
            # Create relative path structure in checkpoint
            relative_path = source.relative_to(Path.cwd())
            dest = checkpoint_path / "files" / relative_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            if source.is_file():
                shutil.copy2(source, dest)
            elif source.is_dir():
                shutil.copytree(source, dest)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to snapshot {file_path}: {e}")
            return False
    
    def rollback(self,
                 checkpoint_id: str,
                 strategy: RollbackStrategy = RollbackStrategy.FULL,
                 target_tasks: Optional[List[str]] = None) -> RollbackResult:
        """Rollback to a checkpoint.
        
        Args:
            checkpoint_id: ID of checkpoint to rollback to
            strategy: Rollback strategy
            target_tasks: Specific tasks to rollback (for selective strategy)
            
        Returns:
            Rollback result
        """
        start_time = datetime.now()
        with self._lock:
            result = RollbackResult(
                success=False,
                checkpoint_id=checkpoint_id,
                strategy=strategy
            )
            
            # Load checkpoint metadata
            all_metadata = self._load_metadata()
            if checkpoint_id not in all_metadata:
                result.errors.append(f"Checkpoint {checkpoint_id} not found")
                return result
            
            metadata = CheckpointMetadata.from_dict(all_metadata[checkpoint_id])
            checkpoint_path = self.checkpoint_dir / checkpoint_id
            
            try:
                if strategy == RollbackStrategy.FULL:
                    self._rollback_full(metadata, checkpoint_path, result)
                elif strategy == RollbackStrategy.PARTIAL:
                    self._rollback_partial(metadata, checkpoint_path, result)
                elif strategy == RollbackStrategy.SELECTIVE:
                    self._rollback_selective(metadata, checkpoint_path, target_tasks or [], result)
                
                result.success = len(result.errors) == 0
                result.duration_seconds = (datetime.now() - start_time).total_seconds()
                
                # Add to history
                self._rollback_history.append(result)
                
                logger.info(f"Rollback completed: {result.success}")
                
            except Exception as e:
                logger.error(f"Rollback failed: {e}")
                result.errors.append(str(e))
            
            return result
    
    def _rollback_full(self, 
                      metadata: CheckpointMetadata,
                      checkpoint_path: Path,
                      result: RollbackResult) -> None:
        """Perform full rollback."""
        # Restore all files
        files_dir = checkpoint_path / "files"
        if files_dir.exists():
            for file_snapshot in metadata.file_snapshots:
                if self._restore_file(file_snapshot, files_dir):
                    result.restored_files.append(file_snapshot)
                else:
                    result.errors.append(f"Failed to restore {file_snapshot}")
        
        # Restore task state
        task_state_file = checkpoint_path / "task_state.pkl"
        if task_state_file.exists():
            try:
                with open(task_state_file, 'rb') as f:
                    state = pickle.load(f)
                    self._current_tasks = state["current_tasks"]
                    self._task_dependencies = state["task_dependencies"]
                    result.rolled_back_tasks = list(self._current_tasks.keys())
            except Exception as e:
                result.errors.append(f"Failed to restore task state: {e}")
    
    def _rollback_partial(self,
                         metadata: CheckpointMetadata,
                         checkpoint_path: Path,
                         result: RollbackResult) -> None:
        """Perform partial rollback."""
        # Analyze dependencies
        affected_tasks = self._analyze_affected_tasks(metadata.task_states)
        
        # Restore only affected files
        files_dir = checkpoint_path / "files"
        if files_dir.exists():
            for file_snapshot in metadata.file_snapshots:
                # Check if file is related to affected tasks
                if self._is_file_affected(file_snapshot, affected_tasks):
                    if self._restore_file(file_snapshot, files_dir):
                        result.restored_files.append(file_snapshot)
        
        # Partially restore task state
        for task_id in affected_tasks:
            if task_id in metadata.task_states:
                result.rolled_back_tasks.append(task_id)
    
    def _rollback_selective(self,
                           metadata: CheckpointMetadata,
                           checkpoint_path: Path,
                           target_tasks: List[str],
                           result: RollbackResult) -> None:
        """Perform selective rollback."""
        # Validate target tasks
        for task_id in target_tasks:
            if task_id not in metadata.task_states:
                result.errors.append(f"Task {task_id} not found in checkpoint")
                return
        
        # Analyze dependencies
        all_affected = self._get_task_dependencies_recursive(target_tasks)
        
        # Restore files for affected tasks
        files_dir = checkpoint_path / "files"
        if files_dir.exists():
            for file_snapshot in metadata.file_snapshots:
                if self._is_file_affected(file_snapshot, all_affected):
                    if self._restore_file(file_snapshot, files_dir):
                        result.restored_files.append(file_snapshot)
        
        # Update task states
        result.rolled_back_tasks = list(all_affected)
    
    def _restore_file(self, file_path: str, files_dir: Path) -> bool:
        """Restore a file from snapshot.
        
        Args:
            file_path: Original file path
            files_dir: Checkpoint files directory
            
        Returns:
            Success status
        """
        try:
            source_path = Path(file_path)
            relative_path = source_path.relative_to(Path.cwd())
            snapshot = files_dir / relative_path
            
            if not snapshot.exists():
                return False
            
            # Backup current version
            if source_path.exists():
                backup = source_path.with_suffix(source_path.suffix + ".rollback_backup")
                shutil.move(str(source_path), str(backup))
            
            # Restore from snapshot
            source_path.parent.mkdir(parents=True, exist_ok=True)
            
            if snapshot.is_file():
                shutil.copy2(snapshot, source_path)
            elif snapshot.is_dir():
                shutil.copytree(snapshot, source_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore {file_path}: {e}")
            return False
    
    def _analyze_affected_tasks(self, checkpoint_tasks: Dict[str, str]) -> Set[str]:
        """Analyze which tasks are affected by rollback."""
        affected = set()
        
        for task_id, checkpoint_status in checkpoint_tasks.items():
            current_status = self._current_tasks.get(task_id, {}).get("status")
            if current_status != checkpoint_status:
                affected.add(task_id)
                # Add dependent tasks
                affected.update(self._get_task_dependencies_recursive([task_id]))
        
        return affected
    
    def _get_task_dependencies_recursive(self, task_ids: List[str]) -> Set[str]:
        """Get all dependencies recursively."""
        all_deps = set(task_ids)
        to_process = list(task_ids)
        
        while to_process:
            task_id = to_process.pop()
            deps = self._task_dependencies.get(task_id, set())
            for dep in deps:
                if dep not in all_deps:
                    all_deps.add(dep)
                    to_process.append(dep)
        
        return all_deps
    
    def _is_file_affected(self, file_path: str, affected_tasks: Set[str]) -> bool:
        """Check if a file is affected by tasks."""
        # Simple heuristic - can be enhanced
        for task_id in affected_tasks:
            if task_id in file_path:
                return True
        return False
    
    def _cleanup_old_checkpoints(self) -> None:
        """Remove old checkpoints beyond limit."""
        all_metadata = self._load_metadata()
        
        if len(all_metadata) <= self.max_checkpoints:
            return
        
        # Sort by timestamp
        sorted_checkpoints = sorted(
            all_metadata.items(),
            key=lambda x: datetime.fromisoformat(x[1]["timestamp"])
        )
        
        # Remove oldest
        to_remove = len(all_metadata) - self.max_checkpoints
        for checkpoint_id, _ in sorted_checkpoints[:to_remove]:
            self.delete_checkpoint(checkpoint_id)
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint to delete
            
        Returns:
            Success status
        """
        with self._lock:
            try:
                # Remove from metadata
                all_metadata = self._load_metadata()
                if checkpoint_id in all_metadata:
                    del all_metadata[checkpoint_id]
                    self._save_metadata(all_metadata)
                
                # Remove directory
                checkpoint_path = self.checkpoint_dir / checkpoint_id
                if checkpoint_path.exists():
                    shutil.rmtree(checkpoint_path)
                
                logger.info(f"Deleted checkpoint {checkpoint_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
                return False
    
    def list_checkpoints(self) -> List[CheckpointMetadata]:
        """List all available checkpoints."""
        with self._lock:
            all_metadata = self._load_metadata()
            checkpoints = []
            
            for cp_data in all_metadata.values():
                try:
                    checkpoints.append(CheckpointMetadata.from_dict(cp_data))
                except Exception as e:
                    logger.error(f"Failed to load checkpoint metadata: {e}")
            
            # Sort by timestamp (newest first)
            checkpoints.sort(key=lambda x: x.timestamp, reverse=True)
            return checkpoints
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointMetadata]:
        """Get specific checkpoint metadata."""
        with self._lock:
            all_metadata = self._load_metadata()
            if checkpoint_id in all_metadata:
                try:
                    return CheckpointMetadata.from_dict(all_metadata[checkpoint_id])
                except Exception as e:
                    logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None
    
    def track_file(self, file_path: str) -> None:
        """Add a file to be tracked for checkpoints."""
        self._tracked_files.add(str(Path(file_path).absolute()))
    
    def untrack_file(self, file_path: str) -> None:
        """Remove a file from tracking."""
        self._tracked_files.discard(str(Path(file_path).absolute()))
    
    def update_task_state(self, task_id: str, state: Dict[str, Any]) -> None:
        """Update task state for tracking."""
        self._current_tasks[task_id] = state
        
        # Auto checkpoint on task completion if enabled
        if self.auto_checkpoint and state.get("status") == "completed":
            self.create_checkpoint(
                checkpoint_type=CheckpointType.TASK_COMPLETION,
                description=f"Task {task_id} completed"
            )
    
    def set_task_dependency(self, task_id: str, depends_on: List[str]) -> None:
        """Set task dependencies."""
        self._task_dependencies[task_id] = set(depends_on)
    
    def get_rollback_history(self) -> List[RollbackResult]:
        """Get rollback history."""
        return self._rollback_history.copy()
    
    def can_rollback_to(self, checkpoint_id: str) -> bool:
        """Check if rollback to checkpoint is possible."""
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            return False
        
        checkpoint_path = self.checkpoint_dir / checkpoint_id
        return checkpoint_path.exists()
    
    def export_checkpoint(self, checkpoint_id: str, export_path: str) -> bool:
        """Export a checkpoint to external location.
        
        Args:
            checkpoint_id: Checkpoint to export
            export_path: Path to export to
            
        Returns:
            Success status
        """
        with self._lock:
            try:
                checkpoint_path = self.checkpoint_dir / checkpoint_id
                if not checkpoint_path.exists():
                    return False
                
                export_dir = Path(export_path)
                export_dir.parent.mkdir(parents=True, exist_ok=True)
                
                # Create archive
                shutil.make_archive(
                    str(export_dir),
                    'zip',
                    str(checkpoint_path)
                )
                
                logger.info(f"Exported checkpoint {checkpoint_id} to {export_path}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to export checkpoint: {e}")
                return False
    
    def import_checkpoint(self, import_path: str) -> Optional[str]:
        """Import a checkpoint from external location.
        
        Args:
            import_path: Path to import from
            
        Returns:
            Imported checkpoint ID or None
        """
        with self._lock:
            try:
                import_file = Path(import_path)
                if not import_file.exists():
                    return None
                
                # Generate new checkpoint ID
                checkpoint_id = f"imported_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                checkpoint_path = self.checkpoint_dir / checkpoint_id
                
                # Extract archive
                shutil.unpack_archive(
                    str(import_file),
                    str(checkpoint_path),
                    'zip'
                )
                
                # Update metadata
                # Note: This is simplified - in production, validate imported metadata
                logger.info(f"Imported checkpoint as {checkpoint_id}")
                return checkpoint_id
                
            except Exception as e:
                logger.error(f"Failed to import checkpoint: {e}")
                return None