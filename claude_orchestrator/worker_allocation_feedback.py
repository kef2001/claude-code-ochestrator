"""
Worker Allocation Feedback Integration

This module extends the worker allocation workflow with comprehensive feedback collection.
It provides non-blocking feedback collection for allocation decisions and worker performance.
"""

import logging
from typing import Optional, Dict, Any, List, Callable, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import threading

from .dynamic_worker_allocation import (
    DynamicWorkerAllocator, TaskRequirements, TaskComplexity, WorkerCapability
)
from .feedback_collector import (
    FeedbackCollector, CollectionPoint, FeedbackPrompt,
    FeedbackValidationError
)
from .feedback_models import FeedbackType, RatingScale, FeedbackEntry
from .feedback_storage import FeedbackStorage


logger = logging.getLogger(__name__)


@dataclass
class AllocationFeedbackMetrics:
    """Metrics for allocation feedback assessment"""
    allocation_time: float  # Time taken to allocate worker (seconds)
    suitability_score: float  # Worker suitability score (0-1)
    task_complexity: TaskComplexity
    worker_availability: float  # Worker load before allocation (0-1)
    alternative_workers_count: int  # Number of other suitable workers
    worker_specialization_match: float  # How well worker matches task requirements


@dataclass
class CompletionFeedbackMetrics:
    """Metrics for task completion feedback assessment"""
    execution_time: float  # Actual execution time (minutes)
    estimated_duration: Optional[float]  # Original estimated duration
    success: bool
    worker_efficiency: float  # Ratio of estimated/actual time
    error_count: int = 0
    quality_indicators: Dict[str, Any] = field(default_factory=dict)


class WorkerAllocationFeedbackCollector:
    """
    Feedback collector for worker allocation and performance workflow
    
    Integrates with DynamicWorkerAllocator to collect feedback at key allocation points
    without blocking the main allocation process.
    """
    
    def __init__(
        self,
        allocator: Optional[DynamicWorkerAllocator] = None,
        feedback_collector: Optional[FeedbackCollector] = None,
        enable_async_collection: bool = True
    ):
        """
        Initialize worker allocation feedback collector
        
        Args:
            allocator: DynamicWorkerAllocator instance (creates new if None)
            feedback_collector: FeedbackCollector instance (creates new if None) 
            enable_async_collection: Whether to collect feedback asynchronously
        """
        self.allocator = allocator or DynamicWorkerAllocator()
        self.feedback_collector = feedback_collector or FeedbackCollector()
        self.enable_async_collection = enable_async_collection
        
        # Thread pool for async feedback collection
        self._thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="worker_feedback")
        
        # Feedback collection settings
        self._feedback_enabled = True
        self._collection_callbacks: List[Callable[[str, FeedbackEntry], None]] = []
        
        # Allocation tracking for feedback correlation
        self._allocation_tracking: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        
        # Setup custom prompts for worker allocation
        self._setup_allocation_prompts()
        
        logger.info("Initialized WorkerAllocationFeedbackCollector")
    
    def _setup_allocation_prompts(self):
        """Setup custom feedback prompts for worker allocation workflow"""
        
        # Worker allocation quality feedback
        allocation_prompt = FeedbackPrompt(
            prompt_text="How appropriate was this worker allocation? Consider worker suitability, task complexity match, and allocation speed.",
            feedback_type=FeedbackType.WORKER_PERFORMANCE,
            requires_rating=True,
            validation_rules={"min_length": 15}
        )
        
        # Worker performance feedback
        performance_prompt = FeedbackPrompt(
            prompt_text="Rate the worker's performance on this task. Consider quality, efficiency, and error handling.",
            feedback_type=FeedbackType.WORKER_PERFORMANCE,
            requires_rating=True,
            validation_rules={"min_length": 10}
        )
        
        # Task completion quality feedback
        completion_prompt = FeedbackPrompt(
            prompt_text="How well was this task completed? Rate the overall quality and efficiency.",
            feedback_type=FeedbackType.TASK_COMPLETION,
            requires_rating=True
        )
        
        # Set custom collection points for allocation
        self.feedback_collector.set_prompt(CollectionPoint.WORKER_ALLOCATION, allocation_prompt)
        self.feedback_collector.set_prompt(CollectionPoint.WORKER_RELEASE, performance_prompt)
        self.feedback_collector.set_prompt(CollectionPoint.TASK_COMPLETION, completion_prompt)
    
    def allocate_worker_with_feedback(
        self,
        task_id: str,
        task_title: str,
        task_description: str,
        task_requirements: Optional[TaskRequirements] = None,
        user_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Allocate worker with feedback collection on allocation decision
        
        Args:
            task_id: Task identifier
            task_title: Task title
            task_description: Task description
            task_requirements: Pre-analyzed task requirements
            user_id: User requesting allocation
            
        Returns:
            Worker ID if allocation successful, None otherwise
        """
        start_time = datetime.now()
        
        logger.info(f"Starting worker allocation with feedback for task {task_id}")
        
        try:
            # Get worker status before allocation for metrics
            worker_status = self.allocator.get_worker_status()
            available_workers = worker_status.get('available_workers', 0)
            
            # Perform the actual allocation
            worker_id = self.allocator.allocate_worker(
                task_id=task_id,
                task_title=task_title,
                task_description=task_description,
                task_requirements=task_requirements
            )
            
            # Calculate allocation metrics
            allocation_time = (datetime.now() - start_time).total_seconds()
            
            if worker_id:
                # Get allocation details for feedback
                allocation_record = self.allocator.allocation_history[-1] if self.allocator.allocation_history else None
                
                # Store allocation tracking info for completion feedback
                with self._lock:
                    self._allocation_tracking[task_id] = {
                        "worker_id": worker_id,
                        "allocation_time": allocation_time,
                        "start_time": start_time,
                        "task_requirements": task_requirements,
                        "allocation_record": allocation_record,
                        "user_id": user_id
                    }
                
                # Collect allocation feedback
                if self._feedback_enabled:
                    self._collect_allocation_feedback(
                        task_id=task_id,
                        worker_id=worker_id,
                        allocation_time=allocation_time,
                        allocation_record=allocation_record,
                        available_workers=available_workers,
                        success=True,
                        user_id=user_id
                    )
                
                logger.info(f"Successfully allocated worker {worker_id} to task {task_id} with feedback")
            else:
                # Collect failure feedback
                if self._feedback_enabled:
                    self._collect_allocation_failure_feedback(
                        task_id=task_id,
                        allocation_time=allocation_time,
                        available_workers=available_workers,
                        task_requirements=task_requirements,
                        user_id=user_id
                    )
                
                logger.warning(f"Failed to allocate worker for task {task_id}")
            
            return worker_id
            
        except Exception as e:
            allocation_time = (datetime.now() - start_time).total_seconds()
            if self._feedback_enabled:
                self._collect_allocation_error_feedback(
                    task_id=task_id,
                    error=e,
                    allocation_time=allocation_time,
                    user_id=user_id
                )
            raise
    
    def release_worker_with_feedback(
        self,
        worker_id: str,
        task_id: str,
        success: bool = True,
        actual_duration: Optional[float] = None,
        error_count: int = 0,
        quality_indicators: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Release worker with comprehensive feedback collection
        
        Args:
            worker_id: Worker identifier
            task_id: Task identifier
            success: Whether task completed successfully
            actual_duration: Actual task duration in minutes
            error_count: Number of errors encountered
            quality_indicators: Dict of quality metrics
            user_id: User releasing worker
            
        Returns:
            True if released successfully
        """
        logger.info(f"Releasing worker {worker_id} from task {task_id} with feedback collection")
        
        try:
            # Get allocation tracking info
            allocation_info = None
            with self._lock:
                allocation_info = self._allocation_tracking.pop(task_id, None)
            
            # Release the worker
            release_success = self.allocator.release_worker(
                worker_id=worker_id,
                task_id=task_id,
                success=success,
                actual_duration=actual_duration
            )
            
            # Collect performance and completion feedback
            if self._feedback_enabled and allocation_info:
                self._collect_completion_feedback(
                    task_id=task_id,
                    worker_id=worker_id,
                    success=success,
                    actual_duration=actual_duration,
                    error_count=error_count,
                    quality_indicators=quality_indicators or {},
                    allocation_info=allocation_info,
                    user_id=user_id or allocation_info.get("user_id")
                )
            
            logger.info(f"Successfully released worker {worker_id} from task {task_id}")
            return release_success
            
        except Exception as e:
            logger.error(f"Failed to release worker {worker_id} from task {task_id}: {e}")
            if self._feedback_enabled:
                self.feedback_collector.collect_error_feedback(
                    task_id=task_id,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    user_id=user_id
                )
            return False
    
    def _collect_allocation_feedback(
        self,
        task_id: str,
        worker_id: str,
        allocation_time: float,
        allocation_record: Optional[Dict[str, Any]],
        available_workers: int,
        success: bool,
        user_id: Optional[str] = None
    ):
        """Collect feedback about worker allocation decision"""
        
        # Generate allocation feedback content
        content = self._generate_allocation_feedback_content(
            worker_id, allocation_time, allocation_record, available_workers, success
        )
        
        # Assess allocation quality rating
        rating = self._assess_allocation_rating(
            allocation_time, allocation_record, available_workers, success
        )
        
        # Prepare context
        context = {
            "worker_id": worker_id,
            "allocation_time": allocation_time,
            "available_workers": available_workers,
            "success": success,
            "auto_generated": True
        }
        
        if allocation_record:
            context.update({
                "suitability_score": allocation_record.get("suitability_score"),
                "task_complexity": allocation_record.get("task_complexity"),
                "estimated_duration": allocation_record.get("estimated_duration"),
                "required_capabilities": allocation_record.get("required_capabilities", [])
            })
        
        self._async_or_sync_collect_feedback(
            task_id=task_id,
            collection_point=CollectionPoint.WORKER_ALLOCATION,
            content=content,
            rating=rating,
            user_id=user_id,
            context=context
        )
    
    def _collect_allocation_failure_feedback(
        self,
        task_id: str,
        allocation_time: float,
        available_workers: int,
        task_requirements: Optional[TaskRequirements],
        user_id: Optional[str] = None
    ):
        """Collect feedback when worker allocation fails"""
        
        content = f"Worker allocation failed after {allocation_time:.2f} seconds. "
        content += f"Available workers: {available_workers}. "
        
        if task_requirements:
            content += f"Required complexity: {task_requirements.complexity.value}. "
            content += f"Required capabilities: {[cap.value for cap in task_requirements.required_capabilities]}."
        
        context = {
            "allocation_time": allocation_time,
            "available_workers": available_workers,
            "task_requirements": task_requirements.complexity.value if task_requirements else None,
            "failure_reason": "no_suitable_workers",
            "auto_generated": True
        }
        
        self._async_or_sync_collect_feedback(
            task_id=task_id,
            collection_point=CollectionPoint.ERROR_OCCURRENCE,
            content=content,
            rating=RatingScale.POOR,
            user_id=user_id,
            context=context
        )
    
    def _collect_allocation_error_feedback(
        self,
        task_id: str,
        error: Exception,
        allocation_time: float,
        user_id: Optional[str] = None
    ):
        """Collect feedback when allocation encounters an error"""
        
        self.feedback_collector.collect_error_feedback(
            task_id=task_id,
            error_message=str(error),
            error_type=type(error).__name__,
            user_id=user_id
        )
    
    def _collect_completion_feedback(
        self,
        task_id: str,
        worker_id: str,
        success: bool,
        actual_duration: Optional[float],
        error_count: int,
        quality_indicators: Dict[str, Any],
        allocation_info: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        """Collect comprehensive feedback about task completion and worker performance"""
        
        # Calculate completion metrics
        start_time = allocation_info.get("start_time", datetime.now())
        total_time = (datetime.now() - start_time).total_seconds() / 60.0  # Convert to minutes
        
        estimated_duration = None
        allocation_record = allocation_info.get("allocation_record")
        if allocation_record:
            estimated_duration = allocation_record.get("estimated_duration")
        
        # Generate completion feedback
        completion_content = self._generate_completion_feedback_content(
            success, total_time, estimated_duration, error_count, quality_indicators
        )
        
        completion_rating = self._assess_completion_rating(
            success, total_time, estimated_duration, error_count, quality_indicators
        )
        
        # Generate worker performance feedback
        performance_content = self._generate_worker_performance_feedback_content(
            worker_id, success, total_time, estimated_duration, error_count
        )
        
        performance_rating = self._assess_worker_performance_rating(
            success, total_time, estimated_duration, error_count
        )
        
        # Prepare contexts
        completion_context = {
            "worker_id": worker_id,
            "total_time": total_time,
            "estimated_duration": estimated_duration,
            "actual_duration": actual_duration,
            "success": success,
            "error_count": error_count,
            "quality_indicators": quality_indicators,
            "auto_generated": True
        }
        
        performance_context = {
            "worker_id": worker_id,
            "efficiency_ratio": estimated_duration / total_time if estimated_duration and total_time > 0 else None,
            "success": success,
            "error_count": error_count,
            "auto_generated": True
        }
        
        # Collect both feedbacks
        self._async_or_sync_collect_feedback(
            task_id=task_id,
            collection_point=CollectionPoint.TASK_COMPLETION,
            content=completion_content,
            rating=completion_rating,
            user_id=user_id,
            context=completion_context
        )
        
        self._async_or_sync_collect_feedback(
            task_id=task_id,
            collection_point=CollectionPoint.WORKER_RELEASE,
            content=performance_content,
            rating=performance_rating,
            user_id=user_id,
            context=performance_context
        )
    
    def _generate_allocation_feedback_content(
        self,
        worker_id: str,
        allocation_time: float,
        allocation_record: Optional[Dict[str, Any]],
        available_workers: int,
        success: bool
    ) -> str:
        """Generate descriptive content for allocation feedback"""
        
        if not success:
            return f"Failed to allocate worker after {allocation_time:.2f} seconds with {available_workers} available workers"
        
        content_parts = [
            f"Allocated worker {worker_id} in {allocation_time:.2f} seconds",
            f"Available workers: {available_workers}"
        ]
        
        if allocation_record:
            suitability_score = allocation_record.get("suitability_score", 0)
            complexity = allocation_record.get("task_complexity", "unknown")
            content_parts.extend([
                f"Suitability score: {suitability_score:.2f}",
                f"Task complexity: {complexity}"
            ])
            
            if suitability_score >= 0.8:
                content_parts.append("Excellent worker-task match")
            elif suitability_score >= 0.6:
                content_parts.append("Good worker-task match")
            else:
                content_parts.append("Suboptimal worker-task match")
        
        if allocation_time <= 1.0:
            content_parts.append("Fast allocation")
        elif allocation_time <= 3.0:
            content_parts.append("Reasonable allocation time")
        else:
            content_parts.append("Slow allocation")
        
        return ". ".join(content_parts)
    
    def _assess_allocation_rating(
        self,
        allocation_time: float,
        allocation_record: Optional[Dict[str, Any]],
        available_workers: int,
        success: bool
    ) -> RatingScale:
        """Assess allocation quality and assign rating"""
        
        if not success:
            return RatingScale.POOR
        
        score = 0
        
        # Suitability score contribution (0-2 points)
        if allocation_record:
            suitability_score = allocation_record.get("suitability_score", 0)
            if suitability_score >= 0.8:
                score += 2
            elif suitability_score >= 0.6:
                score += 1.5
            elif suitability_score >= 0.4:
                score += 1
        
        # Allocation speed contribution (0-1 points)
        if allocation_time <= 1.0:
            score += 1
        elif allocation_time <= 3.0:
            score += 0.5
        
        # Worker availability contribution (0-1 points)
        if available_workers >= 3:
            score += 1
        elif available_workers >= 1:
            score += 0.5
        
        # Success contribution (0-1 points)
        score += 1
        
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
    
    def _generate_completion_feedback_content(
        self,
        success: bool,
        total_time: float,
        estimated_duration: Optional[float],
        error_count: int,
        quality_indicators: Dict[str, Any]
    ) -> str:
        """Generate content for task completion feedback"""
        
        status = "successfully" if success else "with failures"
        content_parts = [f"Task completed {status} in {total_time:.1f} minutes"]
        
        if estimated_duration:
            efficiency = estimated_duration / total_time if total_time > 0 else 0
            content_parts.append(f"Efficiency ratio: {efficiency:.2f}")
            
            if efficiency >= 1.2:
                content_parts.append("Completed faster than estimated")
            elif efficiency >= 0.8:
                content_parts.append("Completed within expected time")
            else:
                content_parts.append("Took longer than estimated")
        
        if error_count > 0:
            content_parts.append(f"Encountered {error_count} errors")
        
        if quality_indicators:
            quality_notes = []
            for indicator, value in quality_indicators.items():
                quality_notes.append(f"{indicator}: {value}")
            if quality_notes:
                content_parts.append(f"Quality metrics: {', '.join(quality_notes)}")
        
        return ". ".join(content_parts)
    
    def _assess_completion_rating(
        self,
        success: bool,
        total_time: float,
        estimated_duration: Optional[float],
        error_count: int,
        quality_indicators: Dict[str, Any]
    ) -> RatingScale:
        """Assess task completion quality"""
        
        if not success:
            return RatingScale.POOR
        
        score = 2  # Base score for success
        
        # Efficiency contribution (0-2 points)
        if estimated_duration and total_time > 0:
            efficiency = estimated_duration / total_time
            if efficiency >= 1.2:
                score += 2
            elif efficiency >= 0.8:
                score += 1
        
        # Error handling contribution (0-1 points)
        if error_count == 0:
            score += 1
        elif error_count <= 2:
            score += 0.5
        
        # Quality indicators contribution (0-1 points)
        if quality_indicators:
            avg_quality = sum(float(v) for v in quality_indicators.values() if isinstance(v, (int, float))) / len(quality_indicators)
            if avg_quality >= 0.8:
                score += 1
            elif avg_quality >= 0.6:
                score += 0.5
        
        # Convert to rating
        if score >= 5:
            return RatingScale.EXCELLENT
        elif score >= 4:
            return RatingScale.VERY_GOOD
        elif score >= 3:
            return RatingScale.GOOD
        elif score >= 2:
            return RatingScale.FAIR
        else:
            return RatingScale.POOR
    
    def _generate_worker_performance_feedback_content(
        self,
        worker_id: str,
        success: bool,
        total_time: float,
        estimated_duration: Optional[float],
        error_count: int
    ) -> str:
        """Generate content for worker performance feedback"""
        
        performance_desc = "excellent" if success and error_count == 0 else "good" if success else "poor"
        content_parts = [f"Worker {worker_id} showed {performance_desc} performance"]
        
        if estimated_duration and total_time > 0:
            efficiency = estimated_duration / total_time
            if efficiency >= 1.2:
                content_parts.append("Completed ahead of schedule")
            elif efficiency >= 0.8:
                content_parts.append("Completed on schedule")
            else:
                content_parts.append("Took longer than expected")
        
        content_parts.append(f"Task time: {total_time:.1f} minutes")
        
        if error_count > 0:
            content_parts.append(f"Errors encountered: {error_count}")
        
        return ". ".join(content_parts)
    
    def _assess_worker_performance_rating(
        self,
        success: bool,
        total_time: float,
        estimated_duration: Optional[float],
        error_count: int
    ) -> RatingScale:
        """Assess worker performance rating"""
        
        if not success:
            return RatingScale.POOR if error_count > 3 else RatingScale.FAIR
        
        score = 2  # Base score for success
        
        # Efficiency score (0-2 points)
        if estimated_duration and total_time > 0:
            efficiency = estimated_duration / total_time
            if efficiency >= 1.2:
                score += 2
            elif efficiency >= 0.8:
                score += 1.5
            elif efficiency >= 0.6:
                score += 1
        
        # Error handling score (0-1 points)
        if error_count == 0:
            score += 1
        elif error_count <= 1:
            score += 0.5
        
        # Convert to rating
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
    
    def _async_or_sync_collect_feedback(
        self,
        task_id: str,
        collection_point: CollectionPoint,
        content: str,
        rating: RatingScale,
        user_id: Optional[str],
        context: Dict[str, Any]
    ):
        """Collect feedback either asynchronously or synchronously"""
        
        if self.enable_async_collection:
            self._thread_pool.submit(
                self._collect_feedback_with_callbacks,
                task_id, collection_point, content, rating, user_id, context
            )
        else:
            self._collect_feedback_with_callbacks(
                task_id, collection_point, content, rating, user_id, context
            )
    
    def _collect_feedback_with_callbacks(
        self,
        task_id: str,
        collection_point: CollectionPoint,
        content: str,
        rating: RatingScale,
        user_id: Optional[str],
        context: Dict[str, Any]
    ):
        """Collect feedback and notify callbacks"""
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
            logger.error(f"Failed to collect feedback for task {task_id}: {e}")
    
    def collect_manual_allocation_feedback(
        self,
        task_id: str,
        content: str,
        rating: Optional[int] = None,
        feedback_type: str = "allocation",
        user_id: Optional[str] = None
    ) -> Optional[FeedbackEntry]:
        """
        Collect manual feedback about worker allocation or performance
        
        Args:
            task_id: Task ID
            content: Feedback content
            rating: Optional rating (1-5)
            feedback_type: Type of feedback ("allocation", "performance", "completion")
            user_id: User providing feedback
            
        Returns:
            FeedbackEntry if successful, None otherwise
        """
        try:
            rating_enum = None
            if rating is not None:
                rating_enum = RatingScale(rating)
            
            # Map feedback type to collection point
            collection_point_map = {
                "allocation": CollectionPoint.WORKER_ALLOCATION,
                "performance": CollectionPoint.WORKER_RELEASE,
                "completion": CollectionPoint.TASK_COMPLETION
            }
            
            collection_point = collection_point_map.get(feedback_type, CollectionPoint.MANUAL_FEEDBACK)
            
            return self.feedback_collector.collect_feedback(
                task_id=task_id,
                collection_point=collection_point,
                content=content,
                rating=rating_enum,
                user_id=user_id,
                context={"feedback_type": f"manual_{feedback_type}_feedback"}
            )
            
        except Exception as e:
            logger.error(f"Failed to collect manual allocation feedback: {e}")
            return None
    
    def get_worker_feedback_summary(self, worker_id: str) -> Dict[str, Any]:
        """
        Get feedback summary for a specific worker
        
        Args:
            worker_id: Worker identifier
            
        Returns:
            Dict with feedback statistics and recent feedback
        """
        try:
            # Get all feedback containing this worker ID
            all_feedback = self.feedback_collector.storage.list_feedback(limit=1000)
            worker_feedback = [
                f for f in all_feedback 
                if f.metadata and f.metadata.context.get("worker_id") == worker_id
            ]
            
            if not worker_feedback:
                return {"worker_id": worker_id, "feedback_count": 0}
            
            # Calculate statistics
            ratings = [f.rating.value for f in worker_feedback if f.rating]
            avg_rating = sum(ratings) / len(ratings) if ratings else None
            
            # Group by feedback type
            by_type = {}
            for feedback in worker_feedback:
                feedback_type = feedback.feedback_type.value
                if feedback_type not in by_type:
                    by_type[feedback_type] = []
                by_type[feedback_type].append(feedback)
            
            return {
                "worker_id": worker_id,
                "feedback_count": len(worker_feedback),
                "average_rating": avg_rating,
                "feedback_by_type": {k: len(v) for k, v in by_type.items()},
                "recent_feedback": [
                    {
                        "content": f.content[:100] + "..." if len(f.content) > 100 else f.content,
                        "rating": f.rating.value if f.rating else None,
                        "timestamp": f.timestamp.isoformat(),
                        "type": f.feedback_type.value
                    }
                    for f in sorted(worker_feedback, key=lambda x: x.timestamp, reverse=True)[:5]
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get worker feedback summary for {worker_id}: {e}")
            return {"worker_id": worker_id, "error": str(e)}
    
    def register_feedback_callback(
        self,
        callback: Callable[[str, FeedbackEntry], None]
    ):
        """Register callback for feedback collection events"""
        self._collection_callbacks.append(callback)
        logger.info("Registered allocation feedback callback")
    
    def enable_feedback_collection(self, enabled: bool = True):
        """Enable or disable feedback collection"""
        self._feedback_enabled = enabled
        logger.info(f"Worker allocation feedback collection {'enabled' if enabled else 'disabled'}")
    
    def close(self):
        """Close the worker allocation feedback collector"""
        self._thread_pool.shutdown(wait=True)
        self.feedback_collector.close()
        logger.info("Closed WorkerAllocationFeedbackCollector")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Convenience functions for worker allocation with feedback
def allocate_worker_with_feedback(
    task_id: str,
    task_title: str,
    task_description: str,
    task_requirements: Optional[TaskRequirements] = None,
    user_id: Optional[str] = None,
    storage: Optional[FeedbackStorage] = None
) -> Optional[str]:
    """
    Convenience function to allocate worker with feedback
    
    Args:
        task_id: Task identifier
        task_title: Task title
        task_description: Task description
        task_requirements: Task requirements
        user_id: User requesting allocation
        storage: Optional feedback storage
        
    Returns:
        Worker ID if successful, None otherwise
    """
    feedback_collector = FeedbackCollector(storage) if storage else None
    
    with WorkerAllocationFeedbackCollector(feedback_collector=feedback_collector) as alloc_feedback:
        return alloc_feedback.allocate_worker_with_feedback(
            task_id=task_id,
            task_title=task_title,
            task_description=task_description,
            task_requirements=task_requirements,
            user_id=user_id
        )