"""Secure Sandbox Execution Environment for Claude Orchestrator.

This module provides a secure environment for executing code and commands
with proper isolation, resource limits, and security controls.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import signal
import resource
import logging
import threading
import time
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import platform
from enum import Enum
import psutil

logger = logging.getLogger(__name__)


class SandboxPolicy(Enum):
    """Security policies for sandbox execution."""
    STRICT = "strict"          # No network, limited filesystem
    MODERATE = "moderate"      # Limited network, controlled filesystem
    PERMISSIVE = "permissive"  # Full network, monitored filesystem
    CUSTOM = "custom"          # User-defined policy


@dataclass
class ResourceLimits:
    """Resource limits for sandbox execution."""
    max_cpu_time: int = 300           # seconds
    max_memory: int = 512 * 1024 * 1024  # 512MB
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    max_processes: int = 10
    max_open_files: int = 100
    network_allowed: bool = False
    allowed_paths: List[str] = field(default_factory=list)
    blocked_paths: List[str] = field(default_factory=list)
    allowed_commands: List[str] = field(default_factory=list)
    blocked_commands: List[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Result of sandbox execution."""
    success: bool
    output: str
    error: str
    exit_code: int
    execution_time: float
    resources_used: Dict[str, Any] = field(default_factory=dict)
    security_violations: List[str] = field(default_factory=list)
    sandbox_id: Optional[str] = None


class SecurityMonitor:
    """Monitors and enforces security policies during execution."""
    
    def __init__(self, policy: SandboxPolicy, limits: ResourceLimits):
        self.policy = policy
        self.limits = limits
        self.violations: List[str] = []
        self._monitoring = False
        self._process: Optional[psutil.Process] = None
        
    def start_monitoring(self, process_id: int):
        """Start monitoring a process."""
        try:
            self._process = psutil.Process(process_id)
            self._monitoring = True
            
            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True
            )
            monitor_thread.start()
            
        except psutil.NoSuchProcess:
            logger.error(f"Process {process_id} not found")
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self._monitoring = False
        self._process = None
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._monitoring and self._process:
            try:
                # Check memory usage
                if self._process.memory_info().rss > self.limits.max_memory:
                    self.violations.append(f"Memory limit exceeded: {self._process.memory_info().rss} bytes")
                    self._terminate_process("Memory limit exceeded")
                
                # Check CPU usage
                cpu_percent = self._process.cpu_percent(interval=0.1)
                if cpu_percent > 90:  # Sustained high CPU
                    logger.warning(f"High CPU usage: {cpu_percent}%")
                
                # Check file operations (platform-specific)
                if platform.system() != "Windows":
                    open_files = self._process.open_files()
                    if len(open_files) > self.limits.max_open_files:
                        self.violations.append(f"Too many open files: {len(open_files)}")
                
                # Check network connections if not allowed
                if not self.limits.network_allowed:
                    connections = self._process.connections()
                    if connections:
                        self.violations.append(f"Unauthorized network connection attempted")
                        self._terminate_process("Network access not allowed")
                
                time.sleep(0.5)  # Check every 500ms
                
            except psutil.NoSuchProcess:
                break
            except Exception as e:
                logger.debug(f"Monitoring error: {e}")
    
    def _terminate_process(self, reason: str):
        """Terminate the monitored process."""
        if self._process:
            try:
                logger.warning(f"Terminating process {self._process.pid}: {reason}")
                self._process.terminate()
                time.sleep(0.5)
                if self._process.is_running():
                    self._process.kill()
            except:
                pass
    
    def check_command(self, command: str) -> bool:
        """Check if a command is allowed."""
        # Extract base command
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return False
        
        base_cmd = cmd_parts[0]
        
        # Check against blocked commands
        if base_cmd in self.limits.blocked_commands:
            self.violations.append(f"Blocked command: {base_cmd}")
            return False
        
        # Check against allowed commands if list is not empty
        if self.limits.allowed_commands and base_cmd not in self.limits.allowed_commands:
            self.violations.append(f"Command not in allowed list: {base_cmd}")
            return False
        
        # Check for dangerous patterns
        dangerous_patterns = [
            "rm -rf /",
            "dd if=/dev/zero",
            "fork bomb",
            ":(){ :|:& };:",
            "> /dev/sda",
            "chmod -R 777 /",
            "mkfs.",
            "shutdown",
            "reboot"
        ]
        
        for pattern in dangerous_patterns:
            if pattern in command:
                self.violations.append(f"Dangerous command pattern detected: {pattern}")
                return False
        
        return True
    
    def check_path(self, path: str) -> bool:
        """Check if a path is allowed for access."""
        abs_path = os.path.abspath(path)
        
        # Check blocked paths
        for blocked in self.limits.blocked_paths:
            if abs_path.startswith(os.path.abspath(blocked)):
                self.violations.append(f"Access to blocked path: {abs_path}")
                return False
        
        # Check allowed paths if specified
        if self.limits.allowed_paths:
            allowed = any(
                abs_path.startswith(os.path.abspath(allowed))
                for allowed in self.limits.allowed_paths
            )
            if not allowed:
                self.violations.append(f"Path not in allowed list: {abs_path}")
                return False
        
        return True


class SecureSandbox:
    """Secure sandbox for code and command execution."""
    
    def __init__(self, 
                 policy: SandboxPolicy = SandboxPolicy.MODERATE,
                 working_dir: Optional[str] = None,
                 cleanup: bool = True):
        self.policy = policy
        self.working_dir = working_dir
        self.cleanup = cleanup
        self.limits = self._get_policy_limits(policy)
        self._sandbox_dir: Optional[str] = None
        self._original_cwd: Optional[str] = None
        
    def _get_policy_limits(self, policy: SandboxPolicy) -> ResourceLimits:
        """Get resource limits based on policy."""
        if policy == SandboxPolicy.STRICT:
            return ResourceLimits(
                max_cpu_time=60,
                max_memory=256 * 1024 * 1024,  # 256MB
                max_file_size=10 * 1024 * 1024,  # 10MB
                max_processes=5,
                network_allowed=False,
                blocked_paths=["/", "/etc", "/usr", "/var", "/tmp"],
                blocked_commands=["sudo", "su", "curl", "wget", "nc", "ssh"]
            )
        elif policy == SandboxPolicy.MODERATE:
            return ResourceLimits(
                max_cpu_time=300,
                max_memory=512 * 1024 * 1024,  # 512MB
                max_file_size=50 * 1024 * 1024,  # 50MB
                max_processes=10,
                network_allowed=True,
                blocked_paths=["/etc", "/usr/bin", "/usr/sbin"],
                blocked_commands=["sudo", "su"]
            )
        elif policy == SandboxPolicy.PERMISSIVE:
            return ResourceLimits(
                max_cpu_time=600,
                max_memory=1024 * 1024 * 1024,  # 1GB
                max_file_size=100 * 1024 * 1024,  # 100MB
                max_processes=20,
                network_allowed=True,
                blocked_commands=["sudo"]
            )
        else:
            # Custom policy - use defaults
            return ResourceLimits()
    
    def __enter__(self):
        """Enter sandbox context."""
        # Create sandbox directory
        self._sandbox_dir = tempfile.mkdtemp(prefix="sandbox_")
        self._original_cwd = os.getcwd()
        
        # Set up sandbox environment
        if self.working_dir:
            # Copy working directory contents to sandbox
            sandbox_work_dir = os.path.join(self._sandbox_dir, "work")
            shutil.copytree(self.working_dir, sandbox_work_dir)
            os.chdir(sandbox_work_dir)
        else:
            os.chdir(self._sandbox_dir)
        
        # Add sandbox to allowed paths
        self.limits.allowed_paths.append(self._sandbox_dir)
        
        logger.info(f"Sandbox created: {self._sandbox_dir}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit sandbox context."""
        # Restore original directory
        if self._original_cwd:
            os.chdir(self._original_cwd)
        
        # Cleanup sandbox
        if self.cleanup and self._sandbox_dir:
            try:
                shutil.rmtree(self._sandbox_dir)
                logger.info(f"Sandbox cleaned up: {self._sandbox_dir}")
            except Exception as e:
                logger.error(f"Failed to cleanup sandbox: {e}")
    
    def execute_command(self, 
                       command: str,
                       timeout: Optional[int] = None,
                       env: Optional[Dict[str, str]] = None) -> ExecutionResult:
        """Execute a command in the sandbox.
        
        Args:
            command: Command to execute
            timeout: Execution timeout in seconds
            env: Environment variables
            
        Returns:
            Execution result
        """
        sandbox_id = hashlib.md5(f"{command}_{time.time()}".encode()).hexdigest()[:8]
        monitor = SecurityMonitor(self.policy, self.limits)
        
        # Check command security
        if not monitor.check_command(command):
            return ExecutionResult(
                success=False,
                output="",
                error="Command blocked by security policy",
                exit_code=-1,
                execution_time=0,
                security_violations=monitor.violations,
                sandbox_id=sandbox_id
            )
        
        # Prepare environment
        sandbox_env = os.environ.copy()
        if env:
            sandbox_env.update(env)
        
        # Add sandbox markers
        sandbox_env["SANDBOX_ID"] = sandbox_id
        sandbox_env["SANDBOX_POLICY"] = self.policy.value
        
        # Remove potentially dangerous environment variables
        dangerous_vars = ["LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH"]
        for var in dangerous_vars:
            sandbox_env.pop(var, None)
        
        # Set resource limits (Unix only)
        def set_limits():
            if platform.system() != "Windows":
                # CPU time limit
                resource.setrlimit(resource.RLIMIT_CPU, 
                                 (self.limits.max_cpu_time, self.limits.max_cpu_time))
                # Memory limit
                resource.setrlimit(resource.RLIMIT_AS,
                                 (self.limits.max_memory, self.limits.max_memory))
                # File size limit
                resource.setrlimit(resource.RLIMIT_FSIZE,
                                 (self.limits.max_file_size, self.limits.max_file_size))
                # Process limit
                resource.setrlimit(resource.RLIMIT_NPROC,
                                 (self.limits.max_processes, self.limits.max_processes))
        
        # Execute command
        start_time = time.time()
        try:
            # Use timeout if specified
            actual_timeout = timeout or self.limits.max_cpu_time
            
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=sandbox_env,
                preexec_fn=set_limits if platform.system() != "Windows" else None
            )
            
            # Start monitoring
            monitor.start_monitoring(process.pid)
            
            # Wait for completion
            stdout, stderr = process.communicate(timeout=actual_timeout)
            
            execution_time = time.time() - start_time
            
            # Get resource usage
            resources_used = {}
            try:
                proc_info = psutil.Process(process.pid)
                resources_used = {
                    "cpu_percent": proc_info.cpu_percent(),
                    "memory_mb": proc_info.memory_info().rss / 1024 / 1024,
                    "num_threads": proc_info.num_threads()
                }
            except:
                pass
            
            return ExecutionResult(
                success=process.returncode == 0,
                output=stdout.decode('utf-8', errors='ignore'),
                error=stderr.decode('utf-8', errors='ignore'),
                exit_code=process.returncode,
                execution_time=execution_time,
                resources_used=resources_used,
                security_violations=monitor.violations,
                sandbox_id=sandbox_id
            )
            
        except subprocess.TimeoutExpired:
            process.kill()
            return ExecutionResult(
                success=False,
                output="",
                error=f"Command timed out after {actual_timeout} seconds",
                exit_code=-1,
                execution_time=time.time() - start_time,
                security_violations=monitor.violations,
                sandbox_id=sandbox_id
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                execution_time=time.time() - start_time,
                security_violations=monitor.violations,
                sandbox_id=sandbox_id
            )
        finally:
            monitor.stop_monitoring()
    
    def execute_python(self,
                      code: str,
                      timeout: Optional[int] = None,
                      modules_allowed: Optional[List[str]] = None) -> ExecutionResult:
        """Execute Python code in the sandbox.
        
        Args:
            code: Python code to execute
            timeout: Execution timeout
            modules_allowed: List of allowed modules
            
        Returns:
            Execution result
        """
        # Create temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Add security wrapper
            wrapper_code = """
import sys
import builtins

# Restrict imports if specified
original_import = builtins.__import__
allowed_modules = {allowed_modules}

def restricted_import(name, *args, **kwargs):
    if allowed_modules and name not in allowed_modules:
        raise ImportError(f"Module '{name}' is not allowed in sandbox")
    return original_import(name, *args, **kwargs)

if allowed_modules:
    builtins.__import__ = restricted_import

# Disable dangerous builtins
dangerous_builtins = ['eval', 'exec', 'compile', '__import__']
for builtin in dangerous_builtins:
    if hasattr(builtins, builtin):
        delattr(builtins, builtin)

# User code below
{code}
"""
            
            final_code = wrapper_code.format(
                allowed_modules=modules_allowed or [],
                code=code
            )
            
            f.write(final_code)
            f.flush()
            
            # Execute Python file
            result = self.execute_command(f"{sys.executable} {f.name}", timeout)
            
            # Cleanup
            try:
                os.unlink(f.name)
            except:
                pass
            
            return result
    
    def execute_function(self,
                        func: Callable,
                        args: tuple = (),
                        kwargs: dict = None,
                        timeout: Optional[int] = None) -> ExecutionResult:
        """Execute a Python function in the sandbox.
        
        Args:
            func: Function to execute
            args: Function arguments
            kwargs: Function keyword arguments
            timeout: Execution timeout
            
        Returns:
            Execution result
        """
        import pickle
        import base64
        
        # Serialize function and arguments
        data = {
            'func': pickle.dumps(func),
            'args': pickle.dumps(args),
            'kwargs': pickle.dumps(kwargs or {})
        }
        
        # Create execution script
        exec_code = """
import pickle
import base64
import json
import sys

# Load serialized data
data = {data}

# Deserialize
func = pickle.loads(base64.b64decode(data['func'].encode()))
args = pickle.loads(base64.b64decode(data['args'].encode()))
kwargs = pickle.loads(base64.b64decode(data['kwargs'].encode()))

# Execute function
try:
    result = func(*args, **kwargs)
    print(json.dumps({{'success': True, 'result': str(result)}}))
except Exception as e:
    print(json.dumps({{'success': False, 'error': str(e)}}))
"""
        
        # Encode data
        encoded_data = {
            k: base64.b64encode(v).decode() 
            for k, v in data.items()
        }
        
        final_code = exec_code.format(data=encoded_data)
        
        return self.execute_python(final_code, timeout)


class SandboxManager:
    """Manages multiple sandbox instances and policies."""
    
    def __init__(self, default_policy: SandboxPolicy = SandboxPolicy.MODERATE):
        self.default_policy = default_policy
        self.active_sandboxes: Dict[str, SecureSandbox] = {}
        self.execution_history: List[ExecutionResult] = []
        self._lock = threading.Lock()
        
    def create_sandbox(self,
                      sandbox_id: str,
                      policy: Optional[SandboxPolicy] = None,
                      working_dir: Optional[str] = None) -> SecureSandbox:
        """Create a new sandbox instance.
        
        Args:
            sandbox_id: Unique sandbox identifier
            policy: Security policy
            working_dir: Working directory to copy
            
        Returns:
            Sandbox instance
        """
        with self._lock:
            if sandbox_id in self.active_sandboxes:
                raise ValueError(f"Sandbox {sandbox_id} already exists")
            
            sandbox = SecureSandbox(
                policy=policy or self.default_policy,
                working_dir=working_dir
            )
            
            self.active_sandboxes[sandbox_id] = sandbox
            return sandbox
    
    def execute_in_sandbox(self,
                          command: str,
                          sandbox_id: Optional[str] = None,
                          policy: Optional[SandboxPolicy] = None,
                          **kwargs) -> ExecutionResult:
        """Execute a command in a sandbox.
        
        Args:
            command: Command to execute
            sandbox_id: Sandbox to use (creates temporary if None)
            policy: Security policy
            **kwargs: Additional execution parameters
            
        Returns:
            Execution result
        """
        # Create temporary sandbox if needed
        temp_sandbox = sandbox_id is None
        if temp_sandbox:
            sandbox_id = f"temp_{int(time.time() * 1000)}"
        
        # Get or create sandbox
        if sandbox_id in self.active_sandboxes:
            sandbox = self.active_sandboxes[sandbox_id]
        else:
            sandbox = self.create_sandbox(sandbox_id, policy)
        
        try:
            # Execute command
            with sandbox:
                result = sandbox.execute_command(command, **kwargs)
                
            # Store in history
            self.execution_history.append(result)
            
            return result
            
        finally:
            # Cleanup temporary sandbox
            if temp_sandbox:
                self.destroy_sandbox(sandbox_id)
    
    def destroy_sandbox(self, sandbox_id: str):
        """Destroy a sandbox instance.
        
        Args:
            sandbox_id: Sandbox to destroy
        """
        with self._lock:
            if sandbox_id in self.active_sandboxes:
                del self.active_sandboxes[sandbox_id]
    
    def get_execution_report(self) -> Dict[str, Any]:
        """Get execution report.
        
        Returns:
            Execution statistics and security incidents
        """
        total_executions = len(self.execution_history)
        successful = sum(1 for r in self.execution_history if r.success)
        failed = total_executions - successful
        
        security_incidents = []
        for result in self.execution_history:
            if result.security_violations:
                security_incidents.append({
                    "sandbox_id": result.sandbox_id,
                    "violations": result.security_violations,
                    "timestamp": datetime.now().isoformat()
                })
        
        return {
            "total_executions": total_executions,
            "successful": successful,
            "failed": failed,
            "security_incidents": len(security_incidents),
            "recent_incidents": security_incidents[-10:],
            "active_sandboxes": list(self.active_sandboxes.keys())
        }


# Global sandbox manager instance
sandbox_manager = SandboxManager()


# Convenience functions
def execute_secure(command: str, 
                  policy: SandboxPolicy = SandboxPolicy.MODERATE,
                  **kwargs) -> ExecutionResult:
    """Execute a command securely in a temporary sandbox.
    
    Args:
        command: Command to execute
        policy: Security policy
        **kwargs: Additional parameters
        
    Returns:
        Execution result
    """
    return sandbox_manager.execute_in_sandbox(command, policy=policy, **kwargs)


def execute_python_secure(code: str,
                         policy: SandboxPolicy = SandboxPolicy.STRICT,
                         **kwargs) -> ExecutionResult:
    """Execute Python code securely in a temporary sandbox.
    
    Args:
        code: Python code to execute
        policy: Security policy
        **kwargs: Additional parameters
        
    Returns:
        Execution result
    """
    with SecureSandbox(policy=policy) as sandbox:
        return sandbox.execute_python(code, **kwargs)