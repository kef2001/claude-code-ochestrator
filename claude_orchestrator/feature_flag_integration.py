"""
Feature Flag Integration Example
Shows how to integrate feature flags with the Claude Orchestrator system
"""

import logging
from typing import Dict, Any, Optional
from .feature_flags import get_flag_manager, is_enabled, get_value, get_number, get_string, get_json

logger = logging.getLogger(__name__)


class FeatureFlaggedOrchestrator:
    """Example orchestrator with feature flag integration"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize with feature flag support"""
        self.flag_manager = get_flag_manager(config_path)
        logger.info("Initialized orchestrator with feature flag support")
    
    def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task with feature flag controls"""
        
        # Check if parallel processing is enabled
        if is_enabled("enable_parallel_processing", default=True):
            logger.info("Parallel processing enabled")
            return self._process_parallel(task_data)
        else:
            logger.info("Parallel processing disabled, using sequential processing")
            return self._process_sequential(task_data)
    
    def _process_parallel(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process task with parallel workers"""
        
        # Get max worker threads from feature flag
        max_workers = get_number("max_worker_threads", default=2)
        timeout = get_number("task_timeout_seconds", default=300)
        
        logger.info(f"Processing task with {max_workers} workers, timeout: {timeout}s")
        
        # Simulate task processing
        return {
            "status": "completed",
            "method": "parallel",
            "workers": max_workers,
            "timeout": timeout,
            "task_id": task_data.get("id", "unknown")
        }
    
    def _process_sequential(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process task sequentially"""
        
        timeout = get_number("task_timeout_seconds", default=300)
        logger.info(f"Processing task sequentially, timeout: {timeout}s")
        
        return {
            "status": "completed",
            "method": "sequential",
            "timeout": timeout,
            "task_id": task_data.get("id", "unknown")
        }
    
    def get_claude_model(self) -> str:
        """Get preferred Claude model from feature flags"""
        return get_string("preferred_claude_model", default="claude-3-haiku-20240307")
    
    def get_circuit_breaker_config(self) -> Dict[str, Any]:
        """Get circuit breaker configuration"""
        default_config = {
            "failure_threshold": 3,
            "recovery_timeout": 30,
            "half_open_max_calls": 2
        }
        return get_json("circuit_breaker_config", default=default_config)
    
    def should_enable_debug(self) -> bool:
        """Check if debug mode should be enabled"""
        return is_enabled("debug_mode", default=False)
    
    def log_feature_flag_status(self):
        """Log current feature flag status"""
        flags = self.flag_manager.list_flags()
        
        logger.info("=== Feature Flag Status ===")
        for name, flag_data in flags.items():
            status = "ON" if flag_data["enabled"] else "OFF"
            logger.info(f"{name}: {status}")
            if flag_data["value"] is not None:
                logger.info(f"  Value: {flag_data['value']}")
        logger.info("=== End Feature Flag Status ===")


def demonstrate_feature_flags():
    """Demonstrate feature flag usage"""
    
    print("=== Feature Flag Demonstration ===")
    
    # Create orchestrator with feature flags
    orchestrator = FeatureFlaggedOrchestrator("example_feature_flags.json")
    
    # Log current flag status
    orchestrator.log_feature_flag_status()
    
    # Example task processing
    task = {"id": "demo_task", "type": "example", "data": "test"}
    result = orchestrator.process_task(task)
    
    print(f"Task processed: {result}")
    
    # Show other flag usage
    print(f"Preferred Claude model: {orchestrator.get_claude_model()}")
    print(f"Debug mode enabled: {orchestrator.should_enable_debug()}")
    print(f"Circuit breaker config: {orchestrator.get_circuit_breaker_config()}")
    
    # Example of runtime flag changes
    print("\n=== Runtime Flag Changes ===")
    
    # Disable parallel processing
    orchestrator.flag_manager.update_flag("enable_parallel_processing", enabled=False)
    print("Disabled parallel processing")
    
    # Process task again
    result = orchestrator.process_task(task)
    print(f"Task processed after flag change: {result}")
    
    # Re-enable parallel processing
    orchestrator.flag_manager.update_flag("enable_parallel_processing", enabled=True)
    print("Re-enabled parallel processing")


if __name__ == "__main__":
    demonstrate_feature_flags()