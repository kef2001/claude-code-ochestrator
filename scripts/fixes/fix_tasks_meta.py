#!/usr/bin/env python3
"""
Fix the missing 'meta' section in tasks.json file
"""

import json
from datetime import datetime
from pathlib import Path

def fix_tasks_meta():
    """Add missing meta section to tasks.json"""
    
    tasks_file = Path(".taskmaster/tasks/tasks.json")
    
    if not tasks_file.exists():
        print("❌ Tasks file not found!")
        return False
    
    # Load current tasks
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    
    # Check if meta already exists
    if 'meta' in data:
        print("✅ Meta section already exists")
        return True
    
    # Add missing meta section
    print("🔧 Adding missing meta section...")
    
    # Create meta section with proper fields
    meta = {
        'projectName': 'claude-code-orchestrator',
        'projectVersion': '1.0.0',
        'createdAt': datetime.now().isoformat(),
        'updatedAt': datetime.now().isoformat(),
        'description': 'Claude Orchestrator Task Management',
        'totalTasks': len(data.get('tasks', [])),
        'completedTasks': len([t for t in data.get('tasks', []) if t.get('status') == 'done']),
        'pendingTasks': len([t for t in data.get('tasks', []) if t.get('status') == 'pending'])
    }
    
    # Create new data structure with meta
    new_data = {
        'meta': meta,
        'tasks': data.get('tasks', [])
    }
    
    # Backup original file
    backup_file = tasks_file.with_suffix('.json.backup')
    with open(backup_file, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"📦 Backup saved to: {backup_file}")
    
    # Save fixed file
    with open(tasks_file, 'w') as f:
        json.dump(new_data, f, indent=2)
    
    print("✅ Fixed tasks.json with meta section")
    print(f"   Total tasks: {meta['totalTasks']}")
    print(f"   Completed: {meta['completedTasks']}")
    print(f"   Pending: {meta['pendingTasks']}")
    
    return True

def verify_fix():
    """Verify the fix by testing task manager"""
    print("\n🔍 Verifying fix...")
    
    try:
        from claude_orchestrator.task_master import TaskManager
        tm = TaskManager()
        
        # Try to list tasks (this was failing before)
        tasks = tm.get_all_tasks()
        print(f"✅ Task Manager can load {len(tasks)} tasks")
        
        # Try to save (this was also failing)
        tm._save_tasks()
        print("✅ Task Manager can save tasks")
        
        return True
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🛠️  Fixing missing 'meta' section in tasks.json")
    print("=" * 50)
    
    if fix_tasks_meta():
        if verify_fix():
            print("\n✅ All fixed! The orchestrator should work now.")
        else:
            print("\n⚠️  Fix applied but verification failed")
    else:
        print("\n❌ Fix failed")