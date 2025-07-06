#!/usr/bin/env python3
"""
Test script for Worker Pool Management System
"""

import sys
import time
import logging
from datetime import datetime
from claude_orchestrator.worker_pool_manager import (
    WorkerPoolManager, WorkerPool, PoolConfiguration, PoolScalingPolicy,
    WorkerState, WorkerMetrics
)
from claude_orchestrator.dynamic_worker_allocation import (
    WorkerProfile, WorkerCapability, TaskComplexity, TaskRequirements
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_worker_pool_creation():
    """Test basic worker pool creation and configuration"""
    print("=" * 60)
    print("Testing Worker Pool Creation")
    print("=" * 60)
    
    # Create pool manager
    pool_manager = WorkerPoolManager()
    
    # Create pool configuration
    config = PoolConfiguration(
        min_workers=2,
        max_workers=8,
        target_utilization=0.7,
        scaling_policy=PoolScalingPolicy.BALANCED,
        scale_up_threshold=0.8,
        scale_down_threshold=0.3
    )
    
    # Create worker pool
    pool = pool_manager.create_pool("test_pool", config)
    
    print(f"✓ Created pool: {pool.pool_name}")
    print(f"✓ Pool config: min={config.min_workers}, max={config.max_workers}")
    
    # Test pool status
    status = pool.get_pool_status()
    print(f"✓ Pool status: {status['statistics']['total_workers']} workers")
    
    return pool_manager, pool


def test_worker_management(pool: WorkerPool):
    """Test adding and removing workers"""
    print("\n" + "=" * 60)
    print("Testing Worker Management")
    print("=" * 60)
    
    # Create test workers
    workers = [
        WorkerProfile(
            worker_id="worker-1",
            model_name="claude-3-5-sonnet-20241022",
            capabilities={WorkerCapability.CODE, WorkerCapability.RESEARCH},
            max_complexity=TaskComplexity.HIGH,
            max_concurrent_tasks=2
        ),
        WorkerProfile(
            worker_id="worker-2",
            model_name="claude-3-5-sonnet-20241022",
            capabilities={WorkerCapability.DOCUMENTATION, WorkerCapability.TESTING},
            max_complexity=TaskComplexity.MEDIUM,
            max_concurrent_tasks=1
        ),
        WorkerProfile(
            worker_id="worker-3",
            model_name="claude-3-opus-20240229",
            capabilities={WorkerCapability.DESIGN, WorkerCapability.REVIEW},
            max_complexity=TaskComplexity.CRITICAL,
            max_concurrent_tasks=3
        )
    ]
    
    # Add workers to pool
    for worker in workers:
        success = pool.add_worker(worker)
        print(f"✓ Added worker {worker.worker_id}: {success}")
    
    # Check pool status
    status = pool.get_pool_status()
    print(f"✓ Pool now has {status['statistics']['total_workers']} workers")
    print(f"✓ Idle workers: {status['statistics']['idle_workers']}")
    
    # Test worker capabilities
    for worker_id, worker_info in status['workers'].items():
        print(f"  - {worker_id}: {worker_info['capabilities']}")
    
    return workers


def test_task_assignment(pool: WorkerPool):
    """Test task assignment and completion"""
    print("\n" + "=" * 60)
    print("Testing Task Assignment")
    print("=" * 60)
    
    # Create test tasks
    tasks = [
        {
            'task_id': 'task-1',
            'title': 'Implement API endpoint',
            'description': 'Create a new REST API endpoint for user authentication',
            'requirements': TaskRequirements(
                complexity=TaskComplexity.MEDIUM,
                estimated_duration=45,
                required_capabilities={WorkerCapability.CODE}
            )
        },
        {
            'task_id': 'task-2',
            'title': 'Write documentation',
            'description': 'Create comprehensive documentation for the new API',
            'requirements': TaskRequirements(
                complexity=TaskComplexity.LOW,
                estimated_duration=30,
                required_capabilities={WorkerCapability.DOCUMENTATION}
            )
        },
        {
            'task_id': 'task-3',
            'title': 'Design system architecture',
            'description': 'Design scalable architecture for microservices',
            'requirements': TaskRequirements(
                complexity=TaskComplexity.HIGH,
                estimated_duration=120,
                required_capabilities={WorkerCapability.DESIGN}
            )
        }
    ]
    
    # Assign tasks
    assigned_workers = {}
    for task in tasks:
        worker_id = pool.assign_task(
            task['task_id'],
            task['title'],
            task['description'],
            task['requirements']
        )
        assigned_workers[task['task_id']] = worker_id
        print(f"✓ Assigned task {task['task_id']} to worker {worker_id}")
    
    # Check pool status after assignment
    status = pool.get_pool_status()
    print(f"✓ Active tasks: {status['active_tasks']}")
    print(f"✓ Queue size: {status['statistics']['queue_size']}")
    print(f"✓ Pool utilization: {status['statistics']['utilization']:.2%}")
    
    # Simulate task completion
    print("\nSimulating task completion...")
    for task_id, worker_id in assigned_workers.items():
        if worker_id:  # Only complete tasks that were assigned
            success = pool.complete_task(
                task_id=task_id,
                worker_id=worker_id,
                success=True,
                actual_duration=30.0
            )
            print(f"✓ Completed task {task_id} on worker {worker_id}: {success}")
    
    return assigned_workers


def test_scaling_behavior(pool: WorkerPool):
    """Test automatic scaling behavior"""
    print("\n" + "=" * 60)
    print("Testing Scaling Behavior")
    print("=" * 60)
    
    # Create many tasks to trigger scaling
    tasks = []
    for i in range(10):
        task_id = f"scale-task-{i}"
        worker_id = pool.assign_task(
            task_id=task_id,
            task_title=f"Scale test task {i}",
            task_description=f"Test task {i} to trigger scaling",
            priority=5
        )
        tasks.append((task_id, worker_id))
        print(f"✓ Created task {task_id} -> worker {worker_id}")
    
    # Check pool status
    status = pool.get_pool_status()
    print(f"✓ Queue size: {status['statistics']['queue_size']}")
    print(f"✓ Pool utilization: {status['statistics']['utilization']:.2%}")
    print(f"✓ Total workers: {status['statistics']['total_workers']}")
    
    # Wait a bit for scaling to potentially occur
    print("\nWaiting for potential scaling...")
    time.sleep(3)
    
    # Check status again
    status = pool.get_pool_status()
    print(f"✓ After scaling - Total workers: {status['statistics']['total_workers']}")
    print(f"✓ Scaling events: {status['statistics']['scaling_events']}")
    
    return tasks


def test_pool_analytics(pool: WorkerPool):
    """Test pool analytics and reporting"""
    print("\n" + "=" * 60)
    print("Testing Pool Analytics")
    print("=" * 60)
    
    # Get comprehensive pool status
    status = pool.get_pool_status()
    
    print("Pool Configuration:")
    for key, value in status['config'].items():
        print(f"  {key}: {value}")
    
    print("\nPool Statistics:")
    for key, value in status['statistics'].items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
    
    print("\nWorker Details:")
    for worker_id, worker_info in status['workers'].items():
        print(f"  {worker_id}:")
        print(f"    State: {worker_info['state']}")
        print(f"    Model: {worker_info['model']}")
        print(f"    Success Rate: {worker_info['success_rate']:.2%}")
        print(f"    Avg Response Time: {worker_info['average_response_time']:.2f}s")
    
    print(f"\nTotal Active Tasks: {status['active_tasks']}")
    print(f"Total Completed Tasks: {status['completed_tasks']}")


def test_pool_manager(pool_manager: WorkerPoolManager):
    """Test the worker pool manager"""
    print("\n" + "=" * 60)
    print("Testing Worker Pool Manager")
    print("=" * 60)
    
    # Create additional pools
    configs = [
        ("dev_pool", PoolConfiguration(
            min_workers=1,
            max_workers=5,
            scaling_policy=PoolScalingPolicy.CONSERVATIVE
        )),
        ("prod_pool", PoolConfiguration(
            min_workers=3,
            max_workers=15,
            scaling_policy=PoolScalingPolicy.AGGRESSIVE
        ))
    ]
    
    for pool_name, config in configs:
        pool = pool_manager.create_pool(pool_name, config)
        print(f"✓ Created pool: {pool_name}")
    
    # Get all pools status
    all_status = pool_manager.get_all_pools_status()
    print(f"✓ Total pools: {all_status['total_pools']}")
    
    for pool_name, pool_status in all_status['pools'].items():
        print(f"  {pool_name}: {pool_status['statistics']['total_workers']} workers")
    
    return configs


def main():
    """Main test function"""
    print("Worker Pool Management System Test Suite")
    print("=" * 60)
    
    try:
        # Test 1: Basic pool creation
        pool_manager, pool = test_worker_pool_creation()
        
        # Test 2: Worker management
        workers = test_worker_management(pool)
        
        # Test 3: Task assignment
        assigned_tasks = test_task_assignment(pool)
        
        # Test 4: Scaling behavior
        scale_tasks = test_scaling_behavior(pool)
        
        # Test 5: Analytics
        test_pool_analytics(pool)
        
        # Test 6: Pool manager
        additional_pools = test_pool_manager(pool_manager)
        
        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        # Clean up
        print("\nCleaning up...")
        pool_manager.shutdown()
        print("✓ Cleanup completed")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())