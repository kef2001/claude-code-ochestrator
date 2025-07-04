"""
Enhanced Worker Session with improved result reporting and file tracking
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import hashlib

from .claude_session_worker import ClaudeSessionWorker
from .worker_result_manager import WorkerResult, ResultStatus, WorkerResultManager


class FileTracker:
    """Tracks file operations during task execution"""
    
    def __init__(self):
        self.initial_state: Dict[str, str] = {}
        self.created_files: Set[str] = set()
        self.modified_files: Set[str] = set()
        self.deleted_files: Set[str] = set()
        
    def scan_directory(self, base_path: Path, patterns: List[str] = None):
        """Scan directory and record file states"""
        if patterns is None:
            patterns = ['*.py', '*.md', '*.json', '*.yaml', '*.yml']
            
        file_states = {}
        for pattern in patterns:
            for file_path in base_path.rglob(pattern):
                if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
                    file_hash = self._hash_file(file_path)
                    file_states[str(file_path)] = file_hash
                    
        return file_states
        
    def _hash_file(self, file_path: Path) -> str:
        """Calculate file hash"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
            
    def start_tracking(self, base_path: Path):
        """Start tracking file changes"""
        self.initial_state = self.scan_directory(base_path)
        
    def detect_changes(self, base_path: Path) -> Dict[str, List[str]]:
        """Detect file changes since tracking started"""
        current_state = self.scan_directory(base_path)
        
        # Find created files
        for file_path in current_state:
            if file_path not in self.initial_state:
                self.created_files.add(file_path)
                
        # Find modified and deleted files
        for file_path, old_hash in self.initial_state.items():
            if file_path not in current_state:
                self.deleted_files.add(file_path)
            elif current_state[file_path] != old_hash:
                self.modified_files.add(file_path)
                
        return {
            'created': list(self.created_files),
            'modified': list(self.modified_files),
            'deleted': list(self.deleted_files)
        }


class EnhancedClaudeSessionWorker(ClaudeSessionWorker):
    """Enhanced worker with better result reporting and validation"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_tracker = FileTracker()
        self.result_manager = WorkerResultManager()
        self.execution_log: List[str] = []
        
    def run(self):
        """Enhanced run method with comprehensive result tracking"""
        start_time = time.time()
        base_path = Path.cwd()
        
        # Start file tracking
        self.file_tracker.start_tracking(base_path)
        
        # Load and validate task
        task = self._load_task()
        if not task:
            self._report_error("Failed to load task", start_time)
            return
            
        task_id = task.get('id', 'unknown')
        self.log(f"Starting task {task_id}: {task.get('title', 'No title')}")
        
        try:
            # Execute task with enhanced prompting
            result = self._execute_task_with_validation(task)
            
            # Detect file changes
            file_changes = self.file_tracker.detect_changes(base_path)
            
            # Prepare detailed result
            execution_time = time.time() - start_time
            worker_result = WorkerResult(
                task_id=task_id,
                worker_id=self.worker_id,
                status=ResultStatus.SUCCESS if result['success'] else ResultStatus.FAILED,
                output=result['output'],
                created_files=file_changes['created'],
                modified_files=file_changes['modified'],
                execution_time=execution_time,
                tokens_used=result.get('usage', {}).get('tokens_used', 0),
                timestamp=datetime.now().isoformat(),
                error_message=result.get('error'),
                metadata={
                    'deleted_files': file_changes['deleted'],
                    'execution_log': self.execution_log,
                    'task_type': task.get('type', 'unknown'),
                    'task_tags': task.get('tags', [])
                }
            )
            
            # Store result in database
            result_id = self.result_manager.store_result(worker_result)
            
            # Also save to file for backward compatibility
            self._save_result_file(worker_result)
            
            # Validate result
            is_valid, validation_message = self.result_manager.validate_result(task_id)
            if not is_valid:
                self.log(f"WARNING: Result validation failed: {validation_message}")
                worker_result.validation_passed = False
                self.result_manager.mark_validated(task_id, False)
            else:
                worker_result.validation_passed = True
                self.result_manager.mark_validated(task_id, True)
                
            self.log(f"Task completed. Result ID: {result_id}, Validation: {'PASSED' if is_valid else 'FAILED'}")
            
        except Exception as e:
            self._report_error(f"Task execution failed: {str(e)}", start_time, task_id)
            
    def _execute_task_with_validation(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with enhanced validation prompting"""
        task_type = task.get('type', 'general')
        
        # Build enhanced prompt
        prompt_parts = [
            f"Task ID: {task.get('id', 'unknown')}",
            f"Title: {task.get('title', 'No title')}",
            f"Type: {task_type}",
            f"\nDescription:\n{task.get('description', 'No description')}",
            "\n" + "="*50 + "\n",
            "IMPORTANT INSTRUCTIONS:",
            "1. You MUST actually implement the requested functionality",
            "2. You MUST create/modify actual files as needed",
            "3. You MUST provide specific details about what you implemented",
            "4. You MUST NOT just describe what you would do - actually do it",
            "5. If you cannot complete the task, explain specifically why",
            "\nFor file operations:",
            "- Use actual file paths starting from the project root",
            "- Place files in appropriate directories (scripts/, docs/, designs/, etc.)",
            "- Follow the project's file organization guidelines",
            "\nAfter completing the task:",
            "- List all files you created or modified with their paths",
            "- Provide a summary of the actual implementation",
            "- Include any relevant code snippets or examples"
        ]
        
        # Add task-specific instructions
        if task_type == 'documentation':
            prompt_parts.extend([
                "\nDocumentation Requirements:",
                "- Create actual documentation files in the docs/ directory",
                "- Use proper markdown formatting",
                "- Include code examples where relevant"
            ])
        elif task_type == 'implementation':
            prompt_parts.extend([
                "\nImplementation Requirements:",
                "- Write actual code, not pseudocode",
                "- Follow the project's coding standards",
                "- Include proper error handling"
            ])
            
        enhanced_prompt = "\n".join(prompt_parts)
        
        # Execute with enhanced prompt
        return self._execute_with_prompt(enhanced_prompt)
        
    def _save_result_file(self, result: WorkerResult):
        """Save result to JSON file for backward compatibility"""
        result_file = self.task_file.with_suffix('.result.json')
        
        result_data = {
            'success': result.status == ResultStatus.SUCCESS,
            'task_id': result.task_id,
            'output': result.output,
            'error': result.error_message,
            'usage': {
                'tokens_used': result.tokens_used,
                'execution_time': result.execution_time
            },
            'files': {
                'created': result.created_files,
                'modified': result.modified_files
            },
            'validation_passed': result.validation_passed
        }
        
        with open(result_file, 'w') as f:
            json.dump(result_data, f, indent=2)
            
    def _report_error(self, error_message: str, start_time: float, task_id: str = 'unknown'):
        """Report error with detailed tracking"""
        execution_time = time.time() - start_time
        
        worker_result = WorkerResult(
            task_id=task_id,
            worker_id=self.worker_id,
            status=ResultStatus.FAILED,
            output="",
            created_files=[],
            modified_files=[],
            execution_time=execution_time,
            tokens_used=0,
            timestamp=datetime.now().isoformat(),
            error_message=error_message,
            metadata={
                'execution_log': self.execution_log,
                'traceback': traceback.format_exc()
            }
        )
        
        self.result_manager.store_result(worker_result)
        self.log(f"ERROR: {error_message}")
        
    def log(self, message: str):
        """Enhanced logging that captures to execution log"""
        self.execution_log.append(f"[{datetime.now().isoformat()}] {message}")
        super().log(message)