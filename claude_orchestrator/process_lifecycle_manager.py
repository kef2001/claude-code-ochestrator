"""
Process Lifecycle Manager - Manages the complete worker-reviewer cycle
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import json
from pathlib import Path

from .worker_result_manager import WorkerResultManager, WorkerResult, ResultStatus
from .enhanced_review_system import EnhancedReviewSystem
from .task_master import TaskManager, TaskStatus
from .enhanced_prompts import EnhancedPromptSystem
from .communication_protocol import CommunicationProtocol, MessageType

logger = logging.getLogger(__name__)


class ProcessState(Enum):
    """States in the worker-reviewer lifecycle"""
    PENDING = "pending"
    WORKER_ASSIGNED = "worker_assigned"
    WORKER_EXECUTING = "worker_executing"
    WORKER_COMPLETED = "worker_completed"
    REVIEW_PENDING = "review_pending"
    REVIEW_IN_PROGRESS = "review_in_progress"
    REVIEW_COMPLETED = "review_completed"
    APPLYING_CHANGES = "applying_changes"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"


@dataclass
class ProcessContext:
    """Context for a task process lifecycle"""
    task_id: str
    task_data: Dict[str, Any]
    state: ProcessState
    worker_id: Optional[str] = None
    worker_result: Optional[WorkerResult] = None
    review_result: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = None
    updated_at: datetime = None
    error_messages: List[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        if self.error_messages is None:
            self.error_messages = []


class ProcessLifecycleManager:
    """Manages the complete lifecycle of task processing"""
    
    def __init__(self, orchestrator_id: str):
        self.orchestrator_id = orchestrator_id
        self.contexts: Dict[str, ProcessContext] = {}
        self.state_transitions: Dict[ProcessState, List[ProcessState]] = {
            ProcessState.PENDING: [ProcessState.WORKER_ASSIGNED, ProcessState.FAILED],
            ProcessState.WORKER_ASSIGNED: [ProcessState.WORKER_EXECUTING, ProcessState.FAILED],
            ProcessState.WORKER_EXECUTING: [ProcessState.WORKER_COMPLETED, ProcessState.FAILED],
            ProcessState.WORKER_COMPLETED: [ProcessState.REVIEW_PENDING, ProcessState.RETRY_PENDING],
            ProcessState.REVIEW_PENDING: [ProcessState.REVIEW_IN_PROGRESS, ProcessState.FAILED],
            ProcessState.REVIEW_IN_PROGRESS: [ProcessState.REVIEW_COMPLETED, ProcessState.FAILED],
            ProcessState.REVIEW_COMPLETED: [ProcessState.APPLYING_CHANGES, ProcessState.RETRY_PENDING],
            ProcessState.APPLYING_CHANGES: [ProcessState.COMPLETED, ProcessState.FAILED],
            ProcessState.FAILED: [ProcessState.RETRY_PENDING],
            ProcessState.RETRY_PENDING: [ProcessState.PENDING],
            ProcessState.COMPLETED: []
        }
        
        # Components
        self.result_manager = WorkerResultManager()
        self.review_system = EnhancedReviewSystem(self.result_manager)
        self.task_manager = TaskManager()
        self.prompt_system = EnhancedPromptSystem()
        self.comm_protocol = CommunicationProtocol()
        
        # State persistence
        self.state_file = Path(".taskmaster/lifecycle_states.json")
        self._load_states()
        
    def _load_states(self):
        """Load persisted states"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    for task_id, context_data in data.items():
                        self.contexts[task_id] = ProcessContext(
                            task_id=task_id,
                            task_data=context_data['task_data'],
                            state=ProcessState(context_data['state']),
                            worker_id=context_data.get('worker_id'),
                            retry_count=context_data.get('retry_count', 0),
                            created_at=datetime.fromisoformat(context_data['created_at']),
                            updated_at=datetime.fromisoformat(context_data['updated_at']),
                            error_messages=context_data.get('error_messages', [])
                        )
            except Exception as e:
                logger.error(f"Failed to load states: {e}")
                
    def _save_states(self):
        """Persist current states"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for task_id, context in self.contexts.items():
                data[task_id] = {
                    'task_data': context.task_data,
                    'state': context.state.value,
                    'worker_id': context.worker_id,
                    'retry_count': context.retry_count,
                    'created_at': context.created_at.isoformat(),
                    'updated_at': context.updated_at.isoformat(),
                    'error_messages': context.error_messages
                }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save states: {e}")
            
    async def initialize_task(self, task_id: str, task_data: Dict[str, Any]) -> ProcessContext:
        """Initialize a new task in the lifecycle"""
        context = ProcessContext(
            task_id=task_id,
            task_data=task_data,
            state=ProcessState.PENDING
        )
        
        self.contexts[task_id] = context
        self._save_states()
        
        logger.info(f"Initialized lifecycle for task {task_id}")
        return context
        
    async def transition_state(self, task_id: str, new_state: ProcessState) -> bool:
        """Transition task to a new state"""
        if task_id not in self.contexts:
            logger.error(f"Task {task_id} not found in lifecycle manager")
            return False
            
        context = self.contexts[task_id]
        current_state = context.state
        
        # Check if transition is valid
        if new_state not in self.state_transitions.get(current_state, []):
            logger.error(f"Invalid state transition for task {task_id}: {current_state} -> {new_state}")
            return False
            
        # Update state
        context.state = new_state
        context.updated_at = datetime.now()
        self._save_states()
        
        # Send state change notification
        await self.comm_protocol.send_message(
            sender_id=self.orchestrator_id,
            recipient_id="broadcast",
            message_type=MessageType.STATE_CHANGE,
            payload={
                'task_id': task_id,
                'old_state': current_state.value,
                'new_state': new_state.value,
                'timestamp': context.updated_at.isoformat()
            }
        )
        
        logger.info(f"Task {task_id} transitioned: {current_state} -> {new_state}")
        return True
        
    async def assign_worker(self, task_id: str, worker_id: str) -> bool:
        """Assign a worker to a task"""
        if task_id not in self.contexts:
            return False
            
        context = self.contexts[task_id]
        context.worker_id = worker_id
        
        # Generate enhanced prompt
        prompt = self.prompt_system.get_worker_prompt(
            context.task_data,
            context={
                'retry_count': context.retry_count,
                'previous_errors': context.error_messages[-3:] if context.error_messages else []
            }
        )
        
        # Save prompt to task file
        task_file = Path(f".taskmaster/tasks/task_{task_id}.json")
        task_file.parent.mkdir(parents=True, exist_ok=True)
        
        enhanced_task_data = context.task_data.copy()
        enhanced_task_data['enhanced_prompt'] = prompt
        enhanced_task_data['lifecycle_state'] = context.state.value
        enhanced_task_data['assigned_worker'] = worker_id
        
        with open(task_file, 'w') as f:
            json.dump(enhanced_task_data, f, indent=2)
            
        await self.transition_state(task_id, ProcessState.WORKER_ASSIGNED)
        return True
        
    async def handle_worker_completion(self, task_id: str, result: WorkerResult):
        """Handle worker completion and trigger review"""
        if task_id not in self.contexts:
            return
            
        context = self.contexts[task_id]
        context.worker_result = result
        
        # Store result
        self.result_manager.store_result(result)
        
        # Transition to review
        await self.transition_state(task_id, ProcessState.WORKER_COMPLETED)
        
        # Check if result needs immediate retry
        if result.status == ResultStatus.FAILED:
            await self._handle_failure(task_id, f"Worker failed: {result.error_message}")
        else:
            # Proceed to review
            await self.transition_state(task_id, ProcessState.REVIEW_PENDING)
            
    async def perform_review(self, task_id: str) -> Dict[str, Any]:
        """Perform review of worker output"""
        if task_id not in self.contexts:
            return {'success': False, 'message': 'Task not found'}
            
        context = self.contexts[task_id]
        
        await self.transition_state(task_id, ProcessState.REVIEW_IN_PROGRESS)
        
        # Perform review
        review_result = await self.review_system.review_task(task_id)
        context.review_result = review_result
        
        await self.transition_state(task_id, ProcessState.REVIEW_COMPLETED)
        
        if review_result['success']:
            # Apply changes
            await self.transition_state(task_id, ProcessState.APPLYING_CHANGES)
            # In practice, this would trigger the actual application
            await self.transition_state(task_id, ProcessState.COMPLETED)
        else:
            # Handle review failure
            await self._handle_failure(task_id, review_result['message'])
            
        return review_result
        
    async def _handle_failure(self, task_id: str, error_message: str):
        """Handle task failure with retry logic"""
        context = self.contexts[task_id]
        context.error_messages.append(error_message)
        
        if context.retry_count < context.max_retries:
            context.retry_count += 1
            logger.info(f"Retrying task {task_id} (attempt {context.retry_count}/{context.max_retries})")
            
            await self.transition_state(task_id, ProcessState.RETRY_PENDING)
            # Reset to pending for retry
            await self.transition_state(task_id, ProcessState.PENDING)
        else:
            logger.error(f"Task {task_id} failed after {context.max_retries} retries")
            await self.transition_state(task_id, ProcessState.FAILED)
            
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get comprehensive task status"""
        if task_id not in self.contexts:
            return {'found': False}
            
        context = self.contexts[task_id]
        
        status = {
            'found': True,
            'task_id': task_id,
            'state': context.state.value,
            'worker_id': context.worker_id,
            'retry_count': context.retry_count,
            'created_at': context.created_at.isoformat(),
            'updated_at': context.updated_at.isoformat(),
            'duration': (context.updated_at - context.created_at).total_seconds(),
            'has_result': context.worker_result is not None,
            'has_review': context.review_result is not None,
            'error_count': len(context.error_messages)
        }
        
        if context.worker_result:
            status['worker_result'] = {
                'status': context.worker_result.status.value,
                'files_created': len(context.worker_result.created_files),
                'files_modified': len(context.worker_result.modified_files),
                'validation_passed': context.worker_result.validation_passed
            }
            
        if context.review_result:
            status['review_result'] = {
                'success': context.review_result['success'],
                'message': context.review_result['message']
            }
            
        return status
        
    async def get_stuck_tasks(self, timeout_minutes: int = 30) -> List[str]:
        """Find tasks that might be stuck"""
        stuck_tasks = []
        timeout = timedelta(minutes=timeout_minutes)
        now = datetime.now()
        
        for task_id, context in self.contexts.items():
            if context.state in [ProcessState.COMPLETED, ProcessState.FAILED]:
                continue
                
            if now - context.updated_at > timeout:
                stuck_tasks.append(task_id)
                
        return stuck_tasks
        
    async def recover_stuck_tasks(self):
        """Attempt to recover stuck tasks"""
        stuck_tasks = await self.get_stuck_tasks()
        
        for task_id in stuck_tasks:
            logger.warning(f"Attempting to recover stuck task {task_id}")
            context = self.contexts[task_id]
            
            # Based on current state, attempt recovery
            if context.state in [ProcessState.WORKER_EXECUTING]:
                # Worker might have crashed
                await self._handle_failure(task_id, "Worker timeout - no response")
            elif context.state in [ProcessState.REVIEW_IN_PROGRESS]:
                # Review might have failed
                await self._handle_failure(task_id, "Review timeout")
            else:
                # Reset to pending
                context.state = ProcessState.PENDING
                
    def get_statistics(self) -> Dict[str, int]:
        """Get lifecycle statistics"""
        stats = {state: 0 for state in ProcessState}
        
        for context in self.contexts.values():
            stats[context.state] += 1
            
        return {state.value: count for state, count in stats.items() if count > 0}