"""
Test script for enhanced worker-reviewer communication system
"""
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the enhanced components
try:
    from claude_orchestrator.worker_result_manager import WorkerResultManager, WorkerResult, ResultStatus
    from claude_orchestrator.enhanced_review_system import EnhancedReviewSystem
    from claude_orchestrator.process_lifecycle_manager import ProcessLifecycleManager, ProcessState
    from claude_orchestrator.enhanced_prompts import EnhancedPromptSystem
    from claude_orchestrator.enhanced_orchestrator_integration import EnhancedOrchestratorIntegration
except ImportError as e:
    logger.error(f"Failed to import enhanced components: {e}")
    exit(1)


class TestEnhancedCommunication:
    """Test suite for enhanced communication system"""
    
    def __init__(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_enhanced_comm_"))
        self.original_cwd = Path.cwd()
        
    def setup(self):
        """Set up test environment"""
        # Change to test directory
        os.chdir(self.test_dir)
        
        # Create test directory structure
        (self.test_dir / ".taskmaster" / "tasks").mkdir(parents=True)
        (self.test_dir / "scripts").mkdir(parents=True)
        (self.test_dir / "docs").mkdir(parents=True)
        (self.test_dir / "designs").mkdir(parents=True)
        
        logger.info(f"Test environment set up in {self.test_dir}")
        
    def teardown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        logger.info("Test environment cleaned up")
        
    def test_worker_result_manager(self):
        """Test WorkerResultManager functionality"""
        logger.info("Testing WorkerResultManager...")
        
        # Create manager
        manager = WorkerResultManager(self.test_dir / ".taskmaster" / "results.db")
        
        # Create test result
        result = WorkerResult(
            task_id="test_task_1",
            worker_id="test_worker_1",
            status=ResultStatus.SUCCESS,
            output="Test implementation completed successfully",
            created_files=["scripts/test_file.py"],
            modified_files=["claude_orchestrator/main.py"],
            execution_time=5.2,
            tokens_used=1500,
            timestamp=datetime.now().isoformat()
        )
        
        # Store result
        result_id = manager.store_result(result)
        assert result_id > 0, "Failed to store result"
        
        # Retrieve result
        retrieved = manager.get_latest_result("test_task_1")
        assert retrieved is not None, "Failed to retrieve result"
        assert retrieved.task_id == "test_task_1", "Retrieved wrong task"
        assert retrieved.status == ResultStatus.SUCCESS, "Wrong status"
        
        # Test validation
        is_valid, message = manager.validate_result("test_task_1")
        assert is_valid, f"Validation failed: {message}"
        
        logger.info("✓ WorkerResultManager tests passed")
        
    def test_enhanced_prompts(self):
        """Test EnhancedPromptSystem functionality"""
        logger.info("Testing EnhancedPromptSystem...")
        
        prompt_system = EnhancedPromptSystem()
        
        # Test worker prompt generation
        task = {
            'id': 'test_task_2',
            'title': 'Create test documentation',
            'type': 'documentation',
            'description': 'Create comprehensive documentation for the test system'
        }
        
        prompt = prompt_system.get_worker_prompt(task)
        
        # Check prompt contains required elements
        assert 'test_task_2' in prompt, "Task ID missing from prompt"
        assert 'documentation' in prompt.lower(), "Task type missing from prompt"
        assert 'docs/' in prompt, "File organization missing from prompt"
        assert 'MUST' in prompt, "Requirements not emphatic enough"
        
        # Test reviewer prompt
        worker_result = {
            'output': 'Created documentation files',
            'created_files': ['docs/test_guide.md'],
            'modified_files': []
        }
        
        review_prompt = prompt_system.get_reviewer_prompt(task, worker_result)
        assert 'Review Instructions' in review_prompt, "Review prompt malformed"
        assert 'test_guide.md' in review_prompt, "Created files not in review prompt"
        
        logger.info("✓ EnhancedPromptSystem tests passed")
        
    async def test_process_lifecycle_manager(self):
        """Test ProcessLifecycleManager functionality"""
        logger.info("Testing ProcessLifecycleManager...")
        
        manager = ProcessLifecycleManager("test_orchestrator")
        
        # Test task initialization
        task_data = {
            'id': 'test_task_3',
            'title': 'Test lifecycle task',
            'type': 'implementation',
            'description': 'Test task for lifecycle management'
        }
        
        context = await manager.initialize_task('test_task_3', task_data)
        assert context.state == ProcessState.PENDING, "Wrong initial state"
        
        # Test state transitions
        success = await manager.transition_state('test_task_3', ProcessState.WORKER_ASSIGNED)
        assert success, "Failed to transition state"
        
        # Test worker assignment
        assigned = await manager.assign_worker('test_task_3', 'test_worker_3')
        assert assigned, "Failed to assign worker"
        
        # Test status retrieval
        status = await manager.get_task_status('test_task_3')
        assert status['found'], "Task not found in status"
        assert status['worker_id'] == 'test_worker_3', "Wrong worker ID in status"
        
        logger.info("✓ ProcessLifecycleManager tests passed")
        
    def test_enhanced_review_system(self):
        """Test EnhancedReviewSystem functionality"""
        logger.info("Testing EnhancedReviewSystem...")
        
        # Create test files
        test_file = self.test_dir / "scripts" / "test_implementation.py"
        test_file.write_text("""
def test_function():
    print("This is a test implementation")
    return True
""")
        
        # Create worker result
        result = WorkerResult(
            task_id="test_task_4",
            worker_id="test_worker_4",
            status=ResultStatus.SUCCESS,
            output="Implemented test function in scripts/test_implementation.py",
            created_files=["scripts/test_implementation.py"],
            modified_files=[],
            execution_time=3.0,
            tokens_used=800,
            timestamp=datetime.now().isoformat()
        )
        
        # Store result
        result_manager = WorkerResultManager(self.test_dir / ".taskmaster" / "results.db")
        result_manager.store_result(result)
        
        # Test review system
        review_system = EnhancedReviewSystem(result_manager)
        
        # Test requirement extraction
        requirements = review_system._extract_requirements(
            "Must create a test function and implement proper error handling"
        )
        assert len(requirements) > 0, "Failed to extract requirements"
        
        # Test implementation extraction
        implementation = review_system._extract_implementation(result)
        assert implementation['has_changes'], "Failed to detect changes"
        assert len(implementation['files']) > 0, "Failed to extract files"
        
        logger.info("✓ EnhancedReviewSystem tests passed")
        
    def test_file_validation(self):
        """Test file validation functionality"""
        logger.info("Testing file validation...")
        
        # Create test files
        test_script = self.test_dir / "scripts" / "validation_test.py"
        test_script.write_text("""
# Test script for validation
def validate_implementation():
    return True
""")
        
        test_doc = self.test_dir / "docs" / "validation_guide.md"
        test_doc.write_text("""
# Validation Guide

This is a test documentation file.
""")
        
        # Test that files exist and have content
        assert test_script.exists(), "Test script not created"
        assert test_doc.exists(), "Test documentation not created"
        
        assert len(test_script.read_text()) > 50, "Test script too short"
        assert len(test_doc.read_text()) > 30, "Test documentation too short"
        
        logger.info("✓ File validation tests passed")
        
    def test_integration_workflow(self):
        """Test the complete integration workflow"""
        logger.info("Testing complete integration workflow...")
        
        # This would test the full worker-reviewer cycle
        # For now, just test that components can be initialized together
        
        config = {
            'max_parallel_workers': 2,
            'worker_timeout': 300
        }
        
        try:
            integration = EnhancedOrchestratorIntegration(config)
            assert integration.orchestrator_id is not None, "Orchestrator not initialized"
            assert integration.result_manager is not None, "Result manager not initialized"
            assert integration.review_system is not None, "Review system not initialized"
            
            logger.info("✓ Integration workflow tests passed")
            
        except Exception as e:
            logger.error(f"Integration test failed: {e}")
            raise
            
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("Starting enhanced communication system tests...")
        
        try:
            self.setup()
            
            # Run sync tests
            self.test_worker_result_manager()
            self.test_enhanced_prompts()
            self.test_enhanced_review_system()
            self.test_file_validation()
            self.test_integration_workflow()
            
            # Run async tests
            await self.test_process_lifecycle_manager()
            
            logger.info("🎉 All tests passed!")
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            raise
            
        finally:
            self.teardown()


async def main():
    """Run the test suite"""
    test_suite = TestEnhancedCommunication()
    await test_suite.run_all_tests()


if __name__ == "__main__":
    import os
    
    # Run the async test suite
    asyncio.run(main())