"""
Evaluator-Optimizer Pattern for Iterative Task Refinement
Implements continuous improvement through evaluation and optimization cycles
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import threading
from collections import deque, defaultdict
import re
import statistics

logger = logging.getLogger(__name__)


class EvaluationCriteria(Enum):
    """Evaluation criteria for task results"""
    CORRECTNESS = "correctness"
    COMPLETENESS = "completeness"
    QUALITY = "quality"
    EFFICIENCY = "efficiency"
    MAINTAINABILITY = "maintainability"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"


class OptimizationStrategy(Enum):
    """Optimization strategies"""
    REFINE_APPROACH = "refine_approach"
    BREAK_DOWN_TASK = "break_down_task"
    CHANGE_WORKER = "change_worker"
    ADD_RESOURCES = "add_resources"
    REVISE_REQUIREMENTS = "revise_requirements"
    IMPROVE_TOOLING = "improve_tooling"


@dataclass
class EvaluationResult:
    """Result of task evaluation"""
    task_id: str
    evaluation_id: str
    criteria_scores: Dict[EvaluationCriteria, float]  # 0.0-1.0
    overall_score: float
    feedback: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)
    passed_threshold: bool = False
    evaluated_at: datetime = field(default_factory=datetime.now)
    evaluator_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_weighted_score(self, weights: Dict[EvaluationCriteria, float] = None) -> float:
        """Calculate weighted overall score"""
        if not weights:
            # Default equal weights
            weights = {criteria: 1.0 for criteria in self.criteria_scores.keys()}
        
        total_weight = sum(weights.values())
        weighted_sum = sum(
            score * weights.get(criteria, 0.0) 
            for criteria, score in self.criteria_scores.items()
        )
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0


@dataclass
class OptimizationPlan:
    """Plan for optimizing task execution"""
    task_id: str
    optimization_id: str
    strategies: List[OptimizationStrategy]
    specific_actions: List[str] = field(default_factory=list)
    expected_improvements: Dict[EvaluationCriteria, float] = field(default_factory=dict)
    estimated_effort: int = 0  # in minutes
    priority: int = 5  # 1-10
    created_at: datetime = field(default_factory=datetime.now)
    optimizer_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IterationCycle:
    """Represents one iteration of evaluate-optimize cycle"""
    cycle_id: str
    task_id: str
    iteration_number: int
    evaluation_result: EvaluationResult
    optimization_plan: Optional[OptimizationPlan] = None
    execution_result: Optional[Dict[str, Any]] = None
    improvement_achieved: Optional[float] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    status: str = "in_progress"  # in_progress, completed, failed


class TaskEvaluator:
    """
    Evaluates task results against multiple criteria
    """
    
    def __init__(self, evaluation_threshold: float = 0.8):
        self.evaluation_threshold = evaluation_threshold
        self.evaluation_history: List[EvaluationResult] = []
        self.custom_evaluators: Dict[str, Callable] = {}
        
        # Default evaluation weights
        self.default_weights = {
            EvaluationCriteria.CORRECTNESS: 0.25,
            EvaluationCriteria.COMPLETENESS: 0.20,
            EvaluationCriteria.QUALITY: 0.15,
            EvaluationCriteria.EFFICIENCY: 0.10,
            EvaluationCriteria.MAINTAINABILITY: 0.10,
            EvaluationCriteria.SECURITY: 0.10,
            EvaluationCriteria.PERFORMANCE: 0.05,
            EvaluationCriteria.DOCUMENTATION: 0.05
        }
    
    def register_custom_evaluator(self, name: str, evaluator_func: Callable):
        """Register a custom evaluation function"""
        self.custom_evaluators[name] = evaluator_func
        logger.info(f"Registered custom evaluator: {name}")
    
    def evaluate_task_result(self, task_id: str, task_description: str,
                           task_result: Dict[str, Any],
                           evaluation_criteria: List[EvaluationCriteria] = None,
                           weights: Dict[EvaluationCriteria, float] = None,
                           evaluator_id: str = None) -> EvaluationResult:
        """
        Evaluate a task result against specified criteria
        
        Args:
            task_id: Task identifier
            task_description: Original task description
            task_result: Task execution result
            evaluation_criteria: Criteria to evaluate (defaults to all)
            weights: Weights for criteria (defaults to standard weights)
            evaluator_id: ID of the evaluator
            
        Returns:
            EvaluationResult with scores and feedback
        """
        evaluation_id = f"eval_{task_id}_{int(time.time())}"
        
        if evaluation_criteria is None:
            evaluation_criteria = list(EvaluationCriteria)
        
        if weights is None:
            weights = self.default_weights
        
        # Evaluate each criterion
        criteria_scores = {}
        feedback = []
        improvement_suggestions = []
        
        for criteria in evaluation_criteria:
            score, crit_feedback, crit_suggestions = self._evaluate_criterion(
                criteria, task_description, task_result
            )
            criteria_scores[criteria] = score
            feedback.extend(crit_feedback)
            improvement_suggestions.extend(crit_suggestions)
        
        # Calculate overall score
        overall_score = sum(
            score * weights.get(criteria, 0.0) 
            for criteria, score in criteria_scores.items()
        ) / sum(weights.get(criteria, 0.0) for criteria in criteria_scores.keys())
        
        # Check if it meets threshold
        passed_threshold = overall_score >= self.evaluation_threshold
        
        evaluation_result = EvaluationResult(
            task_id=task_id,
            evaluation_id=evaluation_id,
            criteria_scores=criteria_scores,
            overall_score=overall_score,
            feedback=feedback,
            improvement_suggestions=improvement_suggestions,
            passed_threshold=passed_threshold,
            evaluator_id=evaluator_id,
            metadata={
                "task_description": task_description,
                "evaluation_criteria": [c.value for c in evaluation_criteria],
                "weights_used": {c.value: w for c, w in weights.items()},
                "threshold": self.evaluation_threshold
            }
        )
        
        self.evaluation_history.append(evaluation_result)
        
        logger.info(f"Evaluated task {task_id}: score={overall_score:.2f}, "
                   f"passed={passed_threshold}")
        
        return evaluation_result
    
    def _evaluate_criterion(self, criteria: EvaluationCriteria, 
                          task_description: str, task_result: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Evaluate a specific criterion"""
        if criteria == EvaluationCriteria.CORRECTNESS:
            return self._evaluate_correctness(task_description, task_result)
        elif criteria == EvaluationCriteria.COMPLETENESS:
            return self._evaluate_completeness(task_description, task_result)
        elif criteria == EvaluationCriteria.QUALITY:
            return self._evaluate_quality(task_description, task_result)
        elif criteria == EvaluationCriteria.EFFICIENCY:
            return self._evaluate_efficiency(task_description, task_result)
        elif criteria == EvaluationCriteria.MAINTAINABILITY:
            return self._evaluate_maintainability(task_description, task_result)
        elif criteria == EvaluationCriteria.SECURITY:
            return self._evaluate_security(task_description, task_result)
        elif criteria == EvaluationCriteria.PERFORMANCE:
            return self._evaluate_performance(task_description, task_result)
        elif criteria == EvaluationCriteria.DOCUMENTATION:
            return self._evaluate_documentation(task_description, task_result)
        else:
            return 0.5, [f"Unknown criteria: {criteria}"], []
    
    def _evaluate_correctness(self, task_description: str, task_result: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Evaluate correctness of the result"""
        score = 0.8  # Default score
        feedback = []
        suggestions = []
        
        # Check for error indicators
        if task_result.get("success", True):
            score += 0.2
            feedback.append("Task completed successfully")
        else:
            score -= 0.3
            feedback.append("Task completed with errors")
            suggestions.append("Review and fix the reported errors")
        
        # Check for validation results
        if "validation_results" in task_result:
            validation = task_result["validation_results"]
            if validation.get("passed", False):
                score += 0.1
                feedback.append("Validation checks passed")
            else:
                score -= 0.2
                feedback.append("Validation checks failed")
                suggestions.append("Address validation failures")
        
        return max(0.0, min(1.0, score)), feedback, suggestions
    
    def _evaluate_completeness(self, task_description: str, task_result: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Evaluate completeness of the result"""
        score = 0.7
        feedback = []
        suggestions = []
        
        # Check if all requested items were addressed
        files_changed = task_result.get("files_changed", [])
        files_created = task_result.get("files_created", [])
        
        if files_changed or files_created:
            score += 0.2
            feedback.append(f"Modified {len(files_changed)} files, created {len(files_created)} files")
        
        # Check for test completion if testing was mentioned
        if "test" in task_description.lower():
            test_files = [f for f in files_changed + files_created if "test" in f.lower()]
            if test_files:
                score += 0.1
                feedback.append("Test files were created/modified")
            else:
                score -= 0.1
                suggestions.append("Consider adding test files for testing-related tasks")
        
        return max(0.0, min(1.0, score)), feedback, suggestions
    
    def _evaluate_quality(self, task_description: str, task_result: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Evaluate quality of the result"""
        score = 0.7
        feedback = []
        suggestions = []
        
        # Check for code quality indicators
        if "code_quality_score" in task_result:
            quality_score = task_result["code_quality_score"]
            score = quality_score
            feedback.append(f"Code quality score: {quality_score:.2f}")
        
        # Check for best practices
        if task_result.get("follows_best_practices", False):
            score += 0.1
            feedback.append("Follows coding best practices")
        
        return max(0.0, min(1.0, score)), feedback, suggestions
    
    def _evaluate_efficiency(self, task_description: str, task_result: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Evaluate efficiency of the result"""
        score = 0.8
        feedback = []
        suggestions = []
        
        # Check execution time if available
        execution_time = task_result.get("execution_time_minutes", 0)
        estimated_time = task_result.get("estimated_time_minutes", 30)
        
        if execution_time > 0 and estimated_time > 0:
            time_ratio = execution_time / estimated_time
            if time_ratio <= 1.0:
                score += 0.2 * (1.0 - time_ratio)
                feedback.append(f"Completed in {execution_time:.1f}min (estimated {estimated_time:.1f}min)")
            else:
                score -= 0.1 * (time_ratio - 1.0)
                feedback.append(f"Took longer than estimated: {execution_time:.1f}min vs {estimated_time:.1f}min")
                suggestions.append("Consider optimizing the approach for better time efficiency")
        
        return max(0.0, min(1.0, score)), feedback, suggestions
    
    def _evaluate_maintainability(self, task_description: str, task_result: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Evaluate maintainability of the result"""
        score = 0.7
        feedback = []
        suggestions = []
        
        # Check for documentation
        if task_result.get("documentation_added", False):
            score += 0.2
            feedback.append("Documentation was added")
        
        # Check for code comments
        if task_result.get("comments_added", False):
            score += 0.1
            feedback.append("Code comments were added")
        
        return max(0.0, min(1.0, score)), feedback, suggestions
    
    def _evaluate_security(self, task_description: str, task_result: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Evaluate security aspects of the result"""
        score = 0.8
        feedback = []
        suggestions = []
        
        # Check for security issues
        security_issues = task_result.get("security_issues", [])
        if security_issues:
            score -= 0.1 * len(security_issues)
            feedback.append(f"Found {len(security_issues)} security issues")
            suggestions.append("Address identified security issues")
        else:
            feedback.append("No security issues detected")
        
        return max(0.0, min(1.0, score)), feedback, suggestions
    
    def _evaluate_performance(self, task_description: str, task_result: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Evaluate performance aspects of the result"""
        score = 0.8
        feedback = []
        suggestions = []
        
        # Check for performance metrics
        if "performance_metrics" in task_result:
            metrics = task_result["performance_metrics"]
            if metrics.get("performance_improved", False):
                score += 0.2
                feedback.append("Performance improvements detected")
            elif metrics.get("performance_degraded", False):
                score -= 0.2
                feedback.append("Performance degradation detected")
                suggestions.append("Investigate and optimize performance issues")
        
        return max(0.0, min(1.0, score)), feedback, suggestions
    
    def _evaluate_documentation(self, task_description: str, task_result: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Evaluate documentation quality"""
        score = 0.7
        feedback = []
        suggestions = []
        
        # Check if documentation was requested and provided
        if "document" in task_description.lower() or "readme" in task_description.lower():
            if task_result.get("documentation_created", False):
                score += 0.3
                feedback.append("Requested documentation was created")
            else:
                score -= 0.3
                suggestions.append("Create the requested documentation")
        
        return max(0.0, min(1.0, score)), feedback, suggestions


class TaskOptimizer:
    """
    Creates optimization plans based on evaluation results
    """
    
    def __init__(self):
        self.optimization_history: List[OptimizationPlan] = []
        self.strategy_effectiveness: Dict[OptimizationStrategy, List[float]] = defaultdict(list)
    
    def create_optimization_plan(self, evaluation_result: EvaluationResult,
                               task_description: str,
                               optimizer_id: str = None) -> OptimizationPlan:
        """
        Create an optimization plan based on evaluation results
        
        Args:
            evaluation_result: Result of task evaluation
            task_description: Original task description
            optimizer_id: ID of the optimizer
            
        Returns:
            OptimizationPlan with specific strategies and actions
        """
        optimization_id = f"opt_{evaluation_result.task_id}_{int(time.time())}"
        
        strategies = []
        actions = []
        expected_improvements = {}
        
        # Analyze each criteria that scored low
        for criteria, score in evaluation_result.criteria_scores.items():
            if score < 0.7:  # Below acceptable threshold
                strategy, action, improvement = self._get_optimization_for_criteria(
                    criteria, score, evaluation_result, task_description
                )
                if strategy:
                    strategies.append(strategy)
                    actions.append(action)
                    expected_improvements[criteria] = improvement
        
        # Determine overall priority based on how far below threshold we are
        score_gap = self.evaluation_threshold - evaluation_result.overall_score
        priority = min(10, max(1, int(score_gap * 10) + 5))
        
        # Estimate effort based on number of strategies
        estimated_effort = len(strategies) * 30  # 30 minutes per strategy
        
        optimization_plan = OptimizationPlan(
            task_id=evaluation_result.task_id,
            optimization_id=optimization_id,
            strategies=strategies,
            specific_actions=actions,
            expected_improvements=expected_improvements,
            estimated_effort=estimated_effort,
            priority=priority,
            optimizer_id=optimizer_id,
            metadata={
                "evaluation_score": evaluation_result.overall_score,
                "threshold": getattr(self, 'evaluation_threshold', 0.8),
                "improvement_suggestions": evaluation_result.improvement_suggestions
            }
        )
        
        self.optimization_history.append(optimization_plan)
        
        logger.info(f"Created optimization plan {optimization_id} for task {evaluation_result.task_id} "
                   f"with {len(strategies)} strategies")
        
        return optimization_plan
    
    def _get_optimization_for_criteria(self, criteria: EvaluationCriteria, score: float,
                                     evaluation_result: EvaluationResult,
                                     task_description: str) -> Tuple[OptimizationStrategy, str, float]:
        """Get optimization strategy for a specific criteria"""
        if criteria == EvaluationCriteria.CORRECTNESS:
            if score < 0.5:
                return (OptimizationStrategy.REVISE_REQUIREMENTS, 
                       "Clarify requirements and re-implement the solution", 0.3)
            else:
                return (OptimizationStrategy.REFINE_APPROACH,
                       "Debug and fix the identified issues", 0.2)
        
        elif criteria == EvaluationCriteria.COMPLETENESS:
            return (OptimizationStrategy.BREAK_DOWN_TASK,
                   "Break down into smaller, more manageable subtasks", 0.25)
        
        elif criteria == EvaluationCriteria.QUALITY:
            return (OptimizationStrategy.REFINE_APPROACH,
                   "Improve code quality with better practices", 0.2)
        
        elif criteria == EvaluationCriteria.EFFICIENCY:
            return (OptimizationStrategy.CHANGE_WORKER,
                   "Assign to a worker with better efficiency profile", 0.15)
        
        elif criteria == EvaluationCriteria.MAINTAINABILITY:
            return (OptimizationStrategy.REFINE_APPROACH,
                   "Add documentation and improve code structure", 0.2)
        
        elif criteria == EvaluationCriteria.SECURITY:
            return (OptimizationStrategy.REFINE_APPROACH,
                   "Review and fix security issues", 0.3)
        
        elif criteria == EvaluationCriteria.PERFORMANCE:
            return (OptimizationStrategy.IMPROVE_TOOLING,
                   "Optimize algorithms and data structures", 0.25)
        
        elif criteria == EvaluationCriteria.DOCUMENTATION:
            return (OptimizationStrategy.REFINE_APPROACH,
                   "Add comprehensive documentation", 0.2)
        
        else:
            return (OptimizationStrategy.REFINE_APPROACH,
                   f"Improve {criteria.value} aspects", 0.1)
    
    def track_optimization_effectiveness(self, optimization_plan: OptimizationPlan,
                                       before_score: float, after_score: float):
        """Track the effectiveness of optimization strategies"""
        improvement = after_score - before_score
        
        for strategy in optimization_plan.strategies:
            self.strategy_effectiveness[strategy].append(improvement)
        
        logger.info(f"Tracked optimization effectiveness: {improvement:.2f} improvement "
                   f"for strategies {[s.value for s in optimization_plan.strategies]}")
    
    def get_strategy_effectiveness_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics on strategy effectiveness"""
        stats = {}
        
        for strategy, improvements in self.strategy_effectiveness.items():
            if improvements:
                stats[strategy.value] = {
                    "mean_improvement": statistics.mean(improvements),
                    "median_improvement": statistics.median(improvements),
                    "success_rate": sum(1 for imp in improvements if imp > 0) / len(improvements),
                    "total_applications": len(improvements)
                }
        
        return stats


class EvaluatorOptimizer:
    """
    Main class that orchestrates the evaluate-optimize cycle
    """
    
    def __init__(self, evaluation_threshold: float = 0.8, max_iterations: int = 3):
        self.evaluator = TaskEvaluator(evaluation_threshold)
        self.optimizer = TaskOptimizer()
        self.max_iterations = max_iterations
        self.iteration_cycles: List[IterationCycle] = []
        self._lock = threading.Lock()
        
        logger.info(f"Evaluator-Optimizer initialized with threshold={evaluation_threshold}, "
                   f"max_iterations={max_iterations}")
    
    def run_evaluation_cycle(self, task_id: str, task_description: str,
                           task_result: Dict[str, Any],
                           evaluator_id: str = None,
                           optimizer_id: str = None) -> IterationCycle:
        """
        Run a complete evaluation-optimization cycle
        
        Args:
            task_id: Task identifier
            task_description: Original task description
            task_result: Task execution result
            evaluator_id: ID of the evaluator
            optimizer_id: ID of the optimizer
            
        Returns:
            IterationCycle with evaluation and optimization results
        """
        with self._lock:
            cycle_id = f"cycle_{task_id}_{int(time.time())}"
            iteration_number = len([c for c in self.iteration_cycles if c.task_id == task_id]) + 1
            
            # Evaluate the task result
            evaluation_result = self.evaluator.evaluate_task_result(
                task_id, task_description, task_result, evaluator_id=evaluator_id
            )
            
            # Create optimization plan if evaluation didn't pass
            optimization_plan = None
            if not evaluation_result.passed_threshold:
                optimization_plan = self.optimizer.create_optimization_plan(
                    evaluation_result, task_description, optimizer_id=optimizer_id
                )
            
            # Create iteration cycle
            cycle = IterationCycle(
                cycle_id=cycle_id,
                task_id=task_id,
                iteration_number=iteration_number,
                evaluation_result=evaluation_result,
                optimization_plan=optimization_plan
            )
            
            self.iteration_cycles.append(cycle)
            
            logger.info(f"Completed evaluation cycle {cycle_id} for task {task_id}: "
                       f"score={evaluation_result.overall_score:.2f}, "
                       f"optimization_needed={optimization_plan is not None}")
            
            return cycle
    
    def should_continue_optimization(self, task_id: str) -> bool:
        """Check if optimization should continue for a task"""
        task_cycles = [c for c in self.iteration_cycles if c.task_id == task_id]
        
        if len(task_cycles) >= self.max_iterations:
            logger.info(f"Max iterations reached for task {task_id}")
            return False
        
        if task_cycles:
            latest_cycle = max(task_cycles, key=lambda c: c.iteration_number)
            if latest_cycle.evaluation_result.passed_threshold:
                logger.info(f"Task {task_id} passed evaluation threshold")
                return False
        
        return True
    
    def get_improvement_trend(self, task_id: str) -> Dict[str, Any]:
        """Get improvement trend for a task across iterations"""
        task_cycles = [c for c in self.iteration_cycles if c.task_id == task_id]
        task_cycles.sort(key=lambda c: c.iteration_number)
        
        if not task_cycles:
            return {"message": "No cycles found for task"}
        
        scores = [c.evaluation_result.overall_score for c in task_cycles]
        
        trend_analysis = {
            "task_id": task_id,
            "total_iterations": len(task_cycles),
            "initial_score": scores[0],
            "final_score": scores[-1],
            "total_improvement": scores[-1] - scores[0],
            "average_improvement_per_iteration": (scores[-1] - scores[0]) / len(scores) if len(scores) > 1 else 0,
            "score_history": scores,
            "converged": scores[-1] >= self.evaluator.evaluation_threshold,
            "improvement_rate": self._calculate_improvement_rate(scores)
        }
        
        return trend_analysis
    
    def _calculate_improvement_rate(self, scores: List[float]) -> str:
        """Calculate improvement rate trend"""
        if len(scores) < 2:
            return "insufficient_data"
        
        improvements = [scores[i] - scores[i-1] for i in range(1, len(scores))]
        
        if all(imp >= 0 for imp in improvements):
            return "consistently_improving"
        elif all(imp <= 0 for imp in improvements):
            return "consistently_declining"
        elif improvements[-1] > 0:
            return "recently_improving"
        elif improvements[-1] < 0:
            return "recently_declining"
        else:
            return "fluctuating"
    
    def get_system_analytics(self) -> Dict[str, Any]:
        """Get analytics about the evaluation-optimization system"""
        with self._lock:
            total_cycles = len(self.iteration_cycles)
            successful_optimizations = sum(
                1 for c in self.iteration_cycles 
                if c.evaluation_result.passed_threshold
            )
            
            # Average improvements
            improvements = []
            for cycle in self.iteration_cycles:
                if cycle.improvement_achieved is not None:
                    improvements.append(cycle.improvement_achieved)
            
            avg_improvement = statistics.mean(improvements) if improvements else 0
            
            # Strategy effectiveness
            strategy_stats = self.optimizer.get_strategy_effectiveness_stats()
            
            return {
                "total_evaluation_cycles": total_cycles,
                "successful_optimizations": successful_optimizations,
                "success_rate": successful_optimizations / total_cycles if total_cycles > 0 else 0,
                "average_improvement": avg_improvement,
                "strategy_effectiveness": strategy_stats,
                "evaluation_threshold": self.evaluator.evaluation_threshold,
                "max_iterations": self.max_iterations
            }


# Global evaluator-optimizer instance
evaluator_optimizer = EvaluatorOptimizer()