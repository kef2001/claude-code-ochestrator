#!/usr/bin/env python3
"""
Follow-up tasks for Task 7: Feedback Analysis Module
Creates specific implementation tasks since the original task was not actually completed
"""

import subprocess
import json
import sys

def add_task(prompt, priority="medium"):
    """Add a task using task-master CLI"""
    cmd = ["task-master", "add-task", "--prompt", prompt, "--priority", priority]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Added task: {prompt[:50]}...")
        else:
            print(f"✗ Failed to add task: {result.stderr}")
    except Exception as e:
        print(f"✗ Error adding task: {e}")

def main():
    print("Creating follow-up tasks for Task 7: Feedback Analysis Module\n")
    
    tasks = [
        {
            "prompt": "Create the core feedback analysis module (feedback_analyzer.py) with classes for FeedbackAnalyzer, DataParser, and ReportGenerator. Include methods for loading feedback data from JSON/CSV, calculating basic statistics (average ratings, response counts), and generating summary reports",
            "priority": "high"
        },
        {
            "prompt": "Implement sentiment analysis functionality in the feedback analysis module using basic text analysis techniques. Add methods for categorizing feedback as positive/negative/neutral, extracting common themes and keywords, and tracking sentiment trends over time",
            "priority": "high"
        },
        {
            "prompt": "Create data visualization components for the feedback analysis module. Implement methods to generate charts showing feedback trends, rating distributions, sentiment analysis results, and export visualizations as PNG/PDF files",
            "priority": "medium"
        },
        {
            "prompt": "Add database integration to the feedback analysis module for storing and retrieving analysis results. Create schemas for feedback_analysis and analysis_reports tables, implement CRUD operations, and add caching for frequently accessed data",
            "priority": "medium"
        },
        {
            "prompt": "Write comprehensive unit tests for the feedback analysis module covering all major functionality. Include tests for data parsing, statistical calculations, sentiment analysis, report generation, and edge cases with invalid/missing data",
            "priority": "high"
        },
        {
            "prompt": "Create API endpoints for the feedback analysis module to expose analysis capabilities. Include endpoints for triggering analysis jobs, retrieving analysis results, generating custom reports, and scheduling automated analysis",
            "priority": "medium"
        },
        {
            "prompt": "Write documentation for the feedback analysis module including API reference, usage examples, configuration options, and integration guide with the feedback collection system",
            "priority": "low"
        }
    ]
    
    for task in tasks:
        add_task(task["prompt"], task["priority"])
    
    print(f"\n✓ Created {len(tasks)} follow-up tasks for proper implementation of the Feedback Analysis Module")

if __name__ == "__main__":
    main()