"""Unit tests for FeedbackAnalyzer."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from claude_orchestrator.feedback_analyzer import (
    FeedbackAnalyzer,
    WorkerPerformance,
    TaskAnalysis,
    TrendAnalysis,
    FeedbackInsights
)
from claude_orchestrator.feedback_storage import FeedbackStorage, JSONFeedbackStorage
from claude_orchestrator.feedback_model import (
    FeedbackModel,
    FeedbackType,
    FeedbackSeverity,
    FeedbackCategory,
    FeedbackContext,
    FeedbackMetrics,
    create_success_feedback,
    create_error_feedback,
    create_performance_feedback
)


class TestFeedbackAnalyzer:
    """Test suite for FeedbackAnalyzer."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def storage(self, temp_dir):
        """Create FeedbackStorage instance."""
        backend = JSONFeedbackStorage(str(Path(temp_dir) / "feedback"))
        return FeedbackStorage(backend=backend)
    
    @pytest.fixture
    def analyzer(self, storage):
        """Create FeedbackAnalyzer instance."""
        return FeedbackAnalyzer(storage)
    
    @pytest.fixture
    def sample_feedbacks(self, storage):
        """Create and save sample feedbacks."""
        feedbacks = []
        
        # Worker 1 - Good performance
        for i in range(5):
            feedback = create_success_feedback(
                task_id=f"task_w1_{i}",
                message="Success",
                worker_id="worker1",
                metrics=FeedbackMetrics(
                    execution_time=10.0 + i,
                    quality_score=0.9,
                    tokens_used=100
                )
            )
            feedbacks.append(feedback)
            storage.save(feedback)
        
        # Worker 1 - One failure
        error_feedback = create_error_feedback(
            task_id="task_w1_error",
            message="Task failed",
            error_details={"error": "timeout"},
            worker_id="worker1"
        )
        feedbacks.append(error_feedback)
        storage.save(error_feedback)
        
        # Worker 2 - Poor performance
        for i in range(3):
            feedback = create_success_feedback(
                task_id=f"task_w2_{i}",
                message="Success",
                worker_id="worker2",
                metrics=FeedbackMetrics(
                    execution_time=50.0 + i,
                    quality_score=0.6,
                    tokens_used=200
                )
            )
            feedbacks.append(feedback)
            storage.save(feedback)
        
        # Worker 2 - Multiple failures
        for i in range(3):
            error_feedback = create_error_feedback(
                task_id=f"task_w2_error_{i}",
                message="Task failed",
                error_details={"error": "memory_error"},
                worker_id="worker2"
            )
            feedbacks.append(error_feedback)
            storage.save(error_feedback)
        
        return feedbacks
    
    def test_analyze_worker_performance(self, analyzer, sample_feedbacks):
        """Test analyzing worker performance."""
        # Analyze worker1
        perf1 = analyzer.analyze_worker_performance("worker1")
        
        assert perf1.worker_id == "worker1"
        assert perf1.total_tasks == 6
        assert perf1.successful_tasks == 5
        assert perf1.failed_tasks == 1
        assert perf1.success_rate == pytest.approx(5/6)
        assert perf1.error_rate == pytest.approx(1/6)
        assert perf1.average_execution_time == pytest.approx(12.0)  # (10+11+12+13+14)/5
        assert perf1.average_quality_score == pytest.approx(0.9)
        assert perf1.average_tokens_used == 100
        
        # Analyze worker2
        perf2 = analyzer.analyze_worker_performance("worker2")
        
        assert perf2.worker_id == "worker2"
        assert perf2.total_tasks == 6
        assert perf2.successful_tasks == 3
        assert perf2.failed_tasks == 3
        assert perf2.success_rate == 0.5
        assert perf2.error_rate == 0.5
        assert perf2.average_execution_time == pytest.approx(51.0)  # (50+51+52)/3
        assert perf2.average_quality_score == pytest.approx(0.6)
    
    def test_analyze_worker_performance_empty(self, analyzer):
        """Test analyzing performance for non-existent worker."""
        perf = analyzer.analyze_worker_performance("nonexistent")
        
        assert perf.worker_id == "nonexistent"
        assert perf.total_tasks == 0
        assert perf.successful_tasks == 0
        assert perf.failed_tasks == 0
        assert perf.success_rate == 0.0
        assert perf.error_rate == 0.0
    
    def test_analyze_task(self, analyzer, storage):
        """Test analyzing specific task."""
        # Create task with multiple feedbacks
        task_id = "test_task"
        
        # Success feedback
        success = create_success_feedback(
            task_id=task_id,
            message="Task completed",
            metrics=FeedbackMetrics(
                execution_time=15.0,
                quality_score=0.85,
                memory_usage=512.0,
                cpu_usage=75.0
            )
        )
        storage.save(success)
        
        # Warning feedback
        warning = FeedbackModel(
            feedback_type=FeedbackType.VALIDATION_FAILURE,
            severity=FeedbackSeverity.WARNING,
            category=FeedbackCategory.QUALITY,
            message="Quality check warning",
            context=FeedbackContext(task_id=task_id)
        )
        storage.save(warning)
        
        # Analyze task
        analysis = analyzer.analyze_task(task_id)
        
        assert analysis.task_id == task_id
        assert analysis.feedback_count == 2
        assert analysis.success is True
        assert analysis.execution_time == 15.0
        assert analysis.quality_score == 0.85
        assert len(analysis.warnings) == 1
        assert analysis.warnings[0] == "Quality check warning"
        assert analysis.resource_usage["memory"] == 512.0
        assert analysis.resource_usage["cpu"] == 75.0
    
    def test_analyze_task_failure(self, analyzer, storage):
        """Test analyzing failed task."""
        task_id = "failed_task"
        
        # Error feedback
        error = create_error_feedback(
            task_id=task_id,
            message="Critical error occurred",
            error_details={"code": "E001"},
            severity=FeedbackSeverity.CRITICAL
        )
        storage.save(error)
        
        # Analyze task
        analysis = analyzer.analyze_task(task_id)
        
        assert analysis.success is False
        assert len(analysis.error_messages) == 1
        assert analysis.error_messages[0] == "Critical error occurred"
    
    def test_analyze_trends_daily(self, analyzer, storage):
        """Test analyzing daily trends."""
        # Create feedbacks over several days
        base_time = datetime.now()
        
        for day in range(7):
            timestamp = base_time - timedelta(days=day)
            
            # Create varying success rates
            success_count = 10 - day  # Declining success
            failure_count = day
            
            for i in range(success_count):
                feedback = create_success_feedback(
                    task_id=f"task_d{day}_s{i}",
                    message="Success",
                    metrics=FeedbackMetrics(
                        execution_time=10.0 + day,
                        quality_score=0.9 - (day * 0.05)
                    )
                )
                feedback.timestamp = timestamp
                storage.save(feedback)
            
            for i in range(failure_count):
                feedback = create_error_feedback(
                    task_id=f"task_d{day}_f{i}",
                    message="Failure",
                    error_details={}
                )
                feedback.timestamp = timestamp
                storage.save(feedback)
        
        # Analyze trends
        trends = analyzer.analyze_trends(
            period="daily",
            time_range=(base_time - timedelta(days=7), base_time)
        )
        
        assert trends.period == "daily"
        assert trends.total_feedback > 0
        assert len(trends.success_rate_trend) > 0
        assert len(trends.error_rate_trend) > 0
        assert len(trends.performance_trend) > 0
        assert len(trends.quality_trend) > 0
    
    def test_get_comprehensive_insights(self, analyzer, sample_feedbacks):
        """Test getting comprehensive insights."""
        insights = analyzer.get_comprehensive_insights()
        
        assert insights.total_feedback == len(sample_feedbacks)
        assert insights.overall_success_rate > 0
        assert insights.overall_error_rate > 0
        assert insights.average_execution_time > 0
        assert insights.average_quality_score > 0
        
        # Check worker identification
        assert "worker1" in insights.high_performing_workers
        assert "worker2" in insights.problematic_workers
        
        # Check recommendations
        assert len(insights.recommendations) > 0
    
    def test_insights_with_common_errors(self, analyzer, storage):
        """Test insights with common error patterns."""
        # Create multiple instances of same error
        for i in range(5):
            error = create_error_feedback(
                task_id=f"task_err_{i}",
                message="Connection timeout",
                error_details={"code": "TIMEOUT"}
            )
            storage.save(error)
        
        for i in range(3):
            error = create_error_feedback(
                task_id=f"task_err2_{i}",
                message="Memory limit exceeded",
                error_details={"code": "OOM"}
            )
            storage.save(error)
        
        insights = analyzer.get_comprehensive_insights()
        
        assert len(insights.most_common_errors) > 0
        assert insights.most_common_errors[0][0] == "Connection timeout"
        assert insights.most_common_errors[0][1] == 5
    
    def test_bottleneck_identification(self, analyzer, storage):
        """Test identifying bottleneck tasks."""
        # Create tasks with varying execution times
        normal_time = 10.0
        
        # Normal tasks
        for i in range(5):
            feedback = create_success_feedback(
                task_id=f"normal_{i}",
                message="Success",
                metrics=FeedbackMetrics(execution_time=normal_time)
            )
            storage.save(feedback)
        
        # Bottleneck tasks (3x normal time)
        for i in range(2):
            feedback = create_success_feedback(
                task_id=f"slow_{i}",
                message="Success",
                metrics=FeedbackMetrics(execution_time=normal_time * 3)
            )
            storage.save(feedback)
        
        insights = analyzer.get_comprehensive_insights()
        
        assert len(insights.bottleneck_tasks) == 2
        assert all(task_id.startswith("slow_") for task_id in insights.bottleneck_tasks)
    
    def test_performance_trend_analysis(self, analyzer, storage):
        """Test performance trend detection."""
        worker_id = "trend_worker"
        base_time = datetime.now()
        
        # Create improving performance
        for i in range(10):
            feedback = create_success_feedback(
                task_id=f"task_{i}",
                message="Success",
                worker_id=worker_id,
                metrics=FeedbackMetrics(
                    execution_time=20.0 - i,  # Getting faster
                    quality_score=0.5 + (i * 0.05)  # Getting better
                )
            )
            feedback.timestamp = base_time - timedelta(hours=10-i)
            storage.save(feedback)
        
        perf = analyzer.analyze_worker_performance(worker_id)
        assert perf.recent_trend == "improving"
    
    def test_export_analysis_report(self, analyzer, storage, temp_dir, sample_feedbacks):
        """Test exporting analysis report."""
        report_path = Path(temp_dir) / "analysis_report.json"
        
        analyzer.export_analysis_report(str(report_path))
        
        assert report_path.exists()
        
        # Verify report content
        import json
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        assert "generated_at" in report
        assert "insights" in report
        assert "trends" in report
        assert "worker_performances" in report
        assert report["insights"]["total_feedback"] == len(sample_feedbacks)
    
    def test_empty_storage_analysis(self, analyzer):
        """Test analysis with empty storage."""
        # Worker performance
        perf = analyzer.analyze_worker_performance("any_worker")
        assert perf.total_tasks == 0
        
        # Task analysis
        task_analysis = analyzer.analyze_task("any_task")
        assert task_analysis.feedback_count == 0
        
        # Trends
        trends = analyzer.analyze_trends()
        assert trends.total_feedback == 0
        
        # Insights
        insights = analyzer.get_comprehensive_insights()
        assert insights.total_feedback == 0
        assert len(insights.recommendations) >= 0
    
    def test_time_range_filtering(self, analyzer, storage):
        """Test analysis with time range filtering."""
        now = datetime.now()
        worker_id = "time_test_worker"
        
        # Old feedback
        old_feedback = create_success_feedback(
            task_id="old_task",
            message="Old success",
            worker_id=worker_id
        )
        old_feedback.timestamp = now - timedelta(days=10)
        storage.save(old_feedback)
        
        # Recent feedback
        recent_feedback = create_success_feedback(
            task_id="recent_task",
            message="Recent success",
            worker_id=worker_id
        )
        recent_feedback.timestamp = now - timedelta(hours=1)
        storage.save(recent_feedback)
        
        # Analyze with time range
        time_range = (now - timedelta(days=1), now)
        perf = analyzer.analyze_worker_performance(worker_id, time_range)
        
        assert perf.total_tasks == 1  # Only recent task
        assert perf.successful_tasks == 1
    
    def test_severity_distribution(self, analyzer, storage):
        """Test severity distribution in worker performance."""
        worker_id = "severity_test"
        
        severities = [
            FeedbackSeverity.INFO,
            FeedbackSeverity.INFO,
            FeedbackSeverity.WARNING,
            FeedbackSeverity.ERROR,
            FeedbackSeverity.CRITICAL
        ]
        
        for i, severity in enumerate(severities):
            if severity in [FeedbackSeverity.ERROR, FeedbackSeverity.CRITICAL]:
                feedback_type = FeedbackType.ERROR_REPORT
            else:
                feedback_type = FeedbackType.TASK_SUCCESS
            
            feedback = FeedbackModel(
                feedback_type=feedback_type,
                severity=severity,
                category=FeedbackCategory.EXECUTION,
                message=f"Test {severity.value}",
                context=FeedbackContext(task_id=f"task_{i}", worker_id=worker_id)
            )
            storage.save(feedback)
        
        perf = analyzer.analyze_worker_performance(worker_id)
        
        assert perf.severity_distribution["info"] == 2
        assert perf.severity_distribution["warning"] == 1
        assert perf.severity_distribution["error"] == 1
        assert perf.severity_distribution["critical"] == 1