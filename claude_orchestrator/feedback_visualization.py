"""Feedback visualization and reporting tools."""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from .feedback_storage import FeedbackStorage
from .feedback_analyzer import FeedbackAnalyzer
from .storage_factory import create_feedback_storage

logger = logging.getLogger(__name__)


class FeedbackVisualizer:
    """Creates visual reports from feedback data."""
    
    def __init__(self, storage: Optional[FeedbackStorage] = None):
        self.storage = storage or create_feedback_storage()
        self.analyzer = FeedbackAnalyzer(self.storage)
        
    def generate_text_report(self, 
                           days: int = 7,
                           worker_id: Optional[str] = None,
                           output_file: Optional[str] = None) -> str:
        """Generate a text-based feedback report.
        
        Args:
            days: Number of days to include
            worker_id: Specific worker to report on (all if None)
            output_file: File to save report to
            
        Returns:
            Report content
        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("FEEDBACK ANALYSIS REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Period: Last {days} days")
        if worker_id:
            report_lines.append(f"Worker: {worker_id}")
        report_lines.append("")
        
        # Get trend analysis
        trends = self.analyzer.analyze_trends(days=days)
        if trends:
            report_lines.append("TREND ANALYSIS")
            report_lines.append("-" * 40)
            
            # Daily activity
            report_lines.append("\nDaily Feedback Counts:")
            for date, count in sorted(trends.daily_counts.items()):
                report_lines.append(f"  {date}: {count} feedback items")
            
            # Success rate trend
            if trends.success_rate_trend:
                report_lines.append("\nSuccess Rate Trend:")
                for date, rate in sorted(trends.success_rate_trend.items()):
                    bar = "█" * int(rate * 20)  # 20-char bar
                    report_lines.append(f"  {date}: {bar} {rate:.1%}")
            
            # Response time trend
            if trends.average_response_time_trend:
                report_lines.append("\nAverage Response Time Trend (seconds):")
                for date, time_val in sorted(trends.average_response_time_trend.items()):
                    report_lines.append(f"  {date}: {time_val:.2f}s")
            
            # Common patterns
            if trends.common_patterns:
                report_lines.append("\nCommon Patterns:")
                for i, (pattern, count) in enumerate(trends.common_patterns[:10], 1):
                    report_lines.append(f"  {i}. {pattern} (occurred {count} times)")
        
        # Worker performance
        report_lines.append("\n\nWORKER PERFORMANCE")
        report_lines.append("-" * 40)
        
        if worker_id:
            # Single worker report
            perf = self.analyzer.get_worker_performance(worker_id)
            if perf:
                report_lines.extend(self._format_worker_performance(worker_id, perf))
            else:
                report_lines.append(f"No performance data for worker {worker_id}")
        else:
            # All workers
            start_date = datetime.now() - timedelta(days=days)
            all_feedback = self.storage.get_by_date_range(start_date, datetime.now())
            
            # Group by worker
            worker_feedback = defaultdict(list)
            for fb in all_feedback:
                if fb.worker_id:
                    worker_feedback[fb.worker_id].append(fb)
            
            for wid in sorted(worker_feedback.keys()):
                perf = self.analyzer.get_worker_performance(wid, start_date=start_date)
                if perf:
                    report_lines.extend(self._format_worker_performance(wid, perf))
                    report_lines.append("")
        
        # Task analysis
        report_lines.append("\n\nTASK ANALYSIS")
        report_lines.append("-" * 40)
        
        # Get all tasks with feedback
        all_feedback = self.storage.get_by_date_range(
            datetime.now() - timedelta(days=days),
            datetime.now()
        )
        
        task_feedback = defaultdict(list)
        for fb in all_feedback:
            task_feedback[fb.task_id].append(fb)
        
        # Sort by feedback count
        sorted_tasks = sorted(
            task_feedback.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:20]  # Top 20 tasks
        
        report_lines.append(f"\nTop {len(sorted_tasks)} Tasks by Feedback Count:")
        for task_id, feedbacks in sorted_tasks:
            analysis = self.analyzer.analyze_task(task_id)
            if analysis:
                status = "✅" if analysis.success else "❌"
                exec_time = f"{analysis.execution_time:.1f}s" if analysis.execution_time else "N/A"
                report_lines.append(
                    f"  {status} Task {task_id}: {len(feedbacks)} feedback items, "
                    f"exec time: {exec_time}"
                )
        
        # Error summary
        report_lines.append("\n\nERROR SUMMARY")
        report_lines.append("-" * 40)
        
        error_types = defaultdict(int)
        error_messages = []
        
        for fb in all_feedback:
            if fb.feedback_type.value == "error":
                error_messages.append(fb.message)
                if fb.context and 'error_type' in fb.context:
                    error_types[fb.context['error_type']] += 1
        
        if error_messages:
            report_lines.append(f"\nTotal Errors: {len(error_messages)}")
            
            # Most common error types
            if error_types:
                report_lines.append("\nError Types:")
                for error_type, count in sorted(
                    error_types.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]:
                    report_lines.append(f"  {error_type}: {count}")
            
            # Sample error messages
            report_lines.append("\nRecent Error Messages:")
            for msg in error_messages[-10:]:
                truncated = msg[:80] + "..." if len(msg) > 80 else msg
                report_lines.append(f"  - {truncated}")
        else:
            report_lines.append("No errors found in the period")
        
        # Summary statistics
        report_lines.append("\n\nSUMMARY STATISTICS")
        report_lines.append("-" * 40)
        
        total_feedback = len(all_feedback)
        success_count = sum(1 for fb in all_feedback if fb.feedback_type.value == "success")
        error_count = sum(1 for fb in all_feedback if fb.feedback_type.value == "error")
        warning_count = sum(1 for fb in all_feedback if fb.feedback_type.value == "warning")
        
        report_lines.append(f"Total Feedback Items: {total_feedback}")
        report_lines.append(f"Success: {success_count} ({success_count/total_feedback*100:.1f}%)" if total_feedback > 0 else "Success: 0")
        report_lines.append(f"Errors: {error_count} ({error_count/total_feedback*100:.1f}%)" if total_feedback > 0 else "Errors: 0")
        report_lines.append(f"Warnings: {warning_count} ({warning_count/total_feedback*100:.1f}%)" if total_feedback > 0 else "Warnings: 0")
        
        # Calculate average execution time
        exec_times = []
        for fb in all_feedback:
            if fb.metrics and hasattr(fb.metrics, 'execution_time') and fb.metrics.execution_time:
                exec_times.append(fb.metrics.execution_time)
        
        if exec_times:
            report_lines.append(f"\nExecution Time Statistics:")
            report_lines.append(f"  Average: {statistics.mean(exec_times):.2f}s")
            report_lines.append(f"  Median: {statistics.median(exec_times):.2f}s")
            report_lines.append(f"  Min: {min(exec_times):.2f}s")
            report_lines.append(f"  Max: {max(exec_times):.2f}s")
        
        report_lines.append("\n" + "=" * 80)
        report_content = "\n".join(report_lines)
        
        # Save to file if requested
        if output_file:
            try:
                with open(output_file, 'w') as f:
                    f.write(report_content)
                logger.info(f"Report saved to {output_file}")
            except Exception as e:
                logger.error(f"Failed to save report: {e}")
        
        return report_content
    
    def _format_worker_performance(self, worker_id: str, perf) -> List[str]:
        """Format worker performance data."""
        lines = []
        lines.append(f"\nWorker: {worker_id}")
        lines.append(f"  Total Tasks: {perf.total_tasks}")
        lines.append(f"  Success Rate: {perf.success_rate:.1%}")
        lines.append(f"  Average Response Time: {perf.average_response_time:.2f}s")
        
        if perf.capability_scores:
            lines.append("  Capability Scores:")
            for cap, score in sorted(perf.capability_scores.items()):
                bar = "█" * int(score * 10)  # 10-char bar
                lines.append(f"    {cap}: {bar} {score:.2f}")
        
        if perf.recent_errors:
            lines.append(f"  Recent Errors: {len(perf.recent_errors)}")
            for error in perf.recent_errors[:3]:
                truncated = error[:60] + "..." if len(error) > 60 else error
                lines.append(f"    - {truncated}")
        
        return lines
    
    def generate_json_report(self,
                           days: int = 7,
                           worker_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate a JSON-formatted feedback report.
        
        Args:
            days: Number of days to include
            worker_id: Specific worker to report on
            
        Returns:
            Report data as dictionary
        """
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "period_days": days,
                "worker_filter": worker_id
            },
            "trends": {},
            "workers": {},
            "tasks": {},
            "errors": {},
            "summary": {}
        }
        
        # Get trend data
        trends = self.analyzer.analyze_trends(days=days)
        if trends:
            report["trends"] = {
                "daily_counts": trends.daily_counts,
                "success_rate_trend": trends.success_rate_trend,
                "response_time_trend": trends.average_response_time_trend,
                "common_patterns": trends.common_patterns[:20]
            }
        
        # Get worker data
        start_date = datetime.now() - timedelta(days=days)
        
        if worker_id:
            perf = self.analyzer.get_worker_performance(worker_id, start_date=start_date)
            if perf:
                report["workers"][worker_id] = {
                    "total_tasks": perf.total_tasks,
                    "successful_tasks": perf.successful_tasks,
                    "failed_tasks": perf.failed_tasks,
                    "success_rate": perf.success_rate,
                    "average_response_time": perf.average_response_time,
                    "capability_scores": perf.capability_scores
                }
        else:
            # Get all workers
            all_feedback = self.storage.get_by_date_range(start_date, datetime.now())
            worker_ids = set(fb.worker_id for fb in all_feedback if fb.worker_id)
            
            for wid in worker_ids:
                perf = self.analyzer.get_worker_performance(wid, start_date=start_date)
                if perf:
                    report["workers"][wid] = {
                        "total_tasks": perf.total_tasks,
                        "successful_tasks": perf.successful_tasks,
                        "failed_tasks": perf.failed_tasks,
                        "success_rate": perf.success_rate,
                        "average_response_time": perf.average_response_time
                    }
        
        # Get task data
        all_feedback = self.storage.get_by_date_range(start_date, datetime.now())
        task_ids = set(fb.task_id for fb in all_feedback)
        
        task_summaries = []
        for tid in list(task_ids)[:100]:  # Limit to 100 tasks
            analysis = self.analyzer.analyze_task(tid)
            if analysis:
                task_summaries.append({
                    "task_id": tid,
                    "feedback_count": analysis.feedback_count,
                    "success": analysis.success,
                    "execution_time": analysis.execution_time,
                    "quality_score": analysis.quality_score
                })
        
        report["tasks"]["count"] = len(task_ids)
        report["tasks"]["summaries"] = sorted(
            task_summaries,
            key=lambda x: x["feedback_count"],
            reverse=True
        )[:50]
        
        # Error analysis
        errors = [fb for fb in all_feedback if fb.feedback_type.value == "error"]
        report["errors"]["total_count"] = len(errors)
        report["errors"]["by_severity"] = defaultdict(int)
        report["errors"]["recent"] = []
        
        for error in errors:
            if error.severity:
                report["errors"]["by_severity"][error.severity.value] += 1
        
        for error in errors[-20:]:
            report["errors"]["recent"].append({
                "timestamp": error.timestamp.isoformat(),
                "task_id": error.task_id,
                "worker_id": error.worker_id,
                "message": error.message,
                "severity": error.severity.value if error.severity else None
            })
        
        # Summary statistics
        report["summary"]["total_feedback"] = len(all_feedback)
        report["summary"]["feedback_by_type"] = defaultdict(int)
        
        for fb in all_feedback:
            report["summary"]["feedback_by_type"][fb.feedback_type.value] += 1
        
        # Execution time stats
        exec_times = [
            fb.metrics.execution_time 
            for fb in all_feedback 
            if fb.metrics and hasattr(fb.metrics, 'execution_time') and fb.metrics.execution_time
        ]
        
        if exec_times:
            report["summary"]["execution_time_stats"] = {
                "mean": statistics.mean(exec_times),
                "median": statistics.median(exec_times),
                "min": min(exec_times),
                "max": max(exec_times),
                "stddev": statistics.stdev(exec_times) if len(exec_times) > 1 else 0
            }
        
        return report
    
    def export_csv_data(self,
                       output_file: str,
                       days: int = 7) -> None:
        """Export feedback data to CSV format.
        
        Args:
            output_file: Path to output CSV file
            days: Number of days to include
        """
        import csv
        
        start_date = datetime.now() - timedelta(days=days)
        all_feedback = self.storage.get_by_date_range(start_date, datetime.now())
        
        with open(output_file, 'w', newline='') as csvfile:
            fieldnames = [
                'feedback_id', 'task_id', 'worker_id', 'timestamp',
                'feedback_type', 'severity', 'category', 'message',
                'execution_time', 'quality_score', 'success'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for fb in all_feedback:
                row = {
                    'feedback_id': fb.feedback_id,
                    'task_id': fb.task_id,
                    'worker_id': fb.worker_id or '',
                    'timestamp': fb.timestamp.isoformat(),
                    'feedback_type': fb.feedback_type.value,
                    'severity': fb.severity.value if fb.severity else '',
                    'category': fb.category.value if fb.category else '',
                    'message': fb.message,
                    'execution_time': '',
                    'quality_score': '',
                    'success': ''
                }
                
                # Add metrics if available
                if fb.metrics:
                    if hasattr(fb.metrics, 'execution_time'):
                        row['execution_time'] = fb.metrics.execution_time or ''
                    if hasattr(fb.metrics, 'quality_score'):
                        row['quality_score'] = fb.metrics.quality_score or ''
                    if hasattr(fb.metrics, 'success_rate'):
                        row['success'] = 'true' if fb.metrics.success_rate > 0.5 else 'false'
                
                writer.writerow(row)
        
        logger.info(f"Exported {len(all_feedback)} feedback items to {output_file}")


def generate_feedback_dashboard(config: Optional[Dict[str, Any]] = None) -> str:
    """Generate a simple text dashboard of feedback metrics.
    
    Args:
        config: Optional configuration
        
    Returns:
        Dashboard content
    """
    storage = create_feedback_storage(config)
    visualizer = FeedbackVisualizer(storage)
    
    # Generate a 7-day report
    return visualizer.generate_text_report(days=7)