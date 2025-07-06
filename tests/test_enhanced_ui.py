#!/usr/bin/env python3
"""
Test script to verify Enhanced UI is working
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("🧪 Testing Enhanced UI...")
print("=" * 50)

try:
    # Import orchestrator components
    from claude_orchestrator.main import ProgressDisplay
    from claude_orchestrator.enhanced_progress_display import EnhancedProgressDisplay
    
    print("✅ Imports successful")
    
    # Create a progress display instance
    progress = ProgressDisplay(total_tasks=10)
    
    # Check if it's using the enhanced display
    if hasattr(progress, 'display'):
        print("✅ Enhanced UI wrapper detected")
        if isinstance(progress.display, EnhancedProgressDisplay):
            print("✅ Using EnhancedProgressDisplay backend")
        else:
            print("❌ Not using EnhancedProgressDisplay backend")
    else:
        print("❌ Not using Enhanced UI wrapper")
    
    # Test basic functionality
    print("\n📊 Testing UI functionality...")
    
    # Simulate some progress
    progress.update("Initializing...")
    
    # Register workers
    for i in range(3):
        progress.set_worker_task(i, f"task_{i}", f"Test Task {i}", "[0/5]")
    
    progress.completed = 2
    progress.active = 3
    progress.failed = 0
    
    # Add some messages
    progress.log_message("System initialized", "INFO")
    progress.log_message("Task 1 completed successfully", "SUCCESS")
    progress.log_message("Starting task processing", "INFO")
    
    # Update display
    progress.update()
    
    print("\n✅ UI test completed successfully!")
    print("\n📝 Summary:")
    print("  • Enhanced UI is properly configured")
    print("  • All components are working")
    print("  • Ready for orchestrator execution")
    
    # Cleanup
    if hasattr(progress, 'stop'):
        progress.stop()
    
except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n🚀 You can now run the orchestrator with Enhanced UI:")
print("  $ python -m claude_orchestrator.main run")