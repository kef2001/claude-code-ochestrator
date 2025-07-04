"""Feedback storage implementation with JSON backend."""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from threading import Lock
import logging

from .feedback_model import FeedbackModel, FeedbackType, FeedbackSeverity, FeedbackCategory


logger = logging.getLogger(__name__)


class FeedbackStorageInterface(ABC):
    """Abstract interface for feedback storage backends."""
    
    @abstractmethod
    def save(self, feedback: FeedbackModel) -> None:
        """Save feedback to storage."""
        pass
    
    @abstractmethod
    def load(self, feedback_id: str) -> Optional[FeedbackModel]:
        """Load feedback by ID."""
        pass
    
    @abstractmethod
    def query(
        self,
        task_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        feedback_type: Optional[FeedbackType] = None,
        severity: Optional[FeedbackSeverity] = None,
        category: Optional[FeedbackCategory] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[FeedbackModel]:
        """Query feedback with filters."""
        pass
    
    @abstractmethod
    def delete(self, feedback_id: str) -> bool:
        """Delete feedback by ID."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all feedback from storage."""
        pass
    
    @abstractmethod
    def count(self) -> int:
        """Count total feedback entries."""
        pass


class JSONFeedbackStorage(FeedbackStorageInterface):
    """JSON file-based feedback storage implementation."""
    
    def __init__(self, storage_path: str = ".feedback"):
        """Initialize JSON feedback storage.
        
        Args:
            storage_path: Directory path for storing feedback files
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._index_file = self.storage_path / "index.json"
        self._ensure_index()
    
    def _ensure_index(self) -> None:
        """Ensure index file exists."""
        if not self._index_file.exists():
            self._save_index({})
    
    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        """Load feedback index."""
        try:
            with open(self._index_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return {}
    
    def _save_index(self, index: Dict[str, Dict[str, Any]]) -> None:
        """Save feedback index."""
        try:
            with open(self._index_file, 'w') as f:
                json.dump(index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
    
    def _get_feedback_file(self, feedback_id: str) -> Path:
        """Get path for feedback file."""
        # Use first 2 chars of ID for directory sharding
        shard = feedback_id[:2] if len(feedback_id) >= 2 else "00"
        shard_dir = self.storage_path / shard
        shard_dir.mkdir(exist_ok=True)
        return shard_dir / f"{feedback_id}.json"
    
    def save(self, feedback: FeedbackModel) -> None:
        """Save feedback to storage."""
        with self._lock:
            try:
                # Validate feedback
                feedback.validate()
                
                # Save feedback file
                feedback_file = self._get_feedback_file(feedback.feedback_id)
                feedback_data = feedback.to_dict()
                
                with open(feedback_file, 'w') as f:
                    json.dump(feedback_data, f, indent=2)
                
                # Update index
                index = self._load_index()
                index[feedback.feedback_id] = {
                    "task_id": feedback.context.task_id,
                    "worker_id": feedback.context.worker_id,
                    "feedback_type": feedback.feedback_type.value,
                    "severity": feedback.severity.value,
                    "category": feedback.category.value,
                    "timestamp": feedback.timestamp.isoformat(),
                    "tags": feedback.context.tags,
                    "file": str(feedback_file.relative_to(self.storage_path))
                }
                self._save_index(index)
                
                logger.info(f"Saved feedback {feedback.feedback_id}")
                
            except Exception as e:
                logger.error(f"Failed to save feedback: {e}")
                raise
    
    def load(self, feedback_id: str) -> Optional[FeedbackModel]:
        """Load feedback by ID."""
        with self._lock:
            try:
                feedback_file = self._get_feedback_file(feedback_id)
                
                if not feedback_file.exists():
                    return None
                
                with open(feedback_file, 'r') as f:
                    data = json.load(f)
                
                return FeedbackModel.from_dict(data)
                
            except Exception as e:
                logger.error(f"Failed to load feedback {feedback_id}: {e}")
                return None
    
    def query(
        self,
        task_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        feedback_type: Optional[FeedbackType] = None,
        severity: Optional[FeedbackSeverity] = None,
        category: Optional[FeedbackCategory] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[FeedbackModel]:
        """Query feedback with filters."""
        with self._lock:
            results = []
            index = self._load_index()
            
            # Filter index entries
            for feedback_id, meta in index.items():
                # Apply filters
                if task_id and meta.get("task_id") != task_id:
                    continue
                
                if worker_id and meta.get("worker_id") != worker_id:
                    continue
                
                if feedback_type and meta.get("feedback_type") != feedback_type.value:
                    continue
                
                if severity and meta.get("severity") != severity.value:
                    continue
                
                if category and meta.get("category") != category.value:
                    continue
                
                if tags:
                    meta_tags = set(meta.get("tags", []))
                    if not all(tag in meta_tags for tag in tags):
                        continue
                
                # Time range filter
                if start_time or end_time:
                    timestamp = datetime.fromisoformat(meta.get("timestamp", ""))
                    if start_time and timestamp < start_time:
                        continue
                    if end_time and timestamp > end_time:
                        continue
                
                # Load the full feedback
                feedback = self.load(feedback_id)
                if feedback:
                    results.append(feedback)
                
                # Check limit
                if limit and len(results) >= limit:
                    break
            
            # Sort by timestamp (newest first)
            results.sort(key=lambda f: f.timestamp, reverse=True)
            
            return results
    
    def delete(self, feedback_id: str) -> bool:
        """Delete feedback by ID."""
        with self._lock:
            try:
                # Remove from index
                index = self._load_index()
                if feedback_id not in index:
                    return False
                
                # Delete file
                feedback_file = self._get_feedback_file(feedback_id)
                if feedback_file.exists():
                    feedback_file.unlink()
                
                # Update index
                del index[feedback_id]
                self._save_index(index)
                
                logger.info(f"Deleted feedback {feedback_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to delete feedback {feedback_id}: {e}")
                return False
    
    def clear(self) -> None:
        """Clear all feedback from storage."""
        with self._lock:
            try:
                # Remove all feedback files
                for item in self.storage_path.rglob("*.json"):
                    if item.name != "index.json":
                        item.unlink()
                
                # Remove shard directories
                for item in self.storage_path.iterdir():
                    if item.is_dir() and len(item.name) == 2:
                        item.rmdir()
                
                # Clear index
                self._save_index({})
                
                logger.info("Cleared all feedback from storage")
                
            except Exception as e:
                logger.error(f"Failed to clear storage: {e}")
                raise
    
    def count(self) -> int:
        """Count total feedback entries."""
        with self._lock:
            index = self._load_index()
            return len(index)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with self._lock:
            index = self._load_index()
            
            # Count by type
            type_counts = {}
            severity_counts = {}
            category_counts = {}
            
            for meta in index.values():
                # Type counts
                ft = meta.get("feedback_type", "unknown")
                type_counts[ft] = type_counts.get(ft, 0) + 1
                
                # Severity counts
                sev = meta.get("severity", "unknown")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
                
                # Category counts
                cat = meta.get("category", "unknown")
                category_counts[cat] = category_counts.get(cat, 0) + 1
            
            return {
                "total_count": len(index),
                "type_counts": type_counts,
                "severity_counts": severity_counts,
                "category_counts": category_counts,
                "storage_size_mb": self._calculate_storage_size() / (1024 * 1024)
            }
    
    def _calculate_storage_size(self) -> int:
        """Calculate total storage size in bytes."""
        total_size = 0
        for item in self.storage_path.rglob("*.json"):
            total_size += item.stat().st_size
        return total_size


class FeedbackStorage:
    """Main feedback storage class with caching and optimization."""
    
    def __init__(self, backend: Optional[FeedbackStorageInterface] = None):
        """Initialize feedback storage.
        
        Args:
            backend: Storage backend to use (defaults to JSONFeedbackStorage)
        """
        self.backend = backend or JSONFeedbackStorage()
        self._cache: Dict[str, FeedbackModel] = {}
        self._cache_size = 1000
        self._lock = Lock()
    
    def save(self, feedback: FeedbackModel) -> None:
        """Save feedback with caching."""
        with self._lock:
            # Save to backend
            self.backend.save(feedback)
            
            # Update cache
            self._cache[feedback.feedback_id] = feedback
            
            # Limit cache size
            if len(self._cache) > self._cache_size:
                # Remove oldest entries
                oldest_ids = sorted(
                    self._cache.keys(),
                    key=lambda fid: self._cache[fid].timestamp
                )[:100]
                for fid in oldest_ids:
                    del self._cache[fid]
    
    def load(self, feedback_id: str) -> Optional[FeedbackModel]:
        """Load feedback with caching."""
        with self._lock:
            # Check cache first
            if feedback_id in self._cache:
                return self._cache[feedback_id]
            
            # Load from backend
            feedback = self.backend.load(feedback_id)
            if feedback:
                self._cache[feedback_id] = feedback
            
            return feedback
    
    def query(self, **kwargs) -> List[FeedbackModel]:
        """Query feedback from backend."""
        return self.backend.query(**kwargs)
    
    def delete(self, feedback_id: str) -> bool:
        """Delete feedback."""
        with self._lock:
            # Remove from cache
            if feedback_id in self._cache:
                del self._cache[feedback_id]
            
            # Delete from backend
            return self.backend.delete(feedback_id)
    
    def clear(self) -> None:
        """Clear all feedback."""
        with self._lock:
            self._cache.clear()
            self.backend.clear()
    
    def count(self) -> int:
        """Count total feedback entries."""
        return self.backend.count()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get storage statistics."""
        if hasattr(self.backend, 'get_statistics'):
            return self.backend.get_statistics()
        return {"total_count": self.count()}
    
    def batch_save(self, feedbacks: List[FeedbackModel]) -> None:
        """Save multiple feedbacks efficiently."""
        for feedback in feedbacks:
            self.save(feedback)
    
    def export_to_file(self, filepath: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """Export feedbacks to a file.
        
        Args:
            filepath: Path to export file
            filters: Optional query filters
            
        Returns:
            Number of feedbacks exported
        """
        feedbacks = self.query(**(filters or {}))
        
        with open(filepath, 'w') as f:
            data = {
                "export_time": datetime.now().isoformat(),
                "count": len(feedbacks),
                "feedbacks": [fb.to_dict() for fb in feedbacks]
            }
            json.dump(data, f, indent=2)
        
        return len(feedbacks)
    
    def import_from_file(self, filepath: str) -> int:
        """Import feedbacks from a file.
        
        Args:
            filepath: Path to import file
            
        Returns:
            Number of feedbacks imported
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        feedbacks_data = data.get("feedbacks", [])
        count = 0
        
        for fb_data in feedbacks_data:
            try:
                feedback = FeedbackModel.from_dict(fb_data)
                self.save(feedback)
                count += 1
            except Exception as e:
                logger.error(f"Failed to import feedback: {e}")
        
        return count