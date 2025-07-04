"""
Enhanced Review System with comprehensive result discovery and validation
"""
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging

from .worker_result_manager import WorkerResultManager, WorkerResult, ResultStatus
from .review_applier import ReviewApplier
from .task_master import TaskMaster

logger = logging.getLogger(__name__)


class EnhancedReviewSystem:
    """Enhanced review system with better worker output discovery and validation"""
    
    def __init__(self, result_manager: WorkerResultManager = None):
        self.result_manager = result_manager or WorkerResultManager()
        self.review_applier = ReviewApplier()
        self.task_master = TaskMaster()
        
    async def review_task(self, task_id: str) -> Dict[str, Any]:
        """Comprehensive task review process"""
        logger.info(f"Starting review for task {task_id}")
        
        # Step 1: Get task details
        task = await self._get_task_details(task_id)
        if not task:
            return self._create_review_result(task_id, False, "Task not found")
            
        # Step 2: Find worker result
        worker_result = self.result_manager.get_latest_result(task_id)
        if not worker_result:
            # Fallback to file-based result
            worker_result = await self._find_file_based_result(task_id)
            if not worker_result:
                return self._create_review_result(task_id, False, "No worker result found")
                
        # Step 3: Validate result
        validation_passed, validation_message = self._validate_worker_result(worker_result, task)
        
        # Step 4: Extract implementation details
        implementation = self._extract_implementation(worker_result)
        
        # Step 5: Create review document
        review_doc = await self._create_review_document(
            task, worker_result, validation_passed, validation_message, implementation
        )
        
        # Step 6: Apply changes if validation passed
        if validation_passed and implementation['has_changes']:
            apply_success = await self._apply_changes(implementation, task_id)
            if not apply_success:
                validation_passed = False
                validation_message = "Failed to apply changes"
                
        # Step 7: Update task status
        await self._update_task_status(task_id, validation_passed)
        
        return self._create_review_result(
            task_id, validation_passed, validation_message, review_doc
        )
        
    async def _get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task details from task master"""
        try:
            return self.task_master.get_task(task_id)
        except Exception as e:
            logger.error(f"Failed to get task details: {e}")
            return None
            
    async def _find_file_based_result(self, task_id: str) -> Optional[WorkerResult]:
        """Find result from file system (backward compatibility)"""
        # Check standard locations
        result_paths = [
            Path(f".taskmaster/tasks/task_{task_id}.result.json"),
            Path(f"task_{task_id}.result.json"),
            Path(f".taskmaster/results/task_{task_id}.json")
        ]
        
        for path in result_paths:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                        
                    # Convert to WorkerResult
                    return WorkerResult(
                        task_id=task_id,
                        worker_id=data.get('worker_id', 'unknown'),
                        status=ResultStatus.SUCCESS if data.get('success') else ResultStatus.FAILED,
                        output=data.get('output', ''),
                        created_files=data.get('files', {}).get('created', []),
                        modified_files=data.get('files', {}).get('modified', []),
                        execution_time=data.get('usage', {}).get('execution_time', 0),
                        tokens_used=data.get('usage', {}).get('tokens_used', 0),
                        timestamp=datetime.now().isoformat(),
                        error_message=data.get('error')
                    )
                except Exception as e:
                    logger.error(f"Failed to load result from {path}: {e}")
                    
        return None
        
    def _validate_worker_result(self, result: WorkerResult, task: Dict[str, Any]) -> Tuple[bool, str]:
        """Comprehensive result validation"""
        # Basic validation from result manager
        is_valid, message = self.result_manager.validate_result(result.task_id)
        if not is_valid:
            return False, message
            
        # Task-specific validation
        task_type = task.get('type', 'general')
        
        if task_type == 'documentation':
            # Check for documentation files
            doc_files = [f for f in result.created_files if f.endswith('.md')]
            if not doc_files:
                return False, "Documentation task completed without creating any .md files"
                
        elif task_type == 'implementation':
            # Check for code files
            code_files = [f for f in result.created_files + result.modified_files 
                         if f.endswith(('.py', '.js', '.ts', '.jsx', '.tsx'))]
            if not code_files and 'implement' in task.get('title', '').lower():
                return False, "Implementation task completed without creating/modifying code files"
                
        # Check output quality
        output_lines = result.output.strip().split('\n')
        if len(output_lines) < 5:
            return False, "Worker output too brief for meaningful implementation"
            
        # Check for specific task requirements
        requirements = self._extract_requirements(task.get('description', ''))
        missing_requirements = self._check_requirements(result, requirements)
        if missing_requirements:
            return False, f"Missing requirements: {', '.join(missing_requirements)}"
            
        return True, "All validations passed"
        
    def _extract_requirements(self, description: str) -> List[str]:
        """Extract specific requirements from task description"""
        requirements = []
        
        # Common requirement patterns
        patterns = [
            r"must (?:create|implement|add) (.+?)(?:\.|,|\n|$)",
            r"should (?:create|implement|add) (.+?)(?:\.|,|\n|$)",
            r"(?:create|implement|add) (?:a |an |the )?(.+?)(?:\.|,|\n|$)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            requirements.extend(matches)
            
        return requirements
        
    def _check_requirements(self, result: WorkerResult, requirements: List[str]) -> List[str]:
        """Check which requirements are missing"""
        missing = []
        
        all_content = result.output.lower()
        all_files = ' '.join(result.created_files + result.modified_files).lower()
        
        for req in requirements:
            req_lower = req.lower()
            # Check if requirement is mentioned in output or files
            if req_lower not in all_content and req_lower not in all_files:
                # Check for partial matches
                req_words = req_lower.split()
                if len(req_words) > 2:
                    # For longer requirements, check if most words are present
                    matches = sum(1 for word in req_words if word in all_content or word in all_files)
                    if matches < len(req_words) * 0.6:
                        missing.append(req)
                else:
                    missing.append(req)
                    
        return missing
        
    def _extract_implementation(self, result: WorkerResult) -> Dict[str, Any]:
        """Extract implementation details from worker output"""
        implementation = {
            'has_changes': False,
            'files': [],
            'code_blocks': [],
            'commands': []
        }
        
        # Extract file operations
        file_patterns = [
            r"(?:created?|wrote|generated?) (?:file |new file )?['\"`]?([^\s'\"]+)['\"`]?",
            r"(?:modified?|updated?) (?:file )?['\"`]?([^\s'\"]+)['\"`]?",
            r"```(?:python|javascript|typescript|jsx|tsx|bash|sh)\n(.+?)```",
        ]
        
        for pattern in file_patterns[:2]:
            matches = re.findall(pattern, result.output, re.IGNORECASE)
            implementation['files'].extend(matches)
            
        # Extract code blocks
        code_block_pattern = r"```(?P<lang>\w+)?\n(?P<code>.+?)```"
        for match in re.finditer(code_block_pattern, result.output, re.DOTALL):
            implementation['code_blocks'].append({
                'language': match.group('lang') or 'text',
                'code': match.group('code')
            })
            implementation['has_changes'] = True
            
        # Extract commands
        command_patterns = [
            r"(?:run|execute) `(.+?)`",
            r"command: `(.+?)`",
        ]
        
        for pattern in command_patterns:
            matches = re.findall(pattern, result.output, re.IGNORECASE)
            implementation['commands'].extend(matches)
            
        # Check tracked files
        if result.created_files or result.modified_files:
            implementation['has_changes'] = True
            implementation['tracked_files'] = {
                'created': result.created_files,
                'modified': result.modified_files
            }
            
        return implementation
        
    async def _create_review_document(self, task: Dict[str, Any], result: WorkerResult,
                                    validation_passed: bool, validation_message: str,
                                    implementation: Dict[str, Any]) -> str:
        """Create comprehensive review document"""
        review_path = Path(f"docs/task_{task['id']}_review.md")
        review_path.parent.mkdir(exist_ok=True)
        
        status_emoji = "✅" if validation_passed else "❌"
        status_text = "COMPLETED" if validation_passed else "NOT COMPLETED"
        
        review_content = f"""# Review: Task {task['id']}

## Task Details
- **ID**: {task['id']}
- **Title**: {task['title']}
- **Type**: {task.get('type', 'general')}
- **Status**: {status_emoji} {status_text}
- **Worker**: {result.worker_id}
- **Execution Time**: {result.execution_time:.2f}s
- **Tokens Used**: {result.tokens_used}

## Review Summary

{validation_message}

## Implementation Analysis

### Files Created
"""
        
        if result.created_files:
            for file in result.created_files:
                review_content += f"- `{file}`\n"
        else:
            review_content += "- None\n"
            
        review_content += "\n### Files Modified\n"
        
        if result.modified_files:
            for file in result.modified_files:
                review_content += f"- `{file}`\n"
        else:
            review_content += "- None\n"
            
        if implementation['code_blocks']:
            review_content += "\n### Code Implementations\n"
            for i, block in enumerate(implementation['code_blocks']):
                review_content += f"\n#### Code Block {i+1} ({block['language']})\n"
                review_content += f"```{block['language']}\n{block['code']}\n```\n"
                
        if not validation_passed:
            review_content += f"\n## Validation Issues\n\n{validation_message}\n"
            
        review_content += f"\n## Next Steps\n\n"
        
        if validation_passed:
            review_content += "- Changes have been applied successfully\n"
            review_content += "- Task marked as completed\n"
        else:
            review_content += "- Task needs to be retried with proper implementation\n"
            review_content += "- Review worker prompts and instructions\n"
            
        review_content += f"\n---\n*Review completed at {datetime.now().isoformat()}*\n"
        
        with open(review_path, 'w') as f:
            f.write(review_content)
            
        return str(review_path)
        
    async def _apply_changes(self, implementation: Dict[str, Any], task_id: str) -> bool:
        """Apply validated changes from worker implementation"""
        try:
            # Use the existing ReviewApplier for code changes
            if implementation.get('code_blocks'):
                for block in implementation['code_blocks']:
                    # Extract file path from context or use task-based naming
                    file_path = self._determine_file_path(block, task_id)
                    if file_path:
                        self.review_applier.apply_file_change(
                            file_path, block['code'], 'create'
                        )
                        
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply changes: {e}")
            return False
            
    def _determine_file_path(self, code_block: Dict[str, Any], task_id: str) -> Optional[str]:
        """Determine appropriate file path for code block"""
        # This is a simplified version - in practice, would need more sophisticated parsing
        language = code_block.get('language', '')
        
        extension_map = {
            'python': '.py',
            'javascript': '.js',
            'typescript': '.ts',
            'bash': '.sh',
            'markdown': '.md'
        }
        
        extension = extension_map.get(language, '.txt')
        
        # Check if code contains file path hints
        code = code_block['code']
        file_pattern = r"(?:File:|file:|#|//)\s*([^\s]+\.\w+)"
        match = re.search(file_pattern, code)
        
        if match:
            return match.group(1)
            
        # Default naming
        return f"scripts/task_{task_id}_implementation{extension}"
        
    async def _update_task_status(self, task_id: str, success: bool):
        """Update task status in task master"""
        try:
            status = 'completed' if success else 'failed'
            self.task_master.update_task_status(task_id, status)
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
            
    def _create_review_result(self, task_id: str, success: bool, 
                            message: str, review_path: str = None) -> Dict[str, Any]:
        """Create standardized review result"""
        return {
            'task_id': task_id,
            'success': success,
            'message': message,
            'review_path': review_path,
            'timestamp': datetime.now().isoformat()
        }