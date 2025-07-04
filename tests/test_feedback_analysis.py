"""
Unit tests for feedback analysis module

Tests the analysis algorithms, metrics calculation, trend detection,
and insights generation.
"""

import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import statistics

from claude_orchestrator.feedback_analysis import (
    FeedbackAnalyzer, FeedbackMetrics, TrendData, AnalysisInsight,
    AnalysisResult, TrendDirection, InsightPriority,
    analyze_recent_feedback, get_worker_performance
)
from claude_orchestrator.feedback_models import (
    FeedbackEntry, FeedbackType, RatingScale, FeedbackMetadata
)
from claude_orchestrator.feedback_storage import FeedbackStorage


class TestFeedbackAnalyzer:
    """Tests for FeedbackAnalyzer class"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.storage = FeedbackStorage(self.temp_db.name)
        self.analyzer = FeedbackAnalyzer(feedback_storage=self.storage)
    
    def teardown_method(self):
        """Clean up after test"""
        self.storage.close()
        os.unlink(self.temp_db.name)
    
    def _create_test_feedback(self, count=10, days_ago=0, rating_range=(3, 5)):
        """Helper to create test feedback entries"""
        feedback_list = []
        base_date = datetime.now() - timedelta(days=days_ago)
        
        for i in range(count):
            # Vary ratings
            rating_value = rating_range[0] + (i % (rating_range[1] - rating_range[0] + 1))
            
            feedback = FeedbackEntry(
                id=f"test-{days_ago}-{i}",
                task_id=f"task-{i % 5}",  # 5 different tasks
                timestamp=base_date + timedelta(hours=i),
                feedback_type=FeedbackType.TASK_COMPLETION,
                content=f"Test feedback {i}. Task completed successfully with good performance.",
                rating=RatingScale(rating_value),
                user_id=f"worker-{i % 3}",  # 3 different workers
                metadata=FeedbackMetadata(
                    source="test",
                    version="1.0",
                    context={
                        "worker_id": f"worker-{i % 3}",
                        "execution_time": 30.0 + (i * 2),
                        "success": True,
                        "task_complexity": "medium" if i % 2 == 0 else "high"
                    }
                )
            )
            
            self.storage.store_feedback(feedback)
            feedback_list.append(feedback)
        
        return feedback_list
    
    def test_initialization(self):
        """Test analyzer initialization"""
        assert self.analyzer.feedback_storage is not None
        assert self.analyzer.min_data_points_for_trend == 5
        assert self.analyzer.trend_confidence_threshold == 0.7
        assert len(self.analyzer.theme_keywords) > 0
    
    def test_analyze_feedback_empty(self):
        """Test analysis with no feedback data"""
        result = self.analyzer.analyze_feedback()
        
        assert isinstance(result, AnalysisResult)
        assert result.metrics.total_count == 0
        assert result.metrics.average_rating is None
        assert len(result.trends) == 0
        assert len(result.insights) == 0
        assert "No feedback data available" in result.summary
    
    def test_analyze_feedback_with_data(self):
        """Test analysis with feedback data"""
        # Create feedback over multiple days
        for days_ago in range(10):
            self._create_test_feedback(count=5, days_ago=days_ago)
        
        result = self.analyzer.analyze_feedback()
        
        assert result.metrics.total_count == 50
        assert result.metrics.average_rating is not None
        assert result.metrics.average_rating >= 3.0
        assert len(result.trends) > 0  # Should detect some trends
        assert result.summary != "No feedback data available for analysis"
    
    def test_calculate_metrics(self):
        """Test metrics calculation"""
        feedback_list = self._create_test_feedback(count=20)
        
        metrics = self.analyzer.calculate_metrics(feedback_list)
        
        assert isinstance(metrics, FeedbackMetrics)
        assert metrics.total_count == 20
        assert metrics.average_rating == 4.0  # With our test data pattern
        assert sum(metrics.rating_distribution.values()) == 20
        assert "positive" in metrics.sentiment_scores
        assert "negative" in metrics.sentiment_scores
        assert "neutral" in metrics.sentiment_scores
        assert sum(metrics.sentiment_scores.values()) == 1.0  # Should sum to 100%
        assert metrics.response_rate > 0
        assert len(metrics.common_themes) <= 5
    
    def test_rating_distribution(self):
        """Test rating distribution calculation"""
        # Create feedback with specific ratings
        feedback_list = []
        ratings = [1, 2, 2, 3, 3, 3, 4, 4, 5]
        
        for i, rating_val in enumerate(ratings):
            feedback = FeedbackEntry(
                id=f"test-{i}",
                task_id=f"task-{i}",
                timestamp=datetime.now(),
                feedback_type=FeedbackType.USER_RATING,
                content="Test",
                rating=RatingScale(rating_val)
            )
            feedback_list.append(feedback)
        
        metrics = self.analyzer.calculate_metrics(feedback_list)
        
        assert metrics.rating_distribution[1] == 1
        assert metrics.rating_distribution[2] == 2
        assert metrics.rating_distribution[3] == 3
        assert metrics.rating_distribution[4] == 2
        assert metrics.rating_distribution[5] == 1
    
    def test_sentiment_analysis(self):
        """Test sentiment score calculation"""
        # Create feedback with different sentiments
        positive_feedback = FeedbackEntry(
            id="pos-1",
            task_id="task-1",
            timestamp=datetime.now(),
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Excellent work! Task completed perfectly with great efficiency.",
            rating=RatingScale.EXCELLENT
        )
        
        negative_feedback = FeedbackEntry(
            id="neg-1",
            task_id="task-2",
            timestamp=datetime.now(),
            feedback_type=FeedbackType.ERROR_REPORT,
            content="Poor performance. Task failed with multiple errors and issues.",
            rating=RatingScale.POOR
        )
        
        neutral_feedback = FeedbackEntry(
            id="neu-1",
            task_id="task-3",
            timestamp=datetime.now(),
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Task completed as requested.",
            rating=RatingScale.GOOD
        )
        
        feedback_list = [positive_feedback, negative_feedback, neutral_feedback]
        
        scores = self.analyzer._calculate_sentiment_scores(feedback_list)
        
        assert scores["positive"] == 1/3
        assert scores["negative"] == 1/3
        assert scores["neutral"] == 1/3
    
    def test_theme_extraction(self):
        """Test common theme extraction"""
        # Create feedback with specific themes
        feedback_list = []
        
        for i in range(5):
            feedback = FeedbackEntry(
                id=f"perf-{i}",
                task_id=f"task-{i}",
                timestamp=datetime.now(),
                feedback_type=FeedbackType.WORKER_PERFORMANCE,
                content="Performance is slow and needs optimization for better speed."
            )
            feedback_list.append(feedback)
        
        for i in range(3):
            feedback = FeedbackEntry(
                id=f"qual-{i}",
                task_id=f"task-{i+5}",
                timestamp=datetime.now(),
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="High quality output with accurate results and no errors."
            )
            feedback_list.append(feedback)
        
        themes = self.analyzer._extract_common_themes(feedback_list)
        
        assert len(themes) > 0
        assert themes[0][0] == "performance"  # Most common theme
        assert themes[0][1] == 5  # Count
    
    def test_detect_trends_insufficient_data(self):
        """Test trend detection with insufficient data"""
        # Create only 3 days of data (less than minimum)
        for days_ago in range(3):
            self._create_test_feedback(count=5, days_ago=days_ago)
        
        feedback_list = self.storage.list_feedback(limit=1000)
        trends = self.analyzer.detect_trends(feedback_list)
        
        assert len(trends) == 0  # No trends due to insufficient data
    
    def test_detect_rating_trend(self):
        """Test rating trend detection"""
        # Create improving ratings over time
        for days_ago in range(10, 0, -1):
            rating_range = (2, 3) if days_ago > 5 else (4, 5)
            self._create_test_feedback(
                count=5,
                days_ago=days_ago,
                rating_range=rating_range
            )
        
        feedback_list = self.storage.list_feedback(limit=1000)
        trends = self.analyzer.detect_trends(feedback_list)
        
        # Find rating trend
        rating_trends = [t for t in trends if t.metric_name == "Average Rating"]
        assert len(rating_trends) > 0
        
        rating_trend = rating_trends[0]
        assert rating_trend.direction == TrendDirection.IMPROVING
        assert rating_trend.change_percentage > 0
        assert len(rating_trend.data_points) >= self.analyzer.min_data_points_for_trend
    
    def test_detect_volume_trend(self):
        """Test volume trend detection"""
        # Create increasing volume over time
        for days_ago in range(10, 0, -1):
            count = 2 if days_ago > 5 else 8
            self._create_test_feedback(count=count, days_ago=days_ago)
        
        feedback_list = self.storage.list_feedback(limit=1000)
        trends = self.analyzer.detect_trends(feedback_list)
        
        # Find volume trend
        volume_trends = [t for t in trends if t.metric_name == "Feedback Volume"]
        assert len(volume_trends) > 0
        
        volume_trend = volume_trends[0]
        assert volume_trend.direction == TrendDirection.IMPROVING
        assert volume_trend.change_percentage > 0
    
    def test_generate_insights_low_ratings(self):
        """Test insight generation for low ratings"""
        # Create feedback with low ratings
        feedback_list = []
        for i in range(10):
            feedback = FeedbackEntry(
                id=f"low-{i}",
                task_id=f"task-{i}",
                timestamp=datetime.now() - timedelta(days=i),
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="Poor performance with errors and slow execution.",
                rating=RatingScale(2)  # Low rating
            )
            self.storage.store_feedback(feedback)
            feedback_list.append(feedback)
        
        metrics = self.analyzer.calculate_metrics(feedback_list)
        insights = self.analyzer.generate_insights(feedback_list, metrics, [])
        
        # Should have low rating insight
        low_rating_insights = [i for i in insights if i.insight_type == "low_rating_alert"]
        assert len(low_rating_insights) > 0
        
        insight = low_rating_insights[0]
        assert insight.priority == InsightPriority.HIGH
        assert "Low Average Rating" in insight.title
    
    def test_generate_worker_performance_insights(self):
        """Test worker performance insights"""
        # Create poor performance for specific worker
        for i in range(10):
            feedback = FeedbackEntry(
                id=f"worker-poor-{i}",
                task_id=f"task-{i}",
                timestamp=datetime.now() - timedelta(days=i),
                feedback_type=FeedbackType.WORKER_PERFORMANCE,
                content="Worker performance below expectations.",
                rating=RatingScale(2),
                metadata=FeedbackMetadata(
                    source="test",
                    version="1.0",
                    context={"worker_id": "worker-poor"}
                )
            )
            self.storage.store_feedback(feedback)
        
        feedback_list = self.storage.list_feedback(limit=1000)
        metrics = self.analyzer.calculate_metrics(feedback_list)
        insights = self.analyzer.generate_insights(feedback_list, metrics, [])
        
        # Should have worker performance insight
        worker_insights = [i for i in insights if i.insight_type == "poor_worker_performance"]
        assert len(worker_insights) > 0
        
        insight = worker_insights[0]
        assert "worker-poor" in insight.affected_entities
        assert insight.priority == InsightPriority.MEDIUM
    
    def test_declining_trend_insight(self):
        """Test insight for declining trends"""
        # Create declining trend data
        trend = TrendData(
            metric_name="Average Rating",
            direction=TrendDirection.DECLINING,
            start_date=datetime.now() - timedelta(days=10),
            end_date=datetime.now(),
            change_percentage=-25.0,
            confidence=0.8,
            data_points=[]
        )
        
        insights = self.analyzer.generate_insights([], FeedbackMetrics(
            total_count=100,
            average_rating=3.5,
            rating_distribution={},
            sentiment_scores={},
            response_rate=0.8,
            common_themes=[]
        ), [trend])
        
        declining_insights = [i for i in insights if i.insight_type == "declining_trend_alert"]
        assert len(declining_insights) > 0
        
        insight = declining_insights[0]
        assert insight.priority == InsightPriority.HIGH
        assert "Declining Trend" in insight.title
    
    def test_export_json_report(self):
        """Test JSON report export"""
        self._create_test_feedback(count=10)
        
        result = self.analyzer.analyze_feedback()
        json_report = self.analyzer.export_analysis_report(result, format="json")
        
        # Verify it's valid JSON
        import json
        parsed = json.loads(json_report)
        
        assert parsed["analysis_id"] == result.analysis_id
        assert "metrics" in parsed
        assert "trends" in parsed
        assert "insights" in parsed
    
    def test_export_markdown_report(self):
        """Test markdown report export"""
        self._create_test_feedback(count=10)
        
        result = self.analyzer.analyze_feedback()
        md_report = self.analyzer.export_analysis_report(result, format="markdown")
        
        # Verify markdown structure
        assert "# Feedback Analysis Report" in md_report
        assert "## Summary" in md_report
        assert "## Metrics" in md_report
        assert result.analysis_id in md_report
    
    def test_get_worker_performance_summary(self):
        """Test worker performance summary"""
        # Create feedback for specific worker
        worker_id = "test-worker"
        
        for i in range(10):
            feedback = FeedbackEntry(
                id=f"worker-{i}",
                task_id=f"task-{i}",
                timestamp=datetime.now() - timedelta(days=i),
                feedback_type=FeedbackType.WORKER_PERFORMANCE,
                content="Worker completed task",
                rating=RatingScale(4),
                metadata=FeedbackMetadata(
                    source="test",
                    version="1.0",
                    context={
                        "worker_id": worker_id,
                        "success": True,
                        "execution_time": 30.0 + i
                    }
                )
            )
            self.storage.store_feedback(feedback)
        
        summary = self.analyzer.get_worker_performance_summary(worker_id)
        
        assert summary["worker_id"] == worker_id
        assert summary["feedback_count"] == 10
        assert summary["average_rating"] == 4.0
        assert summary["success_rate"] > 0
        assert summary["average_execution_time"] is not None
        assert summary["performance_trend"] in ["stable", "improving", "declining"]
    
    def test_worker_performance_no_data(self):
        """Test worker performance summary with no data"""
        summary = self.analyzer.get_worker_performance_summary("unknown-worker")
        
        assert summary["worker_id"] == "unknown-worker"
        assert summary["feedback_count"] == 0
        assert "No feedback found" in summary["message"]
    
    def test_date_filtering(self):
        """Test date range filtering in analysis"""
        # Create feedback across different dates
        for days_ago in range(20):
            self._create_test_feedback(count=2, days_ago=days_ago)
        
        # Analyze only last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        result = self.analyzer.analyze_feedback(
            start_date=start_date,
            end_date=end_date
        )
        
        # Should have approximately 14 feedback entries (2 per day for 7 days)
        assert result.metrics.total_count <= 16  # Allow some variance
        assert result.metrics.total_count >= 12
    
    def test_feedback_type_filtering(self):
        """Test filtering by feedback type"""
        # Create different types of feedback
        for i in range(5):
            feedback = FeedbackEntry(
                id=f"completion-{i}",
                task_id=f"task-{i}",
                timestamp=datetime.now(),
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="Task completed"
            )
            self.storage.store_feedback(feedback)
        
        for i in range(3):
            feedback = FeedbackEntry(
                id=f"error-{i}",
                task_id=f"task-{i}",
                timestamp=datetime.now(),
                feedback_type=FeedbackType.ERROR_REPORT,
                content="Error occurred"
            )
            self.storage.store_feedback(feedback)
        
        # Analyze only error reports
        result = self.analyzer.analyze_feedback(
            feedback_types=[FeedbackType.ERROR_REPORT]
        )
        
        assert result.metrics.total_count == 3
    
    def test_task_filtering(self):
        """Test filtering by task IDs"""
        # Create feedback for different tasks
        task_ids = ["task-A", "task-B", "task-C"]
        
        for task_id in task_ids:
            for i in range(3):
                feedback = FeedbackEntry(
                    id=f"{task_id}-{i}",
                    task_id=task_id,
                    timestamp=datetime.now(),
                    feedback_type=FeedbackType.TASK_COMPLETION,
                    content="Task feedback"
                )
                self.storage.store_feedback(feedback)
        
        # Analyze only specific tasks
        result = self.analyzer.analyze_feedback(
            task_ids=["task-A", "task-B"]
        )
        
        assert result.metrics.total_count == 6
    
    def test_performance_trend_calculation(self):
        """Test performance trend calculation logic"""
        # Test improving trend
        trend = self.analyzer._calculate_performance_trend(3.0, 4.0)
        assert trend == "improving"
        
        # Test declining trend
        trend = self.analyzer._calculate_performance_trend(4.0, 3.0)
        assert trend == "declining"
        
        # Test stable trend
        trend = self.analyzer._calculate_performance_trend(3.5, 3.6)
        assert trend == "stable"
        
        # Test with None values
        trend = self.analyzer._calculate_performance_trend(None, 3.0)
        assert trend == "unknown"


class TestConvenienceFunctions:
    """Tests for convenience functions"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.storage = FeedbackStorage(self.temp_db.name)
    
    def teardown_method(self):
        """Clean up after test"""
        self.storage.close()
        os.unlink(self.temp_db.name)
    
    def test_analyze_recent_feedback(self):
        """Test analyze_recent_feedback convenience function"""
        # Create some test feedback
        for i in range(10):
            feedback = FeedbackEntry(
                id=f"test-{i}",
                task_id=f"task-{i}",
                timestamp=datetime.now() - timedelta(days=i),
                feedback_type=FeedbackType.TASK_COMPLETION,
                content="Test feedback",
                rating=RatingScale(4)
            )
            self.storage.store_feedback(feedback)
        
        # Analyze last 7 days
        result = analyze_recent_feedback(days=7, storage=self.storage)
        
        assert isinstance(result, AnalysisResult)
        assert result.metrics.total_count <= 8  # Should include ~7 days of data
    
    def test_get_worker_performance_convenience(self):
        """Test get_worker_performance convenience function"""
        worker_id = "test-worker"
        
        # Create feedback for worker
        for i in range(5):
            feedback = FeedbackEntry(
                id=f"worker-{i}",
                task_id=f"task-{i}",
                timestamp=datetime.now(),
                feedback_type=FeedbackType.WORKER_PERFORMANCE,
                content="Worker feedback",
                rating=RatingScale(4),
                metadata=FeedbackMetadata(
                    source="test",
                    version="1.0",
                    context={"worker_id": worker_id}
                )
            )
            self.storage.store_feedback(feedback)
        
        summary = get_worker_performance(worker_id, storage=self.storage)
        
        assert summary["worker_id"] == worker_id
        assert summary["feedback_count"] == 5
        assert summary["average_rating"] == 4.0


class TestDataClasses:
    """Tests for data classes"""
    
    def test_feedback_metrics_to_dict(self):
        """Test FeedbackMetrics serialization"""
        metrics = FeedbackMetrics(
            total_count=100,
            average_rating=4.2,
            rating_distribution={1: 5, 2: 10, 3: 20, 4: 35, 5: 30},
            sentiment_scores={"positive": 0.6, "negative": 0.1, "neutral": 0.3},
            response_rate=0.75,
            common_themes=[("performance", 25), ("quality", 20)]
        )
        
        data = metrics.to_dict()
        
        assert data["total_count"] == 100
        assert data["average_rating"] == 4.2
        assert data["rating_distribution"][4] == 35
        assert data["sentiment_scores"]["positive"] == 0.6
        assert data["response_rate"] == 0.75
        assert len(data["common_themes"]) == 2
    
    def test_trend_data_to_dict(self):
        """Test TrendData serialization"""
        trend = TrendData(
            metric_name="Test Metric",
            direction=TrendDirection.IMPROVING,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            change_percentage=15.5,
            confidence=0.85,
            data_points=[(datetime(2024, 1, 1), 3.0), (datetime(2024, 1, 31), 4.0)]
        )
        
        data = trend.to_dict()
        
        assert data["metric_name"] == "Test Metric"
        assert data["direction"] == "improving"
        assert data["change_percentage"] == 15.5
        assert data["confidence"] == 0.85
        assert len(data["data_points"]) == 2
    
    def test_analysis_insight_to_dict(self):
        """Test AnalysisInsight serialization"""
        insight = AnalysisInsight(
            insight_type="test_insight",
            title="Test Insight",
            description="This is a test insight",
            priority=InsightPriority.HIGH,
            affected_entities=["entity1", "entity2"],
            recommended_action="Take action",
            supporting_data={"metric": 123},
            confidence=0.9
        )
        
        data = insight.to_dict()
        
        assert data["insight_type"] == "test_insight"
        assert data["title"] == "Test Insight"
        assert data["priority"] == "high"
        assert len(data["affected_entities"]) == 2
        assert data["confidence"] == 0.9
    
    def test_analysis_result_to_dict(self):
        """Test AnalysisResult serialization"""
        result = AnalysisResult(
            analysis_id="test-123",
            timestamp=datetime.now(),
            period_start=datetime.now() - timedelta(days=30),
            period_end=datetime.now(),
            metrics=FeedbackMetrics(
                total_count=50,
                average_rating=4.0,
                rating_distribution={},
                sentiment_scores={},
                response_rate=0.8,
                common_themes=[]
            ),
            trends=[],
            insights=[],
            summary="Test summary"
        )
        
        data = result.to_dict()
        
        assert data["analysis_id"] == "test-123"
        assert "timestamp" in data
        assert "period_start" in data
        assert "period_end" in data
        assert data["summary"] == "Test summary"
        assert data["metrics"]["total_count"] == 50