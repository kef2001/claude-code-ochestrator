"""Interactive feedback interface for Claude Orchestrator"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import threading
import queue
from pathlib import Path

try:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)


class FeedbackRequestType(Enum):
    """Types of feedback requests"""
    TASK_REVIEW = "task_review"
    ERROR_RESOLUTION = "error_resolution"
    QUALITY_ASSESSMENT = "quality_assessment"
    DECISION_POINT = "decision_point"
    INTERVENTION = "intervention"


@dataclass
class FeedbackRequest:
    """Represents a feedback request"""
    request_id: str
    request_type: FeedbackRequestType
    title: str
    description: str
    context: Dict[str, Any]
    options: Optional[List[str]] = None
    priority: str = "medium"
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class FeedbackResponse:
    """User's response to a feedback request"""
    request_id: str
    response_type: str
    value: Any
    timestamp: datetime = None
    duration_seconds: float = 0.0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class InteractiveFeedbackUI:
    """Interactive UI for collecting user feedback"""
    
    def __init__(self, auto_mode: bool = False):
        """Initialize the feedback UI
        
        Args:
            auto_mode: If True, automatically respond to low-priority requests
        """
        self.auto_mode = auto_mode
        self.console = Console() if RICH_AVAILABLE else None
        self.pending_requests: queue.Queue = queue.Queue()
        self.responses: Dict[str, FeedbackResponse] = {}
        self.active = False
        self._ui_thread = None
        self._stop_event = threading.Event()
        
        # Callbacks
        self.on_response: Optional[Callable[[FeedbackResponse], None]] = None
        
    def start(self):
        """Start the interactive feedback UI"""
        if self.active:
            return
            
        self.active = True
        self._stop_event.clear()
        
        # Start UI thread
        self._ui_thread = threading.Thread(target=self._ui_loop)
        self._ui_thread.daemon = True
        self._ui_thread.start()
        
        logger.info("Interactive feedback UI started")
        
    def stop(self):
        """Stop the interactive feedback UI"""
        if not self.active:
            return
            
        self.active = False
        self._stop_event.set()
        
        # Wait for UI thread to finish
        if self._ui_thread:
            self._ui_thread.join(timeout=5)
            
        logger.info("Interactive feedback UI stopped")
        
    def request_feedback(self, request: FeedbackRequest) -> Optional[FeedbackResponse]:
        """Request feedback from the user
        
        Args:
            request: The feedback request
            
        Returns:
            FeedbackResponse if available, None if queued
        """
        # In auto mode, handle low-priority requests automatically
        if self.auto_mode and request.priority == "low":
            return self._auto_respond(request)
            
        # Queue the request
        self.pending_requests.put(request)
        
        # If not running in background, process immediately
        if not self.active:
            return self._process_request(request)
            
        return None
        
    def _ui_loop(self):
        """Main UI loop for processing feedback requests"""
        while not self._stop_event.is_set():
            try:
                # Wait for request with timeout
                request = self.pending_requests.get(timeout=1.0)
                
                # Process the request
                response = self._process_request(request)
                
                if response:
                    self.responses[request.request_id] = response
                    
                    # Trigger callback
                    if self.on_response:
                        self.on_response(response)
                        
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in feedback UI loop: {e}")
                
    def _process_request(self, request: FeedbackRequest) -> Optional[FeedbackResponse]:
        """Process a single feedback request"""
        start_time = datetime.now()
        
        if RICH_AVAILABLE and self.console:
            response = self._process_rich_request(request)
        else:
            response = self._process_simple_request(request)
            
        if response:
            response.duration_seconds = (datetime.now() - start_time).total_seconds()
            
        return response
        
    def _process_rich_request(self, request: FeedbackRequest) -> Optional[FeedbackResponse]:
        """Process request using rich UI"""
        # Create panel with request information
        panel = Panel(
            f"[bold]{request.title}[/bold]\n\n{request.description}",
            title=f"[cyan]Feedback Request - {request.request_type.value}[/cyan]",
            title_align="left",
            border_style="cyan"
        )
        
        self.console.print("\n")
        self.console.print(panel)
        
        # Show context if available
        if request.context:
            self._show_context(request.context)
            
        # Handle different request types
        if request.request_type == FeedbackRequestType.TASK_REVIEW:
            return self._handle_task_review(request)
        elif request.request_type == FeedbackRequestType.ERROR_RESOLUTION:
            return self._handle_error_resolution(request)
        elif request.request_type == FeedbackRequestType.QUALITY_ASSESSMENT:
            return self._handle_quality_assessment(request)
        elif request.request_type == FeedbackRequestType.DECISION_POINT:
            return self._handle_decision_point(request)
        elif request.request_type == FeedbackRequestType.INTERVENTION:
            return self._handle_intervention(request)
        else:
            return self._handle_generic_request(request)
            
    def _process_simple_request(self, request: FeedbackRequest) -> Optional[FeedbackResponse]:
        """Process request using simple text UI"""
        print(f"\n{'='*60}")
        print(f"FEEDBACK REQUEST: {request.request_type.value}")
        print(f"Title: {request.title}")
        print(f"Description: {request.description}")
        print(f"{'='*60}")
        
        # Show context
        if request.context:
            print("\nContext:")
            for key, value in request.context.items():
                print(f"  {key}: {value}")
                
        # Get response based on type
        if request.options:
            print("\nOptions:")
            for i, option in enumerate(request.options, 1):
                print(f"  {i}. {option}")
            
            while True:
                try:
                    choice = input("\nSelect option (number): ").strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(request.options):
                        value = request.options[idx]
                        break
                    else:
                        print("Invalid option. Please try again.")
                except (ValueError, KeyboardInterrupt):
                    return None
        else:
            value = input("\nYour response: ").strip()
            if not value:
                return None
                
        return FeedbackResponse(
            request_id=request.request_id,
            response_type="user_input",
            value=value
        )
        
    def _show_context(self, context: Dict[str, Any]):
        """Display context information"""
        if not context:
            return
            
        table = Table(title="Context", show_header=True)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        
        for key, value in context.items():
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, indent=2)
            else:
                value_str = str(value)
            table.add_row(key, value_str)
            
        self.console.print(table)
        
    def _handle_task_review(self, request: FeedbackRequest) -> Optional[FeedbackResponse]:
        """Handle task review feedback request"""
        # Show task details
        task_info = request.context.get('task', {})
        
        if RICH_AVAILABLE and self.console:
            table = Table(title="Task Review", show_header=False)
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="white")
            
            table.add_row("Task ID", str(task_info.get('id', 'N/A')))
            table.add_row("Title", task_info.get('title', 'N/A'))
            table.add_row("Status", task_info.get('status', 'N/A'))
            table.add_row("Output", task_info.get('output', 'N/A')[:200] + "...")
            
            self.console.print(table)
            
            # Get review decision
            approve = Confirm.ask("Approve this task?", default=True)
            
            if not approve:
                feedback = Prompt.ask("Please provide feedback for improvement")
                return FeedbackResponse(
                    request_id=request.request_id,
                    response_type="task_review",
                    value={
                        "approved": False,
                        "feedback": feedback
                    }
                )
            else:
                return FeedbackResponse(
                    request_id=request.request_id,
                    response_type="task_review",
                    value={"approved": True}
                )
        else:
            # Simple text UI
            print(f"\nTask ID: {task_info.get('id', 'N/A')}")
            print(f"Title: {task_info.get('title', 'N/A')}")
            print(f"Status: {task_info.get('status', 'N/A')}")
            
            approve = input("\nApprove this task? (y/n): ").lower() == 'y'
            
            if not approve:
                feedback = input("Please provide feedback: ")
                value = {"approved": False, "feedback": feedback}
            else:
                value = {"approved": True}
                
            return FeedbackResponse(
                request_id=request.request_id,
                response_type="task_review",
                value=value
            )
            
    def _handle_error_resolution(self, request: FeedbackRequest) -> Optional[FeedbackResponse]:
        """Handle error resolution feedback request"""
        error_info = request.context.get('error', {})
        
        options = [
            "Retry the operation",
            "Skip this task",
            "Modify parameters and retry",
            "Abort the process",
            "View detailed error information"
        ]
        
        if RICH_AVAILABLE and self.console:
            self.console.print(f"\n[red]Error:[/red] {error_info.get('message', 'Unknown error')}")
            
            choice = Prompt.ask(
                "How would you like to proceed?",
                choices=[str(i) for i in range(1, len(options) + 1)],
                default="1"
            )
            
            selected = options[int(choice) - 1]
            
            # Handle "View detailed error"
            if selected == "View detailed error information":
                self.console.print(Panel(str(error_info), title="Error Details"))
                return self._handle_error_resolution(request)  # Recurse
                
        else:
            print(f"\nError: {error_info.get('message', 'Unknown error')}")
            print("\nOptions:")
            for i, opt in enumerate(options, 1):
                print(f"  {i}. {opt}")
                
            choice = input("\nSelect option: ")
            selected = options[int(choice) - 1]
            
        return FeedbackResponse(
            request_id=request.request_id,
            response_type="error_resolution",
            value=selected
        )
        
    def _handle_quality_assessment(self, request: FeedbackRequest) -> Optional[FeedbackResponse]:
        """Handle quality assessment feedback request"""
        if RICH_AVAILABLE and self.console:
            rating = Prompt.ask(
                "Rate the quality (1-5)",
                choices=["1", "2", "3", "4", "5"],
                default="3"
            )
            
            comments = Prompt.ask("Additional comments (optional)", default="")
        else:
            rating = input("Rate the quality (1-5): ")
            comments = input("Additional comments (optional): ")
            
        return FeedbackResponse(
            request_id=request.request_id,
            response_type="quality_assessment",
            value={
                "rating": int(rating),
                "comments": comments
            }
        )
        
    def _handle_decision_point(self, request: FeedbackRequest) -> Optional[FeedbackResponse]:
        """Handle decision point feedback request"""
        if not request.options:
            request.options = ["Continue", "Modify", "Abort"]
            
        if RICH_AVAILABLE and self.console:
            choice = Prompt.ask(
                "Select decision",
                choices=request.options,
                default=request.options[0]
            )
        else:
            print("\nOptions:")
            for i, opt in enumerate(request.options, 1):
                print(f"  {i}. {opt}")
            
            idx = int(input("\nSelect option: ")) - 1
            choice = request.options[idx]
            
        return FeedbackResponse(
            request_id=request.request_id,
            response_type="decision",
            value=choice
        )
        
    def _handle_intervention(self, request: FeedbackRequest) -> Optional[FeedbackResponse]:
        """Handle intervention request"""
        if RICH_AVAILABLE and self.console:
            self.console.print(Panel(
                "[yellow]Intervention Required[/yellow]\n\n" + request.description,
                border_style="yellow"
            ))
            
            action = Prompt.ask(
                "Action to take",
                default="Continue with caution"
            )
        else:
            print("\n⚠️  INTERVENTION REQUIRED")
            print(request.description)
            action = input("\nAction to take: ")
            
        return FeedbackResponse(
            request_id=request.request_id,
            response_type="intervention",
            value=action
        )
        
    def _handle_generic_request(self, request: FeedbackRequest) -> Optional[FeedbackResponse]:
        """Handle generic feedback request"""
        if request.options:
            return self._handle_decision_point(request)
        else:
            if RICH_AVAILABLE and self.console:
                value = Prompt.ask("Your response")
            else:
                value = input("Your response: ")
                
            return FeedbackResponse(
                request_id=request.request_id,
                response_type="generic",
                value=value
            )
            
    def _auto_respond(self, request: FeedbackRequest) -> FeedbackResponse:
        """Automatically respond to low-priority requests"""
        # Default auto responses
        if request.request_type == FeedbackRequestType.TASK_REVIEW:
            value = {"approved": True}
        elif request.request_type == FeedbackRequestType.QUALITY_ASSESSMENT:
            value = {"rating": 3, "comments": "Auto-approved"}
        elif request.request_type == FeedbackRequestType.DECISION_POINT:
            value = request.options[0] if request.options else "Continue"
        else:
            value = "Auto-response: OK"
            
        logger.info(f"Auto-responding to {request.request_type.value}: {value}")
        
        return FeedbackResponse(
            request_id=request.request_id,
            response_type="auto",
            value=value
        )
        
    def get_pending_count(self) -> int:
        """Get number of pending feedback requests"""
        return self.pending_requests.qsize()
        
    def clear_pending(self):
        """Clear all pending requests"""
        while not self.pending_requests.empty():
            try:
                self.pending_requests.get_nowait()
            except queue.Empty:
                break


# Singleton instance
_ui_instance: Optional[InteractiveFeedbackUI] = None


def get_feedback_ui(auto_mode: bool = False) -> InteractiveFeedbackUI:
    """Get or create the feedback UI instance"""
    global _ui_instance
    
    if _ui_instance is None:
        _ui_instance = InteractiveFeedbackUI(auto_mode)
        
    return _ui_instance