"""Feedback Collection API for Worker Tasks."""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

from .feedback_model import (
    FeedbackModel, FeedbackType, FeedbackSeverity, FeedbackCategory,
    create_success_feedback, create_error_feedback, create_warning_feedback,
    create_performance_feedback
)
from .feedback_storage import FeedbackStorage
from .feedback_analyzer import FeedbackAnalyzer
from .storage_factory import create_feedback_storage

logger = logging.getLogger(__name__)


class FeedbackAPIHandler(BaseHTTPRequestHandler):
    """HTTP handler for feedback API endpoints."""
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)
        
        if path == '/api/feedback/task':
            # Get feedback for a specific task
            task_id = query_params.get('task_id', [None])[0]
            if task_id:
                self._handle_get_task_feedback(task_id)
            else:
                self._send_error(400, "Missing task_id parameter")
                
        elif path == '/api/feedback/worker':
            # Get worker performance
            worker_id = query_params.get('worker_id', [None])[0]
            if worker_id:
                self._handle_get_worker_performance(worker_id)
            else:
                self._send_error(400, "Missing worker_id parameter")
                
        elif path == '/api/feedback/summary':
            # Get feedback summary
            self._handle_get_feedback_summary()
            
        elif path == '/api/feedback/trends':
            # Get feedback trends
            days = int(query_params.get('days', [7])[0])
            self._handle_get_feedback_trends(days)
            
        else:
            self._send_error(404, "Not found")
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/api/feedback/submit':
            # Submit new feedback
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                feedback_data = json.loads(post_data.decode('utf-8'))
                self._handle_submit_feedback(feedback_data)
            except json.JSONDecodeError:
                self._send_error(400, "Invalid JSON data")
                
        elif self.path == '/api/feedback/batch':
            # Submit batch feedback
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                batch_data = json.loads(post_data.decode('utf-8'))
                self._handle_batch_feedback(batch_data)
            except json.JSONDecodeError:
                self._send_error(400, "Invalid JSON data")
                
        else:
            self._send_error(404, "Not found")
    
    def _handle_get_task_feedback(self, task_id: str):
        """Get feedback for a specific task."""
        try:
            storage = self.server.feedback_storage
            feedback_list = storage.get_by_task(task_id)
            
            response_data = {
                "task_id": task_id,
                "feedback_count": len(feedback_list),
                "feedback": [fb.to_dict() for fb in feedback_list]
            }
            
            self._send_json_response(response_data)
            
        except Exception as e:
            logger.error(f"Error getting task feedback: {e}")
            self._send_error(500, str(e))
    
    def _handle_get_worker_performance(self, worker_id: str):
        """Get worker performance data."""
        try:
            analyzer = FeedbackAnalyzer(self.server.feedback_storage)
            performance = analyzer.get_worker_performance(worker_id)
            
            if performance:
                response_data = {
                    "worker_id": worker_id,
                    "total_tasks": performance.total_tasks,
                    "successful_tasks": performance.successful_tasks,
                    "failed_tasks": performance.failed_tasks,
                    "success_rate": performance.success_rate,
                    "average_response_time": performance.average_response_time,
                    "capability_scores": performance.capability_scores,
                    "recent_errors": performance.recent_errors[-5:]  # Last 5 errors
                }
            else:
                response_data = {
                    "worker_id": worker_id,
                    "message": "No performance data available"
                }
            
            self._send_json_response(response_data)
            
        except Exception as e:
            logger.error(f"Error getting worker performance: {e}")
            self._send_error(500, str(e))
    
    def _handle_get_feedback_summary(self):
        """Get overall feedback summary."""
        try:
            analyzer = FeedbackAnalyzer(self.server.feedback_storage)
            
            # Get recent feedback
            all_feedback = self.server.feedback_storage.get_all(limit=1000)
            
            summary = {
                "total_feedback": len(all_feedback),
                "by_type": {},
                "by_severity": {},
                "by_category": {},
                "recent_feedback": []
            }
            
            # Count by type, severity, and category
            for fb in all_feedback:
                fb_type = fb.feedback_type.value
                summary["by_type"][fb_type] = summary["by_type"].get(fb_type, 0) + 1
                
                if fb.severity:
                    severity = fb.severity.value
                    summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
                
                if fb.category:
                    category = fb.category.value
                    summary["by_category"][category] = summary["by_category"].get(category, 0) + 1
            
            # Add recent feedback
            recent = sorted(all_feedback, key=lambda x: x.timestamp, reverse=True)[:10]
            summary["recent_feedback"] = [fb.to_dict() for fb in recent]
            
            self._send_json_response(summary)
            
        except Exception as e:
            logger.error(f"Error getting feedback summary: {e}")
            self._send_error(500, str(e))
    
    def _handle_get_feedback_trends(self, days: int):
        """Get feedback trends over time."""
        try:
            analyzer = FeedbackAnalyzer(self.server.feedback_storage)
            trends = analyzer.analyze_trends(days=days)
            
            if trends:
                response_data = {
                    "period_days": days,
                    "daily_counts": trends.daily_counts,
                    "success_rate_trend": trends.success_rate_trend,
                    "average_response_time_trend": trends.average_response_time_trend,
                    "error_frequency": trends.error_frequency,
                    "common_patterns": trends.common_patterns[:10]  # Top 10 patterns
                }
            else:
                response_data = {
                    "period_days": days,
                    "message": "No trend data available"
                }
            
            self._send_json_response(response_data)
            
        except Exception as e:
            logger.error(f"Error getting feedback trends: {e}")
            self._send_error(500, str(e))
    
    def _handle_submit_feedback(self, feedback_data: Dict[str, Any]):
        """Submit new feedback."""
        try:
            # Validate required fields
            if 'task_id' not in feedback_data:
                self._send_error(400, "Missing required field: task_id")
                return
            
            # Determine feedback type
            feedback_type = feedback_data.get('type', 'info')
            
            # Create appropriate feedback based on type
            if feedback_type == 'success':
                feedback = create_success_feedback(
                    task_id=feedback_data['task_id'],
                    message=feedback_data.get('message', ''),
                    metrics=feedback_data.get('metrics'),
                    worker_id=feedback_data.get('worker_id'),
                    tags=feedback_data.get('tags', [])
                )
            elif feedback_type == 'error':
                feedback = create_error_feedback(
                    task_id=feedback_data['task_id'],
                    message=feedback_data.get('message', ''),
                    error_details=feedback_data.get('error_details', {}),
                    worker_id=feedback_data.get('worker_id'),
                    tags=feedback_data.get('tags', [])
                )
            elif feedback_type == 'warning':
                feedback = create_warning_feedback(
                    task_id=feedback_data['task_id'],
                    message=feedback_data.get('message', ''),
                    details=feedback_data.get('details', {}),
                    worker_id=feedback_data.get('worker_id'),
                    tags=feedback_data.get('tags', [])
                )
            elif feedback_type == 'performance':
                feedback = create_performance_feedback(
                    task_id=feedback_data['task_id'],
                    message=feedback_data.get('message', ''),
                    execution_time=feedback_data.get('execution_time', 0),
                    worker_id=feedback_data.get('worker_id'),
                    tags=feedback_data.get('tags', [])
                )
            else:
                # Generic feedback
                feedback = FeedbackModel(
                    feedback_id=f"fb_{datetime.now().timestamp()}",
                    task_id=feedback_data['task_id'],
                    feedback_type=FeedbackType.INFO,
                    message=feedback_data.get('message', ''),
                    timestamp=datetime.now(),
                    worker_id=feedback_data.get('worker_id'),
                    tags=feedback_data.get('tags', [])
                )
            
            # Save feedback
            self.server.feedback_storage.save(feedback)
            
            response_data = {
                "success": True,
                "feedback_id": feedback.feedback_id,
                "message": "Feedback submitted successfully"
            }
            
            self._send_json_response(response_data, status=201)
            
        except Exception as e:
            logger.error(f"Error submitting feedback: {e}")
            self._send_error(500, str(e))
    
    def _handle_batch_feedback(self, batch_data: Dict[str, Any]):
        """Submit batch feedback."""
        try:
            feedback_list = batch_data.get('feedback', [])
            if not feedback_list:
                self._send_error(400, "No feedback items provided")
                return
            
            results = []
            errors = []
            
            for idx, fb_data in enumerate(feedback_list):
                try:
                    # Process each feedback item
                    if 'task_id' not in fb_data:
                        errors.append(f"Item {idx}: Missing task_id")
                        continue
                    
                    # Create feedback (similar to single submission)
                    feedback_type = fb_data.get('type', 'info')
                    
                    if feedback_type == 'success':
                        feedback = create_success_feedback(
                            task_id=fb_data['task_id'],
                            message=fb_data.get('message', ''),
                            worker_id=fb_data.get('worker_id')
                        )
                    elif feedback_type == 'error':
                        feedback = create_error_feedback(
                            task_id=fb_data['task_id'],
                            message=fb_data.get('message', ''),
                            worker_id=fb_data.get('worker_id')
                        )
                    else:
                        feedback = FeedbackModel(
                            feedback_id=f"fb_{datetime.now().timestamp()}_{idx}",
                            task_id=fb_data['task_id'],
                            feedback_type=FeedbackType.INFO,
                            message=fb_data.get('message', ''),
                            timestamp=datetime.now(),
                            worker_id=fb_data.get('worker_id')
                        )
                    
                    self.server.feedback_storage.save(feedback)
                    results.append(feedback.feedback_id)
                    
                except Exception as e:
                    errors.append(f"Item {idx}: {str(e)}")
            
            response_data = {
                "success": len(errors) == 0,
                "processed": len(results),
                "failed": len(errors),
                "feedback_ids": results,
                "errors": errors
            }
            
            self._send_json_response(response_data, status=201 if errors else 200)
            
        except Exception as e:
            logger.error(f"Error processing batch feedback: {e}")
            self._send_error(500, str(e))
    
    def _send_json_response(self, data: Dict[str, Any], status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))
    
    def _send_error(self, status: int, message: str):
        """Send error response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        error_data = {
            "error": True,
            "message": message,
            "status": status
        }
        self.wfile.write(json.dumps(error_data).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to reduce logging noise."""
        if self.server.verbose_logging:
            logger.info(f"API Request: {format % args}")


class FeedbackAPIServer:
    """Feedback API server."""
    
    def __init__(self, 
                 port: int = 8080,
                 feedback_storage: Optional[FeedbackStorage] = None,
                 verbose_logging: bool = False):
        self.port = port
        self.feedback_storage = feedback_storage or create_feedback_storage()
        self.verbose_logging = verbose_logging
        self.server = None
        self.server_thread = None
        
    def start(self):
        """Start the API server."""
        try:
            # Create HTTP server
            server_address = ('', self.port)
            self.server = HTTPServer(server_address, FeedbackAPIHandler)
            
            # Pass storage to server
            self.server.feedback_storage = self.feedback_storage
            self.server.verbose_logging = self.verbose_logging
            
            # Start server in background thread
            self.server_thread = threading.Thread(
                target=self.server.serve_forever,
                daemon=True,
                name="FeedbackAPIServer"
            )
            self.server_thread.start()
            
            logger.info(f"Feedback API server started on port {self.port}")
            logger.info(f"API endpoints available at http://localhost:{self.port}/api/feedback/")
            
        except Exception as e:
            logger.error(f"Failed to start feedback API server: {e}")
            raise
    
    def stop(self):
        """Stop the API server."""
        if self.server:
            self.server.shutdown()
            self.server_thread.join(timeout=5)
            logger.info("Feedback API server stopped")
    
    def get_api_info(self) -> Dict[str, Any]:
        """Get API endpoint information."""
        return {
            "base_url": f"http://localhost:{self.port}",
            "endpoints": {
                "GET /api/feedback/task": "Get feedback for a specific task",
                "GET /api/feedback/worker": "Get worker performance data",
                "GET /api/feedback/summary": "Get overall feedback summary",
                "GET /api/feedback/trends": "Get feedback trends over time",
                "POST /api/feedback/submit": "Submit new feedback",
                "POST /api/feedback/batch": "Submit batch feedback"
            },
            "examples": {
                "get_task_feedback": f"GET http://localhost:{self.port}/api/feedback/task?task_id=123",
                "submit_feedback": {
                    "url": f"POST http://localhost:{self.port}/api/feedback/submit",
                    "body": {
                        "task_id": "123",
                        "type": "success",
                        "message": "Task completed successfully",
                        "worker_id": "worker-1",
                        "metrics": {
                            "execution_time": 45.2,
                            "quality_score": 0.95
                        }
                    }
                }
            }
        }


class FeedbackCollector:
    """High-level feedback collection interface."""
    
    def __init__(self, storage: Optional[FeedbackStorage] = None):
        self.storage = storage or create_feedback_storage()
        self.api_server = None
        
    def start_api_server(self, port: int = 8080) -> FeedbackAPIServer:
        """Start the feedback API server.
        
        Args:
            port: Port to listen on
            
        Returns:
            API server instance
        """
        self.api_server = FeedbackAPIServer(
            port=port,
            feedback_storage=self.storage
        )
        self.api_server.start()
        return self.api_server
    
    def stop_api_server(self):
        """Stop the feedback API server."""
        if self.api_server:
            self.api_server.stop()
            self.api_server = None
    
    def collect_task_feedback(self,
                            task_id: str,
                            success: bool,
                            message: str = "",
                            worker_id: Optional[str] = None,
                            execution_time: Optional[float] = None,
                            error_details: Optional[Dict[str, Any]] = None) -> str:
        """Collect feedback for a task completion.
        
        Args:
            task_id: Task identifier
            success: Whether task succeeded
            message: Feedback message
            worker_id: Worker that executed the task
            execution_time: Task execution time in seconds
            error_details: Error details if failed
            
        Returns:
            Feedback ID
        """
        if success:
            if execution_time:
                feedback = create_performance_feedback(
                    task_id=task_id,
                    message=message or "Task completed successfully",
                    execution_time=execution_time,
                    worker_id=worker_id
                )
            else:
                feedback = create_success_feedback(
                    task_id=task_id,
                    message=message or "Task completed successfully",
                    worker_id=worker_id
                )
        else:
            feedback = create_error_feedback(
                task_id=task_id,
                message=message or "Task failed",
                error_details=error_details or {},
                worker_id=worker_id
            )
        
        self.storage.save(feedback)
        return feedback.feedback_id
    
    def collect_worker_feedback(self,
                              worker_id: str,
                              task_id: str,
                              performance_score: float,
                              message: str = "") -> str:
        """Collect feedback about worker performance.
        
        Args:
            worker_id: Worker identifier
            task_id: Task being performed
            performance_score: Performance score (0.0-1.0)
            message: Additional feedback
            
        Returns:
            Feedback ID
        """
        feedback = FeedbackModel(
            feedback_id=f"fb_worker_{datetime.now().timestamp()}",
            task_id=task_id,
            feedback_type=FeedbackType.PERFORMANCE,
            message=message or f"Worker performance: {performance_score:.2f}",
            timestamp=datetime.now(),
            worker_id=worker_id,
            metrics={
                "performance_score": performance_score
            },
            tags=["worker_performance"]
        )
        
        self.storage.save(feedback)
        return feedback.feedback_id
    
    def get_task_summary(self, task_id: str) -> Dict[str, Any]:
        """Get feedback summary for a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task feedback summary
        """
        analyzer = FeedbackAnalyzer(self.storage)
        analysis = analyzer.analyze_task(task_id)
        
        if analysis:
            return {
                "task_id": task_id,
                "feedback_count": analysis.feedback_count,
                "success": analysis.success,
                "execution_time": analysis.execution_time,
                "quality_score": analysis.quality_score,
                "error_count": len(analysis.error_messages),
                "warning_count": len(analysis.warnings)
            }
        
        return {
            "task_id": task_id,
            "feedback_count": 0,
            "message": "No feedback available"
        }


# Convenience function to create and start feedback collection
def create_feedback_collector(config: Optional[Dict[str, Any]] = None) -> FeedbackCollector:
    """Create a feedback collector instance.
    
    Args:
        config: Optional configuration
        
    Returns:
        Configured FeedbackCollector
    """
    storage = create_feedback_storage(config)
    return FeedbackCollector(storage=storage)