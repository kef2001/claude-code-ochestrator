"""
Dynamic Worker Allocation System
Allocates workers based on task complexity and resource requirements
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import threading
from collections import deque, defaultdict
import re
import json

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels"""
    TRIVIAL = "trivial"      # Simple, quick tasks
    LOW = "low"              # Basic tasks
    MEDIUM = "medium"        # Standard tasks
    HIGH = "high"            # Complex tasks
    CRITICAL = "critical"    # Very complex, resource-intensive tasks


class WorkerCapability(Enum):
    """Worker capability types"""
    CODE = "code"                    # Code implementation
    RESEARCH = "research"            # Research and analysis
    DOCUMENTATION = "documentation"  # Documentation writing
    TESTING = "testing"             # Testing and QA
    REFACTORING = "refactoring"     # Code refactoring
    DEBUGGING = "debugging"         # Bug fixing
    DESIGN = "design"               # System design
    REVIEW = "review"               # Code review


@dataclass
class TaskRequirements:
    """Task requirements and characteristics"""
    complexity: TaskComplexity
    estimated_duration: int  # in minutes
    required_capabilities: Set[WorkerCapability]
    memory_intensive: bool = False
    cpu_intensive: bool = False
    requires_filesystem_access: bool = False
    requires_network_access: bool = False
    parallel_subtasks: int = 0  # Number of potential parallel subtasks
    priority: int = 1  # 1-10, higher is more priority
    dependencies: List[str] = field(default_factory=list)
    
    def get_resource_score(self) -> float:
        """Calculate resource requirement score"""
        score = 0.0
        
        # Base complexity score
        complexity_scores = {
            TaskComplexity.TRIVIAL: 1.0,
            TaskComplexity.LOW: 2.0,
            TaskComplexity.MEDIUM: 4.0,
            TaskComplexity.HIGH: 7.0,
            TaskComplexity.CRITICAL: 10.0
        }
        score += complexity_scores[self.complexity]
        
        # Resource modifiers
        if self.memory_intensive:
            score *= 1.5
        if self.cpu_intensive:
            score *= 1.3
        if self.requires_filesystem_access:
            score *= 1.1
        if self.requires_network_access:
            score *= 1.2
        
        # Duration modifier
        if self.estimated_duration > 60:  # > 1 hour
            score *= 1.4
        elif self.estimated_duration > 30:  # > 30 minutes
            score *= 1.2
        
        # Capability complexity
        score += len(self.required_capabilities) * 0.5
        
        return score


@dataclass
class WorkerProfile:
    """Worker profile and capabilities"""
    worker_id: str
    model_name: str
    capabilities: Set[WorkerCapability]
    max_complexity: TaskComplexity
    performance_score: float = 1.0  # Historical performance multiplier
    current_load: float = 0.0  # Current workload (0.0-1.0)
    max_concurrent_tasks: int = 1
    current_tasks: List[str] = field(default_factory=list)
    specialization_bonus: Dict[WorkerCapability, float] = field(default_factory=dict)
    last_assigned: Optional[datetime] = None
    total_tasks_completed: int = 0
    average_task_duration: float = 30.0  # minutes
    success_rate: float = 1.0
    
    def is_available(self) -> bool:
        """Check if worker is available for new tasks"""
        return len(self.current_tasks) < self.max_concurrent_tasks
    
    def can_handle_task(self, requirements: TaskRequirements) -> bool:
        """Check if worker can handle the task requirements"""
        # Check complexity
        complexity_order = [
            TaskComplexity.TRIVIAL,
            TaskComplexity.LOW,
            TaskComplexity.MEDIUM,
            TaskComplexity.HIGH,
            TaskComplexity.CRITICAL
        ]
        
        if complexity_order.index(requirements.complexity) > complexity_order.index(self.max_complexity):
            return False
        
        # Check capabilities
        if not requirements.required_capabilities.issubset(self.capabilities):
            return False
        
        return True
    
    def calculate_suitability_score(self, requirements: TaskRequirements, 
                                    feedback_analyzer=None) -> float:
        """Calculate how suitable this worker is for the task"""
        if not self.can_handle_task(requirements):
            return 0.0
        
        score = self.performance_score
        
        # Capability match bonus
        for capability in requirements.required_capabilities:
            if capability in self.specialization_bonus:
                score += self.specialization_bonus[capability]
            else:
                score += 0.5  # Base bonus for having the capability
        
        # Load balancing - prefer less loaded workers
        score *= (1.0 - self.current_load * 0.5)
        
        # Success rate bonus
        score *= self.success_rate
        
        # Complexity efficiency - prefer workers that match task complexity
        complexity_match = self._get_complexity_match_score(requirements.complexity)
        score *= complexity_match
        
        # Historical feedback bonus if analyzer is available
        if feedback_analyzer:
            try:
                # Get worker performance from feedback history
                from datetime import datetime, timedelta
                worker_perf = feedback_analyzer.get_worker_performance(
                    self.worker_id,
                    start_date=datetime.now() - timedelta(days=7)  # Last 7 days
                )
                
                if worker_perf and worker_perf.total_tasks > 0:
                    # Boost score based on historical success rate
                    historical_success_rate = worker_perf.success_rate
                    if historical_success_rate > 0.9:
                        score *= 1.2  # 20% bonus for excellent performance
                    elif historical_success_rate > 0.8:
                        score *= 1.1  # 10% bonus for good performance
                    elif historical_success_rate < 0.5:
                        score *= 0.8  # 20% penalty for poor performance
                    
                    # Consider average response time for the complexity level
                    if requirements.complexity in worker_perf.average_response_time_by_complexity:
                        avg_time = worker_perf.average_response_time_by_complexity[requirements.complexity]
                        expected_time = requirements.estimated_duration * 60  # Convert to seconds
                        
                        # Bonus for faster than expected, penalty for slower
                        if avg_time < expected_time * 0.8:
                            score *= 1.15  # 15% bonus for being consistently fast
                        elif avg_time > expected_time * 1.5:
                            score *= 0.9   # 10% penalty for being consistently slow
                    
                    # Consider capability-specific performance
                    for capability in requirements.required_capabilities:
                        cap_value = capability.value
                        if cap_value in worker_perf.capability_scores:
                            cap_score = worker_perf.capability_scores[cap_value]
                            # Adjust score based on capability-specific performance
                            score *= (0.8 + cap_score * 0.4)  # Scale from 0.8 to 1.2
                            
            except Exception as e:
                # Log but don't fail scoring if feedback analysis fails
                logger.debug(f"Failed to incorporate feedback in scoring: {e}")
        
        return score
    
    def _get_complexity_match_score(self, task_complexity: TaskComplexity) -> float:
        """Get score for how well worker complexity matches task complexity"""
        complexity_order = [
            TaskComplexity.TRIVIAL,
            TaskComplexity.LOW,
            TaskComplexity.MEDIUM,
            TaskComplexity.HIGH,
            TaskComplexity.CRITICAL
        ]
        
        worker_level = complexity_order.index(self.max_complexity)
        task_level = complexity_order.index(task_complexity)
        
        # Perfect match
        if worker_level == task_level:
            return 1.0
        # Worker is more capable than needed (slight penalty)
        elif worker_level > task_level:
            return 0.8 - (worker_level - task_level) * 0.1
        # Worker is less capable (already filtered out in can_handle_task)
        else:
            return 0.0


class TaskComplexityAnalyzer:
    """Analyzes task descriptions to determine complexity and requirements"""
    
    def __init__(self):
        # Keywords that indicate different aspects of complexity
        self.complexity_keywords = {
            TaskComplexity.TRIVIAL: [
                "fix typo", "update comment", "change variable name", "add import",
                "simple change", "quick fix", "minor update"
            ],
            TaskComplexity.LOW: [
                "add function", "create class", "write test", "update config",
                "implement method", "add feature", "simple"
            ],
            TaskComplexity.MEDIUM: [
                "implement api", "create module", "refactor", "optimize",
                "add authentication", "database", "integration"
            ],
            TaskComplexity.HIGH: [
                "architecture", "system design", "complex algorithm", "performance",
                "security", "large refactor", "multiple components"
            ],
            TaskComplexity.CRITICAL: [
                "entire system", "complete rewrite", "major architecture",
                "enterprise", "scalability", "distributed system"
            ]
        }
        
        self.capability_keywords = {
            WorkerCapability.CODE: [
                "implement", "code", "function", "class", "method", "algorithm",
                "programming", "develop", "write"
            ],
            WorkerCapability.RESEARCH: [
                "research", "analyze", "investigate", "study", "explore",
                "evaluate", "assess", "compare"
            ],
            WorkerCapability.DOCUMENTATION: [
                "document", "readme", "docs", "comment", "docstring",
                "explain", "describe", "guide"
            ],
            WorkerCapability.TESTING: [
                "test", "unittest", "pytest", "jest", "spec", "coverage",
                "qa", "quality assurance"
            ],
            WorkerCapability.REFACTORING: [
                "refactor", "restructure", "reorganize", "cleanup",
                "improve code", "modernize"
            ],
            WorkerCapability.DEBUGGING: [
                "debug", "fix bug", "error", "issue", "problem",
                "troubleshoot", "diagnose"
            ],
            WorkerCapability.DESIGN: [
                "design", "architecture", "structure", "pattern",
                "blueprint", "plan"
            ],
            WorkerCapability.REVIEW: [
                "review", "audit", "inspect", "examine", "check",
                "validate", "verify"
            ]
        }
        
        self.resource_keywords = {
            "memory_intensive": ["large data", "memory", "cache", "buffer", "dataset"],
            "cpu_intensive": ["algorithm", "compute", "calculation", "process", "intensive"],
            "filesystem": ["file", "directory", "read", "write", "storage"],
            "network": ["api", "http", "request", "download", "upload", "remote"]
        }
    
    def analyze_task(self, task_description: str, task_title: str = "") -> TaskRequirements:
        """
        Analyze task description to determine requirements
        
        Args:
            task_description: Task description text
            task_title: Task title
            
        Returns:
            TaskRequirements object
        """
        text = f"{task_title} {task_description}".lower()
        
        # Determine complexity
        complexity = self._determine_complexity(text)
        
        # Determine required capabilities
        required_capabilities = self._determine_capabilities(text)
        
        # Determine resource requirements
        memory_intensive = self._check_keywords(text, self.resource_keywords["memory_intensive"])
        cpu_intensive = self._check_keywords(text, self.resource_keywords["cpu_intensive"])
        requires_filesystem = self._check_keywords(text, self.resource_keywords["filesystem"])
        requires_network = self._check_keywords(text, self.resource_keywords["network"])
        
        # Estimate duration based on complexity and scope
        estimated_duration = self._estimate_duration(text, complexity)
        
        # Detect potential parallel subtasks
        parallel_subtasks = self._detect_parallel_subtasks(text)
        
        # Determine priority (can be overridden later)
        priority = self._determine_priority(text)
        
        return TaskRequirements(
            complexity=complexity,
            estimated_duration=estimated_duration,
            required_capabilities=required_capabilities,
            memory_intensive=memory_intensive,
            cpu_intensive=cpu_intensive,
            requires_filesystem_access=requires_filesystem,
            requires_network_access=requires_network,
            parallel_subtasks=parallel_subtasks,
            priority=priority
        )
    
    def _determine_complexity(self, text: str) -> TaskComplexity:
        """Determine task complexity from text"""
        scores = {}
        
        for complexity, keywords in self.complexity_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            scores[complexity] = score
        
        # Additional heuristics
        word_count = len(text.split())
        if word_count > 200:
            scores[TaskComplexity.HIGH] += 2
        elif word_count > 100:
            scores[TaskComplexity.MEDIUM] += 1
        
        # Check for multiple requirements
        requirement_indicators = ["and", "also", "additionally", "furthermore"]
        multiple_reqs = sum(1 for indicator in requirement_indicators if indicator in text)
        if multiple_reqs > 2:
            scores[TaskComplexity.HIGH] += 1
        
        # Return complexity with highest score, default to MEDIUM
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        else:
            return TaskComplexity.MEDIUM
    
    def _determine_capabilities(self, text: str) -> Set[WorkerCapability]:
        """Determine required capabilities from text"""
        capabilities = set()
        
        for capability, keywords in self.capability_keywords.items():
            if any(keyword in text for keyword in keywords):
                capabilities.add(capability)
        
        # If no specific capabilities detected, default to CODE
        if not capabilities:
            capabilities.add(WorkerCapability.CODE)
        
        return capabilities
    
    def _check_keywords(self, text: str, keywords: List[str]) -> bool:
        """Check if any keywords are present in text"""
        return any(keyword in text for keyword in keywords)
    
    def _estimate_duration(self, text: str, complexity: TaskComplexity) -> int:
        """Estimate task duration in minutes"""
        base_durations = {
            TaskComplexity.TRIVIAL: 5,
            TaskComplexity.LOW: 15,
            TaskComplexity.MEDIUM: 45,
            TaskComplexity.HIGH: 120,
            TaskComplexity.CRITICAL: 300
        }
        
        duration = base_durations[complexity]
        
        # Adjust based on text indicators
        if "quick" in text or "simple" in text:
            duration *= 0.7
        elif "complex" in text or "comprehensive" in text:
            duration *= 1.5
        elif "entire" in text or "complete" in text:
            duration *= 2.0
        
        return int(duration)
    
    def _detect_parallel_subtasks(self, text: str) -> int:
        """Detect potential for parallel subtask execution"""
        parallel_indicators = [
            "multiple", "several", "various", "different",
            "each", "all", "batch", "parallel"
        ]
        
        count = sum(1 for indicator in parallel_indicators if indicator in text)
        
        # Look for lists or numbered items
        list_patterns = [r'\d+\.', r'-\s', r'\*\s', r'•']
        for pattern in list_patterns:
            matches = len(re.findall(pattern, text))
            if matches > 1:
                count += matches
        
        return min(count, 5)  # Cap at 5 parallel subtasks
    
    def _determine_priority(self, text: str) -> int:
        """Determine task priority (1-10)"""
        high_priority_keywords = ["urgent", "critical", "asap", "immediately", "priority"]
        low_priority_keywords = ["later", "eventually", "nice to have", "optional"]
        
        if any(keyword in text for keyword in high_priority_keywords):
            return 8
        elif any(keyword in text for keyword in low_priority_keywords):
            return 3
        else:
            return 5  # Default priority


class DynamicWorkerAllocator:
    """
    Manages dynamic allocation of workers based on task requirements
    """
    
    def __init__(self):
        self.workers: Dict[str, WorkerProfile] = {}
        self.task_analyzer = TaskComplexityAnalyzer()
        self.allocation_history: List[Dict[str, Any]] = []
        self.performance_tracker: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self.feedback_storage = None  # Will be set if feedback is enabled
        
        logger.info("Dynamic worker allocator initialized")
    
    def register_worker(self, worker_id: str, model_name: str,
                       capabilities: Set[WorkerCapability],
                       max_complexity: TaskComplexity = TaskComplexity.HIGH,
                       max_concurrent_tasks: int = 1) -> bool:
        """
        Register a new worker
        
        Args:
            worker_id: Unique worker identifier
            model_name: Model name (e.g., "claude-3-5-sonnet-20241022")
            capabilities: Set of worker capabilities
            max_complexity: Maximum task complexity the worker can handle
            max_concurrent_tasks: Maximum concurrent tasks
            
        Returns:
            True if registered successfully
        """
        with self._lock:
            if worker_id in self.workers:
                logger.warning(f"Worker {worker_id} already registered, updating profile")
            
            # Determine specialization bonuses based on model
            specialization_bonus = self._get_model_specializations(model_name)
            
            self.workers[worker_id] = WorkerProfile(
                worker_id=worker_id,
                model_name=model_name,
                capabilities=capabilities,
                max_complexity=max_complexity,
                max_concurrent_tasks=max_concurrent_tasks,
                specialization_bonus=specialization_bonus
            )
            
            logger.info(f"Registered worker {worker_id} with model {model_name}")
            return True
    
    def set_feedback_storage(self, feedback_storage):
        """Set the feedback storage instance for collecting worker feedback"""
        self.feedback_storage = feedback_storage
        logger.info("Feedback storage configured for dynamic worker allocator")
    
    def _get_model_specializations(self, model_name: str) -> Dict[WorkerCapability, float]:
        """Get specialization bonuses based on model capabilities"""
        # Model-specific specializations (these would be configured based on actual model performance)
        specializations = {}
        
        if "opus" in model_name.lower():
            # Opus is good at complex reasoning and planning
            specializations = {
                WorkerCapability.DESIGN: 0.8,
                WorkerCapability.RESEARCH: 0.7,
                WorkerCapability.REVIEW: 0.6
            }
        elif "sonnet" in model_name.lower():
            # Sonnet is good at code implementation
            specializations = {
                WorkerCapability.CODE: 0.8,
                WorkerCapability.REFACTORING: 0.6,
                WorkerCapability.DEBUGGING: 0.5
            }
        elif "haiku" in model_name.lower():
            # Haiku is good at quick tasks
            specializations = {
                WorkerCapability.DOCUMENTATION: 0.6,
                WorkerCapability.TESTING: 0.5
            }
        
        return specializations
    
    def unregister_worker(self, worker_id: str) -> bool:
        """Unregister a worker"""
        with self._lock:
            if worker_id in self.workers:
                del self.workers[worker_id]
                logger.info(f"Unregistered worker {worker_id}")
                return True
            else:
                logger.warning(f"Worker {worker_id} not found for unregistration")
                return False
    
    def allocate_worker(self, task_id: str, task_title: str, 
                       task_description: str,
                       task_requirements: Optional[TaskRequirements] = None) -> Optional[str]:
        """
        Allocate the best available worker for a task
        
        Args:
            task_id: Task identifier
            task_title: Task title
            task_description: Task description
            task_requirements: Pre-analyzed task requirements (optional)
            
        Returns:
            Worker ID if allocation successful, None otherwise
        """
        with self._lock:
            # Analyze task if requirements not provided
            if task_requirements is None:
                task_requirements = self.task_analyzer.analyze_task(
                    task_description, task_title
                )
            
            # Get feedback analyzer if available
            feedback_analyzer = None
            if hasattr(self, 'feedback_storage') and self.feedback_storage:
                try:
                    from .feedback_analyzer import FeedbackAnalyzer
                    feedback_analyzer = FeedbackAnalyzer(self.feedback_storage)
                except Exception as e:
                    logger.debug(f"Failed to create feedback analyzer: {e}")
            
            # Find available workers who can handle the task
            suitable_workers = []
            for worker in self.workers.values():
                if worker.is_available() and worker.can_handle_task(task_requirements):
                    suitability_score = worker.calculate_suitability_score(
                        task_requirements, feedback_analyzer
                    )
                    suitable_workers.append((worker, suitability_score))
            
            if not suitable_workers:
                logger.warning(f"No suitable workers found for task {task_id}")
                return None
            
            # Sort by suitability score (highest first)
            suitable_workers.sort(key=lambda x: x[1], reverse=True)
            
            # Select the best worker
            best_worker, score = suitable_workers[0]
            
            # Assign task to worker
            best_worker.current_tasks.append(task_id)
            best_worker.current_load = len(best_worker.current_tasks) / best_worker.max_concurrent_tasks
            best_worker.last_assigned = datetime.now()
            
            # Record allocation with feedback history
            allocation_record = {
                "timestamp": datetime.now().isoformat(),
                "task_id": task_id,
                "worker_id": best_worker.worker_id,
                "suitability_score": score,
                "task_complexity": task_requirements.complexity.value,
                "required_capabilities": [cap.value for cap in task_requirements.required_capabilities],
                "estimated_duration": task_requirements.estimated_duration
            }
            
            # Add worker feedback history if available
            if feedback_analyzer:
                try:
                    worker_perf = feedback_analyzer.get_worker_performance(best_worker.worker_id)
                    if worker_perf:
                        allocation_record["worker_historical_performance"] = {
                            "success_rate": worker_perf.success_rate,
                            "average_response_time": worker_perf.average_response_time,
                            "total_tasks": worker_perf.total_tasks
                        }
                except Exception as e:
                    logger.debug(f"Failed to add worker performance to allocation record: {e}")
            
            self.allocation_history.append(allocation_record)
            
            logger.info(f"Allocated worker {best_worker.worker_id} to task {task_id} "
                       f"(score: {score:.2f}, complexity: {task_requirements.complexity.value})")
            
            return best_worker.worker_id
    
    def release_worker(self, worker_id: str, task_id: str, 
                      success: bool = True, actual_duration: float = None) -> bool:
        """
        Release a worker from a task
        
        Args:
            worker_id: Worker identifier
            task_id: Task identifier
            success: Whether task completed successfully
            actual_duration: Actual task duration in minutes
            
        Returns:
            True if released successfully
        """
        with self._lock:
            if worker_id not in self.workers:
                logger.error(f"Worker {worker_id} not found for release")
                return False
            
            worker = self.workers[worker_id]
            
            if task_id not in worker.current_tasks:
                logger.warning(f"Task {task_id} not found in worker {worker_id} current tasks")
                return False
            
            # Remove task from worker
            worker.current_tasks.remove(task_id)
            worker.current_load = len(worker.current_tasks) / worker.max_concurrent_tasks
            
            # Update performance metrics
            if success:
                worker.total_tasks_completed += 1
                
                if actual_duration:
                    # Update average duration with exponential moving average
                    alpha = 0.1  # Learning rate
                    worker.average_task_duration = (
                        alpha * actual_duration + 
                        (1 - alpha) * worker.average_task_duration
                    )
                
                # Track performance for this worker
                self.performance_tracker[worker_id].append(1.0)
            else:
                self.performance_tracker[worker_id].append(0.0)
            
            # Update success rate (rolling average over last 10 tasks)
            recent_performance = self.performance_tracker[worker_id][-10:]
            worker.success_rate = sum(recent_performance) / len(recent_performance)
            
            # Update performance score based on success rate and efficiency
            if worker.success_rate > 0.9:
                worker.performance_score = min(worker.performance_score * 1.05, 2.0)
            elif worker.success_rate < 0.7:
                worker.performance_score = max(worker.performance_score * 0.95, 0.5)
            
            # Collect feedback if feedback storage is available
            if hasattr(self, 'feedback_storage') and self.feedback_storage:
                try:
                    from .feedback_model import (
                        create_success_feedback, create_error_feedback,
                        create_performance_feedback, FeedbackMetrics
                    )
                    
                    if success:
                        # Create performance feedback for successful task
                        metrics = FeedbackMetrics(
                            execution_time=actual_duration * 60 if actual_duration else None,  # Convert to seconds
                            success_rate=worker.success_rate,
                            quality_score=worker.performance_score
                        )
                        
                        feedback = create_performance_feedback(
                            task_id=task_id,
                            message=f"Worker {worker_id} completed task successfully",
                            execution_time=actual_duration * 60 if actual_duration else 0,
                            worker_id=worker_id,
                            tags=["worker_release", "task_completion"]
                        )
                        self.feedback_storage.save(feedback)
                        
                        # Also create success feedback
                        success_feedback = create_success_feedback(
                            task_id=task_id,
                            message=f"Task completed by worker {worker_id}",
                            metrics=metrics,
                            worker_id=worker_id,
                            tags=["dynamic_allocation"]
                        )
                        self.feedback_storage.save(success_feedback)
                    else:
                        # Create error feedback for failed task
                        error_feedback = create_error_feedback(
                            task_id=task_id,
                            message=f"Task failed on worker {worker_id}",
                            error_details={
                                "worker_id": worker_id,
                                "worker_capability": worker.capability.value,
                                "worker_load": worker.current_load,
                                "success_rate": worker.success_rate
                            },
                            worker_id=worker_id,
                            tags=["worker_release", "task_failure"]
                        )
                        self.feedback_storage.save(error_feedback)
                        
                except Exception as e:
                    logger.debug(f"Failed to save worker release feedback: {e}")
            
            logger.info(f"Released worker {worker_id} from task {task_id} "
                       f"(success: {success}, success_rate: {worker.success_rate:.2f})")
            
            return True
    
    def get_worker_status(self) -> Dict[str, Any]:
        """Get status of all workers"""
        with self._lock:
            status = {
                "total_workers": len(self.workers),
                "available_workers": sum(1 for w in self.workers.values() if w.is_available()),
                "workers": {}
            }
            
            for worker_id, worker in self.workers.items():
                status["workers"][worker_id] = {
                    "model_name": worker.model_name,
                    "capabilities": [cap.value for cap in worker.capabilities],
                    "max_complexity": worker.max_complexity.value,
                    "current_load": worker.current_load,
                    "current_tasks": len(worker.current_tasks),
                    "max_concurrent_tasks": worker.max_concurrent_tasks,
                    "performance_score": worker.performance_score,
                    "success_rate": worker.success_rate,
                    "total_completed": worker.total_tasks_completed,
                    "average_duration": worker.average_task_duration,
                    "is_available": worker.is_available()
                }
            
            return status
    
    def get_allocation_analytics(self) -> Dict[str, Any]:
        """Get analytics on task allocation patterns"""
        with self._lock:
            if not self.allocation_history:
                return {"message": "No allocation history available"}
            
            # Recent allocations (last 24 hours)
            recent_cutoff = datetime.now() - timedelta(hours=24)
            recent_allocations = [
                a for a in self.allocation_history 
                if datetime.fromisoformat(a["timestamp"]) > recent_cutoff
            ]
            
            # Worker utilization
            worker_allocations = defaultdict(int)
            complexity_distribution = defaultdict(int)
            
            for allocation in recent_allocations:
                worker_allocations[allocation["worker_id"]] += 1
                complexity_distribution[allocation["task_complexity"]] += 1
            
            # Average suitability scores
            avg_suitability = sum(a["suitability_score"] for a in recent_allocations) / len(recent_allocations) if recent_allocations else 0
            
            return {
                "total_allocations": len(self.allocation_history),
                "recent_allocations_24h": len(recent_allocations),
                "worker_utilization": dict(worker_allocations),
                "complexity_distribution": dict(complexity_distribution),
                "average_suitability_score": avg_suitability,
                "allocation_efficiency": self._calculate_allocation_efficiency()
            }
    
    def _calculate_allocation_efficiency(self) -> float:
        """Calculate overall allocation efficiency"""
        if not self.allocation_history:
            return 0.0
        
        # Simple efficiency metric based on average suitability scores
        total_score = sum(a["suitability_score"] for a in self.allocation_history)
        max_possible_score = len(self.allocation_history) * 2.0  # Assuming max score is 2.0
        
        return (total_score / max_possible_score) * 100 if max_possible_score > 0 else 0.0
    
    def optimize_worker_allocation(self) -> Dict[str, Any]:
        """Analyze and suggest worker allocation optimizations"""
        with self._lock:
            suggestions = []
            
            # Check for underutilized workers
            for worker_id, worker in self.workers.items():
                if (worker.total_tasks_completed < 5 and 
                    worker.last_assigned and 
                    datetime.now() - worker.last_assigned > timedelta(hours=2)):
                    suggestions.append(f"Worker {worker_id} appears underutilized")
            
            # Check for overloaded workers
            for worker_id, worker in self.workers.items():
                if worker.current_load > 0.8:
                    suggestions.append(f"Worker {worker_id} is heavily loaded ({worker.current_load:.1%})")
            
            # Check capability gaps
            all_required_capabilities = set()
            for allocation in self.allocation_history[-50:]:  # Last 50 allocations
                all_required_capabilities.update(allocation["required_capabilities"])
            
            available_capabilities = set()
            for worker in self.workers.values():
                available_capabilities.update(cap.value for cap in worker.capabilities)
            
            missing_capabilities = all_required_capabilities - available_capabilities
            if missing_capabilities:
                suggestions.append(f"Consider adding workers with capabilities: {missing_capabilities}")
            
            return {
                "suggestions": suggestions,
                "worker_count": len(self.workers),
                "efficiency_score": self._calculate_allocation_efficiency()
            }


# Global dynamic worker allocator instance
dynamic_allocator = DynamicWorkerAllocator()