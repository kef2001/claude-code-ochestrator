#!/usr/bin/env python3
"""Follow-up task creation script for Task 4: Task Decomposition Integration"""

import subprocess
import sys

def main():
    """Create follow-up task for implementing feedback collection in task decomposition"""
    
    task_prompt = """Implement feedback collection in task decomposition workflow:
1. Integrate the existing feedback collection module (from Task 3) into the TaskDecomposer class
2. Add methods to collect user feedback after decomposition
3. Store feedback data persistently
4. Ensure non-blocking collection (async or background)
5. Add configuration options for enabling/disabling feedback
6. Include integration tests to verify the workflow
7. Update task_decomposer.py with the new functionality"""
    
    cmd = [
        sys.executable,
        "claude_orchestrator/task_master.py",
        "add-task",
        "--prompt", task_prompt,
        "--priority", "high"
    ]
    
    print("Creating follow-up task for Task 4...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Successfully created follow-up task")
        print(result.stdout)
    else:
        print("❌ Failed to create follow-up task")
        print(result.stderr)

if __name__ == "__main__":
    main()