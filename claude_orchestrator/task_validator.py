"""
Task Result Validation System for Claude Orchestrator
Validates task results before marking them as complete
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation strictness levels"""
    BASIC = "basic"        # Basic syntax/format checks
    STANDARD = "standard"  # Standard validation with common checks
    STRICT = "strict"      # Comprehensive validation with all checks


class ValidationResult(Enum):
    """Validation result status"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class ValidationError:
    """Validation error details"""
    code: str
    message: str
    severity: str  # "error", "warning", "info"
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class ValidationReport:
    """Comprehensive validation report"""
    task_id: str
    task_title: str
    validation_level: ValidationLevel
    overall_result: ValidationResult
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    checks_performed: List[str] = field(default_factory=list)
    validation_time: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, code: str, message: str, file_path: str = None, line_number: int = None, details: Dict = None):
        """Add validation error"""
        self.errors.append(ValidationError(
            code=code,
            message=message,
            severity="error",
            file_path=file_path,
            line_number=line_number,
            details=details
        ))
        if self.overall_result == ValidationResult.PASSED:
            self.overall_result = ValidationResult.FAILED
    
    def add_warning(self, code: str, message: str, file_path: str = None, line_number: int = None, details: Dict = None):
        """Add validation warning"""
        self.warnings.append(ValidationError(
            code=code,
            message=message,
            severity="warning",
            file_path=file_path,
            line_number=line_number,
            details=details
        ))
        if self.overall_result == ValidationResult.PASSED:
            self.overall_result = ValidationResult.WARNING
    
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)"""
        return len(self.errors) == 0
    
    def get_summary(self) -> str:
        """Get validation summary"""
        return f"Validation {self.overall_result.value}: {len(self.errors)} errors, {len(self.warnings)} warnings"


class TaskValidator:
    """
    Validates task results before marking them as complete
    """
    
    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STANDARD):
        self.validation_level = validation_level
        self.validators = {
            "code": self._validate_code,
            "files": self._validate_files,
            "dependencies": self._validate_dependencies,
            "tests": self._validate_tests,
            "documentation": self._validate_documentation,
            "security": self._validate_security,
            "performance": self._validate_performance,
            "format": self._validate_format
        }
    
    def validate_task_result(self, task_id: str, task_title: str, 
                           task_description: str, result_data: Dict[str, Any],
                           working_dir: str = None) -> ValidationReport:
        """
        Validate a task result comprehensively
        
        Args:
            task_id: Task identifier
            task_title: Task title
            task_description: Task description
            result_data: Task result data including files changed, output, etc.
            working_dir: Working directory for file validation
            
        Returns:
            ValidationReport with detailed results
        """
        report = ValidationReport(
            task_id=task_id,
            task_title=task_title,
            validation_level=self.validation_level,
            overall_result=ValidationResult.PASSED
        )
        
        working_dir = working_dir or os.getcwd()
        
        logger.info(f"Validating task {task_id}: {task_title}")
        
        # Determine which validations to run based on task type
        validation_types = self._determine_validation_types(task_description, result_data)
        
        for validation_type in validation_types:
            if validation_type in self.validators:
                try:
                    self.validators[validation_type](report, task_description, result_data, working_dir)
                    report.checks_performed.append(validation_type)
                except Exception as e:
                    report.add_error(
                        code=f"VALIDATION_ERROR_{validation_type.upper()}",
                        message=f"Error during {validation_type} validation: {str(e)}",
                        details={"exception": str(e), "type": type(e).__name__}
                    )
                    logger.error(f"Validation error in {validation_type}: {e}")
        
        # Add metadata
        report.metadata = {
            "working_dir": working_dir,
            "validation_types": validation_types,
            "result_data_keys": list(result_data.keys()) if result_data else []
        }
        
        logger.info(f"Task {task_id} validation complete: {report.get_summary()}")
        return report
    
    def _determine_validation_types(self, task_description: str, result_data: Dict[str, Any]) -> List[str]:
        """Determine which validation types to run based on task content"""
        validation_types = ["files", "format"]  # Always run basic validations
        
        description_lower = task_description.lower()
        
        # Code-related validations
        if any(keyword in description_lower for keyword in [
            "code", "implement", "function", "class", "method", "script", "program",
            "python", "javascript", "typescript", "java", "c++", "rust", "go"
        ]):
            validation_types.extend(["code", "dependencies"])
        
        # Test-related validations
        if any(keyword in description_lower for keyword in [
            "test", "testing", "unittest", "pytest", "jest", "spec"
        ]):
            validation_types.append("tests")
        
        # Documentation validations
        if any(keyword in description_lower for keyword in [
            "document", "readme", "docs", "comment", "docstring"
        ]):
            validation_types.append("documentation")
        
        # Security validations
        if any(keyword in description_lower for keyword in [
            "security", "authentication", "authorization", "encrypt", "decrypt",
            "password", "token", "api key", "credential"
        ]):
            validation_types.append("security")
        
        # Performance validations
        if any(keyword in description_lower for keyword in [
            "performance", "optimize", "speed", "memory", "cpu", "benchmark"
        ]):
            validation_types.append("performance")
        
        # Check result data for file changes
        if result_data and "files_changed" in result_data:
            validation_types.append("code")
        
        return list(set(validation_types))  # Remove duplicates
    
    def _validate_code(self, report: ValidationReport, task_description: str, 
                      result_data: Dict[str, Any], working_dir: str):
        """Validate code quality and syntax"""
        files_changed = result_data.get("files_changed", [])
        
        for file_path in files_changed:
            full_path = os.path.join(working_dir, file_path)
            if not os.path.exists(full_path):
                report.add_error(
                    code="FILE_NOT_FOUND",
                    message=f"File not found: {file_path}",
                    file_path=file_path
                )
                continue
            
            # Check file extension and validate accordingly
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.py':
                self._validate_python_file(report, full_path, file_path)
            elif file_ext in ['.js', '.jsx', '.ts', '.tsx']:
                self._validate_javascript_file(report, full_path, file_path)
            elif file_ext in ['.json']:
                self._validate_json_file(report, full_path, file_path)
            elif file_ext in ['.yaml', '.yml']:
                self._validate_yaml_file(report, full_path, file_path)
    
    def _validate_python_file(self, report: ValidationReport, full_path: str, file_path: str):
        """Validate Python file syntax and style"""
        try:
            # Check syntax
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic syntax check
            try:
                compile(content, full_path, 'exec')
            except SyntaxError as e:
                report.add_error(
                    code="PYTHON_SYNTAX_ERROR",
                    message=f"Python syntax error: {e.msg}",
                    file_path=file_path,
                    line_number=e.lineno
                )
                return
            
            # Check for common issues
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                # Check for TODO/FIXME comments
                if re.search(r'#.*\b(TODO|FIXME|XXX)\b', line, re.IGNORECASE):
                    report.add_warning(
                        code="TODO_COMMENT",
                        message=f"TODO/FIXME comment found: {line.strip()}",
                        file_path=file_path,
                        line_number=i
                    )
                
                # Check for print statements (potential debugging code)
                if re.search(r'\bprint\s*\(', line) and not re.search(r'#.*print', line):
                    report.add_warning(
                        code="PRINT_STATEMENT",
                        message=f"Print statement found (potential debugging code): {line.strip()}",
                        file_path=file_path,
                        line_number=i
                    )
        
        except Exception as e:
            report.add_error(
                code="PYTHON_VALIDATION_ERROR",
                message=f"Error validating Python file: {str(e)}",
                file_path=file_path
            )
    
    def _validate_javascript_file(self, report: ValidationReport, full_path: str, file_path: str):
        """Validate JavaScript/TypeScript file"""
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                # Check for console.log statements
                if re.search(r'\bconsole\.log\s*\(', line) and not re.search(r'//.*console\.log', line):
                    report.add_warning(
                        code="CONSOLE_LOG",
                        message=f"Console.log statement found: {line.strip()}",
                        file_path=file_path,
                        line_number=i
                    )
                
                # Check for TODO comments
                if re.search(r'//.*\b(TODO|FIXME|XXX)\b', line, re.IGNORECASE):
                    report.add_warning(
                        code="TODO_COMMENT",
                        message=f"TODO/FIXME comment found: {line.strip()}",
                        file_path=file_path,
                        line_number=i
                    )
        
        except Exception as e:
            report.add_error(
                code="JAVASCRIPT_VALIDATION_ERROR",
                message=f"Error validating JavaScript file: {str(e)}",
                file_path=file_path
            )
    
    def _validate_json_file(self, report: ValidationReport, full_path: str, file_path: str):
        """Validate JSON file syntax"""
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            report.add_error(
                code="JSON_SYNTAX_ERROR",
                message=f"JSON syntax error: {e.msg}",
                file_path=file_path,
                line_number=e.lineno
            )
        except Exception as e:
            report.add_error(
                code="JSON_VALIDATION_ERROR",
                message=f"Error validating JSON file: {str(e)}",
                file_path=file_path
            )
    
    def _validate_yaml_file(self, report: ValidationReport, full_path: str, file_path: str):
        """Validate YAML file syntax"""
        try:
            import yaml
            with open(full_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            report.add_error(
                code="YAML_SYNTAX_ERROR",
                message=f"YAML syntax error: {str(e)}",
                file_path=file_path
            )
        except ImportError:
            report.add_warning(
                code="YAML_VALIDATION_SKIPPED",
                message="YAML validation skipped: PyYAML not available",
                file_path=file_path
            )
        except Exception as e:
            report.add_error(
                code="YAML_VALIDATION_ERROR",
                message=f"Error validating YAML file: {str(e)}",
                file_path=file_path
            )
    
    def _validate_files(self, report: ValidationReport, task_description: str, 
                       result_data: Dict[str, Any], working_dir: str):
        """Validate file operations and changes"""
        files_changed = result_data.get("files_changed", [])
        files_created = result_data.get("files_created", [])
        
        # Check if files actually exist
        for file_path in files_changed + files_created:
            full_path = os.path.join(working_dir, file_path)
            if not os.path.exists(full_path):
                report.add_error(
                    code="FILE_NOT_FOUND",
                    message=f"File not found: {file_path}",
                    file_path=file_path
                )
            else:
                # Check file permissions
                if not os.access(full_path, os.R_OK):
                    report.add_error(
                        code="FILE_NOT_READABLE",
                        message=f"File not readable: {file_path}",
                        file_path=file_path
                    )
        
        # Check for empty files
        for file_path in files_created:
            full_path = os.path.join(working_dir, file_path)
            if os.path.exists(full_path) and os.path.getsize(full_path) == 0:
                report.add_warning(
                    code="EMPTY_FILE",
                    message=f"Empty file created: {file_path}",
                    file_path=file_path
                )
    
    def _validate_dependencies(self, report: ValidationReport, task_description: str, 
                             result_data: Dict[str, Any], working_dir: str):
        """Validate project dependencies"""
        # Check for package.json changes
        package_json_path = os.path.join(working_dir, "package.json")
        if os.path.exists(package_json_path):
            try:
                with open(package_json_path, 'r') as f:
                    package_data = json.load(f)
                
                # Check for development dependencies in production
                dev_deps = package_data.get("devDependencies", {})
                if dev_deps:
                    report.add_warning(
                        code="DEV_DEPENDENCIES_FOUND",
                        message=f"Development dependencies found: {list(dev_deps.keys())}",
                        file_path="package.json"
                    )
            except Exception as e:
                report.add_error(
                    code="PACKAGE_JSON_ERROR",
                    message=f"Error reading package.json: {str(e)}",
                    file_path="package.json"
                )
        
        # Check for requirements.txt changes
        requirements_path = os.path.join(working_dir, "requirements.txt")
        if os.path.exists(requirements_path):
            try:
                with open(requirements_path, 'r') as f:
                    requirements = f.read().strip()
                
                # Check for unpinned versions
                lines = requirements.split('\n')
                for i, line in enumerate(lines, 1):
                    if line.strip() and not re.search(r'[=<>]', line):
                        report.add_warning(
                            code="UNPINNED_DEPENDENCY",
                            message=f"Unpinned dependency: {line.strip()}",
                            file_path="requirements.txt",
                            line_number=i
                        )
            except Exception as e:
                report.add_error(
                    code="REQUIREMENTS_ERROR",
                    message=f"Error reading requirements.txt: {str(e)}",
                    file_path="requirements.txt"
                )
    
    def _validate_tests(self, report: ValidationReport, task_description: str, 
                       result_data: Dict[str, Any], working_dir: str):
        """Validate test files and coverage"""
        files_changed = result_data.get("files_changed", [])
        
        # Check for test files
        test_files = [f for f in files_changed if 'test' in f.lower() or f.endswith('_test.py')]
        
        if not test_files and "test" in task_description.lower():
            report.add_warning(
                code="NO_TEST_FILES",
                message="Task mentions testing but no test files found",
                details={"files_changed": files_changed}
            )
        
        # Validate test files
        for test_file in test_files:
            full_path = os.path.join(working_dir, test_file)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check for test functions
                    if test_file.endswith('.py'):
                        test_functions = re.findall(r'def test_\w+\(', content)
                        if not test_functions:
                            report.add_warning(
                                code="NO_TEST_FUNCTIONS",
                                message=f"No test functions found in {test_file}",
                                file_path=test_file
                            )
                
                except Exception as e:
                    report.add_error(
                        code="TEST_FILE_ERROR",
                        message=f"Error reading test file {test_file}: {str(e)}",
                        file_path=test_file
                    )
    
    def _validate_documentation(self, report: ValidationReport, task_description: str, 
                              result_data: Dict[str, Any], working_dir: str):
        """Validate documentation quality"""
        files_changed = result_data.get("files_changed", [])
        
        # Check for README files
        readme_files = [f for f in files_changed if f.lower().startswith('readme')]
        
        for readme_file in readme_files:
            full_path = os.path.join(working_dir, readme_file)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check for empty documentation
                    if len(content.strip()) < 50:
                        report.add_warning(
                            code="SHORT_DOCUMENTATION",
                            message=f"Documentation is very short: {readme_file}",
                            file_path=readme_file
                        )
                
                except Exception as e:
                    report.add_error(
                        code="DOCUMENTATION_ERROR",
                        message=f"Error reading documentation {readme_file}: {str(e)}",
                        file_path=readme_file
                    )
    
    def _validate_security(self, report: ValidationReport, task_description: str, 
                          result_data: Dict[str, Any], working_dir: str):
        """Validate security aspects"""
        files_changed = result_data.get("files_changed", [])
        
        # Check for potential security issues
        security_patterns = [
            (r'password\s*=\s*["\'][^"\']{1,20}["\']', "HARDCODED_PASSWORD"),
            (r'api_key\s*=\s*["\'][^"\']{1,50}["\']', "HARDCODED_API_KEY"),
            (r'secret\s*=\s*["\'][^"\']{1,50}["\']', "HARDCODED_SECRET"),
            (r'token\s*=\s*["\'][^"\']{1,50}["\']', "HARDCODED_TOKEN"),
            (r'exec\s*\(', "EXEC_USAGE"),
            (r'eval\s*\(', "EVAL_USAGE"),
            (r'shell\s*=\s*True', "SHELL_INJECTION_RISK")
        ]
        
        for file_path in files_changed:
            full_path = os.path.join(working_dir, file_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        for pattern, code in security_patterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                report.add_error(
                                    code=code,
                                    message=f"Security issue found: {line.strip()}",
                                    file_path=file_path,
                                    line_number=i
                                )
                
                except Exception as e:
                    report.add_error(
                        code="SECURITY_VALIDATION_ERROR",
                        message=f"Error during security validation: {str(e)}",
                        file_path=file_path
                    )
    
    def _validate_performance(self, report: ValidationReport, task_description: str, 
                            result_data: Dict[str, Any], working_dir: str):
        """Validate performance aspects"""
        files_changed = result_data.get("files_changed", [])
        
        # Check for potential performance issues
        performance_patterns = [
            (r'for\s+\w+\s+in\s+range\s*\(\s*len\s*\(', "INEFFICIENT_LOOP"),
            (r'\.append\s*\([^)]*\)\s*$', "LIST_APPEND_IN_LOOP"),
            (r'time\.sleep\s*\(\s*\d+\s*\)', "BLOCKING_SLEEP")
        ]
        
        for file_path in files_changed:
            if file_path.endswith('.py'):
                full_path = os.path.join(working_dir, file_path)
                if os.path.exists(full_path):
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        lines = content.split('\n')
                        for i, line in enumerate(lines, 1):
                            for pattern, code in performance_patterns:
                                if re.search(pattern, line):
                                    report.add_warning(
                                        code=code,
                                        message=f"Potential performance issue: {line.strip()}",
                                        file_path=file_path,
                                        line_number=i
                                    )
                    
                    except Exception as e:
                        report.add_error(
                            code="PERFORMANCE_VALIDATION_ERROR",
                            message=f"Error during performance validation: {str(e)}",
                            file_path=file_path
                        )
    
    def _validate_format(self, report: ValidationReport, task_description: str, 
                        result_data: Dict[str, Any], working_dir: str):
        """Validate file formatting and style"""
        files_changed = result_data.get("files_changed", [])
        
        for file_path in files_changed:
            full_path = os.path.join(working_dir, file_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check for trailing whitespace
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if line.rstrip() != line:
                            report.add_warning(
                                code="TRAILING_WHITESPACE",
                                message=f"Trailing whitespace found",
                                file_path=file_path,
                                line_number=i
                            )
                    
                    # Check for mixed line endings
                    if '\r\n' in content and '\n' in content:
                        report.add_warning(
                            code="MIXED_LINE_ENDINGS",
                            message="Mixed line endings found",
                            file_path=file_path
                        )
                
                except Exception as e:
                    report.add_error(
                        code="FORMAT_VALIDATION_ERROR",
                        message=f"Error during format validation: {str(e)}",
                        file_path=file_path
                    )


class ValidationReportManager:
    """Manages validation reports and provides analytics"""
    
    def __init__(self, storage_dir: str = ".taskmaster/validation_reports"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_report(self, report: ValidationReport) -> str:
        """Save validation report to file"""
        filename = f"validation_report_{report.task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.storage_dir / filename
        
        # Convert report to dictionary for JSON serialization
        report_dict = {
            "task_id": report.task_id,
            "task_title": report.task_title,
            "validation_level": report.validation_level.value,
            "overall_result": report.overall_result.value,
            "errors": [
                {
                    "code": error.code,
                    "message": error.message,
                    "severity": error.severity,
                    "file_path": error.file_path,
                    "line_number": error.line_number,
                    "details": error.details
                }
                for error in report.errors
            ],
            "warnings": [
                {
                    "code": warning.code,
                    "message": warning.message,
                    "severity": warning.severity,
                    "file_path": warning.file_path,
                    "line_number": warning.line_number,
                    "details": warning.details
                }
                for warning in report.warnings
            ],
            "checks_performed": report.checks_performed,
            "validation_time": report.validation_time.isoformat(),
            "metadata": report.metadata
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2)
        
        logger.info(f"Validation report saved: {filepath}")
        return str(filepath)
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validation reports"""
        reports = []
        
        for report_file in self.storage_dir.glob("validation_report_*.json"):
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                    reports.append(report_data)
            except Exception as e:
                logger.error(f"Error reading report {report_file}: {e}")
        
        if not reports:
            return {"total_reports": 0, "summary": "No validation reports found"}
        
        # Calculate summary statistics
        total_reports = len(reports)
        passed_reports = sum(1 for r in reports if r["overall_result"] == "passed")
        failed_reports = sum(1 for r in reports if r["overall_result"] == "failed")
        warning_reports = sum(1 for r in reports if r["overall_result"] == "warning")
        
        # Most common error codes
        error_codes = []
        for report in reports:
            error_codes.extend([error["code"] for error in report.get("errors", [])])
        
        from collections import Counter
        common_errors = Counter(error_codes).most_common(5)
        
        return {
            "total_reports": total_reports,
            "passed": passed_reports,
            "failed": failed_reports,
            "warnings": warning_reports,
            "success_rate": (passed_reports / total_reports * 100) if total_reports > 0 else 0,
            "common_errors": common_errors,
            "latest_reports": sorted(reports, key=lambda x: x["validation_time"], reverse=True)[:5]
        }