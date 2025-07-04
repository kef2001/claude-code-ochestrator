"""Interactive feedback interface for real-time user feedback collection."""

import sys
import os
import threading
import queue
import time
import json
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import readline  # For better input handling

from .feedback_model import (
    FeedbackModel, FeedbackType, FeedbackSeverity, 
    create_success_feedback, create_error_feedback, 
    create_warning_feedback, create_info_feedback
)
from .feedback_storage import FeedbackStorage
from .storage_factory import create_feedback_storage

logger = logging.getLogger(__name__)


class InteractionType(Enum):
    """Types of user interactions."""
    RATING = "rating"
    CHOICE = "choice"
    TEXT = "text"
    CONFIRMATION = "confirmation"
    REVIEW = "review"


@dataclass
class FeedbackPrompt:
    """Interactive feedback prompt."""
    prompt_id: str
    message: str
    interaction_type: InteractionType
    options: Optional[List[str]] = None
    min_rating: int = 1
    max_rating: int = 5
    timeout: Optional[int] = None  # seconds
    context: Dict[str, Any] = field(default_factory=dict)
    
    def display(self) -> str:
        """Format prompt for display."""
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("🔔 FEEDBACK REQUEST")
        lines.append("=" * 60)
        lines.append(self.message)
        
        if self.interaction_type == InteractionType.RATING:
            lines.append(f"\nPlease rate ({self.min_rating}-{self.max_rating}):")
            lines.append("  " + " ".join(str(i) for i in range(self.min_rating, self.max_rating + 1)))
            
        elif self.interaction_type == InteractionType.CHOICE and self.options:
            lines.append("\nPlease choose:")
            for i, option in enumerate(self.options, 1):
                lines.append(f"  {i}. {option}")
                
        elif self.interaction_type == InteractionType.CONFIRMATION:
            lines.append("\nPlease confirm (y/n):")
            
        elif self.interaction_type == InteractionType.TEXT:
            lines.append("\nPlease provide your feedback:")
            
        elif self.interaction_type == InteractionType.REVIEW:
            lines.append("\nPlease review and provide feedback:")
            if "content" in self.context:
                lines.append("-" * 40)
                lines.append(str(self.context["content"])[:500])  # Show preview
                if len(str(self.context["content"])) > 500:
                    lines.append("... (truncated)")
                lines.append("-" * 40)
        
        if self.timeout:
            lines.append(f"\n⏱️  Response timeout: {self.timeout} seconds")
        
        lines.append("=" * 60)
        return "\n".join(lines)


class InteractiveFeedbackCollector:
    """Collects interactive feedback from users during task execution."""
    
    def __init__(self, 
                 storage: Optional[FeedbackStorage] = None,
                 auto_mode: bool = False):
        self.storage = storage or create_feedback_storage()
        self.auto_mode = auto_mode  # Auto-respond in non-interactive mode
        
        # Prompt queue and processing
        self.prompt_queue: queue.Queue = queue.Queue()
        self.response_callbacks: Dict[str, Callable] = {}
        self._processing = False
        self._processor_thread: Optional[threading.Thread] = None
        
        # History
        self.interaction_history: List[Dict[str, Any]] = []
        
        # Start processor if not in auto mode
        if not auto_mode:
            self._start_processor()
        
        logger.info(f"Interactive feedback collector initialized (auto_mode={auto_mode})")
    
    def _start_processor(self):
        """Start the prompt processor thread."""
        if self._processing:
            return
        
        self._processing = True
        self._processor_thread = threading.Thread(
            target=self._process_prompts,
            daemon=True,
            name="FeedbackProcessor"
        )
        self._processor_thread.start()
    
    def stop(self):
        """Stop the feedback collector."""
        self._processing = False
        if self._processor_thread:
            # Add sentinel to wake up thread
            self.prompt_queue.put(None)
            self._processor_thread.join(timeout=5)
    
    def _process_prompts(self):
        """Process feedback prompts from the queue."""
        while self._processing:
            try:
                # Get prompt with timeout
                item = self.prompt_queue.get(timeout=1)
                
                if item is None:  # Sentinel
                    break
                
                prompt, callback = item
                
                # Display prompt
                print(prompt.display())
                
                # Collect response
                response = self._collect_response(prompt)
                
                # Save to history
                self.interaction_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "prompt_id": prompt.prompt_id,
                    "prompt": prompt.message,
                    "response": response,
                    "context": prompt.context
                })
                
                # Call callback
                if callback:
                    try:
                        callback(response)
                    except Exception as e:
                        logger.error(f"Error in feedback callback: {e}")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing feedback prompt: {e}")
    
    def _collect_response(self, prompt: FeedbackPrompt) -> Any:
        """Collect user response for a prompt."""
        start_time = time.time()
        
        try:
            if prompt.interaction_type == InteractionType.RATING:
                return self._collect_rating(prompt)
            
            elif prompt.interaction_type == InteractionType.CHOICE:
                return self._collect_choice(prompt)
            
            elif prompt.interaction_type == InteractionType.CONFIRMATION:
                return self._collect_confirmation(prompt)
            
            elif prompt.interaction_type == InteractionType.TEXT:
                return self._collect_text(prompt)
            
            elif prompt.interaction_type == InteractionType.REVIEW:
                return self._collect_review(prompt)
            
        except KeyboardInterrupt:
            print("\n⚠️  Feedback cancelled")
            return None
        except Exception as e:
            logger.error(f"Error collecting response: {e}")
            return None
    
    def _collect_rating(self, prompt: FeedbackPrompt) -> Optional[int]:
        """Collect rating input."""
        while True:
            try:
                response = input("> ").strip()
                
                if not response and prompt.timeout:
                    print("⏱️  Timeout - using default rating")
                    return (prompt.min_rating + prompt.max_rating) // 2
                
                rating = int(response)
                if prompt.min_rating <= rating <= prompt.max_rating:
                    return rating
                else:
                    print(f"Please enter a number between {prompt.min_rating} and {prompt.max_rating}")
                    
            except ValueError:
                print("Please enter a valid number")
    
    def _collect_choice(self, prompt: FeedbackPrompt) -> Optional[str]:
        """Collect choice input."""
        if not prompt.options:
            return None
        
        while True:
            try:
                response = input("> ").strip()
                
                if not response and prompt.timeout:
                    print("⏱️  Timeout - using first option")
                    return prompt.options[0]
                
                # Try as number
                try:
                    choice_idx = int(response) - 1
                    if 0 <= choice_idx < len(prompt.options):
                        return prompt.options[choice_idx]
                except ValueError:
                    # Try as text match
                    response_lower = response.lower()
                    for option in prompt.options:
                        if option.lower().startswith(response_lower):
                            return option
                
                print(f"Please choose a number 1-{len(prompt.options)} or type the option")
                
            except Exception:
                print("Please enter a valid choice")
    
    def _collect_confirmation(self, prompt: FeedbackPrompt) -> bool:
        """Collect confirmation input."""
        while True:
            response = input("> ").strip().lower()
            
            if not response and prompt.timeout:
                print("⏱️  Timeout - assuming no")
                return False
            
            if response in ['y', 'yes', '1', 'true']:
                return True
            elif response in ['n', 'no', '0', 'false']:
                return False
            else:
                print("Please enter y/yes or n/no")
    
    def _collect_text(self, prompt: FeedbackPrompt) -> str:
        """Collect text input."""
        print("(Enter on empty line to finish)")
        lines = []
        
        while True:
            line = input("> ")
            if not line:
                break
            lines.append(line)
        
        return "\n".join(lines)
    
    def _collect_review(self, prompt: FeedbackPrompt) -> Dict[str, Any]:
        """Collect review feedback."""
        review = {}
        
        # Overall rating
        print("\nOverall quality (1-5):")
        rating = self._collect_rating(FeedbackPrompt(
            prompt_id=f"{prompt.prompt_id}_rating",
            message="",
            interaction_type=InteractionType.RATING,
            min_rating=1,
            max_rating=5
        ))
        review["rating"] = rating
        
        # Specific feedback
        print("\nAny specific feedback? (optional)")
        feedback = input("> ").strip()
        if feedback:
            review["feedback"] = feedback
        
        # Issues found
        print("\nAny issues found? (y/n)")
        has_issues = input("> ").strip().lower() in ['y', 'yes']
        review["has_issues"] = has_issues
        
        if has_issues:
            print("Please describe the issues:")
            issues = self._collect_text(FeedbackPrompt(
                prompt_id=f"{prompt.prompt_id}_issues",
                message="",
                interaction_type=InteractionType.TEXT
            ))
            review["issues"] = issues
        
        return review
    
    def request_feedback(self,
                        task_id: str,
                        message: str,
                        interaction_type: InteractionType = InteractionType.TEXT,
                        options: Optional[List[str]] = None,
                        context: Optional[Dict[str, Any]] = None,
                        callback: Optional[Callable] = None,
                        timeout: Optional[int] = None) -> str:
        """Request interactive feedback from user.
        
        Args:
            task_id: Task identifier
            message: Feedback prompt message
            interaction_type: Type of interaction
            options: Options for choice interaction
            context: Additional context
            callback: Callback for response
            timeout: Response timeout in seconds
            
        Returns:
            Prompt ID
        """
        prompt_id = f"prompt_{datetime.now().timestamp()}"
        
        prompt = FeedbackPrompt(
            prompt_id=prompt_id,
            message=message,
            interaction_type=interaction_type,
            options=options,
            timeout=timeout,
            context=context or {}
        )
        
        if self.auto_mode:
            # Auto-respond
            response = self._auto_respond(prompt)
            
            # Save feedback
            self._save_feedback(task_id, prompt, response)
            
            if callback:
                callback(response)
        else:
            # Queue for interactive processing
            self.prompt_queue.put((prompt, lambda r: self._handle_response(
                task_id, prompt, r, callback
            )))
        
        return prompt_id
    
    def _auto_respond(self, prompt: FeedbackPrompt) -> Any:
        """Generate automatic response for non-interactive mode."""
        if prompt.interaction_type == InteractionType.RATING:
            # Default to middle rating
            return (prompt.min_rating + prompt.max_rating) // 2
        
        elif prompt.interaction_type == InteractionType.CHOICE:
            # Default to first option
            return prompt.options[0] if prompt.options else None
        
        elif prompt.interaction_type == InteractionType.CONFIRMATION:
            # Default to yes
            return True
        
        elif prompt.interaction_type == InteractionType.TEXT:
            # Default to empty
            return "Auto-generated response"
        
        elif prompt.interaction_type == InteractionType.REVIEW:
            # Default review
            return {
                "rating": 3,
                "feedback": "Auto-generated review",
                "has_issues": False
            }
        
        return None
    
    def _handle_response(self, 
                        task_id: str,
                        prompt: FeedbackPrompt,
                        response: Any,
                        callback: Optional[Callable]):
        """Handle user response."""
        # Save feedback
        self._save_feedback(task_id, prompt, response)
        
        # Call user callback
        if callback:
            try:
                callback(response)
            except Exception as e:
                logger.error(f"Error in user callback: {e}")
    
    def _save_feedback(self, task_id: str, prompt: FeedbackPrompt, response: Any):
        """Save feedback to storage."""
        try:
            # Create feedback model based on response
            if prompt.interaction_type == InteractionType.RATING:
                quality_score = response / prompt.max_rating if response else 0.5
                feedback = FeedbackModel(
                    feedback_id=f"interactive_{prompt.prompt_id}",
                    task_id=task_id,
                    feedback_type=FeedbackType.REVIEW,
                    message=f"User rating: {response}/{prompt.max_rating}",
                    timestamp=datetime.now(),
                    metrics={"quality_score": quality_score, "rating": response},
                    context=prompt.context,
                    tags=["interactive", "rating"]
                )
                
            elif prompt.interaction_type == InteractionType.REVIEW:
                feedback = FeedbackModel(
                    feedback_id=f"interactive_{prompt.prompt_id}",
                    task_id=task_id,
                    feedback_type=FeedbackType.REVIEW,
                    message="User review",
                    timestamp=datetime.now(),
                    metrics=response if isinstance(response, dict) else {},
                    context=prompt.context,
                    tags=["interactive", "review"]
                )
                
            else:
                # Generic feedback
                feedback = create_info_feedback(
                    task_id=task_id,
                    message=str(response) if response else "No response",
                    details={
                        "prompt": prompt.message,
                        "interaction_type": prompt.interaction_type.value,
                        "response": response
                    },
                    tags=["interactive", prompt.interaction_type.value]
                )
            
            # Save to storage
            self.storage.save(feedback)
            
        except Exception as e:
            logger.error(f"Failed to save interactive feedback: {e}")
    
    def request_task_review(self,
                           task_id: str,
                           task_title: str,
                           task_output: str,
                           callback: Optional[Callable] = None) -> str:
        """Request review of task output.
        
        Args:
            task_id: Task identifier
            task_title: Task title
            task_output: Task output to review
            callback: Callback for review result
            
        Returns:
            Prompt ID
        """
        return self.request_feedback(
            task_id=task_id,
            message=f"Please review the output for task: {task_title}",
            interaction_type=InteractionType.REVIEW,
            context={
                "task_title": task_title,
                "content": task_output
            },
            callback=callback
        )
    
    def request_quality_rating(self,
                             task_id: str,
                             aspect: str,
                             callback: Optional[Callable] = None) -> str:
        """Request quality rating for specific aspect.
        
        Args:
            task_id: Task identifier
            aspect: Aspect to rate (e.g., "code quality", "performance")
            callback: Callback for rating
            
        Returns:
            Prompt ID
        """
        return self.request_feedback(
            task_id=task_id,
            message=f"Please rate the {aspect}:",
            interaction_type=InteractionType.RATING,
            min_rating=1,
            max_rating=5,
            callback=callback
        )
    
    def request_decision(self,
                        task_id: str,
                        question: str,
                        options: List[str],
                        callback: Optional[Callable] = None) -> str:
        """Request user decision between options.
        
        Args:
            task_id: Task identifier
            question: Decision question
            options: Available options
            callback: Callback for selected option
            
        Returns:
            Prompt ID
        """
        return self.request_feedback(
            task_id=task_id,
            message=question,
            interaction_type=InteractionType.CHOICE,
            options=options,
            callback=callback
        )
    
    def get_interaction_summary(self) -> Dict[str, Any]:
        """Get summary of interactions.
        
        Returns:
            Interaction statistics
        """
        total = len(self.interaction_history)
        
        summary = {
            "total_interactions": total,
            "by_type": {},
            "average_ratings": {},
            "recent_interactions": []
        }
        
        # Count by type
        ratings = []
        for interaction in self.interaction_history:
            prompt_type = interaction.get("context", {}).get("interaction_type", "unknown")
            summary["by_type"][prompt_type] = summary["by_type"].get(prompt_type, 0) + 1
            
            # Collect ratings
            response = interaction.get("response")
            if isinstance(response, int):
                ratings.append(response)
            elif isinstance(response, dict) and "rating" in response:
                ratings.append(response["rating"])
        
        # Calculate average ratings
        if ratings:
            summary["average_rating"] = sum(ratings) / len(ratings)
            summary["rating_distribution"] = {
                i: ratings.count(i) for i in range(1, 6)
            }
        
        # Recent interactions
        summary["recent_interactions"] = self.interaction_history[-10:]
        
        return summary


class InteractiveFeedbackUI:
    """Simple UI for displaying feedback requests."""
    
    def __init__(self):
        self.active = False
        
    def show_notification(self, message: str, urgency: str = "normal"):
        """Show desktop notification if available."""
        try:
            # Try to use system notification
            if sys.platform == "darwin":  # macOS
                os.system(f'''
                    osascript -e 'display notification "{message}" with title "Claude Orchestrator Feedback"'
                ''')
            elif sys.platform.startswith("linux"):
                os.system(f'notify-send "Claude Orchestrator Feedback" "{message}"')
            # Windows would use different method
        except Exception:
            # Fallback to console
            print(f"\n🔔 NOTIFICATION: {message}\n")
    
    def create_feedback_window(self):
        """Create a simple feedback window (future enhancement)."""
        # This could be implemented with tkinter or other GUI library
        pass


# Integration helper
class InteractiveFeedbackIntegration:
    """Integrates interactive feedback with orchestrator."""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.collector = InteractiveFeedbackCollector(
            storage=getattr(orchestrator, 'feedback_storage', None),
            auto_mode=getattr(orchestrator.config, 'auto_feedback', True)
        )
        
    def on_task_complete(self, task_id: str, task_title: str, output: str):
        """Called when a task completes."""
        if not self.collector.auto_mode:
            # Request review for important tasks
            if "critical" in task_title.lower() or "important" in task_title.lower():
                self.collector.request_task_review(
                    task_id=task_id,
                    task_title=task_title,
                    task_output=output,
                    callback=lambda review: self._handle_task_review(task_id, review)
                )
    
    def on_decision_point(self, task_id: str, question: str, options: List[str]) -> str:
        """Called at decision points."""
        if self.collector.auto_mode:
            # Auto-select first option
            return options[0]
        
        # Wait for user decision
        result_queue = queue.Queue()
        
        self.collector.request_decision(
            task_id=task_id,
            question=question,
            options=options,
            callback=lambda choice: result_queue.put(choice)
        )
        
        # Wait for response
        try:
            return result_queue.get(timeout=300)  # 5 minute timeout
        except queue.Empty:
            return options[0]  # Default to first option
    
    def _handle_task_review(self, task_id: str, review: Dict[str, Any]):
        """Handle task review results."""
        if review.get("has_issues") and hasattr(self.orchestrator, 'review_queue'):
            # Flag for additional review
            logger.info(f"Task {task_id} flagged for additional review based on user feedback")


# Create convenience function
def create_interactive_feedback(config: Optional[Dict[str, Any]] = None) -> InteractiveFeedbackCollector:
    """Create interactive feedback collector.
    
    Args:
        config: Optional configuration
        
    Returns:
        Configured collector
    """
    auto_mode = config.get("auto_mode", True) if config else True
    storage = create_feedback_storage(config)
    
    return InteractiveFeedbackCollector(
        storage=storage,
        auto_mode=auto_mode
    )