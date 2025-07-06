#!/usr/bin/env python3
"""
Sonnet Worker - Worker component using Claude Sonnet model
"""

import os
import subprocess
import tempfile
import json
import shlex
import logging
import time
from typing import Optional, Dict, Any

from .models import TaskStatus, WorkerTask
from .orchestrator import TaskMasterInterface

# Import direct Claude API
try:
    from .claude_direct_api import create_claude_client, ClaudeResponse
    DIRECT_API_AVAILABLE = True
except ImportError:
    DIRECT_API_AVAILABLE = False

# Import error handler if available
try:
    from .claude_error_handler import ClaudeErrorHandler
    ERROR_HANDLER_AVAILABLE = True
except ImportError:
    ERROR_HANDLER_AVAILABLE = False

logger = logging.getLogger(__name__)


class SonnetWorker:
    """Sonnet model acting as a worker"""
    
    def __init__(self, worker_id: int, working_dir: str, config):
        self.worker_id = worker_id
        self.working_dir = working_dir
        self.config = config
        # Add execution validation flag if not present
        if not hasattr(self.config, 'validate_execution'):
            self.config.validate_execution = True
        self.claude_path = config.claude_command
        self.model = config.worker_model
        self.turns = config.max_turns
        # Statistics
        self.tasks_completed = 0
        self.session_tokens_used = 0
        # Reference to orchestrator (set by orchestrator)
        self.orchestrator = None
        
        # Initialize error handler
        self.error_handler = None
        if ERROR_HANDLER_AVAILABLE:
            self.error_handler = ClaudeErrorHandler(
                max_retries=getattr(config, 'max_retries', 3),
                base_delay=getattr(config, 'retry_base_delay', 1.0),
                max_delay=getattr(config, 'retry_max_delay', 60.0)
            )
        
        # Initialize Claude client (prefer direct API over subprocess)
        self.use_direct_api = DIRECT_API_AVAILABLE and getattr(config, 'use_direct_api', True)
        if self.use_direct_api:
            self.claude_client = create_claude_client(
                use_subprocess=False,
                model=config.worker_model
            )
            logger.info(f"Worker {worker_id} using direct Claude API")
        else:
            self.claude_client = None
            logger.info(f"Worker {worker_id} using subprocess mode")
        
        logger.info(f"Worker {worker_id} initialized in {working_dir}")
    
    def process_task(self, task: WorkerTask) -> WorkerTask:
        """Process a single task using Claude CLI"""
        logger.info(f"Worker {self.worker_id}: Starting task {task.task_id} - {task.title}")
        
        try:
            # Update task status in Task Master
            self.task_master.set_task_status(task.task_id, "in-progress")
            task.status_message = "Updating task status..."
            
            # Create a prompt for Claude
            prompt = self._create_claude_prompt(task)
            
            # Execute Claude command (will use retry logic if error handler is available)
            result = self._execute_claude_command(prompt)
            
            if result['success']:
                task.status = TaskStatus.COMPLETED
                task.result = result['output']
                self.task_master.set_task_status(task.task_id, "done")
                
                # Track usage
                if 'usage' in result:
                    usage = result['usage']
                    self.session_tokens_used += usage.get('tokens_used', 0)
                    self.tasks_completed += 1
                    
                    # Log usage warning if present
                    if usage.get('warning'):
                        logger.warning(f"Worker {self.worker_id} - Usage Warning: {usage['warning']}")
                        logger.warning(f"Total tokens used this session: {self.session_tokens_used}")
                
                # Update subtask with completion notes
                completion_notes = f"Completed by Worker {self.worker_id}. Output: {result['output'][:200]}..."
                self.task_master.update_subtask(task.task_id, completion_notes)
                
                logger.info(f"Worker {self.worker_id}: Completed task {task.task_id}")
            else:
                task.status = TaskStatus.FAILED
                task.error = result['error']
                
                # Check if it's a usage limit error
                if "USAGE LIMIT" in result['error']:
                    logger.error(f"Worker {self.worker_id}: USAGE LIMIT REACHED - Cannot continue processing")
                    # Set a flag to stop this worker
                    task.error = "USAGE_LIMIT_REACHED"
                else:
                    logger.error(f"Worker {self.worker_id}: Failed task {task.task_id} - {result['error']}")
                
                # Log request ID if available
                if 'request_id' in result and result['request_id']:
                    logger.error(f"Request ID for debugging: {result['request_id']}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"Worker {self.worker_id}: Exception processing task {task.task_id} - {e}")
        
        return task
    
    def _create_claude_prompt(self, task: WorkerTask) -> str:
        """Create a prompt for Claude based on the task"""
        prompt_parts = [
            f"Task ID: {task.task_id}",
            f"Title: {task.title}",
            f"Description: {task.description}"
        ]
        
        if task.details:
            prompt_parts.append(f"Details: {task.details}")
        
        prompt_parts.append("\nPlease complete this task. Start by analyzing what needs to be done, then implement the solution.")
        prompt_parts.append("\nIMPORTANT: If this task requires creating files, make sure to actually create them using the Write or Edit tools.")
        
        return "\n".join(prompt_parts)
    
    def _execute_claude_direct(self, prompt: str) -> Dict[str, Any]:
        """Execute Claude using direct API"""
        try:
            # Get allowed tools from config
            allowed_tools = self.config.claude_flags.get("allowed_tools", [])
            
            # Use direct API
            response = self.claude_client.execute_with_tools(prompt, allowed_tools)
            
            if response.success:
                return {
                    'success': True,
                    'output': response.output,
                    'usage': response.usage or {},
                    'request_id': response.request_id
                }
            else:
                return {
                    'success': False,
                    'error': response.error or "Unknown error",
                    'request_id': response.request_id
                }
                
        except Exception as e:
            logger.error(f"Direct API execution error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _execute_claude_command(self, prompt: str) -> Dict[str, Any]:
        """Wrapper for executing Claude command - uses error handler if available"""
        # Use direct API if available
        if self.use_direct_api and self.claude_client:
            return self._execute_claude_direct(prompt)
        
        # Fall back to subprocess mode
        if self.error_handler:
            return self.error_handler.execute_with_retry(
                self._execute_claude_command_internal, prompt
            )
        else:
            return self._execute_claude_command_internal(prompt)
    
    def _execute_claude_command_internal(self, prompt: str) -> Dict[str, Any]:
        """Execute Claude CLI command with the given prompt"""
        try:
            # First check if Claude CLI is available and authenticated
            test_cmd = [self.config.claude_command, "--version"]
            test_result = subprocess.run(test_cmd, capture_output=True, text=True)
            if test_result.returncode != 0:
                return {
                    'success': False,
                    'error': f"Claude CLI not available or not authenticated: {test_result.stderr}"
                }
            
            # Save prompt to temporary file to avoid shell escaping issues
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                prompt_file = f.name
            
            # Construct Claude command
            cmd = [
                self.config.claude_command,
                "-p", f"@{prompt_file}",
                "--model", self.config.worker_model
            ]
            
            # Add additional flags from config
            if self.config.claude_flags.get("verbose"):
                cmd.append("--verbose")
            if self.config.claude_flags.get("dangerously_skip_permissions"):
                cmd.append("--dangerously-skip-permissions")
            
            # Add other CLI flags
            if self.config.claude_flags.get("add_dir"):
                for dir_path in self.config.claude_flags["add_dir"]:
                    cmd.extend(["--add-dir", dir_path])
            
            if self.config.claude_flags.get("allowed_tools"):
                for tool in self.config.claude_flags["allowed_tools"]:
                    cmd.extend(["--allowedTools", tool])
            
            if self.config.claude_flags.get("disallowed_tools"):
                for tool in self.config.claude_flags["disallowed_tools"]:
                    cmd.extend(["--disallowedTools", tool])
            
            if self.config.claude_flags.get("output_format") and self.config.claude_flags["output_format"] != "text":
                cmd.extend(["--output-format", self.config.claude_flags["output_format"]])
            
            if self.config.claude_flags.get("input_format") and self.config.claude_flags["input_format"] != "text":
                cmd.extend(["--input-format", self.config.claude_flags["input_format"]])
            
            if self.config.max_turns:
                cmd.extend(["--max-turns", str(self.config.max_turns)])
            
            if self.config.claude_flags.get("permission_mode"):
                cmd.extend(["--permission-mode", self.config.claude_flags["permission_mode"]])
            
            if self.config.claude_flags.get("permission_prompt_tool"):
                cmd.extend(["--permission-prompt-tool", self.config.claude_flags["permission_prompt_tool"]])
            
            logger.debug(f"Worker {self.worker_id}: Executing command: {' '.join(cmd)}")
            
            # Set up environment variables
            env = os.environ.copy()
            
            # First check if ANTHROPIC_API_KEY is already in environment
            if "ANTHROPIC_API_KEY" not in env:
                # Try to get it from .env file
                try:
                    from dotenv import load_dotenv
                    load_dotenv()
                except ImportError:
                    pass
                
                # Check again after loading .env
                if "ANTHROPIC_API_KEY" not in os.environ:
                    # Try to get from config
                    api_key = self.config.claude_environment.get("ANTHROPIC_API_KEY")
                    if api_key:
                        env["ANTHROPIC_API_KEY"] = api_key
                    else:
                        logger.error("ANTHROPIC_API_KEY not found in environment or config")
                        return {
                            'success': False,
                            'error': "ANTHROPIC_API_KEY not configured"
                        }
            
            # Add other environment variables from config
            for key, value in self.config.claude_environment.items():
                if value is not None:
                    env[key] = str(value)
            
            # Execute command with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.working_dir,
                timeout=self.config.worker_timeout,
                env=env
            )
            
            # Clean up temp file
            os.unlink(prompt_file)
            
            if result.returncode == 0:
                # Try to parse usage information from output
                usage_info = self._parse_usage_info(result.stdout)
                
                return {
                    'success': True,
                    'output': result.stdout,
                    'usage': usage_info
                }
            else:
                # Extract error details
                error_msg = result.stderr or result.stdout
                request_id = self._extract_request_id(error_msg)
                
                return {
                    'success': False,
                    'error': error_msg,
                    'request_id': request_id
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f"Task execution timed out after {self.config.worker_timeout} seconds"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Exception during execution: {str(e)}"
            }
    
    def _parse_usage_info(self, output: str) -> Dict[str, Any]:
        """Parse usage information from Claude output"""
        usage = {}
        
        # Look for usage patterns in the output
        # This is a simplified parser - adjust based on actual Claude output format
        if "Usage:" in output or "Tokens:" in output:
            lines = output.split('\n')
            for line in lines:
                if "tokens" in line.lower():
                    # Try to extract token count
                    import re
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        usage['tokens_used'] = int(numbers[0])
                
                if "warning" in line.lower() and ("usage" in line.lower() or "limit" in line.lower()):
                    usage['warning'] = line.strip()
        
        return usage
    
    def _extract_request_id(self, error_msg: str) -> Optional[str]:
        """Extract request ID from error message for debugging"""
        import re
        # Look for patterns like "request_id: xxx" or "Request ID: xxx"
        match = re.search(r'(?:request_id|Request ID):\s*([a-zA-Z0-9-]+)', error_msg, re.IGNORECASE)
        if match:
            return match.group(1)
        return None


