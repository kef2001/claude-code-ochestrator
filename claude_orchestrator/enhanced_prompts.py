"""
Enhanced Prompts for Worker-Reviewer Communication
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
import json


class EnhancedPromptSystem:
    """Manages enhanced prompts for workers and reviewers"""
    
    @staticmethod
    def get_worker_prompt(task: Dict[str, Any], context: Dict[str, Any] = None) -> str:
        """Generate comprehensive worker prompt with clear expectations"""
        task_type = task.get('type', 'general')
        task_id = task.get('id', 'unknown')
        
        # Base prompt structure
        prompt = f"""# Task Execution Instructions

## Task Details
- **Task ID**: {task_id}
- **Title**: {task.get('title', 'No title')}
- **Type**: {task_type}
- **Priority**: {task.get('priority', 'normal')}

## Task Description
{task.get('description', 'No description provided')}

## CRITICAL REQUIREMENTS

### 1. IMPLEMENTATION REQUIREMENTS
- You MUST actually implement the requested functionality, not just describe it
- You MUST create or modify real files in the appropriate directories
- You MUST write actual, working code that can be executed
- You MUST test your implementation if possible

### 2. FILE ORGANIZATION
The project follows strict file organization rules:
- **Scripts** (*.py): Place in `scripts/` directory
- **Documentation** (*.md): Place in `docs/` directory  
- **Design documents**: Place in `designs/` directory
- **Examples**: Place in `examples/` directory
- **Core code**: Modify files in `claude_orchestrator/` directory

Example paths:
- Script: `scripts/add_new_feature.py`
- Documentation: `docs/feature_guide.md`
- Design: `designs/task_{task_id}_design.md`

### 3. IMPLEMENTATION TRACKING
After completing your work, you MUST provide:
1. **Files Created**: List every file you created with full path
2. **Files Modified**: List every file you modified with full path
3. **Implementation Summary**: Detailed description of what you implemented
4. **Code Examples**: Include key code snippets from your implementation

### 4. VALIDATION CHECKLIST
Before marking the task complete, verify:
- [ ] All requested functionality is implemented
- [ ] Files are created in correct directories
- [ ] Code is syntactically correct
- [ ] Implementation matches task requirements
- [ ] All changes are clearly documented

"""
        
        # Add type-specific instructions
        if task_type == 'documentation':
            prompt += """
## Documentation-Specific Requirements
1. Create actual markdown files in the `docs/` directory
2. Use proper markdown formatting with headers, lists, code blocks
3. Include practical examples and use cases
4. Ensure documentation is comprehensive and clear
5. Add a table of contents for longer documents

Example structure:
```markdown
# Documentation Title

## Table of Contents
1. [Overview](#overview)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Examples](#examples)

## Overview
[Your content here]
```
"""
        
        elif task_type == 'implementation':
            prompt += """
## Implementation-Specific Requirements
1. Write production-ready code with proper error handling
2. Follow Python best practices and PEP 8 style guide
3. Include type hints where appropriate
4. Add docstrings to all functions and classes
5. Implement proper logging using the logger

Example structure:
```python
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class YourClass:
    \"\"\"Description of your class.\"\"\"
    
    def your_method(self, param: str) -> Optional[Dict[str, Any]]:
        \"\"\"
        Description of your method.
        
        Args:
            param: Description of parameter
            
        Returns:
            Description of return value
        \"\"\"
        try:
            # Your implementation
            result = {}
            logger.info(f"Successfully processed {param}")
            return result
        except Exception as e:
            logger.error(f"Error processing {param}: {e}")
            return None
```
"""
        
        elif task_type == 'testing':
            prompt += """
## Testing-Specific Requirements
1. Create test files in appropriate test directories
2. Use pytest framework for Python tests
3. Include unit tests and integration tests where applicable
4. Ensure tests are runnable and pass
5. Include test documentation

Example test structure:
```python
import pytest
from unittest.mock import Mock, patch

class TestYourFeature:
    \"\"\"Test suite for your feature.\"\"\"
    
    def test_basic_functionality(self):
        \"\"\"Test basic functionality works as expected.\"\"\"
        # Arrange
        input_data = {...}
        
        # Act
        result = your_function(input_data)
        
        # Assert
        assert result is not None
        assert result['status'] == 'success'
```
"""
        
        # Add context if provided
        if context:
            prompt += f"""
## Additional Context
{json.dumps(context, indent=2)}
"""
        
        # Add final instructions
        prompt += """
## Output Format

When you complete the task, structure your response as follows:

### Implementation Summary
[Describe what you implemented in 2-3 sentences]

### Files Created
- `path/to/file1.py` - Description of what this file does
- `path/to/file2.md` - Description of what this file contains

### Files Modified  
- `path/to/existing.py` - Description of changes made

### Key Implementation Details
[Include important code snippets or configuration details]

### Testing/Validation
[Describe how you validated the implementation works]

---
Remember: You are creating REAL files and REAL implementations. This is not a simulation or description exercise.
"""
        
        return prompt
        
    @staticmethod
    def get_reviewer_prompt(task: Dict[str, Any], worker_result: Dict[str, Any]) -> str:
        """Generate comprehensive reviewer prompt"""
        return f"""# Task Review Instructions

## Original Task
- **ID**: {task.get('id')}
- **Title**: {task.get('title')}
- **Type**: {task.get('type')}

## Task Requirements
{task.get('description')}

## Worker Output
{worker_result.get('output', 'No output provided')}

## Files Reported
- **Created**: {worker_result.get('created_files', [])}
- **Modified**: {worker_result.get('modified_files', [])}

## Review Checklist

### 1. Completeness Check
- [ ] All task requirements addressed
- [ ] Actual implementation provided (not just description)
- [ ] Files created/modified as claimed

### 2. Quality Check  
- [ ] Code follows project standards
- [ ] Proper error handling implemented
- [ ] Documentation is clear and complete

### 3. File Organization Check
- [ ] Scripts placed in `scripts/` directory
- [ ] Documentation placed in `docs/` directory
- [ ] Files follow naming conventions

### 4. Validation
- [ ] Implementation can be executed/used
- [ ] No obvious bugs or issues
- [ ] Matches the requested functionality

## Review Actions

Based on your review, determine:
1. **APPROVED**: Implementation is complete and correct
2. **NEEDS REVISION**: Specific issues need to be fixed
3. **REJECTED**: Implementation is missing or completely wrong

Provide specific feedback on what needs to be improved if not approved.
"""
        
    @staticmethod
    def get_validation_prompt(files: List[str]) -> str:
        """Generate prompt for validating file existence and content"""
        return f"""# File Validation Check

Please verify the following files exist and contain appropriate content:

## Files to Validate
{chr(10).join(f"- {file}" for file in files)}

For each file:
1. Check if it exists at the specified path
2. Verify it contains actual implementation (not placeholder)
3. Ensure content matches its intended purpose
4. Confirm proper formatting and structure

Report any files that:
- Don't exist
- Contain only placeholders or TODOs
- Don't match their intended purpose
- Have syntax errors or formatting issues
"""