#!/usr/bin/env python3
"""Add feedback analyzer implementation tasks"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_orchestrator.task_master import TaskManager

def main():
    tm = TaskManager()
    
    # Task 1: Create FeedbackAnalyzer module
    task1_id = tm.add_task(
        title="Create FeedbackAnalyzer module",
        description="Create FeedbackAnalyzer module with: 1) FeedbackAnalyzer class to analyze task performance, 2) Methods to collect feedback metrics (execution time, success rate, error patterns), 3) Worker performance tracking, 4) Feedback data storage structure, 5) Analysis methods for insights generation",
        priority="high"
    )
    print(f"Created task {task1_id}: Create FeedbackAnalyzer module")
    
    # Task 2: Integrate FeedbackAnalyzer with main orchestrator
    task2_id = tm.add_task(
        title="Integrate FeedbackAnalyzer with main orchestrator",
        description="Integrate FeedbackAnalyzer in main.py: 1) Import and initialize FeedbackAnalyzer, 2) Add feedback collection after task completion in complete_task method, 3) Store feedback data with completed tasks, 4) Add method to retrieve feedback analytics",
        priority="high"
    )
    print(f"Created task {task2_id}: Integrate FeedbackAnalyzer with main orchestrator")
    
    # Task 3: Implement feedback-based worker allocation
    task3_id = tm.add_task(
        title="Implement feedback-based worker allocation",
        description="Enhance worker allocation with feedback: 1) Modify DynamicWorkerAllocator to accept feedback data, 2) Implement worker performance scoring based on feedback, 3) Add logic to prefer high-performing workers for similar tasks, 4) Handle worker performance degradation",
        priority="medium"
    )
    print(f"Created task {task3_id}: Implement feedback-based worker allocation")
    
    # Task 4: Create feedback visualization and reporting
    task4_id = tm.add_task(
        title="Create feedback visualization and reporting",
        description="Create feedback reporting system: 1) Generate worker performance reports, 2) Task success rate analytics, 3) Error pattern analysis, 4) Performance trends over time, 5) Export feedback data for analysis",
        priority="low"
    )
    print(f"Created task {task4_id}: Create feedback visualization and reporting")

if __name__ == "__main__":
    main()