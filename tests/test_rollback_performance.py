"""
Performance tests for Rollback System

Tests rollback performance with large state data and multiple checkpoints.
"""

import tempfile
import os
import shutil
import time
import json
from datetime import datetime, timedelta
import random
import string
import concurrent.futures

from claude_orchestrator.rollback import (
    RollbackManager, RollbackReason, create_rollback_manager
)
from claude_orchestrator.checkpoint_system import CheckpointManager


class TestRollbackPerformance:
    """Performance tests for rollback system"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_manager = CheckpointManager(
            storage_dir=os.path.join(self.temp_dir, "checkpoints")
        )
        self.rollback_manager = RollbackManager(
            checkpoint_manager=self.checkpoint_manager,
            storage_dir=os.path.join(self.temp_dir, "rollbacks")
        )
    
    def teardown_method(self):
        """Clean up after test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _generate_large_data(self, size_mb: int = 10) -> dict:
        """Generate large data payload for testing"""
        # Generate random data of approximately the requested size
        data = {
            "metadata": {
                "size_mb": size_mb,
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            },
            "arrays": [],
            "strings": {},
            "nested": {}
        }
        
        # Calculate approximate sizes
        target_bytes = size_mb * 1024 * 1024
        current_size = 0
        
        # Add large arrays
        while current_size < target_bytes * 0.4:
            array = [random.random() for _ in range(10000)]
            data["arrays"].append(array)
            current_size += len(str(array))
        
        # Add large strings
        while current_size < target_bytes * 0.7:
            key = f"string_{len(data['strings'])}"
            value = ''.join(random.choices(string.ascii_letters + string.digits, k=10000))
            data["strings"][key] = value
            current_size += len(key) + len(value)
        
        # Add nested structures
        while current_size < target_bytes:
            key = f"nested_{len(data['nested'])}"
            nested = {
                "level1": {
                    f"level2_{i}": {
                        f"level3_{j}": random.random()
                        for j in range(100)
                    }
                    for i in range(10)
                }
            }
            data["nested"][key] = nested
            current_size += len(str(nested))
        
        return data
    
    def test_large_state_checkpoint_creation(self):
        """Test checkpoint creation with large state data"""
        sizes = [1, 5, 10, 20]  # MB
        results = []
        
        for size_mb in sizes:
            large_data = self._generate_large_data(size_mb)
            
            start_time = time.time()
            checkpoint_id = self.rollback_manager.create_checkpoint(
                task_id=f"perf-test-{size_mb}mb",
                task_title=f"Performance Test {size_mb}MB",
                step_number=1,
                step_description=f"Testing with {size_mb}MB data",
                data=large_data,
                metadata={"data_size_mb": size_mb}
            )
            creation_time = time.time() - start_time
            
            results.append({
                "size_mb": size_mb,
                "checkpoint_id": checkpoint_id,
                "creation_time_seconds": creation_time,
                "throughput_mb_per_second": size_mb / creation_time
            })
            
            print(f"Created {size_mb}MB checkpoint in {creation_time:.3f}s "
                  f"({size_mb/creation_time:.2f} MB/s)")
        
        # Verify all checkpoints were created
        assert len(results) == len(sizes)
        for result in results:
            assert result["checkpoint_id"] is not None
            assert result["creation_time_seconds"] > 0
    
    def test_large_state_rollback_restoration(self):
        """Test rollback restoration with large state data"""
        # Create checkpoints with varying sizes
        checkpoint_data = []
        sizes = [1, 5, 10]  # MB
        
        for size_mb in sizes:
            large_data = self._generate_large_data(size_mb)
            checkpoint_id = self.rollback_manager.create_checkpoint(
                task_id=f"restore-test-{size_mb}mb",
                task_title=f"Restore Test {size_mb}MB",
                step_number=1,
                step_description=f"Testing restoration with {size_mb}MB",
                data=large_data
            )
            checkpoint_data.append((checkpoint_id, size_mb))
        
        # Test restoration performance
        results = []
        for checkpoint_id, size_mb in checkpoint_data:
            start_time = time.time()
            success, restored_data = self.rollback_manager.restore_checkpoint(
                checkpoint_id=checkpoint_id,
                reason=RollbackReason.MANUAL
            )
            restoration_time = time.time() - start_time
            
            results.append({
                "size_mb": size_mb,
                "success": success,
                "restoration_time_seconds": restoration_time,
                "throughput_mb_per_second": size_mb / restoration_time
            })
            
            print(f"Restored {size_mb}MB checkpoint in {restoration_time:.3f}s "
                  f"({size_mb/restoration_time:.2f} MB/s)")
            
            assert success is True
            assert restored_data is not None
    
    def test_multiple_checkpoint_performance(self):
        """Test performance with many checkpoints"""
        num_checkpoints = 100
        checkpoint_ids = []
        
        # Create many checkpoints
        start_time = time.time()
        for i in range(num_checkpoints):
            checkpoint_id = self.rollback_manager.create_checkpoint(
                task_id="multi-checkpoint-test",
                task_title="Multiple Checkpoint Test",
                step_number=i,
                step_description=f"Step {i}",
                data={
                    "step": i,
                    "timestamp": datetime.now().isoformat(),
                    "random_data": [random.random() for _ in range(1000)]
                }
            )
            checkpoint_ids.append(checkpoint_id)
        
        creation_time = time.time() - start_time
        print(f"Created {num_checkpoints} checkpoints in {creation_time:.3f}s "
              f"({num_checkpoints/creation_time:.2f} checkpoints/s)")
        
        # Test listing performance
        start_time = time.time()
        all_checkpoints = self.rollback_manager.list_checkpoints()
        list_time = time.time() - start_time
        print(f"Listed {len(all_checkpoints)} checkpoints in {list_time:.3f}s")
        
        # Test restoration of random checkpoints
        restore_times = []
        for _ in range(10):
            checkpoint_id = random.choice(checkpoint_ids)
            start_time = time.time()
            success, _ = self.rollback_manager.restore_checkpoint(
                checkpoint_id=checkpoint_id,
                reason=RollbackReason.MANUAL
            )
            restore_time = time.time() - start_time
            restore_times.append(restore_time)
            assert success is True
        
        avg_restore_time = sum(restore_times) / len(restore_times)
        print(f"Average restoration time: {avg_restore_time:.3f}s")
    
    def test_concurrent_rollback_performance(self):
        """Test performance of concurrent rollback operations"""
        # Create checkpoints for concurrent testing
        num_tasks = 20
        checkpoint_map = {}
        
        for i in range(num_tasks):
            task_id = f"concurrent-task-{i}"
            checkpoint_id = self.rollback_manager.create_checkpoint(
                task_id=task_id,
                task_title=f"Concurrent Task {i}",
                step_number=1,
                step_description="Concurrent test",
                data={"task_number": i, "data": [random.random() for _ in range(5000)]}
            )
            checkpoint_map[task_id] = checkpoint_id
        
        # Perform concurrent rollbacks
        def perform_rollback(task_id):
            checkpoint_id = checkpoint_map[task_id]
            start_time = time.time()
            success, _ = self.rollback_manager.restore_checkpoint(
                checkpoint_id=checkpoint_id,
                reason=RollbackReason.ERROR
            )
            return task_id, success, time.time() - start_time
        
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(perform_rollback, task_id) 
                      for task_id in checkpoint_map.keys()]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # Analyze results
        successful_rollbacks = sum(1 for _, success, _ in results if success)
        avg_rollback_time = sum(time for _, _, time in results) / len(results)
        
        print(f"Performed {len(results)} concurrent rollbacks in {total_time:.3f}s")
        print(f"Successful rollbacks: {successful_rollbacks}/{len(results)}")
        print(f"Average individual rollback time: {avg_rollback_time:.3f}s")
        print(f"Throughput: {len(results)/total_time:.2f} rollbacks/s")
        
        assert successful_rollbacks == len(results)
    
    def test_rollback_history_performance(self):
        """Test performance of rollback history operations"""
        # Create many rollback records
        num_rollbacks = 500
        
        start_time = time.time()
        for i in range(num_rollbacks):
            checkpoint_id = self.rollback_manager.create_checkpoint(
                task_id=f"history-test-{i}",
                task_title=f"History Test {i}",
                step_number=1,
                step_description="History test",
                data={"index": i}
            )
            
            # Perform rollback to create history record
            self.rollback_manager.restore_checkpoint(
                checkpoint_id=checkpoint_id,
                reason=RollbackReason.MANUAL if i % 2 == 0 else RollbackReason.ERROR
            )
        
        creation_time = time.time() - start_time
        print(f"Created {num_rollbacks} rollback records in {creation_time:.3f}s")
        
        # Test history retrieval performance
        start_time = time.time()
        full_history = self.rollback_manager.get_rollback_history()
        retrieval_time = time.time() - start_time
        print(f"Retrieved {len(full_history)} history records in {retrieval_time:.3f}s")
        
        # Test filtered history retrieval
        test_task_id = "history-test-250"
        start_time = time.time()
        task_history = self.rollback_manager.get_rollback_history(test_task_id)
        filtered_time = time.time() - start_time
        print(f"Retrieved {len(task_history)} filtered records in {filtered_time:.3f}s")
        
        assert len(full_history) >= num_rollbacks
        assert len(task_history) >= 1
    
    def test_checkpoint_cleanup_performance(self):
        """Test performance of old checkpoint cleanup"""
        # Create many old checkpoints
        num_old_checkpoints = 200
        old_date = datetime.now() - timedelta(days=40)
        
        for i in range(num_old_checkpoints):
            checkpoint_id = self.rollback_manager.create_checkpoint(
                task_id=f"cleanup-test-{i}",
                task_title=f"Cleanup Test {i}",
                step_number=1,
                step_description="Cleanup test",
                data={"index": i}
            )
            
            # Manually modify checkpoint timestamp to make it old
            checkpoint = self.checkpoint_manager.get_checkpoint(checkpoint_id)
            if checkpoint:
                checkpoint.created_at = old_date
                # Re-save checkpoint with old timestamp
                checkpoint_file = os.path.join(
                    self.checkpoint_manager.storage_dir,
                    f"checkpoint_{checkpoint_id}.json"
                )
                with open(checkpoint_file, 'w') as f:
                    json.dump(checkpoint.to_dict(), f, indent=2)
        
        # Create some recent checkpoints
        num_recent = 50
        for i in range(num_recent):
            self.rollback_manager.create_checkpoint(
                task_id=f"recent-test-{i}",
                task_title=f"Recent Test {i}",
                step_number=1,
                step_description="Recent test",
                data={"index": i}
            )
        
        # Test cleanup performance
        start_time = time.time()
        self.rollback_manager.cleanup_old_checkpoints(days=30)
        cleanup_time = time.time() - start_time
        
        # Verify cleanup results
        remaining_checkpoints = self.rollback_manager.list_checkpoints()
        
        print(f"Cleaned up old checkpoints in {cleanup_time:.3f}s")
        print(f"Remaining checkpoints: {len(remaining_checkpoints)}")
        
        # Should have only recent checkpoints
        assert len(remaining_checkpoints) <= num_recent + 10  # Some margin for test checkpoints


def run_performance_tests():
    """Run all performance tests and generate report"""
    print("=" * 60)
    print("ROLLBACK SYSTEM PERFORMANCE TEST REPORT")
    print("=" * 60)
    print()
    
    test = TestRollbackPerformance()
    
    tests = [
        ("Large State Checkpoint Creation", test.test_large_state_checkpoint_creation),
        ("Large State Rollback Restoration", test.test_large_state_rollback_restoration),
        ("Multiple Checkpoint Performance", test.test_multiple_checkpoint_performance),
        ("Concurrent Rollback Performance", test.test_concurrent_rollback_performance),
        ("Rollback History Performance", test.test_rollback_history_performance),
        ("Checkpoint Cleanup Performance", test.test_checkpoint_cleanup_performance)
    ]
    
    for test_name, test_func in tests:
        print(f"\n{test_name}")
        print("-" * len(test_name))
        
        test.setup_method()
        try:
            test_func()
            print("✓ Test completed successfully")
        except Exception as e:
            print(f"✗ Test failed: {e}")
        finally:
            test.teardown_method()
    
    print("\n" + "=" * 60)
    print("Performance test suite completed")
    print("=" * 60)


if __name__ == "__main__":
    run_performance_tests()