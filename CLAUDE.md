# Claude Code Guidelines for Claude Orchestrator Project

## File Organization

This project maintains a clean root directory by organizing files into specific folders:

### Folder Structure
- `scripts/` - All Python scripts (add_*.py, create_*.py, test_*.py, etc.)
- `docs/` - Documentation, reviews, and follow-up markdown files
- `designs/` - Task design documents
- `examples/` - Example files and templates
- `archive/` - Backup files and temporary files
- `.taskmaster/` - Task management data and logs

### Important: When Creating Files

1. **Task Scripts** (add_*.py, create_*.py): Place in `scripts/` folder
   ```python
   # Create as: scripts/add_new_task.py
   ```

2. **Documentation** (*_review.md, *_followup.md): Place in `docs/` folder
   ```markdown
   # Create as: docs/task_X_review.md
   ```

3. **Design Documents** (*_design.md): Place in `designs/` folder
   ```markdown
   # Create as: designs/task_X_design.md
   ```

4. **Never create temporary files in the root directory**

### File Cleanup

If files accumulate in the root directory, run:
```bash
python3 organize_files.py
```

## Testing Commands

Always run these commands after making changes:
- `co lint` - Run linting checks
- `co typecheck` - Run type checking
- `co test` - Run tests

## Project-Specific Guidelines

1. **Worker Idle Issue**: The worker idle issue has been fixed. Workers now check for new tasks immediately after completion.

2. **Opus Task Priority**: Opus feedback tasks (tagged with 'followup', 'follow-up', or opus-manager-review) are automatically prioritized.

3. **Enhanced UI**: The project uses an enhanced progress display. Import from:
   ```python
   from claude_orchestrator.enhanced_progress_display import EnhancedProgressDisplay
   ```

4. **File Paths**: Use the file_paths module for consistent file placement:
   ```python
   from claude_orchestrator.file_paths import file_paths
   
   # Get appropriate path for any file
   script_path = file_paths.get_script_path('add_task.py')
   doc_path = file_paths.get_doc_path('review.md')
   ```

## Git Commit Guidelines

When committing changes:
1. Only commit essential functional code
2. Exclude temporary work files (they're in .gitignore)
3. Use descriptive commit messages with emojis
4. Include the Claude Code attribution