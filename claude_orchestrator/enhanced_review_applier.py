"""Enhanced Review Application System for Claude Orchestrator.

This module provides an enhanced system for applying code reviews with
advanced pattern matching, conflict resolution, and validation.
"""

import re
import json
import difflib
import ast
import logging
from typing import Dict, List, Optional, Tuple, Any, Set
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import shutil
import tempfile

from .review_applier import ReviewApplier
from .reviewer_agent import ReviewResult, ReviewFinding, ReviewSeverity
from .feedback_model import create_review_feedback, FeedbackSeverity
from .rollback_manager import RollbackManager, CheckpointType

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of code changes."""
    FILE_CREATE = "file_create"
    FILE_EDIT = "file_edit"
    FILE_DELETE = "file_delete"
    CODE_REPLACE = "code_replace"
    LINE_INSERT = "line_insert"
    LINE_DELETE = "line_delete"
    REFACTOR = "refactor"
    FORMAT = "format"


class ConflictResolution(Enum):
    """Strategies for resolving conflicts."""
    MANUAL = "manual"           # Require manual intervention
    PREFER_REVIEW = "prefer_review"    # Use review version
    PREFER_CURRENT = "prefer_current"  # Keep current version
    MERGE = "merge"            # Try to merge changes
    SKIP = "skip"              # Skip conflicting change


@dataclass
class CodeChange:
    """Represents a code change to apply."""
    change_id: str
    change_type: ChangeType
    file_path: str
    description: str = ""
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    line_number: Optional[int] = None
    context_lines: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    applied: bool = False
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "change_id": self.change_id,
            "change_type": self.change_type.value,
            "file_path": self.file_path,
            "description": self.description,
            "line_number": self.line_number,
            "applied": self.applied,
            "error": self.error,
            "metadata": self.metadata
        }


@dataclass
class ChangeConflict:
    """Represents a conflict when applying changes."""
    conflict_id: str
    change: CodeChange
    conflict_type: str  # e.g., "content_mismatch", "file_not_found"
    description: str
    current_content: Optional[str] = None
    expected_content: Optional[str] = None
    suggested_resolution: Optional[ConflictResolution] = None


class ChangeExtractor:
    """Extracts code changes from review text with advanced pattern matching."""
    
    def __init__(self):
        # Enhanced patterns for different change formats
        self.patterns = {
            # Standard code block with file path
            'file_block': re.compile(
                r'```(?P<lang>\w*):(?P<path>[^\n]+)\n(?P<content>.*?)```',
                re.DOTALL | re.MULTILINE
            ),
            
            # Replace/change patterns
            'replace_block': re.compile(
                r'(?:Replace|Change|Update).*?in\s+(?P<file>[^\s:]+).*?'
                r'```(?:\w+)?\n(?P<old>.*?)```.*?'
                r'(?:with|to).*?```(?:\w+)?\n(?P<new>.*?)```',
                re.DOTALL | re.IGNORECASE
            ),
            
            # Line-specific changes
            'line_change': re.compile(
                r'(?:In|At)\s+(?P<file>[^\s,]+),?\s*line\s+(?P<line>\d+).*?'
                r'(?:change|replace)\s+["\'](?P<old>[^"\']+)["\']\s+'
                r'(?:to|with)\s+["\'](?P<new>[^"\']+)["\']',
                re.IGNORECASE
            ),
            
            # Delete patterns
            'delete_pattern': re.compile(
                r'(?:Delete|Remove)\s+(?:line|lines)\s+(?P<start>\d+)'
                r'(?:\s*-\s*(?P<end>\d+))?\s+(?:in|from)\s+(?P<file>[^\s]+)',
                re.IGNORECASE
            ),
            
            # Insert patterns
            'insert_pattern': re.compile(
                r'(?:Insert|Add).*?(?:after|before)\s+line\s+(?P<line>\d+)\s+'
                r'(?:in|to)\s+(?P<file>[^\s:]+).*?```(?:\w+)?\n(?P<content>.*?)```',
                re.DOTALL | re.IGNORECASE
            ),
            
            # Refactor patterns
            'refactor_pattern': re.compile(
                r'Refactor\s+(?P<what>\w+)\s+["\'](?P<old_name>[^"\']+)["\']\s+'
                r'to\s+["\'](?P<new_name>[^"\']+)["\']\s+in\s+(?P<file>[^\s]+)',
                re.IGNORECASE
            )
        }
    
    def extract_changes(self, review_text: str, context: Dict[str, Any] = None) -> List[CodeChange]:
        """Extract all code changes from review text.
        
        Args:
            review_text: Review text containing changes
            context: Additional context (e.g., task info)
            
        Returns:
            List of code changes
        """
        changes = []
        change_counter = 0
        
        # Extract file blocks
        for match in self.patterns['file_block'].finditer(review_text):
            change_counter += 1
            
            # Determine if it's a new file or edit
            file_path = match.group('path').strip()
            content = match.group('content')
            
            # Check context before match to determine type
            before_text = review_text[:match.start()].lower()
            is_new = any(keyword in before_text[-200:] for keyword in [
                'create', 'new file', 'add file', 'create new'
            ])
            
            changes.append(CodeChange(
                change_id=f"change_{change_counter}",
                change_type=ChangeType.FILE_CREATE if is_new else ChangeType.FILE_EDIT,
                file_path=file_path,
                new_content=content,
                description=f"{'Create' if is_new else 'Edit'} file {file_path}"
            ))
        
        # Extract replace blocks
        for match in self.patterns['replace_block'].finditer(review_text):
            change_counter += 1
            changes.append(CodeChange(
                change_id=f"change_{change_counter}",
                change_type=ChangeType.CODE_REPLACE,
                file_path=match.group('file'),
                old_content=match.group('old').strip(),
                new_content=match.group('new').strip(),
                description="Replace code block"
            ))
        
        # Extract line changes
        for match in self.patterns['line_change'].finditer(review_text):
            change_counter += 1
            changes.append(CodeChange(
                change_id=f"change_{change_counter}",
                change_type=ChangeType.CODE_REPLACE,
                file_path=match.group('file'),
                old_content=match.group('old'),
                new_content=match.group('new'),
                line_number=int(match.group('line')),
                description=f"Change line {match.group('line')}"
            ))
        
        # Extract deletions
        for match in self.patterns['delete_pattern'].finditer(review_text):
            change_counter += 1
            start_line = int(match.group('start'))
            end_line = int(match.group('end')) if match.group('end') else start_line
            
            changes.append(CodeChange(
                change_id=f"change_{change_counter}",
                change_type=ChangeType.LINE_DELETE,
                file_path=match.group('file'),
                line_number=start_line,
                metadata={'end_line': end_line},
                description=f"Delete lines {start_line}-{end_line}"
            ))
        
        # Extract insertions
        for match in self.patterns['insert_pattern'].finditer(review_text):
            change_counter += 1
            changes.append(CodeChange(
                change_id=f"change_{change_counter}",
                change_type=ChangeType.LINE_INSERT,
                file_path=match.group('file'),
                new_content=match.group('content').strip(),
                line_number=int(match.group('line')),
                description=f"Insert after line {match.group('line')}"
            ))
        
        # Extract refactorings
        for match in self.patterns['refactor_pattern'].finditer(review_text):
            change_counter += 1
            changes.append(CodeChange(
                change_id=f"change_{change_counter}",
                change_type=ChangeType.REFACTOR,
                file_path=match.group('file'),
                old_content=match.group('old_name'),
                new_content=match.group('new_name'),
                metadata={'refactor_type': match.group('what')},
                description=f"Refactor {match.group('what')} from {match.group('old_name')} to {match.group('new_name')}"
            ))
        
        return changes


class ChangeValidator:
    """Validates changes before applying them."""
    
    def __init__(self, working_dir: Path):
        self.working_dir = Path(working_dir)
    
    def validate_change(self, change: CodeChange) -> Tuple[bool, Optional[str]]:
        """Validate a single change.
        
        Args:
            change: Change to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        file_path = self.working_dir / change.file_path
        
        # Check file existence for edits
        if change.change_type in [ChangeType.FILE_EDIT, ChangeType.CODE_REPLACE, 
                                  ChangeType.LINE_DELETE, ChangeType.LINE_INSERT]:
            if not file_path.exists():
                return False, f"File not found: {change.file_path}"
        
        # Check file doesn't exist for creates
        if change.change_type == ChangeType.FILE_CREATE:
            if file_path.exists():
                return False, f"File already exists: {change.file_path}"
        
        # Validate Python syntax for Python files
        if change.file_path.endswith('.py') and change.new_content:
            try:
                ast.parse(change.new_content)
            except SyntaxError as e:
                return False, f"Python syntax error: {e}"
        
        # Check for dangerous patterns
        if change.new_content:
            dangerous_patterns = [
                r'rm\s+-rf\s+/',
                r'exec\s*\(',
                r'eval\s*\(',
                r'__import__\s*\(',
                r'subprocess\.call\s*\(\s*["\']rm',
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, change.new_content):
                    return False, f"Dangerous pattern detected: {pattern}"
        
        return True, None
    
    def check_conflicts(self, changes: List[CodeChange]) -> List[ChangeConflict]:
        """Check for conflicts between changes.
        
        Args:
            changes: List of changes to check
            
        Returns:
            List of conflicts found
        """
        conflicts = []
        
        # Group changes by file
        file_changes = {}
        for change in changes:
            if change.file_path not in file_changes:
                file_changes[change.file_path] = []
            file_changes[change.file_path].append(change)
        
        # Check for conflicts within each file
        for file_path, file_change_list in file_changes.items():
            if len(file_change_list) > 1:
                # Check for overlapping line changes
                for i, change1 in enumerate(file_change_list):
                    for change2 in file_change_list[i+1:]:
                        conflict = self._check_change_conflict(change1, change2)
                        if conflict:
                            conflicts.append(conflict)
        
        return conflicts
    
    def _check_change_conflict(self, change1: CodeChange, change2: CodeChange) -> Optional[ChangeConflict]:
        """Check if two changes conflict.
        
        Args:
            change1: First change
            change2: Second change
            
        Returns:
            Conflict if found, None otherwise
        """
        # File create/edit conflicts
        if (change1.change_type == ChangeType.FILE_CREATE and 
            change2.change_type == ChangeType.FILE_EDIT):
            return ChangeConflict(
                conflict_id=f"conflict_{change1.change_id}_{change2.change_id}",
                change=change2,
                conflict_type="file_not_exists",
                description="Cannot edit file that's being created",
                suggested_resolution=ConflictResolution.MERGE
            )
        
        # Overlapping line changes
        if (change1.line_number and change2.line_number and
            change1.change_type in [ChangeType.CODE_REPLACE, ChangeType.LINE_DELETE] and
            change2.change_type in [ChangeType.CODE_REPLACE, ChangeType.LINE_DELETE]):
            
            # Check if line ranges overlap
            range1 = (change1.line_number, 
                     change1.metadata.get('end_line', change1.line_number))
            range2 = (change2.line_number,
                     change2.metadata.get('end_line', change2.line_number))
            
            if (range1[0] <= range2[1] and range2[0] <= range1[1]):
                return ChangeConflict(
                    conflict_id=f"conflict_{change1.change_id}_{change2.change_id}",
                    change=change2,
                    conflict_type="overlapping_changes",
                    description=f"Changes overlap at lines {range1} and {range2}",
                    suggested_resolution=ConflictResolution.MANUAL
                )
        
        return None


class EnhancedReviewApplier:
    """Enhanced review applier with advanced features."""
    
    def __init__(self, 
                 working_dir: str = ".",
                 rollback_manager: Optional[RollbackManager] = None,
                 conflict_resolution: ConflictResolution = ConflictResolution.MANUAL):
        self.working_dir = Path(working_dir)
        self.rollback_manager = rollback_manager
        self.conflict_resolution = conflict_resolution
        self.extractor = ChangeExtractor()
        self.validator = ChangeValidator(self.working_dir)
        self.base_applier = ReviewApplier(working_dir)
        
        # Track application history
        self.application_history: List[Dict[str, Any]] = []
        
    def apply_review_advanced(self, 
                            review_text: str,
                            review_result: Optional[ReviewResult] = None,
                            task_context: Optional[Dict[str, Any]] = None,
                            dry_run: bool = False) -> Dict[str, Any]:
        """Apply review with advanced features.
        
        Args:
            review_text: Review text containing changes
            review_result: Structured review result if available
            task_context: Task context
            dry_run: If True, don't actually apply changes
            
        Returns:
            Application result
        """
        result = {
            'success': False,
            'changes_extracted': 0,
            'changes_applied': 0,
            'changes_failed': 0,
            'conflicts': [],
            'validation_errors': [],
            'files_modified': [],
            'rollback_checkpoint': None,
            'details': []
        }
        
        try:
            # Create rollback checkpoint if available
            if self.rollback_manager and not dry_run:
                checkpoint_id = self.rollback_manager.create_checkpoint(
                    checkpoint_type=CheckpointType.MANUAL,
                    description="Before applying review changes"
                )
                result['rollback_checkpoint'] = checkpoint_id
            
            # Extract changes
            changes = self.extractor.extract_changes(review_text, task_context)
            result['changes_extracted'] = len(changes)
            
            if not changes:
                logger.info("No code changes found in review")
                result['success'] = True
                return result
            
            # Validate all changes
            for change in changes:
                is_valid, error = self.validator.validate_change(change)
                if not is_valid:
                    result['validation_errors'].append({
                        'change_id': change.change_id,
                        'error': error
                    })
                    change.error = error
            
            # Check for conflicts
            conflicts = self.validator.check_conflicts(changes)
            result['conflicts'] = [
                {
                    'conflict_id': c.conflict_id,
                    'description': c.description,
                    'resolution': c.suggested_resolution.value if c.suggested_resolution else None
                }
                for c in conflicts
            ]
            
            # Resolve conflicts if possible
            if conflicts and self.conflict_resolution != ConflictResolution.MANUAL:
                changes = self._resolve_conflicts(changes, conflicts)
            
            # Apply changes
            if not dry_run:
                for change in changes:
                    if change.error:
                        result['changes_failed'] += 1
                        continue
                    
                    try:
                        self._apply_single_change(change)
                        change.applied = True
                        result['changes_applied'] += 1
                        
                        if change.file_path not in result['files_modified']:
                            result['files_modified'].append(change.file_path)
                        
                        result['details'].append({
                            'change_id': change.change_id,
                            'status': 'applied',
                            'description': change.description
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to apply change {change.change_id}: {e}")
                        change.error = str(e)
                        result['changes_failed'] += 1
                        result['details'].append({
                            'change_id': change.change_id,
                            'status': 'failed',
                            'error': str(e)
                        })
            
            # Record in history
            self.application_history.append({
                'timestamp': datetime.now().isoformat(),
                'review_length': len(review_text),
                'changes_applied': result['changes_applied'],
                'changes_failed': result['changes_failed'],
                'dry_run': dry_run
            })
            
            result['success'] = result['changes_failed'] == 0
            
        except Exception as e:
            logger.error(f"Error applying review: {e}")
            result['error'] = str(e)
            
            # Rollback if needed
            if (self.rollback_manager and 
                result['rollback_checkpoint'] and 
                result['changes_applied'] > 0):
                try:
                    self.rollback_manager.rollback_to_checkpoint(result['rollback_checkpoint'])
                    result['rollback_performed'] = True
                except Exception as rollback_error:
                    logger.error(f"Rollback failed: {rollback_error}")
        
        return result
    
    def _apply_single_change(self, change: CodeChange):
        """Apply a single code change.
        
        Args:
            change: Change to apply
        """
        file_path = self.working_dir / change.file_path
        
        if change.change_type == ChangeType.FILE_CREATE:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(change.new_content)
            
        elif change.change_type == ChangeType.FILE_EDIT:
            file_path.write_text(change.new_content)
            
        elif change.change_type == ChangeType.FILE_DELETE:
            if file_path.exists():
                file_path.unlink()
            
        elif change.change_type == ChangeType.CODE_REPLACE:
            content = file_path.read_text()
            
            if change.line_number:
                # Line-specific replacement
                lines = content.splitlines()
                if 0 <= change.line_number - 1 < len(lines):
                    lines[change.line_number - 1] = lines[change.line_number - 1].replace(
                        change.old_content, change.new_content
                    )
                    file_path.write_text('\n'.join(lines))
                else:
                    raise ValueError(f"Line {change.line_number} out of range")
            else:
                # General replacement
                if change.old_content in content:
                    new_content = content.replace(change.old_content, change.new_content, 1)
                    file_path.write_text(new_content)
                else:
                    # Try fuzzy matching
                    new_content = self._fuzzy_replace(content, change.old_content, change.new_content)
                    if new_content != content:
                        file_path.write_text(new_content)
                    else:
                        raise ValueError("Could not find content to replace")
        
        elif change.change_type == ChangeType.LINE_INSERT:
            lines = file_path.read_text().splitlines()
            insert_pos = change.line_number
            if 0 <= insert_pos <= len(lines):
                lines.insert(insert_pos, change.new_content)
                file_path.write_text('\n'.join(lines))
            else:
                raise ValueError(f"Insert position {insert_pos} out of range")
        
        elif change.change_type == ChangeType.LINE_DELETE:
            lines = file_path.read_text().splitlines()
            start = change.line_number - 1
            end = change.metadata.get('end_line', change.line_number) - 1
            
            if 0 <= start <= end < len(lines):
                del lines[start:end+1]
                file_path.write_text('\n'.join(lines))
            else:
                raise ValueError(f"Line range {start+1}-{end+1} out of range")
        
        elif change.change_type == ChangeType.REFACTOR:
            content = file_path.read_text()
            refactor_type = change.metadata.get('refactor_type', 'name')
            
            if refactor_type in ['function', 'class', 'variable']:
                # Use word boundaries for safer replacement
                pattern = r'\b' + re.escape(change.old_content) + r'\b'
                new_content = re.sub(pattern, change.new_content, content)
                file_path.write_text(new_content)
            else:
                # Simple replacement
                new_content = content.replace(change.old_content, change.new_content)
                file_path.write_text(new_content)
    
    def _fuzzy_replace(self, content: str, old_text: str, new_text: str) -> str:
        """Perform fuzzy text replacement.
        
        Args:
            content: Original content
            old_text: Text to find (fuzzy)
            new_text: Replacement text
            
        Returns:
            Modified content
        """
        # Normalize whitespace
        old_normalized = ' '.join(old_text.split())
        
        # Try line-by-line fuzzy matching
        lines = content.splitlines()
        best_match_ratio = 0
        best_match_idx = -1
        
        for i, line in enumerate(lines):
            line_normalized = ' '.join(line.split())
            ratio = difflib.SequenceMatcher(None, old_normalized, line_normalized).ratio()
            
            if ratio > best_match_ratio and ratio > 0.8:  # 80% similarity threshold
                best_match_ratio = ratio
                best_match_idx = i
        
        if best_match_idx >= 0:
            # Replace the best matching line
            lines[best_match_idx] = new_text
            return '\n'.join(lines)
        
        return content
    
    def _resolve_conflicts(self, 
                          changes: List[CodeChange],
                          conflicts: List[ChangeConflict]) -> List[CodeChange]:
        """Resolve conflicts based on resolution strategy.
        
        Args:
            changes: List of changes
            conflicts: List of conflicts
            
        Returns:
            Filtered list of changes
        """
        conflicted_change_ids = set()
        
        for conflict in conflicts:
            if self.conflict_resolution == ConflictResolution.SKIP:
                conflicted_change_ids.add(conflict.change.change_id)
            elif self.conflict_resolution == ConflictResolution.PREFER_REVIEW:
                # Keep the review change, mark it as needing careful application
                conflict.change.metadata['has_conflict'] = True
            elif self.conflict_resolution == ConflictResolution.PREFER_CURRENT:
                conflicted_change_ids.add(conflict.change.change_id)
        
        # Filter out skipped changes
        return [c for c in changes if c.change_id not in conflicted_change_ids]
    
    def generate_review_report(self, 
                             review_text: str,
                             application_result: Dict[str, Any]) -> str:
        """Generate a report of the review application.
        
        Args:
            review_text: Original review text
            application_result: Result from apply_review_advanced
            
        Returns:
            Formatted report
        """
        lines = []
        lines.append("=" * 60)
        lines.append("REVIEW APPLICATION REPORT")
        lines.append("=" * 60)
        lines.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        lines.append("SUMMARY")
        lines.append("-" * 30)
        lines.append(f"Changes extracted: {application_result['changes_extracted']}")
        lines.append(f"Changes applied: {application_result['changes_applied']}")
        lines.append(f"Changes failed: {application_result['changes_failed']}")
        lines.append(f"Validation errors: {len(application_result['validation_errors'])}")
        lines.append(f"Conflicts found: {len(application_result['conflicts'])}")
        lines.append("")
        
        if application_result['files_modified']:
            lines.append("FILES MODIFIED")
            lines.append("-" * 30)
            for file_path in application_result['files_modified']:
                lines.append(f"  - {file_path}")
            lines.append("")
        
        if application_result['validation_errors']:
            lines.append("VALIDATION ERRORS")
            lines.append("-" * 30)
            for error in application_result['validation_errors']:
                lines.append(f"  - Change {error['change_id']}: {error['error']}")
            lines.append("")
        
        if application_result['conflicts']:
            lines.append("CONFLICTS")
            lines.append("-" * 30)
            for conflict in application_result['conflicts']:
                lines.append(f"  - {conflict['description']}")
                if conflict['resolution']:
                    lines.append(f"    Suggested resolution: {conflict['resolution']}")
            lines.append("")
        
        if application_result.get('rollback_checkpoint'):
            lines.append("ROLLBACK INFORMATION")
            lines.append("-" * 30)
            lines.append(f"Checkpoint created: {application_result['rollback_checkpoint']}")
            if application_result.get('rollback_performed'):
                lines.append("Rollback was performed due to errors")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Enhanced integration
class EnhancedReviewApplierIntegration:
    """Enhanced integration with orchestrator."""
    
    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.base_applier = ReviewApplier(working_dir)
        self.enhanced_applier = None
    
    def process_review_and_apply(self, review_result: Dict, task: Dict) -> Dict:
        """Process review and apply changes with enhanced features.
        
        Args:
            review_result: Review result
            task: Task information
            
        Returns:
            Application result
        """
        # Initialize enhanced applier if needed
        if not self.enhanced_applier:
            rollback_manager = None
            if hasattr(self, 'orchestrator') and hasattr(self.orchestrator, 'rollback_manager'):
                rollback_manager = self.orchestrator.rollback_manager
            
            self.enhanced_applier = EnhancedReviewApplier(
                working_dir=self.working_dir,
                rollback_manager=rollback_manager,
                conflict_resolution=ConflictResolution.PREFER_REVIEW
            )
        
        # Extract review text
        review_text = review_result.get('review', '')
        
        # Apply with enhanced features
        result = self.enhanced_applier.apply_review_advanced(
            review_text=review_text,
            task_context=task,
            dry_run=False
        )
        
        # Generate report
        if result['changes_extracted'] > 0:
            report = self.enhanced_applier.generate_review_report(review_text, result)
            logger.info(f"Review application report:\n{report}")
        
        # Format response
        return {
            'applied': result['success'],
            'changes': result['details'],
            'errors': result['validation_errors'],
            'needs_re_review': result['changes_applied'] > 0,
            'report': result
        }


def integrate_enhanced_review_applier(orchestrator) -> EnhancedReviewApplierIntegration:
    """Integrate enhanced review applier with orchestrator.
    
    Args:
        orchestrator: Orchestrator instance
        
    Returns:
        Enhanced review applier integration
    """
    integration = EnhancedReviewApplierIntegration(orchestrator.working_dir)
    integration.orchestrator = orchestrator
    
    # Replace the basic review integration
    orchestrator.enhanced_review_integration = integration
    
    logger.info("Enhanced review applier integrated with orchestrator")
    
    return integration