#!/usr/bin/env python3
"""
Script to add follow-up tasks for Task 21: Integrate Feedback into Worker Suitability Scoring
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_orchestrator.task_master import TaskManager

def main():
    task_master = TaskManager()
    
    # Task 1: Implement Feedback Storage System
    task_1 = task_master.add_task(
        title="Implement Feedback Storage System",
        description="""Create a comprehensive feedback storage system that includes:
        
1. Database schema for storing:
   - Task execution feedback (success/failure, performance metrics)
   - Worker performance history
   - Quality scores per worker per task type
   - Time-based performance trends
   
2. Storage implementation using SQLite or JSON file storage
3. APIs for storing and retrieving feedback data
4. Integration points with the existing task execution flow""",
        priority="high"
    )
    print(f"Added task: {task_1.title} (ID: {task_1.id})")
    
    # Task 2: Create Feedback Collection Mechanism
    task_2 = task_master.add_task(
        title="Create Feedback Collection Mechanism",
        description="""Implement feedback collection during and after task execution:
        
1. Automatic collection of:
   - Task completion status
   - Execution time vs estimated time
   - Resource usage metrics
   - Error rates and types
   
2. Manual feedback collection interface for:
   - Task quality assessment
   - Code review feedback
   - Performance ratings
   
3. Integration with task_master and worker execution flow""",
        priority="high"
    )
    print(f"Added task: {task_2.title} (ID: {task_2.id})")
    
    # Task 3: Integrate Feedback into Worker Scoring
    task_3 = task_master.add_task(
        title="Integrate Historical Feedback into Worker Suitability Scoring",
        description="""Modify the calculate_suitability_score method in dynamic_worker_allocation.py to:
        
1. Retrieve historical feedback for the worker
2. Calculate weighted scores based on:
   - Historical success rate for similar tasks
   - Average performance metrics
   - Quality scores from previous executions
   - Recent performance trends (improvement/degradation)
   
3. Adjust suitability score based on:
   - Task type match with worker's historical performance
   - Recent feedback weight (more recent = higher weight)
   - Consistency of performance
   
4. Add configuration for feedback weight in scoring algorithm""",
        priority="high",
        dependencies=[task_1.id, task_2.id]  # Depends on storage and collection
    )
    print(f"Added task: {task_3.title} (ID: {task_3.id})")
    
    # Task 4: Create Feedback Analytics Dashboard
    task_4 = task_master.add_task(
        title="Create Feedback Analytics Dashboard",
        description="""Implement analytics and visualization for feedback data:
        
1. Worker performance trends over time
2. Task success rates by worker and task type
3. Performance comparison between workers
4. Identification of worker strengths/weaknesses
5. Recommendations for worker-task matching
6. Export functionality for reports""",
        priority="medium",
        dependencies=[task_1.id]  # Depends on storage
    )
    print(f"Added task: {task_4.title} (ID: {task_4.id})")
    
    # Task 5: Add Feedback-Based Worker Training
    task_5 = task_master.add_task(
        title="Implement Feedback-Based Worker Optimization",
        description="""Create a system to improve worker performance based on feedback:
        
1. Identify performance patterns and issues
2. Generate targeted improvement suggestions
3. Adjust worker capabilities based on demonstrated performance
4. Create worker specialization profiles
5. Implement adaptive complexity assignment based on feedback""",
        priority="medium",
        dependencies=[task_3.id]  # Depends on feedback integration
    )
    print(f"Added task: {task_5.title} (ID: {task_5.id})")
    
    # Save tasks
    task_master.save_tasks()
    
    print(f"\nTotal tasks added: 5")
    print("\nThese tasks will implement the missing feedback integration functionality for Task 21.")

if __name__ == "__main__":
    main()