#!/usr/bin/env python3
"""Add task to implement feedback analysis algorithms that were not created in previous task."""
import subprocess
import sys

def add_task():
    """Add the feedback analysis implementation task."""
    task_prompt = """[CRITICAL] Implement feedback analysis algorithms in analysis_algorithms.py - Previous task 9307f1ce failed to create the file. 

Must include actual working Python code for:
1) Sentiment analysis for text feedback using TextBlob or similar library
2) Statistical methods: calculate_mean(), calculate_median(), calculate_std_dev(), calculate_percentiles()
3) Trend detection over time using moving averages: detect_trends()
4) Anomaly detection using z-score or IQR: detect_anomalies()
5) Performance scoring algorithm: calculate_performance_score()

Create the actual analysis_algorithms.py file with all functions implemented and documented.
Include proper error handling and type hints."""
    
    cmd = [
        sys.executable, "-m", "claude_orchestrator.task_master",
        "add-task",
        "--prompt", task_prompt,
        "--priority", "high"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Successfully added feedback analysis implementation task")
        print(result.stdout)
    else:
        print("❌ Failed to add task")
        print(result.stderr)
        sys.exit(1)

if __name__ == "__main__":
    add_task()