"""Specialized Agent Framework for Claude Orchestrator

This module implements specialized agents that handle specific types of tasks
with optimized prompts and processing strategies.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AgentCapability(Enum):
    """Types of capabilities agents can have"""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    REFACTORING = "refactoring"
    DEBUGGING = "debugging"
    API_DESIGN = "api_design"
    DATABASE_DESIGN = "database_design"
    SECURITY_ANALYSIS = "security_analysis"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    DATA_ANALYSIS = "data_analysis"
    RESEARCH = "research"


@dataclass
class AgentProfile:
    """Profile defining an agent's specialization"""
    name: str
    description: str
    capabilities: List[AgentCapability]
    preferred_model: str = "claude-3-5-sonnet-20241022"
    custom_prompts: Dict[str, str] = None
    max_context_length: int = 200000
    temperature: float = 0.7
    
    def __post_init__(self):
        if self.custom_prompts is None:
            self.custom_prompts = {}


class SpecializedAgent(ABC):
    """Base class for specialized agents"""
    
    def __init__(self, profile: AgentProfile):
        self.profile = profile
        self.execution_history: List[Dict[str, Any]] = []
        
    @abstractmethod
    def can_handle(self, task: Dict[str, Any]) -> float:
        """Determine if this agent can handle the task
        
        Args:
            task: Task details
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        pass
        
    @abstractmethod
    def prepare_prompt(self, task: Dict[str, Any]) -> str:
        """Prepare specialized prompt for the task
        
        Args:
            task: Task details
            
        Returns:
            Formatted prompt
        """
        pass
        
    @abstractmethod
    def process_response(self, response: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process the agent's response
        
        Args:
            response: Raw response from the model
            task: Original task details
            
        Returns:
            Processed result
        """
        pass
        
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task using this agent
        
        Args:
            task: Task details
            
        Returns:
            Execution result
        """
        result = {
            'agent': self.profile.name,
            'task_id': task.get('task_id'),
            'confidence': self.can_handle(task),
            'prompt': self.prepare_prompt(task),
            'profile': self.profile
        }
        
        self.execution_history.append(result)
        return result


class CodeGenerationAgent(SpecializedAgent):
    """Agent specialized in code generation tasks"""
    
    def __init__(self):
        profile = AgentProfile(
            name="CodeGenerationSpecialist",
            description="Specialized in generating high-quality code implementations",
            capabilities=[
                AgentCapability.CODE_GENERATION,
                AgentCapability.API_DESIGN,
                AgentCapability.DATABASE_DESIGN
            ],
            custom_prompts={
                "prefix": "You are an expert software engineer specializing in clean, efficient code generation.",
                "suffix": "Ensure the code follows best practices, includes error handling, and is well-documented."
            }
        )
        super().__init__(profile)
        
    def can_handle(self, task: Dict[str, Any]) -> float:
        """Check if task involves code generation"""
        keywords = ['implement', 'create', 'build', 'develop', 'code', 'function', 'class', 'module']
        title = task.get('title', '').lower()
        description = task.get('description', '').lower()
        
        score = 0.0
        for keyword in keywords:
            if keyword in title:
                score += 0.3
            if keyword in description:
                score += 0.1
                
        # Check for specific patterns
        if 'api' in title or 'endpoint' in title:
            score += 0.2
        if 'database' in description or 'schema' in description:
            score += 0.2
            
        return min(score, 1.0)
        
    def prepare_prompt(self, task: Dict[str, Any]) -> str:
        """Prepare code generation prompt"""
        prompt = f"{self.profile.custom_prompts['prefix']}\n\n"
        prompt += f"Task: {task.get('title', 'Generate code')}\n"
        prompt += f"Description: {task.get('description', '')}\n"
        
        if task.get('requirements'):
            prompt += f"\nRequirements:\n"
            for req in task['requirements']:
                prompt += f"- {req}\n"
                
        if task.get('language'):
            prompt += f"\nLanguage: {task['language']}\n"
            
        prompt += f"\n{self.profile.custom_prompts['suffix']}"
        return prompt
        
    def process_response(self, response: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process code generation response"""
        # Extract code blocks
        import re
        code_blocks = re.findall(r'```(\w+)?\n(.*?)```', response, re.DOTALL)
        
        return {
            'code_blocks': code_blocks,
            'full_response': response,
            'files_to_create': self._extract_file_suggestions(response),
            'dependencies': self._extract_dependencies(response)
        }
        
    def _extract_file_suggestions(self, response: str) -> List[str]:
        """Extract suggested file names from response"""
        # Simple pattern matching for file names
        import re
        patterns = [
            r'create (?:a )?file (?:named |called )?["`\'](.*?)["`\']',
            r'(?:save|write) (?:this )?(?:to|as) ["`\'](.*?)["`\']',
            r'["`\'](.*?\.(?:py|js|java|cpp|go|rs|rb|php))["`\']'
        ]
        
        files = []
        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            files.extend(matches)
            
        return list(set(files))  # Remove duplicates
        
    def _extract_dependencies(self, response: str) -> List[str]:
        """Extract dependencies mentioned in response"""
        # Look for import/require statements
        import re
        patterns = [
            r'import (\w+)',
            r'from (\w+) import',
            r'require\(["\']([^"\']+)["\']\)',
            r'pip install ([\w\-]+)',
            r'npm install ([\w\-]+)'
        ]
        
        deps = []
        for pattern in patterns:
            matches = re.findall(pattern, response)
            deps.extend(matches)
            
        return list(set(deps))


class TestingAgent(SpecializedAgent):
    """Agent specialized in testing tasks"""
    
    def __init__(self):
        profile = AgentProfile(
            name="TestingSpecialist",
            description="Specialized in creating comprehensive test suites",
            capabilities=[
                AgentCapability.TESTING,
                AgentCapability.DEBUGGING
            ],
            custom_prompts={
                "prefix": "You are a testing expert focused on comprehensive test coverage and edge cases.",
                "suffix": "Include unit tests, integration tests, and edge case scenarios."
            }
        )
        super().__init__(profile)
        
    def can_handle(self, task: Dict[str, Any]) -> float:
        """Check if task involves testing"""
        keywords = ['test', 'verify', 'validate', 'check', 'assert', 'spec', 'coverage']
        title = task.get('title', '').lower()
        description = task.get('description', '').lower()
        
        score = 0.0
        for keyword in keywords:
            if keyword in title:
                score += 0.4
            if keyword in description:
                score += 0.2
                
        return min(score, 1.0)
        
    def prepare_prompt(self, task: Dict[str, Any]) -> str:
        """Prepare testing prompt"""
        prompt = f"{self.profile.custom_prompts['prefix']}\n\n"
        prompt += f"Task: {task.get('title', 'Create tests')}\n"
        prompt += f"Description: {task.get('description', '')}\n"
        
        if task.get('code_to_test'):
            prompt += f"\nCode to test:\n```\n{task['code_to_test']}\n```\n"
            
        if task.get('test_framework'):
            prompt += f"\nTest Framework: {task['test_framework']}\n"
            
        prompt += f"\n{self.profile.custom_prompts['suffix']}"
        return prompt
        
    def process_response(self, response: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process testing response"""
        return {
            'test_cases': self._extract_test_cases(response),
            'coverage_areas': self._extract_coverage_areas(response),
            'full_response': response
        }
        
    def _extract_test_cases(self, response: str) -> List[Dict[str, str]]:
        """Extract individual test cases from response"""
        import re
        # Look for test function definitions
        test_pattern = r'def (test_\w+)\(.*?\):(.*?)(?=def test_|\Z)'
        matches = re.findall(test_pattern, response, re.DOTALL)
        
        test_cases = []
        for name, body in matches:
            test_cases.append({
                'name': name,
                'body': body.strip()
            })
            
        return test_cases
        
    def _extract_coverage_areas(self, response: str) -> List[str]:
        """Extract what areas are being tested"""
        areas = []
        
        # Look for common testing areas mentioned
        patterns = [
            r'test(?:ing|s)? (.*?) (?:functionality|behavior|case)',
            r'(?:unit|integration|edge) (?:test|case) for (.*?)[\.\,\n]',
            r'(?:verify|validate|check) (?:that |if )?(.*?)[\.\,\n]'
        ]
        
        import re
        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            areas.extend([m.strip() for m in matches])
            
        return list(set(areas))


class DocumentationAgent(SpecializedAgent):
    """Agent specialized in documentation tasks"""
    
    def __init__(self):
        profile = AgentProfile(
            name="DocumentationSpecialist",
            description="Specialized in creating clear, comprehensive documentation",
            capabilities=[
                AgentCapability.DOCUMENTATION,
                AgentCapability.API_DESIGN
            ],
            custom_prompts={
                "prefix": "You are a technical writer expert in creating clear, comprehensive documentation.",
                "suffix": "Ensure documentation is well-structured, includes examples, and is easy to understand."
            }
        )
        super().__init__(profile)
        
    def can_handle(self, task: Dict[str, Any]) -> float:
        """Check if task involves documentation"""
        keywords = ['document', 'docs', 'readme', 'guide', 'manual', 'explain', 'describe']
        title = task.get('title', '').lower()
        description = task.get('description', '').lower()
        
        score = 0.0
        for keyword in keywords:
            if keyword in title:
                score += 0.4
            if keyword in description:
                score += 0.2
                
        return min(score, 1.0)
        
    def prepare_prompt(self, task: Dict[str, Any]) -> str:
        """Prepare documentation prompt"""
        prompt = f"{self.profile.custom_prompts['prefix']}\n\n"
        prompt += f"Task: {task.get('title', 'Create documentation')}\n"
        prompt += f"Description: {task.get('description', '')}\n"
        
        if task.get('code_to_document'):
            prompt += f"\nCode to document:\n```\n{task['code_to_document']}\n```\n"
            
        if task.get('documentation_style'):
            prompt += f"\nStyle: {task['documentation_style']}\n"
            
        prompt += f"\n{self.profile.custom_prompts['suffix']}"
        return prompt
        
    def process_response(self, response: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process documentation response"""
        return {
            'sections': self._extract_sections(response),
            'code_examples': self._extract_code_examples(response),
            'full_response': response
        }
        
    def _extract_sections(self, response: str) -> Dict[str, str]:
        """Extract documentation sections"""
        import re
        # Look for markdown headers
        sections = {}
        current_section = "Introduction"
        current_content = []
        
        lines = response.split('\n')
        for line in lines:
            if line.startswith('#'):
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                # Start new section
                current_section = line.strip('#').strip()
                current_content = []
            else:
                current_content.append(line)
                
        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content).strip()
            
        return sections
        
    def _extract_code_examples(self, response: str) -> List[Dict[str, str]]:
        """Extract code examples from documentation"""
        import re
        examples = []
        
        # Find code blocks
        code_blocks = re.findall(r'```(\w+)?\n(.*?)```', response, re.DOTALL)
        
        for lang, code in code_blocks:
            examples.append({
                'language': lang or 'text',
                'code': code.strip()
            })
            
        return examples


class RefactoringAgent(SpecializedAgent):
    """Agent specialized in code refactoring"""
    
    def __init__(self):
        profile = AgentProfile(
            name="RefactoringSpecialist",
            description="Specialized in improving code quality through refactoring",
            capabilities=[
                AgentCapability.REFACTORING,
                AgentCapability.CODE_REVIEW,
                AgentCapability.PERFORMANCE_OPTIMIZATION
            ],
            custom_prompts={
                "prefix": "You are a code refactoring expert focused on clean code principles and design patterns.",
                "suffix": "Explain each refactoring decision and ensure backward compatibility."
            }
        )
        super().__init__(profile)
        
    def can_handle(self, task: Dict[str, Any]) -> float:
        """Check if task involves refactoring"""
        keywords = ['refactor', 'improve', 'optimize', 'clean', 'redesign', 'restructure']
        title = task.get('title', '').lower()
        description = task.get('description', '').lower()
        
        score = 0.0
        for keyword in keywords:
            if keyword in title:
                score += 0.4
            if keyword in description:
                score += 0.2
                
        return min(score, 1.0)
        
    def prepare_prompt(self, task: Dict[str, Any]) -> str:
        """Prepare refactoring prompt"""
        prompt = f"{self.profile.custom_prompts['prefix']}\n\n"
        prompt += f"Task: {task.get('title', 'Refactor code')}\n"
        prompt += f"Description: {task.get('description', '')}\n"
        
        if task.get('code_to_refactor'):
            prompt += f"\nCode to refactor:\n```\n{task['code_to_refactor']}\n```\n"
            
        if task.get('refactoring_goals'):
            prompt += f"\nGoals:\n"
            for goal in task['refactoring_goals']:
                prompt += f"- {goal}\n"
                
        prompt += f"\n{self.profile.custom_prompts['suffix']}"
        return prompt
        
    def process_response(self, response: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process refactoring response"""
        return {
            'refactored_code': self._extract_refactored_code(response),
            'changes': self._extract_changes(response),
            'improvements': self._extract_improvements(response),
            'full_response': response
        }
        
    def _extract_refactored_code(self, response: str) -> str:
        """Extract the refactored code"""
        import re
        # Look for the main code block
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', response, re.DOTALL)
        
        # Usually the largest code block is the refactored version
        if code_blocks:
            return max(code_blocks, key=len)
        return ""
        
    def _extract_changes(self, response: str) -> List[str]:
        """Extract list of changes made"""
        changes = []
        
        # Look for bullet points or numbered lists describing changes
        import re
        patterns = [
            r'[-*•]\s*(.*?)(?=[-*•\n]|\Z)',
            r'\d+\.\s*(.*?)(?=\d+\.|\Z)',
            r'(?:changed|modified|updated|replaced|refactored)\s*(.*?)[\.\n]'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE | re.MULTILINE)
            changes.extend([m.strip() for m in matches if len(m.strip()) > 10])
            
        return list(set(changes))[:10]  # Limit to 10 most relevant
        
    def _extract_improvements(self, response: str) -> Dict[str, str]:
        """Extract improvements made"""
        improvements = {}
        
        # Look for common improvement categories
        categories = {
            'performance': r'(?:performance|speed|efficiency|optimization)',
            'readability': r'(?:readability|clarity|understand|clean)',
            'maintainability': r'(?:maintain|modular|decouple|separation)',
            'testability': r'(?:test|mock|unit|coverage)',
            'security': r'(?:security|vulnerability|sanitiz|validat)'
        }
        
        import re
        for category, pattern in categories.items():
            # Find sentences mentioning these improvements
            matches = re.findall(
                rf'([^.]*{pattern}[^.]*\.)',
                response,
                re.IGNORECASE
            )
            if matches:
                improvements[category] = matches[0].strip()
                
        return improvements


class AgentRegistry:
    """Registry for managing specialized agents"""
    
    def __init__(self):
        self.agents: Dict[str, SpecializedAgent] = {}
        self._register_default_agents()
        
    def _register_default_agents(self):
        """Register the default set of specialized agents"""
        default_agents = [
            CodeGenerationAgent(),
            TestingAgent(),
            DocumentationAgent(),
            RefactoringAgent()
        ]
        
        for agent in default_agents:
            self.register_agent(agent)
            
    def register_agent(self, agent: SpecializedAgent):
        """Register a specialized agent"""
        self.agents[agent.profile.name] = agent
        logger.info(f"Registered agent: {agent.profile.name}")
        
    def find_best_agent(self, task: Dict[str, Any]) -> Optional[SpecializedAgent]:
        """Find the best agent for a task"""
        best_agent = None
        best_score = 0.0
        
        for agent in self.agents.values():
            score = agent.can_handle(task)
            if score > best_score:
                best_score = score
                best_agent = agent
                
        if best_score > 0.3:  # Minimum confidence threshold
            logger.info(f"Selected {best_agent.profile.name} for task with confidence {best_score:.2f}")
            return best_agent
            
        return None
        
    def get_agent(self, name: str) -> Optional[SpecializedAgent]:
        """Get agent by name"""
        return self.agents.get(name)
        
    def list_agents(self) -> List[AgentProfile]:
        """List all registered agents"""
        return [agent.profile for agent in self.agents.values()]
        
    def get_capabilities(self) -> Dict[AgentCapability, List[str]]:
        """Get mapping of capabilities to agents"""
        capabilities = {}
        
        for agent in self.agents.values():
            for capability in agent.profile.capabilities:
                if capability not in capabilities:
                    capabilities[capability] = []
                capabilities[capability].append(agent.profile.name)
                
        return capabilities


# Global registry instance
_registry = None


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry"""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry