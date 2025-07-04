"""
Feedback Collection Module for Claude Orchestrator

This module handles feedback collection at various decision points in the orchestrator.
It provides prompts, validation, and collection handlers for gathering structured feedback.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Union
from enum import Enum
from dataclasses import dataclass
import asyncio
import json

from .feedback_models import (
    FeedbackEntry, FeedbackType, RatingScale, FeedbackMetadata,
    create_feedback_entry, validate_rating
)
from .feedback_storage import FeedbackStorage, create_feedback_storage


logger = logging.getLogger(__name__)


class CollectionPoint(Enum):
    """Points in the workflow where feedback can be collected"""
    TASK_START = "task_start"
    TASK_COMPLETION = "task_completion" 
    TASK_FAILURE = "task_failure"
    WORKER_ALLOCATION = "worker_allocation"
    WORKER_RELEASE = "worker_release"
    REVIEW_COMPLETION = "review_completion"
    ERROR_OCCURRENCE = "error_occurrence"
    MANUAL_FEEDBACK = "manual_feedback"


class FeedbackPrompt:
    """Represents a feedback prompt configuration"""
    
    def __init__(
        self,
        prompt_text: str,
        feedback_type: FeedbackType,
        requires_rating: bool = False,
        rating_scale_description: str = "1=Poor, 2=Fair, 3=Good, 4=Very Good, 5=Excellent",
        max_content_length: int = 500,
        validation_rules: Optional[Dict[str, Any]] = None
    ):
        self.prompt_text = prompt_text
        self.feedback_type = feedback_type
        self.requires_rating = requires_rating
        self.rating_scale_description = rating_scale_description
        self.max_content_length = max_content_length
        self.validation_rules = validation_rules or {}


@dataclass
class FeedbackRequest:
    """Represents a request for feedback collection"""
    task_id: str
    collection_point: CollectionPoint
    prompt: FeedbackPrompt
    context: Dict[str, Any]
    user_id: Optional[str] = None
    timeout_seconds: int = 300  # 5 minutes default
    

class FeedbackValidationError(Exception):
    """Raised when feedback validation fails"""
    pass


class FeedbackCollector:
    """
    Core feedback collection module
    
    Handles feedback collection at various decision points in the orchestrator,
    providing prompts, validation, and storage coordination.
    """
    
    def __init__(self, storage: Optional[FeedbackStorage] = None):
        """
        Initialize feedback collector
        
        Args:
            storage: Optional FeedbackStorage instance. If None, creates default storage.
        """
        self.storage = storage or create_feedback_storage()
        self._prompts = self._initialize_default_prompts()
        self._collection_handlers: Dict[CollectionPoint, List[Callable]] = {}
        self._active_requests: Dict[str, FeedbackRequest] = {}
        
        logger.info("Initialized FeedbackCollector")
    
    def _initialize_default_prompts(self) -> Dict[CollectionPoint, FeedbackPrompt]:
        """Initialize default feedback prompts for each collection point"""
        return {
            CollectionPoint.TASK_COMPLETION: FeedbackPrompt(
                prompt_text="How would you rate the completion of this task? Please provide feedback on quality, efficiency, and any issues encountered.",
                feedback_type=FeedbackType.TASK_COMPLETION,
                requires_rating=True
            ),
            CollectionPoint.TASK_FAILURE: FeedbackPrompt(
                prompt_text="This task failed to complete. Please describe what went wrong and suggest improvements.",
                feedback_type=FeedbackType.ERROR_REPORT,
                requires_rating=False
            ),
            CollectionPoint.WORKER_ALLOCATION: FeedbackPrompt(
                prompt_text="How appropriate was the worker allocation for this task?",
                feedback_type=FeedbackType.WORKER_PERFORMANCE,
                requires_rating=True
            ),
            CollectionPoint.WORKER_RELEASE: FeedbackPrompt(
                prompt_text="Please rate the worker's performance on this task and provide any relevant feedback.",
                feedback_type=FeedbackType.WORKER_PERFORMANCE,
                requires_rating=True
            ),
            CollectionPoint.REVIEW_COMPLETION: FeedbackPrompt(
                prompt_text="Please provide feedback on the review process and quality.",
                feedback_type=FeedbackType.MANAGER_REVIEW,
                requires_rating=True
            ),
            CollectionPoint.ERROR_OCCURRENCE: FeedbackPrompt(
                prompt_text="An error occurred. Please describe the issue and suggest how it could be prevented.",
                feedback_type=FeedbackType.ERROR_REPORT,
                requires_rating=False
            ),
            CollectionPoint.MANUAL_FEEDBACK: FeedbackPrompt(
                prompt_text="Please provide your feedback and rating.",
                feedback_type=FeedbackType.USER_RATING,
                requires_rating=False
            )
        }
    
    def register_collection_handler(
        self, 
        collection_point: CollectionPoint, 
        handler: Callable[[FeedbackRequest, FeedbackEntry], None]
    ):
        """
        Register a handler for feedback collection at a specific point
        
        Args:
            collection_point: The point where feedback is collected
            handler: Function to call when feedback is collected
        """
        if collection_point not in self._collection_handlers:
            self._collection_handlers[collection_point] = []
        self._collection_handlers[collection_point].append(handler)
        logger.info(f"Registered handler for {collection_point.value}")
    
    def set_prompt(self, collection_point: CollectionPoint, prompt: FeedbackPrompt):
        """
        Set custom prompt for a collection point
        
        Args:
            collection_point: The collection point
            prompt: Custom prompt configuration
        """
        self._prompts[collection_point] = prompt
        logger.info(f"Set custom prompt for {collection_point.value}")
    
    def collect_feedback(
        self,
        task_id: str,
        collection_point: CollectionPoint,
        content: str,
        rating: Optional[Union[int, RatingScale]] = None,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> FeedbackEntry:
        """
        Collect feedback at a specific collection point
        
        Args:
            task_id: ID of the task this feedback relates to
            collection_point: Where the feedback is being collected
            content: Feedback content
            rating: Optional rating (1-5 or RatingScale enum)
            user_id: Optional user providing feedback
            context: Additional context information
            
        Returns:
            FeedbackEntry: The created feedback entry
            
        Raises:
            FeedbackValidationError: If validation fails
        """
        prompt = self._prompts.get(collection_point)
        if not prompt:
            raise FeedbackValidationError(f"No prompt configured for {collection_point.value}")
        
        # Validate content
        self._validate_content(content, prompt)
        
        # Validate rating if required
        rating_enum = None
        if rating is not None:
            if isinstance(rating, int):
                rating_enum = validate_rating(rating)
            elif isinstance(rating, RatingScale):
                rating_enum = rating
            else:
                raise FeedbackValidationError(f"Invalid rating type: {type(rating)}")
        elif prompt.requires_rating:
            raise FeedbackValidationError(f"Rating is required for {collection_point.value}")
        
        # Create metadata with collection context
        metadata = FeedbackMetadata(
            source="feedback_collector",
            version="1.0.0",
            context={
                "collection_point": collection_point.value,
                "timestamp": datetime.now().isoformat(),
                **(context or {})
            },
            tags=[collection_point.value]
        )
        
        # Create feedback entry
        feedback_entry = create_feedback_entry(
            task_id=task_id,
            feedback_type=prompt.feedback_type,
            content=content,
            rating=rating_enum,
            user_id=user_id
        )
        feedback_entry.metadata = metadata
        
        # Store in database
        try:
            self.storage.create_feedback(feedback_entry)
            logger.info(f"Collected feedback at {collection_point.value} for task {task_id}")
        except Exception as e:
            logger.error(f"Failed to store feedback: {e}")
            raise FeedbackValidationError(f"Failed to store feedback: {e}")
        
        # Call registered handlers
        self._notify_handlers(collection_point, feedback_entry)
        
        return feedback_entry
    
    def collect_task_completion_feedback(
        self,
        task_id: str,
        success: bool,
        execution_time: float,
        worker_id: Optional[str] = None,
        errors: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> FeedbackEntry:
        """
        Convenience method for collecting task completion feedback
        
        Args:
            task_id: ID of the completed task
            success: Whether the task completed successfully
            execution_time: Time taken to execute the task
            worker_id: ID of the worker that executed the task
            errors: List of errors encountered (if any)
            user_id: Optional user providing feedback
            
        Returns:
            FeedbackEntry: The created feedback entry
        """
        # Generate automatic feedback content
        status = "successfully" if success else "with failures"
        content = f"Task completed {status} in {execution_time:.2f} seconds"
        
        if worker_id:
            content += f" by worker {worker_id}"
        
        if errors:
            content += f". Errors encountered: {'; '.join(errors)}"
        
        # Determine rating based on success and execution time
        if success:
            if execution_time < 30:  # Fast execution
                rating = RatingScale.EXCELLENT
            elif execution_time < 120:  # Reasonable time
                rating = RatingScale.GOOD
            else:  # Slow but successful
                rating = RatingScale.FAIR
        else:
            rating = RatingScale.POOR
        
        context = {
            "success": success,
            "execution_time": execution_time,
            "worker_id": worker_id,
            "errors": errors or [],
            "auto_generated": True
        }
        
        return self.collect_feedback(
            task_id=task_id,
            collection_point=CollectionPoint.TASK_COMPLETION,
            content=content,
            rating=rating,
            user_id=user_id,
            context=context
        )
    
    def collect_worker_performance_feedback(
        self,
        task_id: str,
        worker_id: str,
        performance_score: float,
        issues: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> FeedbackEntry:
        """
        Convenience method for collecting worker performance feedback
        
        Args:
            task_id: ID of the task
            worker_id: ID of the worker
            performance_score: Performance score (0.0 - 1.0)
            issues: List of performance issues
            user_id: Optional user providing feedback
            
        Returns:
            FeedbackEntry: The created feedback entry
        """
        content = f"Worker {worker_id} performance score: {performance_score:.2f}"
        
        if issues:
            content += f". Issues: {'; '.join(issues)}"
        
        # Convert performance score to rating
        if performance_score >= 0.9:
            rating = RatingScale.EXCELLENT
        elif performance_score >= 0.7:
            rating = RatingScale.VERY_GOOD
        elif performance_score >= 0.5:
            rating = RatingScale.GOOD
        elif performance_score >= 0.3:
            rating = RatingScale.FAIR
        else:
            rating = RatingScale.POOR
        
        context = {
            "worker_id": worker_id,
            "performance_score": performance_score,
            "issues": issues or [],
            "auto_generated": True
        }
        
        return self.collect_feedback(
            task_id=task_id,
            collection_point=CollectionPoint.WORKER_RELEASE,
            content=content,
            rating=rating,
            user_id=user_id,
            context=context
        )
    
    def collect_error_feedback(
        self,
        task_id: str,
        error_message: str,
        error_type: str,
        stack_trace: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> FeedbackEntry:
        """
        Convenience method for collecting error feedback
        
        Args:
            task_id: ID of the task where error occurred
            error_message: Error message
            error_type: Type of error
            stack_trace: Optional stack trace
            user_id: Optional user providing feedback
            
        Returns:
            FeedbackEntry: The created feedback entry
        """
        content = f"Error: {error_type} - {error_message}"
        
        if stack_trace:
            content += f"\n\nStack trace:\n{stack_trace}"
        
        context = {
            "error_type": error_type,
            "error_message": error_message,
            "stack_trace": stack_trace,
            "auto_generated": True
        }
        
        return self.collect_feedback(
            task_id=task_id,
            collection_point=CollectionPoint.ERROR_OCCURRENCE,
            content=content,
            rating=None,
            user_id=user_id,
            context=context
        )
    
    def get_feedback_prompt(self, collection_point: CollectionPoint) -> Optional[FeedbackPrompt]:
        """
        Get the feedback prompt for a collection point
        
        Args:
            collection_point: The collection point
            
        Returns:
            FeedbackPrompt or None if not configured
        """
        return self._prompts.get(collection_point)
    
    def get_task_feedback(self, task_id: str) -> List[FeedbackEntry]:
        """
        Get all feedback for a specific task
        
        Args:
            task_id: ID of the task
            
        Returns:
            List of FeedbackEntry objects
        """
        return self.storage.get_feedback_by_task(task_id)
    
    def get_feedback_summary(self, task_id: str):
        """
        Get feedback summary for a task
        
        Args:
            task_id: ID of the task
            
        Returns:
            FeedbackSummary object
        """
        return self.storage.get_feedback_summary(task_id)
    
    def _validate_content(self, content: str, prompt: FeedbackPrompt):
        """Validate feedback content against prompt requirements"""
        if not content or not content.strip():
            raise FeedbackValidationError("Feedback content cannot be empty")
        
        if len(content) > prompt.max_content_length:
            raise FeedbackValidationError(
                f"Feedback content too long: {len(content)} > {prompt.max_content_length}"
            )
        
        # Apply custom validation rules
        for rule_name, rule_value in prompt.validation_rules.items():
            if rule_name == "min_length" and len(content) < rule_value:
                raise FeedbackValidationError(f"Content too short: minimum {rule_value} characters")
            elif rule_name == "required_keywords":
                missing_keywords = [kw for kw in rule_value if kw.lower() not in content.lower()]
                if missing_keywords:
                    raise FeedbackValidationError(f"Missing required keywords: {missing_keywords}")
    
    def _notify_handlers(self, collection_point: CollectionPoint, feedback_entry: FeedbackEntry):
        """Notify registered handlers about collected feedback"""
        handlers = self._collection_handlers.get(collection_point, [])
        for handler in handlers:
            try:
                # Create a mock request for the handler
                request = FeedbackRequest(
                    task_id=feedback_entry.task_id,
                    collection_point=collection_point,
                    prompt=self._prompts[collection_point],
                    context=feedback_entry.metadata.context if feedback_entry.metadata else {}
                )
                handler(request, feedback_entry)
            except Exception as e:
                logger.error(f"Handler error for {collection_point.value}: {e}")
    
    def close(self):
        """Close the feedback collector and its storage"""
        if self.storage:
            self.storage.close()
        logger.info("Closed FeedbackCollector")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Convenience functions for common feedback collection scenarios

def collect_task_feedback(
    task_id: str,
    success: bool,
    execution_time: float,
    worker_id: Optional[str] = None,
    errors: Optional[List[str]] = None,
    storage: Optional[FeedbackStorage] = None
) -> FeedbackEntry:
    """
    Quick function to collect task completion feedback
    
    Args:
        task_id: ID of the task
        success: Whether task was successful
        execution_time: Time taken to execute
        worker_id: Optional worker ID
        errors: Optional list of errors
        storage: Optional storage instance
        
    Returns:
        FeedbackEntry: Created feedback entry
    """
    with FeedbackCollector(storage) as collector:
        return collector.collect_task_completion_feedback(
            task_id=task_id,
            success=success,
            execution_time=execution_time,
            worker_id=worker_id,
            errors=errors
        )


def collect_worker_feedback(
    task_id: str,
    worker_id: str,
    performance_score: float,
    issues: Optional[List[str]] = None,
    storage: Optional[FeedbackStorage] = None
) -> FeedbackEntry:
    """
    Quick function to collect worker performance feedback
    
    Args:
        task_id: ID of the task
        worker_id: ID of the worker
        performance_score: Performance score (0.0-1.0)
        issues: Optional list of issues
        storage: Optional storage instance
        
    Returns:
        FeedbackEntry: Created feedback entry
    """
    with FeedbackCollector(storage) as collector:
        return collector.collect_worker_performance_feedback(
            task_id=task_id,
            worker_id=worker_id,
            performance_score=performance_score,
            issues=issues
        )


def collect_error_feedback(
    task_id: str,
    error_message: str,
    error_type: str,
    stack_trace: Optional[str] = None,
    storage: Optional[FeedbackStorage] = None
) -> FeedbackEntry:
    """
    Quick function to collect error feedback
    
    Args:
        task_id: ID of the task
        error_message: Error message
        error_type: Type of error
        stack_trace: Optional stack trace
        storage: Optional storage instance
        
    Returns:
        FeedbackEntry: Created feedback entry
    """
    with FeedbackCollector(storage) as collector:
        return collector.collect_error_feedback(
            task_id=task_id,
            error_message=error_message,
            error_type=error_type,
            stack_trace=stack_trace
        )