"""
Circuit Breaker Pattern Implementation for Claude Orchestrator
Prevents cascading failures and provides resilience for worker operations
"""

import time
import logging
from typing import Optional, Callable, Any, Dict, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import threading
from collections import deque

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5          # Number of failures before opening
    recovery_timeout: int = 60          # Seconds to wait before trying again
    success_threshold: int = 3          # Successes needed to close from half-open
    timeout: int = 30                   # Request timeout in seconds
    monitor_window: int = 300           # Time window for failure tracking (seconds)


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeouts: int = 0
    circuit_opened_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: List[Dict[str, Any]] = field(default_factory=list)


class CircuitBreaker:
    """
    Circuit breaker implementation for worker resilience
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.next_attempt = 0
        self.metrics = CircuitBreakerMetrics()
        self.recent_failures = deque(maxlen=100)  # Keep track of recent failures
        self._lock = threading.Lock()
        
        logger.info(f"Circuit breaker '{name}' initialized with config: {self.config}")
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap functions with circuit breaker"""
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        with self._lock:
            self.metrics.total_requests += 1
            
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                if time.time() < self.next_attempt:
                    raise CircuitBreakerOpenException(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Next attempt in {self.next_attempt - time.time():.1f}s"
                    )
                else:
                    # Try to transition to half-open
                    self._transition_to_half_open()
            
            # Execute the function
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Check for timeout
                if execution_time > self.config.timeout:
                    self._record_timeout()
                    raise CircuitBreakerTimeoutException(
                        f"Function execution timed out after {execution_time:.1f}s"
                    )
                
                # Record success
                self._record_success()
                return result
                
            except Exception as e:
                # Record failure
                self._record_failure(e)
                raise
    
    def _record_success(self):
        """Record a successful operation"""
        self.metrics.successful_requests += 1
        self.metrics.last_success_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.debug(f"Circuit breaker '{self.name}': Success {self.success_count}/{self.config.success_threshold}")
            
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        
        # Reset failure count on success
        self.failure_count = 0
    
    def _record_failure(self, exception: Exception):
        """Record a failed operation"""
        self.metrics.failed_requests += 1
        self.metrics.last_failure_time = datetime.now()
        self.failure_count += 1
        self.recent_failures.append({
            'timestamp': datetime.now(),
            'exception': str(exception),
            'type': type(exception).__name__
        })
        
        logger.warning(f"Circuit breaker '{self.name}': Failure {self.failure_count}/{self.config.failure_threshold} - {exception}")
        
        # Check if we should open the circuit
        if self.state == CircuitState.CLOSED and self.failure_count >= self.config.failure_threshold:
            self._transition_to_open()
        elif self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open state should open the circuit
            self._transition_to_open()
    
    def _record_timeout(self):
        """Record a timeout"""
        self.metrics.timeouts += 1
        logger.warning(f"Circuit breaker '{self.name}': Timeout recorded")
    
    def _transition_to_open(self):
        """Transition circuit to OPEN state"""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.next_attempt = time.time() + self.config.recovery_timeout
        self.success_count = 0
        self.metrics.circuit_opened_count += 1
        
        self._record_state_change(old_state, CircuitState.OPEN)
        logger.error(f"Circuit breaker '{self.name}' opened due to {self.failure_count} failures. "
                    f"Next attempt in {self.config.recovery_timeout}s")
    
    def _transition_to_half_open(self):
        """Transition circuit to HALF_OPEN state"""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        
        self._record_state_change(old_state, CircuitState.HALF_OPEN)
        logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN - testing recovery")
    
    def _transition_to_closed(self):
        """Transition circuit to CLOSED state"""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        
        self._record_state_change(old_state, CircuitState.CLOSED)
        logger.info(f"Circuit breaker '{self.name}' closed - service recovered")
    
    def _record_state_change(self, old_state: CircuitState, new_state: CircuitState):
        """Record state change for monitoring"""
        self.metrics.state_changes.append({
            'timestamp': datetime.now(),
            'from_state': old_state.value,
            'to_state': new_state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count
        })
    
    def force_open(self):
        """Manually open the circuit"""
        with self._lock:
            self._transition_to_open()
            logger.warning(f"Circuit breaker '{self.name}' manually opened")
    
    def force_close(self):
        """Manually close the circuit"""
        with self._lock:
            self._transition_to_closed()
            logger.info(f"Circuit breaker '{self.name}' manually closed")
    
    def reset(self):
        """Reset circuit breaker to initial state"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.next_attempt = 0
            self.recent_failures.clear()
            logger.info(f"Circuit breaker '{self.name}' reset")
    
    def get_state(self) -> CircuitState:
        """Get current state"""
        return self.state
    
    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get circuit breaker metrics"""
        return self.metrics
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status summary"""
        with self._lock:
            total_requests = self.metrics.total_requests
            success_rate = (self.metrics.successful_requests / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'total_requests': total_requests,
                'success_rate': success_rate,
                'last_failure_time': self.metrics.last_failure_time,
                'last_success_time': self.metrics.last_success_time,
                'next_attempt': self.next_attempt if self.state == CircuitState.OPEN else None,
                'recent_failures': list(self.recent_failures)[-5:]  # Last 5 failures
            }


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class CircuitBreakerTimeoutException(Exception):
    """Exception raised when operation times out"""
    pass


class CircuitBreakerManager:
    """
    Manages multiple circuit breakers for different workers/services
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
    
    def get_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """Get or create a circuit breaker"""
        with self._lock:
            if name not in self.circuit_breakers:
                self.circuit_breakers[name] = CircuitBreaker(name, config)
            return self.circuit_breakers[name]
    
    def remove_circuit_breaker(self, name: str):
        """Remove a circuit breaker"""
        with self._lock:
            if name in self.circuit_breakers:
                del self.circuit_breakers[name]
                logger.info(f"Circuit breaker '{name}' removed")
    
    def get_all_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all circuit breakers"""
        with self._lock:
            return {name: cb.get_health_status() for name, cb in self.circuit_breakers.items()}
    
    def reset_all(self):
        """Reset all circuit breakers"""
        with self._lock:
            for cb in self.circuit_breakers.values():
                cb.reset()
            logger.info("All circuit breakers reset")
    
    def get_failing_services(self) -> List[str]:
        """Get list of services with open circuit breakers"""
        with self._lock:
            return [name for name, cb in self.circuit_breakers.items() 
                   if cb.get_state() == CircuitState.OPEN]
    
    def get_recovering_services(self) -> List[str]:
        """Get list of services in half-open state"""
        with self._lock:
            return [name for name, cb in self.circuit_breakers.items() 
                   if cb.get_state() == CircuitState.HALF_OPEN]


# Global circuit breaker manager instance
circuit_breaker_manager = CircuitBreakerManager()