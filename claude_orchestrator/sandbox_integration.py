"""Integration of Secure Sandbox with Claude Orchestrator.

This module integrates the sandbox execution environment with the
orchestrator to provide secure code execution for workers.
"""

import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from .sandbox_executor import (
    SecureSandbox, SandboxPolicy, SandboxManager,
    ExecutionResult, ResourceLimits
)
from .feedback_model import create_security_feedback, FeedbackSeverity

logger = logging.getLogger(__name__)


class SandboxIntegration:
    """Integrates sandbox execution with the orchestrator."""
    
    def __init__(self, orchestrator, default_policy: SandboxPolicy = SandboxPolicy.MODERATE):
        self.orchestrator = orchestrator
        self.default_policy = default_policy
        self.sandbox_manager = SandboxManager(default_policy)
        
        # Policy mapping for different task types
        self.task_policies = {
            "test": SandboxPolicy.MODERATE,      # Tests need some filesystem access
            "build": SandboxPolicy.MODERATE,     # Builds need network for dependencies
            "deploy": SandboxPolicy.STRICT,      # Deploys should be very restricted
            "analyze": SandboxPolicy.STRICT,     # Analysis should be restricted
            "general": SandboxPolicy.MODERATE    # Default for general tasks
        }
        
        # Track sandbox usage
        self.sandbox_usage = {
            "total_executions": 0,
            "policy_usage": {},
            "security_incidents": 0
        }
        
        logger.info(f"Sandbox integration initialized with default policy: {default_policy.value}")
    
    def get_task_policy(self, task_title: str, task_metadata: Dict[str, Any]) -> SandboxPolicy:
        """Determine sandbox policy for a task.
        
        Args:
            task_title: Task title
            task_metadata: Task metadata
            
        Returns:
            Appropriate sandbox policy
        """
        # Check if policy is explicitly specified
        if "sandbox_policy" in task_metadata:
            policy_name = task_metadata["sandbox_policy"]
            try:
                return SandboxPolicy(policy_name)
            except ValueError:
                logger.warning(f"Invalid sandbox policy: {policy_name}, using default")
        
        # Determine based on task type
        task_lower = task_title.lower()
        
        for task_type, policy in self.task_policies.items():
            if task_type in task_lower:
                return policy
        
        # Check for security-sensitive keywords
        sensitive_keywords = ["production", "database", "credential", "secret", "deploy"]
        if any(keyword in task_lower for keyword in sensitive_keywords):
            return SandboxPolicy.STRICT
        
        return self.default_policy
    
    def execute_worker_command(self,
                             worker_id: str,
                             task_id: str,
                             command: str,
                             task_metadata: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """Execute a worker command in sandbox.
        
        Args:
            worker_id: Worker identifier
            task_id: Task identifier
            command: Command to execute
            task_metadata: Task metadata for policy determination
            
        Returns:
            Execution result
        """
        # Determine policy
        task_title = task_metadata.get("title", "") if task_metadata else ""
        policy = self.get_task_policy(task_title, task_metadata or {})
        
        # Create sandbox ID
        sandbox_id = f"worker_{worker_id}_task_{task_id}"
        
        # Log execution
        logger.info(f"Executing command in sandbox {sandbox_id} with policy {policy.value}")
        
        # Execute in sandbox
        result = self.sandbox_manager.execute_in_sandbox(
            command=command,
            sandbox_id=sandbox_id,
            policy=policy,
            timeout=task_metadata.get("timeout", 300) if task_metadata else 300,
            env={"TASK_ID": task_id, "WORKER_ID": worker_id}
        )
        
        # Update usage statistics
        self.sandbox_usage["total_executions"] += 1
        self.sandbox_usage["policy_usage"][policy.value] = \
            self.sandbox_usage["policy_usage"].get(policy.value, 0) + 1
        
        # Handle security violations
        if result.security_violations:
            self.sandbox_usage["security_incidents"] += 1
            self._handle_security_violations(
                worker_id, task_id, result.security_violations
            )
        
        # Store feedback if available
        if self.orchestrator.feedback_storage:
            self._store_execution_feedback(worker_id, task_id, result)
        
        return result
    
    def execute_worker_code(self,
                           worker_id: str,
                           task_id: str,
                           code: str,
                           language: str = "python",
                           task_metadata: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """Execute worker code in sandbox.
        
        Args:
            worker_id: Worker identifier
            task_id: Task identifier
            code: Code to execute
            language: Programming language
            task_metadata: Task metadata
            
        Returns:
            Execution result
        """
        if language != "python":
            # For non-Python, save to file and execute
            import tempfile
            ext_map = {
                "javascript": ".js",
                "java": ".java",
                "c": ".c",
                "cpp": ".cpp",
                "go": ".go",
                "rust": ".rs"
            }
            
            ext = ext_map.get(language, ".txt")
            with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False) as f:
                f.write(code)
                f.flush()
                
                # Determine execution command
                if language == "javascript":
                    command = f"node {f.name}"
                elif language == "python":
                    command = f"python {f.name}"
                elif language == "java":
                    # Compile first
                    compile_result = self.execute_worker_command(
                        worker_id, task_id, f"javac {f.name}", task_metadata
                    )
                    if compile_result.success:
                        class_name = os.path.splitext(os.path.basename(f.name))[0]
                        command = f"java {class_name}"
                    else:
                        return compile_result
                else:
                    return ExecutionResult(
                        success=False,
                        output="",
                        error=f"Unsupported language: {language}",
                        exit_code=-1,
                        execution_time=0
                    )
                
                result = self.execute_worker_command(
                    worker_id, task_id, command, task_metadata
                )
                
                # Cleanup
                try:
                    os.unlink(f.name)
                except:
                    pass
                
                return result
        
        # Python code execution
        task_title = task_metadata.get("title", "") if task_metadata else ""
        policy = self.get_task_policy(task_title, task_metadata or {})
        
        sandbox_id = f"worker_{worker_id}_task_{task_id}"
        
        # Determine allowed modules based on task
        allowed_modules = self._get_allowed_modules(task_metadata)
        
        # Create sandbox and execute
        with SecureSandbox(policy=policy) as sandbox:
            result = sandbox.execute_python(
                code=code,
                timeout=task_metadata.get("timeout", 300) if task_metadata else 300,
                modules_allowed=allowed_modules
            )
        
        # Update statistics and handle violations
        self.sandbox_usage["total_executions"] += 1
        self.sandbox_usage["policy_usage"][policy.value] = \
            self.sandbox_usage["policy_usage"].get(policy.value, 0) + 1
        
        if result.security_violations:
            self.sandbox_usage["security_incidents"] += 1
            self._handle_security_violations(
                worker_id, task_id, result.security_violations
            )
        
        # Store feedback
        if self.orchestrator.feedback_storage:
            self._store_execution_feedback(worker_id, task_id, result)
        
        return result
    
    def _get_allowed_modules(self, task_metadata: Optional[Dict[str, Any]]) -> Optional[List[str]]:
        """Get allowed Python modules for a task.
        
        Args:
            task_metadata: Task metadata
            
        Returns:
            List of allowed modules or None for no restrictions
        """
        if not task_metadata:
            return None
        
        # Check if modules are explicitly specified
        if "allowed_modules" in task_metadata:
            return task_metadata["allowed_modules"]
        
        # Common safe modules
        safe_modules = [
            "math", "datetime", "json", "re", "collections",
            "itertools", "functools", "typing", "dataclasses",
            "pathlib", "hashlib", "base64", "urllib.parse"
        ]
        
        task_title = task_metadata.get("title", "").lower()
        
        # Add task-specific modules
        if "test" in task_title:
            safe_modules.extend(["unittest", "pytest", "mock"])
        
        if "data" in task_title or "analysis" in task_title:
            safe_modules.extend(["pandas", "numpy", "matplotlib"])
        
        if "web" in task_title or "api" in task_title:
            safe_modules.extend(["requests", "flask", "fastapi"])
        
        # For strict tasks, limit modules
        if task_metadata.get("strict_sandbox", False):
            return safe_modules[:10]  # Only core modules
        
        return None  # No restrictions for general tasks
    
    def _handle_security_violations(self, 
                                  worker_id: str,
                                  task_id: str,
                                  violations: List[str]):
        """Handle security violations.
        
        Args:
            worker_id: Worker identifier
            task_id: Task identifier
            violations: List of violations
        """
        logger.error(f"Security violations in task {task_id} by worker {worker_id}:")
        for violation in violations:
            logger.error(f"  - {violation}")
        
        # Store security feedback
        if self.orchestrator.feedback_storage:
            try:
                feedback = create_security_feedback(
                    issue_type="sandbox_violation",
                    severity=FeedbackSeverity.ERROR,
                    message=f"Security violations detected in task {task_id}",
                    details={
                        "worker_id": worker_id,
                        "task_id": task_id,
                        "violations": violations,
                        "timestamp": datetime.now().isoformat()
                    },
                    affected_files=[],
                    recommendations=[
                        "Review task implementation for security issues",
                        "Consider using stricter sandbox policy",
                        "Audit worker permissions"
                    ]
                )
                self.orchestrator.feedback_storage.save(feedback)
            except Exception as e:
                logger.error(f"Failed to store security feedback: {e}")
        
        # Notify orchestrator of security issue
        if hasattr(self.orchestrator, 'security_handler'):
            self.orchestrator.security_handler.handle_violation(
                worker_id, task_id, violations
            )
    
    def _store_execution_feedback(self,
                                worker_id: str,
                                task_id: str,
                                result: ExecutionResult):
        """Store execution feedback.
        
        Args:
            worker_id: Worker identifier
            task_id: Task identifier
            result: Execution result
        """
        try:
            from .feedback_model import FeedbackModel, FeedbackType
            
            feedback = FeedbackModel(
                feedback_id=f"sandbox_{result.sandbox_id}",
                task_id=task_id,
                feedback_type=FeedbackType.EXECUTION,
                message=f"Sandbox execution {'succeeded' if result.success else 'failed'}",
                severity=FeedbackSeverity.INFO if result.success else FeedbackSeverity.WARNING,
                timestamp=datetime.now(),
                source=f"sandbox_worker_{worker_id}",
                metrics={
                    "execution_time": result.execution_time,
                    "exit_code": result.exit_code,
                    "resources": result.resources_used
                },
                context={
                    "sandbox_id": result.sandbox_id,
                    "has_violations": len(result.security_violations) > 0
                },
                tags=["sandbox", "execution"]
            )
            
            self.orchestrator.feedback_storage.save(feedback)
            
        except Exception as e:
            logger.debug(f"Failed to store execution feedback: {e}")
    
    def get_sandbox_report(self) -> Dict[str, Any]:
        """Get sandbox usage report.
        
        Returns:
            Sandbox statistics and security report
        """
        manager_report = self.sandbox_manager.get_execution_report()
        
        return {
            "usage_statistics": self.sandbox_usage,
            "manager_report": manager_report,
            "policy_distribution": self.sandbox_usage.get("policy_usage", {}),
            "security_summary": {
                "total_incidents": self.sandbox_usage["security_incidents"],
                "incident_rate": (
                    self.sandbox_usage["security_incidents"] / 
                    max(self.sandbox_usage["total_executions"], 1)
                )
            }
        }
    
    def cleanup_sandboxes(self):
        """Cleanup all active sandboxes."""
        active = list(self.sandbox_manager.active_sandboxes.keys())
        for sandbox_id in active:
            try:
                self.sandbox_manager.destroy_sandbox(sandbox_id)
            except Exception as e:
                logger.error(f"Failed to cleanup sandbox {sandbox_id}: {e}")
        
        logger.info(f"Cleaned up {len(active)} sandboxes")


def integrate_sandbox_with_orchestrator(orchestrator,
                                      default_policy: str = "moderate") -> SandboxIntegration:
    """Integrate sandbox execution with orchestrator.
    
    Args:
        orchestrator: Orchestrator instance
        default_policy: Default security policy
        
    Returns:
        Sandbox integration instance
    """
    policy = SandboxPolicy(default_policy)
    integration = SandboxIntegration(orchestrator, policy)
    
    # Store reference in orchestrator
    orchestrator.sandbox_integration = integration
    
    # Modify worker execution to use sandbox
    if hasattr(orchestrator, 'workers'):
        for worker in orchestrator.workers:
            # Wrap worker execution methods
            original_execute = worker.execute_command if hasattr(worker, 'execute_command') else None
            
            def sandboxed_execute(command, **kwargs):
                return integration.execute_worker_command(
                    worker_id=worker.worker_id,
                    task_id=kwargs.get('task_id', 'unknown'),
                    command=command,
                    task_metadata=kwargs.get('metadata', {})
                )
            
            if original_execute:
                worker.execute_command = sandboxed_execute
    
    logger.info("Sandbox execution integrated with orchestrator")
    
    return integration