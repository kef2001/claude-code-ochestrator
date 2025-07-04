"""Resource management and orphaned resource detection system."""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import threading
import time

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources tracked."""
    TEMP_FILE = "temp_file"
    LOCK_FILE = "lock_file"
    SOCKET = "socket"
    PROCESS = "process"
    THREAD = "thread"
    MEMORY_BUFFER = "memory_buffer"
    DATABASE_CONNECTION = "database_connection"
    FILE_HANDLE = "file_handle"


class ResourceStatus(Enum):
    """Resource status."""
    ACTIVE = "active"
    IDLE = "idle"
    ORPHANED = "orphaned"
    CLEANED = "cleaned"
    FAILED = "failed"


@dataclass
class Resource:
    """Resource metadata."""
    resource_id: str
    resource_type: ResourceType
    path: Optional[str] = None
    owner_id: Optional[str] = None  # Task or worker ID
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    status: ResourceStatus = ResourceStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_orphaned(self, idle_threshold_minutes: int = 30) -> bool:
        """Check if resource is orphaned.
        
        Args:
            idle_threshold_minutes: Minutes of inactivity before considering orphaned
            
        Returns:
            True if orphaned
        """
        if self.status == ResourceStatus.ORPHANED:
            return True
        
        # Check if idle too long
        idle_time = datetime.now() - self.last_accessed
        if idle_time > timedelta(minutes=idle_threshold_minutes):
            return True
        
        # Check if file resources still exist
        if self.resource_type in [ResourceType.TEMP_FILE, ResourceType.LOCK_FILE]:
            if self.path and not os.path.exists(self.path):
                return False  # Already cleaned up
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type.value,
            "path": self.path,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "status": self.status.value,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Resource':
        """Create from dictionary."""
        return cls(
            resource_id=data["resource_id"],
            resource_type=ResourceType(data["resource_type"]),
            path=data.get("path"),
            owner_id=data.get("owner_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            status=ResourceStatus(data["status"]),
            metadata=data.get("metadata", {})
        )


class OrphanedResourceDetector:
    """Detects and tracks orphaned resources."""
    
    def __init__(self, 
                 tracking_file: str = ".resource_tracking.json",
                 idle_threshold_minutes: int = 30,
                 scan_interval_seconds: int = 300):
        self.tracking_file = tracking_file
        self.idle_threshold_minutes = idle_threshold_minutes
        self.scan_interval_seconds = scan_interval_seconds
        self.resources: Dict[str, Resource] = {}
        self._lock = threading.RLock()
        self._scanner_thread = None
        self._scanning = False
        
        # Load existing tracking data
        self._load_tracking_data()
        
        logger.info(f"Orphaned resource detector initialized with idle threshold: {idle_threshold_minutes} minutes")
    
    def _load_tracking_data(self):
        """Load tracking data from file."""
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, 'r') as f:
                    data = json.load(f)
                    for resource_data in data.get("resources", []):
                        resource = Resource.from_dict(resource_data)
                        self.resources[resource.resource_id] = resource
                logger.info(f"Loaded {len(self.resources)} tracked resources")
            except Exception as e:
                logger.error(f"Failed to load tracking data: {e}")
    
    def _save_tracking_data(self):
        """Save tracking data to file."""
        try:
            data = {
                "last_updated": datetime.now().isoformat(),
                "resources": [r.to_dict() for r in self.resources.values()]
            }
            
            # Write to temp file first
            temp_file = f"{self.tracking_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Atomic rename
            os.replace(temp_file, self.tracking_file)
            
        except Exception as e:
            logger.error(f"Failed to save tracking data: {e}")
    
    def register_resource(self,
                         resource_type: ResourceType,
                         resource_id: Optional[str] = None,
                         path: Optional[str] = None,
                         owner_id: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """Register a new resource for tracking.
        
        Args:
            resource_type: Type of resource
            resource_id: Optional resource ID (generated if not provided)
            path: File path for file-based resources
            owner_id: ID of owning task or worker
            metadata: Additional metadata
            
        Returns:
            Resource ID
        """
        with self._lock:
            if not resource_id:
                resource_id = f"{resource_type.value}_{datetime.now().timestamp()}"
            
            resource = Resource(
                resource_id=resource_id,
                resource_type=resource_type,
                path=path,
                owner_id=owner_id,
                metadata=metadata or {}
            )
            
            self.resources[resource_id] = resource
            self._save_tracking_data()
            
            logger.debug(f"Registered resource: {resource_id} (type: {resource_type.value})")
            return resource_id
    
    def update_resource_access(self, resource_id: str):
        """Update last access time for a resource."""
        with self._lock:
            if resource_id in self.resources:
                self.resources[resource_id].last_accessed = datetime.now()
                self.resources[resource_id].status = ResourceStatus.ACTIVE
    
    def release_resource(self, resource_id: str):
        """Mark resource as released."""
        with self._lock:
            if resource_id in self.resources:
                self.resources[resource_id].status = ResourceStatus.IDLE
                self._save_tracking_data()
    
    def remove_resource(self, resource_id: str):
        """Remove resource from tracking."""
        with self._lock:
            if resource_id in self.resources:
                del self.resources[resource_id]
                self._save_tracking_data()
    
    def scan_for_orphans(self) -> List[Resource]:
        """Scan for orphaned resources.
        
        Returns:
            List of orphaned resources
        """
        orphaned = []
        
        with self._lock:
            for resource in self.resources.values():
                if resource.is_orphaned(self.idle_threshold_minutes):
                    resource.status = ResourceStatus.ORPHANED
                    orphaned.append(resource)
            
            # Save updated statuses
            if orphaned:
                self._save_tracking_data()
                logger.info(f"Found {len(orphaned)} orphaned resources")
        
        return orphaned
    
    def get_orphaned_resources(self, 
                              resource_type: Optional[ResourceType] = None) -> List[Resource]:
        """Get list of orphaned resources.
        
        Args:
            resource_type: Filter by resource type
            
        Returns:
            List of orphaned resources
        """
        with self._lock:
            orphaned = [
                r for r in self.resources.values()
                if r.status == ResourceStatus.ORPHANED
            ]
            
            if resource_type:
                orphaned = [r for r in orphaned if r.resource_type == resource_type]
            
            return orphaned
    
    def start_auto_scan(self):
        """Start automatic scanning for orphaned resources."""
        if self._scanning:
            return
        
        self._scanning = True
        self._scanner_thread = threading.Thread(
            target=self._auto_scan_loop,
            daemon=True,
            name="OrphanedResourceScanner"
        )
        self._scanner_thread.start()
        logger.info("Started automatic orphaned resource scanning")
    
    def stop_auto_scan(self):
        """Stop automatic scanning."""
        self._scanning = False
        if self._scanner_thread:
            self._scanner_thread.join(timeout=5)
        logger.info("Stopped automatic orphaned resource scanning")
    
    def _auto_scan_loop(self):
        """Automatic scanning loop."""
        while self._scanning:
            try:
                self.scan_for_orphans()
                time.sleep(self.scan_interval_seconds)
            except Exception as e:
                logger.error(f"Error in auto scan: {e}")
                time.sleep(10)
    
    def get_resource_summary(self) -> Dict[str, Any]:
        """Get summary of tracked resources.
        
        Returns:
            Resource summary statistics
        """
        with self._lock:
            summary = {
                "total_resources": len(self.resources),
                "by_status": {},
                "by_type": {},
                "orphaned_count": 0,
                "oldest_orphan": None
            }
            
            # Count by status
            for resource in self.resources.values():
                status = resource.status.value
                summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
                
                # Count by type
                res_type = resource.resource_type.value
                summary["by_type"][res_type] = summary["by_type"].get(res_type, 0) + 1
                
                # Track orphans
                if resource.status == ResourceStatus.ORPHANED:
                    summary["orphaned_count"] += 1
                    if not summary["oldest_orphan"] or resource.created_at < summary["oldest_orphan"]["created_at"]:
                        summary["oldest_orphan"] = {
                            "resource_id": resource.resource_id,
                            "type": resource.resource_type.value,
                            "created_at": resource.created_at.isoformat(),
                            "idle_time": str(datetime.now() - resource.last_accessed)
                        }
            
            return summary


class ResourceCleanupStrategy:
    """Strategy for cleaning up orphaned resources."""
    
    def __init__(self, detector: OrphanedResourceDetector):
        self.detector = detector
        self.cleanup_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        
    def cleanup_orphaned_resources(self,
                                  dry_run: bool = False,
                                  resource_types: Optional[List[ResourceType]] = None,
                                  max_age_hours: Optional[int] = None) -> Dict[str, Any]:
        """Clean up orphaned resources.
        
        Args:
            dry_run: If True, only report what would be cleaned
            resource_types: Limit cleanup to specific types
            max_age_hours: Only clean resources older than this
            
        Returns:
            Cleanup results
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            "cleaned": [],
            "failed": [],
            "skipped": []
        }
        
        # Get orphaned resources
        orphaned = self.detector.get_orphaned_resources()
        
        # Filter by type if specified
        if resource_types:
            orphaned = [r for r in orphaned if r.resource_type in resource_types]
        
        # Filter by age if specified
        if max_age_hours:
            cutoff = datetime.now() - timedelta(hours=max_age_hours)
            orphaned = [r for r in orphaned if r.created_at < cutoff]
        
        # Process each orphaned resource
        for resource in orphaned:
            try:
                if self._should_skip_cleanup(resource):
                    results["skipped"].append({
                        "resource_id": resource.resource_id,
                        "reason": "Protected or in use"
                    })
                    continue
                
                if not dry_run:
                    success = self._cleanup_resource(resource)
                    if success:
                        results["cleaned"].append(resource.to_dict())
                        resource.status = ResourceStatus.CLEANED
                        self.detector.remove_resource(resource.resource_id)
                    else:
                        results["failed"].append({
                            "resource": resource.to_dict(),
                            "error": "Cleanup failed"
                        })
                else:
                    # Dry run - just report
                    results["cleaned"].append(resource.to_dict())
                    
            except Exception as e:
                results["failed"].append({
                    "resource": resource.to_dict(),
                    "error": str(e)
                })
                logger.error(f"Failed to cleanup resource {resource.resource_id}: {e}")
        
        # Save cleanup history
        if not dry_run:
            with self._lock:
                self.cleanup_history.append(results)
        
        logger.info(f"Cleanup complete: {len(results['cleaned'])} cleaned, "
                   f"{len(results['failed'])} failed, {len(results['skipped'])} skipped")
        
        return results
    
    def _should_skip_cleanup(self, resource: Resource) -> bool:
        """Check if resource should be skipped from cleanup.
        
        Args:
            resource: Resource to check
            
        Returns:
            True if should skip
        """
        # Don't clean up resources that were just created
        if datetime.now() - resource.created_at < timedelta(minutes=5):
            return True
        
        # Check for protected resources in metadata
        if resource.metadata.get("protected", False):
            return True
        
        # Check if file is still open (for file handles)
        if resource.resource_type == ResourceType.FILE_HANDLE:
            try:
                # Try to check if file is in use
                if resource.path and os.path.exists(resource.path):
                    # Simple check - try to rename to itself
                    os.rename(resource.path, resource.path)
            except OSError:
                # File is in use
                return True
        
        return False
    
    def _cleanup_resource(self, resource: Resource) -> bool:
        """Clean up a specific resource.
        
        Args:
            resource: Resource to clean up
            
        Returns:
            True if successful
        """
        try:
            if resource.resource_type == ResourceType.TEMP_FILE:
                if resource.path and os.path.exists(resource.path):
                    os.remove(resource.path)
                    logger.debug(f"Removed temp file: {resource.path}")
                    
            elif resource.resource_type == ResourceType.LOCK_FILE:
                if resource.path and os.path.exists(resource.path):
                    os.remove(resource.path)
                    logger.debug(f"Removed lock file: {resource.path}")
                    
            elif resource.resource_type == ResourceType.SOCKET:
                # Socket cleanup would be implemented here
                pass
                
            elif resource.resource_type == ResourceType.PROCESS:
                # Process cleanup would be implemented here
                pass
                
            elif resource.resource_type == ResourceType.THREAD:
                # Thread cleanup would be implemented here
                pass
                
            elif resource.resource_type == ResourceType.MEMORY_BUFFER:
                # Memory cleanup would be implemented here
                pass
                
            elif resource.resource_type == ResourceType.DATABASE_CONNECTION:
                # Database connection cleanup would be implemented here
                pass
                
            elif resource.resource_type == ResourceType.FILE_HANDLE:
                # File handle cleanup would be implemented here
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup resource {resource.resource_id}: {e}")
            return False
    
    def get_cleanup_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get cleanup history.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of cleanup results
        """
        with self._lock:
            return self.cleanup_history[-limit:]
    
    def schedule_periodic_cleanup(self,
                                 interval_minutes: int = 60,
                                 resource_types: Optional[List[ResourceType]] = None):
        """Schedule periodic cleanup of orphaned resources.
        
        Args:
            interval_minutes: Cleanup interval in minutes
            resource_types: Types to clean (all if None)
        """
        def cleanup_task():
            while hasattr(self, '_cleanup_scheduled') and self._cleanup_scheduled:
                try:
                    self.cleanup_orphaned_resources(
                        dry_run=False,
                        resource_types=resource_types
                    )
                except Exception as e:
                    logger.error(f"Periodic cleanup failed: {e}")
                
                time.sleep(interval_minutes * 60)
        
        self._cleanup_scheduled = True
        cleanup_thread = threading.Thread(
            target=cleanup_task,
            daemon=True,
            name="ResourceCleanup"
        )
        cleanup_thread.start()
        logger.info(f"Scheduled periodic cleanup every {interval_minutes} minutes")
    
    def stop_periodic_cleanup(self):
        """Stop periodic cleanup."""
        self._cleanup_scheduled = False
        logger.info("Stopped periodic cleanup")


# Global resource manager instance
orphan_detector = OrphanedResourceDetector()
resource_cleanup = ResourceCleanupStrategy(orphan_detector)