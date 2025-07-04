#!/usr/bin/env python3
"""
File Organization Utility for Claude Orchestrator

This script organizes project files into appropriate folders to keep the root directory clean.
It should be run periodically or when the root directory gets cluttered with work files.
"""

import sys
import os

# Add parent directory to path to import claude_orchestrator modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claude_orchestrator.file_paths import file_paths

def main():
    """Main function to organize files"""
    print("🗂️  Organizing Claude Orchestrator files...")
    print("-" * 50)
    
    # Clean up the root directory
    moved_count = file_paths.clean_root_directory()
    
    print("-" * 50)
    if moved_count > 0:
        print(f"✅ Successfully moved {moved_count} files to appropriate folders")
    else:
        print("✨ No files to move - root directory is already clean!")
    
    print("\nFolder structure:")
    for name, path in file_paths.folders.items():
        file_count = len(list(path.glob('*'))) if path.exists() else 0
        print(f"  📁 {name}/ - {file_count} files")

if __name__ == "__main__":
    main()