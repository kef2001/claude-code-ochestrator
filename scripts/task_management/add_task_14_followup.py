#!/usr/bin/env python3
"""
Follow-up task for Task 14: Proper Feedback Data Model Schema Design
"""

import json
import sys
sys.path.insert(0, '.')

from claude_orchestrator.task_master import TaskMaster

# Initialize TaskMaster
tm = TaskMaster()

# Add the follow-up task
task_prompt = """Design and implement concrete feedback data model schema with the following requirements:

1) Define rating fields supporting:
   - Numeric scales (1-10)
   - Star ratings (1-5 stars)
   - NPS scores (0-10)

2) Create comment/text fields with validation rules:
   - Max length constraints
   - Required/optional field indicators
   - Input sanitization rules

3) Design metadata structure including:
   - Timestamps (created_at, updated_at)
   - User information (user_id, email, name)
   - Context data (page_url, feature_name, session_id)

4) Provide complete examples:
   - JSON schema with full field definitions
   - SQL database schema (CREATE TABLE statements)
   - NoSQL document structure example

5) Include data validation rules and constraints for each field type

The output should be a comprehensive, production-ready data model design document."""

task_id = tm.add_task(task_prompt, priority="high")
print(f"Created follow-up task with ID: {task_id}")