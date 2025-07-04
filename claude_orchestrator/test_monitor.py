"""Continuous test monitoring system for tracking test execution and results."""

import os
import json
import logging
import subprocess
import threading
import time
from typing import Dict, List, Any, Optional, Callable, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Test execution status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    RUNNING = "running"
    PENDING = "pending"


@dataclass
class TestResult:
    """Individual test result."""
    test_name: str
    test_file: str
    status: TestStatus
    duration: float
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    traceback: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_name": self.test_name,
            "test_file": self.test_file,
            "status": self.status.value,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
            "traceback": self.traceback
        }


@dataclass
class TestSuite:
    """Test suite information."""
    name: str
    test_files: List[str]
    last_run: Optional[datetime] = None
    last_status: Optional[TestStatus] = None
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    average_duration: float = 0.0
    
    def update_stats(self, results: List[TestResult]):
        """Update suite statistics from test results."""
        self.last_run = datetime.now()
        self.total_tests = len(results)
        self.passed_tests = sum(1 for r in results if r.status == TestStatus.PASSED)
        self.failed_tests = sum(1 for r in results if r.status == TestStatus.FAILED)
        
        if results:
            total_duration = sum(r.duration for r in results)
            self.average_duration = total_duration / len(results)
            
            # Overall status
            if self.failed_tests > 0:
                self.last_status = TestStatus.FAILED
            elif self.passed_tests == self.total_tests:
                self.last_status = TestStatus.PASSED
            else:
                self.last_status = TestStatus.ERROR


class TestMonitor:
    """Monitors test execution and tracks results over time."""
    
    def __init__(self,
                 test_dir: str = "tests",
                 result_dir: str = ".test_results",
                 watch_patterns: Optional[List[str]] = None):
        self.test_dir = test_dir
        self.result_dir = result_dir
        self.watch_patterns = watch_patterns or ["*.py"]
        
        # Create result directory
        os.makedirs(result_dir, exist_ok=True)
        
        # Test suites and results
        self.test_suites: Dict[str, TestSuite] = {}
        self.test_results: List[TestResult] = []
        self.file_hashes: Dict[str, str] = {}
        
        # Monitoring state
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable] = []
        
        # Load previous results
        self._load_results()
        
        logger.info(f"Test monitor initialized for {test_dir}")
    
    def _load_results(self):
        """Load previous test results."""
        result_file = os.path.join(self.result_dir, "test_history.json")
        if os.path.exists(result_file):
            try:
                with open(result_file, 'r') as f:
                    data = json.load(f)
                    
                # Load test results
                for result_data in data.get("results", []):
                    result = TestResult(
                        test_name=result_data["test_name"],
                        test_file=result_data["test_file"],
                        status=TestStatus(result_data["status"]),
                        duration=result_data["duration"],
                        timestamp=datetime.fromisoformat(result_data["timestamp"]),
                        error_message=result_data.get("error_message"),
                        traceback=result_data.get("traceback")
                    )
                    self.test_results.append(result)
                
                logger.info(f"Loaded {len(self.test_results)} historical test results")
                
            except Exception as e:
                logger.error(f"Failed to load test history: {e}")
    
    def _save_results(self):
        """Save test results to disk."""
        result_file = os.path.join(self.result_dir, "test_history.json")
        
        # Keep only recent results (last 7 days)
        cutoff = datetime.now() - timedelta(days=7)
        recent_results = [r for r in self.test_results if r.timestamp > cutoff]
        
        data = {
            "last_updated": datetime.now().isoformat(),
            "results": [r.to_dict() for r in recent_results[-1000:]]  # Keep last 1000
        }
        
        try:
            with open(result_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save test history: {e}")
    
    def discover_tests(self) -> Dict[str, List[str]]:
        """Discover test files in the test directory.
        
        Returns:
            Dict mapping test suite names to test file paths
        """
        test_files = {}
        
        if not os.path.exists(self.test_dir):
            logger.warning(f"Test directory {self.test_dir} does not exist")
            return test_files
        
        # Find all test files
        for pattern in self.watch_patterns:
            for root, dirs, files in os.walk(self.test_dir):
                for file in files:
                    if file.startswith("test_") and file.endswith(".py"):
                        file_path = os.path.join(root, file)
                        suite_name = os.path.relpath(root, self.test_dir)
                        
                        if suite_name not in test_files:
                            test_files[suite_name] = []
                        
                        test_files[suite_name].append(file_path)
        
        # Update test suites
        for suite_name, files in test_files.items():
            if suite_name not in self.test_suites:
                self.test_suites[suite_name] = TestSuite(
                    name=suite_name,
                    test_files=files
                )
            else:
                self.test_suites[suite_name].test_files = files
        
        return test_files
    
    def run_tests(self, 
                  suite_name: Optional[str] = None,
                  test_file: Optional[str] = None) -> List[TestResult]:
        """Run tests and collect results.
        
        Args:
            suite_name: Specific suite to run (all if None)
            test_file: Specific test file to run
            
        Returns:
            List of test results
        """
        results = []
        
        # Determine what to run
        if test_file:
            files_to_run = [test_file]
        elif suite_name and suite_name in self.test_suites:
            files_to_run = self.test_suites[suite_name].test_files
        else:
            # Run all tests
            files_to_run = []
            for suite in self.test_suites.values():
                files_to_run.extend(suite.test_files)
        
        # Run pytest with JSON output
        for test_file in files_to_run:
            if not os.path.exists(test_file):
                continue
            
            # Create temporary result file
            temp_result = os.path.join(self.result_dir, f"temp_{os.getpid()}.json")
            
            try:
                # Run pytest
                cmd = [
                    "python", "-m", "pytest",
                    test_file,
                    "--json-report",
                    f"--json-report-file={temp_result}",
                    "-v"
                ]
                
                start_time = time.time()
                result = subprocess.run(cmd, capture_output=True, text=True)
                duration = time.time() - start_time
                
                # Parse results
                if os.path.exists(temp_result):
                    with open(temp_result, 'r') as f:
                        pytest_data = json.load(f)
                    
                    # Extract test results
                    for test in pytest_data.get("tests", []):
                        status = TestStatus.PASSED
                        if test["outcome"] == "failed":
                            status = TestStatus.FAILED
                        elif test["outcome"] == "skipped":
                            status = TestStatus.SKIPPED
                        elif test["outcome"] == "error":
                            status = TestStatus.ERROR
                        
                        test_result = TestResult(
                            test_name=test["nodeid"],
                            test_file=test_file,
                            status=status,
                            duration=test.get("duration", 0),
                            error_message=test.get("call", {}).get("longrepr")
                        )
                        
                        results.append(test_result)
                        self.test_results.append(test_result)
                    
                    # Clean up
                    os.remove(temp_result)
                else:
                    # Fallback parsing from output
                    if result.returncode == 0:
                        # Tests passed
                        test_result = TestResult(
                            test_name=os.path.basename(test_file),
                            test_file=test_file,
                            status=TestStatus.PASSED,
                            duration=duration
                        )
                    else:
                        # Tests failed
                        test_result = TestResult(
                            test_name=os.path.basename(test_file),
                            test_file=test_file,
                            status=TestStatus.FAILED,
                            duration=duration,
                            error_message=result.stderr or result.stdout
                        )
                    
                    results.append(test_result)
                    self.test_results.append(test_result)
                
            except Exception as e:
                logger.error(f"Failed to run tests in {test_file}: {e}")
                
                # Record error
                test_result = TestResult(
                    test_name=os.path.basename(test_file),
                    test_file=test_file,
                    status=TestStatus.ERROR,
                    duration=0,
                    error_message=str(e)
                )
                results.append(test_result)
                self.test_results.append(test_result)
        
        # Update suite statistics
        for suite in self.test_suites.values():
            suite_results = [r for r in results if r.test_file in suite.test_files]
            if suite_results:
                suite.update_stats(suite_results)
        
        # Save results
        self._save_results()
        
        # Notify callbacks
        self._notify_callbacks(results)
        
        return results
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate hash of a file."""
        hasher = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                hasher.update(f.read())
            return hasher.hexdigest()
        except Exception:
            return ""
    
    def _check_file_changes(self) -> Set[str]:
        """Check for changed files.
        
        Returns:
            Set of changed file paths
        """
        changed_files = set()
        
        # Check test files
        for suite in self.test_suites.values():
            for test_file in suite.test_files:
                if os.path.exists(test_file):
                    current_hash = self._calculate_file_hash(test_file)
                    
                    if test_file not in self.file_hashes:
                        self.file_hashes[test_file] = current_hash
                        changed_files.add(test_file)
                    elif self.file_hashes[test_file] != current_hash:
                        self.file_hashes[test_file] = current_hash
                        changed_files.add(test_file)
        
        # Also check source files that tests might depend on
        source_dir = os.path.dirname(self.test_dir)
        for root, dirs, files in os.walk(source_dir):
            # Skip test directory
            if root.startswith(self.test_dir):
                continue
            
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    current_hash = self._calculate_file_hash(file_path)
                    
                    if file_path not in self.file_hashes:
                        self.file_hashes[file_path] = current_hash
                    elif self.file_hashes[file_path] != current_hash:
                        self.file_hashes[file_path] = current_hash
                        # Source file changed, mark all tests as potentially affected
                        changed_files.update(
                            f for suite in self.test_suites.values() 
                            for f in suite.test_files
                        )
        
        return changed_files
    
    def start_monitoring(self, interval: int = 60):
        """Start continuous monitoring of tests.
        
        Args:
            interval: Check interval in seconds
        """
        if self._monitoring:
            logger.warning("Test monitoring already active")
            return
        
        self._monitoring = True
        
        def monitor_loop():
            """Main monitoring loop."""
            # Initial discovery
            self.discover_tests()
            
            while self._monitoring:
                try:
                    # Check for file changes
                    changed_files = self._check_file_changes()
                    
                    if changed_files:
                        logger.info(f"Detected changes in {len(changed_files)} files")
                        
                        # Run tests for changed files
                        for test_file in changed_files:
                            if test_file.startswith(self.test_dir):
                                self.run_tests(test_file=test_file)
                    
                    # Periodic full test run (every hour)
                    last_full_run = max(
                        (s.last_run for s in self.test_suites.values() if s.last_run),
                        default=datetime.min
                    )
                    
                    if datetime.now() - last_full_run > timedelta(hours=1):
                        logger.info("Running periodic full test suite")
                        self.run_tests()
                    
                    # Sleep
                    time.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Error in test monitoring loop: {e}")
                    time.sleep(10)
        
        self._monitor_thread = threading.Thread(
            target=monitor_loop,
            daemon=True,
            name="TestMonitor"
        )
        self._monitor_thread.start()
        logger.info(f"Started test monitoring with {interval}s interval")
    
    def stop_monitoring(self):
        """Stop continuous monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Stopped test monitoring")
    
    def add_callback(self, callback: Callable[[List[TestResult]], None]):
        """Add a callback for test results.
        
        Args:
            callback: Function to call with test results
        """
        self._callbacks.append(callback)
    
    def _notify_callbacks(self, results: List[TestResult]):
        """Notify all callbacks with test results."""
        for callback in self._callbacks:
            try:
                callback(results)
            except Exception as e:
                logger.error(f"Error in test result callback: {e}")
    
    def get_test_summary(self) -> Dict[str, Any]:
        """Get summary of test results.
        
        Returns:
            Test summary statistics
        """
        summary = {
            "total_suites": len(self.test_suites),
            "total_test_files": sum(len(s.test_files) for s in self.test_suites.values()),
            "recent_results": len(self.test_results),
            "suites": {}
        }
        
        # Suite summaries
        for suite_name, suite in self.test_suites.items():
            summary["suites"][suite_name] = {
                "test_files": len(suite.test_files),
                "last_run": suite.last_run.isoformat() if suite.last_run else None,
                "last_status": suite.last_status.value if suite.last_status else None,
                "total_tests": suite.total_tests,
                "passed_tests": suite.passed_tests,
                "failed_tests": suite.failed_tests,
                "average_duration": suite.average_duration
            }
        
        # Recent test statistics
        if self.test_results:
            recent_cutoff = datetime.now() - timedelta(hours=24)
            recent_results = [r for r in self.test_results if r.timestamp > recent_cutoff]
            
            if recent_results:
                summary["last_24h"] = {
                    "total_runs": len(recent_results),
                    "passed": sum(1 for r in recent_results if r.status == TestStatus.PASSED),
                    "failed": sum(1 for r in recent_results if r.status == TestStatus.FAILED),
                    "error": sum(1 for r in recent_results if r.status == TestStatus.ERROR),
                    "average_duration": sum(r.duration for r in recent_results) / len(recent_results)
                }
        
        return summary
    
    def get_failing_tests(self) -> List[TestResult]:
        """Get list of currently failing tests.
        
        Returns:
            List of failing test results
        """
        # Get most recent result for each test
        latest_results = {}
        for result in self.test_results:
            key = (result.test_name, result.test_file)
            if key not in latest_results or result.timestamp > latest_results[key].timestamp:
                latest_results[key] = result
        
        # Filter failing tests
        failing = [
            r for r in latest_results.values()
            if r.status in [TestStatus.FAILED, TestStatus.ERROR]
        ]
        
        return sorted(failing, key=lambda x: x.timestamp, reverse=True)
    
    def generate_test_report(self, output_file: Optional[str] = None) -> str:
        """Generate a test report.
        
        Args:
            output_file: Optional file to save report to
            
        Returns:
            Report content
        """
        lines = []
        lines.append("=" * 80)
        lines.append("TEST MONITORING REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Summary
        summary = self.get_test_summary()
        lines.append(f"Total Test Suites: {summary['total_suites']}")
        lines.append(f"Total Test Files: {summary['total_test_files']}")
        lines.append("")
        
        # Suite details
        lines.append("TEST SUITES")
        lines.append("-" * 40)
        
        for suite_name, suite_data in summary["suites"].items():
            status_icon = "✅" if suite_data["last_status"] == "passed" else "❌"
            lines.append(f"\n{status_icon} {suite_name}")
            lines.append(f"  Files: {suite_data['test_files']}")
            
            if suite_data["last_run"]:
                lines.append(f"  Last Run: {suite_data['last_run']}")
                lines.append(f"  Tests: {suite_data['passed_tests']}/{suite_data['total_tests']} passed")
                lines.append(f"  Avg Duration: {suite_data['average_duration']:.2f}s")
        
        # Recent activity
        if "last_24h" in summary:
            lines.append("\n\nLAST 24 HOURS")
            lines.append("-" * 40)
            stats = summary["last_24h"]
            lines.append(f"Total Runs: {stats['total_runs']}")
            lines.append(f"Passed: {stats['passed']} ({stats['passed']/stats['total_runs']*100:.1f}%)")
            lines.append(f"Failed: {stats['failed']}")
            lines.append(f"Errors: {stats['error']}")
            lines.append(f"Avg Duration: {stats['average_duration']:.2f}s")
        
        # Failing tests
        failing_tests = self.get_failing_tests()
        if failing_tests:
            lines.append("\n\nFAILING TESTS")
            lines.append("-" * 40)
            
            for test in failing_tests[:10]:  # Show top 10
                lines.append(f"\n❌ {test.test_name}")
                lines.append(f"  File: {test.test_file}")
                lines.append(f"  Failed: {test.timestamp.strftime('%Y-%m-%d %H:%M')}")
                if test.error_message:
                    error_preview = test.error_message[:100]
                    if len(test.error_message) > 100:
                        error_preview += "..."
                    lines.append(f"  Error: {error_preview}")
        
        lines.append("\n" + "=" * 80)
        
        report = "\n".join(lines)
        
        # Save if requested
        if output_file:
            try:
                with open(output_file, 'w') as f:
                    f.write(report)
                logger.info(f"Test report saved to {output_file}")
            except Exception as e:
                logger.error(f"Failed to save test report: {e}")
        
        return report


# Integration with main orchestrator
class TestMonitorIntegration:
    """Integrates test monitoring with the orchestrator."""
    
    def __init__(self, orchestrator, test_monitor: TestMonitor):
        self.orchestrator = orchestrator
        self.test_monitor = test_monitor
        
        # Register callback
        self.test_monitor.add_callback(self._on_test_results)
    
    def _on_test_results(self, results: List[TestResult]):
        """Handle test results."""
        # Check for failures
        failures = [r for r in results if r.status == TestStatus.FAILED]
        
        if failures and hasattr(self.orchestrator, 'rollback_manager'):
            # Consider creating a checkpoint before risky changes
            logger.warning(f"Test failures detected: {len(failures)} tests failed")
            
            # Could trigger rollback or other actions
            for failure in failures:
                logger.error(f"Test failed: {failure.test_name} - {failure.error_message}")


# Create global test monitor instance
test_monitor = TestMonitor()