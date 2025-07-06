#!/usr/bin/env python3
"""
Script to add follow-up tasks for Task 18: Feedback Analysis Module implementation
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# Read existing tasks
tasks_file = Path(".taskmaster/tasks/tasks.json")
with open(tasks_file, 'r') as f:
    data = json.load(f)

# Define follow-up tasks for the incomplete Task 18
followup_tasks = [
    {
        "id": str(uuid.uuid4()),
        "prompt": "Create feedback_analysis.py module in claude_orchestrator with FeedbackAnalyzer class including: 1) analyze_task_feedback() method to process feedback data, 2) calculate_feedback_metrics() for statistical analysis, 3) generate_insights() for actionable recommendations, 4) aggregate_worker_performance() for worker-level metrics",
        "priority": "high",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "tags": ["feedback-analysis", "implementation", "core-module"]
    },
    {
        "id": str(uuid.uuid4()),
        "prompt": "Implement feedback data structures in feedback_models.py including: 1) FeedbackEntry dataclass with fields for task_id, worker_id, feedback_type, rating, content, timestamp, 2) FeedbackMetrics dataclass for storing analysis results, 3) WorkerPerformance dataclass for aggregated worker stats, 4) Enums for feedback types and rating scales",
        "priority": "high",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "tags": ["feedback-analysis", "data-models", "implementation"]
    },
    {
        "id": str(uuid.uuid4()),
        "prompt": "Create feedback analysis algorithms in analysis_algorithms.py including: 1) Sentiment analysis for text feedback, 2) Statistical methods for ratings (mean, median, std dev, percentiles), 3) Trend detection over time, 4) Anomaly detection for outlier feedback, 5) Performance scoring algorithm",
        "priority": "high",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "tags": ["feedback-analysis", "algorithms", "implementation"]
    },
    {
        "id": str(uuid.uuid4()),
        "prompt": "Integrate FeedbackAnalyzer with orchestrator in enhanced_orchestrator.py: 1) Add feedback collection after task completion, 2) Call analyzer methods during orchestration, 3) Use insights for worker allocation decisions, 4) Store analysis results with task data, 5) Add feedback-based worker selection logic",
        "priority": "high",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "tags": ["feedback-analysis", "integration", "orchestrator"]
    },
    {
        "id": str(uuid.uuid4()),
        "prompt": "Create comprehensive unit tests for feedback analysis module in tests/test_feedback_analysis.py covering: 1) FeedbackAnalyzer methods, 2) Data model validation, 3) Algorithm accuracy, 4) Edge cases and error handling, 5) Integration with mocked orchestrator, 6) Performance benchmarks",
        "priority": "medium",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "tags": ["feedback-analysis", "testing", "unit-tests"]
    },
    {
        "id": str(uuid.uuid4()),
        "prompt": "Add feedback analysis CLI commands to main.py: 1) 'analyze-feedback <task-id>' to analyze specific task feedback, 2) 'worker-performance' to show worker metrics, 3) 'feedback-report' for comprehensive analysis report, 4) 'export-metrics' to export analysis data",
        "priority": "medium",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "tags": ["feedback-analysis", "cli", "interface"]
    },
    {
        "id": str(uuid.uuid4()),
        "prompt": "Create feedback analysis documentation in docs/feedback_analysis.md covering: 1) Architecture overview, 2) API reference for FeedbackAnalyzer class, 3) Configuration options, 4) Usage examples, 5) Algorithm explanations, 6) Integration guide with orchestrator",
        "priority": "low",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "tags": ["feedback-analysis", "documentation"]
    }
]

# Add tasks to the data
for task in followup_tasks:
    data["tasks"].append(task)

# Write back to file
with open(tasks_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"✅ Added {len(followup_tasks)} follow-up tasks for Feedback Analysis Module implementation")
print("\nTasks added:")
for i, task in enumerate(followup_tasks, 1):
    print(f"{i}. {task['prompt'][:80]}... [Priority: {task['priority']}]")