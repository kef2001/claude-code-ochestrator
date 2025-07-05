"""Integration between Specialized Agents and Dynamic Task Router.

This module bridges the specialized agent framework with the existing
dynamic task routing system.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from .specialized_agents import (
    SpecializedAgent, AgentCapability, AgentRole,
    AgentRegistry, AgentOrchestrator, AgentProfile,
    create_code_generation_agent, create_code_review_agent, create_testing_agent
)
from .dynamic_task_router import DynamicTaskRouter, RoutingDecision, RoutingRule
from .dynamic_worker_allocation import (
    WorkerCapability, TaskComplexity, TaskRequirements,
    DynamicWorkerAllocator, WorkerProfile
)
from .task_master import Task as TMTask

logger = logging.getLogger(__name__)


class AgentWorkerAdapter:
    """Adapts specialized agents to work with the dynamic worker allocation system."""
    
    def __init__(self, agent: SpecializedAgent):
        self.agent = agent
        self._worker_profile = None
        
    def to_worker_profile(self) -> WorkerProfile:
        """Convert agent to worker profile for compatibility.
        
        Returns:
            Worker profile representation
        """
        if not self._worker_profile:
            # Map agent capabilities to worker capabilities
            worker_caps = set()
            capability_map = {
                AgentCapability.CODE_GENERATION: WorkerCapability.CODE_WRITING,
                AgentCapability.CODE_REVIEW: WorkerCapability.CODE_REVIEW,
                AgentCapability.TESTING: WorkerCapability.TESTING,
                AgentCapability.DOCUMENTATION: WorkerCapability.DOCUMENTATION,
                AgentCapability.DEBUGGING: WorkerCapability.DEBUGGING,
                AgentCapability.OPTIMIZATION: WorkerCapability.OPTIMIZATION,
                AgentCapability.ARCHITECTURE: WorkerCapability.ARCHITECTURE
            }
            
            for agent_cap in self.agent.profile.capabilities:
                if agent_cap in capability_map:
                    worker_caps.add(capability_map[agent_cap])
            
            # Determine complexity levels based on agent role
            complexity_levels = set()
            if self.agent.profile.role in [AgentRole.ARCHITECT, AgentRole.RESEARCHER]:
                complexity_levels = {TaskComplexity.HIGH, TaskComplexity.VERY_HIGH}
            elif self.agent.profile.role in [AgentRole.DEVELOPER, AgentRole.REVIEWER]:
                complexity_levels = {TaskComplexity.MEDIUM, TaskComplexity.HIGH}
            else:
                complexity_levels = {TaskComplexity.LOW, TaskComplexity.MEDIUM}
            
            self._worker_profile = WorkerProfile(
                worker_id=self.agent.profile.agent_id,
                name=self.agent.profile.name,
                capabilities=worker_caps,
                complexity_levels=complexity_levels,
                max_concurrent_tasks=self.agent.profile.max_concurrent_tasks,
                performance_score=0.8,  # Base score
                model=self.agent.profile.model
            )
            
        return self._worker_profile
    
    async def can_handle_task_requirements(self, requirements: TaskRequirements) -> float:
        """Check if agent can handle task with given requirements.
        
        Args:
            requirements: Task requirements from dynamic allocation
            
        Returns:
            Confidence score (0.0-1.0)
        """
        # Create a minimal task representation
        task = TMTask(
            id=f"eval_{datetime.now().timestamp()}",
            title=requirements.metadata.get("title", ""),
            description=requirements.metadata.get("description", ""),
            metadata={
                "complexity": requirements.complexity.value,
                "capabilities": [cap.value for cap in requirements.required_capabilities]
            }
        )
        
        return await self.agent.can_handle_task(task)


class SpecializedAgentRouter:
    """Routes tasks to specialized agents using the existing routing infrastructure."""
    
    def __init__(self,
                 agent_registry: AgentRegistry,
                 task_router: DynamicTaskRouter,
                 worker_allocator: DynamicWorkerAllocator):
        self.agent_registry = agent_registry
        self.task_router = task_router
        self.worker_allocator = worker_allocator
        self.agent_adapters: Dict[str, AgentWorkerAdapter] = {}
        
        # Initialize adapters
        self._create_adapters()
        
        # Add routing rules for specialized agents
        self._add_agent_routing_rules()
        
        logger.info("Specialized agent router initialized")
    
    def _create_adapters(self):
        """Create adapters for all registered agents."""
        for agent_id, agent in self.agent_registry.agents.items():
            adapter = AgentWorkerAdapter(agent)
            self.agent_adapters[agent_id] = adapter
            
            # Register with worker allocator
            worker_profile = adapter.to_worker_profile()
            self.worker_allocator.register_worker(worker_profile)
    
    def _add_agent_routing_rules(self):
        """Add routing rules for specialized agent types."""
        
        # Code generation tasks to code generation agents
        self.task_router.add_routing_rule(
            rule_id="agent_code_gen",
            name="Code generation to specialized agents",
            condition=lambda t: any(word in t.get("title", "").lower() 
                                  for word in ["implement", "create", "build", "generate"]),
            target_capability=WorkerCapability.CODE_WRITING,
            priority=95
        )
        
        # Code review tasks to review agents
        self.task_router.add_routing_rule(
            rule_id="agent_code_review",
            name="Code review to specialized agents",
            condition=lambda t: any(word in t.get("title", "").lower() 
                                  for word in ["review", "analyze code", "check code"]),
            target_capability=WorkerCapability.CODE_REVIEW,
            priority=95
        )
        
        # Architecture tasks to architect agents
        self.task_router.add_routing_rule(
            rule_id="agent_architecture",
            name="Architecture to specialized agents",
            condition=lambda t: any(word in t.get("title", "").lower() 
                                  for word in ["design", "architect", "structure"]),
            target_capability=WorkerCapability.ARCHITECTURE,
            priority=95
        )
    
    async def route_task_to_agent(self, task: TMTask) -> Optional[Tuple[str, RoutingDecision]]:
        """Route a task to a specialized agent.
        
        Args:
            task: Task to route
            
        Returns:
            Tuple of (agent_id, routing_decision) or None
        """
        # First try using the dynamic task router
        routing_decision = self.task_router.route_task(
            task_id=task.id,
            task_title=task.title,
            task_description=task.description,
            task_metadata={
                "priority": getattr(task, "priority", 5),
                "tags": getattr(task, "tags", [])
            }
        )
        
        # Check if selected worker is actually a specialized agent
        if routing_decision.selected_worker in self.agent_adapters:
            return routing_decision.selected_worker, routing_decision
        
        # Fallback to agent orchestrator
        agent_orchestrator = AgentOrchestrator(self.agent_registry)
        agent_id = await agent_orchestrator.assign_task(task)
        
        if agent_id:
            # Create routing decision for consistency
            decision = RoutingDecision(
                task_id=task.id,
                selected_worker=agent_id,
                strategy_used="agent_orchestrator",
                score=0.8,
                reasoning="Selected by specialized agent orchestrator"
            )
            return agent_id, decision
        
        return None
    
    async def execute_task_with_agent(self, 
                                     task: TMTask,
                                     agent_id: str,
                                     context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a task using a specialized agent.
        
        Args:
            task: Task to execute
            agent_id: Agent to use
            context: Execution context
            
        Returns:
            Execution result
        """
        agent = self.agent_registry.get_agent(agent_id)
        if not agent:
            return {
                "status": "failed",
                "error": f"Agent {agent_id} not found"
            }
        
        # Execute through agent orchestrator for consistency
        orchestrator = AgentOrchestrator(self.agent_registry)
        return await orchestrator.execute_task(task, context)
    
    def update_agent_performance(self, agent_id: str, task_id: str, success: bool, duration: float):
        """Update agent performance metrics.
        
        Args:
            agent_id: Agent ID
            task_id: Task ID
            success: Whether task succeeded
            duration: Execution duration
        """
        # Update in task router
        self.task_router.update_route_performance(task_id, success, duration)
        
        # Update worker allocator if agent is registered
        if agent_id in self.worker_allocator.workers:
            if success:
                self.worker_allocator.report_task_completion(task_id, agent_id)
            else:
                self.worker_allocator.report_task_failure(task_id, agent_id, "Task failed")
    
    def get_agent_statistics(self) -> Dict[str, Any]:
        """Get comprehensive agent statistics.
        
        Returns:
            Statistics including both agent and routing data
        """
        # Get agent registry stats
        agent_stats = self.agent_registry.get_agent_statistics()
        
        # Get routing analytics
        routing_stats = self.task_router.get_routing_analytics()
        
        # Get worker allocation stats
        worker_stats = self.worker_allocator.get_allocation_stats()
        
        # Combine statistics
        combined_stats = {
            "agents": agent_stats,
            "routing": routing_stats,
            "allocation": worker_stats,
            "agent_worker_mapping": {
                agent_id: adapter.to_worker_profile().worker_id
                for agent_id, adapter in self.agent_adapters.items()
            }
        }
        
        return combined_stats


def create_default_agents(agent_registry: AgentRegistry):
    """Create and register default specialized agents.
    
    Args:
        agent_registry: Registry to add agents to
    """
    # Import reviewer agents
    from .reviewer_agent import (
        create_reviewer_agent, create_output_analysis_reviewer,
        ReviewType
    )
    
    # Create code generation agents
    python_dev = create_code_generation_agent(
        agent_id="python_dev_001",
        name="Python Developer",
        languages=["python", "django", "flask"]
    )
    agent_registry.register_agent(python_dev)
    
    js_dev = create_code_generation_agent(
        agent_id="js_dev_001",
        name="JavaScript Developer",
        languages=["javascript", "typescript", "react", "node"]
    )
    agent_registry.register_agent(js_dev)
    
    # Create code review agent
    reviewer = create_code_review_agent(
        agent_id="reviewer_001",
        name="Code Reviewer"
    )
    agent_registry.register_agent(reviewer)
    
    # Create advanced reviewer agents
    quality_reviewer = create_reviewer_agent(
        agent_id="quality_reviewer_001",
        name="Quality Assurance Reviewer",
        review_types=[ReviewType.CODE_QUALITY, ReviewType.DOCUMENTATION, ReviewType.TESTING]
    )
    agent_registry.register_agent(quality_reviewer)
    
    security_reviewer = create_reviewer_agent(
        agent_id="security_reviewer_001",
        name="Security Reviewer",
        review_types=[ReviewType.SECURITY, ReviewType.COMPLIANCE]
    )
    agent_registry.register_agent(security_reviewer)
    
    output_analyzer = create_output_analysis_reviewer(
        agent_id="output_analyzer_001",
        name="Output Analysis Specialist"
    )
    agent_registry.register_agent(output_analyzer)
    
    # Create testing agents
    unit_tester = create_testing_agent(
        agent_id="unit_tester_001",
        name="Unit Test Specialist",
        test_types=["unit", "component"]
    )
    agent_registry.register_agent(unit_tester)
    
    integration_tester = create_testing_agent(
        agent_id="integration_tester_001",
        name="Integration Test Specialist",
        test_types=["integration", "e2e"]
    )
    agent_registry.register_agent(integration_tester)
    
    logger.info("Created default specialized agents including advanced reviewers")


async def integrate_specialized_agents(orchestrator) -> SpecializedAgentRouter:
    """Integrate specialized agents with the orchestrator.
    
    Args:
        orchestrator: Main orchestrator instance
        
    Returns:
        Configured agent router
    """
    # Get or create agent registry
    if not hasattr(orchestrator, 'agent_registry'):
        orchestrator.agent_registry = AgentRegistry()
        
    # Create default agents
    create_default_agents(orchestrator.agent_registry)
    
    # Initialize registry
    await orchestrator.agent_registry.initialize()
    
    # Get or create task router
    if not hasattr(orchestrator, 'task_router'):
        from .dynamic_task_router import create_task_router
        orchestrator.task_router = create_task_router(
            orchestrator.worker_allocator,
            orchestrator.feedback_storage
        )
    
    # Create specialized agent router
    agent_router = SpecializedAgentRouter(
        agent_registry=orchestrator.agent_registry,
        task_router=orchestrator.task_router,
        worker_allocator=orchestrator.worker_allocator
    )
    
    # Store reference in orchestrator
    orchestrator.agent_router = agent_router
    
    logger.info("Specialized agents integrated with orchestrator")
    
    return agent_router