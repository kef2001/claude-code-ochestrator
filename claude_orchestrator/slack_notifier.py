#!/usr/bin/env python3
"""
Slack Notification Manager for Claude Orchestrator
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# import requests  # Temporarily disabled for task creation


class SlackNotificationManager:
    """Manages Slack notifications for the orchestrator"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url
        
    def send_notification(self, message: str, emoji: str = ":robot_face:", blocks: Optional[List[Dict]] = None) -> bool:
        """Send a notification to Slack"""
        if not self.webhook_url:
            return False
            
        try:
            payload = {
                "text": message,
                "icon_emoji": emoji
            }
            
            if blocks:
                payload["blocks"] = blocks
                
            response = requests.post(self.webhook_url, json=payload)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False
    
    def send_task_complete(self, task_id: str, task_title: str) -> bool:
        """Send notification when a task is completed"""
        message = f"✅ Task completed: {task_id} - {task_title}"
        return self.send_notification(message, ":white_check_mark:")
    
    def send_task_failed(self, task_id: str, task_title: str, error: str) -> bool:
        """Send notification when a task fails"""
        message = f"❌ Task failed: {task_id} - {task_title}\nError: {error}"
        return self.send_notification(message, ":x:")
    
    def send_all_complete(self, total_tasks: int, completed: int, failed: int, elapsed_time: str) -> bool:
        """Send notification when all tasks are complete"""
        message = (f"All tasks complete!\n"
                  f"Total: {total_tasks} | Completed: {completed} | Failed: {failed}\n"
                  f"Time: {elapsed_time}")
        emoji = ":tada:" if failed == 0 else ":warning:"
        return self.send_notification(message, emoji)
    
    def send_opus_review(self, review_summary: str, task_results: List[Dict[str, Any]], elapsed_time: str, follow_up_count: int = 0) -> bool:
        """Send Opus review notification with structured blocks"""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🎭 Opus Review Summary"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": review_summary
                }
            },
            {
                "type": "divider"
            }
        ]
        
        # Add task results
        for result in task_results[:10]:  # Limit to 10 to avoid message size limits
            status_emoji = "✅" if result['status'] == 'completed' else "❌"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_emoji} *{result['title']}*\n{result.get('summary', 'No summary available')}"
                }
            })
        
        if len(task_results) > 10:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_... and {len(task_results) - 10} more tasks_"
                }
            })
        
        # Add follow-up count if any
        if follow_up_count > 0:
            blocks.append({
                "type": "divider"
            })
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🔧 *Follow-up Tasks Created:* {follow_up_count}"
                }
            })
        
        # Add footer with timing
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"⏱ Execution time: {elapsed_time}"
                }
            ]
        })
        
        return self.send_notification("Opus Review Complete", ":robot_face:", blocks)