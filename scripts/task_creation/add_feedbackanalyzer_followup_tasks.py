#!/usr/bin/env python3
"""
Add follow-up tasks for implementing FeedbackAnalyzer integration
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_orchestrator.task_master import TaskManager

def main():
    tm = TaskManager()
    
    tasks = [
        {
            "title": "Implement FeedbackAnalyzer class in feedback_analysis.py",
            "description": "Create FeedbackAnalyzer class with methods: collect_feedback(), analyze_performance(), get_worker_insights(), and store_analysis_results()",
            "priority": "high",
            "details": """
Implement the core FeedbackAnalyzer class with the following structure:

```python
class FeedbackAnalyzer:
    def __init__(self):
        # Initialize feedback storage and metrics
        
    def collect_feedback(self, task_id: str, worker_id: str, result: Any) -> Dict:
        # Collect feedback data from task execution
        
    def analyze_performance(self, worker_id: str) -> Dict:
        # Analyze worker performance based on historical data
        
    def get_worker_insights(self) -> Dict:
        # Get insights about all workers' performance
        
    def store_analysis_results(self, task_id: str, analysis: Dict):
        # Store analysis results with task data
```
"""
        },
        {
            "title": "Integrate FeedbackAnalyzer into enhanced_orchestrator.py task processing",
            "description": "Add feedback collection calls in the process_task method after task completion",
            "priority": "high", 
            "details": """
Modify enhanced_orchestrator.py to:
1. Import FeedbackAnalyzer
2. Initialize FeedbackAnalyzer instance in EnhancedOrchestrator.__init__
3. Add feedback collection in process_task after task completion:
   - Call collect_feedback() with task result
   - Store feedback data in task context
4. Handle any exceptions from feedback collection gracefully
"""
        },
        {
            "title": "Implement feedback-based worker allocation logic",
            "description": "Modify DynamicWorkerAllocator to use FeedbackAnalyzer insights for worker selection",
            "priority": "high",
            "details": """
Update DynamicWorkerAllocator to:
1. Get worker insights from FeedbackAnalyzer
2. Consider historical performance in allocate_worker method
3. Weight feedback data alongside capabilities and complexity
4. Prefer workers with better performance for similar tasks
5. Add fallback logic if no feedback data exists
"""
        },
        {
            "title": "Add feedback analysis storage to task metadata",
            "description": "Store feedback analysis results with task data in the task context",
            "priority": "medium",
            "details": """
Modify task storage to:
1. Add 'feedback_analysis' field to task context metadata
2. Store analysis results after each task completion
3. Include performance metrics, success rates, and insights
4. Ensure persistence across orchestrator restarts
"""
        },
        {
            "title": "Create comprehensive tests for FeedbackAnalyzer integration",
            "description": "Write unit and integration tests for all FeedbackAnalyzer functionality",
            "priority": "medium", 
            "details": """
Create tests covering:
1. FeedbackAnalyzer class methods
2. Integration with enhanced_orchestrator
3. Worker allocation with feedback data
4. Storage and retrieval of feedback analysis
5. Edge cases and error handling
6. Performance impact of feedback collection
"""
        }
    ]
    
    print("Adding FeedbackAnalyzer implementation follow-up tasks...")
    
    for task_data in tasks:
        task = tm.add_task(**task_data)
        print(f"✅ Added task {task.id}: {task.title}")
    
    print(f"\nTotal tasks added: {len(tasks)}")
    print("\nThese tasks will be prioritized due to 'followup' and 'opus-manager-review' tags.")

if __name__ == "__main__":
    main()