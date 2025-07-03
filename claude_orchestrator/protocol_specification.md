# Inter-Worker Communication Protocol Specification

## Overview

The Claude Orchestrator Inter-Worker Communication Protocol defines a comprehensive messaging system for coordination between workers, orchestrators, and system components. This protocol ensures reliable, secure, and efficient communication across the distributed system.

## Protocol Architecture

### Components

1. **Message Router**: Routes messages between components
2. **Communication Protocol**: Manages message sending/receiving for each worker
3. **Message Handlers**: Process incoming messages
4. **Request-Response Pattern**: Supports synchronous communication

### Message Flow

```
Worker A → Message Router → Worker B
       ↘              ↙
        Orchestrator
```

## Message Structure

### Message Format

All messages follow a standardized format:

```json
{
  "header": {
    "message_id": "uuid",
    "message_type": "task_assignment",
    "timestamp": "2024-01-01T00:00:00Z",
    "sender_id": "worker_1",
    "recipient_id": "worker_2",
    "correlation_id": "uuid", 
    "priority": 2,
    "delivery_mode": "reliable",
    "ttl": 300,
    "reply_to": "worker_1",
    "content_type": "application/json",
    "content_encoding": "utf-8"
  },
  "payload": {
    // Message-specific data
  }
}
```

### Message Types

#### Task Management
- `TASK_ASSIGNMENT`: Assign a task to a worker
- `TASK_COMPLETION`: Report task completion
- `TASK_PROGRESS`: Update task progress
- `TASK_CANCELLATION`: Cancel a task
- `TASK_DELEGATION`: Delegate task to another worker

#### Worker Management
- `WORKER_REGISTRATION`: Register a new worker
- `WORKER_HEARTBEAT`: Worker status update
- `WORKER_STATUS_UPDATE`: Status change notification
- `WORKER_SHUTDOWN`: Worker shutdown notification

#### Coordination
- `COORDINATION_REQUEST`: Request coordination with another worker
- `COORDINATION_RESPONSE`: Response to coordination request
- `RESOURCE_SHARING`: Share resources between workers
- `DEPENDENCY_NOTIFICATION`: Notify about task dependencies

#### Error Handling
- `ERROR_REPORT`: Report errors
- `RETRY_REQUEST`: Request task retry
- `CIRCUIT_BREAKER_OPEN`: Circuit breaker activated
- `CIRCUIT_BREAKER_CLOSED`: Circuit breaker deactivated

#### System
- `SYSTEM_STATUS`: System status inquiry
- `PING`: Health check
- `PONG`: Health check response
- `BROADCAST`: Broadcast message to all workers

#### Acknowledgment
- `ACK`: Positive acknowledgment
- `NACK`: Negative acknowledgment

## Protocol Semantics

### Message Delivery Modes

#### 1. Immediate (`immediate`)
- Messages must be delivered immediately
- No queuing or buffering
- Fails if recipient unavailable
- Use for time-critical operations

#### 2. Best Effort (`best_effort`)
- Attempt delivery once
- No retries on failure
- Use for non-critical updates

#### 3. Reliable (`reliable`)
- Guaranteed delivery
- Automatic retries with exponential backoff
- Timeout handling
- Use for critical operations

#### 4. Broadcast (`broadcast`)
- Send to all registered workers
- Best effort delivery to each recipient
- Use for system-wide notifications

### Priority Levels

1. **CRITICAL (1)**: System-critical messages (errors, shutdowns)
2. **HIGH (2)**: Important operations (task assignments, completions)
3. **NORMAL (3)**: Regular operations (progress updates, heartbeats)
4. **LOW (4)**: Background operations (statistics, cleanup)

### Message Ordering

- Messages with higher priority are processed first
- Messages with same priority are processed FIFO
- Critical messages bypass normal queuing

### Timeout Handling

- Default timeout: 30 seconds for requests
- Configurable per message type
- Automatic cleanup of expired messages
- TTL (Time To Live) respected

## Communication Patterns

### 1. Request-Response Pattern

Used for synchronous communication requiring a response:

```python
# Send request
response = await protocol.send_request(
    MessageType.COORDINATION_REQUEST,
    "worker_2",
    request_payload,
    timeout=30.0
)

# Handle response
if response:
    # Process response
    pass
else:
    # Handle timeout
    pass
```

### 2. Fire-and-Forget Pattern

Used for asynchronous notifications:

```python
# Send notification
await protocol.send_message(
    MessageType.TASK_PROGRESS,
    "orchestrator",
    progress_payload
)
```

### 3. Publish-Subscribe Pattern

Used for system-wide notifications:

```python
# Broadcast message
await protocol.send_message(
    MessageType.BROADCAST,
    "all",
    broadcast_payload,
    delivery_mode=DeliveryMode.BROADCAST
)
```

## Error Handling

### Error Types

1. **Network Errors**: Connection failures, timeouts
2. **Protocol Errors**: Invalid message format, unsupported operations
3. **Application Errors**: Task failures, resource unavailability
4. **System Errors**: Out of memory, disk full

### Error Recovery

1. **Retry Strategy**: Exponential backoff for transient errors
2. **Circuit Breaker**: Prevent cascading failures
3. **Fallback**: Alternative processing paths
4. **Dead Letter Queue**: Store undeliverable messages

### Error Reporting

All errors must be reported using the `ERROR_REPORT` message type:

```json
{
  "error_type": "network_error",
  "error_message": "Connection timeout",
  "error_code": "TIMEOUT_001",
  "task_id": "task_123",
  "worker_id": "worker_1",
  "stack_trace": "...",
  "context": {
    "retry_count": 3,
    "last_attempt": "2024-01-01T00:00:00Z"
  }
}
```

## Security Considerations

### Message Integrity

- All messages include checksums for integrity verification
- Tampered messages are rejected
- Message authentication codes (MAC) for critical messages

### Access Control

- Workers must be registered before sending messages
- Message type permissions enforced
- Sender authentication required

### Data Privacy

- Sensitive data encrypted in transit
- Minimal data exposure in logs
- Secure key management

## Performance Considerations

### Message Batching

- Multiple messages can be batched for efficiency
- Batch size limits to prevent memory issues
- Automatic batching for high-frequency messages

### Flow Control

- Backpressure handling to prevent queue overflow
- Rate limiting per worker
- Priority-based throttling

### Resource Management

- Connection pooling for network efficiency
- Memory limits for message queues
- Automatic cleanup of stale connections

## Implementation Guidelines

### Worker Registration

Every worker must register with the orchestrator:

```python
payload = WorkerRegistrationPayload(
    worker_id="worker_1",
    worker_type="sonnet",
    model_name="claude-3-5-sonnet-20241022",
    capabilities=["code", "research"],
    max_concurrent_tasks=3,
    version="1.0.0"
)

await protocol.send_message(
    MessageType.WORKER_REGISTRATION,
    "orchestrator",
    payload.to_dict()
)
```

### Task Assignment Flow

1. Orchestrator sends `TASK_ASSIGNMENT` to worker
2. Worker acknowledges with `ACK`
3. Worker periodically sends `TASK_PROGRESS` updates
4. Worker sends `TASK_COMPLETION` when done
5. Orchestrator acknowledges with `ACK`

### Heartbeat Mechanism

Workers must send heartbeats every 60 seconds:

```python
await protocol.send_heartbeat(
    "orchestrator",
    status="busy",
    current_tasks=["task_1", "task_2"],
    cpu_usage=45.2,
    memory_usage=67.8,
    uptime=3600.0
)
```

### Coordination Between Workers

For worker-to-worker coordination:

```python
# Request resource from another worker
response = await protocol.request_coordination(
    "worker_2",
    "resource_request",
    "file_access",
    "/path/to/file",
    {"operation": "read", "mode": "exclusive"}
)

if response and response.payload.get("granted"):
    # Use resource
    pass
else:
    # Handle denial
    pass
```

## Message Routing Rules

### Routing Logic

1. **Direct Routing**: Messages with specific recipient_id
2. **Broadcast Routing**: Messages to all registered workers
3. **Load Balancing**: Distribute messages across worker pools
4. **Failover**: Redirect messages when primary route fails

### Route Discovery

- Dynamic route discovery based on worker registration
- Route health monitoring
- Automatic route updates

### Quality of Service

- Priority-based routing
- Bandwidth allocation
- Latency optimization

## Monitoring and Observability

### Metrics Collection

- Message throughput (messages/second)
- Message latency (end-to-end)
- Error rates by message type
- Queue depths
- Worker utilization

### Logging

All protocol events are logged with:
- Timestamp
- Message ID
- Sender/Recipient
- Message type
- Processing time
- Error details (if any)

### Tracing

- Distributed tracing for message flows
- Correlation IDs for request tracking
- Performance profiling

## Configuration

### Protocol Configuration

```json
{
  "protocol": {
    "default_timeout": 30,
    "max_retries": 3,
    "heartbeat_interval": 60,
    "message_ttl": 300,
    "max_queue_size": 1000,
    "batch_size": 10,
    "compression": true,
    "encryption": true
  }
}
```

### Worker Configuration

```json
{
  "worker": {
    "worker_id": "worker_1",
    "worker_type": "sonnet",
    "max_concurrent_tasks": 3,
    "capabilities": ["code", "research"],
    "heartbeat_interval": 60
  }
}
```

## Testing and Validation

### Unit Tests

- Message serialization/deserialization
- Protocol handler registration
- Error handling scenarios
- Timeout behavior

### Integration Tests

- End-to-end message flow
- Multi-worker coordination
- Failover scenarios
- Performance benchmarks

### Load Testing

- High message volume handling
- Concurrent worker scenarios
- Resource exhaustion testing
- Stress testing

## Versioning and Compatibility

### Protocol Versioning

- Semantic versioning (MAJOR.MINOR.PATCH)
- Backward compatibility maintenance
- Version negotiation during handshake

### Message Format Evolution

- Optional fields for backward compatibility
- Deprecated field handling
- Migration strategies

## Future Enhancements

### Planned Features

1. **Message Persistence**: Durable message storage
2. **Advanced Routing**: Content-based routing
3. **Federation**: Multi-cluster communication
4. **Streaming**: Real-time message streaming
5. **Analytics**: Advanced message analytics

### Extension Points

- Custom message types
- Pluggable routers
- Custom serialization formats
- External message brokers

## Conclusion

This protocol specification provides a robust foundation for inter-worker communication in the Claude Orchestrator system. It ensures reliable, secure, and efficient message exchange while maintaining flexibility for future enhancements.

The protocol supports both synchronous and asynchronous communication patterns, comprehensive error handling, and extensive monitoring capabilities. Implementation should follow the guidelines provided to ensure system reliability and performance.