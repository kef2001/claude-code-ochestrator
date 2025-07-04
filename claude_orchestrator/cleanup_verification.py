"""Cleanup verification system for ensuring resources are properly cleaned up."""

import os
import json
import logging
import psutil
import tempfile
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
import threading
import time

from .resource_manager import (
    OrphanedResourceDetector, ResourceCleanupStrategy, 
    ResourceType, ResourceStatus, Resource
)

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of cleanup verification."""
    success: bool
    resource_id: str
    resource_type: ResourceType
    verification_type: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type.value,
            "verification_type": self.verification_type,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


class CleanupVerifier:
    """Verifies that resource cleanup was successful."""
    
    def __init__(self, 
                 verification_log: str = ".cleanup_verification.log"):
        self.verification_log = verification_log
        self.verification_history: List[VerificationResult] = []
        self._lock = threading.Lock()
        
        # System resource baseline
        self.baseline_metrics = self._capture_system_metrics()
        
        logger.info("Cleanup verifier initialized")
    
    def _capture_system_metrics(self) -> Dict[str, Any]:
        """Capture current system resource metrics."""
        try:
            process = psutil.Process()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "memory": {
                    "rss": process.memory_info().rss,
                    "vms": process.memory_info().vms,
                    "percent": process.memory_percent()
                },
                "files": {
                    "open_files": len(process.open_files()),
                    "connections": len(process.connections())
                },
                "threads": process.num_threads(),
                "cpu_percent": process.cpu_percent(interval=0.1)
            }
        except Exception as e:
            logger.error(f"Failed to capture system metrics: {e}")
            return {}
    
    def verify_resource_cleanup(self, resource: Resource) -> VerificationResult:
        """Verify that a resource has been properly cleaned up.
        
        Args:
            resource: Resource that was cleaned
            
        Returns:
            Verification result
        """
        if resource.resource_type == ResourceType.TEMP_FILE:
            return self._verify_file_cleanup(resource)
        elif resource.resource_type == ResourceType.LOCK_FILE:
            return self._verify_lock_file_cleanup(resource)
        elif resource.resource_type == ResourceType.SOCKET:
            return self._verify_socket_cleanup(resource)
        elif resource.resource_type == ResourceType.PROCESS:
            return self._verify_process_cleanup(resource)
        elif resource.resource_type == ResourceType.THREAD:
            return self._verify_thread_cleanup(resource)
        elif resource.resource_type == ResourceType.MEMORY_BUFFER:
            return self._verify_memory_cleanup(resource)
        elif resource.resource_type == ResourceType.DATABASE_CONNECTION:
            return self._verify_database_cleanup(resource)
        elif resource.resource_type == ResourceType.FILE_HANDLE:
            return self._verify_file_handle_cleanup(resource)
        else:
            return VerificationResult(
                success=False,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="unknown",
                message=f"Unknown resource type: {resource.resource_type}"
            )
    
    def _verify_file_cleanup(self, resource: Resource) -> VerificationResult:
        """Verify temp file cleanup."""
        if not resource.path:
            return VerificationResult(
                success=True,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="file_existence",
                message="No file path specified"
            )
        
        # Check if file exists
        if os.path.exists(resource.path):
            return VerificationResult(
                success=False,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="file_existence",
                message=f"File still exists: {resource.path}",
                details={"path": resource.path, "exists": True}
            )
        
        # Check parent directory for any related files
        parent_dir = os.path.dirname(resource.path)
        filename = os.path.basename(resource.path)
        related_files = []
        
        if os.path.exists(parent_dir):
            for f in os.listdir(parent_dir):
                if filename in f or f.startswith(f"{filename}."):
                    related_files.append(f)
        
        if related_files:
            return VerificationResult(
                success=False,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="related_files",
                message=f"Related files still exist",
                details={"related_files": related_files}
            )
        
        return VerificationResult(
            success=True,
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            verification_type="file_cleanup",
            message="File successfully cleaned up",
            details={"path": resource.path}
        )
    
    def _verify_lock_file_cleanup(self, resource: Resource) -> VerificationResult:
        """Verify lock file cleanup."""
        # Similar to temp file verification
        return self._verify_file_cleanup(resource)
    
    def _verify_socket_cleanup(self, resource: Resource) -> VerificationResult:
        """Verify socket cleanup."""
        try:
            process = psutil.Process()
            connections = process.connections()
            
            # Check if socket info is in metadata
            socket_info = resource.metadata.get("socket_info", {})
            port = socket_info.get("port")
            
            if port:
                for conn in connections:
                    if conn.laddr.port == port:
                        return VerificationResult(
                            success=False,
                            resource_id=resource.resource_id,
                            resource_type=resource.resource_type,
                            verification_type="socket_connection",
                            message=f"Socket still open on port {port}",
                            details={"port": port, "status": conn.status}
                        )
            
            return VerificationResult(
                success=True,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="socket_cleanup",
                message="Socket successfully cleaned up"
            )
            
        except Exception as e:
            return VerificationResult(
                success=False,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="socket_verification_error",
                message=f"Failed to verify socket cleanup: {e}"
            )
    
    def _verify_process_cleanup(self, resource: Resource) -> VerificationResult:
        """Verify process cleanup."""
        try:
            pid = resource.metadata.get("pid")
            if not pid:
                return VerificationResult(
                    success=True,
                    resource_id=resource.resource_id,
                    resource_type=resource.resource_type,
                    verification_type="process_cleanup",
                    message="No PID specified"
                )
            
            # Check if process exists
            if psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    return VerificationResult(
                        success=False,
                        resource_id=resource.resource_id,
                        resource_type=resource.resource_type,
                        verification_type="process_existence",
                        message=f"Process {pid} still running",
                        details={
                            "pid": pid,
                            "name": proc.name(),
                            "status": proc.status()
                        }
                    )
                except psutil.NoSuchProcess:
                    pass
            
            return VerificationResult(
                success=True,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="process_cleanup",
                message=f"Process {pid} successfully terminated"
            )
            
        except Exception as e:
            return VerificationResult(
                success=False,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="process_verification_error",
                message=f"Failed to verify process cleanup: {e}"
            )
    
    def _verify_thread_cleanup(self, resource: Resource) -> VerificationResult:
        """Verify thread cleanup."""
        thread_name = resource.metadata.get("thread_name")
        
        if thread_name:
            # Check if thread is still active
            for thread in threading.enumerate():
                if thread.name == thread_name:
                    return VerificationResult(
                        success=False,
                        resource_id=resource.resource_id,
                        resource_type=resource.resource_type,
                        verification_type="thread_active",
                        message=f"Thread '{thread_name}' still active",
                        details={
                            "thread_name": thread_name,
                            "is_alive": thread.is_alive()
                        }
                    )
        
        return VerificationResult(
            success=True,
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            verification_type="thread_cleanup",
            message="Thread successfully cleaned up"
        )
    
    def _verify_memory_cleanup(self, resource: Resource) -> VerificationResult:
        """Verify memory cleanup."""
        # Compare current memory usage with baseline
        current_metrics = self._capture_system_metrics()
        
        if not current_metrics or not self.baseline_metrics:
            return VerificationResult(
                success=True,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="memory_cleanup",
                message="Unable to verify memory cleanup"
            )
        
        # Check for memory leak indicators
        baseline_rss = self.baseline_metrics.get("memory", {}).get("rss", 0)
        current_rss = current_metrics.get("memory", {}).get("rss", 0)
        
        # Allow for some variance (10MB)
        variance_threshold = 10 * 1024 * 1024  # 10MB in bytes
        
        if current_rss > baseline_rss + variance_threshold:
            return VerificationResult(
                success=False,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="memory_leak",
                message="Potential memory leak detected",
                details={
                    "baseline_rss": baseline_rss,
                    "current_rss": current_rss,
                    "increase": current_rss - baseline_rss
                }
            )
        
        return VerificationResult(
            success=True,
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            verification_type="memory_cleanup",
            message="Memory successfully cleaned up"
        )
    
    def _verify_database_cleanup(self, resource: Resource) -> VerificationResult:
        """Verify database connection cleanup."""
        # This would be implemented based on specific database system
        return VerificationResult(
            success=True,
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            verification_type="database_cleanup",
            message="Database connection cleanup assumed successful"
        )
    
    def _verify_file_handle_cleanup(self, resource: Resource) -> VerificationResult:
        """Verify file handle cleanup."""
        try:
            process = psutil.Process()
            open_files = process.open_files()
            
            file_path = resource.path or resource.metadata.get("file_path")
            
            if file_path:
                for open_file in open_files:
                    if open_file.path == file_path:
                        return VerificationResult(
                            success=False,
                            resource_id=resource.resource_id,
                            resource_type=resource.resource_type,
                            verification_type="file_handle_open",
                            message=f"File handle still open: {file_path}",
                            details={"path": file_path}
                        )
            
            return VerificationResult(
                success=True,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="file_handle_cleanup",
                message="File handle successfully closed"
            )
            
        except Exception as e:
            return VerificationResult(
                success=False,
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                verification_type="file_handle_verification_error",
                message=f"Failed to verify file handle cleanup: {e}"
            )
    
    def verify_batch_cleanup(self, 
                            resources: List[Resource],
                            parallel: bool = True) -> Dict[str, Any]:
        """Verify cleanup of multiple resources.
        
        Args:
            resources: List of resources to verify
            parallel: Whether to verify in parallel
            
        Returns:
            Batch verification results
        """
        results = {
            "total": len(resources),
            "successful": 0,
            "failed": 0,
            "results": [],
            "summary": {}
        }
        
        if parallel and len(resources) > 1:
            # Parallel verification
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_resource = {
                    executor.submit(self.verify_resource_cleanup, resource): resource
                    for resource in resources
                }
                
                for future in concurrent.futures.as_completed(future_to_resource):
                    result = future.result()
                    results["results"].append(result.to_dict())
                    
                    if result.success:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
        else:
            # Sequential verification
            for resource in resources:
                result = self.verify_resource_cleanup(resource)
                results["results"].append(result.to_dict())
                
                if result.success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
        
        # Summary by resource type
        for result in results["results"]:
            res_type = result["resource_type"]
            if res_type not in results["summary"]:
                results["summary"][res_type] = {"successful": 0, "failed": 0}
            
            if result["success"]:
                results["summary"][res_type]["successful"] += 1
            else:
                results["summary"][res_type]["failed"] += 1
        
        # Save verification history
        with self._lock:
            self.verification_history.extend([
                VerificationResult(**r) for r in results["results"]
            ])
            self._save_verification_log(results)
        
        return results
    
    def _save_verification_log(self, results: Dict[str, Any]):
        """Save verification results to log file."""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "results": results
            }
            
            # Append to log file
            with open(self.verification_log, 'a') as f:
                f.write(json.dumps(log_entry) + "\n")
                
        except Exception as e:
            logger.error(f"Failed to save verification log: {e}")
    
    def get_verification_summary(self, 
                                hours: int = 24) -> Dict[str, Any]:
        """Get summary of verification results.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Verification summary
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            recent_results = [
                r for r in self.verification_history
                if r.timestamp > cutoff
            ]
        
        summary = {
            "period_hours": hours,
            "total_verifications": len(recent_results),
            "successful": sum(1 for r in recent_results if r.success),
            "failed": sum(1 for r in recent_results if not r.success),
            "by_type": {},
            "failure_reasons": {}
        }
        
        # Analyze by resource type
        for result in recent_results:
            res_type = result.resource_type.value
            if res_type not in summary["by_type"]:
                summary["by_type"][res_type] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0
                }
            
            summary["by_type"][res_type]["total"] += 1
            if result.success:
                summary["by_type"][res_type]["successful"] += 1
            else:
                summary["by_type"][res_type]["failed"] += 1
                
                # Track failure reasons
                reason = result.verification_type
                if reason not in summary["failure_reasons"]:
                    summary["failure_reasons"][reason] = 0
                summary["failure_reasons"][reason] += 1
        
        # Calculate success rate
        if summary["total_verifications"] > 0:
            summary["success_rate"] = (
                summary["successful"] / summary["total_verifications"]
            )
        else:
            summary["success_rate"] = 0.0
        
        return summary
    
    def perform_system_health_check(self) -> Dict[str, Any]:
        """Perform overall system health check after cleanup.
        
        Returns:
            System health report
        """
        current_metrics = self._capture_system_metrics()
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "issues": [],
            "metrics": current_metrics,
            "comparisons": {}
        }
        
        if not current_metrics or not self.baseline_metrics:
            health_report["status"] = "unknown"
            health_report["issues"].append("Unable to capture system metrics")
            return health_report
        
        # Memory check
        baseline_memory = self.baseline_metrics.get("memory", {})
        current_memory = current_metrics.get("memory", {})
        
        memory_increase = current_memory.get("rss", 0) - baseline_memory.get("rss", 0)
        health_report["comparisons"]["memory_increase"] = memory_increase
        
        if memory_increase > 50 * 1024 * 1024:  # 50MB threshold
            health_report["status"] = "warning"
            health_report["issues"].append(
                f"Memory usage increased by {memory_increase / 1024 / 1024:.1f}MB"
            )
        
        # File handle check
        baseline_files = self.baseline_metrics.get("files", {})
        current_files = current_metrics.get("files", {})
        
        file_handle_increase = (
            current_files.get("open_files", 0) - 
            baseline_files.get("open_files", 0)
        )
        health_report["comparisons"]["file_handle_increase"] = file_handle_increase
        
        if file_handle_increase > 10:
            health_report["status"] = "warning"
            health_report["issues"].append(
                f"Open file handles increased by {file_handle_increase}"
            )
        
        # Thread check
        thread_increase = (
            current_metrics.get("threads", 0) - 
            self.baseline_metrics.get("threads", 0)
        )
        health_report["comparisons"]["thread_increase"] = thread_increase
        
        if thread_increase > 5:
            health_report["status"] = "warning"
            health_report["issues"].append(
                f"Thread count increased by {thread_increase}"
            )
        
        return health_report


# Integration with cleanup strategy
class VerifiedCleanupStrategy(ResourceCleanupStrategy):
    """Cleanup strategy with built-in verification."""
    
    def __init__(self, 
                 detector: OrphanedResourceDetector,
                 verifier: Optional[CleanupVerifier] = None):
        super().__init__(detector)
        self.verifier = verifier or CleanupVerifier()
        
    def cleanup_orphaned_resources(self,
                                  dry_run: bool = False,
                                  resource_types: Optional[List[ResourceType]] = None,
                                  max_age_hours: Optional[int] = None,
                                  verify: bool = True) -> Dict[str, Any]:
        """Clean up orphaned resources with verification.
        
        Args:
            dry_run: If True, only report what would be cleaned
            resource_types: Limit cleanup to specific types
            max_age_hours: Only clean resources older than this
            verify: Whether to verify cleanup success
            
        Returns:
            Cleanup results with verification
        """
        # Perform cleanup
        results = super().cleanup_orphaned_resources(
            dry_run=dry_run,
            resource_types=resource_types,
            max_age_hours=max_age_hours
        )
        
        # Skip verification for dry runs
        if dry_run or not verify:
            return results
        
        # Verify cleaned resources
        cleaned_resources = []
        for cleaned_dict in results.get("cleaned", []):
            resource = Resource.from_dict(cleaned_dict)
            cleaned_resources.append(resource)
        
        if cleaned_resources:
            verification_results = self.verifier.verify_batch_cleanup(
                cleaned_resources
            )
            results["verification"] = verification_results
            
            # Update overall success based on verification
            if verification_results["failed"] > 0:
                results["verification_failed"] = verification_results["failed"]
                logger.warning(
                    f"Cleanup verification failed for {verification_results['failed']} resources"
                )
        
        # Perform system health check
        health_check = self.verifier.perform_system_health_check()
        results["system_health"] = health_check
        
        return results