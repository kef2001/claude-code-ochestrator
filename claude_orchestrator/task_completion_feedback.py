"""
Task Completion Feedback Integration

This module extends the task completion workflow with comprehensive feedback collection.
It provides non-blocking feedback collection at task completion points.
"""

import logging
from typing import Optional, Dict, Any, List, Callable, Union
from datetime import datetime
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import threading
import json

from .feedback_collector import (
    FeedbackCollector, CollectionPoint, FeedbackPrompt,
    FeedbackValidationError
)
from .feedback_models import FeedbackType, RatingScale, FeedbackEntry
from .feedback_storage import FeedbackStorage


logger = logging.getLogger(__name__)


@dataclass
class TaskCompletionMetrics:
    """Metrics for task completion assessment"""
    task_id: str
    success: bool
    execution_time: float  # Total execution time in minutes
    error_count: int = 0
    retry_count: int = 0
    worker_changes: int = 0  # Number of times worker was changed
    subtask_count: int = 0
    subtasks_completed: int = 0
    code_changes_made: bool = False
    tests_passed: Optional[bool] = None
    review_required: bool = False
    review_score: Optional[float] = None  # Review score if reviewed
    quality_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class TaskResult:
    """Result of a completed task"""
    task_id: str
    title: str
    description: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    worker_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskCompletionFeedbackCollector:
    """
    Feedback collector for task completion workflow
    
    Integrates with the orchestrator to collect comprehensive feedback
    when tasks are completed, including success metrics, quality assessments,
    and automatic rating generation.
    """
    
    def __init__(
        self,
        feedback_collector: Optional[FeedbackCollector] = None,
        enable_async_collection: bool = True
    ):
        """
        Initialize task completion feedback collector
        
        Args:
            feedback_collector: FeedbackCollector instance (creates new if None)
            enable_async_collection: Whether to collect feedback asynchronously
        """
        self.feedback_collector = feedback_collector or FeedbackCollector()
        self.enable_async_collection = enable_async_collection
        
        # Thread pool for async feedback collection
        self._thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="completion_feedback")
        
        # Feedback collection settings
        self._feedback_enabled = True
        self._collection_callbacks: List[Callable[[str, FeedbackEntry], None]] = []
        
        # Task tracking for comprehensive feedback
        self._task_tracking: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        
        # Setup custom prompts for task completion
        self._setup_completion_prompts()
        
        logger.info("Initialized TaskCompletionFeedbackCollector")
    
    def _setup_completion_prompts(self):
        """Setup custom feedback prompts for task completion workflow"""
        
        # Task success feedback
        success_prompt = FeedbackPrompt(
            prompt_text="Rate the overall quality of this task completion. Consider correctness, efficiency, and code quality.",
            feedback_type=FeedbackType.TASK_COMPLETION,
            requires_rating=True,
            validation_rules={"min_length": 20}
        )
        
        # Task failure feedback
        failure_prompt = FeedbackPrompt(
            prompt_text="This task failed. Describe what went wrong and suggest improvements.",
            feedback_type=FeedbackType.ERROR_REPORT,
            requires_rating=False,
            validation_rules={"min_length": 30}
        )
        
        # Manager review feedback
        review_prompt = FeedbackPrompt(
            prompt_text="Rate the quality of the Opus manager's review and guidance.",
            feedback_type=FeedbackType.MANAGER_REVIEW,
            requires_rating=True
        )
        
        # Set custom collection points
        self.feedback_collector.set_prompt(CollectionPoint.TASK_COMPLETION, success_prompt)
        self.feedback_collector.set_prompt(CollectionPoint.TASK_FAILURE, failure_prompt)
        self.feedback_collector.set_prompt(CollectionPoint.REVIEW_COMPLETION, review_prompt)
    
    def start_task_tracking(
        self,
        task_id: str,
        title: str,
        description: str,
        worker_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Start tracking a task for comprehensive feedback collection
        
        Args:
            task_id: Task identifier
            title: Task title
            description: Task description
            worker_id: Initial worker assigned
            metadata: Additional task metadata
        """
        with self._lock:
            self._task_tracking[task_id] = {
                "title": title,
                "description": description,
                "start_time": datetime.now(),
                "worker_id": worker_id,
                "worker_changes": [],
                "errors": [],
                "retries": 0,
                "metadata": metadata or {}
            }
        
        logger.info(f"Started tracking task {task_id} for completion feedback")
    
    def update_task_tracking(
        self,
        task_id: str,
        update_type: str,
        data: Any
    ):
        """
        Update task tracking information
        
        Args:
            task_id: Task identifier
            update_type: Type of update (error, retry, worker_change, etc.)
            data: Update data
        """
        with self._lock:
            if task_id not in self._task_tracking:
                logger.warning(f"Task {task_id} not being tracked, starting tracking now")
                self._task_tracking[task_id] = {
                    "start_time": datetime.now(),
                    "errors": [],
                    "retries": 0,
                    "worker_changes": []
                }
            
            tracking = self._task_tracking[task_id]
            
            if update_type == "error":
                tracking["errors"].append({
                    "timestamp": datetime.now(),
                    "error": str(data)
                })
            elif update_type == "retry":
                tracking["retries"] += 1
            elif update_type == "worker_change":
                tracking["worker_changes"].append({
                    "timestamp": datetime.now(),
                    "from_worker": tracking.get("worker_id"),
                    "to_worker": data
                })
                tracking["worker_id"] = data
            elif update_type == "subtask_count":
                tracking["subtask_count"] = data
            elif update_type == "subtasks_completed":
                tracking["subtasks_completed"] = data
            elif update_type == "review_score":
                tracking["review_score"] = data
    
    def collect_task_completion_feedback(
        self,
        task_result: TaskResult,
        metrics: Optional[TaskCompletionMetrics] = None,
        user_id: Optional[str] = None
    ) -> Optional[FeedbackEntry]:
        """
        Collect comprehensive feedback for task completion
        
        Args:
            task_result: Result of the completed task
            metrics: Optional detailed metrics
            user_id: User who executed/managed the task
            
        Returns:
            FeedbackEntry if successful, None if collection disabled
        """
        if not self._feedback_enabled:
            return None
        
        logger.info(f"Collecting completion feedback for task {task_result.task_id}")
        
        # Get tracking information
        tracking_info = None
        with self._lock:
            tracking_info = self._task_tracking.pop(task_result.task_id, None)
        
        # Calculate metrics if not provided
        if not metrics and tracking_info:
            metrics = self._calculate_metrics_from_tracking(
                task_result, tracking_info
            )
        
        try:
            if task_result.success:
                feedback_entry = self._collect_success_feedback(
                    task_result, metrics, tracking_info, user_id
                )
            else:
                feedback_entry = self._collect_failure_feedback(
                    task_result, metrics, tracking_info, user_id
                )
            
            # Notify callbacks
            if feedback_entry:
                for callback in self._collection_callbacks:
                    try:
                        callback(task_result.task_id, feedback_entry)
                    except Exception as e:
                        logger.error(f"Callback error for task {task_result.task_id}: {e}")
            
            return feedback_entry
            
        except Exception as e:
            logger.error(f"Failed to collect completion feedback for task {task_result.task_id}: {e}")
            return None
    
    def _calculate_metrics_from_tracking(
        self,
        task_result: TaskResult,
        tracking_info: Dict[str, Any]
    ) -> TaskCompletionMetrics:
        """Calculate completion metrics from tracking information"""
        
        start_time = tracking_info.get("start_time", datetime.now())
        execution_time = (datetime.now() - start_time).total_seconds() / 60.0
        
        return TaskCompletionMetrics(
            task_id=task_result.task_id,
            success=task_result.success,
            execution_time=execution_time,
            error_count=len(tracking_info.get("errors", [])),
            retry_count=tracking_info.get("retries", 0),
            worker_changes=len(tracking_info.get("worker_changes", [])),
            subtask_count=tracking_info.get("subtask_count", 0),
            subtasks_completed=tracking_info.get("subtasks_completed", 0),
            review_score=tracking_info.get("review_score"),
            quality_metrics=task_result.metadata.get("quality_metrics", {})
        )
    
    def _collect_success_feedback(
        self,
        task_result: TaskResult,
        metrics: Optional[TaskCompletionMetrics],
        tracking_info: Optional[Dict[str, Any]],
        user_id: Optional[str]
    ) -> Optional[FeedbackEntry]:
        """Collect feedback for successful task completion"""
        
        # Generate success feedback content
        content = self._generate_success_feedback_content(
            task_result, metrics, tracking_info
        )
        
        # Assess quality rating
        rating = self._assess_success_rating(task_result, metrics)
        
        # Prepare context
        context = {
            "success": True,
            "execution_time": metrics.execution_time if metrics else None,
            "error_count": metrics.error_count if metrics else 0,
            "retry_count": metrics.retry_count if metrics else 0,
            "worker_id": task_result.worker_id,
            "auto_generated": True
        }
        
        if metrics:
            context.update({
                "worker_changes": metrics.worker_changes,
                "subtask_completion_rate": (
                    metrics.subtasks_completed / metrics.subtask_count 
                    if metrics.subtask_count > 0 else 1.0
                ),
                "review_score": metrics.review_score,
                "quality_metrics": metrics.quality_metrics
            })
        
        collection_point = CollectionPoint.TASK_COMPLETION
        
        if self.enable_async_collection:
            self._thread_pool.submit(
                self._collect_feedback_async,
                task_result.task_id,
                collection_point,
                content,
                rating,
                user_id,
                context
            )
            return None  # Async collection doesn't return immediately
        else:
            return self._collect_feedback_sync(
                task_result.task_id,
                collection_point,
                content,
                rating,
                user_id,
                context
            )
    
    def _collect_failure_feedback(
        self,
        task_result: TaskResult,
        metrics: Optional[TaskCompletionMetrics],
        tracking_info: Optional[Dict[str, Any]],
        user_id: Optional[str]
    ) -> Optional[FeedbackEntry]:
        """Collect feedback for failed task"""
        
        # Generate failure feedback content
        content = self._generate_failure_feedback_content(
            task_result, metrics, tracking_info
        )
        
        # Prepare context
        context = {
            "success": False,
            "execution_time": metrics.execution_time if metrics else None,
            "error_count": metrics.error_count if metrics else 0,
            "retry_count": metrics.retry_count if metrics else 0,
            "worker_id": task_result.worker_id,
            "error_message": task_result.error,
            "auto_generated": True
        }
        
        if tracking_info:
            # Add error history
            context["error_history"] = tracking_info.get("errors", [])
            context["worker_changes"] = tracking_info.get("worker_changes", [])
        
        collection_point = CollectionPoint.TASK_FAILURE
        
        if self.enable_async_collection:
            self._thread_pool.submit(
                self._collect_feedback_async,
                task_result.task_id,
                collection_point,
                content,
                None,  # No rating for failures
                user_id,
                context
            )
            return None
        else:
            return self._collect_feedback_sync(
                task_result.task_id,
                collection_point,
                content,
                None,
                user_id,
                context
            )
    
    def _generate_success_feedback_content(
        self,
        task_result: TaskResult,
        metrics: Optional[TaskCompletionMetrics],
        tracking_info: Optional[Dict[str, Any]]
    ) -> str:
        """Generate descriptive content for successful task completion"""
        
        content_parts = [
            f"Task '{task_result.title}' completed successfully"
        ]
        
        if metrics:
            content_parts.append(f"in {metrics.execution_time:.1f} minutes")
            
            if metrics.error_count > 0:
                content_parts.append(f"after {metrics.error_count} errors")
            
            if metrics.retry_count > 0:
                content_parts.append(f"with {metrics.retry_count} retries")
            
            if metrics.worker_changes > 0:
                content_parts.append(f"requiring {metrics.worker_changes} worker changes")
            
            if metrics.subtask_count > 0:
                completion_rate = metrics.subtasks_completed / metrics.subtask_count
                content_parts.append(f"Subtask completion: {metrics.subtasks_completed}/{metrics.subtask_count} ({completion_rate:.0%})")
            
            if metrics.review_score is not None:
                content_parts.append(f"Review score: {metrics.review_score:.1f}/5")
        
        return ". ".join(content_parts)
    
    def _generate_failure_feedback_content(
        self,
        task_result: TaskResult,
        metrics: Optional[TaskCompletionMetrics],
        tracking_info: Optional[Dict[str, Any]]
    ) -> str:
        """Generate descriptive content for failed task"""
        
        content_parts = [
            f"Task '{task_result.title}' failed"
        ]
        
        if task_result.error:
            content_parts.append(f"Error: {task_result.error[:100]}")
        
        if metrics:
            content_parts.append(f"after {metrics.execution_time:.1f} minutes")
            
            if metrics.error_count > 0:
                content_parts.append(f"with {metrics.error_count} total errors")
            
            if metrics.retry_count > 0:
                content_parts.append(f"and {metrics.retry_count} retry attempts")
            
            if metrics.worker_changes > 0:
                content_parts.append(f"Failed across {metrics.worker_changes + 1} different workers")
        
        if tracking_info and tracking_info.get("errors"):
            # Add first and last error if different
            errors = tracking_info["errors"]
            if len(errors) > 1:
                content_parts.append(f"First error: {errors[0]['error'][:50]}...")
                if errors[0]['error'] != errors[-1]['error']:
                    content_parts.append(f"Last error: {errors[-1]['error'][:50]}...")
        
        return ". ".join(content_parts)
    
    def _assess_success_rating(
        self,
        task_result: TaskResult,
        metrics: Optional[TaskCompletionMetrics]
    ) -> RatingScale:
        """Assess quality rating for successful task completion"""
        
        if not metrics:
            # Default rating without metrics
            return RatingScale.GOOD
        
        score = 3.0  # Base score for success
        
        # Efficiency bonus (0-1 points)
        # Assume tasks should complete within 30 minutes ideally
        if metrics.execution_time <= 15:
            score += 1.0
        elif metrics.execution_time <= 30:
            score += 0.7
        elif metrics.execution_time <= 60:
            score += 0.3
        
        # Error handling penalty (-0.5 points per error, max -1)
        error_penalty = min(metrics.error_count * 0.5, 1.0)
        score -= error_penalty
        
        # Retry penalty (-0.3 points per retry, max -0.6)
        retry_penalty = min(metrics.retry_count * 0.3, 0.6)
        score -= retry_penalty
        
        # Worker changes penalty (-0.2 per change, max -0.4)
        change_penalty = min(metrics.worker_changes * 0.2, 0.4)
        score -= change_penalty
        
        # Subtask completion bonus (0-0.5 points)
        if metrics.subtask_count > 0:
            completion_rate = metrics.subtasks_completed / metrics.subtask_count
            score += completion_rate * 0.5
        
        # Review score bonus (0-0.5 points)
        if metrics.review_score is not None:
            score += (metrics.review_score / 5.0) * 0.5
        
        # Convert score to rating
        if score >= 4.5:
            return RatingScale.EXCELLENT
        elif score >= 3.8:
            return RatingScale.VERY_GOOD
        elif score >= 2.8:
            return RatingScale.GOOD
        elif score >= 2.0:
            return RatingScale.FAIR
        else:
            return RatingScale.POOR
    
    def _collect_feedback_async(
        self,
        task_id: str,
        collection_point: CollectionPoint,
        content: str,
        rating: Optional[RatingScale],
        user_id: Optional[str],
        context: Dict[str, Any]
    ):
        """Collect feedback asynchronously"""
        try:
            self.feedback_collector.collect_feedback(
                task_id=task_id,
                collection_point=collection_point,
                content=content,
                rating=rating,
                user_id=user_id,
                context=context
            )
        except Exception as e:
            logger.error(f"Failed to collect async feedback for task {task_id}: {e}")
    
    def _collect_feedback_sync(
        self,
        task_id: str,
        collection_point: CollectionPoint,
        content: str,
        rating: Optional[RatingScale],
        user_id: Optional[str],
        context: Dict[str, Any]
    ) -> Optional[FeedbackEntry]:
        """Collect feedback synchronously"""
        try:
            return self.feedback_collector.collect_feedback(
                task_id=task_id,
                collection_point=collection_point,
                content=content,
                rating=rating,
                user_id=user_id,
                context=context
            )
        except Exception as e:
            logger.error(f"Failed to collect sync feedback for task {task_id}: {e}")
            return None
    
    def collect_manual_completion_feedback(
        self,
        task_id: str,
        content: str,
        rating: Optional[int] = None,
        success: bool = True,
        user_id: Optional[str] = None
    ) -> Optional[FeedbackEntry]:
        """
        Collect manual feedback about task completion
        
        Args:
            task_id: Task ID
            content: Feedback content
            rating: Optional rating (1-5)
            success: Whether task was successful
            user_id: User providing feedback
            
        Returns:
            FeedbackEntry if successful, None otherwise
        """
        try:
            rating_enum = None
            if rating is not None:
                rating_enum = RatingScale(rating)
            
            collection_point = (
                CollectionPoint.TASK_COMPLETION if success 
                else CollectionPoint.TASK_FAILURE
            )
            
            return self.feedback_collector.collect_feedback(
                task_id=task_id,
                collection_point=collection_point,
                content=content,
                rating=rating_enum,
                user_id=user_id,
                context={
                    "feedback_type": "manual_completion_feedback",
                    "success": success
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to collect manual completion feedback: {e}")
            return None
    
    def collect_review_feedback(
        self,
        task_id: str,
        review_score: float,
        review_comments: str,
        reviewer_id: Optional[str] = None
    ) -> Optional[FeedbackEntry]:
        """
        Collect feedback about Opus review quality
        
        Args:
            task_id: Task ID
            review_score: Review score (0-5)
            review_comments: Review comments
            reviewer_id: ID of the reviewer
            
        Returns:
            FeedbackEntry if successful
        """
        try:
            # Convert review score to rating
            rating = RatingScale(max(1, min(5, round(review_score))))
            
            content = f"Opus review score: {review_score:.1f}/5. Comments: {review_comments[:200]}"
            
            return self.feedback_collector.collect_feedback(
                task_id=task_id,
                collection_point=CollectionPoint.REVIEW_COMPLETION,
                content=content,
                rating=rating,
                user_id=reviewer_id,
                context={
                    "review_score": review_score,
                    "review_comments": review_comments,
                    "auto_generated": True
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to collect review feedback: {e}")
            return None
    
    def get_task_completion_summary(self, task_id: str) -> Dict[str, Any]:
        """
        Get completion feedback summary for a task
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dict with feedback summary and metrics
        """
        try:
            feedback_list = self.feedback_collector.get_task_feedback(task_id)
            
            if not feedback_list:
                return {"task_id": task_id, "feedback_count": 0}
            
            # Separate by type
            completion_feedback = [
                f for f in feedback_list 
                if f.feedback_type == FeedbackType.TASK_COMPLETION
            ]
            
            failure_feedback = [
                f for f in feedback_list
                if f.feedback_type == FeedbackType.ERROR_REPORT
            ]
            
            review_feedback = [
                f for f in feedback_list
                if f.feedback_type == FeedbackType.MANAGER_REVIEW
            ]
            
            # Calculate averages
            ratings = [f.rating.value for f in feedback_list if f.rating]
            avg_rating = sum(ratings) / len(ratings) if ratings else None
            
            # Extract metrics from context
            execution_times = []
            error_counts = []
            
            for feedback in feedback_list:
                if feedback.metadata and feedback.metadata.context:
                    ctx = feedback.metadata.context
                    if "execution_time" in ctx and ctx["execution_time"] is not None:
                        execution_times.append(ctx["execution_time"])
                    if "error_count" in ctx:
                        error_counts.append(ctx["error_count"])
            
            return {
                "task_id": task_id,
                "feedback_count": len(feedback_list),
                "average_rating": avg_rating,
                "completion_feedback_count": len(completion_feedback),
                "failure_feedback_count": len(failure_feedback), 
                "review_feedback_count": len(review_feedback),
                "average_execution_time": (
                    sum(execution_times) / len(execution_times) 
                    if execution_times else None
                ),
                "total_errors": sum(error_counts),
                "success_rate": (
                    len(completion_feedback) / 
                    (len(completion_feedback) + len(failure_feedback))
                    if (len(completion_feedback) + len(failure_feedback)) > 0
                    else None
                )
            }
            
        except Exception as e:
            logger.error(f"Failed to get completion summary for task {task_id}: {e}")
            return {"task_id": task_id, "error": str(e)}
    
    def register_feedback_callback(
        self,
        callback: Callable[[str, FeedbackEntry], None]
    ):
        """Register callback for feedback collection events"""
        self._collection_callbacks.append(callback)
        logger.info("Registered completion feedback callback")
    
    def enable_feedback_collection(self, enabled: bool = True):
        """Enable or disable feedback collection"""
        self._feedback_enabled = enabled
        logger.info(f"Task completion feedback collection {'enabled' if enabled else 'disabled'}")
    
    def close(self):
        """Close the task completion feedback collector"""
        self._thread_pool.shutdown(wait=True)
        self.feedback_collector.close()
        logger.info("Closed TaskCompletionFeedbackCollector")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Convenience function for collecting task completion feedback
def collect_completion_feedback(
    task_id: str,
    title: str,
    success: bool,
    execution_time: float,
    error: Optional[str] = None,
    worker_id: Optional[str] = None,
    user_id: Optional[str] = None,
    storage: Optional[FeedbackStorage] = None
) -> Optional[FeedbackEntry]:
    """
    Convenience function to collect task completion feedback
    
    Args:
        task_id: Task identifier
        title: Task title
        success: Whether task completed successfully
        execution_time: Execution time in minutes
        error: Error message if failed
        worker_id: Worker who executed the task
        user_id: User managing the task
        storage: Optional feedback storage
        
    Returns:
        FeedbackEntry if successful
    """
    feedback_collector = FeedbackCollector(storage) if storage else None
    
    with TaskCompletionFeedbackCollector(feedback_collector=feedback_collector) as completion_feedback:
        task_result = TaskResult(
            task_id=task_id,
            title=title,
            description="",
            success=success,
            error=error,
            execution_time=execution_time,
            worker_id=worker_id
        )
        
        metrics = TaskCompletionMetrics(
            task_id=task_id,
            success=success,
            execution_time=execution_time
        )
        
        return completion_feedback.collect_task_completion_feedback(
            task_result=task_result,
            metrics=metrics,
            user_id=user_id
        )