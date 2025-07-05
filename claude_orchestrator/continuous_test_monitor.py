"""Continuous test monitoring for Claude Orchestrator"""

import os
import sys
import time
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Test execution status"""
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"
    RUNNING = "running"
    PENDING = "pending"


@dataclass
class TestResult:
    """Result of a test execution"""
    test_name: str
    test_file: str
    status: TestStatus
    duration: float
    error_message: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TestSuite:
    """Collection of test results"""
    suite_name: str
    test_results: List[TestResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    @property
    def duration(self) -> float:
        """Total duration of test suite"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def passed_count(self) -> int:
        """Number of passed tests"""
        return sum(1 for r in self.test_results if r.status == TestStatus.PASSED)
    
    @property
    def failed_count(self) -> int:
        """Number of failed tests"""
        return sum(1 for r in self.test_results if r.status == TestStatus.FAILED)
    
    @property
    def error_count(self) -> int:
        """Number of tests with errors"""
        return sum(1 for r in self.test_results if r.status == TestStatus.ERROR)
    
    @property
    def success_rate(self) -> float:
        """Percentage of successful tests"""
        total = len(self.test_results)
        if total == 0:
            return 0.0
        return (self.passed_count / total) * 100


class ContinuousTestMonitor:
    """Monitors and runs tests continuously without file watching"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize test monitor
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.test_dir = Path(self.config.get('test_dir', 'tests'))
        self.result_dir = Path(self.config.get('result_dir', '.test_results'))
        self.result_dir.mkdir(parents=True, exist_ok=True)
        
        self.watch_patterns = self.config.get('watch_patterns', ['test_*.py', '*_test.py'])
        self.check_interval = self.config.get('check_interval', 60)  # seconds
        self.periodic_full_run = self.config.get('periodic_full_run_hours', 1)
        
        self.test_suites: Dict[str, TestSuite] = {}
        self.running = False
        self._stop_event = threading.Event()
        self._monitor_thread = None
        
        # Track file modifications
        self._file_mtimes: Dict[str, float] = {}
        
        # Callbacks
        self.on_test_complete: Optional[Callable[[TestResult], None]] = None
        self.on_suite_complete: Optional[Callable[[TestSuite], None]] = None
        
    def start(self):
        """Start continuous test monitoring"""
        if self.running:
            logger.warning("Test monitor already running")
            return
            
        self.running = True
        self._stop_event.clear()
        
        # Start periodic test runner
        self._monitor_thread = threading.Thread(target=self._monitor_loop)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        
        logger.info("Continuous test monitoring started")
        
    def stop(self):
        """Stop continuous test monitoring"""
        if not self.running:
            return
            
        self.running = False
        self._stop_event.set()
            
        # Stop monitor thread
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            
        logger.info("Continuous test monitoring stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop"""
        last_full_run = datetime.now()
        last_file_check = datetime.now()
        
        while not self._stop_event.is_set():
            try:
                current_time = datetime.now()
                
                # Check for file changes every 10 seconds
                if self.config.get('run_on_file_change', True) and \
                   (current_time - last_file_check).total_seconds() > 10:
                    self._check_file_changes()
                    last_file_check = current_time
                
                # Check if we should run full test suite
                if (current_time - last_full_run).total_seconds() > self.periodic_full_run * 3600:
                    logger.info("Running periodic full test suite")
                    self.run_all_tests()
                    last_full_run = current_time
                
                # Wait for next check
                self._stop_event.wait(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                
    def _check_file_changes(self):
        """Check for modified test files"""
        for pattern in self.watch_patterns:
            for test_file in self.test_dir.rglob(pattern):
                try:
                    mtime = test_file.stat().st_mtime
                    last_mtime = self._file_mtimes.get(str(test_file), 0)
                    
                    if mtime > last_mtime:
                        self._file_mtimes[str(test_file)] = mtime
                        if last_mtime > 0:  # Skip initial scan
                            logger.info(f"Test file modified: {test_file}")
                            self.run_test_file(str(test_file))
                except Exception as e:
                    logger.debug(f"Failed to check file {test_file}: {e}")
                    
    def run_all_tests(self) -> TestSuite:
        """Run all tests in test directory"""
        suite_name = f"full_suite_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        suite = TestSuite(suite_name=suite_name)
        
        # Find all test files
        test_files = []
        for pattern in self.watch_patterns:
            test_files.extend(self.test_dir.rglob(pattern))
            
        logger.info(f"Found {len(test_files)} test files")
        
        # Run each test file
        for test_file in test_files:
            results = self._run_pytest(str(test_file))
            suite.test_results.extend(results)
            
        suite.end_time = datetime.now()
        
        # Save results
        self._save_suite_results(suite)
        
        # Trigger callback
        if self.on_suite_complete:
            self.on_suite_complete(suite)
            
        self.test_suites[suite_name] = suite
        
        logger.info(f"Test suite completed: {suite.passed_count} passed, "
                   f"{suite.failed_count} failed, {suite.error_count} errors")
        
        return suite
        
    def run_test_file(self, file_path: str) -> List[TestResult]:
        """Run a specific test file"""
        logger.info(f"Running test file: {file_path}")
        
        results = self._run_pytest(file_path)
        
        # Trigger callbacks
        for result in results:
            if self.on_test_complete:
                self.on_test_complete(result)
                
        # Save individual results
        self._save_test_results(results)
        
        return results
        
    def _run_pytest(self, test_path: str) -> List[TestResult]:
        """Run pytest on a file and parse results"""
        results = []
        
        try:
            # Run pytest with simple output
            cmd = [
                sys.executable, "-m", "pytest",
                test_path,
                "--tb=short",
                "-v"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            # Parse output
            results = self._parse_pytest_output(result.stdout + result.stderr, test_path)
                
        except subprocess.TimeoutExpired:
            logger.error(f"Test timeout: {test_path}")
            results.append(TestResult(
                test_name=Path(test_path).name,
                test_file=test_path,
                status=TestStatus.ERROR,
                duration=300.0,
                error_message="Test execution timeout"
            ))
        except Exception as e:
            logger.error(f"Failed to run tests: {e}")
            results.append(TestResult(
                test_name=Path(test_path).name,
                test_file=test_path,
                status=TestStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            ))
            
        return results
        
    def _parse_pytest_output(self, output: str, test_path: str) -> List[TestResult]:
        """Parse pytest text output"""
        results = []
        
        # Simple parsing - look for test results
        lines = output.split('\n')
        current_test = None
        
        for line in lines:
            # Look for test result lines
            if '::' in line and any(status in line for status in ['PASSED', 'FAILED', 'ERROR', 'SKIPPED']):
                parts = line.strip().split()
                if len(parts) >= 2:
                    # Extract test name and status
                    test_spec = parts[0]
                    status_str = parts[1]
                    
                    # Parse test name from full spec
                    if '::' in test_spec:
                        test_name = test_spec.split('::')[-1]
                    else:
                        test_name = test_spec
                    
                    # Determine status
                    status = TestStatus.PASSED
                    if 'FAILED' in status_str:
                        status = TestStatus.FAILED
                    elif 'ERROR' in status_str:
                        status = TestStatus.ERROR
                    elif 'SKIPPED' in status_str:
                        status = TestStatus.SKIPPED
                        
                    # Extract duration if present
                    duration = 0.0
                    for part in parts[2:]:
                        if 's]' in part:
                            try:
                                duration = float(part.replace('[', '').replace('s]', ''))
                            except:
                                pass
                                
                    result = TestResult(
                        test_name=test_name,
                        test_file=test_path,
                        status=status,
                        duration=duration
                    )
                    results.append(result)
                    
        # If no results parsed, check summary
        if not results:
            if 'passed' in output.lower() and 'failed' not in output.lower():
                status = TestStatus.PASSED
            elif 'failed' in output.lower():
                status = TestStatus.FAILED
            else:
                status = TestStatus.ERROR
                
            results.append(TestResult(
                test_name=Path(test_path).stem,
                test_file=test_path,
                status=status,
                duration=0.0,
                stdout=output
            ))
            
        return results
        
    def _save_suite_results(self, suite: TestSuite):
        """Save test suite results to file"""
        file_path = self.result_dir / f"{suite.suite_name}.json"
        
        data = {
            'suite_name': suite.suite_name,
            'start_time': suite.start_time.isoformat(),
            'end_time': suite.end_time.isoformat() if suite.end_time else None,
            'duration': suite.duration,
            'passed_count': suite.passed_count,
            'failed_count': suite.failed_count,
            'error_count': suite.error_count,
            'success_rate': suite.success_rate,
            'test_results': [
                {
                    'test_name': r.test_name,
                    'test_file': r.test_file,
                    'status': r.status.value,
                    'duration': r.duration,
                    'error_message': r.error_message,
                    'timestamp': r.timestamp.isoformat()
                }
                for r in suite.test_results
            ]
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
            
    def _save_test_results(self, results: List[TestResult]):
        """Save individual test results"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = self.result_dir / f"test_run_{timestamp}.json"
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'results': [
                {
                    'test_name': r.test_name,
                    'test_file': r.test_file,
                    'status': r.status.value,
                    'duration': r.duration,
                    'error_message': r.error_message
                }
                for r in results
            ]
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
            
    def get_test_history(self, test_name: str, limit: int = 10) -> List[TestResult]:
        """Get history of test results"""
        history = []
        
        # Search through saved results
        result_files = sorted(self.result_dir.glob("*.json"), reverse=True)
        
        for file_path in result_files[:limit * 10]:  # Check more files
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    
                # Check suite results
                if 'test_results' in data:
                    for result_data in data['test_results']:
                        if result_data['test_name'] == test_name:
                            result = TestResult(
                                test_name=result_data['test_name'],
                                test_file=result_data['test_file'],
                                status=TestStatus(result_data['status']),
                                duration=result_data['duration'],
                                error_message=result_data.get('error_message'),
                                timestamp=datetime.fromisoformat(result_data['timestamp'])
                            )
                            history.append(result)
                            
                # Check individual results
                elif 'results' in data:
                    for result_data in data['results']:
                        if result_data['test_name'] == test_name:
                            result = TestResult(
                                test_name=result_data['test_name'],
                                test_file=result_data['test_file'],
                                status=TestStatus(result_data['status']),
                                duration=result_data['duration'],
                                error_message=result_data.get('error_message'),
                                timestamp=datetime.fromisoformat(data['timestamp'])
                            )
                            history.append(result)
                            
                if len(history) >= limit:
                    break
                    
            except Exception as e:
                logger.debug(f"Failed to read result file {file_path}: {e}")
                
        return history[:limit]
        
    def get_test_statistics(self) -> Dict[str, Any]:
        """Get overall test statistics"""
        stats = {
            'total_suites': len(self.test_suites),
            'total_tests_run': 0,
            'total_passed': 0,
            'total_failed': 0,
            'total_errors': 0,
            'average_success_rate': 0.0,
            'last_run': None
        }
        
        if self.test_suites:
            for suite in self.test_suites.values():
                stats['total_tests_run'] += len(suite.test_results)
                stats['total_passed'] += suite.passed_count
                stats['total_failed'] += suite.failed_count
                stats['total_errors'] += suite.error_count
                
            stats['average_success_rate'] = (
                (stats['total_passed'] / stats['total_tests_run'] * 100)
                if stats['total_tests_run'] > 0 else 0.0
            )
            
            # Find most recent suite
            latest_suite = max(self.test_suites.values(), key=lambda s: s.start_time)
            stats['last_run'] = latest_suite.start_time.isoformat()
            
        return stats


# Singleton instance
_monitor_instance: Optional[ContinuousTestMonitor] = None


def get_test_monitor(config: Optional[Dict[str, Any]] = None) -> ContinuousTestMonitor:
    """Get or create the test monitor instance"""
    global _monitor_instance
    
    if _monitor_instance is None:
        _monitor_instance = ContinuousTestMonitor(config)
        
    return _monitor_instance