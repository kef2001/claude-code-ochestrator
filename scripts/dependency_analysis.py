#!/usr/bin/env python3
"""
Dependency Analysis for Claude Orchestrator Tasks

This script analyzes the dependency relationships in tasks.json, focusing on:
1. Tasks that depend on failed tasks
2. Circular dependencies
3. Blocked tasks count
"""

import json
from pathlib import Path
from typing import List, Dict, Set, Tuple

def load_tasks(file_path: str) -> Dict:
    """Load tasks from JSON file"""
    with open(file_path, 'r') as f:
        return json.load(f)

def analyze_dependencies(tasks_data: Dict, failed_task_ids: List[int]) -> Dict:
    """Analyze task dependencies and identify issues"""
    tasks = tasks_data['tasks']
    task_map = {task['id']: task for task in tasks}
    
    # Results structure
    results = {
        'failed_tasks': failed_task_ids,
        'tasks_blocked_by_failures': [],
        'circular_dependencies': [],
        'dependency_chains': {},
        'total_blocked_count': 0
    }
    
    # Find tasks blocked by failed tasks
    def is_blocked_by_failure(task_id: int, visited: Set[int] = None) -> Tuple[bool, List[int]]:
        """Check if a task is blocked by any failed task, return chain"""
        if visited is None:
            visited = set()
        
        if task_id in visited:
            return False, []  # Circular dependency, handle separately
        
        visited.add(task_id)
        
        if task_id not in task_map:
            return False, []
        
        task = task_map[task_id]
        
        # Direct dependency on failed task
        for dep_id in task['dependencies']:
            if dep_id in failed_task_ids:
                return True, [dep_id]
            
            # Recursive check
            is_blocked, chain = is_blocked_by_failure(dep_id, visited.copy())
            if is_blocked:
                return True, [dep_id] + chain
        
        return False, []
    
    # Check each task
    for task in tasks:
        task_id = task['id']
        
        # Skip if it's a failed task itself
        if task_id in failed_task_ids:
            continue
        
        # Check if blocked by failed tasks
        is_blocked, blocking_chain = is_blocked_by_failure(task_id)
        if is_blocked:
            results['tasks_blocked_by_failures'].append({
                'id': task_id,
                'title': task['title'],
                'status': task['status'],
                'blocking_chain': blocking_chain,
                'direct_dependencies': task['dependencies']
            })
    
    # Detect circular dependencies
    def has_circular_dependency(task_id: int, path: List[int] = None) -> List[int]:
        """Detect circular dependencies, return the cycle if found"""
        if path is None:
            path = []
        
        if task_id in path:
            # Found a cycle
            cycle_start = path.index(task_id)
            return path[cycle_start:] + [task_id]
        
        if task_id not in task_map:
            return []
        
        path.append(task_id)
        task = task_map[task_id]
        
        for dep_id in task['dependencies']:
            cycle = has_circular_dependency(dep_id, path.copy())
            if cycle:
                return cycle
        
        return []
    
    # Check all tasks for circular dependencies
    checked_cycles = set()
    for task in tasks:
        cycle = has_circular_dependency(task['id'])
        if cycle:
            # Normalize cycle (start with smallest ID) to avoid duplicates
            min_idx = cycle.index(min(cycle))
            normalized_cycle = cycle[min_idx:] + cycle[:min_idx]
            cycle_tuple = tuple(normalized_cycle[:-1])  # Remove duplicate last element
            
            if cycle_tuple not in checked_cycles:
                checked_cycles.add(cycle_tuple)
                results['circular_dependencies'].append({
                    'cycle': list(cycle_tuple),
                    'tasks': [{'id': tid, 'title': task_map[tid]['title'][:50] + '...' if len(task_map[tid]['title']) > 50 else task_map[tid]['title']} for tid in cycle_tuple]
                })
    
    # Count total blocked tasks
    results['total_blocked_count'] = len(results['tasks_blocked_by_failures'])
    
    # Add summary of blocking impact for each failed task
    blocking_impact = {}
    for failed_id in failed_task_ids:
        blocked_by_this = [t for t in results['tasks_blocked_by_failures'] 
                          if failed_id in t['blocking_chain']]
        blocking_impact[failed_id] = {
            'title': task_map[failed_id]['title'][:50] + '...' if len(task_map[failed_id]['title']) > 50 else task_map[failed_id]['title'],
            'status': task_map[failed_id]['status'],
            'blocks_count': len(blocked_by_this),
            'blocks_tasks': [{'id': t['id'], 'title': t['title'][:50] + '...' if len(t['title']) > 50 else t['title']} for t in blocked_by_this]
        }
    
    results['blocking_impact'] = blocking_impact
    
    return results

def print_analysis_report(results: Dict):
    """Print a formatted analysis report"""
    print("=" * 80)
    print("DEPENDENCY ANALYSIS REPORT")
    print("=" * 80)
    
    print(f"\nFailed Tasks: {results['failed_tasks']}")
    print(f"Total Tasks Blocked by Failures: {results['total_blocked_count']}")
    
    print("\n" + "-" * 80)
    print("BLOCKING IMPACT BY FAILED TASK:")
    print("-" * 80)
    
    for failed_id, impact in results['blocking_impact'].items():
        print(f"\nTask {failed_id}: {impact['title']}")
        print(f"  Status: {impact['status']}")
        print(f"  Blocks {impact['blocks_count']} tasks:")
        for blocked in impact['blocks_tasks']:
            print(f"    - Task {blocked['id']}: {blocked['title']}")
    
    print("\n" + "-" * 80)
    print("CIRCULAR DEPENDENCIES:")
    print("-" * 80)
    
    if results['circular_dependencies']:
        for i, cycle_info in enumerate(results['circular_dependencies'], 1):
            print(f"\nCircular Dependency {i}:")
            print(f"  Cycle: {' -> '.join(map(str, cycle_info['cycle']))} -> {cycle_info['cycle'][0]}")
            for task in cycle_info['tasks']:
                print(f"    - Task {task['id']}: {task['title']}")
    else:
        print("\n  No circular dependencies found!")
    
    print("\n" + "-" * 80)
    print("BLOCKED TASKS DETAILS:")
    print("-" * 80)
    
    for blocked in results['tasks_blocked_by_failures']:
        print(f"\nTask {blocked['id']}: {blocked['title'][:60]}...")
        print(f"  Status: {blocked['status']}")
        print(f"  Direct Dependencies: {blocked['direct_dependencies']}")
        print(f"  Blocking Chain: {' -> '.join(map(str, blocked['blocking_chain']))}")

def main():
    # Load tasks
    tasks_file = Path(__file__).parent / '.taskmaster' / 'tasks' / 'tasks.json'
    tasks_data = load_tasks(tasks_file)
    
    # Failed task IDs from the user's request
    failed_task_ids = [12, 18, 25, 32, 13, 11, 6, 5]
    
    # Analyze dependencies
    results = analyze_dependencies(tasks_data, failed_task_ids)
    
    # Print report
    print_analysis_report(results)
    
    # Save results to JSON for further analysis
    output_file = Path(__file__).parent / 'dependency_analysis_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n\nDetailed results saved to: {output_file}")

if __name__ == '__main__':
    main()