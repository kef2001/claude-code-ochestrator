"""
Feedback Analysis Module

This module provides comprehensive analysis of collected feedback data,
including sentiment analysis, trend detection, statistical analysis,
and insights generation.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import statistics
import json
from enum import Enum

from .feedback_models import FeedbackEntry, FeedbackType, RatingScale
from .feedback_storage import FeedbackStorage
from .feedback_collector import FeedbackCollector, CollectionPoint


logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Direction of a trend"""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"


class InsightPriority(Enum):
    """Priority level for insights"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FeedbackMetrics:
    """Metrics calculated from feedback analysis"""
    total_count: int
    average_rating: Optional[float]
    rating_distribution: Dict[int, int]  # rating value -> count
    sentiment_scores: Dict[str, float]  # positive, negative, neutral percentages
    response_rate: float  # percentage of tasks with feedback
    common_themes: List[Tuple[str, int]]  # theme -> occurrence count
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "total_count": self.total_count,
            "average_rating": self.average_rating,
            "rating_distribution": self.rating_distribution,
            "sentiment_scores": self.sentiment_scores,
            "response_rate": self.response_rate,
            "common_themes": self.common_themes
        }


@dataclass
class TrendData:
    """Data about a detected trend"""
    metric_name: str
    direction: TrendDirection
    start_date: datetime
    end_date: datetime
    change_percentage: float
    confidence: float  # 0-1 confidence in the trend
    data_points: List[Tuple[datetime, float]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "metric_name": self.metric_name,
            "direction": self.direction.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "change_percentage": self.change_percentage,
            "confidence": self.confidence,
            "data_points": [(dt.isoformat(), val) for dt, val in self.data_points]
        }


@dataclass
class AnalysisInsight:
    """An actionable insight from feedback analysis"""
    insight_type: str
    title: str
    description: str
    priority: InsightPriority
    affected_entities: List[str]  # workers, tasks, etc.
    recommended_action: str
    supporting_data: Dict[str, Any]
    confidence: float  # 0-1 confidence in the insight
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "insight_type": self.insight_type,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "affected_entities": self.affected_entities,
            "recommended_action": self.recommended_action,
            "supporting_data": self.supporting_data,
            "confidence": self.confidence
        }


@dataclass
class AnalysisResult:
    """Result of feedback analysis"""
    analysis_id: str
    timestamp: datetime
    period_start: datetime
    period_end: datetime
    metrics: FeedbackMetrics
    trends: List[TrendData]
    insights: List[AnalysisInsight]
    summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "analysis_id": self.analysis_id,
            "timestamp": self.timestamp.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metrics": self.metrics.to_dict(),
            "trends": [trend.to_dict() for trend in self.trends],
            "insights": [insight.to_dict() for insight in self.insights],
            "summary": self.summary
        }


class FeedbackAnalyzer:
    """
    Analyzes feedback data to generate metrics, detect trends, and provide insights
    """
    
    def __init__(
        self,
        feedback_storage: Optional[FeedbackStorage] = None,
        min_data_points_for_trend: int = 5,
        trend_confidence_threshold: float = 0.7
    ):
        """
        Initialize the feedback analyzer
        
        Args:
            feedback_storage: FeedbackStorage instance
            min_data_points_for_trend: Minimum data points needed to detect a trend
            trend_confidence_threshold: Minimum confidence to report a trend
        """
        self.feedback_storage = feedback_storage or FeedbackStorage()
        self.min_data_points_for_trend = min_data_points_for_trend
        self.trend_confidence_threshold = trend_confidence_threshold
        
        # Common themes/keywords to look for
        self.theme_keywords = {
            "performance": ["slow", "fast", "performance", "speed", "efficient"],
            "quality": ["quality", "accurate", "correct", "error", "bug", "issue"],
            "complexity": ["complex", "difficult", "simple", "easy", "straightforward"],
            "communication": ["clear", "unclear", "confusing", "helpful", "responsive"],
            "reliability": ["reliable", "unreliable", "stable", "crash", "fail"]
        }
        
        logger.info("Initialized FeedbackAnalyzer")
    
    def analyze_feedback(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        feedback_types: Optional[List[FeedbackType]] = None,
        task_ids: Optional[List[str]] = None,
        worker_ids: Optional[List[str]] = None
    ) -> AnalysisResult:
        """
        Analyze feedback data for the specified period and filters
        
        Args:
            start_date: Start of analysis period (default: 30 days ago)
            end_date: End of analysis period (default: now)
            feedback_types: Filter by feedback types
            task_ids: Filter by specific task IDs
            worker_ids: Filter by specific worker IDs
            
        Returns:
            AnalysisResult with metrics, trends, and insights
        """
        # Set default date range
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=30)
        
        logger.info(f"Analyzing feedback from {start_date} to {end_date}")
        
        # Retrieve feedback data
        feedback_data = self._retrieve_feedback(
            start_date, end_date, feedback_types, task_ids, worker_ids
        )
        
        if not feedback_data:
            logger.warning("No feedback data found for analysis")
            return self._create_empty_result(start_date, end_date)
        
        # Calculate metrics
        metrics = self.calculate_metrics(feedback_data)
        
        # Detect trends
        trends = self.detect_trends(feedback_data)
        
        # Generate insights
        insights = self.generate_insights(feedback_data, metrics, trends)
        
        # Create summary
        summary = self._generate_summary(metrics, trends, insights)
        
        # Create and return result
        result = AnalysisResult(
            analysis_id=f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(),
            period_start=start_date,
            period_end=end_date,
            metrics=metrics,
            trends=trends,
            insights=insights,
            summary=summary
        )
        
        logger.info(f"Analysis complete. Found {len(trends)} trends and {len(insights)} insights")
        
        return result
    
    def calculate_metrics(self, feedback_list: List[FeedbackEntry]) -> FeedbackMetrics:
        """
        Calculate metrics from feedback data
        
        Args:
            feedback_list: List of feedback entries
            
        Returns:
            FeedbackMetrics object
        """
        total_count = len(feedback_list)
        
        # Calculate rating metrics
        ratings = [f.rating.value for f in feedback_list if f.rating]
        average_rating = statistics.mean(ratings) if ratings else None
        
        rating_distribution = Counter(ratings)
        rating_dist_dict = {i: rating_distribution.get(i, 0) for i in range(1, 6)}
        
        # Calculate sentiment scores
        sentiment_scores = self._calculate_sentiment_scores(feedback_list)
        
        # Calculate response rate (approximate based on task coverage)
        unique_tasks = set(f.task_id for f in feedback_list)
        # Assume we should have feedback for more tasks
        estimated_total_tasks = len(unique_tasks) * 1.5  # Rough estimate
        response_rate = len(unique_tasks) / estimated_total_tasks if estimated_total_tasks > 0 else 0
        
        # Extract common themes
        common_themes = self._extract_common_themes(feedback_list)
        
        return FeedbackMetrics(
            total_count=total_count,
            average_rating=average_rating,
            rating_distribution=rating_dist_dict,
            sentiment_scores=sentiment_scores,
            response_rate=response_rate,
            common_themes=common_themes
        )
    
    def detect_trends(self, feedback_list: List[FeedbackEntry]) -> List[TrendData]:
        """
        Detect trends in feedback data over time
        
        Args:
            feedback_list: List of feedback entries
            
        Returns:
            List of detected trends
        """
        trends = []
        
        # Group feedback by date
        feedback_by_date = defaultdict(list)
        for feedback in feedback_list:
            date_key = feedback.timestamp.date()
            feedback_by_date[date_key].append(feedback)
        
        # Sort dates
        sorted_dates = sorted(feedback_by_date.keys())
        
        if len(sorted_dates) < self.min_data_points_for_trend:
            logger.info(f"Not enough data points for trend detection ({len(sorted_dates)} < {self.min_data_points_for_trend})")
            return trends
        
        # Analyze rating trends
        rating_trend = self._analyze_rating_trend(feedback_by_date, sorted_dates)
        if rating_trend:
            trends.append(rating_trend)
        
        # Analyze volume trends
        volume_trend = self._analyze_volume_trend(feedback_by_date, sorted_dates)
        if volume_trend:
            trends.append(volume_trend)
        
        # Analyze sentiment trends
        sentiment_trend = self._analyze_sentiment_trend(feedback_by_date, sorted_dates)
        if sentiment_trend:
            trends.append(sentiment_trend)
        
        # Analyze performance trends (task completion times)
        performance_trend = self._analyze_performance_trend(feedback_by_date, sorted_dates)
        if performance_trend:
            trends.append(performance_trend)
        
        return trends
    
    def generate_insights(
        self,
        feedback_list: List[FeedbackEntry],
        metrics: FeedbackMetrics,
        trends: List[TrendData]
    ) -> List[AnalysisInsight]:
        """
        Generate actionable insights from feedback analysis
        
        Args:
            feedback_list: List of feedback entries
            metrics: Calculated metrics
            trends: Detected trends
            
        Returns:
            List of insights
        """
        insights = []
        
        # Check for low ratings
        if metrics.average_rating and metrics.average_rating < 3.0:
            insights.append(self._create_low_rating_insight(metrics, feedback_list))
        
        # Check for declining trends
        declining_trends = [t for t in trends if t.direction == TrendDirection.DECLINING]
        if declining_trends:
            insights.append(self._create_declining_trend_insight(declining_trends))
        
        # Check for poor performing workers
        worker_insights = self._analyze_worker_performance(feedback_list)
        insights.extend(worker_insights)
        
        # Check for problematic task types
        task_insights = self._analyze_task_patterns(feedback_list)
        insights.extend(task_insights)
        
        # Check for common issues in themes
        theme_insights = self._analyze_theme_patterns(metrics.common_themes, feedback_list)
        insights.extend(theme_insights)
        
        # Check response rate
        if metrics.response_rate < 0.5:
            insights.append(self._create_low_response_rate_insight(metrics))
        
        return insights
    
    def _retrieve_feedback(
        self,
        start_date: datetime,
        end_date: datetime,
        feedback_types: Optional[List[FeedbackType]],
        task_ids: Optional[List[str]],
        worker_ids: Optional[List[str]]
    ) -> List[FeedbackEntry]:
        """Retrieve feedback from storage with filters"""
        all_feedback = self.feedback_storage.list_feedback(limit=10000)
        
        filtered_feedback = []
        for feedback in all_feedback:
            # Date filter
            if feedback.timestamp < start_date or feedback.timestamp > end_date:
                continue
            
            # Type filter
            if feedback_types and feedback.feedback_type not in feedback_types:
                continue
            
            # Task filter
            if task_ids and feedback.task_id not in task_ids:
                continue
            
            # Worker filter
            if worker_ids and feedback.user_id not in worker_ids:
                continue
            
            filtered_feedback.append(feedback)
        
        return filtered_feedback
    
    def _calculate_sentiment_scores(self, feedback_list: List[FeedbackEntry]) -> Dict[str, float]:
        """Calculate sentiment distribution from feedback content"""
        positive_keywords = ["excellent", "great", "good", "perfect", "successful", "efficient", "fast"]
        negative_keywords = ["poor", "bad", "slow", "failed", "error", "issue", "problem"]
        
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for feedback in feedback_list:
            content_lower = feedback.content.lower()
            
            has_positive = any(keyword in content_lower for keyword in positive_keywords)
            has_negative = any(keyword in content_lower for keyword in negative_keywords)
            
            if has_positive and not has_negative:
                positive_count += 1
            elif has_negative and not has_positive:
                negative_count += 1
            else:
                neutral_count += 1
        
        total = len(feedback_list)
        return {
            "positive": positive_count / total if total > 0 else 0,
            "negative": negative_count / total if total > 0 else 0,
            "neutral": neutral_count / total if total > 0 else 0
        }
    
    def _extract_common_themes(self, feedback_list: List[FeedbackEntry]) -> List[Tuple[str, int]]:
        """Extract common themes from feedback content"""
        theme_counts = defaultdict(int)
        
        for feedback in feedback_list:
            content_lower = feedback.content.lower()
            
            for theme, keywords in self.theme_keywords.items():
                if any(keyword in content_lower for keyword in keywords):
                    theme_counts[theme] += 1
        
        # Sort by count and return top themes
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_themes[:5]  # Top 5 themes
    
    def _analyze_rating_trend(
        self,
        feedback_by_date: Dict[Any, List[FeedbackEntry]],
        sorted_dates: List[Any]
    ) -> Optional[TrendData]:
        """Analyze trend in average ratings over time"""
        data_points = []
        
        for date in sorted_dates:
            daily_feedback = feedback_by_date[date]
            daily_ratings = [f.rating.value for f in daily_feedback if f.rating]
            
            if daily_ratings:
                avg_rating = statistics.mean(daily_ratings)
                data_points.append((datetime.combine(date, datetime.min.time()), avg_rating))
        
        if len(data_points) < self.min_data_points_for_trend:
            return None
        
        # Calculate trend direction
        first_half_avg = statistics.mean([dp[1] for dp in data_points[:len(data_points)//2]])
        second_half_avg = statistics.mean([dp[1] for dp in data_points[len(data_points)//2:]])
        
        change_percentage = ((second_half_avg - first_half_avg) / first_half_avg) * 100
        
        if abs(change_percentage) < 5:
            direction = TrendDirection.STABLE
        elif change_percentage > 0:
            direction = TrendDirection.IMPROVING
        else:
            direction = TrendDirection.DECLINING
        
        # Calculate confidence based on data consistency
        all_values = [dp[1] for dp in data_points]
        std_dev = statistics.stdev(all_values) if len(all_values) > 1 else 0
        mean_val = statistics.mean(all_values)
        cv = std_dev / mean_val if mean_val > 0 else 0  # Coefficient of variation
        
        confidence = max(0, min(1, 1 - cv))  # Lower CV = higher confidence
        
        if confidence < self.trend_confidence_threshold:
            return None
        
        return TrendData(
            metric_name="Average Rating",
            direction=direction,
            start_date=data_points[0][0],
            end_date=data_points[-1][0],
            change_percentage=change_percentage,
            confidence=confidence,
            data_points=data_points
        )
    
    def _analyze_volume_trend(
        self,
        feedback_by_date: Dict[Any, List[FeedbackEntry]],
        sorted_dates: List[Any]
    ) -> Optional[TrendData]:
        """Analyze trend in feedback volume over time"""
        data_points = []
        
        for date in sorted_dates:
            daily_count = len(feedback_by_date[date])
            data_points.append((datetime.combine(date, datetime.min.time()), float(daily_count)))
        
        if len(data_points) < self.min_data_points_for_trend:
            return None
        
        # Similar trend calculation as rating trend
        first_half_avg = statistics.mean([dp[1] for dp in data_points[:len(data_points)//2]])
        second_half_avg = statistics.mean([dp[1] for dp in data_points[len(data_points)//2:]])
        
        if first_half_avg == 0:
            return None
        
        change_percentage = ((second_half_avg - first_half_avg) / first_half_avg) * 100
        
        if abs(change_percentage) < 10:
            direction = TrendDirection.STABLE
        elif change_percentage > 0:
            direction = TrendDirection.IMPROVING
        else:
            direction = TrendDirection.DECLINING
        
        return TrendData(
            metric_name="Feedback Volume",
            direction=direction,
            start_date=data_points[0][0],
            end_date=data_points[-1][0],
            change_percentage=change_percentage,
            confidence=0.8,  # Volume trends are generally reliable
            data_points=data_points
        )
    
    def _analyze_sentiment_trend(
        self,
        feedback_by_date: Dict[Any, List[FeedbackEntry]],
        sorted_dates: List[Any]
    ) -> Optional[TrendData]:
        """Analyze trend in sentiment scores over time"""
        data_points = []
        
        for date in sorted_dates:
            daily_feedback = feedback_by_date[date]
            daily_sentiment = self._calculate_sentiment_scores(daily_feedback)
            
            # Use positive sentiment percentage as the metric
            positive_pct = daily_sentiment["positive"]
            data_points.append((datetime.combine(date, datetime.min.time()), positive_pct))
        
        if len(data_points) < self.min_data_points_for_trend:
            return None
        
        # Calculate trend
        first_half_avg = statistics.mean([dp[1] for dp in data_points[:len(data_points)//2]])
        second_half_avg = statistics.mean([dp[1] for dp in data_points[len(data_points)//2:]])
        
        if first_half_avg == 0:
            change_percentage = 100 if second_half_avg > 0 else 0
        else:
            change_percentage = ((second_half_avg - first_half_avg) / first_half_avg) * 100
        
        if abs(change_percentage) < 5:
            direction = TrendDirection.STABLE
        elif change_percentage > 0:
            direction = TrendDirection.IMPROVING
        else:
            direction = TrendDirection.DECLINING
        
        return TrendData(
            metric_name="Positive Sentiment",
            direction=direction,
            start_date=data_points[0][0],
            end_date=data_points[-1][0],
            change_percentage=change_percentage,
            confidence=0.75,
            data_points=data_points
        )
    
    def _analyze_performance_trend(
        self,
        feedback_by_date: Dict[Any, List[FeedbackEntry]],
        sorted_dates: List[Any]
    ) -> Optional[TrendData]:
        """Analyze trend in task performance (execution times)"""
        data_points = []
        
        for date in sorted_dates:
            daily_feedback = feedback_by_date[date]
            
            # Extract execution times from feedback metadata
            execution_times = []
            for feedback in daily_feedback:
                if feedback.metadata and feedback.metadata.context.get("execution_time"):
                    execution_times.append(feedback.metadata.context["execution_time"])
            
            if execution_times:
                avg_time = statistics.mean(execution_times)
                data_points.append((datetime.combine(date, datetime.min.time()), avg_time))
        
        if len(data_points) < self.min_data_points_for_trend:
            return None
        
        # Calculate trend (for execution time, decreasing is good)
        first_half_avg = statistics.mean([dp[1] for dp in data_points[:len(data_points)//2]])
        second_half_avg = statistics.mean([dp[1] for dp in data_points[len(data_points)//2:]])
        
        change_percentage = ((second_half_avg - first_half_avg) / first_half_avg) * 100
        
        # Reverse direction for execution time (decreasing time = improving)
        if abs(change_percentage) < 5:
            direction = TrendDirection.STABLE
        elif change_percentage < 0:
            direction = TrendDirection.IMPROVING
        else:
            direction = TrendDirection.DECLINING
        
        return TrendData(
            metric_name="Average Execution Time",
            direction=direction,
            start_date=data_points[0][0],
            end_date=data_points[-1][0],
            change_percentage=change_percentage,
            confidence=0.7,
            data_points=data_points
        )
    
    def _create_low_rating_insight(
        self,
        metrics: FeedbackMetrics,
        feedback_list: List[FeedbackEntry]
    ) -> AnalysisInsight:
        """Create insight for low average rating"""
        # Find common issues in low-rated feedback
        low_rated = [f for f in feedback_list if f.rating and f.rating.value <= 2]
        
        common_issues = []
        if low_rated:
            # Extract common words from low-rated feedback
            issue_words = defaultdict(int)
            for feedback in low_rated:
                words = feedback.content.lower().split()
                for word in words:
                    if len(word) > 4:  # Skip short words
                        issue_words[word] += 1
            
            common_issues = sorted(issue_words.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return AnalysisInsight(
            insight_type="low_rating_alert",
            title="Low Average Rating Detected",
            description=f"The average rating of {metrics.average_rating:.2f} is below acceptable levels",
            priority=InsightPriority.HIGH,
            affected_entities=[],
            recommended_action="Review low-rated feedback to identify and address common issues",
            supporting_data={
                "average_rating": metrics.average_rating,
                "low_rated_count": len(low_rated),
                "common_issues": common_issues
            },
            confidence=0.9
        )
    
    def _create_declining_trend_insight(self, declining_trends: List[TrendData]) -> AnalysisInsight:
        """Create insight for declining trends"""
        most_severe = max(declining_trends, key=lambda t: abs(t.change_percentage))
        
        return AnalysisInsight(
            insight_type="declining_trend_alert",
            title=f"Declining Trend in {most_severe.metric_name}",
            description=f"{most_severe.metric_name} has declined by {abs(most_severe.change_percentage):.1f}%",
            priority=InsightPriority.HIGH,
            affected_entities=[],
            recommended_action="Investigate recent changes that may have caused this decline",
            supporting_data={
                "metric": most_severe.metric_name,
                "change_percentage": most_severe.change_percentage,
                "trend_period": f"{most_severe.start_date.date()} to {most_severe.end_date.date()}"
            },
            confidence=most_severe.confidence
        )
    
    def _analyze_worker_performance(self, feedback_list: List[FeedbackEntry]) -> List[AnalysisInsight]:
        """Analyze worker performance and identify issues"""
        insights = []
        
        # Group feedback by worker
        worker_feedback = defaultdict(list)
        for feedback in feedback_list:
            if feedback.metadata and feedback.metadata.context.get("worker_id"):
                worker_id = feedback.metadata.context["worker_id"]
                worker_feedback[worker_id].append(feedback)
        
        # Analyze each worker
        for worker_id, feedbacks in worker_feedback.items():
            worker_ratings = [f.rating.value for f in feedbacks if f.rating]
            
            if worker_ratings and len(worker_ratings) >= 5:  # Need enough data
                avg_rating = statistics.mean(worker_ratings)
                
                if avg_rating < 2.5:
                    insights.append(AnalysisInsight(
                        insight_type="poor_worker_performance",
                        title=f"Poor Performance: Worker {worker_id}",
                        description=f"Worker {worker_id} has an average rating of {avg_rating:.2f}",
                        priority=InsightPriority.MEDIUM,
                        affected_entities=[worker_id],
                        recommended_action="Consider additional training or task reallocation",
                        supporting_data={
                            "worker_id": worker_id,
                            "average_rating": avg_rating,
                            "feedback_count": len(feedbacks)
                        },
                        confidence=0.8
                    ))
        
        return insights
    
    def _analyze_task_patterns(self, feedback_list: List[FeedbackEntry]) -> List[AnalysisInsight]:
        """Analyze task patterns and identify problematic task types"""
        insights = []
        
        # Group by task characteristics
        task_feedback = defaultdict(list)
        for feedback in feedback_list:
            if feedback.metadata and feedback.metadata.context.get("task_complexity"):
                complexity = feedback.metadata.context["task_complexity"]
                task_feedback[complexity].append(feedback)
        
        # Analyze by complexity
        for complexity, feedbacks in task_feedback.items():
            ratings = [f.rating.value for f in feedbacks if f.rating]
            
            if ratings and len(ratings) >= 10:
                avg_rating = statistics.mean(ratings)
                
                if avg_rating < 3.0:
                    insights.append(AnalysisInsight(
                        insight_type="problematic_task_type",
                        title=f"Issues with {complexity} complexity tasks",
                        description=f"{complexity} tasks have low average rating of {avg_rating:.2f}",
                        priority=InsightPriority.MEDIUM,
                        affected_entities=[],
                        recommended_action=f"Review {complexity} task allocation and requirements",
                        supporting_data={
                            "task_complexity": complexity,
                            "average_rating": avg_rating,
                            "task_count": len(feedbacks)
                        },
                        confidence=0.75
                    ))
        
        return insights
    
    def _analyze_theme_patterns(
        self,
        common_themes: List[Tuple[str, int]],
        feedback_list: List[FeedbackEntry]
    ) -> List[AnalysisInsight]:
        """Analyze theme patterns for insights"""
        insights = []
        
        total_feedback = len(feedback_list)
        
        for theme, count in common_themes:
            percentage = (count / total_feedback) * 100
            
            # Create insights for prevalent themes
            if theme == "performance" and percentage > 30:
                insights.append(AnalysisInsight(
                    insight_type="performance_concerns",
                    title="High Performance Concerns",
                    description=f"{percentage:.1f}% of feedback mentions performance issues",
                    priority=InsightPriority.HIGH,
                    affected_entities=[],
                    recommended_action="Investigate and optimize system performance",
                    supporting_data={
                        "theme": theme,
                        "occurrence_percentage": percentage,
                        "count": count
                    },
                    confidence=0.85
                ))
            elif theme == "quality" and percentage > 25:
                insights.append(AnalysisInsight(
                    insight_type="quality_concerns",
                    title="Quality Issues Detected",
                    description=f"{percentage:.1f}% of feedback mentions quality concerns",
                    priority=InsightPriority.HIGH,
                    affected_entities=[],
                    recommended_action="Review quality assurance processes",
                    supporting_data={
                        "theme": theme,
                        "occurrence_percentage": percentage,
                        "count": count
                    },
                    confidence=0.85
                ))
        
        return insights
    
    def _create_low_response_rate_insight(self, metrics: FeedbackMetrics) -> AnalysisInsight:
        """Create insight for low response rate"""
        return AnalysisInsight(
            insight_type="low_response_rate",
            title="Low Feedback Response Rate",
            description=f"Only {metrics.response_rate:.1%} of tasks have feedback",
            priority=InsightPriority.MEDIUM,
            affected_entities=[],
            recommended_action="Improve feedback collection mechanisms and incentives",
            supporting_data={
                "response_rate": metrics.response_rate,
                "total_feedback": metrics.total_count
            },
            confidence=0.7
        )
    
    def _create_empty_result(self, start_date: datetime, end_date: datetime) -> AnalysisResult:
        """Create empty analysis result when no data is available"""
        return AnalysisResult(
            analysis_id=f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(),
            period_start=start_date,
            period_end=end_date,
            metrics=FeedbackMetrics(
                total_count=0,
                average_rating=None,
                rating_distribution={i: 0 for i in range(1, 6)},
                sentiment_scores={"positive": 0, "negative": 0, "neutral": 0},
                response_rate=0,
                common_themes=[]
            ),
            trends=[],
            insights=[],
            summary="No feedback data available for analysis"
        )
    
    def _generate_summary(
        self,
        metrics: FeedbackMetrics,
        trends: List[TrendData],
        insights: List[AnalysisInsight]
    ) -> str:
        """Generate executive summary of the analysis"""
        summary_parts = []
        
        # Overall metrics summary
        summary_parts.append(
            f"Analyzed {metrics.total_count} feedback entries with an average rating of "
            f"{metrics.average_rating:.2f}/5" if metrics.average_rating else 
            f"Analyzed {metrics.total_count} feedback entries"
        )
        
        # Sentiment summary
        if metrics.sentiment_scores["positive"] > 0.6:
            summary_parts.append("Overall sentiment is positive")
        elif metrics.sentiment_scores["negative"] > 0.4:
            summary_parts.append("Overall sentiment is negative")
        else:
            summary_parts.append("Overall sentiment is mixed")
        
        # Trends summary
        if trends:
            improving = sum(1 for t in trends if t.direction == TrendDirection.IMPROVING)
            declining = sum(1 for t in trends if t.direction == TrendDirection.DECLINING)
            
            if improving > 0:
                summary_parts.append(f"{improving} metrics showing improvement")
            if declining > 0:
                summary_parts.append(f"{declining} metrics showing decline")
        
        # Insights summary
        if insights:
            high_priority = sum(1 for i in insights if i.priority in [InsightPriority.HIGH, InsightPriority.CRITICAL])
            if high_priority > 0:
                summary_parts.append(f"{high_priority} high-priority issues require attention")
        
        return ". ".join(summary_parts) + "."
    
    def export_analysis_report(
        self,
        analysis_result: AnalysisResult,
        format: str = "json"
    ) -> str:
        """
        Export analysis report in specified format
        
        Args:
            analysis_result: Analysis result to export
            format: Export format (json, markdown)
            
        Returns:
            Formatted report string
        """
        if format == "json":
            return json.dumps(analysis_result.to_dict(), indent=2)
        elif format == "markdown":
            return self._generate_markdown_report(analysis_result)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _generate_markdown_report(self, result: AnalysisResult) -> str:
        """Generate markdown formatted report"""
        lines = [
            f"# Feedback Analysis Report",
            f"**Analysis ID:** {result.analysis_id}",
            f"**Generated:** {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Period:** {result.period_start.date()} to {result.period_end.date()}",
            "",
            f"## Summary",
            result.summary,
            "",
            f"## Metrics",
            f"- **Total Feedback:** {result.metrics.total_count}",
            f"- **Average Rating:** {result.metrics.average_rating:.2f}/5" if result.metrics.average_rating else "- **Average Rating:** N/A",
            f"- **Response Rate:** {result.metrics.response_rate:.1%}",
            "",
            f"### Sentiment Distribution",
            f"- Positive: {result.metrics.sentiment_scores['positive']:.1%}",
            f"- Neutral: {result.metrics.sentiment_scores['neutral']:.1%}",
            f"- Negative: {result.metrics.sentiment_scores['negative']:.1%}",
            ""
        ]
        
        if result.metrics.common_themes:
            lines.extend([
                f"### Common Themes",
                *[f"- {theme}: {count} occurrences" for theme, count in result.metrics.common_themes],
                ""
            ])
        
        if result.trends:
            lines.extend([
                f"## Trends",
                *[f"- **{trend.metric_name}**: {trend.direction.value} "
                  f"({trend.change_percentage:+.1f}% change)" for trend in result.trends],
                ""
            ])
        
        if result.insights:
            lines.extend([
                f"## Key Insights",
                *[f"### {insight.title}\n{insight.description}\n"
                  f"**Priority:** {insight.priority.value}\n"
                  f"**Recommended Action:** {insight.recommended_action}\n"
                  for insight in result.insights]
            ])
        
        return "\n".join(lines)
    
    def get_worker_performance_summary(self, worker_id: str) -> Dict[str, Any]:
        """
        Get performance summary for a specific worker
        
        Args:
            worker_id: Worker identifier
            
        Returns:
            Performance summary dictionary
        """
        # Get all feedback for this worker
        all_feedback = self.feedback_storage.list_feedback(limit=10000)
        worker_feedback = [
            f for f in all_feedback
            if f.metadata and f.metadata.context.get("worker_id") == worker_id
        ]
        
        if not worker_feedback:
            return {"worker_id": worker_id, "feedback_count": 0, "message": "No feedback found"}
        
        # Calculate metrics
        ratings = [f.rating.value for f in worker_feedback if f.rating]
        avg_rating = statistics.mean(ratings) if ratings else None
        
        # Task success rate
        successful_tasks = sum(
            1 for f in worker_feedback
            if f.metadata and f.metadata.context.get("success") is True
        )
        total_tasks = len(set(f.task_id for f in worker_feedback))
        success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0
        
        # Average execution time
        execution_times = [
            f.metadata.context["execution_time"]
            for f in worker_feedback
            if f.metadata and f.metadata.context.get("execution_time")
        ]
        avg_execution_time = statistics.mean(execution_times) if execution_times else None
        
        # Recent trend
        recent_feedback = sorted(worker_feedback, key=lambda f: f.timestamp, reverse=True)[:10]
        recent_ratings = [f.rating.value for f in recent_feedback if f.rating]
        recent_avg = statistics.mean(recent_ratings) if recent_ratings else None
        
        return {
            "worker_id": worker_id,
            "feedback_count": len(worker_feedback),
            "average_rating": avg_rating,
            "success_rate": success_rate,
            "average_execution_time": avg_execution_time,
            "recent_average_rating": recent_avg,
            "total_tasks": total_tasks,
            "performance_trend": self._calculate_performance_trend(avg_rating, recent_avg)
        }
    
    def _calculate_performance_trend(
        self,
        overall_avg: Optional[float],
        recent_avg: Optional[float]
    ) -> str:
        """Calculate performance trend based on overall vs recent average"""
        if overall_avg is None or recent_avg is None:
            return "unknown"
        
        diff = recent_avg - overall_avg
        if abs(diff) < 0.2:
            return "stable"
        elif diff > 0:
            return "improving"
        else:
            return "declining"


# Convenience functions
def analyze_recent_feedback(
    days: int = 30,
    storage: Optional[FeedbackStorage] = None
) -> AnalysisResult:
    """
    Analyze recent feedback for the specified number of days
    
    Args:
        days: Number of days to analyze
        storage: Optional feedback storage instance
        
    Returns:
        AnalysisResult
    """
    analyzer = FeedbackAnalyzer(feedback_storage=storage)
    start_date = datetime.now() - timedelta(days=days)
    
    return analyzer.analyze_feedback(start_date=start_date)


def get_worker_performance(
    worker_id: str,
    storage: Optional[FeedbackStorage] = None
) -> Dict[str, Any]:
    """
    Get performance summary for a specific worker
    
    Args:
        worker_id: Worker identifier
        storage: Optional feedback storage instance
        
    Returns:
        Performance summary
    """
    analyzer = FeedbackAnalyzer(feedback_storage=storage)
    return analyzer.get_worker_performance_summary(worker_id)