"""ReviewerAgent for automated output analysis and quality assurance.

This module provides specialized agents for reviewing and analyzing
task outputs, code quality, and implementation correctness.
"""

import logging
import re
import json
import ast
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import difflib

from .specialized_agents import (
    SpecializedAgent, AgentCapability, AgentProfile, AgentRole
)
from .task_master import Task as TMTask
from .feedback_model import (
    FeedbackModel, FeedbackType, FeedbackSeverity,
    create_review_feedback, create_warning_feedback
)

logger = logging.getLogger(__name__)


class ReviewType(Enum):
    """Types of reviews that can be performed."""
    CODE_QUALITY = "code_quality"
    CORRECTNESS = "correctness"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    ARCHITECTURE = "architecture"
    COMPLIANCE = "compliance"


class ReviewSeverity(Enum):
    """Severity levels for review findings."""
    CRITICAL = "critical"    # Must fix
    HIGH = "high"           # Should fix
    MEDIUM = "medium"       # Consider fixing
    LOW = "low"            # Nice to have
    INFO = "info"          # Informational


@dataclass
class ReviewFinding:
    """Individual finding from a review."""
    finding_id: str
    review_type: ReviewType
    severity: ReviewSeverity
    title: str
    description: str
    location: Optional[str] = None  # File path or line number
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class ReviewResult:
    """Complete review result for a task."""
    task_id: str
    reviewer_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    overall_score: float = 0.0  # 0.0-1.0
    passed: bool = False
    findings: List[ReviewFinding] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    follow_up_required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "task_id": self.task_id,
            "reviewer_id": self.reviewer_id,
            "timestamp": self.timestamp.isoformat(),
            "overall_score": self.overall_score,
            "passed": self.passed,
            "findings": [
                {
                    "id": f.finding_id,
                    "type": f.review_type.value,
                    "severity": f.severity.value,
                    "title": f.title,
                    "description": f.description,
                    "location": f.location,
                    "suggestion": f.suggestion,
                    "tags": f.tags
                }
                for f in self.findings
            ],
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "follow_up_required": self.follow_up_required
        }


class CodeAnalyzer:
    """Analyzes code for quality and issues."""
    
    def __init__(self):
        # Common code issues patterns
        self.issue_patterns = {
            # Security issues
            "hardcoded_secret": r'(password|secret|key|token)\s*=\s*["\'][^"\']+["\']',
            "sql_injection": r'(query|execute)\s*\([^)]*\+[^)]*\)',
            "eval_usage": r'\beval\s*\(',
            "exec_usage": r'\bexec\s*\(',
            
            # Code quality issues
            "long_line": r'^.{121,}$',  # Lines over 120 chars
            "todo_comment": r'#\s*(TODO|FIXME|HACK|XXX)',
            "print_statement": r'\bprint\s*\(',
            "bare_except": r'except\s*:',
            "unused_import": r'^import\s+\w+\s*$',
            
            # Python specific
            "mutable_default": r'def\s+\w+\([^)]*=\s*(\[\]|\{\})',
            "global_usage": r'\bglobal\s+',
            "type_comparison": r'type\([^)]+\)\s*==',
        }
        
        # Complexity thresholds
        self.complexity_thresholds = {
            "max_function_length": 50,
            "max_complexity": 10,
            "max_nesting": 4,
            "max_parameters": 6
        }
    
    def analyze_code(self, code: str, language: str = "python") -> List[ReviewFinding]:
        """Analyze code and return findings.
        
        Args:
            code: Code to analyze
            language: Programming language
            
        Returns:
            List of review findings
        """
        findings = []
        
        if language == "python":
            findings.extend(self._analyze_python(code))
        elif language == "javascript":
            findings.extend(self._analyze_javascript(code))
        
        # General pattern matching
        findings.extend(self._analyze_patterns(code))
        
        return findings
    
    def _analyze_python(self, code: str) -> List[ReviewFinding]:
        """Analyze Python code specifically."""
        findings = []
        
        try:
            # Parse AST
            tree = ast.parse(code)
            
            # Check for various issues
            for node in ast.walk(tree):
                # Long functions
                if isinstance(node, ast.FunctionDef):
                    func_lines = node.end_lineno - node.lineno
                    if func_lines > self.complexity_thresholds["max_function_length"]:
                        findings.append(ReviewFinding(
                            finding_id=f"long_func_{node.name}",
                            review_type=ReviewType.CODE_QUALITY,
                            severity=ReviewSeverity.MEDIUM,
                            title=f"Long function: {node.name}",
                            description=f"Function has {func_lines} lines, exceeds threshold of {self.complexity_thresholds['max_function_length']}",
                            location=f"Line {node.lineno}",
                            suggestion="Consider breaking this function into smaller, more focused functions"
                        ))
                    
                    # Too many parameters
                    param_count = len(node.args.args)
                    if param_count > self.complexity_thresholds["max_parameters"]:
                        findings.append(ReviewFinding(
                            finding_id=f"many_params_{node.name}",
                            review_type=ReviewType.CODE_QUALITY,
                            severity=ReviewSeverity.LOW,
                            title=f"Too many parameters: {node.name}",
                            description=f"Function has {param_count} parameters, exceeds threshold of {self.complexity_thresholds['max_parameters']}",
                            location=f"Line {node.lineno}",
                            suggestion="Consider using a configuration object or reducing parameters"
                        ))
                
                # Check for pass statements (incomplete implementation)
                if isinstance(node, ast.Pass):
                    findings.append(ReviewFinding(
                        finding_id=f"pass_stmt_{node.lineno}",
                        review_type=ReviewType.CORRECTNESS,
                        severity=ReviewSeverity.HIGH,
                        title="Incomplete implementation",
                        description="Found 'pass' statement indicating incomplete implementation",
                        location=f"Line {node.lineno}",
                        suggestion="Implement the missing functionality"
                    ))
                
        except SyntaxError as e:
            findings.append(ReviewFinding(
                finding_id="syntax_error",
                review_type=ReviewType.CORRECTNESS,
                severity=ReviewSeverity.CRITICAL,
                title="Syntax Error",
                description=str(e),
                location=f"Line {e.lineno}" if hasattr(e, 'lineno') else None,
                suggestion="Fix the syntax error before proceeding"
            ))
        
        return findings
    
    def _analyze_javascript(self, code: str) -> List[ReviewFinding]:
        """Analyze JavaScript code specifically."""
        findings = []
        
        # Basic JavaScript checks
        js_patterns = {
            "var_usage": r'\bvar\s+',
            "console_log": r'console\.\w+\(',
            "debugger": r'\bdebugger\b',
            "alert": r'\balert\s*\(',
        }
        
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            for pattern_name, pattern in js_patterns.items():
                if re.search(pattern, line):
                    if pattern_name == "var_usage":
                        findings.append(ReviewFinding(
                            finding_id=f"var_usage_{i}",
                            review_type=ReviewType.CODE_QUALITY,
                            severity=ReviewSeverity.LOW,
                            title="Use of 'var' keyword",
                            description="Consider using 'let' or 'const' instead of 'var'",
                            location=f"Line {i}",
                            suggestion="Replace 'var' with 'let' or 'const'"
                        ))
                    elif pattern_name == "console_log":
                        findings.append(ReviewFinding(
                            finding_id=f"console_{i}",
                            review_type=ReviewType.CODE_QUALITY,
                            severity=ReviewSeverity.LOW,
                            title="Console statement found",
                            description="Remove console statements from production code",
                            location=f"Line {i}"
                        ))
        
        return findings
    
    def _analyze_patterns(self, code: str) -> List[ReviewFinding]:
        """Analyze code using regex patterns."""
        findings = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            for issue_name, pattern in self.issue_patterns.items():
                if re.search(pattern, line, re.IGNORECASE):
                    severity = ReviewSeverity.HIGH if issue_name in [
                        "hardcoded_secret", "sql_injection", "eval_usage"
                    ] else ReviewSeverity.MEDIUM
                    
                    findings.append(ReviewFinding(
                        finding_id=f"{issue_name}_{i}",
                        review_type=ReviewType.SECURITY if "secret" in issue_name or "injection" in issue_name else ReviewType.CODE_QUALITY,
                        severity=severity,
                        title=issue_name.replace('_', ' ').title(),
                        description=f"Potential issue: {issue_name}",
                        location=f"Line {i}",
                        code_snippet=line.strip()
                    ))
        
        return findings


class ReviewerAgent(SpecializedAgent):
    """Agent specialized in reviewing and analyzing outputs."""
    
    def __init__(self, profile: AgentProfile):
        super().__init__(profile)
        self.code_analyzer = CodeAnalyzer()
        self.review_types = profile.metadata.get('review_types', [
            ReviewType.CODE_QUALITY,
            ReviewType.CORRECTNESS,
            ReviewType.SECURITY
        ])
        self.severity_thresholds = {
            ReviewSeverity.CRITICAL: 0,     # Any critical issue fails
            ReviewSeverity.HIGH: 2,         # More than 2 high issues fails
            ReviewSeverity.MEDIUM: 5,       # More than 5 medium issues warns
            ReviewSeverity.LOW: 10          # More than 10 low issues noted
        }
    
    async def initialize(self) -> bool:
        """Initialize reviewer agent."""
        logger.info(f"Initializing ReviewerAgent {self.profile.agent_id}")
        self._initialized = True
        return True
    
    async def can_handle_task(self, task: TMTask) -> float:
        """Evaluate if agent can handle review task."""
        confidence = 0.0
        
        task_text = f"{task.title} {task.description}".lower()
        
        # Check for review keywords
        review_keywords = ['review', 'analyze', 'check', 'verify', 'validate', 'audit', 'inspect']
        if any(keyword in task_text for keyword in review_keywords):
            confidence += 0.6
        
        # Check for output/result keywords
        if any(word in task_text for word in ['output', 'result', 'implementation', 'code']):
            confidence += 0.2
        
        # Check capabilities
        if self.profile.has_capability(AgentCapability.CODE_REVIEW):
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    async def execute_task(self, task: TMTask, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute review task."""
        logger.info(f"ReviewerAgent {self.profile.agent_id} reviewing task {task.id}")
        
        # Extract output to review
        output_to_review = context.get('output', '')
        file_changes = context.get('file_changes', [])
        task_type = context.get('task_type', 'general')
        
        # Perform review
        review_result = await self.review_output(
            task_id=task.id,
            output=output_to_review,
            file_changes=file_changes,
            task_type=task_type
        )
        
        # Format result
        result = {
            "status": "completed",
            "agent_id": self.profile.agent_id,
            "review_passed": review_result.passed,
            "overall_score": review_result.overall_score,
            "findings": len(review_result.findings),
            "critical_issues": sum(1 for f in review_result.findings if f.severity == ReviewSeverity.CRITICAL),
            "recommendations": review_result.recommendations,
            "follow_up_required": review_result.follow_up_required,
            "detailed_review": review_result.to_dict()
        }
        
        return result
    
    async def validate_output(self, output: Any) -> bool:
        """Validate review output."""
        if not isinstance(output, dict):
            return False
        
        required_fields = ['status', 'review_passed', 'overall_score']
        return all(field in output for field in required_fields)
    
    async def review_output(self,
                           task_id: str,
                           output: str,
                           file_changes: List[Dict[str, Any]] = None,
                           task_type: str = "general") -> ReviewResult:
        """Perform comprehensive review of task output.
        
        Args:
            task_id: Task identifier
            output: Task output to review
            file_changes: List of file changes
            task_type: Type of task
            
        Returns:
            Review result
        """
        findings = []
        metrics = {}
        
        # Review based on content type
        if file_changes:
            for file_change in file_changes:
                file_path = file_change.get('path', '')
                content = file_change.get('content', '')
                change_type = file_change.get('type', 'modify')
                
                if file_path.endswith('.py'):
                    # Python code review
                    code_findings = self.code_analyzer.analyze_code(content, 'python')
                    findings.extend(code_findings)
                    
                elif file_path.endswith('.js'):
                    # JavaScript code review
                    code_findings = self.code_analyzer.analyze_code(content, 'javascript')
                    findings.extend(code_findings)
                
                # Check for large files
                if len(content) > 10000:
                    findings.append(ReviewFinding(
                        finding_id=f"large_file_{file_path}",
                        review_type=ReviewType.ARCHITECTURE,
                        severity=ReviewSeverity.MEDIUM,
                        title="Large file detected",
                        description=f"File {file_path} is very large ({len(content)} chars)",
                        location=file_path,
                        suggestion="Consider splitting into smaller modules"
                    ))
        
        # Analyze output text
        if output:
            # Check for error indicators
            error_patterns = [
                (r'error:', ReviewSeverity.HIGH),
                (r'exception:', ReviewSeverity.HIGH),
                (r'failed:', ReviewSeverity.HIGH),
                (r'warning:', ReviewSeverity.MEDIUM),
                (r'deprecated:', ReviewSeverity.LOW)
            ]
            
            output_lower = output.lower()
            for pattern, severity in error_patterns:
                if re.search(pattern, output_lower):
                    findings.append(ReviewFinding(
                        finding_id=f"output_{pattern.strip(':')}",
                        review_type=ReviewType.CORRECTNESS,
                        severity=severity,
                        title=f"Output contains {pattern.strip(':')}",
                        description="Task output indicates potential issues",
                        suggestion="Review the error/warning and address if needed"
                    ))
        
        # Calculate metrics
        metrics['total_findings'] = len(findings)
        metrics['findings_by_severity'] = {}
        for severity in ReviewSeverity:
            count = sum(1 for f in findings if f.severity == severity)
            metrics['findings_by_severity'][severity.value] = count
        
        metrics['findings_by_type'] = {}
        for review_type in ReviewType:
            count = sum(1 for f in findings if f.review_type == review_type)
            metrics['findings_by_type'][review_type.value] = count
        
        # Determine if review passed
        critical_count = metrics['findings_by_severity'].get(ReviewSeverity.CRITICAL.value, 0)
        high_count = metrics['findings_by_severity'].get(ReviewSeverity.HIGH.value, 0)
        
        passed = (
            critical_count <= self.severity_thresholds[ReviewSeverity.CRITICAL] and
            high_count <= self.severity_thresholds[ReviewSeverity.HIGH]
        )
        
        # Calculate overall score
        total_weight = 0
        weighted_score = 0
        severity_weights = {
            ReviewSeverity.CRITICAL: 10,
            ReviewSeverity.HIGH: 5,
            ReviewSeverity.MEDIUM: 2,
            ReviewSeverity.LOW: 1,
            ReviewSeverity.INFO: 0
        }
        
        for finding in findings:
            weight = severity_weights.get(finding.severity, 0)
            total_weight += weight
        
        # Score calculation (1.0 is perfect, 0.0 is worst)
        if total_weight > 0:
            overall_score = max(0.0, 1.0 - (total_weight / 100.0))
        else:
            overall_score = 1.0
        
        # Generate recommendations
        recommendations = self._generate_recommendations(findings, task_type)
        
        # Determine if follow-up is required
        follow_up_required = critical_count > 0 or high_count > 2
        
        return ReviewResult(
            task_id=task_id,
            reviewer_id=self.profile.agent_id,
            overall_score=overall_score,
            passed=passed,
            findings=findings,
            metrics=metrics,
            recommendations=recommendations,
            follow_up_required=follow_up_required
        )
    
    def _generate_recommendations(self, 
                                findings: List[ReviewFinding],
                                task_type: str) -> List[str]:
        """Generate recommendations based on findings.
        
        Args:
            findings: Review findings
            task_type: Type of task
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Group findings by type
        findings_by_type = {}
        for finding in findings:
            if finding.review_type not in findings_by_type:
                findings_by_type[finding.review_type] = []
            findings_by_type[finding.review_type].append(finding)
        
        # Generate type-specific recommendations
        if ReviewType.SECURITY in findings_by_type:
            security_count = len(findings_by_type[ReviewType.SECURITY])
            if security_count > 0:
                recommendations.append(
                    f"Address {security_count} security findings before deployment"
                )
                if any(f.severity == ReviewSeverity.CRITICAL for f in findings_by_type[ReviewType.SECURITY]):
                    recommendations.append(
                        "CRITICAL: Security vulnerabilities found - immediate action required"
                    )
        
        if ReviewType.CODE_QUALITY in findings_by_type:
            quality_issues = len(findings_by_type[ReviewType.CODE_QUALITY])
            if quality_issues > 5:
                recommendations.append(
                    "Consider refactoring to improve code quality"
                )
            if quality_issues > 10:
                recommendations.append(
                    "Code quality issues are impacting maintainability"
                )
        
        if ReviewType.TESTING in findings_by_type:
            recommendations.append(
                "Add comprehensive tests to ensure correctness"
            )
        
        if ReviewType.DOCUMENTATION in findings_by_type:
            recommendations.append(
                "Improve documentation for better maintainability"
            )
        
        # Task-specific recommendations
        if task_type == "feature":
            if not any("test" in str(f.tags) for f in findings):
                recommendations.append(
                    "Add tests for the new feature"
                )
        
        if task_type == "bugfix":
            recommendations.append(
                "Ensure the fix includes regression tests"
            )
        
        # General recommendations based on score
        if findings and not recommendations:
            if any(f.severity in [ReviewSeverity.CRITICAL, ReviewSeverity.HIGH] for f in findings):
                recommendations.append(
                    "Address high-priority issues before marking task complete"
                )
            else:
                recommendations.append(
                    "Consider addressing medium/low priority issues in follow-up tasks"
                )
        
        return recommendations


class OutputAnalysisReviewer(ReviewerAgent):
    """Specialized reviewer for analyzing task outputs."""
    
    def __init__(self, profile: AgentProfile):
        super().__init__(profile)
        self.output_patterns = {
            # Success indicators
            "success": [
                r"success", r"completed", r"done", r"finished",
                r"passed", r"✓", r"✅", r"implemented"
            ],
            # Failure indicators
            "failure": [
                r"error", r"failed", r"exception", r"crash",
                r"abort", r"❌", r"✗", r"unsuccessful"
            ],
            # Warning indicators
            "warning": [
                r"warning", r"warn", r"deprecated", r"caution",
                r"⚠️", r"notice", r"attention"
            ]
        }
    
    async def analyze_task_output(self,
                                 task: TMTask,
                                 output: str,
                                 expected_output: Optional[str] = None) -> ReviewResult:
        """Analyze task output for correctness and completeness.
        
        Args:
            task: Task that was executed
            output: Actual output
            expected_output: Expected output if available
            
        Returns:
            Analysis result
        """
        findings = []
        
        # Check output indicators
        output_lower = output.lower()
        
        failure_count = sum(
            1 for pattern in self.output_patterns["failure"]
            if re.search(pattern, output_lower)
        )
        
        success_count = sum(
            1 for pattern in self.output_patterns["success"]
            if re.search(pattern, output_lower)
        )
        
        warning_count = sum(
            1 for pattern in self.output_patterns["warning"]
            if re.search(pattern, output_lower)
        )
        
        # Analyze based on indicators
        if failure_count > success_count:
            findings.append(ReviewFinding(
                finding_id="output_indicates_failure",
                review_type=ReviewType.CORRECTNESS,
                severity=ReviewSeverity.HIGH,
                title="Output indicates task failure",
                description=f"Found {failure_count} failure indicators vs {success_count} success indicators",
                suggestion="Review the task execution for errors"
            ))
        
        if warning_count > 0:
            findings.append(ReviewFinding(
                finding_id="output_has_warnings",
                review_type=ReviewType.CORRECTNESS,
                severity=ReviewSeverity.MEDIUM,
                title="Output contains warnings",
                description=f"Found {warning_count} warning indicators",
                suggestion="Address warnings to ensure robust implementation"
            ))
        
        # Compare with expected output if provided
        if expected_output:
            similarity = difflib.SequenceMatcher(None, output, expected_output).ratio()
            
            if similarity < 0.8:  # Less than 80% similar
                findings.append(ReviewFinding(
                    finding_id="output_mismatch",
                    review_type=ReviewType.CORRECTNESS,
                    severity=ReviewSeverity.HIGH,
                    title="Output doesn't match expected",
                    description=f"Output similarity is only {similarity:.1%}",
                    suggestion="Review implementation to ensure it meets requirements"
                ))
        
        # Check for incomplete output
        incomplete_indicators = ["todo", "fixme", "not implemented", "placeholder"]
        if any(indicator in output_lower for indicator in incomplete_indicators):
            findings.append(ReviewFinding(
                finding_id="incomplete_output",
                review_type=ReviewType.CORRECTNESS,
                severity=ReviewSeverity.HIGH,
                title="Output indicates incomplete implementation",
                description="Found indicators of incomplete work",
                suggestion="Complete the implementation before marking task done"
            ))
        
        # Calculate score and create result
        passed = failure_count == 0 and all(
            f.severity not in [ReviewSeverity.CRITICAL, ReviewSeverity.HIGH]
            for f in findings
        )
        
        score = 1.0
        if failure_count > 0:
            score -= 0.3 * failure_count
        if warning_count > 0:
            score -= 0.1 * warning_count
        score = max(0.0, score)
        
        return ReviewResult(
            task_id=task.id,
            reviewer_id=self.profile.agent_id,
            overall_score=score,
            passed=passed,
            findings=findings,
            metrics={
                "success_indicators": success_count,
                "failure_indicators": failure_count,
                "warning_indicators": warning_count
            },
            recommendations=self._generate_recommendations(findings, "output_analysis"),
            follow_up_required=not passed
        )


# Factory function
def create_reviewer_agent(agent_id: str, 
                         name: str,
                         review_types: Optional[List[ReviewType]] = None) -> ReviewerAgent:
    """Create a reviewer agent.
    
    Args:
        agent_id: Unique agent identifier
        name: Agent name
        review_types: Types of reviews to perform
        
    Returns:
        Configured reviewer agent
    """
    profile = AgentProfile(
        agent_id=agent_id,
        name=name,
        role=AgentRole.REVIEWER,
        capabilities={
            AgentCapability.CODE_REVIEW,
            AgentCapability.DOCUMENTATION,
            AgentCapability.TESTING
        },
        metadata={
            "review_types": review_types or [
                ReviewType.CODE_QUALITY,
                ReviewType.CORRECTNESS,
                ReviewType.SECURITY
            ]
        }
    )
    
    return ReviewerAgent(profile)


def create_output_analysis_reviewer(agent_id: str, name: str) -> OutputAnalysisReviewer:
    """Create an output analysis reviewer.
    
    Args:
        agent_id: Unique identifier
        name: Agent name
        
    Returns:
        Output analysis reviewer
    """
    profile = AgentProfile(
        agent_id=agent_id,
        name=name,
        role=AgentRole.REVIEWER,
        capabilities={AgentCapability.CODE_REVIEW},
        specializations=["output_analysis", "correctness_verification"]
    )
    
    return OutputAnalysisReviewer(profile)