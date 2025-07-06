#!/usr/bin/env python3
"""Test script to diagnose worker issue"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Monkey-patch to bypass requests import
sys.modules['requests'] = type(sys)('requests')

import json
from pathlib import Path

def check_task_states():
    """Check task states in the task file"""
    task_file = Path(".taskmaster/tasks/tasks.json")
    
    if not task_file.exists():
        print("Task file not found!")
        return
    
    with open(task_file, 'r') as f:
        data = json.load(f)
    
    tasks = data.get('tasks', [])
    print(f"Total tasks in file: {len(tasks)}")
    
    # Count by status
    status_counts = {}
    for task in tasks:
        status = task.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("\nTask status breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    
    # Show first few tasks
    print("\nFirst 3 tasks:")
    for i, task in enumerate(tasks[:3]):
        print(f"\n  Task {i+1}:")
        print(f"    ID: {task.get('id')}")
        print(f"    Title: {task.get('title')}")
        print(f"    Status: {task.get('status')}")
        print(f"    Priority: {task.get('priority')}")

if __name__ == "__main__":
    check_task_states()