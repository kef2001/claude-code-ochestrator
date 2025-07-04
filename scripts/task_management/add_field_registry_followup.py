#!/usr/bin/env python3
"""
Add follow-up task for implementing field registry system
"""

from claude_orchestrator.task_master import TaskManager

def main():
    tm = TaskManager()
    
    task = tm.add_task(
        title="Implement field registry system with all field types",
        description="""Properly implement field registry system for custom field types including:
        
1. BaseField abstract class with common interface
2. Specific field implementations:
   - TextField (with max_length validation)
   - NumberField (with min/max validation)
   - BooleanField
   - DateField (with date format validation)
   - EmailField (with email validation)
   - URLField (with URL validation)
   - SelectField (with choices validation)
   - MultiSelectField (with multiple choices validation)
3. Field validation methods for each type
4. Serialization/deserialization methods
5. Field registry class to manage all field types
6. Comprehensive unit tests for all field types

This task should create actual code files with working implementations, not just placeholder comments.""",
        priority="high"
    )
    
    print(f"Created follow-up task: {task.id}")
    print(f"Title: {task.title}")
    print(f"Priority: {task.priority}")

if __name__ == "__main__":
    main()