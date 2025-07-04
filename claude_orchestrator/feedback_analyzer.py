"""Feedback analysis module for analyzing patterns and insights from feedback data."""

import statistics
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
import logging

from .feedback_model import (
    FeedbackModel, 
    FeedbackType, 
    FeedbackSeverity, 
    FeedbackCategory,
    FeedbackMetrics
)
from .feedback_storage import FeedbackStorage


logger = logging.getLogger(__name__)


@dataclass
class WorkerPerformance:
    """Worker performance metrics."""
    worker_id: str
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    average_execution_time: float = 0.0
    average_quality_score: float = 0.0
    average_tokens_used: int = 0
    error_rate: float = 0.0
    success_rate: float = 0.0
    total_feedback_count: int = 0
    severity_distribution: Dict[str, int] = field(default_factory=dict)
    category_distribution: Dict[str, int] = field(default_factory=dict)
    recent_trend: str = "stable"  # improving, declining, stable


@dataclass
class TaskAnalysis:
    """Task-specific analysis results."""
    task_id: str
    feedback_count: int = 0
    success: bool = False
    execution_time: Optional[float] = None
    quality_score: Optional[float] = None
    error_messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    resource_usage: Dict[str, float] = field(default_factory=dict)
    related_tasks: List[str] = field(default_factory=list)


@dataclass
class TrendAnalysis:
    """Trend analysis over time."""
    period: str  # daily, weekly, monthly
    start_date: datetime
    end_date: datetime
    total_feedback: int = 0
    success_rate_trend: List[float] = field(default_factory=list)
    error_rate_trend: List[float] = field(default_factory=list)
    performance_trend: List[float] = field(default_factory=list)
    quality_trend: List[float] = field(default_factory=list)
    peak_periods: List[Tuple[datetime, int]] = field(default_factory=list)


@dataclass
class FeedbackInsights:
    """Comprehensive feedback insights."""
    total_feedback: int = 0
    time_period: Optional[Tuple[datetime, datetime]] = None
    overall_success_rate: float = 0.0
    overall_error_rate: float = 0.0
    average_execution_time: float = 0.0
    average_quality_score: float = 0.0
    most_common_errors: List[Tuple[str, int]] = field(default_factory=list)
    bottleneck_tasks: List[str] = field(default_factory=list)
    high_performing_workers: List[str] = field(default_factory=list)
    problematic_workers: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class FeedbackAnalyzer:
    """Analyzes feedback data to provide insights and recommendations."""
    
    def __init__(self, storage: FeedbackStorage):
        """Initialize feedback analyzer.
        
        Args:
            storage: Feedback storage instance
        """
        self.storage = storage
        self._cache: Dict[str, Any] = {}
        self._cache_timeout = 300  # 5 minutes
    
    def analyze_worker_performance(self, 
                                 worker_id: str,
                                 time_range: Optional[Tuple[datetime, datetime]] = None) -> WorkerPerformance:
        """Analyze performance metrics for a specific worker.
        
        Args:
            worker_id: Worker to analyze
            time_range: Optional time range filter
            
        Returns:
            Worker performance metrics
        """
        # Query feedback for worker
        query_params = {"worker_id": worker_id}
        if time_range:
            query_params["start_time"] = time_range[0]
            query_params["end_time"] = time_range[1]
        
        feedbacks = self.storage.query(**query_params)
        
        # Initialize performance metrics
        performance = WorkerPerformance(worker_id=worker_id)
        
        if not feedbacks:
            return performance
        
        # Analyze feedback
        execution_times = []
        quality_scores = []
        tokens_used = []
        task_outcomes = defaultdict(int)
        
        for feedback in feedbacks:
            performance.total_feedback_count += 1
            
            # Track task outcomes
            if feedback.context.task_id:
                if feedback.feedback_type == FeedbackType.TASK_SUCCESS:
                    task_outcomes["success"] += 1
                elif feedback.feedback_type in [FeedbackType.TASK_FAILURE, FeedbackType.ERROR_REPORT]:
                    task_outcomes["failure"] += 1
                else:
                    task_outcomes["partial"] += 1
            
            # Collect metrics
            if feedback.metrics.execution_time is not None:
                execution_times.append(feedback.metrics.execution_time)
            
            if feedback.metrics.quality_score is not None:
                quality_scores.append(feedback.metrics.quality_score)
            
            if feedback.metrics.tokens_used is not None:
                tokens_used.append(feedback.metrics.tokens_used)
            
            # Track severity and category
            performance.severity_distribution[feedback.severity.value] = \
                performance.severity_distribution.get(feedback.severity.value, 0) + 1
            
            performance.category_distribution[feedback.category.value] = \
                performance.category_distribution.get(feedback.category.value, 0) + 1
        
        # Calculate aggregated metrics
        performance.total_tasks = sum(task_outcomes.values())
        performance.successful_tasks = task_outcomes["success"]
        performance.failed_tasks = task_outcomes["failure"]
        
        if performance.total_tasks > 0:
            performance.success_rate = performance.successful_tasks / performance.total_tasks
            performance.error_rate = performance.failed_tasks / performance.total_tasks
        
        if execution_times:
            performance.average_execution_time = statistics.mean(execution_times)
        
        if quality_scores:
            performance.average_quality_score = statistics.mean(quality_scores)
        
        if tokens_used:
            performance.average_tokens_used = int(statistics.mean(tokens_used))
        
        # Analyze recent trend
        performance.recent_trend = self._analyze_performance_trend(feedbacks)
        
        return performance
    
    def analyze_task(self, task_id: str) -> TaskAnalysis:
        """Analyze feedback for a specific task.
        
        Args:
            task_id: Task to analyze
            
        Returns:
            Task analysis results
        """
        feedbacks = self.storage.query(task_id=task_id)
        
        analysis = TaskAnalysis(task_id=task_id)
        analysis.feedback_count = len(feedbacks)
        
        if not feedbacks:
            return analysis
        
        # Determine task success
        success_count = sum(1 for f in feedbacks if f.feedback_type == FeedbackType.TASK_SUCCESS)
        failure_count = sum(1 for f in feedbacks if f.feedback_type == FeedbackType.TASK_FAILURE)
        
        analysis.success = success_count > 0 and failure_count == 0
        
        # Collect metrics and messages
        execution_times = []
        quality_scores = []
        
        for feedback in feedbacks:
            # Collect error messages
            if feedback.severity in [FeedbackSeverity.ERROR, FeedbackSeverity.CRITICAL]:
                analysis.error_messages.append(feedback.message)
            elif feedback.severity == FeedbackSeverity.WARNING:
                analysis.warnings.append(feedback.message)
            
            # Collect metrics
            if feedback.metrics.execution_time is not None:
                execution_times.append(feedback.metrics.execution_time)
            
            if feedback.metrics.quality_score is not None:
                quality_scores.append(feedback.metrics.quality_score)
            
            # Resource usage
            if feedback.metrics.memory_usage is not None:
                analysis.resource_usage["memory"] = feedback.metrics.memory_usage
            
            if feedback.metrics.cpu_usage is not None:
                analysis.resource_usage["cpu"] = feedback.metrics.cpu_usage
            
            # Related tasks
            if feedback.context.parent_task_id:
                analysis.related_tasks.append(feedback.context.parent_task_id)
        
        # Calculate averages
        if execution_times:
            analysis.execution_time = statistics.mean(execution_times)
        
        if quality_scores:
            analysis.quality_score = statistics.mean(quality_scores)
        
        return analysis
    
    def analyze_trends(self,
                      period: str = "daily",
                      time_range: Optional[Tuple[datetime, datetime]] = None) -> TrendAnalysis:
        """Analyze feedback trends over time.
        
        Args:
            period: Analysis period (daily, weekly, monthly)
            time_range: Time range to analyze
            
        Returns:
            Trend analysis results
        """
        if not time_range:
            end_time = datetime.now()
            if period == "daily":
                start_time = end_time - timedelta(days=30)
            elif period == "weekly":
                start_time = end_time - timedelta(weeks=12)
            else:  # monthly
                start_time = end_time - timedelta(days=365)
            time_range = (start_time, end_time)
        
        feedbacks = self.storage.query(
            start_time=time_range[0],
            end_time=time_range[1]
        )
        
        trend = TrendAnalysis(
            period=period,
            start_date=time_range[0],
            end_date=time_range[1],
            total_feedback=len(feedbacks)
        )
        
        if not feedbacks:
            return trend
        
        # Group feedback by period
        period_data = defaultdict(list)
        
        for feedback in feedbacks:
            if period == "daily":
                key = feedback.timestamp.date()
            elif period == "weekly":
                key = feedback.timestamp.isocalendar()[1]  # Week number
            else:  # monthly
                key = (feedback.timestamp.year, feedback.timestamp.month)
            
            period_data[key].append(feedback)
        
        # Analyze each period
        for period_key in sorted(period_data.keys()):
            period_feedbacks = period_data[period_key]
            
            # Calculate metrics for period
            success_count = sum(1 for f in period_feedbacks 
                              if f.feedback_type == FeedbackType.TASK_SUCCESS)
            total_tasks = sum(1 for f in period_feedbacks 
                            if f.feedback_type in [FeedbackType.TASK_SUCCESS, 
                                                 FeedbackType.TASK_FAILURE])
            
            if total_tasks > 0:
                trend.success_rate_trend.append(success_count / total_tasks)
                trend.error_rate_trend.append(1 - (success_count / total_tasks))
            
            # Performance metrics
            exec_times = [f.metrics.execution_time for f in period_feedbacks 
                         if f.metrics.execution_time is not None]
            if exec_times:
                trend.performance_trend.append(statistics.mean(exec_times))
            
            # Quality metrics
            quality_scores = [f.metrics.quality_score for f in period_feedbacks 
                            if f.metrics.quality_score is not None]
            if quality_scores:
                trend.quality_trend.append(statistics.mean(quality_scores))
        
        # Find peak periods
        period_counts = [(k, len(v)) for k, v in period_data.items()]
        period_counts.sort(key=lambda x: x[1], reverse=True)
        
        for period_key, count in period_counts[:5]:  # Top 5 peaks
            if isinstance(period_key, tuple):  # Monthly
                peak_date = datetime(period_key[0], period_key[1], 1)
            else:
                peak_date = datetime.combine(period_key, datetime.min.time())
            trend.peak_periods.append((peak_date, count))
        
        return trend
    
    def get_comprehensive_insights(self,
                                 time_range: Optional[Tuple[datetime, datetime]] = None) -> FeedbackInsights:
        """Get comprehensive insights from all feedback data.
        
        Args:
            time_range: Optional time range filter
            
        Returns:
            Comprehensive feedback insights
        """
        query_params = {}
        if time_range:
            query_params["start_time"] = time_range[0]
            query_params["end_time"] = time_range[1]
        
        feedbacks = self.storage.query(**query_params)
        
        insights = FeedbackInsights(
            total_feedback=len(feedbacks),
            time_period=time_range
        )
        
        if not feedbacks:
            return insights
        
        # Calculate overall metrics
        success_count = sum(1 for f in feedbacks 
                          if f.feedback_type == FeedbackType.TASK_SUCCESS)
        failure_count = sum(1 for f in feedbacks 
                          if f.feedback_type == FeedbackType.TASK_FAILURE)
        total_tasks = success_count + failure_count
        
        if total_tasks > 0:
            insights.overall_success_rate = success_count / total_tasks
            insights.overall_error_rate = failure_count / total_tasks
        
        # Aggregate metrics
        execution_times = []
        quality_scores = []
        error_messages = []
        
        # Worker performance tracking
        worker_metrics = defaultdict(lambda: {"success": 0, "failure": 0, "total": 0})
        
        # Task performance tracking
        task_execution_times = defaultdict(list)
        
        for feedback in feedbacks:
            # Collect metrics
            if feedback.metrics.execution_time is not None:
                execution_times.append(feedback.metrics.execution_time)
                if feedback.context.task_id:
                    task_execution_times[feedback.context.task_id].append(
                        feedback.metrics.execution_time
                    )
            
            if feedback.metrics.quality_score is not None:
                quality_scores.append(feedback.metrics.quality_score)
            
            # Collect errors
            if feedback.feedback_type == FeedbackType.ERROR_REPORT:
                error_messages.append(feedback.message)
            
            # Track worker performance
            if feedback.context.worker_id:
                worker_id = feedback.context.worker_id
                worker_metrics[worker_id]["total"] += 1
                
                if feedback.feedback_type == FeedbackType.TASK_SUCCESS:
                    worker_metrics[worker_id]["success"] += 1
                elif feedback.feedback_type == FeedbackType.TASK_FAILURE:
                    worker_metrics[worker_id]["failure"] += 1
        
        # Calculate averages
        if execution_times:
            insights.average_execution_time = statistics.mean(execution_times)
        
        if quality_scores:
            insights.average_quality_score = statistics.mean(quality_scores)
        
        # Find most common errors
        if error_messages:
            error_counter = Counter(error_messages)
            insights.most_common_errors = error_counter.most_common(10)
        
        # Identify bottleneck tasks (slow execution)
        if task_execution_times:
            avg_task_times = {
                task_id: statistics.mean(times)
                for task_id, times in task_execution_times.items()
                if times
            }
            
            if avg_task_times:
                overall_avg = statistics.mean(avg_task_times.values())
                threshold = overall_avg * 2  # Tasks taking 2x average time
                
                insights.bottleneck_tasks = [
                    task_id for task_id, avg_time in avg_task_times.items()
                    if avg_time > threshold
                ]
        
        # Identify high/low performing workers
        worker_performance = []
        for worker_id, metrics in worker_metrics.items():
            if metrics["total"] >= 5:  # Minimum tasks for evaluation
                success_rate = metrics["success"] / metrics["total"]
                worker_performance.append((worker_id, success_rate))
        
        if worker_performance:
            worker_performance.sort(key=lambda x: x[1], reverse=True)
            
            # Top 20% are high performers
            high_performer_count = max(1, len(worker_performance) // 5)
            insights.high_performing_workers = [
                w[0] for w in worker_performance[:high_performer_count]
            ]
            
            # Bottom 20% are problematic
            insights.problematic_workers = [
                w[0] for w in worker_performance[-high_performer_count:]
                if w[1] < 0.5  # Less than 50% success rate
            ]
        
        # Generate recommendations
        insights.recommendations = self._generate_recommendations(insights)
        
        return insights
    
    def _analyze_performance_trend(self, feedbacks: List[FeedbackModel]) -> str:
        """Analyze performance trend from feedback.
        
        Args:
            feedbacks: List of feedback to analyze
            
        Returns:
            Trend indicator (improving, declining, stable)
        """
        if len(feedbacks) < 10:
            return "stable"
        
        # Sort by timestamp
        sorted_feedback = sorted(feedbacks, key=lambda f: f.timestamp)
        
        # Split into two halves
        mid_point = len(sorted_feedback) // 2
        first_half = sorted_feedback[:mid_point]
        second_half = sorted_feedback[mid_point:]
        
        # Calculate success rates
        def calc_success_rate(feedback_list):
            success = sum(1 for f in feedback_list 
                        if f.feedback_type == FeedbackType.TASK_SUCCESS)
            total = sum(1 for f in feedback_list 
                      if f.feedback_type in [FeedbackType.TASK_SUCCESS, 
                                           FeedbackType.TASK_FAILURE])
            return success / total if total > 0 else 0
        
        first_rate = calc_success_rate(first_half)
        second_rate = calc_success_rate(second_half)
        
        # Determine trend
        if second_rate > first_rate + 0.1:
            return "improving"
        elif second_rate < first_rate - 0.1:
            return "declining"
        else:
            return "stable"
    
    def _generate_recommendations(self, insights: FeedbackInsights) -> List[str]:
        """Generate recommendations based on insights.
        
        Args:
            insights: Feedback insights
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Success rate recommendations
        if insights.overall_success_rate < 0.7:
            recommendations.append(
                f"Overall success rate is {insights.overall_success_rate:.1%}. "
                "Consider reviewing task complexity and worker allocation strategies."
            )
        
        # Error rate recommendations
        if insights.overall_error_rate > 0.2:
            recommendations.append(
                f"High error rate detected ({insights.overall_error_rate:.1%}). "
                "Review common errors and implement preventive measures."
            )
        
        # Performance recommendations
        if insights.bottleneck_tasks:
            recommendations.append(
                f"Found {len(insights.bottleneck_tasks)} bottleneck tasks. "
                "Consider optimizing or parallelizing these tasks."
            )
        
        # Worker recommendations
        if insights.problematic_workers:
            recommendations.append(
                f"Identified {len(insights.problematic_workers)} underperforming workers. "
                "Consider additional training or task reallocation."
            )
        
        if insights.high_performing_workers:
            recommendations.append(
                f"Leverage {len(insights.high_performing_workers)} high-performing workers "
                "for critical or complex tasks."
            )
        
        # Quality recommendations
        if insights.average_quality_score < 0.7:
            recommendations.append(
                "Average quality score is below threshold. "
                "Implement quality checks and validation processes."
            )
        
        # Error pattern recommendations
        if insights.most_common_errors:
            top_error = insights.most_common_errors[0]
            recommendations.append(
                f"Most common error: '{top_error[0][:50]}...' "
                f"(occurred {top_error[1]} times). Address this issue priority."
            )
        
        return recommendations
    
    def export_analysis_report(self,
                             output_path: str,
                             time_range: Optional[Tuple[datetime, datetime]] = None) -> None:
        """Export comprehensive analysis report.
        
        Args:
            output_path: Path to save report
            time_range: Time range for analysis
        """
        import json
        
        # Gather all analysis data
        insights = self.get_comprehensive_insights(time_range)
        trends = self.analyze_trends(time_range=time_range)
        
        # Get worker performances
        worker_performances = []
        for worker_id in set(f.context.worker_id for f in 
                           self.storage.query(**{"start_time": time_range[0], 
                                               "end_time": time_range[1]} 
                                             if time_range else {})
                           if f.context.worker_id):
            perf = self.analyze_worker_performance(worker_id, time_range)
            worker_performances.append({
                "worker_id": perf.worker_id,
                "success_rate": perf.success_rate,
                "average_execution_time": perf.average_execution_time,
                "total_tasks": perf.total_tasks
            })
        
        # Create report
        report = {
            "generated_at": datetime.now().isoformat(),
            "time_range": {
                "start": time_range[0].isoformat() if time_range else None,
                "end": time_range[1].isoformat() if time_range else None
            },
            "insights": {
                "total_feedback": insights.total_feedback,
                "overall_success_rate": insights.overall_success_rate,
                "overall_error_rate": insights.overall_error_rate,
                "average_execution_time": insights.average_execution_time,
                "average_quality_score": insights.average_quality_score,
                "recommendations": insights.recommendations
            },
            "trends": {
                "period": trends.period,
                "success_rate_trend": trends.success_rate_trend,
                "error_rate_trend": trends.error_rate_trend,
                "performance_trend": trends.performance_trend
            },
            "worker_performances": worker_performances,
            "bottleneck_tasks": insights.bottleneck_tasks,
            "most_common_errors": insights.most_common_errors
        }
        
        # Save report
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Analysis report exported to {output_path}")