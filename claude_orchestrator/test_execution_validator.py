"""Test Execution Validator for preventing false positive test results.

This module validates test execution results to ensure tests actually ran
and results are accurate.
"""

import re
import logging
import os
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TestExecutionStatus(Enum):
    """Status of test execution validation."""
    VALID = "valid"                    # Tests ran and results are valid
    NO_TESTS_FOUND = "no_tests_found" # No test files found
    NO_TESTS_RAN = "no_tests_ran"     # Test files exist but no tests ran
    INVALID_OUTPUT = "invalid_output"  # Output doesn't match test execution
    SUSPICIOUS = "suspicious"          # Results seem suspicious
    ERROR = "error"                    # Error during validation


@dataclass
class TestExecutionResult:
    """Result of test execution validation."""
    status: TestExecutionStatus
    tests_found: int = 0
    tests_ran: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    test_files: List[str] = field(default_factory=list)
    suspicious_indicators: List[str] = field(default_factory=list)
    confidence: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class TestOutputPatterns:
    """Patterns for identifying test execution output."""
    
    def __init__(self):
        # Pytest patterns
        self.pytest_patterns = {
            'collected': re.compile(r'collected\s+(\d+)\s+item', re.IGNORECASE),
            'passed': re.compile(r'(\d+)\s+passed', re.IGNORECASE),
            'failed': re.compile(r'(\d+)\s+failed', re.IGNORECASE),
            'skipped': re.compile(r'(\d+)\s+skipped', re.IGNORECASE),
            'error': re.compile(r'(\d+)\s+error', re.IGNORECASE),
            'test_session': re.compile(r'=+\s*test session starts\s*=+', re.IGNORECASE),
            'summary': re.compile(r'=+.*?(failed|passed|error)', re.IGNORECASE),
            'no_tests': re.compile(r'no tests ran|collected 0 items', re.IGNORECASE)
        }
        
        # Unittest patterns
        self.unittest_patterns = {
            'ran': re.compile(r'Ran\s+(\d+)\s+test', re.IGNORECASE),
            'ok': re.compile(r'^OK$', re.MULTILINE),
            'failed': re.compile(r'FAILED\s*\(.*?failures=(\d+)', re.IGNORECASE),
            'errors': re.compile(r'errors=(\d+)', re.IGNORECASE),
            'test_result': re.compile(r'\.+|F+|E+|S+', re.MULTILINE)
        }
        
        # Generic test patterns
        self.generic_patterns = {
            'test_file': re.compile(r'test_\w+\.py|tests/.*\.py', re.IGNORECASE),
            'test_function': re.compile(r'def\s+test_\w+|class\s+Test\w+', re.IGNORECASE),
            'assertion': re.compile(r'assert\s+|self\.assert|expect\(', re.IGNORECASE),
            'test_framework': re.compile(r'pytest|unittest|nose|behave', re.IGNORECASE)
        }
        
        # False positive indicators
        self.false_positive_patterns = {
            'no_output': re.compile(r'^\s*$'),
            'generic_success': re.compile(r'^(success|done|completed|ok)$', re.IGNORECASE | re.MULTILINE),
            'no_test_keywords': re.compile(r'test|spec|assert|expect', re.IGNORECASE),
            'file_not_found': re.compile(r'(file not found|no such file|cannot find)', re.IGNORECASE),
            'import_error': re.compile(r'(ImportError|ModuleNotFoundError)', re.IGNORECASE)
        }


class TestExecutionValidator:
    """Validates test execution results to prevent false positives."""
    
    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.patterns = TestOutputPatterns()
        self.validation_history: List[TestExecutionResult] = []
    
    def validate_test_execution(self, 
                              output: str,
                              task_context: Optional[Dict[str, Any]] = None,
                              expected_test_files: Optional[List[str]] = None) -> TestExecutionResult:
        """Validate test execution output.
        
        Args:
            output: Test execution output
            task_context: Task context (title, description, etc.)
            expected_test_files: Expected test files if known
            
        Returns:
            Test execution validation result
        """
        result = TestExecutionResult(status=TestExecutionStatus.VALID)
        
        # Check if output is empty or too generic
        if not output or not output.strip():
            result.status = TestExecutionStatus.NO_TESTS_RAN
            result.suspicious_indicators.append("Empty output")
            result.confidence = 0.0
            return result
        
        # Check for false positive patterns
        false_positives = self._check_false_positives(output)
        if false_positives:
            result.suspicious_indicators.extend(false_positives)
        
        # Try to parse test execution results
        pytest_result = self._parse_pytest_output(output)
        unittest_result = self._parse_unittest_output(output)
        
        # Determine which parser found results
        if pytest_result['found']:
            result.tests_ran = pytest_result['tests_ran']
            result.tests_passed = pytest_result['tests_passed']
            result.tests_failed = pytest_result['tests_failed']
            result.details['framework'] = 'pytest'
        elif unittest_result['found']:
            result.tests_ran = unittest_result['tests_ran']
            result.tests_passed = unittest_result['tests_passed']
            result.tests_failed = unittest_result['tests_failed']
            result.details['framework'] = 'unittest'
        else:
            # No test framework output detected
            result.status = TestExecutionStatus.INVALID_OUTPUT
            result.suspicious_indicators.append("No test framework output detected")
        
        # Check for test files
        if expected_test_files:
            result.test_files = expected_test_files
            result.tests_found = len(expected_test_files)
        else:
            # Try to find test files in output
            test_files = self._extract_test_files_from_output(output)
            result.test_files = test_files
            result.tests_found = len(test_files)
        
        # Validate results
        validation_status = self._validate_results(result, output, task_context)
        result.status = validation_status
        
        # Calculate confidence score
        result.confidence = self._calculate_confidence(result)
        
        # Store in history
        self.validation_history.append(result)
        
        return result
    
    def _check_false_positives(self, output: str) -> List[str]:
        """Check for false positive indicators.
        
        Args:
            output: Test output
            
        Returns:
            List of suspicious indicators
        """
        indicators = []
        
        # Check if output is too short
        if len(output) < 50:
            indicators.append("Output too short for real test execution")
        
        # Check for generic success messages without test details
        if (self.patterns.false_positive_patterns['generic_success'].search(output) and
            not self.patterns.false_positive_patterns['no_test_keywords'].search(output)):
            indicators.append("Generic success message without test keywords")
        
        # Check for file not found errors
        if self.patterns.false_positive_patterns['file_not_found'].search(output):
            indicators.append("File not found errors in output")
        
        # Check for import errors
        if self.patterns.false_positive_patterns['import_error'].search(output):
            indicators.append("Import errors in output")
        
        return indicators
    
    def _parse_pytest_output(self, output: str) -> Dict[str, Any]:
        """Parse pytest output.
        
        Args:
            output: Test output
            
        Returns:
            Parsed results
        """
        result = {
            'found': False,
            'tests_ran': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'tests_skipped': 0
        }
        
        # Check for pytest session
        if self.patterns.pytest_patterns['test_session'].search(output):
            result['found'] = True
            
            # Extract collected tests
            collected_match = self.patterns.pytest_patterns['collected'].search(output)
            if collected_match:
                result['tests_ran'] = int(collected_match.group(1))
            
            # Extract passed tests
            passed_match = self.patterns.pytest_patterns['passed'].search(output)
            if passed_match:
                result['tests_passed'] = int(passed_match.group(1))
            
            # Extract failed tests
            failed_match = self.patterns.pytest_patterns['failed'].search(output)
            if failed_match:
                result['tests_failed'] = int(failed_match.group(1))
            
            # Check for no tests ran
            if self.patterns.pytest_patterns['no_tests'].search(output):
                result['tests_ran'] = 0
        
        return result
    
    def _parse_unittest_output(self, output: str) -> Dict[str, Any]:
        """Parse unittest output.
        
        Args:
            output: Test output
            
        Returns:
            Parsed results
        """
        result = {
            'found': False,
            'tests_ran': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'tests_errors': 0
        }
        
        # Check for unittest output
        ran_match = self.patterns.unittest_patterns['ran'].search(output)
        if ran_match:
            result['found'] = True
            result['tests_ran'] = int(ran_match.group(1))
            
            # Check if all passed
            if self.patterns.unittest_patterns['ok'].search(output):
                result['tests_passed'] = result['tests_ran']
            else:
                # Extract failures
                failed_match = self.patterns.unittest_patterns['failed'].search(output)
                if failed_match:
                    result['tests_failed'] = int(failed_match.group(1))
                
                # Extract errors
                errors_match = self.patterns.unittest_patterns['errors'].search(output)
                if errors_match:
                    result['tests_errors'] = int(errors_match.group(1))
                
                # Calculate passed
                result['tests_passed'] = result['tests_ran'] - result['tests_failed'] - result['tests_errors']
        
        return result
    
    def _extract_test_files_from_output(self, output: str) -> List[str]:
        """Extract test file names from output.
        
        Args:
            output: Test output
            
        Returns:
            List of test files
        """
        test_files = []
        
        # Find test file references
        for match in self.patterns.generic_patterns['test_file'].finditer(output):
            file_path = match.group(0)
            if file_path not in test_files:
                test_files.append(file_path)
        
        return test_files
    
    def _validate_results(self, 
                         result: TestExecutionResult,
                         output: str,
                         task_context: Optional[Dict[str, Any]]) -> TestExecutionStatus:
        """Validate the test execution results.
        
        Args:
            result: Current result
            output: Test output
            task_context: Task context
            
        Returns:
            Validation status
        """
        # No tests ran but claims success
        if result.tests_ran == 0 and result.tests_found == 0:
            if task_context:
                task_title = task_context.get('title', '').lower()
                task_desc = task_context.get('description', '').lower()
                
                # Check if task was about creating tests
                if any(word in task_title + task_desc for word in ['create test', 'write test', 'add test']):
                    result.suspicious_indicators.append("Task was to create tests but no tests found")
                    return TestExecutionStatus.NO_TESTS_FOUND
            
            return TestExecutionStatus.NO_TESTS_RAN
        
        # Tests found but none ran
        if result.tests_found > 0 and result.tests_ran == 0:
            result.suspicious_indicators.append("Test files found but no tests executed")
            return TestExecutionStatus.NO_TESTS_RAN
        
        # Suspicious patterns
        if len(result.suspicious_indicators) >= 2:
            return TestExecutionStatus.SUSPICIOUS
        
        # Output doesn't match test execution
        if result.tests_ran == 0 and len(output) > 100:
            # Check if output contains test-like content
            if not any(pattern.search(output) for pattern in [
                self.patterns.pytest_patterns['test_session'],
                self.patterns.unittest_patterns['ran'],
                self.patterns.generic_patterns['test_framework']
            ]):
                return TestExecutionStatus.INVALID_OUTPUT
        
        return TestExecutionStatus.VALID
    
    def _calculate_confidence(self, result: TestExecutionResult) -> float:
        """Calculate confidence score for the validation.
        
        Args:
            result: Validation result
            
        Returns:
            Confidence score (0.0-1.0)
        """
        confidence = 1.0
        
        # Reduce confidence for suspicious indicators
        confidence -= len(result.suspicious_indicators) * 0.2
        
        # Reduce confidence for invalid status
        status_penalties = {
            TestExecutionStatus.VALID: 0.0,
            TestExecutionStatus.NO_TESTS_FOUND: 0.5,
            TestExecutionStatus.NO_TESTS_RAN: 0.5,
            TestExecutionStatus.INVALID_OUTPUT: 0.7,
            TestExecutionStatus.SUSPICIOUS: 0.8,
            TestExecutionStatus.ERROR: 0.9
        }
        
        confidence -= status_penalties.get(result.status, 0.5)
        
        # Boost confidence if tests actually ran
        if result.tests_ran > 0:
            confidence += 0.3
        
        # Boost confidence if framework was detected
        if result.details.get('framework'):
            confidence += 0.2
        
        return max(0.0, min(1.0, confidence))
    
    def check_test_files_exist(self, test_dir: str = "tests") -> Tuple[bool, List[str]]:
        """Check if test files actually exist.
        
        Args:
            test_dir: Test directory
            
        Returns:
            Tuple of (tests_exist, test_file_list)
        """
        test_path = self.working_dir / test_dir
        test_files = []
        
        if test_path.exists():
            # Find all test files
            for pattern in ['test_*.py', '*_test.py']:
                test_files.extend([str(f.relative_to(self.working_dir)) 
                                 for f in test_path.glob(pattern)])
        
        # Also check root directory
        for pattern in ['test_*.py', '*_test.py']:
            test_files.extend([str(f.relative_to(self.working_dir)) 
                             for f in self.working_dir.glob(pattern)])
        
        return len(test_files) > 0, test_files
    
    def generate_validation_report(self, result: TestExecutionResult) -> str:
        """Generate a validation report.
        
        Args:
            result: Validation result
            
        Returns:
            Formatted report
        """
        lines = []
        lines.append("TEST EXECUTION VALIDATION REPORT")
        lines.append("=" * 40)
        lines.append(f"Status: {result.status.value}")
        lines.append(f"Confidence: {result.confidence:.1%}")
        lines.append(f"Tests Found: {result.tests_found}")
        lines.append(f"Tests Ran: {result.tests_ran}")
        lines.append(f"Tests Passed: {result.tests_passed}")
        lines.append(f"Tests Failed: {result.tests_failed}")
        
        if result.test_files:
            lines.append("\nTest Files:")
            for file in result.test_files:
                lines.append(f"  - {file}")
        
        if result.suspicious_indicators:
            lines.append("\nSuspicious Indicators:")
            for indicator in result.suspicious_indicators:
                lines.append(f"  - {indicator}")
        
        if result.details:
            lines.append("\nDetails:")
            for key, value in result.details.items():
                lines.append(f"  {key}: {value}")
        
        lines.append("=" * 40)
        
        return "\n".join(lines)


# Integration helper
class TestValidationIntegration:
    """Integrates test validation with workers."""
    
    def __init__(self, working_dir: Optional[str] = None):
        self.validator = TestExecutionValidator(working_dir)
        self.validation_enabled = True
        
    def validate_worker_test_result(self,
                                  worker_id: int,
                                  task: Any,
                                  output: str) -> Tuple[bool, TestExecutionResult]:
        """Validate worker test execution result.
        
        Args:
            worker_id: Worker ID
            task: Task being executed
            output: Task output
            
        Returns:
            Tuple of (is_valid, validation_result)
        """
        if not self.validation_enabled:
            return True, None
        
        # Check if this is a test-related task
        task_title = getattr(task, 'title', '').lower()
        task_desc = getattr(task, 'description', '').lower()
        
        is_test_task = any(word in task_title + task_desc for word in [
            'test', 'pytest', 'unittest', 'spec', 'verify'
        ])
        
        if not is_test_task:
            return True, None  # Not a test task, no validation needed
        
        # Check if task claims to run tests
        claims_test_execution = any(phrase in output.lower() for phrase in [
            'tests passed', 'test execution', 'ran test', 'test result',
            'all tests passed', 'test successful'
        ])
        
        if not claims_test_execution:
            return True, None  # Doesn't claim test execution
        
        # Validate the test execution
        task_context = {
            'title': task_title,
            'description': task_desc,
            'worker_id': worker_id
        }
        
        result = self.validator.validate_test_execution(output, task_context)
        
        # Log validation result
        if result.status != TestExecutionStatus.VALID:
            logger.warning(
                f"Worker {worker_id} test validation failed: {result.status.value}\n"
                f"Confidence: {result.confidence:.1%}\n"
                f"Suspicious indicators: {', '.join(result.suspicious_indicators)}"
            )
            
            # Generate detailed report for debugging
            report = self.validator.generate_validation_report(result)
            logger.debug(f"Validation report:\n{report}")
        
        # Determine if valid
        is_valid = (result.status == TestExecutionStatus.VALID and 
                   result.confidence > 0.5)
        
        return is_valid, result


def integrate_test_validation(orchestrator) -> TestValidationIntegration:
    """Integrate test validation with orchestrator.
    
    Args:
        orchestrator: Orchestrator instance
        
    Returns:
        Test validation integration
    """
    integration = TestValidationIntegration(orchestrator.working_dir)
    
    # Patch worker process_task method
    if hasattr(orchestrator, 'workers'):
        for worker in orchestrator.workers:
            if hasattr(worker, 'process_task'):
                original_process = worker.process_task
                
                def validated_process(task, original=original_process, worker=worker):
                    # Process task normally
                    result = original(task)
                    
                    # Validate if successful
                    if result.status == TaskStatus.COMPLETED and result.result:
                        is_valid, validation = integration.validate_worker_test_result(
                            worker.worker_id,
                            task,
                            result.result
                        )
                        
                        if not is_valid:
                            # Mark as suspicious
                            result.status_message = (
                                f"WARNING: Test execution validation failed - "
                                f"{validation.status.value} (confidence: {validation.confidence:.1%})"
                            )
                            
                            # Add validation details to result
                            if not hasattr(result, 'validation'):
                                result.validation = validation
                    
                    return result
                
                worker.process_task = validated_process
    
    # Store reference in orchestrator
    orchestrator.test_validator = integration
    
    logger.info("Test execution validator integrated with orchestrator")
    
    return integration