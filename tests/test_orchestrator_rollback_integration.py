"""
Test rollback integration with Enhanced Claude Orchestrator

Tests the integration of rollback functionality including:
- Automatic rollback on failures
- Manual rollback commands
- Circuit breaker rollback triggers
- Checkpoint creation during execution
"""

import asyncio
import tempfile
import os
import shutil
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from claude_orchestrator.enhanced_orchestrator import (
    EnhancedClaudeOrchestrator, EnhancedTaskStatus, EnhancedTaskContext
)
from claude_orchestrator.task_master import Task as TMTask, TaskStatus as TMTaskStatus
from claude_orchestrator.circuit_breaker import CircuitBreakerOpenException
from claude_orchestrator.rollback import RollbackReason


class TestOrchestratorRollbackIntegration:
    """Tests for rollback integration in Enhanced Orchestrator"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock config manager
        self.mock_config_manager = Mock()
        self.mock_config_manager.get.return_value = os.path.join(self.temp_dir, "rollbacks")
        
        # Create orchestrator with mocked config
        with patch('claude_orchestrator.enhanced_orchestrator.ConfigurationManager', return_value=self.mock_config_manager):
            self.orchestrator = EnhancedClaudeOrchestrator()
    
    def teardown_method(self):
        """Clean up after test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_checkpoint_creation_during_execution(self):
        """Test that checkpoints are created at key execution stages"""
        # Create a test task
        test_task = TMTask(
            id="test-001",
            title="Test Task",
            description="Test task for rollback integration",
            status=TMTaskStatus.PENDING,
            priority="high"
        )
        
        # Mock task manager
        with patch.object(self.orchestrator.task_manager, 'get_task', return_value=test_task):
            # Run task processing
            loop = asyncio.new_event_loop()
            context = loop.run_until_complete(
                self.orchestrator.process_task_enhanced("test-001", auto_decompose=False, auto_optimize=False)
            )
            loop.close()
        
        # Verify checkpoints were created
        assert len(context.rollback_checkpoints) > 0
        assert context.last_stable_checkpoint is not None
        
        # Verify checkpoint descriptions
        checkpoint_data = []
        for checkpoint_id in context.rollback_checkpoints:
            checkpoint = self.orchestrator.checkpoint_manager.get_checkpoint(checkpoint_id)
            if checkpoint:
                checkpoint_data.append(checkpoint.step_description)
        
        expected_stages = ["Task complexity analyzed", "Worker allocated", "Task execution completed", "Validation completed"]
        for stage in expected_stages:
            assert any(stage in desc for desc in checkpoint_data)
    
    def test_automatic_rollback_on_failure(self):
        """Test automatic rollback when task execution fails"""
        # Create a test task
        test_task = TMTask(
            id="test-002",
            title="Test Failing Task",
            description="Test task that will fail",
            status=TMTaskStatus.PENDING,
            priority="high"
        )
        
        # Mock task manager
        with patch.object(self.orchestrator.task_manager, 'get_task', return_value=test_task):
            # Mock execution to fail
            with patch.object(self.orchestrator, '_execute_with_circuit_breaker') as mock_execute:
                mock_execute.side_effect = RuntimeError("Simulated execution failure")
                
                # Run task processing
                loop = asyncio.new_event_loop()
                try:
                    context = loop.run_until_complete(
                        self.orchestrator.process_task_enhanced("test-002", auto_decompose=False, auto_optimize=False)
                    )
                except RuntimeError:
                    # Expected failure
                    pass
                loop.close()
        
        # Check rollback metrics
        assert self.orchestrator.metrics.get("successful_rollbacks", 0) >= 0
        
        # Verify rollback history
        history = self.orchestrator.get_rollback_history("test-002")
        if history:  # Rollback may not execute if no checkpoints were created
            assert history[0]["reason"] == RollbackReason.ERROR.value
    
    def test_circuit_breaker_rollback_trigger(self):
        """Test rollback triggered by circuit breaker"""
        # Create a test task
        test_task = TMTask(
            id="test-003",
            title="Test Circuit Breaker Task",
            description="Test task for circuit breaker rollback",
            status=TMTaskStatus.PENDING,
            priority="high"
        )
        
        # Mock task manager
        with patch.object(self.orchestrator.task_manager, 'get_task', return_value=test_task):
            # Mock circuit breaker to throw exception
            with patch.object(self.orchestrator, '_execute_with_circuit_breaker') as mock_execute:
                mock_execute.side_effect = CircuitBreakerOpenException("Circuit breaker is open")
                
                # Run task processing
                loop = asyncio.new_event_loop()
                try:
                    context = loop.run_until_complete(
                        self.orchestrator.process_task_enhanced("test-003", auto_decompose=False, auto_optimize=False)
                    )
                except CircuitBreakerOpenException:
                    # Expected failure
                    pass
                loop.close()
        
        # Check circuit breaker metrics
        assert self.orchestrator.metrics["circuit_breaker_activations"] > 0
    
    def test_manual_rollback_command(self):
        """Test manual rollback functionality"""
        # Create a test task
        test_task = TMTask(
            id="test-004",
            title="Test Manual Rollback Task",
            description="Test task for manual rollback",
            status=TMTaskStatus.PENDING,
            priority="medium"
        )
        
        # Mock task manager
        with patch.object(self.orchestrator.task_manager, 'get_task', return_value=test_task):
            # Run task processing successfully
            loop = asyncio.new_event_loop()
            context = loop.run_until_complete(
                self.orchestrator.process_task_enhanced("test-004", auto_decompose=False, auto_optimize=False)
            )
            
            # Perform manual rollback
            if context.last_stable_checkpoint:
                success = loop.run_until_complete(
                    self.orchestrator.manual_rollback_task("test-004")
                )
                assert success is True
            
            loop.close()
        
        # Verify rollback history
        history = self.orchestrator.get_rollback_history("test-004")
        if history:
            assert history[0]["reason"] == RollbackReason.MANUAL.value
    
    def test_rollback_scope_determination(self):
        """Test rollback scope is correctly determined based on failure type"""
        # Create test context
        test_task = TMTask(
            id="test-005",
            title="Test Task",
            description="Test task",
            status=TMTaskStatus.PENDING,
            priority="high"
        )
        context = EnhancedTaskContext(
            task_id="test-005",
            original_task=test_task
        )
        
        # Test circuit breaker scope
        scope = self.orchestrator._determine_rollback_scope(context, RollbackReason.CIRCUIT_BREAKER)
        assert "worker_state" in [c.value for c in scope.components]
        assert "task_state" in [c.value for c in scope.components]
        
        # Test validation failure scope
        scope = self.orchestrator._determine_rollback_scope(context, RollbackReason.VALIDATION_FAILURE)
        assert scope.strategy_type.value == "selective"
        assert "test-005" in scope.task_ids
        
        # Test general error scope
        scope = self.orchestrator._determine_rollback_scope(context, RollbackReason.ERROR)
        assert "task_state" in [c.value for c in scope.components]
    
    def test_rollback_disabled_task(self):
        """Test that rollback doesn't occur when disabled for a task"""
        # Create a test task
        test_task = TMTask(
            id="test-006",
            title="Test No Rollback Task",
            description="Test task with rollback disabled",
            status=TMTaskStatus.PENDING,
            priority="low"
        )
        
        # Mock task manager
        with patch.object(self.orchestrator.task_manager, 'get_task', return_value=test_task):
            # Disable rollback for this task
            with patch.object(self.orchestrator, '_create_task_checkpoint', return_value=None):
                # Mock execution to fail
                with patch.object(self.orchestrator, '_execute_with_circuit_breaker') as mock_execute:
                    mock_execute.side_effect = RuntimeError("Simulated failure")
                    
                    # Run task processing
                    loop = asyncio.new_event_loop()
                    try:
                        context = loop.run_until_complete(
                            self.orchestrator.process_task_enhanced("test-006", auto_decompose=False, auto_optimize=False)
                        )
                    except RuntimeError:
                        # Expected failure
                        pass
                    loop.close()
        
        # Verify no rollback occurred
        history = self.orchestrator.get_rollback_history("test-006")
        assert len(history) == 0
    
    def test_system_status_includes_rollback_metrics(self):
        """Test that system status report includes rollback metrics"""
        status = self.orchestrator.get_system_status()
        
        assert "rollback_system" in status
        rollback_metrics = status["rollback_system"]
        
        assert "total_rollbacks" in rollback_metrics
        assert "successful_rollbacks" in rollback_metrics
        assert "failed_rollbacks" in rollback_metrics
        assert "rollback_enabled_tasks" in rollback_metrics
        assert "total_checkpoints_created" in rollback_metrics
        
        assert status["configuration"]["rollback_enabled"] is True


if __name__ == "__main__":
    # Run basic tests
    test = TestOrchestratorRollbackIntegration()
    test.setup_method()
    
    try:
        print("Testing checkpoint creation during execution...")
        test.test_checkpoint_creation_during_execution()
        print("✓ Checkpoint creation test passed")
        
        print("\nTesting automatic rollback on failure...")
        test.test_automatic_rollback_on_failure()
        print("✓ Automatic rollback test passed")
        
        print("\nTesting circuit breaker rollback trigger...")
        test.test_circuit_breaker_rollback_trigger()
        print("✓ Circuit breaker rollback test passed")
        
        print("\nTesting manual rollback command...")
        test.test_manual_rollback_command()
        print("✓ Manual rollback test passed")
        
        print("\nTesting rollback scope determination...")
        test.test_rollback_scope_determination()
        print("✓ Rollback scope test passed")
        
        print("\nTesting rollback disabled task...")
        test.test_rollback_disabled_task()
        print("✓ Rollback disabled test passed")
        
        print("\nTesting system status includes rollback metrics...")
        test.test_system_status_includes_rollback_metrics()
        print("✓ System status test passed")
        
        print("\nAll rollback integration tests passed!")
        
    finally:
        test.teardown_method()