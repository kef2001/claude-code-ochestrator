"""
File Path Management for Claude Orchestrator

Centralizes file creation and path management to keep the project organized.
"""

import os
from pathlib import Path
from typing import Optional

class FilePaths:
    """Manages file paths for the orchestrator"""
    
    def __init__(self, base_dir: Optional[str] = None):
        """Initialize with base directory (defaults to project root)"""
        if base_dir is None:
            # Get the project root (parent of claude_orchestrator)
            base_dir = Path(__file__).parent.parent
        self.base_dir = Path(base_dir)
        
        # Define folder structure
        self.folders = {
            'scripts': self.base_dir / 'scripts',
            'docs': self.base_dir / 'docs',
            'designs': self.base_dir / 'designs',
            'examples': self.base_dir / 'examples',
            'archive': self.base_dir / 'archive',
            'logs': self.base_dir / '.taskmaster' / 'logs',
            'tasks': self.base_dir / '.taskmaster' / 'tasks',
        }
        
        # Ensure folders exist
        self._ensure_folders_exist()
    
    def _ensure_folders_exist(self):
        """Create folders if they don't exist"""
        for folder in self.folders.values():
            folder.mkdir(parents=True, exist_ok=True)
    
    def get_script_path(self, filename: str) -> Path:
        """Get path for a script file"""
        if filename.startswith(('add_', 'create_', 'test_', 'debug_', 'fix_', 'enable_', 'run_')) and filename.endswith('.py'):
            return self.folders['scripts'] / filename
        return self.base_dir / filename
    
    def get_doc_path(self, filename: str) -> Path:
        """Get path for a documentation file"""
        if filename.endswith(('_review.md', '_followup.md', '_summary.md')):
            return self.folders['docs'] / filename
        return self.base_dir / filename
    
    def get_design_path(self, filename: str) -> Path:
        """Get path for a design file"""
        if filename.startswith('task_') and filename.endswith('_design.md'):
            return self.folders['designs'] / filename
        return self.base_dir / filename
    
    def get_archive_path(self, filename: str) -> Path:
        """Get path for an archive file"""
        if filename.endswith(('.backup', '.original', '.tmp')):
            return self.folders['archive'] / filename
        return self.base_dir / filename
    
    def get_appropriate_path(self, filename: str) -> Path:
        """Automatically determine the appropriate path for a file"""
        # Check for specific file patterns
        if filename.endswith('.py'):
            return self.get_script_path(filename)
        elif filename.endswith('.md'):
            if '_design' in filename:
                return self.get_design_path(filename)
            else:
                return self.get_doc_path(filename)
        elif filename.endswith(('.backup', '.original', '.tmp')):
            return self.get_archive_path(filename)
        elif filename.endswith('.json') and 'task' in filename:
            return self.folders['scripts'] / filename
        else:
            # Default to base directory for other files
            return self.base_dir / filename
    
    def clean_root_directory(self):
        """Move misplaced files to their appropriate folders"""
        moved_count = 0
        
        # Patterns to move
        patterns = {
            'scripts': ['add_*.py', 'create_*.py', 'test_*.py', 'debug_*.py', 
                       'fix_*.py', 'enable_*.py', 'run_*.py', '*_patch.py',
                       'task_*.json'],
            'docs': ['*_review*.md', '*_followup*.md', 'task_*.md'],
            'designs': ['*_design.md'],
            'archive': ['*.backup', '*.original', '*.tmp']
        }
        
        for folder_name, file_patterns in patterns.items():
            folder = self.folders[folder_name]
            for pattern in file_patterns:
                import glob
                files = glob.glob(str(self.base_dir / pattern))
                for file_path in files:
                    file_path = Path(file_path)
                    if file_path.exists() and file_path.parent == self.base_dir:
                        dest_path = folder / file_path.name
                        file_path.rename(dest_path)
                        moved_count += 1
                        print(f"Moved {file_path.name} to {folder_name}/")
        
        return moved_count


# Global instance
file_paths = FilePaths()