#!/usr/bin/env python3
"""
Add review application step to the orchestrator workflow
"""

import os
import sys

def add_review_application():
    """Add review application to main.py"""
    
    file_path = "claude_orchestrator/main.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Add import for ReviewApplier
    import_section = "from .task_master_ai import TaskMasterAI"
    new_import = """from .task_master_ai import TaskMasterAI
from .review_applier import ReviewApplier, ReviewApplierIntegration"""
    
    content = content.replace(import_section, new_import)
    
    # Initialize ReviewApplier in __init__
    init_section = "self.slack_notifier = SlackNotificationManager(slack_webhook_url)"
    new_init = """self.slack_notifier = SlackNotificationManager(slack_webhook_url)
        
        # Initialize review applier
        self.review_applier = ReviewApplier(working_dir)
        self.review_integration = ReviewApplierIntegration(self.review_applier)"""
    
    content = content.replace(init_section, new_init)
    
    # Modify review_loop to apply changes after review
    review_application = '''
                # Log review summary  
                logger.debug(f"Opus review for task {task.task_id}:\\n{review_result['review']}")
                
                # Apply review changes to code
                if self.use_progress_display and self.progress:
                    self.progress.log_message(f"📝 Applying review feedback for task {task.task_id}", "INFO")
                
                apply_result = self.review_integration.process_review_and_apply(
                    review_result, 
                    {'task_id': task.task_id, 'title': task.title}
                )
                
                if apply_result['applied']:
                    changes_count = len(apply_result['changes'])
                    if self.use_progress_display and self.progress:
                        self.progress.log_message(
                            f"✅ Applied {changes_count} changes from review to task {task.task_id}", 
                            "SUCCESS"
                        )
                    logger.info(f"Applied {changes_count} review changes to task {task.task_id}")
                    
                    # If significant changes were made, might need re-review
                    if apply_result['needs_re_review'] and changes_count > 2:
                        logger.info(f"Task {task.task_id} needs re-review after changes")
                        # Could put back in review queue, but for now just log
                elif apply_result['errors']:
                    if self.use_progress_display and self.progress:
                        self.progress.log_message(
                            f"⚠️ Failed to apply some review changes for task {task.task_id}", 
                            "WARNING"
                        )
                    logger.warning(f"Errors applying review: {apply_result['errors']}")'''
    
    # Find the right place to insert (after review summary log)
    target = 'logger.debug(f"Opus review for task {task.task_id}:\\n{review_result[\'review\']}")'
    
    # Replace the line with itself plus the new code
    content = content.replace(target, target + review_application)
    
    # Save the modified file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Added review application step to main.py")
    print("\nThe orchestrator will now:")
    print("1. Worker completes task")
    print("2. Opus reviews the task") 
    print("3. 🆕 Review feedback is automatically applied to the code")
    print("4. Changes are tracked and logged")
    print("\nThis closes the feedback loop!")

if __name__ == "__main__":
    add_review_application()