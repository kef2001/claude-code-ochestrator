"""
Task Execution Tracing System
Provides detailed tracking and analysis of task execution flows
"""

import logging
import time
import json
import threading
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import uuid
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class TraceEventType(Enum):
    """Types of trace events"""
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    SUBTASK_CREATED = "subtask_created"
    WORKER_ASSIGNED = "worker_assigned"
    WORKER_RELEASED = "worker_released"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    CHECKPOINT_CREATED = "checkpoint_created"
    VALIDATION_PERFORMED = "validation_performed"
    RETRY_ATTEMPT = "retry_attempt"
    DEPENDENCY_RESOLVED = "dependency_resolved"
    ERROR_OCCURRED = "error_occurred"
    CUSTOM_EVENT = "custom_event"


class TraceLevel(Enum):
    """Trace detail levels"""
    MINIMAL = "minimal"      # Only major events
    STANDARD = "standard"    # Standard detail level
    DETAILED = "detailed"    # All events including tool calls
    DEBUG = "debug"          # Everything including internal operations


@dataclass
class TraceEvent:
    """Individual trace event"""
    event_id: str
    trace_id: str
    task_id: str
    event_type: TraceEventType
    timestamp: datetime
    worker_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    duration_ms: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "worker_id": self.worker_id,
            "parent_event_id": self.parent_event_id,
            "duration_ms": self.duration_ms,
            "details": self.details,
            "metadata": self.metadata,
            "tags": list(self.tags)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TraceEvent':
        """Create from dictionary"""
        data = data.copy()
        data['event_type'] = TraceEventType(data['event_type'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['tags'] = set(data.get('tags', []))
        return cls(**data)


@dataclass
class ExecutionTrace:
    """Complete execution trace for a task"""
    trace_id: str
    task_id: str
    task_title: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"  # running, completed, failed
    events: List[TraceEvent] = field(default_factory=list)
    worker_assignments: Dict[str, List[str]] = field(default_factory=dict)  # worker_id -> event_ids
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    error_summary: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_event(self, event: TraceEvent):
        """Add an event to the trace"""
        self.events.append(event)
        
        # Track worker assignments
        if event.worker_id:
            if event.worker_id not in self.worker_assignments:
                self.worker_assignments[event.worker_id] = []
            self.worker_assignments[event.worker_id].append(event.event_id)
    
    def get_duration_ms(self) -> float:
        """Get total execution duration"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        else:
            return (datetime.now() - self.started_at).total_seconds() * 1000
    
    def get_events_by_type(self, event_type: TraceEventType) -> List[TraceEvent]:
        """Get events of a specific type"""
        return [e for e in self.events if e.event_type == event_type]
    
    def get_events_by_worker(self, worker_id: str) -> List[TraceEvent]:
        """Get events for a specific worker"""
        return [e for e in self.events if e.worker_id == worker_id]
    
    def get_timeline(self) -> List[Tuple[datetime, str, str]]:
        """Get timeline of events as (timestamp, event_type, description)"""
        timeline = []
        for event in sorted(self.events, key=lambda e: e.timestamp):
            description = f"{event.event_type.value}"
            if event.worker_id:
                description += f" (worker: {event.worker_id})"
            if event.details:
                key_detail = next(iter(event.details.values())) if event.details else ""
                if isinstance(key_detail, str) and len(key_detail) < 50:
                    description += f" - {key_detail}"
            timeline.append((event.timestamp, event.event_type.value, description))
        return timeline


class ExecutionTracer:
    """
    Main execution tracer that tracks task execution
    """
    
    def __init__(self, trace_level: TraceLevel = TraceLevel.STANDARD,
                 storage_dir: str = ".taskmaster/traces"):
        self.trace_level = trace_level
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.active_traces: Dict[str, ExecutionTrace] = {}
        self.completed_traces: deque = deque(maxlen=1000)  # Keep last 1000 completed traces
        self.trace_statistics: Dict[str, Any] = defaultdict(int)
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Event context stack for hierarchical events
        self._context_stack: Dict[str, List[str]] = defaultdict(list)  # task_id -> event_id stack
        
        logger.info(f"Execution tracer initialized with level {trace_level.value}")
    
    def start_trace(self, task_id: str, task_title: str) -> str:
        """
        Start a new execution trace
        
        Args:
            task_id: Task identifier
            task_title: Task title
            
        Returns:
            Trace ID
        """
        with self._lock:
            trace_id = f"trace_{task_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            trace = ExecutionTrace(
                trace_id=trace_id,
                task_id=task_id,
                task_title=task_title,
                started_at=datetime.now()
            )
            
            self.active_traces[trace_id] = trace
            
            # Add initial event
            self._add_event(
                trace_id=trace_id,
                task_id=task_id,
                event_type=TraceEventType.TASK_STARTED,
                details={"task_title": task_title}
            )
            
            logger.debug(f"Started trace {trace_id} for task {task_id}")
            return trace_id
    
    def complete_trace(self, trace_id: str, success: bool = True, 
                      final_details: Dict[str, Any] = None):
        """
        Complete an execution trace
        
        Args:
            trace_id: Trace identifier
            success: Whether task completed successfully
            final_details: Final details to record
        """
        with self._lock:
            if trace_id not in self.active_traces:
                logger.warning(f"Trace {trace_id} not found in active traces")
                return
            
            trace = self.active_traces[trace_id]
            trace.completed_at = datetime.now()
            trace.status = "completed" if success else "failed"
            
            # Add completion event
            event_type = TraceEventType.TASK_COMPLETED if success else TraceEventType.TASK_FAILED
            self._add_event(
                trace_id=trace_id,
                task_id=trace.task_id,
                event_type=event_type,
                details=final_details or {},
                duration_ms=trace.get_duration_ms()
            )
            
            # Calculate performance metrics
            trace.performance_metrics = self._calculate_performance_metrics(trace)
            
            # Move to completed traces
            self.completed_traces.append(trace)
            del self.active_traces[trace_id]
            
            # Update statistics
            self.trace_statistics["total_completed"] += 1
            self.trace_statistics[f"total_{trace.status}"] += 1
            
            # Save trace if configured
            self._save_trace(trace)
            
            logger.debug(f"Completed trace {trace_id} with status {trace.status}")
    
    def add_event(self, trace_id: str, task_id: str, event_type: TraceEventType,
                 worker_id: str = None, details: Dict[str, Any] = None,
                 metadata: Dict[str, Any] = None, tags: Set[str] = None,
                 duration_ms: float = None) -> str:
        """
        Add an event to a trace
        
        Args:
            trace_id: Trace identifier
            task_id: Task identifier
            event_type: Type of event
            worker_id: Worker responsible for event
            details: Event details
            metadata: Additional metadata
            tags: Event tags
            duration_ms: Event duration
            
        Returns:
            Event ID
        """
        with self._lock:
            return self._add_event(
                trace_id=trace_id,
                task_id=task_id,
                event_type=event_type,
                worker_id=worker_id,
                details=details or {},
                metadata=metadata or {},
                tags=tags or set(),
                duration_ms=duration_ms
            )
    
    def _add_event(self, trace_id: str, task_id: str, event_type: TraceEventType,
                  worker_id: str = None, details: Dict[str, Any] = None,
                  metadata: Dict[str, Any] = None, tags: Set[str] = None,
                  duration_ms: float = None) -> str:
        """Internal method to add event (assumes lock is held)"""
        if trace_id not in self.active_traces:
            logger.warning(f"Trace {trace_id} not found, skipping event {event_type.value}")
            return ""
        
        # Check if event should be recorded based on trace level
        if not self._should_record_event(event_type):
            return ""
        
        event_id = f"event_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        
        # Determine parent event from context stack
        parent_event_id = None
        if task_id in self._context_stack and self._context_stack[task_id]:
            parent_event_id = self._context_stack[task_id][-1]
        
        event = TraceEvent(
            event_id=event_id,
            trace_id=trace_id,
            task_id=task_id,
            event_type=event_type,
            timestamp=datetime.now(),
            worker_id=worker_id,
            parent_event_id=parent_event_id,
            duration_ms=duration_ms,
            details=details or {},
            metadata=metadata or {},
            tags=tags or set()
        )
        
        self.active_traces[trace_id].add_event(event)
        
        # Update statistics
        self.trace_statistics[f"events_{event_type.value}"] += 1
        
        return event_id
    
    def _should_record_event(self, event_type: TraceEventType) -> bool:
        """Check if event should be recorded based on trace level"""
        if self.trace_level == TraceLevel.DEBUG:
            return True
        elif self.trace_level == TraceLevel.DETAILED:
            return event_type != TraceEventType.CUSTOM_EVENT
        elif self.trace_level == TraceLevel.STANDARD:
            detailed_events = {
                TraceEventType.TOOL_CALLED,
                TraceEventType.TOOL_COMPLETED,
                TraceEventType.CUSTOM_EVENT
            }
            return event_type not in detailed_events
        else:  # MINIMAL
            minimal_events = {
                TraceEventType.TASK_STARTED,
                TraceEventType.TASK_COMPLETED,
                TraceEventType.TASK_FAILED,
                TraceEventType.ERROR_OCCURRED
            }
            return event_type in minimal_events
    
    def push_context(self, task_id: str, event_id: str):
        """Push event onto context stack for hierarchical tracking"""
        with self._lock:
            self._context_stack[task_id].append(event_id)
    
    def pop_context(self, task_id: str) -> Optional[str]:
        """Pop event from context stack"""
        with self._lock:
            if task_id in self._context_stack and self._context_stack[task_id]:
                return self._context_stack[task_id].pop()
            return None
    
    def get_trace(self, trace_id: str) -> Optional[ExecutionTrace]:
        """Get a trace by ID"""
        with self._lock:
            # Check active traces first
            if trace_id in self.active_traces:
                return self.active_traces[trace_id]
            
            # Check completed traces
            for trace in self.completed_traces:
                if trace.trace_id == trace_id:
                    return trace
            
            return None
    
    def get_traces_for_task(self, task_id: str) -> List[ExecutionTrace]:
        """Get all traces for a specific task"""
        with self._lock:
            traces = []
            
            # Check active traces
            for trace in self.active_traces.values():
                if trace.task_id == task_id:
                    traces.append(trace)
            
            # Check completed traces
            for trace in self.completed_traces:
                if trace.task_id == task_id:
                    traces.append(trace)
            
            return traces
    
    def get_active_traces(self) -> List[ExecutionTrace]:
        """Get all currently active traces"""
        with self._lock:
            return list(self.active_traces.values())
    
    def _calculate_performance_metrics(self, trace: ExecutionTrace) -> Dict[str, Any]:
        """Calculate performance metrics for a trace"""
        metrics = {}
        
        # Overall duration
        metrics["total_duration_ms"] = trace.get_duration_ms()
        
        # Event counts
        event_counts = defaultdict(int)
        for event in trace.events:
            event_counts[event.event_type.value] += 1
        metrics["event_counts"] = dict(event_counts)
        
        # Worker utilization
        worker_durations = defaultdict(float)
        for worker_id, event_ids in trace.worker_assignments.items():
            worker_events = [e for e in trace.events if e.event_id in event_ids and e.duration_ms]
            total_duration = sum(e.duration_ms for e in worker_events)
            worker_durations[worker_id] = total_duration
        metrics["worker_durations_ms"] = dict(worker_durations)
        
        # Error analysis
        error_events = trace.get_events_by_type(TraceEventType.ERROR_OCCURRED)
        metrics["error_count"] = len(error_events)
        if error_events:
            metrics["first_error_time_ms"] = (error_events[0].timestamp - trace.started_at).total_seconds() * 1000
        
        # Tool usage
        tool_events = trace.get_events_by_type(TraceEventType.TOOL_CALLED)
        metrics["tool_calls"] = len(tool_events)
        
        return metrics
    
    def _save_trace(self, trace: ExecutionTrace):
        """Save trace to storage"""
        try:
            trace_file = self.storage_dir / f"trace_{trace.trace_id}.json"
            
            # Convert trace to dictionary
            trace_dict = {
                "trace_id": trace.trace_id,
                "task_id": trace.task_id,
                "task_title": trace.task_title,
                "started_at": trace.started_at.isoformat(),
                "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
                "status": trace.status,
                "events": [event.to_dict() for event in trace.events],
                "worker_assignments": trace.worker_assignments,
                "performance_metrics": trace.performance_metrics,
                "error_summary": trace.error_summary
            }
            
            with open(trace_file, 'w', encoding='utf-8') as f:
                json.dump(trace_dict, f, indent=2)
                
            logger.debug(f"Saved trace {trace.trace_id} to {trace_file}")
            
        except Exception as e:
            logger.error(f"Error saving trace {trace.trace_id}: {e}")
    
    def get_trace_analytics(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Get analytics for traces within a time window"""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
            
            # Collect traces within time window
            relevant_traces = []
            for trace in self.completed_traces:
                if trace.started_at >= cutoff_time:
                    relevant_traces.append(trace)
            
            if not relevant_traces:
                return {"message": "No traces found in time window"}
            
            # Calculate analytics
            total_traces = len(relevant_traces)
            successful_traces = sum(1 for t in relevant_traces if t.status == "completed")
            failed_traces = sum(1 for t in relevant_traces if t.status == "failed")
            
            # Duration statistics
            durations = [t.get_duration_ms() for t in relevant_traces]
            avg_duration = sum(durations) / len(durations)
            
            # Event statistics
            total_events = sum(len(t.events) for t in relevant_traces)
            avg_events_per_trace = total_events / total_traces
            
            # Worker utilization
            worker_usage = defaultdict(int)
            for trace in relevant_traces:
                for worker_id in trace.worker_assignments:
                    worker_usage[worker_id] += 1
            
            return {
                "time_window_hours": time_window_hours,
                "total_traces": total_traces,
                "successful_traces": successful_traces,
                "failed_traces": failed_traces,
                "success_rate": successful_traces / total_traces if total_traces > 0 else 0,
                "average_duration_ms": avg_duration,
                "total_events": total_events,
                "average_events_per_trace": avg_events_per_trace,
                "worker_utilization": dict(worker_usage),
                "trace_statistics": dict(self.trace_statistics)
            }
    
    def cleanup_old_traces(self, max_age_days: int = 30):
        """Clean up old trace files"""
        try:
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            deleted_count = 0
            
            for trace_file in self.storage_dir.glob("trace_*.json"):
                try:
                    # Check file modification time
                    file_mtime = datetime.fromtimestamp(trace_file.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        trace_file.unlink()
                        deleted_count += 1
                except Exception as e:
                    logger.error(f"Error processing trace file {trace_file}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old trace files")
            
        except Exception as e:
            logger.error(f"Error during trace cleanup: {e}")


class TraceContext:
    """Context manager for automatic event tracing"""
    
    def __init__(self, tracer: ExecutionTracer, trace_id: str, task_id: str,
                 event_type: TraceEventType, worker_id: str = None,
                 details: Dict[str, Any] = None):
        self.tracer = tracer
        self.trace_id = trace_id
        self.task_id = task_id
        self.event_type = event_type
        self.worker_id = worker_id
        self.details = details or {}
        self.start_time = None
        self.event_id = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.event_id = self.tracer.add_event(
            trace_id=self.trace_id,
            task_id=self.task_id,
            event_type=self.event_type,
            worker_id=self.worker_id,
            details=self.details
        )
        
        # Push context for hierarchical events
        if self.event_id:
            self.tracer.push_context(self.task_id, self.event_id)
        
        return self.event_id
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Pop context
        self.tracer.pop_context(self.task_id)
        
        # Add completion event if there was an exception
        if exc_type is not None:
            duration_ms = (time.time() - self.start_time) * 1000
            self.tracer.add_event(
                trace_id=self.trace_id,
                task_id=self.task_id,
                event_type=TraceEventType.ERROR_OCCURRED,
                worker_id=self.worker_id,
                details={
                    "error_type": exc_type.__name__,
                    "error_message": str(exc_val),
                    "parent_event_id": self.event_id
                },
                duration_ms=duration_ms
            )


# Global execution tracer instance
execution_tracer = ExecutionTracer()