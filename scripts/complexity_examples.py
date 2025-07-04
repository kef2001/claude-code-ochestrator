#!/usr/bin/env python3
"""
Example usage of the Task Complexity Scoring System
"""

from task_complexity_scorer import TaskComplexityScorer, TaskMetrics, ComplexityLevel


def main():
    scorer = TaskComplexityScorer()
    
    # Example 1: Simple data processing task
    simple_task = TaskMetrics(
        input_size=50,      # 50MB data
        compute_intensity=3, # Low-moderate processing
        output_size=25,     # 25MB output
        time_sensitivity=2,  # Not urgent
        resource_dependencies=1  # One external API
    )
    
    # Example 2: Complex ML training task
    complex_task = TaskMetrics(
        input_size=5000,    # 5GB dataset
        compute_intensity=9, # High computational load
        output_size=100,    # 100MB model
        time_sensitivity=7,  # Time-sensitive
        resource_dependencies=4  # Multiple GPU/cloud resources
    )
    
    # Example 3: Trivial file operation
    trivial_task = TaskMetrics(
        input_size=1,       # 1MB file
        compute_intensity=1, # Minimal processing
        output_size=1,      # 1MB output
        time_sensitivity=1,  # No urgency
        resource_dependencies=0  # No dependencies
    )
    
    tasks = [
        ("Simple Data Processing", simple_task),
        ("ML Model Training", complex_task),
        ("File Copy Operation", trivial_task)
    ]
    
    for name, task in tasks:
        result = scorer.score_task(task)
        print(f"\n{name}:")
        print(f"  Score: {result['score']}/100")
        print(f"  Level: {result['level'].name}")
        print(f"  Breakdown:")
        for component, value in result['breakdown'].items():
            print(f"    {component}: {value}")


if __name__ == "__main__":
    main()