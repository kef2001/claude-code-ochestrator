"""Claude Session Worker - Executes tasks using the current Claude session"""
import json
import logging
import sys
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ClaudeSessionWorker:
    """Worker that executes tasks in the current Claude session"""
    
    def __init__(self, task_file: str):
        self.task_file = Path(task_file)
        self.result_file = self.task_file.with_suffix('.result.json')
        
    def run(self):
        """Load task, execute it, and save results"""
        try:
            # Load task
            with open(self.task_file, 'r') as f:
                task_data = json.load(f)
            
            # Execute task
            result = self.execute_task(task_data)
            
            # Save result
            with open(self.result_file, 'w') as f:
                json.dump(result, f, indent=2)
                
        except Exception as e:
            logger.error(f"Worker error: {str(e)}")
            error_result = {
                'success': False,
                'error': str(e),
                'task_id': task_data.get('task_id', 'unknown') if 'task_data' in locals() else 'unknown'
            }
            with open(self.result_file, 'w') as f:
                json.dump(error_result, f, indent=2)
    
    def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task and return results"""
        task_id = task_data.get('task_id', 'unknown')
        title = task_data.get('title', 'Untitled Task')
        description = task_data.get('description', '')
        details = task_data.get('details', '')
        
        print(f"\n{'='*60}")
        print(f"Executing Task {task_id}: {title}")
        print(f"{'='*60}")
        print(f"\nDescription: {description}")
        if details:
            print(f"Details: {details}")
        print(f"\n{'='*60}\n")
        
        # Execute the task using Claude API
        try:
            # Build the prompt for Claude
            prompt = self._build_task_prompt(task_id, task_description, task_details)
            
            # Execute via Claude API
            result = self._execute_with_claude(prompt, task_id)
            
            # Ensure we have a proper result
            if not result:
                result = {
                    'success': False,
                    'task_id': task_id,
                    'output': "Failed to execute task - no response from Claude",
                    'usage': {'tokens_used': 0}
                }
        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}")
            result = {
                'success': False,
                'task_id': task_id,
                'output': f"Error: {str(e)}",
                'usage': {'tokens_used': 0}
            }
        
        return result


def main():
    """Main entry point for the worker script"""
    if len(sys.argv) != 2:
        print("Usage: python -m claude_orchestrator.claude_session_worker <task_file>")
        sys.exit(1)
    
    task_file = sys.argv[1]
    worker = ClaudeSessionWorker(task_file)
    worker.run()


if __name__ == "__main__":
    main()