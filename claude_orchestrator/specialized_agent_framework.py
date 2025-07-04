"""Specialized Agent Framework for task-specific AI agents."""

import logging
import json
from typing import Dict, List, Any, Optional, Callable, Type
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime
import threading

from .dynamic_worker_allocation import WorkerCapability, TaskComplexity
from .feedback_model import create_success_feedback, create_error_feedback

logger = logging.getLogger(__name__)


class AgentRole:
    """Predefined agent roles."""
    CODE_REVIEWER = "code_reviewer"
    ARCHITECT = "architect"
    DEBUGGER = "debugger"
    TESTER = "tester"
    DOCUMENTER = "documenter"
    REFACTORER = "refactorer"
    SECURITY_AUDITOR = "security_auditor"
    PERFORMANCE_OPTIMIZER = "performance_optimizer"
    DATA_ANALYST = "data_analyst"
    DEVOPS_ENGINEER = "devops_engineer"


@dataclass
class AgentCapabilities:
    """Capabilities and constraints for an agent."""
    primary_role: str
    secondary_roles: List[str] = field(default_factory=list)
    max_complexity: TaskComplexity = TaskComplexity.HIGH
    supported_languages: List[str] = field(default_factory=list)
    supported_frameworks: List[str] = field(default_factory=list)
    tools_allowed: List[str] = field(default_factory=list)
    context_window: int = 200000  # tokens
    
    def can_handle(self, requirements: Dict[str, Any]) -> bool:
        """Check if agent can handle given requirements."""
        # Check complexity
        if "complexity" in requirements:
            req_complexity = requirements["complexity"]
            if isinstance(req_complexity, str):
                req_complexity = TaskComplexity(req_complexity)
            complexity_order = [
                TaskComplexity.TRIVIAL,
                TaskComplexity.LOW,
                TaskComplexity.MEDIUM,
                TaskComplexity.HIGH,
                TaskComplexity.CRITICAL
            ]
            if complexity_order.index(req_complexity) > complexity_order.index(self.max_complexity):
                return False
        
        # Check language requirements
        if "language" in requirements and self.supported_languages:
            if requirements["language"] not in self.supported_languages:
                return False
        
        # Check framework requirements
        if "framework" in requirements and self.supported_frameworks:
            if requirements["framework"] not in self.supported_frameworks:
                return False
        
        return True


class SpecializedAgent(ABC):
    """Base class for specialized agents."""
    
    def __init__(self, 
                 agent_id: str,
                 name: str,
                 capabilities: AgentCapabilities):
        self.agent_id = agent_id
        self.name = name
        self.capabilities = capabilities
        self.active_tasks = 0
        self.total_tasks_completed = 0
        self.success_rate = 1.0
        self._lock = threading.Lock()
        
    @abstractmethod
    def prepare_prompt(self, task: Dict[str, Any]) -> str:
        """Prepare specialized prompt for the task."""
        pass
    
    @abstractmethod
    def process_response(self, response: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process agent response into structured output."""
        pass
    
    @abstractmethod
    def validate_output(self, output: Dict[str, Any], task: Dict[str, Any]) -> bool:
        """Validate agent output meets requirements."""
        pass
    
    def pre_process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-process task before execution."""
        return task
    
    def post_process(self, output: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process output after execution."""
        return output
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        with self._lock:
            return {
                "agent_id": self.agent_id,
                "name": self.name,
                "role": self.capabilities.primary_role,
                "active_tasks": self.active_tasks,
                "total_completed": self.total_tasks_completed,
                "success_rate": self.success_rate
            }


class CodeReviewerAgent(SpecializedAgent):
    """Specialized agent for code review."""
    
    def __init__(self, agent_id: str = "code_reviewer_1"):
        capabilities = AgentCapabilities(
            primary_role=AgentRole.CODE_REVIEWER,
            secondary_roles=[AgentRole.SECURITY_AUDITOR],
            supported_languages=["python", "javascript", "typescript", "java", "go"],
            tools_allowed=["read_file", "search_files", "list_files"]
        )
        super().__init__(agent_id, "Code Reviewer Agent", capabilities)
        
    def prepare_prompt(self, task: Dict[str, Any]) -> str:
        """Prepare code review prompt."""
        code_path = task.get("code_path", "")
        review_type = task.get("review_type", "general")
        
        prompt = f"""You are an expert code reviewer. Please review the code at {code_path}.

Focus on:
1. Code quality and readability
2. Best practices and design patterns
3. Potential bugs or issues
4. Security vulnerabilities
5. Performance considerations
6. Test coverage

Review Type: {review_type}

Provide structured feedback with:
- Summary of findings
- Critical issues (if any)
- Suggestions for improvement
- Code quality score (1-10)
"""
        
        if "specific_concerns" in task:
            prompt += f"\nSpecific concerns to address:\n{task['specific_concerns']}"
        
        return prompt
    
    def process_response(self, response: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process code review response."""
        # Parse structured response
        output = {
            "review_id": f"review_{datetime.now().timestamp()}",
            "code_path": task.get("code_path", ""),
            "review_type": task.get("review_type", "general"),
            "findings": [],
            "critical_issues": [],
            "suggestions": [],
            "quality_score": 0,
            "raw_response": response
        }
        
        # Extract sections from response
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect sections
            if "critical issue" in line.lower():
                current_section = "critical"
            elif "suggestion" in line.lower():
                current_section = "suggestion"
            elif "finding" in line.lower():
                current_section = "finding"
            elif "score:" in line.lower():
                try:
                    score = float(line.split(":")[-1].strip().split("/")[0])
                    output["quality_score"] = score
                except:
                    pass
            elif line.startswith("-") or line.startswith("*"):
                # Add to current section
                item = line[1:].strip()
                if current_section == "critical":
                    output["critical_issues"].append(item)
                elif current_section == "suggestion":
                    output["suggestions"].append(item)
                elif current_section == "finding":
                    output["findings"].append(item)
        
        return output
    
    def validate_output(self, output: Dict[str, Any], task: Dict[str, Any]) -> bool:
        """Validate review output."""
        # Must have at least some findings or score
        return (
            output.get("quality_score", 0) > 0 or
            len(output.get("findings", [])) > 0 or
            len(output.get("critical_issues", [])) > 0
        )


class DebuggerAgent(SpecializedAgent):
    """Specialized agent for debugging."""
    
    def __init__(self, agent_id: str = "debugger_1"):
        capabilities = AgentCapabilities(
            primary_role=AgentRole.DEBUGGER,
            secondary_roles=[AgentRole.TESTER],
            max_complexity=TaskComplexity.CRITICAL,
            tools_allowed=["read_file", "edit_file", "run_command", "search_files"]
        )
        super().__init__(agent_id, "Debugger Agent", capabilities)
    
    def prepare_prompt(self, task: Dict[str, Any]) -> str:
        """Prepare debugging prompt."""
        error_description = task.get("error_description", "Unknown error")
        error_trace = task.get("error_trace", "")
        context = task.get("context", {})
        
        prompt = f"""You are an expert debugger. Please diagnose and fix the following issue:

Error Description: {error_description}

Error Trace:
{error_trace}

Context:
- File: {context.get('file_path', 'Unknown')}
- Function: {context.get('function', 'Unknown')}
- Line: {context.get('line_number', 'Unknown')}

Please:
1. Analyze the error and identify the root cause
2. Provide a detailed explanation of what's wrong
3. Suggest or implement a fix
4. Explain how to prevent this issue in the future

Use debugging tools as needed to investigate."""
        
        return prompt
    
    def process_response(self, response: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process debugging response."""
        return {
            "debug_id": f"debug_{datetime.now().timestamp()}",
            "error_description": task.get("error_description", ""),
            "root_cause": self._extract_section(response, "root cause"),
            "explanation": self._extract_section(response, "explanation"),
            "fix_implemented": self._extract_section(response, "fix"),
            "prevention": self._extract_section(response, "prevent"),
            "files_modified": self._extract_files(response),
            "raw_response": response
        }
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a section from response text."""
        lines = text.split('\n')
        in_section = False
        section_content = []
        
        for line in lines:
            if section_name.lower() in line.lower():
                in_section = True
                continue
            elif in_section and line.strip() and not line.startswith(' '):
                # End of section
                break
            elif in_section:
                section_content.append(line)
        
        return '\n'.join(section_content).strip()
    
    def _extract_files(self, text: str) -> List[str]:
        """Extract file paths mentioned in response."""
        import re
        # Simple pattern to match file paths
        pattern = r'[\w/\\]+\.\w+'
        return list(set(re.findall(pattern, text)))
    
    def validate_output(self, output: Dict[str, Any], task: Dict[str, Any]) -> bool:
        """Validate debugging output."""
        return bool(output.get("root_cause") or output.get("explanation"))


class ArchitectAgent(SpecializedAgent):
    """Specialized agent for system architecture and design."""
    
    def __init__(self, agent_id: str = "architect_1"):
        capabilities = AgentCapabilities(
            primary_role=AgentRole.ARCHITECT,
            secondary_roles=[AgentRole.CODE_REVIEWER],
            max_complexity=TaskComplexity.CRITICAL,
            tools_allowed=["read_file", "create_file", "list_files", "search_files"]
        )
        super().__init__(agent_id, "Architecture Agent", capabilities)
    
    def prepare_prompt(self, task: Dict[str, Any]) -> str:
        """Prepare architecture prompt."""
        project_type = task.get("project_type", "application")
        requirements = task.get("requirements", [])
        constraints = task.get("constraints", [])
        
        prompt = f"""You are a senior software architect. Design the architecture for a {project_type}.

Requirements:
{json.dumps(requirements, indent=2)}

Constraints:
{json.dumps(constraints, indent=2)}

Please provide:
1. High-level architecture overview
2. Component breakdown and responsibilities
3. Data flow and interactions
4. Technology stack recommendations
5. Scalability considerations
6. Security architecture
7. Deployment architecture

Format your response with clear sections and diagrams where helpful."""
        
        return prompt
    
    def process_response(self, response: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process architecture response."""
        return {
            "design_id": f"arch_{datetime.now().timestamp()}",
            "project_type": task.get("project_type", ""),
            "overview": self._extract_section(response, "overview"),
            "components": self._extract_components(response),
            "technology_stack": self._extract_tech_stack(response),
            "scalability": self._extract_section(response, "scalability"),
            "security": self._extract_section(response, "security"),
            "deployment": self._extract_section(response, "deployment"),
            "diagrams": self._extract_diagrams(response),
            "raw_response": response
        }
    
    def _extract_components(self, text: str) -> List[Dict[str, str]]:
        """Extract component descriptions."""
        components = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if "component" in line.lower() and (":" in line or "-" in line):
                name = line.split(":")[-1].strip() if ":" in line else line.split("-")[-1].strip()
                # Get description from next lines
                desc = []
                for j in range(i + 1, min(i + 4, len(lines))):
                    if lines[j].strip() and not lines[j].startswith(' '):
                        break
                    desc.append(lines[j].strip())
                
                components.append({
                    "name": name,
                    "description": ' '.join(desc)
                })
        
        return components
    
    def _extract_tech_stack(self, text: str) -> Dict[str, str]:
        """Extract technology recommendations."""
        stack = {}
        categories = ["backend", "frontend", "database", "cache", "queue", "monitoring"]
        
        for category in categories:
            if category in text.lower():
                # Find technology mentioned near category
                stack[category] = self._extract_section(text, category)
        
        return stack
    
    def _extract_diagrams(self, text: str) -> List[str]:
        """Extract diagram descriptions or ASCII art."""
        diagrams = []
        lines = text.split('\n')
        in_diagram = False
        current_diagram = []
        
        for line in lines:
            if any(indicator in line for indicator in ['```', '┌', '─', '│', '+']):
                if not in_diagram:
                    in_diagram = True
                current_diagram.append(line)
            elif in_diagram and line.strip() == '':
                # End of diagram
                if current_diagram:
                    diagrams.append('\n'.join(current_diagram))
                    current_diagram = []
                in_diagram = False
        
        return diagrams
    
    def validate_output(self, output: Dict[str, Any], task: Dict[str, Any]) -> bool:
        """Validate architecture output."""
        return (
            bool(output.get("overview")) and
            len(output.get("components", [])) > 0
        )


class TestGeneratorAgent(SpecializedAgent):
    """Specialized agent for generating tests."""
    
    def __init__(self, agent_id: str = "test_generator_1"):
        capabilities = AgentCapabilities(
            primary_role=AgentRole.TESTER,
            supported_languages=["python", "javascript", "typescript"],
            supported_frameworks=["pytest", "jest", "mocha", "unittest"],
            tools_allowed=["read_file", "create_file", "edit_file", "run_command"]
        )
        super().__init__(agent_id, "Test Generator Agent", capabilities)
    
    def prepare_prompt(self, task: Dict[str, Any]) -> str:
        """Prepare test generation prompt."""
        code_path = task.get("code_path", "")
        test_type = task.get("test_type", "unit")
        framework = task.get("framework", "pytest")
        
        prompt = f"""You are an expert test engineer. Generate comprehensive {test_type} tests for the code at {code_path}.

Test Framework: {framework}

Requirements:
1. Achieve high code coverage (aim for >90%)
2. Test edge cases and error conditions
3. Include positive and negative test cases
4. Use appropriate mocking where needed
5. Follow testing best practices
6. Include clear test descriptions

Generate tests that are:
- Well-organized and maintainable
- Independent and isolated
- Fast and reliable
- Clear in their intent"""
        
        return prompt
    
    def process_response(self, response: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process test generation response."""
        return {
            "test_id": f"test_{datetime.now().timestamp()}",
            "code_path": task.get("code_path", ""),
            "test_type": task.get("test_type", "unit"),
            "framework": task.get("framework", ""),
            "test_code": self._extract_code(response),
            "test_cases": self._extract_test_cases(response),
            "coverage_estimate": self._extract_coverage(response),
            "raw_response": response
        }
    
    def _extract_code(self, text: str) -> str:
        """Extract test code from response."""
        import re
        # Find code blocks
        code_pattern = r'```(?:python|javascript|typescript)?\n(.*?)\n```'
        matches = re.findall(code_pattern, text, re.DOTALL)
        return '\n\n'.join(matches) if matches else text
    
    def _extract_test_cases(self, text: str) -> List[str]:
        """Extract individual test case names."""
        import re
        # Common test function patterns
        patterns = [
            r'def (test_\w+)',
            r'it\(["\']([^"\']+)',
            r'test\(["\']([^"\']+)',
            r'describe\(["\']([^"\']+)'
        ]
        
        test_cases = []
        for pattern in patterns:
            test_cases.extend(re.findall(pattern, text))
        
        return list(set(test_cases))
    
    def _extract_coverage(self, text: str) -> float:
        """Extract coverage estimate from response."""
        import re
        # Look for percentage mentions
        pattern = r'(\d+)%'
        matches = re.findall(pattern, text)
        if matches:
            # Return highest percentage mentioned
            return max(float(m) for m in matches) / 100
        return 0.0
    
    def validate_output(self, output: Dict[str, Any], task: Dict[str, Any]) -> bool:
        """Validate test output."""
        return bool(output.get("test_code")) and len(output.get("test_cases", [])) > 0


class AgentOrchestrator:
    """Orchestrates specialized agents for complex tasks."""
    
    def __init__(self):
        self.agents: Dict[str, SpecializedAgent] = {}
        self.agent_registry: Dict[str, Type[SpecializedAgent]] = {
            AgentRole.CODE_REVIEWER: CodeReviewerAgent,
            AgentRole.DEBUGGER: DebuggerAgent,
            AgentRole.ARCHITECT: ArchitectAgent,
            AgentRole.TESTER: TestGeneratorAgent
        }
        self._lock = threading.Lock()
        
        # Initialize default agents
        self._initialize_default_agents()
        
    def _initialize_default_agents(self):
        """Initialize one instance of each agent type."""
        for role, agent_class in self.agent_registry.items():
            agent = agent_class()
            self.register_agent(agent)
    
    def register_agent(self, agent: SpecializedAgent) -> bool:
        """Register a specialized agent."""
        with self._lock:
            if agent.agent_id in self.agents:
                logger.warning(f"Agent {agent.agent_id} already registered")
                return False
            
            self.agents[agent.agent_id] = agent
            logger.info(f"Registered agent: {agent.name} ({agent.agent_id})")
            return True
    
    def find_agent_for_task(self, task: Dict[str, Any]) -> Optional[SpecializedAgent]:
        """Find the best agent for a task."""
        with self._lock:
            # Check if specific role is requested
            if "agent_role" in task:
                role = task["agent_role"]
                # Find agent with this role
                for agent in self.agents.values():
                    if agent.capabilities.primary_role == role:
                        if agent.capabilities.can_handle(task):
                            return agent
            
            # Find any capable agent
            capable_agents = []
            for agent in self.agents.values():
                if agent.capabilities.can_handle(task):
                    capable_agents.append(agent)
            
            if capable_agents:
                # Return least busy agent
                return min(capable_agents, key=lambda a: a.active_tasks)
            
            return None
    
    def execute_specialized_task(self, 
                               task: Dict[str, Any],
                               worker_execute_fn: Callable) -> Dict[str, Any]:
        """Execute a task with specialized agent.
        
        Args:
            task: Task description
            worker_execute_fn: Function to execute prompts
            
        Returns:
            Task result
        """
        # Find suitable agent
        agent = self.find_agent_for_task(task)
        if not agent:
            return {
                "success": False,
                "error": "No suitable specialized agent found",
                "task": task
            }
        
        try:
            with self._lock:
                agent.active_tasks += 1
            
            # Pre-process task
            processed_task = agent.pre_process(task)
            
            # Prepare specialized prompt
            prompt = agent.prepare_prompt(processed_task)
            
            # Execute with worker
            result = worker_execute_fn(prompt)
            
            if result.get("success"):
                # Process response
                output = agent.process_response(result["output"], processed_task)
                
                # Validate output
                if agent.validate_output(output, processed_task):
                    # Post-process
                    final_output = agent.post_process(output, processed_task)
                    
                    with self._lock:
                        agent.total_tasks_completed += 1
                    
                    return {
                        "success": True,
                        "output": final_output,
                        "agent_id": agent.agent_id,
                        "agent_role": agent.capabilities.primary_role
                    }
                else:
                    return {
                        "success": False,
                        "error": "Agent output validation failed",
                        "output": output,
                        "agent_id": agent.agent_id
                    }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Execution failed"),
                    "agent_id": agent.agent_id
                }
                
        except Exception as e:
            logger.error(f"Error in specialized task execution: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_id": agent.agent_id
            }
        finally:
            with self._lock:
                agent.active_tasks -= 1
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        with self._lock:
            return {
                "total_agents": len(self.agents),
                "agents": [agent.get_status() for agent in self.agents.values()]
            }


# Create global orchestrator instance
agent_orchestrator = AgentOrchestrator()