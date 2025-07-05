"""Plan Validation Stage for Claude Orchestrator.

This module provides validation for task execution plans before
they are executed, ensuring correctness, feasibility, and safety.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json

from .task_master import Task as TMTask, TaskStatus as TMTaskStatus
from .feedback_model import (
    FeedbackModel, FeedbackType, FeedbackSeverity,
    create_warning_feedback, create_validation_feedback
)

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Result of plan validation."""
    APPROVED = "approved"           # Plan is good to execute
    APPROVED_WITH_WARNINGS = "approved_with_warnings"  # Execute with caution
    REQUIRES_MODIFICATION = "requires_modification"     # Needs changes
    REJECTED = "rejected"           # Should not execute


class ValidationCategory(Enum):
    """Categories of validation checks."""
    DEPENDENCIES = "dependencies"
    RESOURCES = "resources"
    SECURITY = "security"
    FEASIBILITY = "feasibility"
    COMPLEXITY = "complexity"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"


@dataclass
class ValidationIssue:
    """Individual validation issue found."""
    issue_id: str
    category: ValidationCategory
    severity: FeedbackSeverity
    title: str
    description: str
    affected_tasks: List[str] = field(default_factory=list)
    suggestion: Optional[str] = None
    blocking: bool = False  # If true, prevents execution


@dataclass
class PlanValidationReport:
    """Complete validation report for a plan."""
    plan_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    result: ValidationResult = ValidationResult.APPROVED
    issues: List[ValidationIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    estimated_duration: Optional[timedelta] = None
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    risk_assessment: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "plan_id": self.plan_id,
            "timestamp": self.timestamp.isoformat(),
            "result": self.result.value,
            "issues": [
                {
                    "id": issue.issue_id,
                    "category": issue.category.value,
                    "severity": issue.severity.value,
                    "title": issue.title,
                    "description": issue.description,
                    "affected_tasks": issue.affected_tasks,
                    "suggestion": issue.suggestion,
                    "blocking": issue.blocking
                }
                for issue in self.issues
            ],
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "estimated_duration": str(self.estimated_duration) if self.estimated_duration else None,
            "resource_requirements": self.resource_requirements,
            "risk_assessment": self.risk_assessment
        }


class DependencyValidator:
    """Validates task dependencies."""
    
    def validate_dependencies(self, tasks: List[TMTask]) -> List[ValidationIssue]:
        """Validate task dependencies are correct and achievable.
        
        Args:
            tasks: List of tasks to validate
            
        Returns:
            List of validation issues
        """
        issues = []
        task_ids = {task.id for task in tasks}
        
        # Check for missing dependencies
        for task in tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    issues.append(ValidationIssue(
                        issue_id=f"missing_dep_{task.id}_{dep}",
                        category=ValidationCategory.DEPENDENCIES,
                        severity=FeedbackSeverity.ERROR,
                        title="Missing dependency",
                        description=f"Task {task.id} depends on {dep} which is not in the plan",
                        affected_tasks=[task.id],
                        suggestion="Add the missing task or remove the dependency",
                        blocking=True
                    ))
        
        # Check for circular dependencies
        cycles = self._find_dependency_cycles(tasks)
        for cycle in cycles:
            issues.append(ValidationIssue(
                issue_id=f"circular_dep_{'_'.join(cycle)}",
                category=ValidationCategory.DEPENDENCIES,
                severity=FeedbackSeverity.ERROR,
                title="Circular dependency detected",
                description=f"Tasks form a circular dependency: {' -> '.join(cycle)}",
                affected_tasks=cycle,
                suggestion="Restructure tasks to remove the circular dependency",
                blocking=True
            ))
        
        # Check for deep dependency chains
        max_depth = 5
        for task in tasks:
            depth = self._get_dependency_depth(task, tasks, task_ids)
            if depth > max_depth:
                issues.append(ValidationIssue(
                    issue_id=f"deep_deps_{task.id}",
                    category=ValidationCategory.DEPENDENCIES,
                    severity=FeedbackSeverity.WARNING,
                    title="Deep dependency chain",
                    description=f"Task {task.id} has a dependency depth of {depth}",
                    affected_tasks=[task.id],
                    suggestion="Consider flattening the dependency structure"
                ))
        
        return issues
    
    def _find_dependency_cycles(self, tasks: List[TMTask]) -> List[List[str]]:
        """Find circular dependencies using DFS.
        
        Args:
            tasks: List of tasks
            
        Returns:
            List of cycles (each cycle is a list of task IDs)
        """
        # Build adjacency list
        graph = {}
        for task in tasks:
            graph[task.id] = task.dependencies
        
        # DFS to find cycles
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                    return True
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        for task in tasks:
            if task.id not in visited:
                dfs(task.id, [])
        
        return cycles
    
    def _get_dependency_depth(self, task: TMTask, all_tasks: List[TMTask], 
                            task_ids: Set[str], visited: Optional[Set[str]] = None) -> int:
        """Get the maximum dependency depth for a task.
        
        Args:
            task: Task to check
            all_tasks: All tasks
            task_ids: Set of valid task IDs
            visited: Set of visited tasks (for cycle detection)
            
        Returns:
            Maximum dependency depth
        """
        if visited is None:
            visited = set()
        
        if task.id in visited:
            return 0  # Cycle detected
        
        visited.add(task.id)
        
        if not task.dependencies:
            return 0
        
        max_depth = 0
        task_map = {t.id: t for t in all_tasks}
        
        for dep_id in task.dependencies:
            if dep_id in task_ids and dep_id in task_map:
                dep_task = task_map[dep_id]
                depth = 1 + self._get_dependency_depth(dep_task, all_tasks, task_ids, visited)
                max_depth = max(max_depth, depth)
        
        visited.remove(task.id)
        return max_depth


class ResourceValidator:
    """Validates resource requirements and availability."""
    
    def __init__(self, max_workers: int = 4, max_memory_gb: int = 16):
        self.max_workers = max_workers
        self.max_memory_gb = max_memory_gb
        self.resource_patterns = {
            "high_memory": ["large", "data processing", "analysis", "ml", "ai"],
            "high_cpu": ["compute", "build", "compile", "optimization"],
            "network": ["api", "download", "upload", "fetch", "request"],
            "disk": ["file", "save", "write", "export", "generate"]
        }
    
    def validate_resources(self, tasks: List[TMTask]) -> Tuple[List[ValidationIssue], Dict[str, Any]]:
        """Validate resource requirements for tasks.
        
        Args:
            tasks: List of tasks
            
        Returns:
            Tuple of (issues, resource_requirements)
        """
        issues = []
        requirements = {
            "estimated_workers": 0,
            "estimated_memory_gb": 0,
            "estimated_duration_hours": 0,
            "resource_intensive_tasks": []
        }
        
        # Estimate resource needs
        concurrent_tasks = self._estimate_max_concurrent_tasks(tasks)
        requirements["estimated_workers"] = min(concurrent_tasks, self.max_workers)
        
        # Check individual task resources
        for task in tasks:
            task_resources = self._estimate_task_resources(task)
            
            if task_resources["memory_gb"] > 4:  # High memory task
                requirements["resource_intensive_tasks"].append({
                    "task_id": task.id,
                    "type": "high_memory",
                    "estimated_memory_gb": task_resources["memory_gb"]
                })
                
                if task_resources["memory_gb"] > self.max_memory_gb / 2:
                    issues.append(ValidationIssue(
                        issue_id=f"high_memory_{task.id}",
                        category=ValidationCategory.RESOURCES,
                        severity=FeedbackSeverity.WARNING,
                        title="High memory requirement",
                        description=f"Task {task.id} may require {task_resources['memory_gb']}GB memory",
                        affected_tasks=[task.id],
                        suggestion="Consider breaking into smaller tasks or optimizing memory usage"
                    ))
            
            requirements["estimated_memory_gb"] = max(
                requirements["estimated_memory_gb"],
                task_resources["memory_gb"]
            )
            requirements["estimated_duration_hours"] += task_resources["duration_hours"]
        
        # Check total resource requirements
        if concurrent_tasks > self.max_workers * 2:
            issues.append(ValidationIssue(
                issue_id="insufficient_workers",
                category=ValidationCategory.RESOURCES,
                severity=FeedbackSeverity.WARNING,
                title="High parallelism required",
                description=f"Plan could benefit from {concurrent_tasks} workers but only {self.max_workers} available",
                affected_tasks=[],
                suggestion="Tasks will be queued, consider increasing worker count"
            ))
        
        if requirements["estimated_memory_gb"] > self.max_memory_gb:
            issues.append(ValidationIssue(
                issue_id="insufficient_memory",
                category=ValidationCategory.RESOURCES,
                severity=FeedbackSeverity.ERROR,
                title="Insufficient memory",
                description=f"Plan requires {requirements['estimated_memory_gb']}GB but only {self.max_memory_gb}GB available",
                affected_tasks=[],
                suggestion="Reduce memory requirements or increase available memory",
                blocking=True
            ))
        
        return issues, requirements
    
    def _estimate_max_concurrent_tasks(self, tasks: List[TMTask]) -> int:
        """Estimate maximum number of concurrent tasks.
        
        Args:
            tasks: List of tasks
            
        Returns:
            Maximum concurrent tasks
        """
        if not tasks:
            return 0
        
        # Simple estimation based on dependency levels
        levels = {}
        task_map = {t.id: t for t in tasks}
        
        def get_level(task_id: str, visited: Set[str] = None) -> int:
            if visited is None:
                visited = set()
            
            if task_id in levels:
                return levels[task_id]
            
            if task_id in visited:
                return 0
            
            visited.add(task_id)
            
            task = task_map.get(task_id)
            if not task or not task.dependencies:
                level = 0
            else:
                level = 1 + max(
                    get_level(dep, visited) 
                    for dep in task.dependencies 
                    if dep in task_map
                )
            
            levels[task_id] = level
            return level
        
        for task in tasks:
            get_level(task.id)
        
        # Count tasks at each level
        level_counts = {}
        for level in levels.values():
            level_counts[level] = level_counts.get(level, 0) + 1
        
        return max(level_counts.values()) if level_counts else 1
    
    def _estimate_task_resources(self, task: TMTask) -> Dict[str, Any]:
        """Estimate resource requirements for a task.
        
        Args:
            task: Task to estimate
            
        Returns:
            Resource estimates
        """
        resources = {
            "memory_gb": 1,  # Default 1GB
            "cpu_cores": 1,
            "duration_hours": 0.5,  # Default 30 minutes
            "requires_network": False,
            "requires_disk": False
        }
        
        task_text = f"{task.title} {task.description}".lower()
        
        # Check for resource indicators
        for resource_type, patterns in self.resource_patterns.items():
            if any(pattern in task_text for pattern in patterns):
                if resource_type == "high_memory":
                    resources["memory_gb"] = 4
                elif resource_type == "high_cpu":
                    resources["cpu_cores"] = 2
                    resources["duration_hours"] = 1
                elif resource_type == "network":
                    resources["requires_network"] = True
                elif resource_type == "disk":
                    resources["requires_disk"] = True
        
        # Adjust based on task metadata if available
        if hasattr(task, 'metadata'):
            if 'estimated_duration' in task.metadata:
                resources["duration_hours"] = task.metadata['estimated_duration'] / 60
            if 'memory_requirement' in task.metadata:
                resources["memory_gb"] = task.metadata['memory_requirement']
        
        return resources


class SecurityValidator:
    """Validates security aspects of the plan."""
    
    def __init__(self):
        self.sensitive_patterns = [
            r'password|passwd|pwd',
            r'secret|token|key',
            r'credential|auth',
            r'api[_-]?key',
            r'private[_-]?key',
            r'database|db[_-]?conn',
            r'production|prod[_-]?env'
        ]
        
        self.risky_operations = [
            "delete", "remove", "drop", "truncate",
            "deploy", "publish", "release",
            "sudo", "admin", "root",
            "execute", "eval", "exec"
        ]
    
    def validate_security(self, tasks: List[TMTask]) -> Tuple[List[ValidationIssue], Dict[str, Any]]:
        """Validate security aspects of tasks.
        
        Args:
            tasks: List of tasks
            
        Returns:
            Tuple of (issues, risk_assessment)
        """
        issues = []
        risk_assessment = {
            "risk_level": "low",
            "sensitive_tasks": [],
            "risky_operations": [],
            "security_recommendations": []
        }
        
        for task in tasks:
            task_text = f"{task.title} {task.description}".lower()
            
            # Check for sensitive data handling
            for pattern in self.sensitive_patterns:
                if re.search(pattern, task_text, re.IGNORECASE):
                    risk_assessment["sensitive_tasks"].append({
                        "task_id": task.id,
                        "pattern": pattern,
                        "title": task.title
                    })
                    
                    issues.append(ValidationIssue(
                        issue_id=f"sensitive_data_{task.id}",
                        category=ValidationCategory.SECURITY,
                        severity=FeedbackSeverity.WARNING,
                        title="Sensitive data handling",
                        description=f"Task {task.id} may handle sensitive data ({pattern})",
                        affected_tasks=[task.id],
                        suggestion="Ensure proper security measures and avoid logging sensitive data"
                    ))
            
            # Check for risky operations
            for operation in self.risky_operations:
                if operation in task_text:
                    risk_assessment["risky_operations"].append({
                        "task_id": task.id,
                        "operation": operation,
                        "title": task.title
                    })
                    
                    if operation in ["delete", "drop", "truncate"]:
                        issues.append(ValidationIssue(
                            issue_id=f"destructive_op_{task.id}",
                            category=ValidationCategory.SECURITY,
                            severity=FeedbackSeverity.HIGH,
                            title="Destructive operation",
                            description=f"Task {task.id} performs destructive operation: {operation}",
                            affected_tasks=[task.id],
                            suggestion="Ensure backups exist and add confirmation steps",
                            blocking=False
                        ))
                    
                    if operation in ["sudo", "admin", "root"]:
                        issues.append(ValidationIssue(
                            issue_id=f"elevated_privs_{task.id}",
                            category=ValidationCategory.SECURITY,
                            severity=FeedbackSeverity.HIGH,
                            title="Elevated privileges required",
                            description=f"Task {task.id} requires elevated privileges",
                            affected_tasks=[task.id],
                            suggestion="Minimize privilege requirements and use least privilege principle",
                            blocking=False
                        ))
        
        # Determine overall risk level
        if len(risk_assessment["risky_operations"]) > 3:
            risk_assessment["risk_level"] = "high"
        elif len(risk_assessment["sensitive_tasks"]) > 2 or len(risk_assessment["risky_operations"]) > 1:
            risk_assessment["risk_level"] = "medium"
        
        # Add recommendations
        if risk_assessment["sensitive_tasks"]:
            risk_assessment["security_recommendations"].append(
                "Use environment variables for sensitive data"
            )
            risk_assessment["security_recommendations"].append(
                "Implement proper access controls"
            )
        
        if risk_assessment["risky_operations"]:
            risk_assessment["security_recommendations"].append(
                "Create backups before destructive operations"
            )
            risk_assessment["security_recommendations"].append(
                "Add confirmation steps for critical operations"
            )
        
        return issues, risk_assessment


class PlanValidator:
    """Main plan validator that orchestrates all validation checks."""
    
    def __init__(self, 
                 max_workers: int = 4,
                 strict_mode: bool = False):
        self.max_workers = max_workers
        self.strict_mode = strict_mode
        
        # Initialize validators
        self.dependency_validator = DependencyValidator()
        self.resource_validator = ResourceValidator(max_workers=max_workers)
        self.security_validator = SecurityValidator()
        
        logger.info(f"Plan validator initialized (strict_mode={strict_mode})")
    
    def validate_plan(self, tasks: List[TMTask], plan_metadata: Optional[Dict[str, Any]] = None) -> PlanValidationReport:
        """Validate a complete execution plan.
        
        Args:
            tasks: List of tasks in the plan
            plan_metadata: Additional plan metadata
            
        Returns:
            Validation report
        """
        plan_id = plan_metadata.get("plan_id", f"plan_{datetime.now().timestamp()}")
        report = PlanValidationReport(plan_id=plan_id)
        
        if not tasks:
            report.result = ValidationResult.REJECTED
            report.issues.append(ValidationIssue(
                issue_id="empty_plan",
                category=ValidationCategory.COMPLETENESS,
                severity=FeedbackSeverity.ERROR,
                title="Empty plan",
                description="No tasks provided in the plan",
                blocking=True
            ))
            return report
        
        # Run all validators
        all_issues = []
        
        # Dependency validation
        dep_issues = self.dependency_validator.validate_dependencies(tasks)
        all_issues.extend(dep_issues)
        
        # Resource validation
        resource_issues, resource_requirements = self.resource_validator.validate_resources(tasks)
        all_issues.extend(resource_issues)
        report.resource_requirements = resource_requirements
        
        # Security validation
        security_issues, risk_assessment = self.security_validator.validate_security(tasks)
        all_issues.extend(security_issues)
        report.risk_assessment = risk_assessment
        
        # Additional validations
        all_issues.extend(self._validate_completeness(tasks))
        all_issues.extend(self._validate_complexity(tasks))
        all_issues.extend(self._validate_consistency(tasks))
        
        # Store all issues
        report.issues = all_issues
        
        # Calculate metrics
        report.metrics = {
            "total_tasks": len(tasks),
            "total_issues": len(all_issues),
            "blocking_issues": sum(1 for i in all_issues if i.blocking),
            "issues_by_category": {},
            "issues_by_severity": {}
        }
        
        for issue in all_issues:
            cat = issue.category.value
            sev = issue.severity.value
            report.metrics["issues_by_category"][cat] = report.metrics["issues_by_category"].get(cat, 0) + 1
            report.metrics["issues_by_severity"][sev] = report.metrics["issues_by_severity"].get(sev, 0) + 1
        
        # Determine validation result
        blocking_count = report.metrics["blocking_issues"]
        error_count = report.metrics["issues_by_severity"].get(FeedbackSeverity.ERROR.value, 0)
        warning_count = report.metrics["issues_by_severity"].get(FeedbackSeverity.WARNING.value, 0)
        
        if blocking_count > 0:
            report.result = ValidationResult.REJECTED
        elif error_count > 0:
            report.result = ValidationResult.REQUIRES_MODIFICATION
        elif warning_count > 0:
            report.result = ValidationResult.APPROVED_WITH_WARNINGS
        else:
            report.result = ValidationResult.APPROVED
        
        # In strict mode, warnings become errors
        if self.strict_mode and warning_count > 0:
            report.result = ValidationResult.REQUIRES_MODIFICATION
        
        # Estimate duration
        report.estimated_duration = timedelta(
            hours=resource_requirements.get("estimated_duration_hours", 0)
        )
        
        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)
        
        return report
    
    def _validate_completeness(self, tasks: List[TMTask]) -> List[ValidationIssue]:
        """Validate plan completeness.
        
        Args:
            tasks: List of tasks
            
        Returns:
            List of issues
        """
        issues = []
        
        # Check for tasks with empty descriptions
        for task in tasks:
            if not task.description or len(task.description.strip()) < 10:
                issues.append(ValidationIssue(
                    issue_id=f"incomplete_desc_{task.id}",
                    category=ValidationCategory.COMPLETENESS,
                    severity=FeedbackSeverity.WARNING,
                    title="Incomplete task description",
                    description=f"Task {task.id} has insufficient description",
                    affected_tasks=[task.id],
                    suggestion="Add detailed description of what needs to be done"
                ))
        
        # Check for orphaned tasks (no dependencies and nothing depends on them)
        task_ids = {t.id for t in tasks}
        depended_on = set()
        for task in tasks:
            depended_on.update(task.dependencies)
        
        for task in tasks:
            if not task.dependencies and task.id not in depended_on:
                if len(tasks) > 1:  # Only flag if there are multiple tasks
                    issues.append(ValidationIssue(
                        issue_id=f"orphaned_task_{task.id}",
                        category=ValidationCategory.COMPLETENESS,
                        severity=FeedbackSeverity.INFO,
                        title="Isolated task",
                        description=f"Task {task.id} has no dependencies and nothing depends on it",
                        affected_tasks=[task.id],
                        suggestion="Consider if this task should be connected to others"
                    ))
        
        return issues
    
    def _validate_complexity(self, tasks: List[TMTask]) -> List[ValidationIssue]:
        """Validate plan complexity.
        
        Args:
            tasks: List of tasks
            
        Returns:
            List of issues
        """
        issues = []
        
        # Check overall plan size
        if len(tasks) > 50:
            issues.append(ValidationIssue(
                issue_id="plan_too_large",
                category=ValidationCategory.COMPLEXITY,
                severity=FeedbackSeverity.WARNING,
                title="Large plan",
                description=f"Plan contains {len(tasks)} tasks",
                affected_tasks=[],
                suggestion="Consider breaking into multiple smaller plans"
            ))
        
        # Check for overly complex tasks
        for task in tasks:
            # Simple heuristic: long descriptions might indicate complex tasks
            if len(task.description) > 1000:
                issues.append(ValidationIssue(
                    issue_id=f"complex_task_{task.id}",
                    category=ValidationCategory.COMPLEXITY,
                    severity=FeedbackSeverity.WARNING,
                    title="Complex task",
                    description=f"Task {task.id} appears complex (long description)",
                    affected_tasks=[task.id],
                    suggestion="Consider breaking into subtasks"
                ))
        
        return issues
    
    def _validate_consistency(self, tasks: List[TMTask]) -> List[ValidationIssue]:
        """Validate plan consistency.
        
        Args:
            tasks: List of tasks
            
        Returns:
            List of issues
        """
        issues = []
        
        # Check for duplicate task titles
        titles = {}
        for task in tasks:
            if task.title in titles:
                issues.append(ValidationIssue(
                    issue_id=f"duplicate_title_{task.id}",
                    category=ValidationCategory.CONSISTENCY,
                    severity=FeedbackSeverity.WARNING,
                    title="Duplicate task title",
                    description=f"Task {task.id} has same title as {titles[task.title]}",
                    affected_tasks=[task.id, titles[task.title]],
                    suggestion="Use unique, descriptive titles for each task"
                ))
            titles[task.title] = task.id
        
        # Check for inconsistent naming patterns
        # (This is a simple check - could be made more sophisticated)
        naming_styles = {"camelCase": 0, "snake_case": 0, "kebab-case": 0, "other": 0}
        
        for task in tasks:
            if re.match(r'^[a-z]+([A-Z][a-z]*)*$', task.id):
                naming_styles["camelCase"] += 1
            elif re.match(r'^[a-z]+(_[a-z]+)*$', task.id):
                naming_styles["snake_case"] += 1
            elif re.match(r'^[a-z]+(-[a-z]+)*$', task.id):
                naming_styles["kebab-case"] += 1
            else:
                naming_styles["other"] += 1
        
        # If multiple styles are used significantly
        used_styles = [k for k, v in naming_styles.items() if v > len(tasks) * 0.2]
        if len(used_styles) > 1:
            issues.append(ValidationIssue(
                issue_id="inconsistent_naming",
                category=ValidationCategory.CONSISTENCY,
                severity=FeedbackSeverity.INFO,
                title="Inconsistent naming style",
                description="Multiple naming conventions used for task IDs",
                affected_tasks=[],
                suggestion="Use consistent naming convention across all tasks"
            ))
        
        return issues
    
    def _generate_recommendations(self, report: PlanValidationReport) -> List[str]:
        """Generate recommendations based on validation report.
        
        Args:
            report: Validation report
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Based on validation result
        if report.result == ValidationResult.REJECTED:
            recommendations.append("Fix all blocking issues before executing this plan")
        elif report.result == ValidationResult.REQUIRES_MODIFICATION:
            recommendations.append("Address error-level issues to improve plan reliability")
        elif report.result == ValidationResult.APPROVED_WITH_WARNINGS:
            recommendations.append("Review warnings and address if possible before execution")
        
        # Based on specific issues
        if report.metrics.get("issues_by_category", {}).get(ValidationCategory.DEPENDENCIES.value, 0) > 0:
            recommendations.append("Review and fix dependency issues to ensure proper execution order")
        
        if report.metrics.get("issues_by_category", {}).get(ValidationCategory.RESOURCES.value, 0) > 0:
            recommendations.append("Monitor resource usage during execution")
        
        if report.risk_assessment.get("risk_level") in ["medium", "high"]:
            recommendations.append("Implement additional safety checks for risky operations")
            recommendations.append("Ensure backups are available before execution")
        
        # Based on plan characteristics
        if report.metrics.get("total_tasks", 0) > 20:
            recommendations.append("Consider running in batches for better manageability")
        
        if report.estimated_duration and report.estimated_duration.total_seconds() > 3600:
            recommendations.append("Plan execution may take significant time, ensure adequate monitoring")
        
        return recommendations


# Integration with orchestrator
class PlanValidationIntegration:
    """Integrates plan validation with the orchestrator."""
    
    def __init__(self, orchestrator, strict_mode: bool = False):
        self.orchestrator = orchestrator
        self.validator = PlanValidator(
            max_workers=getattr(orchestrator, 'max_workers', 4),
            strict_mode=strict_mode
        )
        self.validation_history: List[PlanValidationReport] = []
        
    def validate_before_execution(self, tasks: List[Any]) -> Tuple[bool, PlanValidationReport]:
        """Validate plan before execution.
        
        Args:
            tasks: List of tasks to validate
            
        Returns:
            Tuple of (can_execute, validation_report)
        """
        # Convert to TMTask format if needed
        tm_tasks = []
        for task in tasks:
            if hasattr(task, 'task_id'):  # WorkerTask format
                tm_task = TMTask(
                    id=task.task_id,
                    title=task.title,
                    description=task.description,
                    dependencies=task.dependencies,
                    metadata=getattr(task, 'metadata', {})
                )
            else:
                tm_task = task
            tm_tasks.append(tm_task)
        
        # Validate
        report = self.validator.validate_plan(tm_tasks)
        self.validation_history.append(report)
        
        # Store feedback if available
        if self.orchestrator.feedback_storage:
            try:
                feedback = create_validation_feedback(
                    validation_type="plan",
                    passed=report.result in [ValidationResult.APPROVED, ValidationResult.APPROVED_WITH_WARNINGS],
                    issues=[
                        {
                            "id": issue.issue_id,
                            "category": issue.category.value,
                            "severity": issue.severity.value,
                            "title": issue.title
                        }
                        for issue in report.issues
                    ],
                    details=report.to_dict()
                )
                self.orchestrator.feedback_storage.save(feedback)
            except Exception as e:
                logger.error(f"Failed to store validation feedback: {e}")
        
        # Determine if execution can proceed
        can_execute = report.result in [
            ValidationResult.APPROVED,
            ValidationResult.APPROVED_WITH_WARNINGS
        ]
        
        # Log results
        logger.info(f"Plan validation result: {report.result.value}")
        if report.issues:
            logger.info(f"Found {len(report.issues)} issues during validation")
            for issue in report.issues[:5]:  # Log first 5 issues
                logger.info(f"  - {issue.severity.value}: {issue.title}")
        
        return can_execute, report
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation history.
        
        Returns:
            Validation statistics
        """
        if not self.validation_history:
            return {"total_validations": 0}
        
        summary = {
            "total_validations": len(self.validation_history),
            "approved": sum(1 for r in self.validation_history 
                          if r.result == ValidationResult.APPROVED),
            "approved_with_warnings": sum(1 for r in self.validation_history 
                                        if r.result == ValidationResult.APPROVED_WITH_WARNINGS),
            "rejected": sum(1 for r in self.validation_history 
                          if r.result == ValidationResult.REJECTED),
            "recent_validations": []
        }
        
        # Add recent validation summaries
        for report in self.validation_history[-5:]:
            summary["recent_validations"].append({
                "plan_id": report.plan_id,
                "timestamp": report.timestamp.isoformat(),
                "result": report.result.value,
                "total_issues": len(report.issues),
                "blocking_issues": sum(1 for i in report.issues if i.blocking)
            })
        
        return summary


def integrate_plan_validation(orchestrator, strict_mode: bool = False) -> PlanValidationIntegration:
    """Integrate plan validation with orchestrator.
    
    Args:
        orchestrator: Orchestrator instance
        strict_mode: Whether to use strict validation
        
    Returns:
        Plan validation integration
    """
    integration = PlanValidationIntegration(orchestrator, strict_mode)
    
    # Store reference in orchestrator
    orchestrator.plan_validator = integration
    
    # Modify the task planning phase to include validation
    if hasattr(orchestrator, 'manager') and hasattr(orchestrator.manager, 'analyze_and_plan'):
        original_plan = orchestrator.manager.analyze_and_plan
        
        def validated_plan():
            tasks = original_plan()
            
            if tasks and integration:
                can_execute, report = integration.validate_before_execution(tasks)
                
                if not can_execute:
                    logger.error("Plan validation failed, cannot proceed with execution")
                    # Could raise exception or return empty list
                    if strict_mode:
                        raise ValueError(f"Plan validation failed: {report.result.value}")
            
            return tasks
        
        orchestrator.manager.analyze_and_plan = validated_plan
    
    logger.info("Plan validation integrated with orchestrator")
    
    return integration