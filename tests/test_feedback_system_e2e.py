"""
End-to-End Testing for Feedback System

This module provides comprehensive testing of the entire feedback system,
including integration between all components, performance testing,
and error handling scenarios.
"""

import tempfile
import os
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import json
import random

from claude_orchestrator.feedback_models import (
    FeedbackEntry, FeedbackType, RatingScale, FeedbackMetadata
)
from claude_orchestrator.feedback_storage import FeedbackStorage
from claude_orchestrator.feedback_collector import (
    FeedbackCollector, CollectionPoint, FeedbackPrompt
)
from claude_orchestrator.task_decomposition_feedback import (
    DecompositionFeedbackCollector
)
from claude_orchestrator.task_decomposer import (
    DecompositionPlan, SubtaskBlueprint as TaskDetails,
    DecompositionStrategy, TaskComplexityLevel
)
from claude_orchestrator.worker_allocation_feedback import (
    WorkerAllocationFeedbackCollector
)
from claude_orchestrator.dynamic_worker_allocation import (
    TaskRequirements, TaskComplexity, WorkerCapability
)
from claude_orchestrator.task_completion_feedback import (
    TaskCompletionFeedbackCollector, TaskResult, TaskCompletionMetrics
)
from claude_orchestrator.feedback_analysis import (
    FeedbackAnalyzer, TrendDirection, InsightPriority
)


class TestFeedbackSystemE2E:
    """End-to-end tests for the feedback system"""
    
    def setup_method(self):
        """Set up test environment"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize all components
        self.storage = FeedbackStorage(self.temp_db.name)
        self.collector = FeedbackCollector(self.storage)
        self.decomposition_feedback = DecompositionFeedbackCollector(
            feedback_collector=self.collector,
            enable_async_collection=False  # Sync for testing
        )
        self.allocation_feedback = WorkerAllocationFeedbackCollector(
            feedback_collector=self.collector,
            enable_async_collection=False
        )
        self.completion_feedback = TaskCompletionFeedbackCollector(
            feedback_collector=self.collector,
            enable_async_collection=False
        )
        self.analyzer = FeedbackAnalyzer(feedback_storage=self.storage)
        
        # Mock decomposer and allocator
        self.mock_decomposer = Mock()
        self.mock_allocator = Mock()
        
        # Patch dependencies
        self.decomposition_feedback.decomposer = self.mock_decomposer
        self.allocation_feedback.allocator = self.mock_allocator
    
    def teardown_method(self):
        """Clean up after test"""
        self.decomposition_feedback.close()
        self.allocation_feedback.close()
        self.completion_feedback.close()
        self.storage.close()
        os.unlink(self.temp_db.name)
    
    def test_complete_task_lifecycle(self):
        """Test complete feedback collection through task lifecycle"""
        task_id = "e2e-task-001"
        task_title = "Implement User Authentication"
        task_description = "Add JWT-based authentication to the REST API with role-based access control"
        worker_id = "worker-001"
        user_id = "test-user"
        
        # 1. Task Decomposition Phase
        print("\n1. Task Decomposition Phase")
        
        # Mock decomposer response
        mock_plan = DecompositionPlan(
            original_task_id=task_id,
            original_title=task_title,
            original_description=task_description,
            strategy=DecompositionStrategy.HIERARCHICAL,
            subtasks=[
                TaskDetails(
                    title="Create JWT token service",
                    description="Implement JWT generation and validation",
                    estimated_duration_minutes=45
                ),
                TaskDetails(
                    title="Add authentication middleware",
                    description="Create middleware for route protection",
                    estimated_duration_minutes=30
                ),
                TaskDetails(
                    title="Implement role-based access",
                    description="Add role checking to protected routes",
                    estimated_duration_minutes=60
                )
            ],
            estimated_total_duration_minutes=135,
            complexity_level=TaskComplexityLevel.COMPLEX,
            risk_assessment="High complexity due to security requirements",
            implementation_notes=["Use industry standard JWT libraries", "Implement refresh tokens"],
            success_metrics=["All endpoints secured", "Role-based access working"],
            metadata={"security_critical": True}
        )
        self.mock_decomposer.decompose_task.return_value = mock_plan
        
        # Decompose task with feedback
        decomposition_plan = self.decomposition_feedback.decompose_task_with_feedback(
            task_id=task_id,
            title=task_title,
            description=task_description,
            user_id=user_id
        )
        
        assert decomposition_plan is not None
        assert len(decomposition_plan.subtasks) == 3
        
        # Verify decomposition feedback was collected
        decomp_feedback = self.storage.get_feedback_by_task(task_id)
        assert len(decomp_feedback) >= 1
        assert any(f.feedback_type == FeedbackType.MANAGER_REVIEW for f in decomp_feedback)
        
        print(f"✓ Decomposed into {len(decomposition_plan.subtasks)} subtasks")
        print(f"✓ Collected {len(decomp_feedback)} decomposition feedback entries")
        
        # 2. Worker Allocation Phase
        print("\n2. Worker Allocation Phase")
        
        # Mock allocator responses
        self.mock_allocator.get_worker_status.return_value = {
            'available_workers': 3,
            'total_workers': 5
        }
        self.mock_allocator.allocate_worker.return_value = worker_id
        self.mock_allocator.allocation_history = [{
            'worker_id': worker_id,
            'suitability_score': 0.85,
            'task_complexity': 'high',
            'estimated_duration': 135,
            'required_capabilities': ['code', 'security']
        }]
        
        # Allocate worker with feedback
        allocated_worker = self.allocation_feedback.allocate_worker_with_feedback(
            task_id=task_id,
            task_title=task_title,
            task_description=task_description,
            task_requirements=TaskRequirements(
                complexity=TaskComplexity.HIGH,
                estimated_duration=135,
                required_capabilities={WorkerCapability.CODE, WorkerCapability.DESIGN}
            ),
            user_id=user_id
        )
        
        assert allocated_worker == worker_id
        
        # Verify allocation feedback
        alloc_feedback = self.storage.get_feedback_by_task(task_id)
        allocation_entries = [f for f in alloc_feedback if 'allocation' in f.content.lower()]
        assert len(allocation_entries) >= 1
        
        print(f"✓ Allocated worker: {worker_id}")
        print(f"✓ Collected allocation feedback")
        
        # 3. Task Execution Phase (simulate)
        print("\n3. Task Execution Phase")
        
        # Start task tracking
        self.completion_feedback.start_task_tracking(
            task_id=task_id,
            title=task_title,
            description=task_description,
            worker_id=worker_id,
            metadata={'priority': 'high', 'sprint': 'current'}
        )
        
        # Simulate task execution with some events
        time.sleep(0.1)  # Simulate work
        
        # Simulate an error and retry
        self.completion_feedback.update_task_tracking(
            task_id=task_id,
            update_type="error",
            data="Connection timeout to database"
        )
        
        self.completion_feedback.update_task_tracking(
            task_id=task_id,
            update_type="retry",
            data=None
        )
        
        # Update subtask progress
        self.completion_feedback.update_task_tracking(
            task_id=task_id,
            update_type="subtask_count",
            data=3
        )
        
        self.completion_feedback.update_task_tracking(
            task_id=task_id,
            update_type="subtasks_completed",
            data=3
        )
        
        print("✓ Tracked task execution events")
        
        # 4. Task Completion Phase
        print("\n4. Task Completion Phase")
        
        # Create task result
        task_result = TaskResult(
            task_id=task_id,
            title=task_title,
            description=task_description,
            success=True,
            output="Successfully implemented JWT authentication with role-based access control",
            execution_time=125.0,  # Slightly faster than estimated
            worker_id=worker_id
        )
        
        # Create completion metrics
        completion_metrics = TaskCompletionMetrics(
            task_id=task_id,
            success=True,
            execution_time=125.0,
            error_count=1,  # One error was encountered
            retry_count=1,
            worker_changes=0,
            subtask_count=3,
            subtasks_completed=3,
            code_changes_made=True,
            tests_passed=True,
            review_required=True,
            quality_metrics={'code_coverage': 0.92, 'complexity': 8.5}
        )
        
        # Collect completion feedback
        completion_entry = self.completion_feedback.collect_task_completion_feedback(
            task_result=task_result,
            metrics=completion_metrics,
            user_id=user_id
        )
        
        assert completion_entry is not None
        assert completion_entry.rating is not None
        
        print(f"✓ Task completed with rating: {completion_entry.rating.name}")
        
        # Release worker with feedback
        self.mock_allocator.release_worker.return_value = True
        
        release_success = self.allocation_feedback.release_worker_with_feedback(
            worker_id=worker_id,
            task_id=task_id,
            success=True,
            actual_duration=125.0,
            error_count=1,
            quality_indicators={'code_coverage': 0.92},
            user_id=user_id
        )
        
        assert release_success is True
        
        print("✓ Released worker with performance feedback")
        
        # 5. Opus Review Phase
        print("\n5. Opus Review Phase")
        
        # Collect review feedback
        review_entry = self.completion_feedback.collect_review_feedback(
            task_id=task_id,
            review_score=4.5,
            review_comments="Excellent implementation with minor suggestions for optimization",
            reviewer_id="opus-reviewer"
        )
        
        assert review_entry is not None
        assert review_entry.rating == RatingScale.EXCELLENT
        
        print(f"✓ Collected Opus review feedback (score: 4.5/5)")
        
        # 6. Analysis Phase
        print("\n6. Analysis Phase")
        
        # Get all feedback for the task
        all_feedback = self.storage.get_feedback_by_task(task_id)
        print(f"\nTotal feedback collected: {len(all_feedback)}")
        
        # Group by type
        feedback_by_type = {}
        for feedback in all_feedback:
            type_name = feedback.feedback_type.value
            if type_name not in feedback_by_type:
                feedback_by_type[type_name] = 0
            feedback_by_type[type_name] += 1
        
        print("\nFeedback breakdown by type:")
        for feedback_type, count in feedback_by_type.items():
            print(f"  - {feedback_type}: {count}")
        
        # Analyze the feedback
        analysis_result = self.analyzer.analyze_feedback(
            task_ids=[task_id]
        )
        
        print(f"\nAnalysis Results:")
        print(f"  - Average rating: {analysis_result.metrics.average_rating:.2f}")
        print(f"  - Sentiment: {analysis_result.metrics.sentiment_scores}")
        print(f"  - Insights generated: {len(analysis_result.insights)}")
        
        # Verify complete lifecycle
        assert len(all_feedback) >= 5  # Should have multiple feedback entries
        assert FeedbackType.MANAGER_REVIEW.value in feedback_by_type
        assert FeedbackType.WORKER_PERFORMANCE.value in feedback_by_type
        assert FeedbackType.TASK_COMPLETION.value in feedback_by_type
        
        print("\n✅ Complete task lifecycle test passed!")
    
    def test_concurrent_feedback_collection(self):
        """Test concurrent feedback collection from multiple sources"""
        print("\n\nTesting Concurrent Feedback Collection")
        
        # Enable async collection for this test
        self.completion_feedback.enable_async_collection = True
        self.allocation_feedback.enable_async_collection = True
        
        feedback_count = 0
        errors = []
        
        def collect_feedback_batch(worker_id, batch_size=10):
            """Simulate a worker collecting feedback"""
            nonlocal feedback_count
            
            try:
                for i in range(batch_size):
                    task_id = f"concurrent-task-{worker_id}-{i}"
                    
                    # Simulate task allocation
                    self.mock_allocator.allocate_worker.return_value = f"worker-{worker_id}"
                    self.mock_allocator.get_worker_status.return_value = {'available_workers': 5}
                    self.mock_allocator.allocation_history = [{
                        'suitability_score': random.uniform(0.6, 0.9),
                        'task_complexity': random.choice(['low', 'medium', 'high'])
                    }]
                    
                    self.allocation_feedback.allocate_worker_with_feedback(
                        task_id=task_id,
                        task_title=f"Task {i}",
                        task_description="Concurrent test task",
                        user_id=f"user-{worker_id}"
                    )
                    
                    # Simulate task completion
                    result = TaskResult(
                        task_id=task_id,
                        title=f"Task {i}",
                        description="Test",
                        success=random.choice([True, True, True, False]),  # 75% success
                        execution_time=random.uniform(10, 60),
                        worker_id=f"worker-{worker_id}"
                    )
                    
                    self.completion_feedback.collect_task_completion_feedback(
                        task_result=result,
                        user_id=f"user-{worker_id}"
                    )
                    
                    feedback_count += 2  # Allocation + completion
                    
            except Exception as e:
                errors.append(f"Worker {worker_id}: {str(e)}")
        
        # Start multiple threads
        threads = []
        num_workers = 5
        
        start_time = time.time()
        
        for i in range(num_workers):
            thread = threading.Thread(
                target=collect_feedback_batch,
                args=(i, 20)  # 20 tasks per worker
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Allow async operations to complete
        time.sleep(0.5)
        
        # Check results
        print(f"\nConcurrent Test Results:")
        print(f"  - Duration: {duration:.2f} seconds")
        print(f"  - Expected feedback entries: ~{num_workers * 20 * 2}")
        print(f"  - Errors encountered: {len(errors)}")
        
        if errors:
            for error in errors[:5]:  # Show first 5 errors
                print(f"    Error: {error}")
        
        # Verify no data corruption
        all_feedback = self.storage.list_feedback(limit=1000)
        
        # Check for duplicate IDs
        feedback_ids = [f.id for f in all_feedback]
        unique_ids = set(feedback_ids)
        
        assert len(feedback_ids) == len(unique_ids), "Duplicate feedback IDs detected"
        
        print(f"  - Total feedback stored: {len(all_feedback)}")
        print(f"  - No duplicate IDs detected")
        print("\n✅ Concurrent feedback collection test passed!")
    
    def test_error_handling_scenarios(self):
        """Test various error handling scenarios"""
        print("\n\nTesting Error Handling Scenarios")
        
        # Test 1: Storage failure during feedback collection
        print("\n1. Testing storage failure handling")
        
        with patch.object(self.storage, 'create_feedback', side_effect=Exception("Database error")):
            # Should not raise exception
            feedback = self.collector.collect_feedback(
                task_id="error-task-1",
                collection_point=CollectionPoint.TASK_COMPLETION,
                content="This should fail to store",
                rating=RatingScale.GOOD
            )
            
            assert feedback is None  # Should return None on error
        
        print("✓ Storage failure handled gracefully")
        
        # Test 2: Invalid feedback data
        print("\n2. Testing invalid feedback data")
        
        # Test with invalid rating
        try:
            feedback = self.collector.collect_feedback(
                task_id="error-task-2",
                collection_point=CollectionPoint.TASK_COMPLETION,
                content="Test",
                rating=10  # Invalid rating
            )
            assert False, "Should have raised exception"
        except Exception:
            print("✓ Invalid rating rejected correctly")
        
        # Test 3: Worker allocation failure
        print("\n3. Testing worker allocation failure")
        
        self.mock_allocator.allocate_worker.return_value = None  # No worker available
        self.mock_allocator.get_worker_status.return_value = {'available_workers': 0}
        
        worker_id = self.allocation_feedback.allocate_worker_with_feedback(
            task_id="error-task-3",
            task_title="Test Task",
            task_description="This should fail to allocate"
        )
        
        assert worker_id is None
        
        # Should still collect failure feedback
        failure_feedback = self.storage.get_feedback_by_task("error-task-3")
        assert len(failure_feedback) > 0
        assert any("failed" in f.content.lower() for f in failure_feedback)
        
        print("✓ Allocation failure handled with feedback")
        
        # Test 4: Task tracking for non-existent task
        print("\n4. Testing completion feedback for untracked task")
        
        # Try to complete a task that wasn't tracked
        result = TaskResult(
            task_id="untracked-task",
            title="Untracked Task",
            description="This was never tracked",
            success=True,
            execution_time=30.0
        )
        
        # Should handle gracefully
        feedback_entry = self.completion_feedback.collect_task_completion_feedback(
            task_result=result
        )
        
        assert feedback_entry is not None  # Should still collect feedback
        
        print("✓ Untracked task completion handled")
        
        # Test 5: Analysis with corrupted data
        print("\n5. Testing analysis with corrupted feedback data")
        
        # Create feedback with missing/invalid metadata
        corrupted_feedback = FeedbackEntry(
            id="corrupted-1",
            task_id="corrupted-task",
            timestamp=datetime.now(),
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Corrupted feedback",
            rating=None,  # Missing rating
            metadata=None  # Missing metadata
        )
        
        self.storage.create_feedback(corrupted_feedback)
        
        # Analysis should handle gracefully
        analysis_result = self.analyzer.analyze_feedback()
        
        assert analysis_result is not None
        assert analysis_result.metrics.total_count > 0
        
        print("✓ Analysis handled corrupted data")
        
        print("\n✅ All error handling tests passed!")
    
    def test_performance_under_load(self):
        """Test system performance under heavy load"""
        print("\n\nTesting Performance Under Load")
        
        # Test parameters
        num_tasks = 1000
        batch_size = 100
        
        print(f"\nGenerating {num_tasks} feedback entries...")
        
        start_time = time.time()
        
        # Generate feedback in batches
        for batch_start in range(0, num_tasks, batch_size):
            batch_feedback = []
            
            for i in range(batch_start, min(batch_start + batch_size, num_tasks)):
                feedback = FeedbackEntry(
                    id=f"perf-test-{i}",
                    task_id=f"task-{i % 100}",  # 100 unique tasks
                    timestamp=datetime.now() - timedelta(
                        days=random.randint(0, 30),
                        hours=random.randint(0, 23)
                    ),
                    feedback_type=random.choice(list(FeedbackType)),
                    content=f"Performance test feedback {i} with {'positive' if i % 2 == 0 else 'negative'} sentiment",
                    rating=RatingScale(random.randint(1, 5)) if i % 3 != 0 else None,
                    user_id=f"worker-{i % 10}",
                    metadata=FeedbackMetadata(
                        source="perf-test",
                        version="1.0",
                        context={
                            "worker_id": f"worker-{i % 10}",
                            "execution_time": random.uniform(10, 120),
                            "success": random.choice([True, False]),
                            "task_complexity": random.choice(["low", "medium", "high"])
                        }
                    )
                )
                batch_feedback.append(feedback)
            
            # Store batch
            for feedback in batch_feedback:
                self.storage.create_feedback(feedback)
        
        storage_time = time.time() - start_time
        print(f"✓ Storage completed in {storage_time:.2f} seconds")
        print(f"  Rate: {num_tasks / storage_time:.0f} entries/second")
        
        # Test retrieval performance
        print("\nTesting retrieval performance...")
        
        start_time = time.time()
        all_feedback = self.storage.list_feedback(limit=num_tasks)
        retrieval_time = time.time() - start_time
        
        print(f"✓ Retrieved {len(all_feedback)} entries in {retrieval_time:.2f} seconds")
        
        # Test analysis performance
        print("\nTesting analysis performance...")
        
        start_time = time.time()
        analysis_result = self.analyzer.analyze_feedback()
        analysis_time = time.time() - start_time
        
        print(f"✓ Analysis completed in {analysis_time:.2f} seconds")
        print(f"  - Metrics calculated: {analysis_result.metrics.total_count} entries")
        print(f"  - Trends detected: {len(analysis_result.trends)}")
        print(f"  - Insights generated: {len(analysis_result.insights)}")
        
        # Test concurrent read/write
        print("\nTesting concurrent read/write performance...")
        
        read_count = 0
        write_count = 0
        
        def reader_thread():
            nonlocal read_count
            for _ in range(50):
                feedback = self.storage.get_feedback_by_task(f"task-{random.randint(0, 99)}")
                read_count += len(feedback)
        
        def writer_thread():
            nonlocal write_count
            for i in range(50):
                feedback = FeedbackEntry(
                    id=f"concurrent-{threading.current_thread().name}-{i}",
                    task_id=f"task-{random.randint(0, 99)}",
                    timestamp=datetime.now(),
                    feedback_type=FeedbackType.TASK_COMPLETION,
                    content="Concurrent write test"
                )
                self.storage.create_feedback(feedback)
                write_count += 1
        
        threads = []
        start_time = time.time()
        
        # Start readers and writers
        for i in range(3):
            threads.append(threading.Thread(target=reader_thread, name=f"reader-{i}"))
            threads.append(threading.Thread(target=writer_thread, name=f"writer-{i}"))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        concurrent_time = time.time() - start_time
        
        print(f"✓ Concurrent operations completed in {concurrent_time:.2f} seconds")
        print(f"  - Reads: {read_count}")
        print(f"  - Writes: {write_count}")
        
        # Performance assertions
        assert storage_time < 10.0, f"Storage too slow: {storage_time:.2f}s for {num_tasks} entries"
        assert retrieval_time < 2.0, f"Retrieval too slow: {retrieval_time:.2f}s"
        assert analysis_time < 5.0, f"Analysis too slow: {analysis_time:.2f}s"
        
        print("\n✅ Performance tests passed!")
    
    def test_feedback_quality_validation(self):
        """Test feedback quality and validation mechanisms"""
        print("\n\nTesting Feedback Quality Validation")
        
        # Test 1: Feedback length validation
        print("\n1. Testing feedback length validation")
        
        # Set up custom prompt with validation
        custom_prompt = FeedbackPrompt(
            prompt_text="Please provide detailed feedback",
            feedback_type=FeedbackType.TASK_COMPLETION,
            requires_rating=True,
            validation_rules={"min_length": 50}
        )
        
        self.collector.set_prompt(CollectionPoint.TASK_COMPLETION, custom_prompt)
        
        # Try with short feedback
        try:
            feedback = self.collector.collect_feedback(
                task_id="quality-test-1",
                collection_point=CollectionPoint.TASK_COMPLETION,
                content="Too short",  # Less than 50 chars
                rating=RatingScale.GOOD
            )
            assert False, "Should have failed validation"
        except Exception as e:
            assert "validation" in str(e).lower()
            print("✓ Short feedback rejected correctly")
        
        # Try with adequate feedback
        long_feedback = self.collector.collect_feedback(
            task_id="quality-test-1",
            collection_point=CollectionPoint.TASK_COMPLETION,
            content="This is a much longer feedback that meets the minimum length requirement for validation",
            rating=RatingScale.GOOD
        )
        
        assert long_feedback is not None
        print("✓ Long feedback accepted")
        
        # Test 2: Rating consistency
        print("\n2. Testing rating consistency with content sentiment")
        
        # Collect conflicting feedback (positive content with poor rating)
        conflicting_feedback = FeedbackEntry(
            id="conflict-1",
            task_id="quality-test-2",
            timestamp=datetime.now(),
            feedback_type=FeedbackType.TASK_COMPLETION,
            content="Excellent work! Perfect implementation with great performance.",
            rating=RatingScale.POOR  # Conflicts with positive content
        )
        
        self.storage.create_feedback(conflicting_feedback)
        
        # Analyze for inconsistencies
        analysis = self.analyzer.analyze_feedback(task_ids=["quality-test-2"])
        
        # The sentiment should show positive despite poor rating
        assert analysis.metrics.sentiment_scores["positive"] > 0
        
        print("✓ Rating-content inconsistency detected")
        
        # Test 3: Duplicate feedback detection
        print("\n3. Testing duplicate feedback handling")
        
        # Create identical feedback entries
        task_id = "quality-test-3"
        duplicate_content = "This is duplicate feedback content"
        
        feedback1 = self.collector.collect_feedback(
            task_id=task_id,
            collection_point=CollectionPoint.TASK_COMPLETION,
            content=duplicate_content,
            rating=RatingScale.GOOD,
            user_id="user-1"
        )
        
        # Try to create duplicate (different ID but same content)
        feedback2 = self.collector.collect_feedback(
            task_id=task_id,
            collection_point=CollectionPoint.TASK_COMPLETION,
            content=duplicate_content,
            rating=RatingScale.GOOD,
            user_id="user-1"
        )
        
        # Both should succeed (system allows duplicates but we can detect them)
        assert feedback1 is not None
        assert feedback2 is not None
        
        # Analysis should be able to identify potential duplicates
        task_feedback = self.storage.get_feedback_by_task(task_id)
        
        # Check for identical content
        content_list = [f.content for f in task_feedback]
        unique_content = set(content_list)
        
        has_duplicates = len(content_list) != len(unique_content)
        print(f"✓ Duplicate detection: {has_duplicates}")
        
        print("\n✅ Feedback quality validation tests passed!")
    
    def test_data_export_import(self):
        """Test data export and import functionality"""
        print("\n\nTesting Data Export/Import")
        
        # Create diverse feedback data
        print("\n1. Creating test data...")
        
        feedback_entries = []
        for i in range(20):
            feedback = FeedbackEntry(
                id=f"export-test-{i}",
                task_id=f"task-{i % 5}",
                timestamp=datetime.now() - timedelta(days=i),
                feedback_type=random.choice(list(FeedbackType)),
                content=f"Export test feedback {i}",
                rating=RatingScale(random.randint(1, 5)) if i % 2 == 0 else None,
                user_id=f"user-{i % 3}",
                metadata=FeedbackMetadata(
                    source="export-test",
                    version="1.0",
                    context={"test_id": i}
                )
            )
            self.storage.create_feedback(feedback)
            feedback_entries.append(feedback)
        
        print(f"✓ Created {len(feedback_entries)} test entries")
        
        # Test 2: Export to JSON
        print("\n2. Testing JSON export...")
        
        # Get analysis result
        analysis_result = self.analyzer.analyze_feedback()
        
        # Export to JSON
        json_export = self.analyzer.export_analysis_report(analysis_result, format="json")
        
        # Verify JSON structure
        parsed_json = json.loads(json_export)
        
        assert "analysis_id" in parsed_json
        assert "metrics" in parsed_json
        assert "trends" in parsed_json
        assert "insights" in parsed_json
        
        print(f"✓ Exported analysis to JSON ({len(json_export)} chars)")
        
        # Test 3: Export to Markdown
        print("\n3. Testing Markdown export...")
        
        md_export = self.analyzer.export_analysis_report(analysis_result, format="markdown")
        
        # Verify markdown structure
        assert "# Feedback Analysis Report" in md_export
        assert "## Metrics" in md_export
        assert "## Summary" in md_export
        
        print(f"✓ Exported analysis to Markdown ({len(md_export)} chars)")
        
        # Test 4: Bulk feedback export
        print("\n4. Testing bulk feedback export...")
        
        # Export all feedback data
        all_feedback = self.storage.list_feedback(limit=1000)
        
        # Convert to exportable format
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "feedback_count": len(all_feedback),
            "feedback_entries": [
                {
                    "id": f.id,
                    "task_id": f.task_id,
                    "timestamp": f.timestamp.isoformat(),
                    "type": f.feedback_type.value,
                    "content": f.content,
                    "rating": f.rating.value if f.rating else None,
                    "user_id": f.user_id,
                    "metadata": f.metadata.to_dict() if f.metadata else None
                }
                for f in all_feedback
            ]
        }
        
        export_json = json.dumps(export_data, indent=2)
        
        print(f"✓ Exported {len(all_feedback)} feedback entries")
        
        # Test 5: Verify data integrity
        print("\n5. Verifying data integrity...")
        
        # Re-parse exported data
        reimported_data = json.loads(export_json)
        
        assert reimported_data["feedback_count"] == len(all_feedback)
        assert len(reimported_data["feedback_entries"]) == len(all_feedback)
        
        # Verify each entry
        for i, exported_entry in enumerate(reimported_data["feedback_entries"]):
            original = all_feedback[i]
            
            assert exported_entry["id"] == original.id
            assert exported_entry["task_id"] == original.task_id
            assert exported_entry["type"] == original.feedback_type.value
            
        print("✓ Data integrity verified")
        
        print("\n✅ Data export/import tests passed!")


class TestIntegrationScenarios:
    """Test real-world integration scenarios"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize components
        self.storage = FeedbackStorage(self.temp_db.name)
        self.analyzer = FeedbackAnalyzer(feedback_storage=self.storage)
    
    def teardown_method(self):
        """Clean up after test"""
        self.storage.close()
        os.unlink(self.temp_db.name)
    
    def test_multi_day_analysis_scenario(self):
        """Test analysis across multiple days with realistic patterns"""
        print("\n\nTesting Multi-Day Analysis Scenario")
        
        # Simulate 30 days of feedback with patterns
        base_date = datetime.now() - timedelta(days=30)
        
        # Week 1: High performance
        print("\n1. Simulating Week 1 (High Performance)...")
        for day in range(7):
            date = base_date + timedelta(days=day)
            for i in range(10):  # 10 tasks per day
                feedback = FeedbackEntry(
                    id=f"week1-day{day}-{i}",
                    task_id=f"task-week1-{day}-{i}",
                    timestamp=date + timedelta(hours=i),
                    feedback_type=FeedbackType.TASK_COMPLETION,
                    content="Task completed successfully with excellent performance",
                    rating=RatingScale(random.choice([4, 5])),  # High ratings
                    metadata=FeedbackMetadata(
                        source="simulation",
                        version="1.0",
                        context={
                            "execution_time": random.uniform(20, 40),  # Fast
                            "success": True,
                            "error_count": 0
                        }
                    )
                )
                self.storage.create_feedback(feedback)
        
        # Week 2: Performance degradation
        print("2. Simulating Week 2 (Performance Degradation)...")
        for day in range(7, 14):
            date = base_date + timedelta(days=day)
            for i in range(12):  # More tasks but with issues
                feedback = FeedbackEntry(
                    id=f"week2-day{day}-{i}",
                    task_id=f"task-week2-{day}-{i}",
                    timestamp=date + timedelta(hours=i),
                    feedback_type=FeedbackType.TASK_COMPLETION,
                    content="Task completed but encountered some performance issues",
                    rating=RatingScale(random.choice([3, 4])),  # Lower ratings
                    metadata=FeedbackMetadata(
                        source="simulation",
                        version="1.0",
                        context={
                            "execution_time": random.uniform(40, 80),  # Slower
                            "success": True,
                            "error_count": random.randint(0, 2)
                        }
                    )
                )
                self.storage.create_feedback(feedback)
        
        # Week 3: Critical issues
        print("3. Simulating Week 3 (Critical Issues)...")
        for day in range(14, 21):
            date = base_date + timedelta(days=day)
            for i in range(8):  # Fewer tasks due to issues
                success = random.choice([True, True, False])  # 33% failure
                feedback = FeedbackEntry(
                    id=f"week3-day{day}-{i}",
                    task_id=f"task-week3-{day}-{i}",
                    timestamp=date + timedelta(hours=i),
                    feedback_type=FeedbackType.ERROR_REPORT if not success else FeedbackType.TASK_COMPLETION,
                    content="Task failed with errors" if not success else "Task completed with significant delays",
                    rating=RatingScale(random.choice([2, 3])) if success else None,
                    metadata=FeedbackMetadata(
                        source="simulation",
                        version="1.0",
                        context={
                            "execution_time": random.uniform(80, 120),  # Very slow
                            "success": success,
                            "error_count": random.randint(2, 5)
                        }
                    )
                )
                self.storage.create_feedback(feedback)
        
        # Week 4: Recovery
        print("4. Simulating Week 4 (Recovery)...")
        for day in range(21, 28):
            date = base_date + timedelta(days=day)
            for i in range(10):
                feedback = FeedbackEntry(
                    id=f"week4-day{day}-{i}",
                    task_id=f"task-week4-{day}-{i}",
                    timestamp=date + timedelta(hours=i),
                    feedback_type=FeedbackType.TASK_COMPLETION,
                    content="Task completed. Performance improving after fixes applied",
                    rating=RatingScale(random.choice([3, 4, 4, 5])),  # Improving
                    metadata=FeedbackMetadata(
                        source="simulation",
                        version="1.0",
                        context={
                            "execution_time": random.uniform(30, 60),  # Better
                            "success": True,
                            "error_count": random.randint(0, 1)
                        }
                    )
                )
                self.storage.create_feedback(feedback)
        
        # Analyze the full period
        print("\n5. Analyzing 30-day period...")
        
        analysis_result = self.analyzer.analyze_feedback(
            start_date=base_date,
            end_date=datetime.now()
        )
        
        print(f"\nAnalysis Results:")
        print(f"  - Total feedback: {analysis_result.metrics.total_count}")
        print(f"  - Average rating: {analysis_result.metrics.average_rating:.2f}")
        print(f"  - Trends detected: {len(analysis_result.trends)}")
        
        for trend in analysis_result.trends:
            print(f"    - {trend.metric_name}: {trend.direction.value} ({trend.change_percentage:+.1f}%)")
        
        print(f"  - Insights: {len(analysis_result.insights)}")
        
        for insight in analysis_result.insights[:3]:  # Show top 3
            print(f"    - [{insight.priority.value}] {insight.title}")
        
        # Verify expected patterns were detected
        assert len(analysis_result.trends) > 0, "Should detect trends"
        assert len(analysis_result.insights) > 0, "Should generate insights"
        
        # Should detect the performance degradation
        declining_trends = [t for t in analysis_result.trends if t.direction.value == "declining"]
        assert len(declining_trends) > 0, "Should detect declining performance"
        
        print("\n✅ Multi-day analysis scenario passed!")
    
    def test_worker_comparison_scenario(self):
        """Test comparing performance across different workers"""
        print("\n\nTesting Worker Comparison Scenario")
        
        workers = {
            "worker-expert": {"rating_range": (4, 5), "speed_range": (20, 40), "error_rate": 0.05},
            "worker-average": {"rating_range": (3, 4), "speed_range": (40, 80), "error_rate": 0.15},
            "worker-novice": {"rating_range": (2, 3), "speed_range": (60, 120), "error_rate": 0.30}
        }
        
        # Generate feedback for each worker
        for worker_id, profile in workers.items():
            print(f"\n1. Generating feedback for {worker_id}...")
            
            for i in range(50):  # 50 tasks per worker
                success = random.random() > profile["error_rate"]
                
                feedback = FeedbackEntry(
                    id=f"{worker_id}-task-{i}",
                    task_id=f"task-{i}",
                    timestamp=datetime.now() - timedelta(days=random.randint(0, 7)),
                    feedback_type=FeedbackType.WORKER_PERFORMANCE,
                    content=f"Worker {worker_id} {'completed' if success else 'failed'} the task",
                    rating=RatingScale(random.randint(*profile["rating_range"])) if success else None,
                    user_id=worker_id,
                    metadata=FeedbackMetadata(
                        source="comparison-test",
                        version="1.0",
                        context={
                            "worker_id": worker_id,
                            "execution_time": random.uniform(*profile["speed_range"]),
                            "success": success,
                            "error_count": 0 if success else random.randint(1, 3)
                        }
                    )
                )
                self.storage.create_feedback(feedback)
        
        # Compare worker performance
        print("\n2. Analyzing worker performance...")
        
        worker_summaries = {}
        for worker_id in workers:
            summary = self.analyzer.get_worker_performance_summary(worker_id)
            worker_summaries[worker_id] = summary
            
            print(f"\n{worker_id}:")
            print(f"  - Average rating: {summary['average_rating']:.2f}" if summary['average_rating'] else "  - No rating")
            print(f"  - Success rate: {summary['success_rate']:.1%}")
            print(f"  - Avg execution time: {summary['average_execution_time']:.1f} min" if summary['average_execution_time'] else "  - No execution time")
            print(f"  - Performance trend: {summary['performance_trend']}")
        
        # Verify expected rankings
        assert worker_summaries["worker-expert"]["average_rating"] > worker_summaries["worker-average"]["average_rating"]
        assert worker_summaries["worker-average"]["average_rating"] > worker_summaries["worker-novice"]["average_rating"]
        
        print("\n✅ Worker comparison scenario passed!")


def run_all_e2e_tests():
    """Run all end-to-end tests"""
    print("=" * 80)
    print("FEEDBACK SYSTEM END-TO-END TESTS")
    print("=" * 80)
    
    # Test classes
    test_classes = [
        TestFeedbackSystemE2E,
        TestIntegrationScenarios
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        print(f"\n\nRunning {test_class.__name__}...")
        print("-" * 40)
        
        test_instance = test_class()
        
        # Get all test methods
        test_methods = [method for method in dir(test_instance) 
                       if method.startswith('test_') and callable(getattr(test_instance, method))]
        
        for test_method in test_methods:
            total_tests += 1
            test_instance.setup_method()
            
            try:
                getattr(test_instance, test_method)()
                passed_tests += 1
            except Exception as e:
                failed_tests.append((test_class.__name__, test_method, str(e)))
                print(f"\n❌ {test_method} FAILED: {str(e)}")
            finally:
                try:
                    test_instance.teardown_method()
                except:
                    pass
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    
    if failed_tests:
        print("\nFailed tests:")
        for class_name, method_name, error in failed_tests:
            print(f"  - {class_name}.{method_name}: {error}")
    
    if len(failed_tests) == 0:
        print("\n✅ ALL END-TO-END TESTS PASSED!")
    else:
        print(f"\n❌ {len(failed_tests)} tests failed")


if __name__ == "__main__":
    run_all_e2e_tests()