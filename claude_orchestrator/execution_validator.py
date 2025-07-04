"""
Task Execution Validator - Ensures workers actually execute tasks
"""

import os
import re
import logging
from typing import Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ExecutionValidator:
    """Validates that tasks were actually executed, not just analyzed"""
    
    def __init__(self):
        self.validation_patterns = {
            'implementation': [
                r'created?.+file',
                r'implemented',
                r'added.+class',
                r'added.+function',
                r'import',
                r'def ',
                r'class '
            ],
            'avoidance_patterns': [
                r'would\s+create',
                r'would\s+implement', 
                r'would\s+add',
                r'should\s+create',
                r'could\s+implement',
                r'plan\s+to',
                r'suggest\s+creating'
            ]
        }
    
    def validate_execution(self, task_output: str, task_type: str = 'implementation') -> Dict:
        """Validate that a task was actually executed"""
        result = {
            'executed': False,
            'confidence': 0.0,
            'issues': [],
            'files_created': []
        }
        
        # Check for avoidance patterns
        avoidance_count = 0
        for pattern in self.validation_patterns['avoidance_patterns']:
            if re.search(pattern, task_output, re.IGNORECASE):
                avoidance_count += 1
                result['issues'].append(f"Found avoidance pattern: {pattern}")
        
        # Check for implementation patterns
        implementation_count = 0
        for pattern in self.validation_patterns['implementation']:
            if re.search(pattern, task_output, re.IGNORECASE):
                implementation_count += 1
        
        # Extract file paths that were supposedly created
        file_patterns = [
            r'(?:created?|wrote|generated?)\s+(?:file\s+)?['"`]?([\w\/.\-_]+\.\w+)['"`]?',
            r'(?:File|Created?):\s*([\w\/.\-_]+\.\w+)'
        ]
        
        for pattern in file_patterns:
            matches = re.findall(pattern, task_output, re.IGNORECASE)
            result['files_created'].extend(matches)
        
        # Calculate confidence
        if avoidance_count > 0:
            result['confidence'] = 0.2
        elif implementation_count > 3:
            result['confidence'] = 0.9
            result['executed'] = True
        elif implementation_count > 0:
            result['confidence'] = 0.6
            result['executed'] = implementation_count > avoidance_count
        
        # Verify files actually exist
        verified_files = []
        for file_path in result['files_created']:
            if Path(file_path).exists():
                verified_files.append(file_path)
            else:
                result['issues'].append(f"File not found: {file_path}")
        
        result['files_created'] = verified_files
        
        # Final check
        if not verified_files and result['executed']:
            result['executed'] = False
            result['confidence'] = 0.3
            result['issues'].append("No actual files were created")
        
        return result
    
    def generate_execution_report(self, task_results: List[Dict]) -> str:
        """Generate a report on task execution"""
        total = len(task_results)
        executed = sum(1 for r in task_results if r.get('validation', {}).get('executed', False))
        
        report = f"""
Task Execution Report
====================
Total Tasks: {total}
Actually Executed: {executed} ({executed/total*100:.1f}%)
Only Analyzed: {total - executed} ({(total-executed)/total*100:.1f}%)

Issues Found:
"""
        
        # Collect all issues
        all_issues = {}
        for result in task_results:
            validation = result.get('validation', {})
            for issue in validation.get('issues', []):
                all_issues[issue] = all_issues.get(issue, 0) + 1
        
        for issue, count in sorted(all_issues.items(), key=lambda x: x[1], reverse=True):
            report += f"- {issue}: {count} occurrences\n"
        
        return report
