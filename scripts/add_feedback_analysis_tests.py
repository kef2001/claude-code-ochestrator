#!/usr/bin/env python3
"""Add follow-up tasks for feedback analysis module testing."""

import json
import os
import uuid
from datetime import datetime
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_orchestrator.file_paths import file_paths

def add_task(title, description, priority="high", tags=None):
    """Add a task to the tasks.json file."""
    tasks_file = file_paths.folders['tasks'] / 'tasks.json'
    
    # Load existing tasks
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Create new task
    task = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "priority": priority,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "tags": tags or []
    }
    
    # Add to tasks
    data["tasks"].append(task)
    
    # Save
    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Added task: {title}")
    return task["id"]

def main():
    """Add feedback analysis testing tasks."""
    
    # Task 1: Create the test file structure
    add_task(
        title="Create tests/test_feedback_analysis.py with basic structure and imports",
        description=(
            "Create the test file tests/test_feedback_analysis.py with:\n"
            "1. Proper imports (unittest, mock, sys, os)\n"
            "2. Test class structure for FeedbackAnalyzer\n"
            "3. setUp and tearDown methods\n"
            "4. Basic test method stubs for all required functionality"
        ),
        priority="high",
        tags=["testing", "feedback-analysis", "followup"]
    )
    
    # Task 2: Implement FeedbackAnalyzer method tests
    add_task(
        title="Implement comprehensive unit tests for FeedbackAnalyzer methods",
        description=(
            "In tests/test_feedback_analysis.py, implement tests for:\n"
            "1. test_init - Test FeedbackAnalyzer initialization\n"
            "2. test_analyze_task_feedback - Test feedback analysis logic\n"
            "3. test_generate_improvement_suggestions - Test suggestion generation\n"
            "4. test_prioritize_feedback - Test feedback prioritization\n"
            "5. test_aggregate_feedback - Test feedback aggregation across tasks"
        ),
        priority="high",
        tags=["testing", "feedback-analysis", "followup"]
    )
    
    # Task 3: Data model validation tests
    add_task(
        title="Add data model validation tests for feedback analysis",
        description=(
            "Add tests in tests/test_feedback_analysis.py for:\n"
            "1. test_feedback_data_validation - Validate feedback data structure\n"
            "2. test_invalid_feedback_handling - Test handling of malformed data\n"
            "3. test_feedback_schema_compliance - Ensure data follows expected schema\n"
            "4. test_data_type_conversions - Test type conversions and transformations"
        ),
        priority="high",
        tags=["testing", "feedback-analysis", "validation", "followup"]
    )
    
    # Task 4: Algorithm accuracy tests
    add_task(
        title="Create algorithm accuracy tests for feedback analysis",
        description=(
            "Implement accuracy tests in tests/test_feedback_analysis.py:\n"
            "1. test_sentiment_analysis_accuracy - Test sentiment detection accuracy\n"
            "2. test_category_classification - Test feedback categorization\n"
            "3. test_priority_scoring - Test priority calculation algorithms\n"
            "4. test_confidence_scores - Test confidence level calculations\n"
            "5. Include sample test data with known expected outputs"
        ),
        priority="medium",
        tags=["testing", "feedback-analysis", "algorithms", "followup"]
    )
    
    # Task 5: Edge cases and error handling
    add_task(
        title="Implement edge case and error handling tests",
        description=(
            "Add edge case tests in tests/test_feedback_analysis.py:\n"
            "1. test_empty_feedback - Handle empty feedback data\n"
            "2. test_null_values - Handle None/null values gracefully\n"
            "3. test_large_feedback_sets - Test with large data volumes\n"
            "4. test_unicode_handling - Test special characters and unicode\n"
            "5. test_concurrent_analysis - Test thread safety if applicable\n"
            "6. test_memory_efficiency - Ensure no memory leaks"
        ),
        priority="high",
        tags=["testing", "feedback-analysis", "error-handling", "followup"]
    )
    
    # Task 6: Integration tests with mocked orchestrator
    add_task(
        title="Create integration tests with mocked orchestrator components",
        description=(
            "Add integration tests in tests/test_feedback_analysis.py:\n"
            "1. Mock orchestrator interfaces and dependencies\n"
            "2. test_orchestrator_feedback_flow - Test full feedback flow\n"
            "3. test_task_completion_feedback - Test feedback on task completion\n"
            "4. test_feedback_persistence - Test feedback storage/retrieval\n"
            "5. test_feedback_reporting - Test report generation\n"
            "Use unittest.mock for all orchestrator dependencies"
        ),
        priority="medium",
        tags=["testing", "feedback-analysis", "integration", "followup"]
    )
    
    # Task 7: Performance benchmarks
    add_task(
        title="Add performance benchmark tests for feedback analysis",
        description=(
            "Create performance tests in tests/test_feedback_analysis.py:\n"
            "1. test_analysis_speed - Benchmark analysis speed\n"
            "2. test_memory_usage - Monitor memory consumption\n"
            "3. test_scalability - Test with increasing data sizes\n"
            "4. test_response_times - Measure operation latencies\n"
            "5. Create performance baseline metrics\n"
            "Use time.perf_counter() and memory_profiler if available"
        ),
        priority="low",
        tags=["testing", "feedback-analysis", "performance", "followup"]
    )
    
    print("\nSuccessfully added 7 follow-up tasks for feedback analysis testing!")

if __name__ == "__main__":
    main()