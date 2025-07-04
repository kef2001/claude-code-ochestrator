"""
Enhanced Orchestrator Integration - Connects all communication components
"""
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import subprocess
import json
import tempfile

from .worker_result_manager import WorkerResultManager, WorkerResult
from .enhanced_review_system import EnhancedReviewSystem
from .task_master import TaskManager, TaskStatus
from .communication_protocol import CommunicationProtocol, MessageType

logger = logging.getLogger(__name__)


class WorkerProcessManager:
    """Manages worker process lifecycle and communication"""
    
    def __init__(self, orchestrator_id: str):
        self.orchestrator_id = orchestrator_id
        self.active_workers: Dict[str, subprocess.Popen] = {}
        self.result_manager = WorkerResultManager()
        self.comm_protocol = CommunicationProtocol()
        
    async def start_worker(self, task_id: str, worker_id: str) -> subprocess.Popen:
        """Start a worker process with enhanced communication"""
        # Create task file
        task_file = Path(f".taskmaster/tasks/task_{task_id}.json")
        
        # Prepare worker command with enhanced session
        cmd = [
            sys.executable, "-m", "claude_orchestrator.enhanced_worker_session",
            "--task-file", str(task_file),
            "--worker-id", worker_id,
            "--orchestrator-id", self.orchestrator_id
        ]
        
        # Start worker process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        self.active_workers[worker_id] = process
        
        # Send initial handshake
        await self.comm_protocol.send_message(
            sender_id=self.orchestrator_id,
            recipient_id=worker_id,
            message_type=MessageType.TASK_ASSIGNMENT,
            payload={
                'task_id': task_id,
                'task_file': str(task_file),
                'started_at': datetime.now().isoformat()
            }
        )
        
        logger.info(f"Started worker {worker_id} for task {task_id}")
        return process
        
    async def monitor_worker(self, worker_id: str, process: subprocess.Popen) -> WorkerResult:
        """Monitor worker process and capture results"""
        # Poll process completion
        while process.poll() is None:
            await asyncio.sleep(0.5)
            
            # Check for heartbeat
            heartbeat_msg = await self.comm_protocol.receive_message(
                recipient_id=self.orchestrator_id,
                sender_id=worker_id,
                timeout=1.0
            )
            
            if heartbeat_msg and heartbeat_msg.header.message_type == MessageType.WORKER_HEARTBEAT:
                logger.debug(f"Received heartbeat from {worker_id}")
                
        # Process completed - get return code
        return_code = process.returncode
        
        # Capture output
        stdout, stderr = process.communicate()
        
        # Get task result from database
        task_id = self._extract_task_id(worker_id)
        result = self.result_manager.get_latest_result(task_id)
        
        if not result:
            # Create error result
            result = WorkerResult(
                task_id=task_id,
                worker_id=worker_id,
                status=ResultStatus.FAILED,
                output=stdout or "",
                created_files=[],
                modified_files=[],
                execution_time=0,
                tokens_used=0,
                timestamp=datetime.now().isoformat(),
                error_message=stderr or f"Process exited with code {return_code}"
            )
            self.result_manager.store_result(result)
            
        # Clean up
        del self.active_workers[worker_id]
        
        return result
        
    def _extract_task_id(self, worker_id: str) -> str:
        """Extract task ID from worker ID"""
        # Worker ID format: worker_<task_id>_<timestamp>
        parts = worker_id.split('_')
        if len(parts) >= 2:
            return parts[1]
        return "unknown"
        
    async def shutdown_all_workers(self):
        """Gracefully shutdown all active workers"""
        for worker_id, process in self.active_workers.items():
            try:
                # Send shutdown message
                await self.comm_protocol.send_message(
                    sender_id=self.orchestrator_id,
                    recipient_id=worker_id,
                    message_type=MessageType.SHUTDOWN,
                    payload={}
                )
                
                # Give worker time to cleanup
                await asyncio.sleep(1.0)
                
                # Terminate if still running
                if process.poll() is None:
                    process.terminate()
                    await asyncio.sleep(0.5)
                    
                    # Force kill if needed
                    if process.poll() is None:
                        process.kill()
                        
            except Exception as e:
                logger.error(f"Error shutting down worker {worker_id}: {e}")


class EnhancedOrchestratorIntegration:
    """Main integration point for enhanced orchestration system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.orchestrator_id = f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize components
        self.task_manager = TaskManager()
        self.result_manager = WorkerResultManager()
        self.review_system = EnhancedReviewSystem(self.result_manager)
        self.worker_manager = WorkerProcessManager(self.orchestrator_id)
        
        # Configuration
        self.max_parallel_workers = config.get('max_parallel_workers', 3)
        self.worker_timeout = config.get('worker_timeout', 600)  # 10 minutes
        
    async def process_tasks(self, task_ids: List[str]):
        """Process a list of tasks with enhanced communication"""
        logger.info(f"Processing {len(task_ids)} tasks")
        
        # Create task queue
        task_queue = asyncio.Queue()
        for task_id in task_ids:
            await task_queue.put(task_id)
            
        # Start worker tasks
        worker_tasks = []
        for i in range(min(self.max_parallel_workers, len(task_ids))):
            task = asyncio.create_task(self._worker_loop(task_queue, i))
            worker_tasks.append(task)
            
        # Wait for all workers to complete
        await asyncio.gather(*worker_tasks)
        
        # Review all completed tasks
        for task_id in task_ids:
            await self._review_task(task_id)
            
    async def _worker_loop(self, task_queue: asyncio.Queue, worker_index: int):
        """Worker loop that processes tasks from queue"""
        while not task_queue.empty():
            try:
                task_id = await task_queue.get()
                await self._process_single_task(task_id, worker_index)
                
            except Exception as e:
                logger.error(f"Worker {worker_index} error: {e}")
                
    async def _process_single_task(self, task_id: str, worker_index: int):
        """Process a single task with a worker"""
        worker_id = f"worker_{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Update task status
            self.task_manager.update_task_status(task_id, TaskStatus.IN_PROGRESS)
            
            # Start worker
            process = await self.worker_manager.start_worker(task_id, worker_id)
            
            # Monitor with timeout
            result = await asyncio.wait_for(
                self.worker_manager.monitor_worker(worker_id, process),
                timeout=self.worker_timeout
            )
            
            # Validate result
            is_valid, message = self.result_manager.validate_result(task_id)
            
            if is_valid:
                logger.info(f"Task {task_id} completed successfully")
            else:
                logger.warning(f"Task {task_id} validation failed: {message}")
                
        except asyncio.TimeoutError:
            logger.error(f"Task {task_id} timed out")
            # Kill the worker process
            if worker_id in self.worker_manager.active_workers:
                self.worker_manager.active_workers[worker_id].kill()
                
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
            
    async def _review_task(self, task_id: str):
        """Review a completed task"""
        try:
            review_result = await self.review_system.review_task(task_id)
            
            if review_result['success']:
                logger.info(f"Task {task_id} review passed")
                self.task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
            else:
                logger.warning(f"Task {task_id} review failed: {review_result['message']}")
                self.task_manager.update_task_status(task_id, TaskStatus.FAILED)
                
        except Exception as e:
            logger.error(f"Error reviewing task {task_id}: {e}")
            
    async def create_task_from_description(self, description: str) -> List[str]:
        """Create tasks from a high-level description using Opus"""
        # This would use the Opus manager to break down the description
        # For now, return a placeholder
        task_id = self.task_manager.create_task(
            title="User requested task",
            description=description,
            type="implementation"
        )
        
        return [task_id]
        
    async def shutdown(self):
        """Gracefully shutdown the orchestrator"""
        logger.info("Shutting down orchestrator")
        await self.worker_manager.shutdown_all_workers()