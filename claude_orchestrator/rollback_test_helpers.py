"""Test helpers for rollback functionality."""

import os
import json
import tempfile
import shutil
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from .rollback_manager import RollbackManager, CheckpointType, RollbackStrategy
from .task_master import TaskManager, Task, TaskStatus


class RollbackTestEnvironment:
    """Test environment for rollback testing."""
    
    def __init__(self):
        self.temp_dir = None
        self.rollback_manager = None
        self.task_manager = None
        self.test_files = {}
        self.original_state = {}
        
    def setup(self, 
              with_files: bool = True,
              with_tasks: bool = True,
              file_count: int = 5) -> Dict[str, Any]:
        """Set up test environment.
        
        Args:
            with_files: Create test files
            with_tasks: Create test tasks
            file_count: Number of test files to create
            
        Returns:
            Environment configuration
        """
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp(prefix="rollback_test_")
        
        # Initialize managers
        checkpoint_dir = os.path.join(self.temp_dir, ".checkpoints")
        self.rollback_manager = RollbackManager(checkpoint_dir=checkpoint_dir)
        
        if with_tasks:
            task_file = os.path.join(self.temp_dir, "tasks.json")
            self.task_manager = TaskManager(task_file=task_file)
        
        # Create test files
        if with_files:
            self._create_test_files(file_count)
        
        # Create test tasks
        if with_tasks:
            self._create_test_tasks()
        
        # Store original state
        self.original_state = self._capture_state()
        
        return {
            "temp_dir": self.temp_dir,
            "checkpoint_dir": checkpoint_dir,
            "test_files": self.test_files,
            "original_state": self.original_state
        }
    
    def teardown(self):
        """Clean up test environment."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        self.temp_dir = None
        self.rollback_manager = None
        self.task_manager = None
        self.test_files = {}
        self.original_state = {}
    
    def _create_test_files(self, count: int):
        """Create test files."""
        for i in range(count):
            filename = f"test_file_{i}.txt"
            filepath = os.path.join(self.temp_dir, filename)
            content = f"Original content of file {i}\nLine 2\nLine 3"
            
            with open(filepath, 'w') as f:
                f.write(content)
            
            self.test_files[filename] = {
                "path": filepath,
                "original_content": content
            }
    
    def _create_test_tasks(self):
        """Create test tasks."""
        tasks = [
            {
                "title": "Test Task 1",
                "description": "First test task",
                "status": "pending"
            },
            {
                "title": "Test Task 2", 
                "description": "Second test task",
                "status": "in_progress"
            },
            {
                "title": "Test Task 3",
                "description": "Third test task",
                "status": "completed"
            }
        ]
        
        for task_data in tasks:
            task = self.task_manager.create_task(
                title=task_data["title"],
                description=task_data["description"]
            )
            if task_data["status"] != "pending":
                self.task_manager.update_task_status(task.id, task_data["status"])
    
    def _capture_state(self) -> Dict[str, Any]:
        """Capture current state."""
        state = {
            "files": {},
            "tasks": []
        }
        
        # Capture file state
        for filename, file_info in self.test_files.items():
            if os.path.exists(file_info["path"]):
                with open(file_info["path"], 'r') as f:
                    state["files"][filename] = f.read()
        
        # Capture task state
        if self.task_manager:
            tasks = self.task_manager.list_tasks()
            state["tasks"] = [
                {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                    "description": task.description
                }
                for task in tasks
            ]
        
        return state
    
    def modify_files(self, modifications: Dict[str, str]):
        """Modify test files.
        
        Args:
            modifications: Dict of filename -> new content
        """
        for filename, new_content in modifications.items():
            if filename in self.test_files:
                with open(self.test_files[filename]["path"], 'w') as f:
                    f.write(new_content)
    
    def modify_tasks(self, modifications: List[Dict[str, Any]]):
        """Modify test tasks.
        
        Args:
            modifications: List of task modifications
        """
        if not self.task_manager:
            return
        
        for mod in modifications:
            task_id = mod.get("id")
            if "status" in mod:
                self.task_manager.update_task_status(task_id, mod["status"])
            if "title" in mod:
                task = self.task_manager.get_task(task_id)
                if task:
                    task.title = mod["title"]
                    self.task_manager._save_tasks()
    
    def create_checkpoint(self, 
                         checkpoint_type: CheckpointType = CheckpointType.MANUAL,
                         description: str = "Test checkpoint") -> str:
        """Create a checkpoint.
        
        Returns:
            Checkpoint ID
        """
        include_files = list(self.test_files.values())
        include_files = [f["path"] for f in include_files]
        
        return self.rollback_manager.create_checkpoint(
            checkpoint_type=checkpoint_type,
            description=description,
            include_files=include_files
        )
    
    def verify_state_matches(self, expected_state: Dict[str, Any]) -> Dict[str, Any]:
        """Verify current state matches expected state.
        
        Returns:
            Dict with verification results
        """
        current_state = self._capture_state()
        results = {
            "matches": True,
            "differences": {
                "files": {},
                "tasks": []
            }
        }
        
        # Check files
        for filename, expected_content in expected_state.get("files", {}).items():
            current_content = current_state["files"].get(filename)
            if current_content != expected_content:
                results["matches"] = False
                results["differences"]["files"][filename] = {
                    "expected": expected_content,
                    "actual": current_content
                }
        
        # Check tasks
        expected_tasks = {t["id"]: t for t in expected_state.get("tasks", [])}
        current_tasks = {t["id"]: t for t in current_state.get("tasks", [])}
        
        for task_id, expected_task in expected_tasks.items():
            current_task = current_tasks.get(task_id)
            if not current_task or current_task != expected_task:
                results["matches"] = False
                results["differences"]["tasks"].append({
                    "task_id": task_id,
                    "expected": expected_task,
                    "actual": current_task
                })
        
        return results


class RollbackScenarioTester:
    """Test various rollback scenarios."""
    
    def __init__(self):
        self.env = RollbackTestEnvironment()
        self.scenarios_run = []
        
    def run_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """Run a specific test scenario.
        
        Args:
            scenario_name: Name of scenario to run
            
        Returns:
            Test results
        """
        scenario_methods = {
            "simple_file_rollback": self._test_simple_file_rollback,
            "partial_rollback": self._test_partial_rollback,
            "selective_rollback": self._test_selective_rollback,
            "failed_task_rollback": self._test_failed_task_rollback,
            "multi_checkpoint_rollback": self._test_multi_checkpoint_rollback
        }
        
        if scenario_name not in scenario_methods:
            return {
                "success": False,
                "error": f"Unknown scenario: {scenario_name}"
            }
        
        # Set up environment
        self.env.setup()
        
        try:
            result = scenario_methods[scenario_name]()
            result["scenario"] = scenario_name
            self.scenarios_run.append(result)
            return result
        finally:
            self.env.teardown()
    
    def _test_simple_file_rollback(self) -> Dict[str, Any]:
        """Test simple file rollback."""
        # Create initial checkpoint
        checkpoint_id = self.env.create_checkpoint(description="Initial state")
        
        # Modify files
        self.env.modify_files({
            "test_file_0.txt": "Modified content for file 0",
            "test_file_1.txt": "Modified content for file 1"
        })
        
        # Rollback
        success = self.env.rollback_manager.rollback_to_checkpoint(
            checkpoint_id,
            strategy=RollbackStrategy.FULL
        )
        
        # Verify
        verification = self.env.verify_state_matches(self.env.original_state)
        
        return {
            "success": success and verification["matches"],
            "checkpoint_id": checkpoint_id,
            "verification": verification
        }
    
    def _test_partial_rollback(self) -> Dict[str, Any]:
        """Test partial rollback (tasks only)."""
        # Create checkpoint
        checkpoint_id = self.env.create_checkpoint(description="Before changes")
        
        # Modify both files and tasks
        self.env.modify_files({
            "test_file_0.txt": "Modified content"
        })
        
        tasks = self.env.task_manager.list_tasks()
        self.env.modify_tasks([
            {"id": tasks[0].id, "status": "completed"},
            {"id": tasks[1].id, "status": "failed"}
        ])
        
        # Partial rollback (tasks only)
        success = self.env.rollback_manager.rollback_to_checkpoint(
            checkpoint_id,
            strategy=RollbackStrategy.PARTIAL,
            include_files=False,
            include_tasks=True
        )
        
        # Verify tasks rolled back but files not
        current_state = self.env._capture_state()
        tasks_match = all(
            t["status"] == orig["status"] 
            for t, orig in zip(current_state["tasks"], self.env.original_state["tasks"])
        )
        files_modified = current_state["files"]["test_file_0.txt"] != self.env.original_state["files"]["test_file_0.txt"]
        
        return {
            "success": success and tasks_match and files_modified,
            "checkpoint_id": checkpoint_id,
            "tasks_rolled_back": tasks_match,
            "files_preserved": files_modified
        }
    
    def _test_selective_rollback(self) -> Dict[str, Any]:
        """Test selective file rollback."""
        # Create checkpoint
        checkpoint_id = self.env.create_checkpoint(description="Selective test")
        
        # Modify multiple files
        self.env.modify_files({
            "test_file_0.txt": "Modified 0",
            "test_file_1.txt": "Modified 1",
            "test_file_2.txt": "Modified 2"
        })
        
        # Selective rollback (only file 1)
        success = self.env.rollback_manager.rollback_to_checkpoint(
            checkpoint_id,
            strategy=RollbackStrategy.SELECTIVE,
            selected_files=[self.env.test_files["test_file_1.txt"]["path"]]
        )
        
        # Verify only file 1 rolled back
        current_state = self.env._capture_state()
        file_0_modified = current_state["files"]["test_file_0.txt"] == "Modified 0"
        file_1_original = current_state["files"]["test_file_1.txt"] == self.env.original_state["files"]["test_file_1.txt"]
        file_2_modified = current_state["files"]["test_file_2.txt"] == "Modified 2"
        
        return {
            "success": success and file_0_modified and file_1_original and file_2_modified,
            "checkpoint_id": checkpoint_id,
            "selective_success": file_1_original,
            "others_preserved": file_0_modified and file_2_modified
        }
    
    def _test_failed_task_rollback(self) -> Dict[str, Any]:
        """Test rollback after task failure."""
        # Create checkpoint before task
        checkpoint_id = self.env.create_checkpoint(description="Before task")
        
        # Simulate task execution with file changes
        self.env.modify_files({
            "test_file_0.txt": "Task in progress..."
        })
        
        # Mark task as failed
        tasks = self.env.task_manager.list_tasks()
        self.env.modify_tasks([
            {"id": tasks[0].id, "status": "failed"}
        ])
        
        # Rollback due to failure
        success = self.env.rollback_manager.rollback_to_checkpoint(
            checkpoint_id,
            strategy=RollbackStrategy.FULL
        )
        
        # Verify complete rollback
        verification = self.env.verify_state_matches(self.env.original_state)
        
        return {
            "success": success and verification["matches"],
            "checkpoint_id": checkpoint_id,
            "verification": verification
        }
    
    def _test_multi_checkpoint_rollback(self) -> Dict[str, Any]:
        """Test rollback through multiple checkpoints."""
        checkpoints = []
        
        # Create checkpoint 1
        cp1 = self.env.create_checkpoint(description="Checkpoint 1")
        checkpoints.append(cp1)
        
        # First modification
        self.env.modify_files({"test_file_0.txt": "After checkpoint 1"})
        
        # Create checkpoint 2
        cp2 = self.env.create_checkpoint(description="Checkpoint 2")
        checkpoints.append(cp2)
        
        # Second modification
        self.env.modify_files({"test_file_0.txt": "After checkpoint 2"})
        
        # Create checkpoint 3
        cp3 = self.env.create_checkpoint(description="Checkpoint 3")
        checkpoints.append(cp3)
        
        # Rollback to checkpoint 1 (skip 2 and 3)
        success = self.env.rollback_manager.rollback_to_checkpoint(
            cp1,
            strategy=RollbackStrategy.FULL
        )
        
        # Verify back to original state
        verification = self.env.verify_state_matches(self.env.original_state)
        
        # List checkpoints to verify history
        checkpoint_list = self.env.rollback_manager.list_checkpoints()
        
        return {
            "success": success and verification["matches"],
            "checkpoints_created": checkpoints,
            "rolled_back_to": cp1,
            "verification": verification,
            "checkpoint_count": len(checkpoint_list)
        }
    
    def run_all_scenarios(self) -> Dict[str, Any]:
        """Run all test scenarios.
        
        Returns:
            Summary of all test results
        """
        scenarios = [
            "simple_file_rollback",
            "partial_rollback",
            "selective_rollback", 
            "failed_task_rollback",
            "multi_checkpoint_rollback"
        ]
        
        results = {}
        for scenario in scenarios:
            results[scenario] = self.run_scenario(scenario)
        
        # Summary
        total = len(results)
        passed = sum(1 for r in results.values() if r.get("success", False))
        
        return {
            "total_scenarios": total,
            "passed": passed,
            "failed": total - passed,
            "results": results,
            "success_rate": passed / total if total > 0 else 0
        }


def create_rollback_test_suite() -> RollbackScenarioTester:
    """Create a rollback test suite instance.
    
    Returns:
        Configured test suite
    """
    return RollbackScenarioTester()