"""Dynamic task routing system for intelligent task distribution."""

import logging
import time
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import threading
import json
import re

from .dynamic_worker_allocation import (
    TaskRequirements, TaskComplexity, WorkerCapability,
    TaskComplexityAnalyzer, DynamicWorkerAllocator
)
from .feedback_analyzer import FeedbackAnalyzer
from .feedback_storage import FeedbackStorage

logger = logging.getLogger(__name__)


class RoutingStrategy:
    """Task routing strategies."""
    CAPABILITY_BASED = "capability_based"      # Route based on required capabilities
    LOAD_BALANCED = "load_balanced"           # Distribute evenly across workers
    PERFORMANCE_OPTIMIZED = "performance"     # Route to best performing workers
    COMPLEXITY_MATCHED = "complexity"         # Match task complexity to worker level
    SPECIALIZED = "specialized"               # Route to specialized workers
    HYBRID = "hybrid"                        # Combine multiple strategies


@dataclass
class RoutingRule:
    """Rule for task routing."""
    rule_id: str
    name: str
    condition: Callable[[Dict[str, Any]], bool]  # Task dict -> bool
    target_worker: Optional[str] = None  # Specific worker ID
    target_capability: Optional[WorkerCapability] = None
    priority: int = 0  # Higher priority rules are evaluated first
    enabled: bool = True
    
    def matches(self, task: Dict[str, Any]) -> bool:
        """Check if rule matches the task."""
        if not self.enabled:
            return False
        try:
            return self.condition(task)
        except Exception as e:
            logger.error(f"Error evaluating routing rule {self.rule_id}: {e}")
            return False


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    task_id: str
    selected_worker: Optional[str]
    strategy_used: str
    score: float
    alternatives: List[Tuple[str, float]] = field(default_factory=list)
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class DynamicTaskRouter:
    """Routes tasks to workers based on dynamic strategies."""
    
    def __init__(self,
                 allocator: DynamicWorkerAllocator,
                 feedback_storage: Optional[FeedbackStorage] = None,
                 default_strategy: str = RoutingStrategy.HYBRID):
        self.allocator = allocator
        self.feedback_storage = feedback_storage
        self.default_strategy = default_strategy
        
        # Routing components
        self.routing_rules: List[RoutingRule] = []
        self.routing_history: List[RoutingDecision] = []
        self.strategy_weights = {
            RoutingStrategy.CAPABILITY_BASED: 0.3,
            RoutingStrategy.LOAD_BALANCED: 0.2,
            RoutingStrategy.PERFORMANCE_OPTIMIZED: 0.3,
            RoutingStrategy.COMPLEXITY_MATCHED: 0.2
        }
        
        # Performance tracking
        self.route_performance: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "success_rate": 0.0,
            "avg_execution_time": 0.0,
            "total_routed": 0
        })
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Initialize built-in rules
        self._initialize_default_rules()
        
        logger.info(f"Dynamic task router initialized with strategy: {default_strategy}")
    
    def _initialize_default_rules(self):
        """Initialize default routing rules."""
        # Route critical tasks to best performers
        self.add_routing_rule(
            rule_id="critical_to_best",
            name="Critical tasks to best performers",
            condition=lambda t: t.get("priority", 0) >= 8 or "critical" in t.get("title", "").lower(),
            priority=100
        )
        
        # Route documentation tasks to specialized workers
        self.add_routing_rule(
            rule_id="docs_to_specialist",
            name="Documentation to specialists",
            condition=lambda t: any(word in t.get("title", "").lower() 
                                  for word in ["document", "readme", "docs"]),
            target_capability=WorkerCapability.DOCUMENTATION,
            priority=90
        )
        
        # Route test tasks to test specialists
        self.add_routing_rule(
            rule_id="tests_to_specialist",
            name="Tests to test specialists",
            condition=lambda t: any(word in t.get("title", "").lower() 
                                  for word in ["test", "unittest", "pytest"]),
            target_capability=WorkerCapability.TESTING,
            priority=90
        )
        
        # Route debugging tasks
        self.add_routing_rule(
            rule_id="debug_to_specialist",
            name="Debugging to specialists",
            condition=lambda t: any(word in t.get("title", "").lower() 
                                  for word in ["debug", "fix", "bug", "error"]),
            target_capability=WorkerCapability.DEBUGGING,
            priority=85
        )
    
    def add_routing_rule(self,
                        rule_id: str,
                        name: str,
                        condition: Callable[[Dict[str, Any]], bool],
                        target_worker: Optional[str] = None,
                        target_capability: Optional[WorkerCapability] = None,
                        priority: int = 0) -> bool:
        """Add a routing rule.
        
        Args:
            rule_id: Unique rule identifier
            name: Rule name
            condition: Function to check if rule applies
            target_worker: Specific worker to route to
            target_capability: Required capability
            priority: Rule priority
            
        Returns:
            True if added successfully
        """
        with self._lock:
            # Check for duplicate
            if any(r.rule_id == rule_id for r in self.routing_rules):
                logger.warning(f"Routing rule {rule_id} already exists")
                return False
            
            rule = RoutingRule(
                rule_id=rule_id,
                name=name,
                condition=condition,
                target_worker=target_worker,
                target_capability=target_capability,
                priority=priority
            )
            
            self.routing_rules.append(rule)
            # Sort by priority
            self.routing_rules.sort(key=lambda r: r.priority, reverse=True)
            
            logger.info(f"Added routing rule: {name}")
            return True
    
    def remove_routing_rule(self, rule_id: str) -> bool:
        """Remove a routing rule."""
        with self._lock:
            self.routing_rules = [r for r in self.routing_rules if r.rule_id != rule_id]
            return True
    
    def route_task(self,
                  task_id: str,
                  task_title: str,
                  task_description: str,
                  task_metadata: Optional[Dict[str, Any]] = None,
                  strategy: Optional[str] = None) -> RoutingDecision:
        """Route a task to the best worker.
        
        Args:
            task_id: Task identifier
            task_title: Task title
            task_description: Task description
            task_metadata: Additional task metadata
            strategy: Routing strategy to use
            
        Returns:
            Routing decision
        """
        with self._lock:
            # Prepare task data
            task_data = {
                "id": task_id,
                "title": task_title,
                "description": task_description,
                **(task_metadata or {})
            }
            
            # Check routing rules first
            for rule in self.routing_rules:
                if rule.matches(task_data):
                    logger.info(f"Task {task_id} matched rule: {rule.name}")
                    
                    # Find worker based on rule
                    if rule.target_worker and rule.target_worker in self.allocator.workers:
                        decision = RoutingDecision(
                            task_id=task_id,
                            selected_worker=rule.target_worker,
                            strategy_used="rule_based",
                            score=1.0,
                            reasoning=f"Matched rule: {rule.name}"
                        )
                        self._record_decision(decision)
                        return decision
                    
                    elif rule.target_capability:
                        # Find workers with capability
                        capable_workers = [
                            w for w in self.allocator.workers.values()
                            if rule.target_capability in w.capabilities and w.is_available()
                        ]
                        if capable_workers:
                            # Pick best among capable
                            best_worker = max(
                                capable_workers,
                                key=lambda w: w.performance_score
                            )
                            decision = RoutingDecision(
                                task_id=task_id,
                                selected_worker=best_worker.worker_id,
                                strategy_used="rule_based",
                                score=best_worker.performance_score,
                                reasoning=f"Matched rule: {rule.name}, selected best with {rule.target_capability.value}"
                            )
                            self._record_decision(decision)
                            return decision
            
            # No rules matched, use strategy-based routing
            strategy = strategy or self.default_strategy
            
            if strategy == RoutingStrategy.HYBRID:
                return self._route_hybrid(task_id, task_title, task_description, task_data)
            elif strategy == RoutingStrategy.CAPABILITY_BASED:
                return self._route_by_capability(task_id, task_title, task_description, task_data)
            elif strategy == RoutingStrategy.LOAD_BALANCED:
                return self._route_load_balanced(task_id, task_title, task_description, task_data)
            elif strategy == RoutingStrategy.PERFORMANCE_OPTIMIZED:
                return self._route_by_performance(task_id, task_title, task_description, task_data)
            elif strategy == RoutingStrategy.COMPLEXITY_MATCHED:
                return self._route_by_complexity(task_id, task_title, task_description, task_data)
            else:
                # Fallback to allocator
                worker_id = self.allocator.allocate_worker(task_id, task_title, task_description)
                decision = RoutingDecision(
                    task_id=task_id,
                    selected_worker=worker_id,
                    strategy_used="fallback",
                    score=0.5,
                    reasoning="Used default allocator"
                )
                self._record_decision(decision)
                return decision
    
    def _route_hybrid(self, task_id: str, task_title: str, 
                     task_description: str, task_data: Dict[str, Any]) -> RoutingDecision:
        """Route using hybrid strategy combining multiple factors."""
        # Analyze task
        analyzer = TaskComplexityAnalyzer()
        requirements = analyzer.analyze_task(task_description, task_title)
        
        # Score each available worker
        worker_scores = {}
        alternatives = []
        
        for worker in self.allocator.workers.values():
            if not worker.is_available() or not worker.can_handle_task(requirements):
                continue
            
            # Base suitability score
            base_score = worker.calculate_suitability_score(requirements)
            
            # Capability match score
            capability_score = self._calculate_capability_score(worker, requirements)
            
            # Load balance score
            load_score = 1.0 - worker.current_load
            
            # Performance score from feedback
            perf_score = self._calculate_performance_score(worker.worker_id, requirements)
            
            # Combine scores with weights
            final_score = (
                base_score * 0.3 +
                capability_score * self.strategy_weights[RoutingStrategy.CAPABILITY_BASED] +
                load_score * self.strategy_weights[RoutingStrategy.LOAD_BALANCED] +
                perf_score * self.strategy_weights[RoutingStrategy.PERFORMANCE_OPTIMIZED]
            )
            
            worker_scores[worker.worker_id] = final_score
            alternatives.append((worker.worker_id, final_score))
        
        # Select best worker
        if not worker_scores:
            return RoutingDecision(
                task_id=task_id,
                selected_worker=None,
                strategy_used=RoutingStrategy.HYBRID,
                score=0.0,
                reasoning="No suitable workers available"
            )
        
        best_worker = max(worker_scores.items(), key=lambda x: x[1])
        
        # Allocate through allocator to maintain state
        allocated = self.allocator.allocate_worker(task_id, task_title, task_description, requirements)
        
        decision = RoutingDecision(
            task_id=task_id,
            selected_worker=allocated or best_worker[0],
            strategy_used=RoutingStrategy.HYBRID,
            score=best_worker[1],
            alternatives=sorted(alternatives, key=lambda x: x[1], reverse=True)[:5],
            reasoning=f"Hybrid scoring: base={base_score:.2f}, capability={capability_score:.2f}, load={load_score:.2f}, performance={perf_score:.2f}"
        )
        
        self._record_decision(decision)
        return decision
    
    def _route_by_capability(self, task_id: str, task_title: str,
                           task_description: str, task_data: Dict[str, Any]) -> RoutingDecision:
        """Route based on capability match."""
        analyzer = TaskComplexityAnalyzer()
        requirements = analyzer.analyze_task(task_description, task_title)
        
        # Find workers with best capability match
        best_match = None
        best_score = 0.0
        
        for worker in self.allocator.workers.values():
            if not worker.is_available() or not worker.can_handle_task(requirements):
                continue
            
            score = self._calculate_capability_score(worker, requirements)
            if score > best_score:
                best_score = score
                best_match = worker.worker_id
        
        if best_match:
            allocated = self.allocator.allocate_worker(task_id, task_title, task_description, requirements)
            
        decision = RoutingDecision(
            task_id=task_id,
            selected_worker=allocated if best_match else None,
            strategy_used=RoutingStrategy.CAPABILITY_BASED,
            score=best_score,
            reasoning=f"Best capability match with score {best_score:.2f}"
        )
        
        self._record_decision(decision)
        return decision
    
    def _route_load_balanced(self, task_id: str, task_title: str,
                           task_description: str, task_data: Dict[str, Any]) -> RoutingDecision:
        """Route to least loaded worker."""
        analyzer = TaskComplexityAnalyzer()
        requirements = analyzer.analyze_task(task_description, task_title)
        
        # Find least loaded capable worker
        best_worker = None
        lowest_load = float('inf')
        
        for worker in self.allocator.workers.values():
            if worker.can_handle_task(requirements) and worker.current_load < lowest_load:
                lowest_load = worker.current_load
                best_worker = worker.worker_id
        
        if best_worker:
            allocated = self.allocator.allocate_worker(task_id, task_title, task_description, requirements)
            
        decision = RoutingDecision(
            task_id=task_id,
            selected_worker=allocated if best_worker else None,
            strategy_used=RoutingStrategy.LOAD_BALANCED,
            score=1.0 - lowest_load if best_worker else 0.0,
            reasoning=f"Least loaded worker with load {lowest_load:.2f}"
        )
        
        self._record_decision(decision)
        return decision
    
    def _route_by_performance(self, task_id: str, task_title: str,
                            task_description: str, task_data: Dict[str, Any]) -> RoutingDecision:
        """Route based on historical performance."""
        analyzer = TaskComplexityAnalyzer()
        requirements = analyzer.analyze_task(task_description, task_title)
        
        # Score workers by performance
        best_worker = None
        best_score = 0.0
        
        for worker in self.allocator.workers.values():
            if not worker.is_available() or not worker.can_handle_task(requirements):
                continue
            
            perf_score = self._calculate_performance_score(worker.worker_id, requirements)
            if perf_score > best_score:
                best_score = perf_score
                best_worker = worker.worker_id
        
        if best_worker:
            allocated = self.allocator.allocate_worker(task_id, task_title, task_description, requirements)
            
        decision = RoutingDecision(
            task_id=task_id,
            selected_worker=allocated if best_worker else None,
            strategy_used=RoutingStrategy.PERFORMANCE_OPTIMIZED,
            score=best_score,
            reasoning=f"Best historical performance with score {best_score:.2f}"
        )
        
        self._record_decision(decision)
        return decision
    
    def _route_by_complexity(self, task_id: str, task_title: str,
                           task_description: str, task_data: Dict[str, Any]) -> RoutingDecision:
        """Route based on complexity matching."""
        analyzer = TaskComplexityAnalyzer()
        requirements = analyzer.analyze_task(task_description, task_title)
        
        # Find best complexity match
        best_worker = None
        best_score = 0.0
        
        for worker in self.allocator.workers.values():
            if not worker.is_available() or not worker.can_handle_task(requirements):
                continue
            
            # Prefer exact complexity match
            complexity_score = worker._get_complexity_match_score(requirements.complexity)
            if complexity_score > best_score:
                best_score = complexity_score
                best_worker = worker.worker_id
        
        if best_worker:
            allocated = self.allocator.allocate_worker(task_id, task_title, task_description, requirements)
            
        decision = RoutingDecision(
            task_id=task_id,
            selected_worker=allocated if best_worker else None,
            strategy_used=RoutingStrategy.COMPLEXITY_MATCHED,
            score=best_score,
            reasoning=f"Best complexity match with score {best_score:.2f}"
        )
        
        self._record_decision(decision)
        return decision
    
    def _calculate_capability_score(self, worker, requirements: TaskRequirements) -> float:
        """Calculate capability match score."""
        if not requirements.required_capabilities:
            return 1.0
        
        matched = len(worker.capabilities.intersection(requirements.required_capabilities))
        required = len(requirements.required_capabilities)
        
        # Base match ratio
        score = matched / required if required > 0 else 0.0
        
        # Bonus for specialization
        for cap in requirements.required_capabilities:
            if cap in worker.specialization_bonus:
                score += worker.specialization_bonus[cap] * 0.2
        
        return min(score, 1.0)
    
    def _calculate_performance_score(self, worker_id: str, requirements: TaskRequirements) -> float:
        """Calculate performance score from historical data."""
        if not self.feedback_storage:
            return 0.5  # Default neutral score
        
        try:
            analyzer = FeedbackAnalyzer(self.feedback_storage)
            perf = analyzer.get_worker_performance(worker_id)
            
            if not perf or perf.total_tasks < 3:  # Need minimum history
                return 0.5
            
            # Base score from success rate
            score = perf.success_rate
            
            # Adjust for complexity-specific performance
            if requirements.complexity in perf.average_response_time_by_complexity:
                avg_time = perf.average_response_time_by_complexity[requirements.complexity]
                expected_time = requirements.estimated_duration * 60
                
                # Bonus/penalty for speed
                if avg_time < expected_time * 0.8:
                    score *= 1.1
                elif avg_time > expected_time * 1.5:
                    score *= 0.9
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.debug(f"Error calculating performance score: {e}")
            return 0.5
    
    def _record_decision(self, decision: RoutingDecision):
        """Record routing decision for analysis."""
        with self._lock:
            self.routing_history.append(decision)
            
            # Update performance tracking
            strategy = decision.strategy_used
            if decision.selected_worker:
                self.route_performance[strategy]["total_routed"] += 1
            
            # Keep only recent history
            if len(self.routing_history) > 1000:
                self.routing_history = self.routing_history[-1000:]
    
    def update_route_performance(self, task_id: str, success: bool, execution_time: float):
        """Update routing performance metrics.
        
        Args:
            task_id: Task identifier
            success: Whether task completed successfully
            execution_time: Task execution time
        """
        with self._lock:
            # Find routing decision
            decision = next((d for d in reversed(self.routing_history) 
                           if d.task_id == task_id), None)
            
            if decision and decision.strategy_used:
                strategy = decision.strategy_used
                perf = self.route_performance[strategy]
                
                # Update metrics
                total = perf["total_routed"]
                if total > 0:
                    # Update success rate
                    current_successes = perf["success_rate"] * (total - 1)
                    perf["success_rate"] = (current_successes + (1 if success else 0)) / total
                    
                    # Update average execution time
                    current_avg = perf["avg_execution_time"]
                    perf["avg_execution_time"] = (current_avg * (total - 1) + execution_time) / total
    
    def get_routing_analytics(self) -> Dict[str, Any]:
        """Get routing analytics and statistics.
        
        Returns:
            Analytics data
        """
        with self._lock:
            analytics = {
                "total_routed": len(self.routing_history),
                "active_rules": len([r for r in self.routing_rules if r.enabled]),
                "strategy_performance": dict(self.route_performance),
                "recent_decisions": []
            }
            
            # Recent decisions
            for decision in self.routing_history[-20:]:
                analytics["recent_decisions"].append({
                    "task_id": decision.task_id,
                    "worker": decision.selected_worker,
                    "strategy": decision.strategy_used,
                    "score": decision.score,
                    "timestamp": decision.timestamp.isoformat()
                })
            
            # Strategy distribution
            strategy_counts = defaultdict(int)
            for decision in self.routing_history:
                strategy_counts[decision.strategy_used] += 1
            
            analytics["strategy_distribution"] = dict(strategy_counts)
            
            # Worker utilization
            worker_assignments = defaultdict(int)
            for decision in self.routing_history:
                if decision.selected_worker:
                    worker_assignments[decision.selected_worker] += 1
            
            analytics["worker_distribution"] = dict(worker_assignments)
            
            return analytics
    
    def optimize_routing_weights(self):
        """Optimize routing strategy weights based on performance."""
        with self._lock:
            # Calculate strategy effectiveness
            strategy_scores = {}
            
            for strategy, perf in self.route_performance.items():
                if perf["total_routed"] > 10:  # Need minimum sample
                    # Combine success rate and speed
                    effectiveness = perf["success_rate"]
                    if perf["avg_execution_time"] > 0:
                        # Normalize execution time (lower is better)
                        speed_factor = 1.0 / (1.0 + perf["avg_execution_time"] / 3600)
                        effectiveness = effectiveness * 0.7 + speed_factor * 0.3
                    
                    strategy_scores[strategy] = effectiveness
            
            # Update weights based on scores
            if strategy_scores:
                total_score = sum(strategy_scores.values())
                if total_score > 0:
                    for strategy, score in strategy_scores.items():
                        if strategy in self.strategy_weights:
                            # Gradual adjustment
                            current_weight = self.strategy_weights[strategy]
                            target_weight = score / total_score
                            self.strategy_weights[strategy] = (
                                current_weight * 0.7 + target_weight * 0.3
                            )
                    
                    # Normalize weights
                    weight_sum = sum(self.strategy_weights.values())
                    if weight_sum > 0:
                        for strategy in self.strategy_weights:
                            self.strategy_weights[strategy] /= weight_sum
                    
                    logger.info(f"Optimized routing weights: {self.strategy_weights}")


# Integration with orchestrator
def create_task_router(allocator: DynamicWorkerAllocator,
                      feedback_storage: Optional[FeedbackStorage] = None,
                      config: Optional[Dict[str, Any]] = None) -> DynamicTaskRouter:
    """Create configured task router.
    
    Args:
        allocator: Worker allocator
        feedback_storage: Feedback storage
        config: Router configuration
        
    Returns:
        Configured router
    """
    config = config or {}
    
    router = DynamicTaskRouter(
        allocator=allocator,
        feedback_storage=feedback_storage,
        default_strategy=config.get("default_strategy", RoutingStrategy.HYBRID)
    )
    
    # Add custom rules from config
    for rule_config in config.get("routing_rules", []):
        # Create condition function from config
        condition_str = rule_config.get("condition", "True")
        condition = eval(f"lambda t: {condition_str}")
        
        router.add_routing_rule(
            rule_id=rule_config["id"],
            name=rule_config["name"],
            condition=condition,
            target_worker=rule_config.get("target_worker"),
            target_capability=WorkerCapability(rule_config["target_capability"]) 
                if "target_capability" in rule_config else None,
            priority=rule_config.get("priority", 0)
        )
    
    return router