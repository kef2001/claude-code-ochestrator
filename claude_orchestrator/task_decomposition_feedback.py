"""
Task Decomposition Feedback Integration

This module extends the task decomposition workflow with feedback collection capabilities.
It provides non-blocking feedback collection at key decomposition points.
"""

import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .task_decomposer import TaskDecomposer, DecompositionPlan, DecompositionStrategy, TaskComplexityLevel
from .feedback_collector import (
    FeedbackCollector, CollectionPoint, FeedbackPrompt,
    FeedbackValidationError
)
from .feedback_models import FeedbackType, RatingScale, FeedbackEntry
from .feedback_storage import FeedbackStorage


logger = logging.getLogger(__name__)


class DecompositionFeedbackCollector:
    """
    Feedback collector specifically for task decomposition workflow
    
    Integrates with TaskDecomposer to collect feedback at key decomposition points
    without blocking the main decomposition process.
    """
    
    def __init__(
        self, 
        decomposer: Optional[TaskDecomposer] = None,
        feedback_collector: Optional[FeedbackCollector] = None,
        enable_async_collection: bool = True
    ):
        """
        Initialize decomposition feedback collector
        
        Args:
            decomposer: TaskDecomposer instance (creates new if None)
            feedback_collector: FeedbackCollector instance (creates new if None)
            enable_async_collection: Whether to collect feedback asynchronously
        """
        self.decomposer = decomposer or TaskDecomposer()
        self.feedback_collector = feedback_collector or FeedbackCollector()
        self.enable_async_collection = enable_async_collection
        
        # Thread pool for async feedback collection
        self._thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="feedback")
        
        # Feedback collection settings
        self._feedback_enabled = True
        self._collection_callbacks: List[Callable[[str, FeedbackEntry], None]] = []
        
        # Setup custom prompts for decomposition
        self._setup_decomposition_prompts()
        
        logger.info("Initialized DecompositionFeedbackCollector")
    
    def _setup_decomposition_prompts(self):
        """Setup custom feedback prompts for decomposition workflow"""
        
        # Decomposition quality feedback
        decomposition_prompt = FeedbackPrompt(
            prompt_text="How well did the task decomposition work? Rate the quality of subtask breakdown and strategy choice.",
            feedback_type=FeedbackType.TASK_COMPLETION,
            requires_rating=True,
            validation_rules={
                "min_length": 10
            }
        )
        
        # Strategy effectiveness feedback  
        strategy_prompt = FeedbackPrompt(
            prompt_text="How effective was the chosen decomposition strategy for this task?",
            feedback_type=FeedbackType.MANAGER_REVIEW,
            requires_rating=True
        )
        
        # Subtask quality feedback
        subtask_prompt = FeedbackPrompt(
            prompt_text="Rate the quality of the generated subtasks. Are they well-defined, appropriately sized, and properly sequenced?",
            feedback_type=FeedbackType.TASK_COMPLETION,
            requires_rating=True
        )
        
        # Set custom collection points for decomposition
        self.feedback_collector.set_prompt(CollectionPoint.TASK_COMPLETION, decomposition_prompt)
        self.feedback_collector.set_prompt(CollectionPoint.REVIEW_COMPLETION, strategy_prompt)
        self.feedback_collector.set_prompt(CollectionPoint.MANUAL_FEEDBACK, subtask_prompt)
    
    def decompose_task_with_feedback(
        self,
        task_id: str,
        title: str,
        description: str,
        estimated_duration: Optional[int] = None,
        complexity_hint: Optional[TaskComplexityLevel] = None,
        strategy_hint: Optional[DecompositionStrategy] = None,
        user_id: Optional[str] = None
    ) -> DecompositionPlan:
        """
        Decompose task and collect feedback on the decomposition process
        
        Args:
            task_id: Original task identifier
            title: Task title
            description: Task description  
            estimated_duration: Estimated duration in minutes
            complexity_hint: Hint about task complexity
            strategy_hint: Hint about decomposition strategy
            user_id: User performing the decomposition
            
        Returns:
            DecompositionPlan with feedback collection initiated
        """
        start_time = datetime.now()
        
        logger.info(f"Starting decomposition with feedback for task {task_id}")
        
        try:
            # Perform the actual decomposition
            plan = self.decomposer.decompose_task(
                task_id=task_id,
                title=title,
                description=description,
                estimated_duration=estimated_duration,
                complexity_hint=complexity_hint,
                strategy_hint=strategy_hint
            )
            
            # Calculate decomposition metrics
            decomposition_time = (datetime.now() - start_time).total_seconds()
            success = len(plan.subtasks) > 0
            
            # Collect automatic feedback about the decomposition
            if self._feedback_enabled:
                self._collect_decomposition_feedback(
                    plan=plan,
                    decomposition_time=decomposition_time,
                    success=success,
                    user_id=user_id
                )
            
            logger.info(f"Successfully decomposed task {task_id} with feedback collection")
            return plan
            
        except Exception as e:
            # Collect error feedback
            decomposition_time = (datetime.now() - start_time).total_seconds()
            if self._feedback_enabled:
                self._collect_decomposition_error_feedback(
                    task_id=task_id,
                    error=e,
                    decomposition_time=decomposition_time,
                    user_id=user_id
                )
            raise
    
    def _collect_decomposition_feedback(
        self,
        plan: DecompositionPlan,
        decomposition_time: float,
        success: bool,
        user_id: Optional[str] = None
    ):
        """Collect automatic feedback about the decomposition process"""
        
        # Generate automatic feedback content
        content = self._generate_decomposition_feedback_content(plan, decomposition_time, success)
        
        # Determine rating based on decomposition quality
        rating = self._assess_decomposition_rating(plan, decomposition_time, success)
        
        # Prepare context
        context = {
            "decomposition_time": decomposition_time,
            "success": success,
            "strategy": plan.strategy.value,
            "subtask_count": len(plan.subtasks),
            "confidence_score": plan.confidence_score,
            "execution_groups": len(plan.execution_order),
            "critical_path_duration": plan.get_critical_path_duration(),
            "auto_generated": True
        }
        
        if self.enable_async_collection:
            # Collect feedback asynchronously to avoid blocking decomposition
            self._thread_pool.submit(
                self._async_collect_feedback,
                plan.original_task_id,
                CollectionPoint.TASK_COMPLETION,
                content,
                rating,
                user_id,
                context
            )
        else:
            # Collect feedback synchronously
            self._sync_collect_feedback(
                plan.original_task_id,
                CollectionPoint.TASK_COMPLETION,
                content,
                rating,
                user_id,
                context
            )
    
    def _collect_decomposition_error_feedback(
        self,
        task_id: str,
        error: Exception,
        decomposition_time: float,
        user_id: Optional[str] = None
    ):
        """Collect feedback when decomposition fails"""
        
        content = f"Task decomposition failed after {decomposition_time:.2f} seconds. Error: {str(error)}"
        
        context = {
            "decomposition_time": decomposition_time,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "auto_generated": True
        }
        
        if self.enable_async_collection:
            self._thread_pool.submit(
                self.feedback_collector.collect_error_feedback,
                task_id,
                str(error),
                type(error).__name__,
                None,  # No stack trace for now
                user_id
            )
        else:
            self.feedback_collector.collect_error_feedback(
                task_id=task_id,
                error_message=str(error),
                error_type=type(error).__name__,
                user_id=user_id
            )
    
    def _generate_decomposition_feedback_content(
        self,
        plan: DecompositionPlan,
        decomposition_time: float,
        success: bool
    ) -> str:
        """Generate descriptive feedback content for decomposition"""
        
        if not success:
            return f"Task decomposition failed after {decomposition_time:.2f} seconds"
        
        content_parts = [
            f"Task decomposed successfully in {decomposition_time:.2f} seconds",
            f"Strategy: {plan.strategy.value}",
            f"Created {len(plan.subtasks)} subtasks",
            f"Execution groups: {len(plan.execution_order)}",
            f"Confidence score: {plan.confidence_score:.2f}"
        ]
        
        # Add assessment of decomposition quality
        if plan.confidence_score >= 0.8:
            content_parts.append("High confidence in decomposition quality")
        elif plan.confidence_score >= 0.6:
            content_parts.append("Moderate confidence in decomposition quality")
        else:
            content_parts.append("Low confidence in decomposition quality")
        
        # Add notes about execution complexity
        if len(plan.execution_order) == 1:
            content_parts.append("All subtasks can be executed in parallel")
        elif len(plan.execution_order) == len(plan.subtasks):
            content_parts.append("All subtasks must be executed sequentially")
        else:
            content_parts.append("Mixed parallel and sequential execution required")
        
        return ". ".join(content_parts)
    
    def _assess_decomposition_rating(
        self,
        plan: DecompositionPlan,
        decomposition_time: float,
        success: bool
    ) -> RatingScale:
        """Assess the quality of decomposition and assign rating"""
        
        if not success:
            return RatingScale.POOR
        
        score = 0
        
        # Confidence score contribution (0-2 points)
        if plan.confidence_score >= 0.8:
            score += 2
        elif plan.confidence_score >= 0.6:
            score += 1
        
        # Decomposition time contribution (0-1 points)
        if decomposition_time <= 5.0:  # Fast decomposition
            score += 1
        
        # Subtask count appropriateness (0-1 points)
        if 3 <= len(plan.subtasks) <= 8:  # Good range
            score += 1
        elif len(plan.subtasks) <= 15:  # Acceptable range
            score += 0.5
        
        # Execution efficiency (0-1 points)
        if len(plan.execution_order) <= len(plan.subtasks) / 2:  # Good parallelization
            score += 1
        elif len(plan.execution_order) <= len(plan.subtasks) * 0.8:  # Some parallelization
            score += 0.5
        
        # Convert score to rating
        if score >= 4.5:
            return RatingScale.EXCELLENT
        elif score >= 3.5:
            return RatingScale.VERY_GOOD
        elif score >= 2.5:
            return RatingScale.GOOD
        elif score >= 1.5:
            return RatingScale.FAIR
        else:
            return RatingScale.POOR
    
    def _async_collect_feedback(
        self,
        task_id: str,
        collection_point: CollectionPoint,
        content: str,
        rating: RatingScale,
        user_id: Optional[str],
        context: Dict[str, Any]
    ):
        """Collect feedback asynchronously"""
        try:
            feedback_entry = self.feedback_collector.collect_feedback(
                task_id=task_id,
                collection_point=collection_point,
                content=content,
                rating=rating,
                user_id=user_id,
                context=context
            )
            
            # Notify callbacks
            for callback in self._collection_callbacks:
                try:
                    callback(task_id, feedback_entry)
                except Exception as e:
                    logger.error(f"Callback error for task {task_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to collect async feedback for task {task_id}: {e}")
    
    def _sync_collect_feedback(
        self,
        task_id: str,
        collection_point: CollectionPoint,
        content: str,
        rating: RatingScale,
        user_id: Optional[str],
        context: Dict[str, Any]
    ):
        """Collect feedback synchronously"""
        try:
            feedback_entry = self.feedback_collector.collect_feedback(
                task_id=task_id,
                collection_point=collection_point,
                content=content,
                rating=rating,
                user_id=user_id,
                context=context
            )
            
            # Notify callbacks
            for callback in self._collection_callbacks:
                try:
                    callback(task_id, feedback_entry)
                except Exception as e:
                    logger.error(f"Callback error for task {task_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to collect sync feedback for task {task_id}: {e}")
    
    def collect_manual_decomposition_feedback(
        self,
        task_id: str,
        content: str,
        rating: Optional[int] = None,
        user_id: Optional[str] = None
    ) -> Optional[FeedbackEntry]:
        """
        Collect manual feedback about task decomposition
        
        Args:
            task_id: Task ID that was decomposed
            content: Feedback content
            rating: Optional rating (1-5)
            user_id: User providing feedback
            
        Returns:
            FeedbackEntry if successful, None otherwise
        """
        try:
            rating_enum = None
            if rating is not None:
                rating_enum = RatingScale(rating)
            
            return self.feedback_collector.collect_feedback(
                task_id=task_id,
                collection_point=CollectionPoint.MANUAL_FEEDBACK,
                content=content,
                rating=rating_enum,
                user_id=user_id,
                context={"feedback_type": "manual_decomposition_feedback"}
            )
            
        except Exception as e:
            logger.error(f"Failed to collect manual decomposition feedback: {e}")
            return None
    
    def get_decomposition_feedback_summary(self, task_id: str):
        """Get feedback summary for a decomposed task"""
        return self.feedback_collector.get_feedback_summary(task_id)
    
    def register_feedback_callback(
        self, 
        callback: Callable[[str, FeedbackEntry], None]
    ):
        """
        Register callback to be called when feedback is collected
        
        Args:
            callback: Function to call with (task_id, feedback_entry)
        """
        self._collection_callbacks.append(callback)
        logger.info("Registered feedback collection callback")
    
    def enable_feedback_collection(self, enabled: bool = True):
        """Enable or disable feedback collection"""
        self._feedback_enabled = enabled
        logger.info(f"Feedback collection {'enabled' if enabled else 'disabled'}")
    
    def close(self):
        """Close the decomposition feedback collector"""
        self._thread_pool.shutdown(wait=True)
        self.feedback_collector.close()
        logger.info("Closed DecompositionFeedbackCollector")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Convenience function for quick decomposition with feedback
def decompose_with_feedback(
    task_id: str,
    title: str,
    description: str,
    estimated_duration: Optional[int] = None,
    strategy_hint: Optional[DecompositionStrategy] = None,
    user_id: Optional[str] = None,
    storage: Optional[FeedbackStorage] = None
) -> DecompositionPlan:
    """
    Convenience function to decompose a task with feedback collection
    
    Args:
        task_id: Task identifier
        title: Task title
        description: Task description
        estimated_duration: Estimated duration in minutes
        strategy_hint: Decomposition strategy hint
        user_id: User performing decomposition
        storage: Optional feedback storage instance
        
    Returns:
        DecompositionPlan with feedback collection
    """
    feedback_collector = FeedbackCollector(storage) if storage else None
    
    with DecompositionFeedbackCollector(feedback_collector=feedback_collector) as decomp_feedback:
        return decomp_feedback.decompose_task_with_feedback(
            task_id=task_id,
            title=title,
            description=description,
            estimated_duration=estimated_duration,
            strategy_hint=strategy_hint,
            user_id=user_id
        )