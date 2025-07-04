#!/usr/bin/env python3
"""Add follow-up tasks for Task 30 (Test Metrics Reporting)"""

import subprocess
import json

def add_task(prompt, priority="medium"):
    """Add a task using the task-master CLI"""
    cmd = ["python", "-m", "claude_orchestrator", "task-master", "add-task", 
           "--prompt", prompt, "--priority", priority]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Added task: {prompt[:50]}...")
        else:
            print(f"✗ Failed to add task: {result.stderr}")
    except Exception as e:
        print(f"✗ Error adding task: {str(e)}")

def main():
    """Add all follow-up tasks for test metrics reporting"""
    
    tasks = [
        {
            "prompt": "Create test metrics collector module: Implement a TestMetricsCollector class that gathers test count per category (unit, integration, e2e), execution times, and test results from pytest/unittest runners",
            "priority": "high"
        },
        {
            "prompt": "Implement code coverage integration: Build coverage reporting functionality that integrates with coverage.py, calculates coverage percentage per module, generates HTML/JSON reports, and tracks coverage trends",
            "priority": "high"
        },
        {
            "prompt": "Create performance benchmarking system: Implement performance metrics collection for response times, throughput calculations, memory usage tracking, and performance regression detection",
            "priority": "medium"
        },
        {
            "prompt": "Build security scan results aggregator: Create security metrics reporting that integrates with tools like bandit and safety, aggregates vulnerability findings, and tracks security issues over time",
            "priority": "high"
        },
        {
            "prompt": "Develop unified test report generator: Create comprehensive report generation that combines all metrics, supports multiple output formats (HTML, JSON, Markdown), includes visualizations, and generates executive summaries",
            "priority": "medium"
        },
        {
            "prompt": "Add CLI commands for test metrics: Extend the orchestrator CLI with test-metrics command, support filtering by date range and test type, enable export to different formats, and add metrics comparison features",
            "priority": "low"
        }
    ]
    
    print("Adding follow-up tasks for Task 30 (Test Metrics Reporting)...\n")
    
    for task in tasks:
        add_task(task["prompt"], task["priority"])
    
    print("\nAll follow-up tasks have been processed.")

if __name__ == "__main__":
    main()