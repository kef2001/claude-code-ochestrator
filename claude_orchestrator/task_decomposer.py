"""
Automatic Task Decomposition System
Intelligently breaks down large tasks into smaller, manageable subtasks
"""

import logging
import re
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)


class DecompositionStrategy(Enum):
    """Task decomposition strategies"""
    SEQUENTIAL = "sequential"        # Tasks that must be done in order
    PARALLEL = "parallel"           # Tasks that can be done simultaneously
    HIERARCHICAL = "hierarchical"   # Nested task structures
    FEATURE_BASED = "feature_based" # Decompose by features/components
    LAYER_BASED = "layer_based"     # Decompose by architectural layers
    WORKFLOW = "workflow"           # Follow a specific workflow pattern


class TaskComplexityLevel(Enum):
    """Task complexity assessment"""
    TRIVIAL = 1
    SIMPLE = 2
    MODERATE = 3
    COMPLEX = 4
    VERY_COMPLEX = 5


@dataclass
class SubtaskBlueprint:
    """Blueprint for a subtask"""
    title: str
    description: str
    estimated_duration_minutes: int
    dependencies: List[str] = field(default_factory=list)  # IDs of prerequisite subtasks
    priority: int = 5  # 1-10
    complexity: TaskComplexityLevel = TaskComplexityLevel.SIMPLE
    required_skills: Set[str] = field(default_factory=set)
    deliverables: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate subtask blueprint after creation"""
        if self.estimated_duration_minutes <= 0:
            self.estimated_duration_minutes = 30  # Default to 30 minutes
        if not self.title.strip():
            raise ValueError("Subtask title cannot be empty")
        if not self.description.strip():
            raise ValueError("Subtask description cannot be empty")


@dataclass
class DecompositionPlan:
    """Complete plan for task decomposition"""
    original_task_id: str
    original_title: str
    original_description: str
    strategy: DecompositionStrategy
    subtasks: List[SubtaskBlueprint]
    execution_order: List[List[str]] = field(default_factory=list)  # Groups of subtask IDs that can run in parallel
    total_estimated_duration: int = 0
    confidence_score: float = 0.0  # 0.0-1.0 confidence in decomposition quality
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived values after creation"""
        if not self.total_estimated_duration:
            self.total_estimated_duration = sum(st.estimated_duration_minutes for st in self.subtasks)
        
        if not self.execution_order:
            self.execution_order = self._calculate_execution_order()
    
    def _calculate_execution_order(self) -> List[List[str]]:
        """Calculate optimal execution order based on dependencies"""
        # Create a mapping of subtask titles for dependency resolution
        title_to_index = {st.title: i for i, st in enumerate(self.subtasks)}
        
        # Build dependency graph
        remaining_tasks = set(range(len(self.subtasks)))
        completed_tasks = set()
        execution_order = []
        
        while remaining_tasks:
            # Find tasks with no unmet dependencies
            ready_tasks = []
            for task_idx in remaining_tasks:
                subtask = self.subtasks[task_idx]
                dependencies_met = all(
                    title_to_index.get(dep_title, -1) in completed_tasks or dep_title not in title_to_index
                    for dep_title in subtask.dependencies
                )
                if dependencies_met:
                    ready_tasks.append(str(task_idx))
            
            if not ready_tasks:
                # Circular dependency or missing dependency - just take remaining tasks
                ready_tasks = [str(i) for i in remaining_tasks]
                logger.warning(f"Potential circular dependency in task decomposition")
            
            execution_order.append(ready_tasks)
            
            # Mark these tasks as completed for next iteration
            for task_id in ready_tasks:
                task_idx = int(task_id)
                completed_tasks.add(task_idx)
                remaining_tasks.discard(task_idx)
        
        return execution_order
    
    def get_critical_path_duration(self) -> int:
        """Calculate critical path duration considering dependencies"""
        # This is a simplified critical path calculation
        max_duration = 0
        for group in self.execution_order:
            group_duration = max(
                self.subtasks[int(task_id)].estimated_duration_minutes 
                for task_id in group
            )
            max_duration += group_duration
        return max_duration


class TaskPatternMatcher:
    """Matches tasks against known patterns for decomposition"""
    
    def __init__(self):
        self.patterns = {
            "web_application": {
                "keywords": ["web app", "website", "frontend", "backend", "full stack"],
                "strategy": DecompositionStrategy.LAYER_BASED,
                "template": "web_app_layers"
            },
            "api_development": {
                "keywords": ["api", "rest", "graphql", "endpoints", "microservice"],
                "strategy": DecompositionStrategy.FEATURE_BASED,
                "template": "api_features"
            },
            "data_processing": {
                "keywords": ["data", "etl", "pipeline", "process", "transform"],
                "strategy": DecompositionStrategy.WORKFLOW,
                "template": "data_workflow"
            },
            "testing_project": {
                "keywords": ["test", "testing", "qa", "unit test", "integration"],
                "strategy": DecompositionStrategy.HIERARCHICAL,
                "template": "testing_hierarchy"
            },
            "refactoring": {
                "keywords": ["refactor", "restructure", "cleanup", "modernize"],
                "strategy": DecompositionStrategy.SEQUENTIAL,
                "template": "refactoring_steps"
            },
            "database_design": {
                "keywords": ["database", "schema", "model", "migration"],
                "strategy": DecompositionStrategy.LAYER_BASED,
                "template": "database_layers"
            }
        }
    
    def match_pattern(self, title: str, description: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Match task against known patterns"""
        text = f"{title} {description}".lower()
        
        for pattern_name, pattern_config in self.patterns.items():
            keyword_matches = sum(1 for keyword in pattern_config["keywords"] if keyword in text)
            if keyword_matches >= 2:  # Require at least 2 keyword matches
                return pattern_name, pattern_config
        
        return None
    
    def get_template_subtasks(self, template_name: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get subtask templates for a specific pattern"""
        templates = {
            "web_app_layers": [
                {
                    "title": "Set up project structure",
                    "description": "Create project directories, configuration files, and initial setup",
                    "duration": 30,
                    "skills": ["project_setup"],
                    "deliverables": ["Project structure", "Configuration files"]
                },
                {
                    "title": "Design database schema",
                    "description": "Design and implement database schema and models",
                    "duration": 60,
                    "dependencies": ["Set up project structure"],
                    "skills": ["database_design"],
                    "deliverables": ["Database schema", "Data models"]
                },
                {
                    "title": "Implement backend API",
                    "description": "Create backend API endpoints and business logic",
                    "duration": 120,
                    "dependencies": ["Design database schema"],
                    "skills": ["backend_development"],
                    "deliverables": ["API endpoints", "Business logic"]
                },
                {
                    "title": "Create frontend components",
                    "description": "Develop frontend user interface components",
                    "duration": 90,
                    "dependencies": ["Set up project structure"],
                    "skills": ["frontend_development"],
                    "deliverables": ["UI components", "User interface"]
                },
                {
                    "title": "Integrate frontend with backend",
                    "description": "Connect frontend to backend API",
                    "duration": 60,
                    "dependencies": ["Implement backend API", "Create frontend components"],
                    "skills": ["full_stack_integration"],
                    "deliverables": ["Integrated application"]
                },
                {
                    "title": "Add authentication and security",
                    "description": "Implement user authentication and security measures",
                    "duration": 75,
                    "dependencies": ["Integrate frontend with backend"],
                    "skills": ["security", "authentication"],
                    "deliverables": ["Authentication system", "Security measures"]
                },
                {
                    "title": "Testing and deployment",
                    "description": "Write tests and deploy the application",
                    "duration": 45,
                    "dependencies": ["Add authentication and security"],
                    "skills": ["testing", "deployment"],
                    "deliverables": ["Test suite", "Deployed application"]
                }
            ],
            "api_features": [
                {
                    "title": "API design and documentation",
                    "description": "Design API endpoints and create documentation",
                    "duration": 45,
                    "skills": ["api_design"],
                    "deliverables": ["API specification", "Documentation"]
                },
                {
                    "title": "Authentication endpoints",
                    "description": "Implement user authentication endpoints",
                    "duration": 60,
                    "dependencies": ["API design and documentation"],
                    "skills": ["authentication", "security"],
                    "deliverables": ["Auth endpoints", "Token management"]
                },
                {
                    "title": "Core business logic endpoints",
                    "description": "Implement main application functionality endpoints",
                    "duration": 90,
                    "dependencies": ["Authentication endpoints"],
                    "skills": ["backend_development"],
                    "deliverables": ["Business logic endpoints"]
                },
                {
                    "title": "Data validation and error handling",
                    "description": "Add input validation and comprehensive error handling",
                    "duration": 40,
                    "dependencies": ["Core business logic endpoints"],
                    "skills": ["validation", "error_handling"],
                    "deliverables": ["Validation layer", "Error handling"]
                },
                {
                    "title": "API testing",
                    "description": "Create comprehensive API test suite",
                    "duration": 50,
                    "dependencies": ["Data validation and error handling"],
                    "skills": ["api_testing"],
                    "deliverables": ["API test suite"]
                }
            ],
            "data_workflow": [
                {
                    "title": "Data source analysis",
                    "description": "Analyze and understand data sources and formats",
                    "duration": 30,
                    "skills": ["data_analysis"],
                    "deliverables": ["Data source documentation"]
                },
                {
                    "title": "Data extraction",
                    "description": "Implement data extraction from various sources",
                    "duration": 45,
                    "dependencies": ["Data source analysis"],
                    "skills": ["data_extraction"],
                    "deliverables": ["Data extraction scripts"]
                },
                {
                    "title": "Data transformation",
                    "description": "Clean, transform, and normalize the data",
                    "duration": 60,
                    "dependencies": ["Data extraction"],
                    "skills": ["data_transformation"],
                    "deliverables": ["Data transformation pipeline"]
                },
                {
                    "title": "Data validation",
                    "description": "Implement data quality checks and validation",
                    "duration": 35,
                    "dependencies": ["Data transformation"],
                    "skills": ["data_validation"],
                    "deliverables": ["Data validation rules"]
                },
                {
                    "title": "Data loading",
                    "description": "Load processed data into target system",
                    "duration": 40,
                    "dependencies": ["Data validation"],
                    "skills": ["data_loading"],
                    "deliverables": ["Data loading process"]
                }
            ],
            "testing_hierarchy": [
                {
                    "title": "Test strategy and planning",
                    "description": "Define testing strategy and create test plan",
                    "duration": 30,
                    "skills": ["test_planning"],
                    "deliverables": ["Test strategy", "Test plan"]
                },
                {
                    "title": "Unit tests",
                    "description": "Write unit tests for individual components",
                    "duration": 60,
                    "dependencies": ["Test strategy and planning"],
                    "skills": ["unit_testing"],
                    "deliverables": ["Unit test suite"]
                },
                {
                    "title": "Integration tests",
                    "description": "Create integration tests for component interactions",
                    "duration": 45,
                    "dependencies": ["Unit tests"],
                    "skills": ["integration_testing"],
                    "deliverables": ["Integration test suite"]
                },
                {
                    "title": "End-to-end tests",
                    "description": "Implement end-to-end user journey tests",
                    "duration": 50,
                    "dependencies": ["Integration tests"],
                    "skills": ["e2e_testing"],
                    "deliverables": ["E2E test suite"]
                },
                {
                    "title": "Performance tests",
                    "description": "Create performance and load tests",
                    "duration": 40,
                    "dependencies": ["End-to-end tests"],
                    "skills": ["performance_testing"],
                    "deliverables": ["Performance test suite"]
                }
            ],
            "refactoring_steps": [
                {
                    "title": "Code analysis and assessment",
                    "description": "Analyze current code structure and identify issues",
                    "duration": 45,
                    "skills": ["code_analysis"],
                    "deliverables": ["Code analysis report", "Refactoring plan"]
                },
                {
                    "title": "Write comprehensive tests",
                    "description": "Ensure adequate test coverage before refactoring",
                    "duration": 60,
                    "dependencies": ["Code analysis and assessment"],
                    "skills": ["testing"],
                    "deliverables": ["Test suite", "Coverage report"]
                },
                {
                    "title": "Extract and organize functions",
                    "description": "Break down large functions and improve organization",
                    "duration": 50,
                    "dependencies": ["Write comprehensive tests"],
                    "skills": ["refactoring"],
                    "deliverables": ["Refactored functions"]
                },
                {
                    "title": "Improve data structures",
                    "description": "Optimize data structures and their usage",
                    "duration": 40,
                    "dependencies": ["Extract and organize functions"],
                    "skills": ["data_structures", "optimization"],
                    "deliverables": ["Improved data structures"]
                },
                {
                    "title": "Update documentation",
                    "description": "Update documentation to reflect changes",
                    "duration": 25,
                    "dependencies": ["Improve data structures"],
                    "skills": ["documentation"],
                    "deliverables": ["Updated documentation"]
                }
            ],
            "database_layers": [
                {
                    "title": "Requirements analysis",
                    "description": "Analyze data requirements and business rules",
                    "duration": 30,
                    "skills": ["requirements_analysis"],
                    "deliverables": ["Requirements document"]
                },
                {
                    "title": "Conceptual model design",
                    "description": "Create high-level conceptual data model",
                    "duration": 40,
                    "dependencies": ["Requirements analysis"],
                    "skills": ["data_modeling"],
                    "deliverables": ["Conceptual model"]
                },
                {
                    "title": "Logical schema design",
                    "description": "Design detailed logical database schema",
                    "duration": 50,
                    "dependencies": ["Conceptual model design"],
                    "skills": ["database_design"],
                    "deliverables": ["Logical schema"]
                },
                {
                    "title": "Physical implementation",
                    "description": "Implement physical database structure",
                    "duration": 45,
                    "dependencies": ["Logical schema design"],
                    "skills": ["database_implementation"],
                    "deliverables": ["Physical database"]
                },
                {
                    "title": "Indexing and optimization",
                    "description": "Add indexes and optimize database performance",
                    "duration": 35,
                    "dependencies": ["Physical implementation"],
                    "skills": ["database_optimization"],
                    "deliverables": ["Optimized database"]
                }
            ]
        }
        
        return templates.get(template_name, [])


class TaskDecomposer:
    """
    Main class for automatic task decomposition
    """
    
    def __init__(self):
        self.pattern_matcher = TaskPatternMatcher()
        self.decomposition_history: List[DecompositionPlan] = []
        self._lock = threading.Lock()
        
        # Configuration
        self.max_subtasks = 15  # Maximum number of subtasks to create
        self.min_subtask_duration = 15  # Minimum duration for a subtask (minutes)
        self.max_subtask_duration = 180  # Maximum duration for a subtask (minutes)
        
        logger.info("Task decomposer initialized")
    
    def decompose_task(self, task_id: str, title: str, description: str,
                      estimated_duration: int = None,
                      complexity_hint: TaskComplexityLevel = None,
                      strategy_hint: DecompositionStrategy = None) -> DecompositionPlan:
        """
        Decompose a task into smaller subtasks
        
        Args:
            task_id: Original task identifier
            title: Task title
            description: Task description
            estimated_duration: Estimated duration in minutes (optional)
            complexity_hint: Hint about task complexity (optional)
            strategy_hint: Hint about decomposition strategy (optional)
            
        Returns:
            DecompositionPlan with subtasks and execution strategy
        """
        with self._lock:
            logger.info(f"Decomposing task {task_id}: {title}")
            
            # Determine complexity if not provided
            if complexity_hint is None:
                complexity_hint = self._assess_complexity(title, description, estimated_duration)
            
            # Check if decomposition is needed
            if complexity_hint.value <= 2 and (estimated_duration or 0) <= 60:
                logger.info(f"Task {task_id} is simple enough, no decomposition needed")
                return self._create_simple_plan(task_id, title, description, estimated_duration)
            
            # Determine strategy if not provided
            if strategy_hint is None:
                strategy_hint = self._determine_strategy(title, description)
            
            # Generate subtasks based on strategy
            subtasks = self._generate_subtasks(title, description, strategy_hint, complexity_hint)
            
            # Create decomposition plan
            plan = DecompositionPlan(
                original_task_id=task_id,
                original_title=title,
                original_description=description,
                strategy=strategy_hint,
                subtasks=subtasks,
                confidence_score=self._calculate_confidence_score(subtasks, strategy_hint),
                metadata={
                    "complexity_assessed": complexity_hint.value,
                    "original_estimated_duration": estimated_duration
                }
            )
            
            self.decomposition_history.append(plan)
            
            logger.info(f"Decomposed task {task_id} into {len(subtasks)} subtasks "
                       f"using {strategy_hint.value} strategy "
                       f"(confidence: {plan.confidence_score:.2f})")
            
            return plan
    
    def _assess_complexity(self, title: str, description: str, 
                          estimated_duration: int = None) -> TaskComplexityLevel:
        """Assess task complexity based on various factors"""
        complexity_score = 0
        
        # Duration factor
        if estimated_duration:
            if estimated_duration > 240:  # > 4 hours
                complexity_score += 3
            elif estimated_duration > 120:  # > 2 hours
                complexity_score += 2
            elif estimated_duration > 60:  # > 1 hour
                complexity_score += 1
        
        # Text analysis factors
        text = f"{title} {description}".lower()
        
        # Complexity keywords
        complex_keywords = [
            "architecture", "system", "framework", "complex", "comprehensive",
            "enterprise", "scalable", "distributed", "microservice", "multiple",
            "integration", "migration", "refactor", "redesign"
        ]
        complexity_score += sum(1 for keyword in complex_keywords if keyword in text)
        
        # Technical depth indicators
        tech_indicators = [
            "algorithm", "optimization", "performance", "security", "database",
            "api", "backend", "frontend", "devops", "testing"
        ]
        complexity_score += len(set(tech_indicators) & set(text.split())) * 0.5
        
        # Word count factor
        word_count = len(description.split())
        if word_count > 100:
            complexity_score += 2
        elif word_count > 50:
            complexity_score += 1
        
        # Multiple components indicator
        if any(word in text for word in ["and", "also", "additionally", "plus"]):
            complexity_score += 1
        
        # Convert score to complexity level
        if complexity_score >= 7:
            return TaskComplexityLevel.VERY_COMPLEX
        elif complexity_score >= 5:
            return TaskComplexityLevel.COMPLEX
        elif complexity_score >= 3:
            return TaskComplexityLevel.MODERATE
        elif complexity_score >= 1:
            return TaskComplexityLevel.SIMPLE
        else:
            return TaskComplexityLevel.TRIVIAL
    
    def _determine_strategy(self, title: str, description: str) -> DecompositionStrategy:
        """Determine the best decomposition strategy"""
        # Try pattern matching first
        pattern_match = self.pattern_matcher.match_pattern(title, description)
        if pattern_match:
            _, pattern_config = pattern_match
            return pattern_config["strategy"]
        
        # Fallback to heuristic analysis
        text = f"{title} {description}".lower()
        
        # Sequential indicators
        sequential_words = ["step", "phase", "first", "then", "after", "before", "sequence"]
        if any(word in text for word in sequential_words):
            return DecompositionStrategy.SEQUENTIAL
        
        # Parallel indicators
        parallel_words = ["parallel", "concurrent", "simultaneously", "independent"]
        if any(word in text for word in parallel_words):
            return DecompositionStrategy.PARALLEL
        
        # Feature-based indicators
        feature_words = ["feature", "functionality", "component", "module", "service"]
        if any(word in text for word in feature_words):
            return DecompositionStrategy.FEATURE_BASED
        
        # Layer-based indicators
        layer_words = ["layer", "tier", "frontend", "backend", "database", "ui"]
        if any(word in text for word in layer_words):
            return DecompositionStrategy.LAYER_BASED
        
        # Workflow indicators
        workflow_words = ["process", "pipeline", "workflow", "etl", "transform"]
        if any(word in text for word in workflow_words):
            return DecompositionStrategy.WORKFLOW
        
        # Default to hierarchical
        return DecompositionStrategy.HIERARCHICAL
    
    def _generate_subtasks(self, title: str, description: str,
                          strategy: DecompositionStrategy,
                          complexity: TaskComplexityLevel) -> List[SubtaskBlueprint]:
        """Generate subtasks based on strategy and complexity"""
        # Try template-based generation first
        pattern_match = self.pattern_matcher.match_pattern(title, description)
        if pattern_match:
            pattern_name, pattern_config = pattern_match
            template_name = pattern_config["template"]
            template_subtasks = self.pattern_matcher.get_template_subtasks(template_name)
            
            if template_subtasks:
                return self._create_subtasks_from_template(template_subtasks, title, description)
        
        # Fallback to heuristic generation
        return self._generate_heuristic_subtasks(title, description, strategy, complexity)
    
    def _create_subtasks_from_template(self, template_subtasks: List[Dict[str, Any]],
                                     title: str, description: str) -> List[SubtaskBlueprint]:
        """Create subtasks from template"""
        subtasks = []
        
        for i, template in enumerate(template_subtasks):
            subtask = SubtaskBlueprint(
                title=template["title"],
                description=template["description"],
                estimated_duration_minutes=template.get("duration", 30),
                dependencies=template.get("dependencies", []),
                priority=template.get("priority", 5),
                complexity=TaskComplexityLevel(template.get("complexity", 2)),
                required_skills=set(template.get("skills", [])),
                deliverables=template.get("deliverables", []),
                acceptance_criteria=template.get("acceptance_criteria", []),
                metadata={"template_based": True, "template_index": i}
            )
            subtasks.append(subtask)
        
        return subtasks
    
    def _generate_heuristic_subtasks(self, title: str, description: str,
                                   strategy: DecompositionStrategy,
                                   complexity: TaskComplexityLevel) -> List[SubtaskBlueprint]:
        """Generate subtasks using heuristic rules"""
        subtasks = []
        
        # Base subtasks that most tasks need
        base_subtasks = [
            {
                "title": "Analysis and planning",
                "description": f"Analyze requirements and create implementation plan for: {title}",
                "duration": 30,
                "skills": ["analysis", "planning"]
            }
        ]
        
        # Add strategy-specific subtasks
        if strategy == DecompositionStrategy.SEQUENTIAL:
            subtasks.extend(self._generate_sequential_subtasks(title, description))
        elif strategy == DecompositionStrategy.PARALLEL:
            subtasks.extend(self._generate_parallel_subtasks(title, description))
        elif strategy == DecompositionStrategy.FEATURE_BASED:
            subtasks.extend(self._generate_feature_subtasks(title, description))
        elif strategy == DecompositionStrategy.LAYER_BASED:
            subtasks.extend(self._generate_layer_subtasks(title, description))
        elif strategy == DecompositionStrategy.WORKFLOW:
            subtasks.extend(self._generate_workflow_subtasks(title, description))
        else:  # HIERARCHICAL
            subtasks.extend(self._generate_hierarchical_subtasks(title, description))
        
        # Add completion subtasks
        completion_subtasks = [
            {
                "title": "Testing and validation",
                "description": f"Test and validate the implementation of: {title}",
                "duration": 45,
                "skills": ["testing", "validation"],
                "dependencies": ["Implementation"]
            },
            {
                "title": "Documentation and cleanup",
                "description": f"Document the solution and perform cleanup for: {title}",
                "duration": 20,
                "skills": ["documentation"],
                "dependencies": ["Testing and validation"]
            }
        ]
        
        # Combine all subtasks
        all_subtask_templates = base_subtasks + subtasks + completion_subtasks
        
        # Convert to SubtaskBlueprint objects
        blueprint_subtasks = []
        for template in all_subtask_templates:
            blueprint = SubtaskBlueprint(
                title=template["title"],
                description=template["description"],
                estimated_duration_minutes=template.get("duration", 30),
                dependencies=template.get("dependencies", []),
                required_skills=set(template.get("skills", [])),
                complexity=TaskComplexityLevel.SIMPLE
            )
            blueprint_subtasks.append(blueprint)
        
        return blueprint_subtasks[:self.max_subtasks]  # Limit number of subtasks
    
    def _generate_sequential_subtasks(self, title: str, description: str) -> List[Dict[str, Any]]:
        """Generate subtasks for sequential decomposition"""
        return [
            {
                "title": "Phase 1: Foundation",
                "description": f"Establish foundation and basic structure for: {title}",
                "duration": 60,
                "skills": ["foundation", "setup"]
            },
            {
                "title": "Phase 2: Core implementation",
                "description": f"Implement core functionality for: {title}",
                "duration": 90,
                "skills": ["implementation"],
                "dependencies": ["Phase 1: Foundation"]
            },
            {
                "title": "Phase 3: Enhancement",
                "description": f"Add enhancements and polish for: {title}",
                "duration": 45,
                "skills": ["enhancement"],
                "dependencies": ["Phase 2: Core implementation"]
            }
        ]
    
    def _generate_parallel_subtasks(self, title: str, description: str) -> List[Dict[str, Any]]:
        """Generate subtasks for parallel decomposition"""
        return [
            {
                "title": "Component A implementation",
                "description": f"Implement component A for: {title}",
                "duration": 60,
                "skills": ["implementation"]
            },
            {
                "title": "Component B implementation",
                "description": f"Implement component B for: {title}",
                "duration": 60,
                "skills": ["implementation"]
            },
            {
                "title": "Integration",
                "description": f"Integrate all components for: {title}",
                "duration": 30,
                "skills": ["integration"],
                "dependencies": ["Component A implementation", "Component B implementation"]
            }
        ]
    
    def _generate_feature_subtasks(self, title: str, description: str) -> List[Dict[str, Any]]:
        """Generate subtasks for feature-based decomposition"""
        return [
            {
                "title": "Core feature implementation",
                "description": f"Implement main feature for: {title}",
                "duration": 75,
                "skills": ["feature_development"]
            },
            {
                "title": "Supporting features",
                "description": f"Implement supporting features for: {title}",
                "duration": 60,
                "skills": ["feature_development"],
                "dependencies": ["Core feature implementation"]
            },
            {
                "title": "Feature integration",
                "description": f"Integrate all features for: {title}",
                "duration": 30,
                "skills": ["integration"],
                "dependencies": ["Supporting features"]
            }
        ]
    
    def _generate_layer_subtasks(self, title: str, description: str) -> List[Dict[str, Any]]:
        """Generate subtasks for layer-based decomposition"""
        return [
            {
                "title": "Data layer",
                "description": f"Implement data layer for: {title}",
                "duration": 60,
                "skills": ["data_layer", "database"]
            },
            {
                "title": "Business logic layer",
                "description": f"Implement business logic for: {title}",
                "duration": 75,
                "skills": ["business_logic"],
                "dependencies": ["Data layer"]
            },
            {
                "title": "Presentation layer",
                "description": f"Implement presentation layer for: {title}",
                "duration": 60,
                "skills": ["presentation", "ui"],
                "dependencies": ["Business logic layer"]
            }
        ]
    
    def _generate_workflow_subtasks(self, title: str, description: str) -> List[Dict[str, Any]]:
        """Generate subtasks for workflow-based decomposition"""
        return [
            {
                "title": "Input processing",
                "description": f"Implement input processing for: {title}",
                "duration": 45,
                "skills": ["input_processing"]
            },
            {
                "title": "Core processing",
                "description": f"Implement core processing logic for: {title}",
                "duration": 75,
                "skills": ["processing"],
                "dependencies": ["Input processing"]
            },
            {
                "title": "Output generation",
                "description": f"Implement output generation for: {title}",
                "duration": 45,
                "skills": ["output_generation"],
                "dependencies": ["Core processing"]
            }
        ]
    
    def _generate_hierarchical_subtasks(self, title: str, description: str) -> List[Dict[str, Any]]:
        """Generate subtasks for hierarchical decomposition"""
        return [
            {
                "title": "High-level design",
                "description": f"Create high-level design for: {title}",
                "duration": 45,
                "skills": ["design", "architecture"]
            },
            {
                "title": "Detailed implementation",
                "description": f"Implement detailed components for: {title}",
                "duration": 90,
                "skills": ["implementation"],
                "dependencies": ["High-level design"]
            },
            {
                "title": "Integration and refinement",
                "description": f"Integrate components and refine for: {title}",
                "duration": 45,
                "skills": ["integration", "refinement"],
                "dependencies": ["Detailed implementation"]
            }
        ]
    
    def _create_simple_plan(self, task_id: str, title: str, description: str,
                          estimated_duration: int = None) -> DecompositionPlan:
        """Create a simple plan with no decomposition"""
        single_subtask = SubtaskBlueprint(
            title=title,
            description=description,
            estimated_duration_minutes=estimated_duration or 30,
            complexity=TaskComplexityLevel.SIMPLE
        )
        
        return DecompositionPlan(
            original_task_id=task_id,
            original_title=title,
            original_description=description,
            strategy=DecompositionStrategy.SEQUENTIAL,
            subtasks=[single_subtask],
            confidence_score=1.0,
            metadata={"decomposition_skipped": True, "reason": "Task too simple"}
        )
    
    def _calculate_confidence_score(self, subtasks: List[SubtaskBlueprint],
                                  strategy: DecompositionStrategy) -> float:
        """Calculate confidence score for decomposition quality"""
        score = 0.8  # Base confidence
        
        # Adjust based on number of subtasks
        num_subtasks = len(subtasks)
        if 3 <= num_subtasks <= 8:
            score += 0.1  # Optimal range
        elif num_subtasks > 10:
            score -= 0.2  # Too many subtasks
        elif num_subtasks < 2:
            score -= 0.3  # Too few subtasks
        
        # Adjust based on dependency structure
        total_dependencies = sum(len(st.dependencies) for st in subtasks)
        if total_dependencies > 0:
            score += 0.1  # Good dependency structure
        
        # Adjust based on duration distribution
        durations = [st.estimated_duration_minutes for st in subtasks]
        if durations:
            avg_duration = sum(durations) / len(durations)
            if 20 <= avg_duration <= 90:  # Reasonable duration range
                score += 0.1
        
        return min(1.0, max(0.0, score))
    
    def get_decomposition_statistics(self) -> Dict[str, Any]:
        """Get statistics about decomposition patterns"""
        with self._lock:
            if not self.decomposition_history:
                return {"message": "No decomposition history available"}
            
            total_decompositions = len(self.decomposition_history)
            
            # Strategy distribution
            strategy_counts = defaultdict(int)
            for plan in self.decomposition_history:
                strategy_counts[plan.strategy.value] += 1
            
            # Average metrics
            avg_subtasks = sum(len(plan.subtasks) for plan in self.decomposition_history) / total_decompositions
            avg_confidence = sum(plan.confidence_score for plan in self.decomposition_history) / total_decompositions
            avg_duration = sum(plan.total_estimated_duration for plan in self.decomposition_history) / total_decompositions
            
            return {
                "total_decompositions": total_decompositions,
                "strategy_distribution": dict(strategy_counts),
                "average_subtasks_per_task": avg_subtasks,
                "average_confidence_score": avg_confidence,
                "average_estimated_duration_minutes": avg_duration,
                "most_common_strategy": max(strategy_counts.items(), key=lambda x: x[1])[0] if strategy_counts else None
            }


# Global task decomposer instance
task_decomposer = TaskDecomposer()