"""Specialized Agent Framework for Claude Orchestrator.

This module provides a framework for creating specialized agents with specific
capabilities and roles within the orchestration system.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json

from .feedback_model import FeedbackModel, create_info_feedback
from .task_master import Task as TMTask

logger = logging.getLogger(__name__)


class AgentCapability(Enum):
    """Capabilities that agents can possess."""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    DEBUGGING = "debugging"
    OPTIMIZATION = "optimization"
    SECURITY_ANALYSIS = "security_analysis"
    DATA_ANALYSIS = "data_analysis"
    UI_DESIGN = "ui_design"
    API_DESIGN = "api_design"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    RESEARCH = "research"
    PLANNING = "planning"


class AgentRole(Enum):
    """Predefined agent roles."""
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    TESTER = "tester"
    DOCUMENTER = "documenter"
    SECURITY_ANALYST = "security_analyst"
    DEVOPS = "devops"
    RESEARCHER = "researcher"
    PLANNER = "planner"
    GENERALIST = "generalist"


@dataclass
class AgentProfile:
    """Profile defining an agent's capabilities and preferences."""
    agent_id: str
    name: str
    role: AgentRole
    capabilities: Set[AgentCapability]
    model: str = "claude-3-5-sonnet-20241022"
    max_concurrent_tasks: int = 1
    priority_level: int = 1  # Higher number = higher priority
    specializations: List[str] = field(default_factory=list)
    performance_history: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if agent has a specific capability."""
        return capability in self.capabilities
    
    def get_capability_score(self, capability: AgentCapability) -> float:
        """Get performance score for a capability (0.0-1.0)."""
        if capability not in self.capabilities:
            return 0.0
        
        # Base score
        score = 0.7
        
        # Adjust based on performance history
        capability_key = f"capability_{capability.value}"
        if capability_key in self.performance_history:
            score = self.performance_history[capability_key]
        
        return min(max(score, 0.0), 1.0)
    
    def update_performance(self, capability: AgentCapability, score: float):
        """Update performance score for a capability."""
        if capability in self.capabilities:
            key = f"capability_{capability.value}"
            # Weighted average with existing score
            if key in self.performance_history:
                old_score = self.performance_history[key]
                self.performance_history[key] = 0.7 * old_score + 0.3 * score
            else:
                self.performance_history[key] = score


class SpecializedAgent(ABC):
    """Base class for specialized agents."""
    
    def __init__(self, profile: AgentProfile):
        self.profile = profile
        self.current_task: Optional[Any] = None
        self.task_history: List[Dict[str, Any]] = []
        self._initialized = False
        
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the agent."""
        pass
    
    @abstractmethod
    async def can_handle_task(self, task: TMTask) -> float:
        """Evaluate if agent can handle the task (0.0-1.0 confidence)."""
        pass
    
    @abstractmethod
    async def execute_task(self, task: TMTask, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the given task."""
        pass
    
    @abstractmethod
    async def validate_output(self, output: Any) -> bool:
        """Validate task output."""
        pass
    
    def record_task_result(self, task: TMTask, success: bool, duration: float):
        """Record task execution result."""
        self.task_history.append({
            "task_id": task.id,
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "duration": duration
        })
        
        # Update performance based on required capabilities
        if hasattr(task, 'required_capabilities'):
            for capability in task.required_capabilities:
                if isinstance(capability, AgentCapability):
                    score = 1.0 if success else 0.5
                    self.profile.update_performance(capability, score)


class CodeGenerationAgent(SpecializedAgent):
    """Agent specialized in code generation."""
    
    def __init__(self, profile: AgentProfile):
        super().__init__(profile)
        self.supported_languages = profile.metadata.get('languages', ['python', 'javascript', 'java'])
        self.code_style_preferences = profile.metadata.get('code_style', {})
        
    async def initialize(self) -> bool:
        """Initialize code generation agent."""
        logger.info(f"Initializing CodeGenerationAgent {self.profile.agent_id}")
        self._initialized = True
        return True
    
    async def can_handle_task(self, task: TMTask) -> float:
        """Evaluate if agent can handle code generation task."""
        confidence = 0.0
        
        # Check for code generation keywords
        task_text = f"{task.title} {task.description}".lower()
        code_keywords = ['implement', 'create', 'build', 'develop', 'code', 'function', 'class', 'module']
        
        if any(keyword in task_text for keyword in code_keywords):
            confidence += 0.5
        
        # Check for language requirements
        if hasattr(task, 'metadata') and 'language' in task.metadata:
            if task.metadata['language'] in self.supported_languages:
                confidence += 0.3
            else:
                confidence -= 0.2
        
        # Check capabilities
        if self.profile.has_capability(AgentCapability.CODE_GENERATION):
            confidence += 0.2
        
        return min(max(confidence, 0.0), 1.0)
    
    async def execute_task(self, task: TMTask, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code generation task."""
        logger.info(f"CodeGenerationAgent {self.profile.agent_id} executing task {task.id}")
        
        # Simulate code generation (in real implementation, this would call Claude API)
        result = {
            "status": "completed",
            "agent_id": self.profile.agent_id,
            "code": f"# Generated code for task: {task.title}\n# TODO: Implement actual code generation",
            "language": context.get('language', 'python'),
            "files_created": [],
            "files_modified": []
        }
        
        return result
    
    async def validate_output(self, output: Any) -> bool:
        """Validate generated code."""
        if not isinstance(output, dict):
            return False
        
        required_fields = ['status', 'code']
        return all(field in output for field in required_fields)


class CodeReviewAgent(SpecializedAgent):
    """Agent specialized in code review."""
    
    def __init__(self, profile: AgentProfile):
        super().__init__(profile)
        self.review_criteria = profile.metadata.get('review_criteria', [
            'code_quality', 'performance', 'security', 'maintainability'
        ])
        
    async def initialize(self) -> bool:
        """Initialize code review agent."""
        logger.info(f"Initializing CodeReviewAgent {self.profile.agent_id}")
        self._initialized = True
        return True
    
    async def can_handle_task(self, task: TMTask) -> float:
        """Evaluate if agent can handle code review task."""
        confidence = 0.0
        
        task_text = f"{task.title} {task.description}".lower()
        review_keywords = ['review', 'check', 'analyze', 'audit', 'inspect', 'validate']
        
        if any(keyword in task_text for keyword in review_keywords):
            confidence += 0.6
        
        if self.profile.has_capability(AgentCapability.CODE_REVIEW):
            confidence += 0.4
        
        return min(max(confidence, 0.0), 1.0)
    
    async def execute_task(self, task: TMTask, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code review task."""
        logger.info(f"CodeReviewAgent {self.profile.agent_id} reviewing task {task.id}")
        
        # Simulate code review
        result = {
            "status": "completed",
            "agent_id": self.profile.agent_id,
            "review_passed": True,
            "findings": [],
            "suggestions": ["Consider adding more comments", "Optimize loop performance"],
            "score": 0.85
        }
        
        return result
    
    async def validate_output(self, output: Any) -> bool:
        """Validate review output."""
        if not isinstance(output, dict):
            return False
        
        required_fields = ['status', 'review_passed', 'findings']
        return all(field in output for field in required_fields)


class TestingAgent(SpecializedAgent):
    """Agent specialized in testing."""
    
    def __init__(self, profile: AgentProfile):
        super().__init__(profile)
        self.test_types = profile.metadata.get('test_types', ['unit', 'integration', 'e2e'])
        
    async def initialize(self) -> bool:
        """Initialize testing agent."""
        logger.info(f"Initializing TestingAgent {self.profile.agent_id}")
        self._initialized = True
        return True
    
    async def can_handle_task(self, task: TMTask) -> float:
        """Evaluate if agent can handle testing task."""
        confidence = 0.0
        
        task_text = f"{task.title} {task.description}".lower()
        test_keywords = ['test', 'verify', 'validate', 'check', 'ensure', 'assert']
        
        if any(keyword in task_text for keyword in test_keywords):
            confidence += 0.7
        
        if self.profile.has_capability(AgentCapability.TESTING):
            confidence += 0.3
        
        return min(max(confidence, 0.0), 1.0)
    
    async def execute_task(self, task: TMTask, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute testing task."""
        logger.info(f"TestingAgent {self.profile.agent_id} testing task {task.id}")
        
        # Simulate test execution
        result = {
            "status": "completed",
            "agent_id": self.profile.agent_id,
            "tests_passed": 8,
            "tests_failed": 2,
            "coverage": 0.75,
            "test_results": []
        }
        
        return result
    
    async def validate_output(self, output: Any) -> bool:
        """Validate test output."""
        if not isinstance(output, dict):
            return False
        
        required_fields = ['status', 'tests_passed', 'tests_failed']
        return all(field in output for field in required_fields)


class AgentRegistry:
    """Registry for managing specialized agents."""
    
    def __init__(self):
        self.agents: Dict[str, SpecializedAgent] = {}
        self.role_agents: Dict[AgentRole, List[str]] = {}
        self.capability_agents: Dict[AgentCapability, List[str]] = {}
        self._initialized = False
        
    async def initialize(self):
        """Initialize the agent registry."""
        if self._initialized:
            return
        
        logger.info("Initializing Agent Registry")
        
        # Initialize all registered agents
        for agent_id, agent in self.agents.items():
            if not agent._initialized:
                success = await agent.initialize()
                if not success:
                    logger.error(f"Failed to initialize agent {agent_id}")
        
        self._initialized = True
    
    def register_agent(self, agent: SpecializedAgent):
        """Register a specialized agent."""
        agent_id = agent.profile.agent_id
        
        if agent_id in self.agents:
            logger.warning(f"Agent {agent_id} already registered, overwriting")
        
        self.agents[agent_id] = agent
        
        # Index by role
        role = agent.profile.role
        if role not in self.role_agents:
            self.role_agents[role] = []
        if agent_id not in self.role_agents[role]:
            self.role_agents[role].append(agent_id)
        
        # Index by capabilities
        for capability in agent.profile.capabilities:
            if capability not in self.capability_agents:
                self.capability_agents[capability] = []
            if agent_id not in self.capability_agents[capability]:
                self.capability_agents[capability].append(agent_id)
        
        logger.info(f"Registered agent {agent_id} with role {role.value}")
    
    def unregister_agent(self, agent_id: str):
        """Unregister an agent."""
        if agent_id not in self.agents:
            return
        
        agent = self.agents[agent_id]
        
        # Remove from role index
        role = agent.profile.role
        if role in self.role_agents:
            self.role_agents[role].remove(agent_id)
        
        # Remove from capability index
        for capability in agent.profile.capabilities:
            if capability in self.capability_agents:
                self.capability_agents[capability].remove(agent_id)
        
        del self.agents[agent_id]
        logger.info(f"Unregistered agent {agent_id}")
    
    def get_agent(self, agent_id: str) -> Optional[SpecializedAgent]:
        """Get agent by ID."""
        return self.agents.get(agent_id)
    
    def get_agents_by_role(self, role: AgentRole) -> List[SpecializedAgent]:
        """Get all agents with a specific role."""
        agent_ids = self.role_agents.get(role, [])
        return [self.agents[aid] for aid in agent_ids if aid in self.agents]
    
    def get_agents_by_capability(self, capability: AgentCapability) -> List[SpecializedAgent]:
        """Get all agents with a specific capability."""
        agent_ids = self.capability_agents.get(capability, [])
        return [self.agents[aid] for aid in agent_ids if aid in self.agents]
    
    async def find_best_agent_for_task(self, task: TMTask) -> Optional[SpecializedAgent]:
        """Find the best agent for a given task."""
        best_agent = None
        best_confidence = 0.0
        
        # Evaluate all agents
        for agent in self.agents.values():
            try:
                confidence = await agent.can_handle_task(task)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_agent = agent
            except Exception as e:
                logger.error(f"Error evaluating agent {agent.profile.agent_id}: {e}")
        
        if best_confidence > 0.5:  # Minimum confidence threshold
            return best_agent
        
        return None
    
    def get_agent_statistics(self) -> Dict[str, Any]:
        """Get statistics about registered agents."""
        stats = {
            "total_agents": len(self.agents),
            "agents_by_role": {},
            "agents_by_capability": {},
            "performance_summary": {}
        }
        
        # Count by role
        for role in AgentRole:
            count = len(self.role_agents.get(role, []))
            if count > 0:
                stats["agents_by_role"][role.value] = count
        
        # Count by capability
        for capability in AgentCapability:
            count = len(self.capability_agents.get(capability, []))
            if count > 0:
                stats["agents_by_capability"][capability.value] = count
        
        # Performance summary
        for agent in self.agents.values():
            if agent.profile.performance_history:
                avg_score = sum(agent.profile.performance_history.values()) / len(agent.profile.performance_history)
                stats["performance_summary"][agent.profile.agent_id] = {
                    "average_score": avg_score,
                    "task_count": len(agent.task_history)
                }
        
        return stats


# Agent Factory Functions
def create_code_generation_agent(agent_id: str, name: str, languages: List[str]) -> CodeGenerationAgent:
    """Create a code generation agent."""
    profile = AgentProfile(
        agent_id=agent_id,
        name=name,
        role=AgentRole.DEVELOPER,
        capabilities={AgentCapability.CODE_GENERATION, AgentCapability.DEBUGGING},
        metadata={"languages": languages}
    )
    return CodeGenerationAgent(profile)


def create_code_review_agent(agent_id: str, name: str) -> CodeReviewAgent:
    """Create a code review agent."""
    profile = AgentProfile(
        agent_id=agent_id,
        name=name,
        role=AgentRole.REVIEWER,
        capabilities={AgentCapability.CODE_REVIEW, AgentCapability.SECURITY_ANALYSIS}
    )
    return CodeReviewAgent(profile)


def create_testing_agent(agent_id: str, name: str, test_types: List[str]) -> TestingAgent:
    """Create a testing agent."""
    profile = AgentProfile(
        agent_id=agent_id,
        name=name,
        role=AgentRole.TESTER,
        capabilities={AgentCapability.TESTING, AgentCapability.DEBUGGING},
        metadata={"test_types": test_types}
    )
    return TestingAgent(profile)


# Global registry instance
agent_registry = AgentRegistry()


class AgentOrchestrator:
    """Orchestrates work among specialized agents."""
    
    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.task_assignments: Dict[str, str] = {}  # task_id -> agent_id
        
    async def assign_task(self, task: TMTask) -> Optional[str]:
        """Assign task to the best available agent."""
        agent = await self.registry.find_best_agent_for_task(task)
        
        if agent:
            self.task_assignments[task.id] = agent.profile.agent_id
            logger.info(f"Assigned task {task.id} to agent {agent.profile.agent_id}")
            return agent.profile.agent_id
        
        logger.warning(f"No suitable agent found for task {task.id}")
        return None
    
    async def execute_task(self, task: TMTask, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute task using assigned agent."""
        if task.id not in self.task_assignments:
            agent_id = await self.assign_task(task)
            if not agent_id:
                return {
                    "status": "failed",
                    "error": "No suitable agent found"
                }
        
        agent_id = self.task_assignments[task.id]
        agent = self.registry.get_agent(agent_id)
        
        if not agent:
            return {
                "status": "failed",
                "error": f"Agent {agent_id} not found"
            }
        
        try:
            # Execute task
            start_time = datetime.now()
            result = await agent.execute_task(task, context or {})
            duration = (datetime.now() - start_time).total_seconds()
            
            # Validate output
            is_valid = await agent.validate_output(result)
            
            # Record result
            agent.record_task_result(task, is_valid, duration)
            
            if not is_valid:
                result["validation_failed"] = True
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing task {task.id} with agent {agent_id}: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "agent_id": agent_id
            }
    
    def get_task_assignment(self, task_id: str) -> Optional[str]:
        """Get agent assigned to task."""
        return self.task_assignments.get(task_id)
    
    def reassign_task(self, task_id: str, new_agent_id: str) -> bool:
        """Reassign task to a different agent."""
        if new_agent_id not in self.registry.agents:
            return False
        
        self.task_assignments[task_id] = new_agent_id
        logger.info(f"Reassigned task {task_id} to agent {new_agent_id}")
        return True