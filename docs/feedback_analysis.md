# Feedback Analysis Documentation

## Overview

The Feedback Analysis module provides comprehensive analytics and insights from collected feedback data. It integrates with the Feedback Storage system to analyze task completion feedback, worker performance, and system effectiveness.

## Architecture

### Core Components

1. **FeedbackAnalyzer** (`feedback_analysis.py`)
   - Main analysis engine
   - Metrics calculation
   - Trend detection
   - Insight generation
   - Report generation

2. **Data Models**
   - `FeedbackMetrics`: Aggregated metrics data
   - `TrendData`: Trend analysis results
   - `AnalysisInsight`: Generated insights
   - `AnalysisResult`: Complete analysis output

3. **Analysis Algorithms**
   - Rating trend analysis
   - Volume trend detection
   - Sentiment analysis
   - Performance pattern detection
   - Theme extraction

## Usage Guide

### Basic Analysis

```python
from claude_orchestrator.feedback_analysis import FeedbackAnalyzer
from claude_orchestrator.feedback_storage import FeedbackStorage

# Initialize analyzer with storage
storage = FeedbackStorage()
analyzer = FeedbackAnalyzer(storage)

# Analyze all feedback
result = analyzer.analyze_feedback()

# Access metrics
print(f"Average Rating: {result.metrics.average_rating}")
print(f"Total Feedback: {result.metrics.total_count}")
print(f"Rating Distribution: {result.metrics.rating_distribution}")
```

### Task-Specific Analysis

```python
# Analyze feedback for a specific task
task_result = analyzer.analyze_feedback(task_id="task-123")

# Get task-specific insights
for insight in task_result.insights:
    print(f"{insight.priority.value}: {insight.title}")
    print(f"  {insight.description}")
    print(f"  Impact: {insight.impact_score}")
```

### Worker Performance Analysis

```python
# Get worker performance summary
worker_summary = analyzer.get_worker_performance_summary("worker-456")

print(f"Worker: {worker_summary.worker_id}")
print(f"Tasks Completed: {worker_summary.total_tasks}")
print(f"Average Rating: {worker_summary.average_rating}")
print(f"Success Rate: {worker_summary.success_rate}")
print(f"Performance Trend: {worker_summary.performance_trend}")
```

### Trend Analysis

```python
# Analyze trends over time
from datetime import datetime, timedelta

end_date = datetime.now()
start_date = end_date - timedelta(days=30)

trends = analyzer.analyze_feedback(
    start_date=start_date,
    end_date=end_date
).trends

for trend in trends:
    print(f"{trend.metric}: {trend.direction.value}")
    print(f"  Change: {trend.change_percentage:.1f}%")
    print(f"  Confidence: {trend.confidence}")
```

## Analysis Features

### 1. Metrics Calculation

The analyzer calculates comprehensive metrics:

```python
metrics = result.metrics

# Basic metrics
average_rating = metrics.average_rating
total_count = metrics.total_count
rating_distribution = metrics.rating_distribution

# Advanced metrics
sentiment_scores = metrics.sentiment_scores
response_rate = metrics.response_rate
common_themes = metrics.common_themes
```

### 2. Trend Detection

Automatic trend detection for key metrics:

```python
# Rating trends
rating_trend = analyzer._analyze_rating_trend(feedback_list)
if rating_trend.direction == TrendDirection.IMPROVING:
    print(f"Ratings improving by {rating_trend.change_percentage}%")

# Volume trends
volume_trend = analyzer._analyze_volume_trend(feedback_list)
if volume_trend.direction == TrendDirection.INCREASING:
    print(f"Feedback volume up {volume_trend.change_percentage}%")
```

### 3. Insight Generation

Automatic insight generation based on patterns:

```python
insights = result.insights

# Filter by priority
high_priority = [i for i in insights if i.priority == InsightPriority.HIGH]

# Common insight types:
# - Poor performing workers
# - Problematic task types
# - Recurring themes
# - System bottlenecks
```

### 4. Export Capabilities

Export analysis results in various formats:

```python
# Export as JSON
json_report = analyzer.export_analysis_report(
    result,
    format='json',
    output_path='analysis_report.json'
)

# Export as Markdown
md_report = analyzer.export_analysis_report(
    result,
    format='markdown',
    output_path='analysis_report.md'
)

# Export as CSV
csv_report = analyzer.export_analysis_report(
    result,
    format='csv',
    output_path='analysis_report.csv'
)
```

## Advanced Features

### Custom Analysis Windows

```python
# Analyze specific time periods
weekly_result = analyzer.analyze_feedback(
    start_date=datetime.now() - timedelta(days=7)
)

# Compare periods
current_week = analyzer.analyze_feedback(
    start_date=datetime.now() - timedelta(days=7)
)
previous_week = analyzer.analyze_feedback(
    start_date=datetime.now() - timedelta(days=14),
    end_date=datetime.now() - timedelta(days=7)
)

# Calculate week-over-week change
rating_change = (
    (current_week.metrics.average_rating - 
     previous_week.metrics.average_rating) / 
    previous_week.metrics.average_rating * 100
)
```

### Filtering and Segmentation

```python
# Analyze by feedback type
completion_feedback = analyzer.analyze_feedback(
    feedback_type=FeedbackType.TASK_COMPLETION
)

# Analyze by rating range
positive_feedback = analyzer.analyze_feedback(
    min_rating=4
)

# Combine filters
recent_positive = analyzer.analyze_feedback(
    start_date=datetime.now() - timedelta(days=7),
    min_rating=4,
    feedback_type=FeedbackType.TASK_COMPLETION
)
```

### Theme Analysis

```python
# Extract common themes
themes = analyzer._extract_common_themes(feedback_list)

for theme, count in themes.items():
    print(f"{theme}: {count} occurrences")

# Analyze theme patterns
theme_insights = analyzer._analyze_theme_patterns(feedback_list)
for insight in theme_insights:
    if "error" in insight.description.lower():
        print(f"Error pattern detected: {insight.description}")
```

## Integration with Orchestrator

### Automated Analysis

```python
# Schedule periodic analysis
import asyncio

async def periodic_analysis():
    while True:
        # Run analysis
        result = analyzer.analyze_feedback()
        
        # Check for critical insights
        critical = [i for i in result.insights 
                   if i.priority == InsightPriority.HIGH]
        
        if critical:
            # Trigger alerts or actions
            await notify_admin(critical)
        
        # Wait for next run
        await asyncio.sleep(3600)  # Run hourly
```

### Real-time Monitoring

```python
# Monitor feedback in real-time
def on_new_feedback(feedback_entry):
    # Quick analysis of new feedback
    if feedback_entry.rating <= 2:
        # Low rating alert
        analyzer.analyze_feedback(
            task_id=feedback_entry.task_id
        )
```

## Best Practices

### 1. Regular Analysis

Run analysis regularly to catch trends early:

```python
# Daily summary
daily_result = analyzer.analyze_feedback(
    start_date=datetime.now().replace(hour=0, minute=0, second=0)
)

# Weekly report
weekly_result = analyzer.analyze_feedback(
    start_date=datetime.now() - timedelta(days=7)
)
```

### 2. Actionable Insights

Focus on insights that drive action:

```python
# Filter actionable insights
actionable = [
    insight for insight in result.insights
    if insight.actionable and insight.impact_score > 0.7
]

# Generate action items
for insight in actionable:
    action = create_action_item(insight)
    task_queue.add(action)
```

### 3. Performance Optimization

For large datasets:

```python
# Use pagination for large analyses
def analyze_in_batches(batch_size=1000):
    offset = 0
    all_metrics = []
    
    while True:
        batch = storage.get_filtered(
            limit=batch_size,
            offset=offset
        )
        
        if not batch:
            break
            
        batch_result = analyzer.analyze_feedback(
            feedback_list=batch
        )
        all_metrics.append(batch_result.metrics)
        
        offset += batch_size
    
    # Aggregate results
    return aggregate_metrics(all_metrics)
```

## Performance Metrics

Typical analysis performance:

- Small dataset (<1000 records): ~50-100ms
- Medium dataset (1000-10000): ~200-500ms
- Large dataset (>10000): ~1-5s

Optimization tips:
- Use database indexes on frequently queried fields
- Cache analysis results for repeated queries
- Run heavy analyses asynchronously
- Consider data aggregation for historical data

## Error Handling

```python
try:
    result = analyzer.analyze_feedback()
except Exception as e:
    logger.error(f"Analysis failed: {e}")
    # Fallback to basic metrics
    result = AnalysisResult(
        metrics=FeedbackMetrics(
            total_count=0,
            average_rating=0.0,
            rating_distribution={}
        ),
        trends=[],
        insights=[]
    )
```

## CLI Commands (To Be Implemented)

The following CLI commands are planned for implementation:

### analyze-feedback

```bash
co analyze-feedback <task-id>
# Analyzes feedback for a specific task
```

### worker-performance

```bash
co worker-performance
# Shows performance metrics for all workers
```

### feedback-report

```bash
co feedback-report --format json --output report.json
# Generates comprehensive feedback report
```

### export-metrics

```bash
co export-metrics --start-date 2024-01-01 --format csv
# Exports feedback metrics for analysis
```

## Summary

The Feedback Analysis module provides powerful analytics capabilities for understanding system performance, worker effectiveness, and task quality. By leveraging trend detection and automated insights, it helps identify issues early and optimize orchestrator operations.