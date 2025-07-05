"""Integration of feedback collection into existing decision points"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from enum import Enum

from .feedback_model import (
    FeedbackModel, FeedbackType, FeedbackSeverity, 
    FeedbackCategory, create_decision_feedback
)
from .feedback_storage import FeedbackStorage
from .interactive_feedback_ui import (
    InteractiveFeedbackUI, FeedbackRequest, FeedbackRequestType
)

logger = logging.getLogger(__name__)


class DecisionPoint(Enum):
    """Critical decision points in the orchestration process"""
    TASK_ASSIGNMENT = "task_assignment"
    WORKER_SELECTION = "worker_selection"
    ERROR_RECOVERY = "error_recovery"
    TASK_VALIDATION = "task_validation"
    PLAN_APPROVAL = "plan_approval"
    REVIEW_APPLICATION = "review_application"
    ROLLBACK_DECISION = "rollback_decision"
    RESOURCE_ALLOCATION = "resource_allocation"
    QUALITY_GATE = "quality_gate"
    COMPLETION_VERIFICATION = "completion_verification"


class FeedbackIntegration:
    """Integrates feedback collection into orchestrator decision points"""
    
    def __init__(self, orchestrator, feedback_storage: Optional[FeedbackStorage] = None):
        """Initialize feedback integration
        
        Args:
            orchestrator: The main orchestrator instance
            feedback_storage: Optional feedback storage instance
        """
        self.orchestrator = orchestrator
        self.feedback_storage = feedback_storage or FeedbackStorage()
        self.interactive_ui = None
        self.decision_callbacks: Dict[DecisionPoint, List[Callable]] = {}
        
        # Initialize interactive UI if configured
        if hasattr(orchestrator.config, 'interactive_feedback'):
            config = orchestrator.config.interactive_feedback
            if config.get('enabled', False):
                from .interactive_feedback_ui import get_feedback_ui
                self.interactive_ui = get_feedback_ui(
                    auto_mode=config.get('auto_mode', True)
                )
                if self.interactive_ui:
                    self.interactive_ui.start()
                    logger.info("Interactive feedback UI initialized")
        
        # Register default decision points
        self._register_default_handlers()
        
    def _register_default_handlers(self):
        """Register default feedback handlers for decision points"""
        # Task assignment decisions
        self.register_decision_handler(
            DecisionPoint.TASK_ASSIGNMENT,
            self._handle_task_assignment_feedback
        )
        
        # Worker selection decisions
        self.register_decision_handler(
            DecisionPoint.WORKER_SELECTION,
            self._handle_worker_selection_feedback
        )
        
        # Error recovery decisions
        self.register_decision_handler(
            DecisionPoint.ERROR_RECOVERY,
            self._handle_error_recovery_feedback
        )
        
        # Task validation decisions
        self.register_decision_handler(
            DecisionPoint.TASK_VALIDATION,
            self._handle_task_validation_feedback
        )
        
        # Plan approval decisions
        self.register_decision_handler(
            DecisionPoint.PLAN_APPROVAL,
            self._handle_plan_approval_feedback
        )
        
    def register_decision_handler(self, point: DecisionPoint, handler: Callable):
        """Register a feedback handler for a decision point
        
        Args:
            point: The decision point
            handler: Callback function to handle feedback collection
        """
        if point not in self.decision_callbacks:
            self.decision_callbacks[point] = []
        self.decision_callbacks[point].append(handler)
        
    def collect_feedback(self, 
                        point: DecisionPoint,
                        context: Dict[str, Any],
                        options: Optional[List[str]] = None,
                        priority: str = "medium") -> Optional[Any]:
        """Collect feedback at a decision point
        
        Args:
            point: The decision point
            context: Context information
            options: Optional list of choices
            priority: Priority level (low, medium, high)
            
        Returns:
            Decision result or None
        """
        # Create feedback model
        feedback = create_decision_feedback(
            decision_point=point.value,
            context=context,
            options=options,
            session_id=str(id(self.orchestrator))
        )
        
        # Store feedback request
        self.feedback_storage.save(feedback)
        
        # Execute registered handlers
        results = []
        for handler in self.decision_callbacks.get(point, []):
            try:
                result = handler(context, options, priority)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error in feedback handler for {point.value}: {e}")
                
        # If interactive UI is available and enabled, request user feedback
        if self.interactive_ui and self._should_request_interactive(point, priority):
            interactive_result = self._request_interactive_feedback(
                point, context, options, priority
            )
            if interactive_result is not None:
                results.append(interactive_result)
                
        # Return first non-None result
        return results[0] if results else None
        
    def _should_request_interactive(self, point: DecisionPoint, priority: str) -> bool:
        """Determine if interactive feedback should be requested
        
        Args:
            point: The decision point
            priority: Priority level
            
        Returns:
            True if interactive feedback should be requested
        """
        # Always request for high priority
        if priority == "high":
            return True
            
        # Check configuration for specific decision points
        if hasattr(self.orchestrator.config, 'interactive_feedback'):
            config = self.orchestrator.config.interactive_feedback
            decision_points = config.get('decision_points_enabled', True)
            
            # Check if this specific point is enabled
            if isinstance(decision_points, dict):
                return decision_points.get(point.value, True)
            else:
                return bool(decision_points)
                
        return False
        
    def _request_interactive_feedback(self,
                                    point: DecisionPoint,
                                    context: Dict[str, Any],
                                    options: Optional[List[str]],
                                    priority: str) -> Optional[Any]:
        """Request interactive feedback from user
        
        Args:
            point: The decision point
            context: Context information
            options: Optional list of choices
            priority: Priority level
            
        Returns:
            User decision or None
        """
        # Map decision point to request type
        request_type_map = {
            DecisionPoint.TASK_ASSIGNMENT: FeedbackRequestType.DECISION_POINT,
            DecisionPoint.WORKER_SELECTION: FeedbackRequestType.DECISION_POINT,
            DecisionPoint.ERROR_RECOVERY: FeedbackRequestType.ERROR_RESOLUTION,
            DecisionPoint.TASK_VALIDATION: FeedbackRequestType.TASK_REVIEW,
            DecisionPoint.PLAN_APPROVAL: FeedbackRequestType.DECISION_POINT,
            DecisionPoint.REVIEW_APPLICATION: FeedbackRequestType.TASK_REVIEW,
            DecisionPoint.ROLLBACK_DECISION: FeedbackRequestType.INTERVENTION,
            DecisionPoint.QUALITY_GATE: FeedbackRequestType.QUALITY_ASSESSMENT,
        }
        
        request_type = request_type_map.get(point, FeedbackRequestType.DECISION_POINT)
        
        # Create feedback request
        request = FeedbackRequest(
            request_id=f"{point.value}_{datetime.now().timestamp()}",
            request_type=request_type,
            title=f"Decision Required: {point.value.replace('_', ' ').title()}",
            description=self._format_decision_description(point, context),
            context=context,
            options=options,
            priority=priority
        )
        
        # Request feedback
        response = self.interactive_ui.request_feedback(request)
        
        if response:
            # Store the response
            response_feedback = create_decision_feedback(
                decision_point=point.value,
                context=context,
                decision=response.value,
                response_time=response.duration_seconds,
                session_id=str(id(self.orchestrator))
            )
            self.feedback_storage.save(response_feedback)
            
            return response.value
            
        return None
        
    def _format_decision_description(self, point: DecisionPoint, context: Dict[str, Any]) -> str:
        """Format a human-readable description for the decision point
        
        Args:
            point: The decision point
            context: Context information
            
        Returns:
            Formatted description
        """
        descriptions = {
            DecisionPoint.TASK_ASSIGNMENT: "A task needs to be assigned to a worker.",
            DecisionPoint.WORKER_SELECTION: "Select the best worker for this task.",
            DecisionPoint.ERROR_RECOVERY: "An error occurred and recovery action is needed.",
            DecisionPoint.TASK_VALIDATION: "Validate if the task output meets requirements.",
            DecisionPoint.PLAN_APPROVAL: "Review and approve the execution plan.",
            DecisionPoint.REVIEW_APPLICATION: "Apply the review feedback to the task.",
            DecisionPoint.ROLLBACK_DECISION: "Decide whether to rollback changes.",
            DecisionPoint.RESOURCE_ALLOCATION: "Allocate resources for task execution.",
            DecisionPoint.QUALITY_GATE: "Assess if quality standards are met.",
            DecisionPoint.COMPLETION_VERIFICATION: "Verify task completion status."
        }
        
        base_desc = descriptions.get(point, "A decision is required.")
        
        # Add context-specific details
        if 'task_id' in context:
            base_desc += f"\n\nTask ID: {context['task_id']}"
        if 'task_title' in context:
            base_desc += f"\nTask: {context['task_title']}"
        if 'error' in context:
            base_desc += f"\nError: {context['error']}"
            
        return base_desc
        
    # Default feedback handlers
    
    def _handle_task_assignment_feedback(self, context: Dict[str, Any], 
                                       options: Optional[List[str]], 
                                       priority: str) -> Optional[Any]:
        """Handle task assignment feedback"""
        # Log the decision point
        logger.info(f"Task assignment decision for task {context.get('task_id')}")
        
        # Could implement automatic assignment logic here
        # For now, return None to allow interactive feedback
        return None
        
    def _handle_worker_selection_feedback(self, context: Dict[str, Any],
                                        options: Optional[List[str]],
                                        priority: str) -> Optional[Any]:
        """Handle worker selection feedback"""
        # Log available workers
        workers = context.get('available_workers', [])
        logger.info(f"Worker selection: {len(workers)} workers available")
        
        # Could implement automatic selection based on performance metrics
        return None
        
    def _handle_error_recovery_feedback(self, context: Dict[str, Any],
                                      options: Optional[List[str]],
                                      priority: str) -> Optional[Any]:
        """Handle error recovery feedback"""
        error = context.get('error', {})
        retry_count = context.get('retry_count', 0)
        
        # Auto-retry for certain errors
        if retry_count < 3 and error.get('type') == 'timeout':
            logger.info("Auto-retrying after timeout error")
            return "retry"
            
        # For other errors, request user input
        return None
        
    def _handle_task_validation_feedback(self, context: Dict[str, Any],
                                       options: Optional[List[str]],
                                       priority: str) -> Optional[Any]:
        """Handle task validation feedback"""
        # Could implement automatic validation based on patterns
        output = context.get('output', '')
        
        # Simple auto-validation for test outputs
        if 'test' in context.get('task_type', '').lower():
            if 'passed' in output.lower() and 'failed' not in output.lower():
                logger.info("Auto-approving test task with passing output")
                return {"approved": True}
                
        return None
        
    def _handle_plan_approval_feedback(self, context: Dict[str, Any],
                                     options: Optional[List[str]],
                                     priority: str) -> Optional[Any]:
        """Handle plan approval feedback"""
        plan = context.get('plan', {})
        task_count = len(plan.get('tasks', []))
        
        # Auto-approve small plans in auto mode
        if hasattr(self.orchestrator.config, 'interactive_feedback'):
            if self.orchestrator.config.interactive_feedback.get('auto_mode'):
                if task_count <= 5:
                    logger.info(f"Auto-approving small plan with {task_count} tasks")
                    return "approve"
                    
        return None
        
    def integrate_with_orchestrator(self):
        """Integrate feedback collection hooks into the orchestrator"""
        # Hook into task assignment
        if hasattr(self.orchestrator.manager, 'assign_task'):
            original_assign = self.orchestrator.manager.assign_task
            
            def wrapped_assign(task, worker):
                # Collect feedback before assignment
                context = {
                    'task_id': task.task_id,
                    'task_title': task.title,
                    'worker_id': worker.worker_id,
                    'worker_load': len(worker.active_tasks)
                }
                
                decision = self.collect_feedback(
                    DecisionPoint.TASK_ASSIGNMENT,
                    context,
                    priority="low"
                )
                
                # Apply decision if provided
                if decision == "skip":
                    logger.info(f"Skipping task assignment based on feedback")
                    return None
                    
                return original_assign(task, worker)
                
            self.orchestrator.manager.assign_task = wrapped_assign
            
        # Hook into error handling
        if hasattr(self.orchestrator, 'handle_worker_error'):
            original_error_handler = self.orchestrator.handle_worker_error
            
            def wrapped_error_handler(worker, error):
                # Collect feedback for error recovery
                context = {
                    'worker_id': worker.worker_id,
                    'error': {
                        'type': type(error).__name__,
                        'message': str(error)
                    },
                    'retry_count': getattr(worker, 'retry_count', 0)
                }
                
                decision = self.collect_feedback(
                    DecisionPoint.ERROR_RECOVERY,
                    context,
                    options=["retry", "skip", "abort"],
                    priority="high"
                )
                
                if decision == "abort":
                    raise error
                elif decision == "skip":
                    return None
                    
                return original_error_handler(worker, error)
                
            self.orchestrator.handle_worker_error = wrapped_error_handler
            
        logger.info("Feedback collection integrated with orchestrator")
        
    def shutdown(self):
        """Shutdown feedback integration"""
        if self.interactive_ui:
            self.interactive_ui.stop()
            

def integrate_feedback_collection(orchestrator) -> FeedbackIntegration:
    """Create and integrate feedback collection
    
    Args:
        orchestrator: The orchestrator instance
        
    Returns:
        FeedbackIntegration instance
    """
    integration = FeedbackIntegration(orchestrator)
    integration.integrate_with_orchestrator()
    return integration