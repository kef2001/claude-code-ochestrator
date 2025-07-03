"""
Inter-Worker Communication Protocol
Defines message format, protocol semantics, and communication rules for Claude Orchestrator
"""

import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Message types for inter-worker communication"""
    # Task Management
    TASK_ASSIGNMENT = "task_assignment"
    TASK_COMPLETION = "task_completion"
    TASK_PROGRESS = "task_progress"
    TASK_CANCELLATION = "task_cancellation"
    TASK_DELEGATION = "task_delegation"
    
    # Worker Management
    WORKER_REGISTRATION = "worker_registration"
    WORKER_HEARTBEAT = "worker_heartbeat"
    WORKER_STATUS_UPDATE = "worker_status_update"
    WORKER_SHUTDOWN = "worker_shutdown"
    
    # Coordination
    COORDINATION_REQUEST = "coordination_request"
    COORDINATION_RESPONSE = "coordination_response"
    RESOURCE_SHARING = "resource_sharing"
    DEPENDENCY_NOTIFICATION = "dependency_notification"
    
    # Error Handling
    ERROR_REPORT = "error_report"
    RETRY_REQUEST = "retry_request"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    
    # System
    SYSTEM_STATUS = "system_status"
    PING = "ping"
    PONG = "pong"
    BROADCAST = "broadcast"
    
    # Acknowledgment
    ACK = "acknowledgment"
    NACK = "negative_acknowledgment"


class Priority(Enum):
    """Message priority levels"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class DeliveryMode(Enum):
    """Message delivery modes"""
    IMMEDIATE = "immediate"       # Must be delivered immediately
    BEST_EFFORT = "best_effort"   # Deliver if possible, don't retry
    RELIABLE = "reliable"         # Retry until delivered or timeout
    BROADCAST = "broadcast"       # Send to all workers


@dataclass
class MessageHeader:
    """Message header containing metadata"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.PING
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sender_id: str = ""
    recipient_id: str = ""
    correlation_id: Optional[str] = None
    priority: Priority = Priority.NORMAL
    delivery_mode: DeliveryMode = DeliveryMode.BEST_EFFORT
    ttl: Optional[int] = None  # Time to live in seconds
    reply_to: Optional[str] = None
    content_type: str = "application/json"
    content_encoding: str = "utf-8"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert header to dictionary"""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "timestamp": self.timestamp,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "correlation_id": self.correlation_id,
            "priority": self.priority.value,
            "delivery_mode": self.delivery_mode.value,
            "ttl": self.ttl,
            "reply_to": self.reply_to,
            "content_type": self.content_type,
            "content_encoding": self.content_encoding
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageHeader':
        """Create header from dictionary"""
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            message_type=MessageType(data.get("message_type", MessageType.PING.value)),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            sender_id=data.get("sender_id", ""),
            recipient_id=data.get("recipient_id", ""),
            correlation_id=data.get("correlation_id"),
            priority=Priority(data.get("priority", Priority.NORMAL.value)),
            delivery_mode=DeliveryMode(data.get("delivery_mode", DeliveryMode.BEST_EFFORT.value)),
            ttl=data.get("ttl"),
            reply_to=data.get("reply_to"),
            content_type=data.get("content_type", "application/json"),
            content_encoding=data.get("content_encoding", "utf-8")
        )


@dataclass
class Message:
    """Complete message structure"""
    header: MessageHeader
    payload: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            "header": self.header.to_dict(),
            "payload": self.payload
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary"""
        return cls(
            header=MessageHeader.from_dict(data.get("header", {})),
            payload=data.get("payload", {})
        )
    
    def to_json(self) -> str:
        """Convert message to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Create message from JSON string"""
        return cls.from_dict(json.loads(json_str))


# Predefined message payloads for common operations

@dataclass
class TaskAssignmentPayload:
    """Payload for task assignment messages"""
    task_id: str
    task_title: str
    task_description: str
    task_requirements: Dict[str, Any] = field(default_factory=dict)
    deadline: Optional[str] = None
    priority: str = "medium"
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskCompletionPayload:
    """Payload for task completion messages"""
    task_id: str
    success: bool
    result: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[float] = None
    error_message: Optional[str] = None
    files_changed: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskProgressPayload:
    """Payload for task progress messages"""
    task_id: str
    progress_percentage: float
    status: str
    current_step: Optional[str] = None
    estimated_completion: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkerRegistrationPayload:
    """Payload for worker registration messages"""
    worker_id: str
    worker_type: str
    model_name: str
    capabilities: List[str]
    max_concurrent_tasks: int
    version: str
    status: str = "idle"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkerHeartbeatPayload:
    """Payload for worker heartbeat messages"""
    worker_id: str
    status: str
    current_tasks: List[str]
    cpu_usage: float
    memory_usage: float
    uptime: float
    last_activity: str
    health_status: str = "healthy"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CoordinationRequestPayload:
    """Payload for coordination request messages"""
    request_type: str
    resource_type: str
    resource_id: str
    requester_id: str
    request_data: Dict[str, Any] = field(default_factory=dict)
    timeout: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ErrorReportPayload:
    """Payload for error report messages"""
    error_type: str
    error_message: str
    error_code: Optional[str] = None
    task_id: Optional[str] = None
    worker_id: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MessageRouter(ABC):
    """Abstract base class for message routing"""
    
    @abstractmethod
    async def send_message(self, message: Message) -> bool:
        """Send a message"""
        pass
    
    @abstractmethod
    async def receive_message(self) -> Optional[Message]:
        """Receive a message"""
        pass
    
    @abstractmethod
    async def register_handler(self, message_type: MessageType, handler: Callable[[Message], Any]):
        """Register a message handler"""
        pass


class InMemoryMessageRouter(MessageRouter):
    """In-memory message router for testing and local development"""
    
    def __init__(self):
        self.message_queues: Dict[str, asyncio.Queue] = {}
        self.handlers: Dict[MessageType, List[Callable]] = {}
        self.broadcast_subscribers: List[str] = []
        self._lock = asyncio.Lock()
    
    async def send_message(self, message: Message) -> bool:
        """Send a message to the appropriate queue"""
        async with self._lock:
            try:
                if message.header.delivery_mode == DeliveryMode.BROADCAST:
                    # Send to all subscribers
                    for subscriber_id in self.broadcast_subscribers:
                        if subscriber_id not in self.message_queues:
                            self.message_queues[subscriber_id] = asyncio.Queue()
                        await self.message_queues[subscriber_id].put(message)
                    return True
                else:
                    # Send to specific recipient
                    recipient_id = message.header.recipient_id
                    if recipient_id not in self.message_queues:
                        self.message_queues[recipient_id] = asyncio.Queue()
                    
                    await self.message_queues[recipient_id].put(message)
                    return True
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                return False
    
    async def receive_message(self, worker_id: str) -> Optional[Message]:
        """Receive a message from the worker's queue"""
        if worker_id not in self.message_queues:
            self.message_queues[worker_id] = asyncio.Queue()
        
        try:
            # Non-blocking receive with timeout
            message = await asyncio.wait_for(
                self.message_queues[worker_id].get(),
                timeout=1.0
            )
            return message
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Failed to receive message: {e}")
            return None
    
    async def register_handler(self, message_type: MessageType, handler: Callable[[Message], Any]):
        """Register a message handler"""
        if message_type not in self.handlers:
            self.handlers[message_type] = []
        self.handlers[message_type].append(handler)
    
    async def subscribe_to_broadcasts(self, worker_id: str):
        """Subscribe a worker to broadcast messages"""
        if worker_id not in self.broadcast_subscribers:
            self.broadcast_subscribers.append(worker_id)
    
    async def unsubscribe_from_broadcasts(self, worker_id: str):
        """Unsubscribe a worker from broadcast messages"""
        if worker_id in self.broadcast_subscribers:
            self.broadcast_subscribers.remove(worker_id)


class CommunicationProtocol:
    """Main communication protocol implementation"""
    
    def __init__(self, worker_id: str, router: MessageRouter):
        self.worker_id = worker_id
        self.router = router
        self.message_handlers: Dict[MessageType, List[Callable]] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self._running = False
        self._message_loop_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the communication protocol"""
        self._running = True
        self._message_loop_task = asyncio.create_task(self._message_loop())
        logger.info(f"Communication protocol started for worker {self.worker_id}")
    
    async def stop(self):
        """Stop the communication protocol"""
        self._running = False
        if self._message_loop_task:
            self._message_loop_task.cancel()
            try:
                await self._message_loop_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Communication protocol stopped for worker {self.worker_id}")
    
    async def _message_loop(self):
        """Main message processing loop"""
        while self._running:
            try:
                message = await self.router.receive_message(self.worker_id)
                if message:
                    await self._process_message(message)
            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_message(self, message: Message):
        """Process an incoming message"""
        try:
            # Handle correlation for request-response pattern
            if message.header.correlation_id and message.header.correlation_id in self.pending_requests:
                future = self.pending_requests[message.header.correlation_id]
                future.set_result(message)
                del self.pending_requests[message.header.correlation_id]
                return
            
            # Handle message with registered handlers
            if message.header.message_type in self.message_handlers:
                handlers = self.message_handlers[message.header.message_type]
                for handler in handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")
            else:
                logger.warning(f"No handler registered for message type: {message.header.message_type}")
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def register_handler(self, message_type: MessageType, handler: Callable[[Message], Any]):
        """Register a message handler"""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)
    
    async def send_message(self, message_type: MessageType, recipient_id: str, 
                          payload: Dict[str, Any], priority: Priority = Priority.NORMAL,
                          delivery_mode: DeliveryMode = DeliveryMode.BEST_EFFORT,
                          reply_to: Optional[str] = None) -> bool:
        """Send a message"""
        header = MessageHeader(
            message_type=message_type,
            sender_id=self.worker_id,
            recipient_id=recipient_id,
            priority=priority,
            delivery_mode=delivery_mode,
            reply_to=reply_to
        )
        
        message = Message(header=header, payload=payload)
        return await self.router.send_message(message)
    
    async def send_request(self, message_type: MessageType, recipient_id: str,
                          payload: Dict[str, Any], timeout: float = 30.0) -> Optional[Message]:
        """Send a request and wait for response"""
        correlation_id = str(uuid.uuid4())
        
        header = MessageHeader(
            message_type=message_type,
            sender_id=self.worker_id,
            recipient_id=recipient_id,
            correlation_id=correlation_id,
            priority=Priority.HIGH,
            delivery_mode=DeliveryMode.RELIABLE,
            reply_to=self.worker_id
        )
        
        message = Message(header=header, payload=payload)
        
        # Set up future for response
        future = asyncio.Future()
        self.pending_requests[correlation_id] = future
        
        try:
            # Send request
            success = await self.router.send_message(message)
            if not success:
                del self.pending_requests[correlation_id]
                return None
            
            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        
        except asyncio.TimeoutError:
            if correlation_id in self.pending_requests:
                del self.pending_requests[correlation_id]
            logger.warning(f"Request timeout for correlation_id: {correlation_id}")
            return None
        
        except Exception as e:
            if correlation_id in self.pending_requests:
                del self.pending_requests[correlation_id]
            logger.error(f"Error sending request: {e}")
            return None
    
    async def send_response(self, request_message: Message, response_payload: Dict[str, Any]):
        """Send a response to a request"""
        if not request_message.header.reply_to or not request_message.header.correlation_id:
            logger.error("Cannot send response: missing reply_to or correlation_id")
            return False
        
        header = MessageHeader(
            message_type=MessageType.ACK,
            sender_id=self.worker_id,
            recipient_id=request_message.header.reply_to,
            correlation_id=request_message.header.correlation_id,
            priority=Priority.HIGH,
            delivery_mode=DeliveryMode.RELIABLE
        )
        
        response = Message(header=header, payload=response_payload)
        return await self.router.send_message(response)
    
    # Convenience methods for common operations
    
    async def send_task_completion(self, orchestrator_id: str, task_id: str, 
                                  success: bool, result: Dict[str, Any],
                                  duration: Optional[float] = None,
                                  error_message: Optional[str] = None):
        """Send task completion notification"""
        payload = TaskCompletionPayload(
            task_id=task_id,
            success=success,
            result=result,
            duration=duration,
            error_message=error_message
        ).to_dict()
        
        return await self.send_message(
            MessageType.TASK_COMPLETION,
            orchestrator_id,
            payload,
            priority=Priority.HIGH
        )
    
    async def send_task_progress(self, orchestrator_id: str, task_id: str,
                               progress_percentage: float, status: str,
                               current_step: Optional[str] = None):
        """Send task progress update"""
        payload = TaskProgressPayload(
            task_id=task_id,
            progress_percentage=progress_percentage,
            status=status,
            current_step=current_step
        ).to_dict()
        
        return await self.send_message(
            MessageType.TASK_PROGRESS,
            orchestrator_id,
            payload
        )
    
    async def send_heartbeat(self, orchestrator_id: str, status: str,
                           current_tasks: List[str], cpu_usage: float,
                           memory_usage: float, uptime: float):
        """Send heartbeat to orchestrator"""
        payload = WorkerHeartbeatPayload(
            worker_id=self.worker_id,
            status=status,
            current_tasks=current_tasks,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            uptime=uptime,
            last_activity=datetime.now(timezone.utc).isoformat()
        ).to_dict()
        
        return await self.send_message(
            MessageType.WORKER_HEARTBEAT,
            orchestrator_id,
            payload
        )
    
    async def send_error_report(self, orchestrator_id: str, error_type: str,
                              error_message: str, task_id: Optional[str] = None,
                              error_code: Optional[str] = None):
        """Send error report"""
        payload = ErrorReportPayload(
            error_type=error_type,
            error_message=error_message,
            error_code=error_code,
            task_id=task_id,
            worker_id=self.worker_id
        ).to_dict()
        
        return await self.send_message(
            MessageType.ERROR_REPORT,
            orchestrator_id,
            payload,
            priority=Priority.HIGH
        )
    
    async def request_coordination(self, coordinator_id: str, request_type: str,
                                 resource_type: str, resource_id: str,
                                 request_data: Dict[str, Any] = None,
                                 timeout: float = 30.0) -> Optional[Message]:
        """Request coordination with another worker"""
        payload = CoordinationRequestPayload(
            request_type=request_type,
            resource_type=resource_type,
            resource_id=resource_id,
            requester_id=self.worker_id,
            request_data=request_data or {}
        ).to_dict()
        
        return await self.send_request(
            MessageType.COORDINATION_REQUEST,
            coordinator_id,
            payload,
            timeout=timeout
        )


# Global message router instance
global_message_router = InMemoryMessageRouter()