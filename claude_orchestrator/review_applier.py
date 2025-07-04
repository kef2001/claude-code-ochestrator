"""
Review Applier - Applies Opus review feedback to code
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class ReviewApplier:
    """Applies code review feedback to actual files"""
    
    def __init__(self, working_dir: str = "."):
        self.working_dir = Path(working_dir)
        
    def apply_review(self, review_text: str, task_context: Dict) -> Dict:
        """Apply review feedback to code files"""
        result = {
            'success': False,
            'changes_applied': [],
            'errors': [],
            'files_modified': []
        }
        
        try:
            # Extract code blocks from review
            code_changes = self._extract_code_changes(review_text)
            
            if not code_changes:
                logger.info("No code changes found in review")
                result['success'] = True
                return result
            
            # Apply each change
            for change in code_changes:
                try:
                    if change['type'] == 'file_edit':
                        self._apply_file_edit(change)
                        result['changes_applied'].append(change)
                        result['files_modified'].append(change['file_path'])
                    elif change['type'] == 'file_create':
                        self._apply_file_create(change)
                        result['changes_applied'].append(change)
                        result['files_modified'].append(change['file_path'])
                    elif change['type'] == 'code_replace':
                        self._apply_code_replace(change)
                        result['changes_applied'].append(change)
                        result['files_modified'].append(change['file_path'])
                except Exception as e:
                    logger.error(f"Failed to apply change: {e}")
                    result['errors'].append(str(e))
            
            result['success'] = len(result['errors']) == 0
            result['files_modified'] = list(set(result['files_modified']))
            
        except Exception as e:
            logger.error(f"Error applying review: {e}")
            result['errors'].append(str(e))
        
        return result
    
    def _extract_code_changes(self, review_text: str) -> List[Dict]:
        """Extract code changes from review text"""
        changes = []
        
        # Pattern 1: File creation/replacement blocks
        # ```python:path/to/file.py
        # code content
        # ```
        file_pattern = r'```(?:python|py|javascript|js|typescript|ts)?:([^\n]+)\n(.*?)```'
        for match in re.finditer(file_pattern, review_text, re.DOTALL):
            file_path = match.group(1).strip()
            code_content = match.group(2)
            changes.append({
                'type': 'file_create' if 'new file' in review_text[:match.start()].lower() else 'file_edit',
                'file_path': file_path,
                'content': code_content
            })
        
        # Pattern 2: Code replacement suggestions
        # "Replace this code:" followed by old code and new code blocks
        replace_pattern = r'(?:Replace|Change|Update).*?:\s*```.*?\n(.*?)```.*?(?:with|to):\s*```.*?\n(.*?)```'
        for match in re.finditer(replace_pattern, review_text, re.DOTALL | re.IGNORECASE):
            old_code = match.group(1).strip()
            new_code = match.group(2).strip()
            
            # Try to find file context
            file_context = self._find_file_context(review_text, match.start())
            if file_context:
                changes.append({
                    'type': 'code_replace',
                    'file_path': file_context,
                    'old_code': old_code,
                    'new_code': new_code
                })
        
        # Pattern 3: Direct edit instructions
        # "In file.py, change X to Y"
        edit_pattern = r'In\s+([^\s,]+\.(?:py|js|ts|jsx|tsx)),?\s+(?:change|replace|update)\s+"([^"]+)"\s+(?:to|with)\s+"([^"]+)"'
        for match in re.finditer(edit_pattern, review_text, re.IGNORECASE):
            changes.append({
                'type': 'code_replace',
                'file_path': match.group(1),
                'old_code': match.group(2),
                'new_code': match.group(3)
            })
        
        return changes
    
    def _find_file_context(self, text: str, position: int) -> Optional[str]:
        """Find the file path mentioned near a position in text"""
        # Look backwards for file mentions
        context = text[max(0, position-500):position]
        file_pattern = r'([^\s]+\.(?:py|js|ts|jsx|tsx))'
        matches = list(re.finditer(file_pattern, context))
        if matches:
            return matches[-1].group(1)
        return None
    
    def _apply_file_edit(self, change: Dict):
        """Apply edits to an existing file"""
        file_path = self.working_dir / change['file_path']
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the new content
        file_path.write_text(change['content'])
        logger.info(f"Updated file: {change['file_path']}")
    
    def _apply_file_create(self, change: Dict):
        """Create a new file with content"""
        file_path = self.working_dir / change['file_path']
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the content
        file_path.write_text(change['content'])
        logger.info(f"Created file: {change['file_path']}")
    
    def _apply_code_replace(self, change: Dict):
        """Replace specific code in a file"""
        file_path = self.working_dir / change['file_path']
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {change['file_path']}")
        
        content = file_path.read_text()
        
        # Try exact match first
        if change['old_code'] in content:
            new_content = content.replace(change['old_code'], change['new_code'], 1)
            file_path.write_text(new_content)
            logger.info(f"Replaced code in: {change['file_path']}")
        else:
            # Try normalized match (removing extra whitespace)
            old_normalized = ' '.join(change['old_code'].split())
            new_normalized = ' '.join(change['new_code'].split())
            content_lines = content.splitlines()
            
            found = False
            for i, line in enumerate(content_lines):
                line_normalized = ' '.join(line.split())
                if old_normalized in line_normalized:
                    content_lines[i] = line.replace(line.strip(), change['new_code'].strip())
                    found = True
                    break
            
            if found:
                file_path.write_text('\n'.join(content_lines))
                logger.info(f"Replaced code in: {change['file_path']} (normalized match)")
            else:
                raise ValueError(f"Could not find code to replace in {change['file_path']}")


class ReviewApplierIntegration:
    """Integration with the orchestrator's review workflow"""
    
    def __init__(self, review_applier: ReviewApplier):
        self.review_applier = review_applier
        
    def process_review_and_apply(self, review_result: Dict, task: Dict) -> Dict:
        """Process review results and apply changes"""
        result = {
            'applied': False,
            'changes': [],
            'errors': [],
            'needs_re_review': False
        }
        
        try:
            # Extract review text
            review_text = review_result.get('review', '')
            
            # Apply the review
            apply_result = self.review_applier.apply_review(review_text, task)
            
            result['applied'] = apply_result['success']
            result['changes'] = apply_result['changes_applied']
            result['errors'] = apply_result['errors']
            
            # If changes were applied, we might need another review
            if apply_result['changes_applied']:
                result['needs_re_review'] = True
                logger.info(f"Applied {len(apply_result['changes_applied'])} changes from review")
            
        except Exception as e:
            logger.error(f"Error in review application: {e}")
            result['errors'].append(str(e))
        
        return result