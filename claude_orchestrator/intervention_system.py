"""Active Intervention Request System for Claude Orchestrator.

This module provides a system for requesting human intervention during
task execution when issues arise or decisions need to be made.
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import threading
import queue
import uuid

from .feedback_model import (
    FeedbackModel, FeedbackType, FeedbackSeverity,
    create_intervention_feedback
)
from .interactive_feedback import InteractiveFeedbackCollector, InteractionType

logger = logging.getLogger(__name__)


class InterventionType(Enum):
    """Types of interventions that can be requested."""
    DECISION_REQUIRED = "decision_required"      # Need user to make a choice
    ERROR_RECOVERY = "error_recovery"            # Error occurred, need guidance
    APPROVAL_NEEDED = "approval_needed"          # Need approval to proceed
    CLARIFICATION = "clarification"              # Need clarification on requirements
    RESOURCE_CONFLICT = "resource_conflict"      # Resource conflict needs resolution
    SECURITY_REVIEW = "security_review"          # Security issue needs review
    QUALITY_REVIEW = "quality_review"            # Quality issue needs review
    EMERGENCY_STOP = "emergency_stop"            # Critical issue, stop everything


class InterventionPriority(Enum):
    """Priority levels for interventions."""
    CRITICAL = "critical"    # Immediate attention required
    HIGH = "high"           # Important, address soon
    MEDIUM = "medium"       # Normal priority
    LOW = "low"            # Can wait
    INFO = "info"          # Informational only


class InterventionStatus(Enum):
    """Status of an intervention request."""
    PENDING = "pending"          # Waiting for response
    IN_PROGRESS = "in_progress"  # Being handled
    RESOLVED = "resolved"        # Resolved with action
    CANCELLED = "cancelled"      # Cancelled
    TIMEOUT = "timeout"          # Timed out
    AUTO_RESOLVED = "auto_resolved"  # Resolved automatically


@dataclass
class InterventionRequest:
    """Request for human intervention."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intervention_type: InterventionType = InterventionType.DECISION_REQUIRED
    priority: InterventionPriority = InterventionPriority.MEDIUM
    title: str = ""
    description: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    options: Optional[List[str]] = None  # For decision requests
    requesting_component: str = "unknown"
    task_id: Optional[str] = None
    worker_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    timeout: Optional[timedelta] = None
    auto_resolve_action: Optional[str] = None  # Action to take if timeout
    status: InterventionStatus = InterventionStatus.PENDING
    resolution: Optional[Dict[str, Any]] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "request_id": self.request_id,
            "intervention_type": self.intervention_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "context": self.context,
            "options": self.options,
            "requesting_component": self.requesting_component,
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "timestamp": self.timestamp.isoformat(),
            "timeout": str(self.timeout) if self.timeout else None,
            "auto_resolve_action": self.auto_resolve_action,
            "status": self.status.value,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by
        }


class InterventionHandler:
    """Handles intervention requests and responses."""
    
    def __init__(self, 
                 feedback_collector: Optional[InteractiveFeedbackCollector] = None,
                 auto_mode: bool = False):
        self.feedback_collector = feedback_collector
        self.auto_mode = auto_mode
        self.active_requests: Dict[str, InterventionRequest] = {}
        self.request_history: List[InterventionRequest] = []
        self.handlers: Dict[InterventionType, List[Callable]] = {}
        self._lock = threading.RLock()
        self._request_queue = queue.Queue()
        self._processing = False
        self._processor_thread = None
        
        # Start processor if not in auto mode
        if not auto_mode:
            self._start_processor()
        
        logger.info(f"Intervention handler initialized (auto_mode={auto_mode})")
    
    def _start_processor(self):
        """Start the intervention processor thread."""
        if self._processing:
            return
        
        self._processing = True
        self._processor_thread = threading.Thread(
            target=self._process_interventions,
            daemon=True,
            name="InterventionProcessor"
        )
        self._processor_thread.start()
    
    def stop(self):
        """Stop the intervention handler."""
        self._processing = False
        if self._processor_thread:
            self._request_queue.put(None)  # Sentinel
            self._processor_thread.join(timeout=5)
    
    def register_handler(self, 
                        intervention_type: InterventionType,
                        handler: Callable[[InterventionRequest], Any]):
        """Register a handler for specific intervention type.
        
        Args:
            intervention_type: Type of intervention
            handler: Handler function
        """
        with self._lock:
            if intervention_type not in self.handlers:
                self.handlers[intervention_type] = []
            self.handlers[intervention_type].append(handler)
    
    def request_intervention(self,
                           intervention_type: InterventionType,
                           title: str,
                           description: str,
                           priority: InterventionPriority = InterventionPriority.MEDIUM,
                           context: Optional[Dict[str, Any]] = None,
                           options: Optional[List[str]] = None,
                           task_id: Optional[str] = None,
                           worker_id: Optional[str] = None,
                           timeout: Optional[int] = None,
                           auto_resolve_action: Optional[str] = None,
                           requesting_component: str = "unknown") -> InterventionRequest:
        """Request human intervention.
        
        Args:
            intervention_type: Type of intervention needed
            title: Short title
            description: Detailed description
            priority: Priority level
            context: Additional context
            options: Options for decision requests
            task_id: Associated task ID
            worker_id: Associated worker ID
            timeout: Timeout in seconds
            auto_resolve_action: Action to take on timeout
            requesting_component: Component requesting intervention
            
        Returns:
            Intervention request object
        """
        request = InterventionRequest(
            intervention_type=intervention_type,
            priority=priority,
            title=title,
            description=description,
            context=context or {},
            options=options,
            requesting_component=requesting_component,
            task_id=task_id,
            worker_id=worker_id,
            timeout=timedelta(seconds=timeout) if timeout else None,
            auto_resolve_action=auto_resolve_action
        )
        
        with self._lock:
            self.active_requests[request.request_id] = request
            self.request_history.append(request)
        
        # Log the intervention request
        logger.info(
            f"Intervention requested: {intervention_type.value} - {title} "
            f"(priority: {priority.value}, id: {request.request_id})"
        )
        
        # Handle based on mode
        if self.auto_mode:
            # Auto-resolve in auto mode
            self._auto_resolve(request)
        else:
            # Queue for processing
            self._request_queue.put(request)
        
        return request
    
    def _process_interventions(self):
        """Process intervention requests."""
        while self._processing:
            try:
                # Get request with timeout
                request = self._request_queue.get(timeout=1)
                
                if request is None:  # Sentinel
                    break
                
                # Check if already resolved
                if request.status != InterventionStatus.PENDING:
                    continue
                
                # Update status
                request.status = InterventionStatus.IN_PROGRESS
                
                # Try custom handlers first
                handled = False
                if request.intervention_type in self.handlers:
                    for handler in self.handlers[request.intervention_type]:
                        try:
                            result = handler(request)
                            if result is not None:
                                self.resolve_intervention(
                                    request.request_id,
                                    resolution={"handler_result": result},
                                    resolved_by="custom_handler"
                                )
                                handled = True
                                break
                        except Exception as e:
                            logger.error(f"Error in custom handler: {e}")
                
                # If not handled and feedback collector available
                if not handled and self.feedback_collector:
                    self._handle_with_feedback_collector(request)
                
                # Check timeout
                if request.timeout and not handled:
                    elapsed = datetime.now() - request.timestamp
                    if elapsed > request.timeout:
                        self._handle_timeout(request)
                
            except queue.Empty:
                # Check for timeouts
                self._check_timeouts()
            except Exception as e:
                logger.error(f"Error processing intervention: {e}")
    
    def _handle_with_feedback_collector(self, request: InterventionRequest):
        """Handle intervention using feedback collector.
        
        Args:
            request: Intervention request
        """
        if not self.feedback_collector:
            return
        
        # Map intervention type to interaction type
        if request.intervention_type == InterventionType.DECISION_REQUIRED and request.options:
            # Use choice interaction
            self.feedback_collector.request_feedback(
                task_id=request.task_id or "intervention",
                message=f"{request.title}\n\n{request.description}",
                interaction_type=InteractionType.CHOICE,
                options=request.options,
                context=request.context,
                callback=lambda choice: self.resolve_intervention(
                    request.request_id,
                    resolution={"choice": choice},
                    resolved_by="user"
                ),
                timeout=int(request.timeout.total_seconds()) if request.timeout else None
            )
        
        elif request.intervention_type == InterventionType.APPROVAL_NEEDED:
            # Use confirmation interaction
            self.feedback_collector.request_feedback(
                task_id=request.task_id or "intervention",
                message=f"{request.title}\n\n{request.description}\n\nApprove?",
                interaction_type=InteractionType.CONFIRMATION,
                context=request.context,
                callback=lambda approved: self.resolve_intervention(
                    request.request_id,
                    resolution={"approved": approved},
                    resolved_by="user"
                ),
                timeout=int(request.timeout.total_seconds()) if request.timeout else None
            )
        
        else:
            # Use text interaction for general feedback
            self.feedback_collector.request_feedback(
                task_id=request.task_id or "intervention",
                message=f"{request.title}\n\n{request.description}\n\nPlease provide guidance:",
                interaction_type=InteractionType.TEXT,
                context=request.context,
                callback=lambda text: self.resolve_intervention(
                    request.request_id,
                    resolution={"guidance": text},
                    resolved_by="user"
                ),
                timeout=int(request.timeout.total_seconds()) if request.timeout else None
            )
    
    def _auto_resolve(self, request: InterventionRequest):
        """Auto-resolve intervention in auto mode.
        
        Args:
            request: Intervention request
        """
        resolution = {}
        
        if request.intervention_type == InterventionType.DECISION_REQUIRED:
            # Choose first option or auto-resolve action
            if request.options:
                resolution["choice"] = request.options[0]
            elif request.auto_resolve_action:
                resolution["action"] = request.auto_resolve_action
            else:
                resolution["action"] = "continue"
        
        elif request.intervention_type == InterventionType.APPROVAL_NEEDED:
            # Auto-approve in auto mode (configurable)
            resolution["approved"] = True
            resolution["note"] = "Auto-approved in auto mode"
        
        elif request.intervention_type == InterventionType.ERROR_RECOVERY:
            # Use auto-resolve action or retry
            resolution["action"] = request.auto_resolve_action or "retry"
        
        else:
            # Generic auto-resolution
            resolution["action"] = request.auto_resolve_action or "continue"
            resolution["note"] = f"Auto-resolved in auto mode"
        
        self.resolve_intervention(
            request.request_id,
            resolution=resolution,
            resolved_by="auto_mode"
        )
    
    def _handle_timeout(self, request: InterventionRequest):
        """Handle timeout for intervention request.
        
        Args:
            request: Intervention request
        """
        request.status = InterventionStatus.TIMEOUT
        
        # Use auto-resolve action if specified
        if request.auto_resolve_action:
            resolution = {"action": request.auto_resolve_action, "reason": "timeout"}
            self.resolve_intervention(
                request.request_id,
                resolution=resolution,
                resolved_by="timeout_handler"
            )
        else:
            # Mark as timeout without resolution
            request.resolved_at = datetime.now()
            logger.warning(f"Intervention request {request.request_id} timed out without resolution")
    
    def _check_timeouts(self):
        """Check for timed out requests."""
        with self._lock:
            for request_id, request in list(self.active_requests.items()):
                if request.status == InterventionStatus.PENDING and request.timeout:
                    elapsed = datetime.now() - request.timestamp
                    if elapsed > request.timeout:
                        self._handle_timeout(request)
    
    def resolve_intervention(self,
                           request_id: str,
                           resolution: Dict[str, Any],
                           resolved_by: str = "unknown"):
        """Resolve an intervention request.
        
        Args:
            request_id: Request ID
            resolution: Resolution details
            resolved_by: Who resolved it
        """
        with self._lock:
            if request_id not in self.active_requests:
                logger.warning(f"Unknown intervention request: {request_id}")
                return
            
            request = self.active_requests[request_id]
            request.status = InterventionStatus.RESOLVED
            request.resolution = resolution
            request.resolved_at = datetime.now()
            request.resolved_by = resolved_by
            
            # Remove from active
            del self.active_requests[request_id]
            
            logger.info(
                f"Intervention resolved: {request_id} by {resolved_by} "
                f"(type: {request.intervention_type.value})"
            )
    
    def cancel_intervention(self, request_id: str):
        """Cancel an intervention request.
        
        Args:
            request_id: Request ID to cancel
        """
        with self._lock:
            if request_id in self.active_requests:
                request = self.active_requests[request_id]
                request.status = InterventionStatus.CANCELLED
                request.resolved_at = datetime.now()
                del self.active_requests[request_id]
                logger.info(f"Intervention cancelled: {request_id}")
    
    def get_active_interventions(self, 
                               priority: Optional[InterventionPriority] = None,
                               intervention_type: Optional[InterventionType] = None) -> List[InterventionRequest]:
        """Get active intervention requests.
        
        Args:
            priority: Filter by priority
            intervention_type: Filter by type
            
        Returns:
            List of active interventions
        """
        with self._lock:
            interventions = list(self.active_requests.values())
            
            if priority:
                interventions = [i for i in interventions if i.priority == priority]
            
            if intervention_type:
                interventions = [i for i in interventions if i.intervention_type == intervention_type]
            
            return sorted(interventions, key=lambda x: (
                list(InterventionPriority).index(x.priority),
                x.timestamp
            ))
    
    def get_intervention_stats(self) -> Dict[str, Any]:
        """Get intervention statistics.
        
        Returns:
            Statistics dictionary
        """
        with self._lock:
            total = len(self.request_history)
            active = len(self.active_requests)
            
            stats = {
                "total_requests": total,
                "active_requests": active,
                "resolved_requests": sum(1 for r in self.request_history 
                                       if r.status == InterventionStatus.RESOLVED),
                "timeout_requests": sum(1 for r in self.request_history 
                                      if r.status == InterventionStatus.TIMEOUT),
                "cancelled_requests": sum(1 for r in self.request_history 
                                        if r.status == InterventionStatus.CANCELLED),
                "by_type": {},
                "by_priority": {},
                "average_resolution_time": timedelta(0)
            }
            
            # Count by type and priority
            resolution_times = []
            
            for request in self.request_history:
                # By type
                type_key = request.intervention_type.value
                stats["by_type"][type_key] = stats["by_type"].get(type_key, 0) + 1
                
                # By priority
                priority_key = request.priority.value
                stats["by_priority"][priority_key] = stats["by_priority"].get(priority_key, 0) + 1
                
                # Resolution time
                if request.resolved_at and request.status == InterventionStatus.RESOLVED:
                    resolution_times.append(request.resolved_at - request.timestamp)
            
            # Average resolution time
            if resolution_times:
                avg_time = sum(resolution_times, timedelta(0)) / len(resolution_times)
                stats["average_resolution_time"] = str(avg_time)
            
            return stats


class InterventionTriggers:
    """Triggers for automatic intervention requests."""
    
    def __init__(self, intervention_handler: InterventionHandler):
        self.handler = intervention_handler
        self.thresholds = {
            "error_count": 3,         # Errors before intervention
            "failure_rate": 0.5,      # Failure rate threshold
            "resource_usage": 0.9,    # Resource usage threshold
            "security_violations": 1,  # Security violations before intervention
            "quality_score": 0.6      # Quality score threshold
        }
        self.metrics = {
            "error_count": 0,
            "total_tasks": 0,
            "failed_tasks": 0,
            "resource_usage": 0.0,
            "security_violations": 0,
            "quality_scores": []
        }
    
    def check_error_threshold(self, error_count: int) -> Optional[InterventionRequest]:
        """Check if error threshold exceeded.
        
        Args:
            error_count: Current error count
            
        Returns:
            Intervention request if threshold exceeded
        """
        self.metrics["error_count"] = error_count
        
        if error_count >= self.thresholds["error_count"]:
            return self.handler.request_intervention(
                intervention_type=InterventionType.ERROR_RECOVERY,
                title="High Error Rate Detected",
                description=f"Error count ({error_count}) exceeds threshold ({self.thresholds['error_count']})",
                priority=InterventionPriority.HIGH,
                context={
                    "error_count": error_count,
                    "threshold": self.thresholds["error_count"]
                },
                options=["Continue", "Pause execution", "Rollback", "Debug mode"],
                auto_resolve_action="continue"
            )
        return None
    
    def check_failure_rate(self, total_tasks: int, failed_tasks: int) -> Optional[InterventionRequest]:
        """Check if failure rate threshold exceeded.
        
        Args:
            total_tasks: Total tasks
            failed_tasks: Failed tasks
            
        Returns:
            Intervention request if threshold exceeded
        """
        self.metrics["total_tasks"] = total_tasks
        self.metrics["failed_tasks"] = failed_tasks
        
        if total_tasks > 0:
            failure_rate = failed_tasks / total_tasks
            
            if failure_rate >= self.thresholds["failure_rate"]:
                return self.handler.request_intervention(
                    intervention_type=InterventionType.DECISION_REQUIRED,
                    title="High Failure Rate",
                    description=f"Task failure rate ({failure_rate:.1%}) exceeds threshold ({self.thresholds['failure_rate']:.1%})",
                    priority=InterventionPriority.HIGH,
                    context={
                        "total_tasks": total_tasks,
                        "failed_tasks": failed_tasks,
                        "failure_rate": failure_rate
                    },
                    options=["Continue with remaining tasks", "Stop and review", "Retry failed tasks"],
                    auto_resolve_action="continue"
                )
        return None
    
    def check_resource_usage(self, cpu_percent: float, memory_percent: float) -> Optional[InterventionRequest]:
        """Check if resource usage threshold exceeded.
        
        Args:
            cpu_percent: CPU usage percentage
            memory_percent: Memory usage percentage
            
        Returns:
            Intervention request if threshold exceeded
        """
        max_usage = max(cpu_percent, memory_percent) / 100.0
        self.metrics["resource_usage"] = max_usage
        
        if max_usage >= self.thresholds["resource_usage"]:
            return self.handler.request_intervention(
                intervention_type=InterventionType.RESOURCE_CONFLICT,
                title="High Resource Usage",
                description=f"Resource usage (CPU: {cpu_percent}%, Memory: {memory_percent}%) is critical",
                priority=InterventionPriority.CRITICAL,
                context={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent
                },
                options=["Reduce worker count", "Pause execution", "Continue anyway"],
                auto_resolve_action="continue"
            )
        return None
    
    def check_security_violations(self, violations: int) -> Optional[InterventionRequest]:
        """Check if security violations threshold exceeded.
        
        Args:
            violations: Number of security violations
            
        Returns:
            Intervention request if threshold exceeded
        """
        self.metrics["security_violations"] = violations
        
        if violations >= self.thresholds["security_violations"]:
            return self.handler.request_intervention(
                intervention_type=InterventionType.SECURITY_REVIEW,
                title="Security Violations Detected",
                description=f"Detected {violations} security violations",
                priority=InterventionPriority.CRITICAL,
                context={
                    "violations": violations,
                    "threshold": self.thresholds["security_violations"]
                },
                options=["Stop execution", "Continue with restrictions", "Review and continue"],
                auto_resolve_action="stop"
            )
        return None
    
    def check_quality_score(self, quality_score: float, task_id: str) -> Optional[InterventionRequest]:
        """Check if quality score below threshold.
        
        Args:
            quality_score: Quality score (0.0-1.0)
            task_id: Task ID
            
        Returns:
            Intervention request if threshold not met
        """
        self.metrics["quality_scores"].append(quality_score)
        
        if quality_score < self.thresholds["quality_score"]:
            return self.handler.request_intervention(
                intervention_type=InterventionType.QUALITY_REVIEW,
                title="Low Quality Score",
                description=f"Task {task_id} quality score ({quality_score:.2f}) below threshold ({self.thresholds['quality_score']})",
                priority=InterventionPriority.MEDIUM,
                context={
                    "quality_score": quality_score,
                    "task_id": task_id,
                    "threshold": self.thresholds["quality_score"]
                },
                options=["Accept anyway", "Retry task", "Manual review"],
                task_id=task_id,
                auto_resolve_action="accept"
            )
        return None


class InterventionSystem:
    """Main intervention system integrating all components."""
    
    def __init__(self,
                 feedback_collector: Optional[InteractiveFeedbackCollector] = None,
                 auto_mode: bool = False,
                 storage: Optional[Any] = None):
        self.handler = InterventionHandler(feedback_collector, auto_mode)
        self.triggers = InterventionTriggers(self.handler)
        self.storage = storage
        
        # Register default handlers
        self._register_default_handlers()
        
        logger.info("Intervention system initialized")
    
    def _register_default_handlers(self):
        """Register default intervention handlers."""
        # Emergency stop handler
        def emergency_stop_handler(request: InterventionRequest):
            logger.critical(f"EMERGENCY STOP requested: {request.description}")
            # In real implementation, would trigger immediate shutdown
            return {"action": "emergency_stop", "timestamp": datetime.now().isoformat()}
        
        self.handler.register_handler(
            InterventionType.EMERGENCY_STOP,
            emergency_stop_handler
        )
    
    def request_user_decision(self,
                            title: str,
                            description: str,
                            options: List[str],
                            context: Optional[Dict[str, Any]] = None,
                            timeout: Optional[int] = None) -> InterventionRequest:
        """Request user decision between options.
        
        Args:
            title: Decision title
            description: Decision description
            options: Available options
            context: Additional context
            timeout: Timeout in seconds
            
        Returns:
            Intervention request
        """
        return self.handler.request_intervention(
            intervention_type=InterventionType.DECISION_REQUIRED,
            title=title,
            description=description,
            options=options,
            context=context,
            timeout=timeout,
            priority=InterventionPriority.HIGH
        )
    
    def request_error_guidance(self,
                             error: str,
                             task_id: Optional[str] = None,
                             worker_id: Optional[str] = None,
                             suggestions: Optional[List[str]] = None) -> InterventionRequest:
        """Request guidance for error recovery.
        
        Args:
            error: Error description
            task_id: Task where error occurred
            worker_id: Worker that encountered error
            suggestions: Suggested recovery actions
            
        Returns:
            Intervention request
        """
        return self.handler.request_intervention(
            intervention_type=InterventionType.ERROR_RECOVERY,
            title="Error Recovery Needed",
            description=f"Error occurred: {error}",
            priority=InterventionPriority.HIGH,
            context={
                "error": error,
                "suggestions": suggestions
            },
            options=suggestions,
            task_id=task_id,
            worker_id=worker_id,
            timeout=300,  # 5 minutes
            auto_resolve_action="retry"
        )
    
    def request_approval(self,
                        action: str,
                        details: str,
                        risk_level: str = "medium") -> InterventionRequest:
        """Request approval for an action.
        
        Args:
            action: Action requiring approval
            details: Action details
            risk_level: Risk level (low/medium/high)
            
        Returns:
            Intervention request
        """
        priority_map = {
            "low": InterventionPriority.LOW,
            "medium": InterventionPriority.MEDIUM,
            "high": InterventionPriority.HIGH,
            "critical": InterventionPriority.CRITICAL
        }
        
        return self.handler.request_intervention(
            intervention_type=InterventionType.APPROVAL_NEEDED,
            title=f"Approval Required: {action}",
            description=details,
            priority=priority_map.get(risk_level, InterventionPriority.MEDIUM),
            context={
                "action": action,
                "risk_level": risk_level
            },
            timeout=600  # 10 minutes
        )
    
    def check_metrics_and_trigger(self, metrics: Dict[str, Any]) -> List[InterventionRequest]:
        """Check metrics and trigger interventions if needed.
        
        Args:
            metrics: Current system metrics
            
        Returns:
            List of triggered intervention requests
        """
        triggered = []
        
        # Check various thresholds
        if "error_count" in metrics:
            req = self.triggers.check_error_threshold(metrics["error_count"])
            if req:
                triggered.append(req)
        
        if "total_tasks" in metrics and "failed_tasks" in metrics:
            req = self.triggers.check_failure_rate(
                metrics["total_tasks"],
                metrics["failed_tasks"]
            )
            if req:
                triggered.append(req)
        
        if "cpu_percent" in metrics and "memory_percent" in metrics:
            req = self.triggers.check_resource_usage(
                metrics["cpu_percent"],
                metrics["memory_percent"]
            )
            if req:
                triggered.append(req)
        
        if "security_violations" in metrics:
            req = self.triggers.check_security_violations(metrics["security_violations"])
            if req:
                triggered.append(req)
        
        return triggered
    
    def shutdown(self):
        """Shutdown the intervention system."""
        self.handler.stop()
        logger.info("Intervention system shut down")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get intervention system statistics.
        
        Returns:
            System statistics
        """
        stats = self.handler.get_intervention_stats()
        stats["trigger_metrics"] = self.triggers.metrics
        stats["trigger_thresholds"] = self.triggers.thresholds
        return stats


# Integration with orchestrator
def integrate_intervention_system(orchestrator, auto_mode: Optional[bool] = None) -> InterventionSystem:
    """Integrate intervention system with orchestrator.
    
    Args:
        orchestrator: Orchestrator instance
        auto_mode: Override auto mode setting
        
    Returns:
        Intervention system instance
    """
    # Use interactive feedback collector if available
    feedback_collector = None
    if hasattr(orchestrator, 'interactive_feedback') and orchestrator.interactive_feedback:
        feedback_collector = orchestrator.interactive_feedback.collector
    
    # Determine auto mode
    if auto_mode is None:
        auto_mode = not getattr(orchestrator.config, 'interactive_feedback', {}).get('enabled', False)
    
    # Create intervention system
    intervention_system = InterventionSystem(
        feedback_collector=feedback_collector,
        auto_mode=auto_mode,
        storage=getattr(orchestrator, 'feedback_storage', None)
    )
    
    # Store reference in orchestrator
    orchestrator.intervention_system = intervention_system
    
    # Add hooks for automatic interventions
    if hasattr(orchestrator, 'workers'):
        # Monitor worker errors
        original_process = None
        for worker in orchestrator.workers:
            if hasattr(worker, 'process_task'):
                original_process = worker.process_task
                
                def monitored_process(task, original=original_process):
                    try:
                        result = original(task)
                        return result
                    except Exception as e:
                        # Request intervention for errors
                        intervention_system.request_error_guidance(
                            error=str(e),
                            task_id=task.task_id if hasattr(task, 'task_id') else None,
                            worker_id=worker.worker_id if hasattr(worker, 'worker_id') else None
                        )
                        raise
                
                worker.process_task = monitored_process
    
    logger.info("Intervention system integrated with orchestrator")
    
    return intervention_system