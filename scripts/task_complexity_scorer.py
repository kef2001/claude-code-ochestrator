from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass


class ComplexityLevel(Enum):
    TRIVIAL = 1
    SIMPLE = 2
    MODERATE = 3
    COMPLEX = 4
    VERY_COMPLEX = 5


@dataclass
class TaskMetrics:
    input_size: int = 0  # MB or record count
    compute_intensity: int = 1  # 1-10 scale
    output_size: int = 0  # MB or record count
    time_sensitivity: int = 1  # 1-10 scale (10 = urgent)
    resource_dependencies: int = 0  # Number of external dependencies


class TaskComplexityScorer:
    def __init__(self):
        self.weights = {
            'input_size': 0.25,
            'compute_intensity': 0.30,
            'output_size': 0.20,
            'time_sensitivity': 0.15,
            'resource_dependencies': 0.10
        }
    
    def calculate_complexity_score(self, metrics: TaskMetrics) -> float:
        """Calculate weighted complexity score (0-100)"""
        # Normalize input size (log scale for large values)
        input_score = min(10, (metrics.input_size / 100) ** 0.5 * 10)
        
        # Compute intensity is already 1-10
        compute_score = metrics.compute_intensity
        
        # Normalize output size
        output_score = min(10, (metrics.output_size / 100) ** 0.5 * 10)
        
        # Time sensitivity is already 1-10
        time_score = metrics.time_sensitivity
        
        # Resource dependencies score
        resource_score = min(10, metrics.resource_dependencies * 2)
        
        # Calculate weighted score
        weighted_score = (
            input_score * self.weights['input_size'] +
            compute_score * self.weights['compute_intensity'] +
            output_score * self.weights['output_size'] +
            time_score * self.weights['time_sensitivity'] +
            resource_score * self.weights['resource_dependencies']
        )
        
        return weighted_score * 10  # Scale to 0-100
    
    def get_complexity_level(self, score: float) -> ComplexityLevel:
        """Map score to complexity level"""
        if score < 20:
            return ComplexityLevel.TRIVIAL
        elif score < 40:
            return ComplexityLevel.SIMPLE
        elif score < 60:
            return ComplexityLevel.MODERATE
        elif score < 80:
            return ComplexityLevel.COMPLEX
        else:
            return ComplexityLevel.VERY_COMPLEX
    
    def score_task(self, metrics: TaskMetrics) -> Dict[str, any]:
        """Complete scoring with detailed breakdown"""
        score = self.calculate_complexity_score(metrics)
        level = self.get_complexity_level(score)
        
        return {
            'score': round(score, 2),
            'level': level,
            'metrics': metrics,
            'breakdown': {
                'input_contribution': round(min(10, (metrics.input_size / 100) ** 0.5 * 10) * self.weights['input_size'] * 10, 2),
                'compute_contribution': round(metrics.compute_intensity * self.weights['compute_intensity'] * 10, 2),
                'output_contribution': round(min(10, (metrics.output_size / 100) ** 0.5 * 10) * self.weights['output_size'] * 10, 2),
                'time_contribution': round(metrics.time_sensitivity * self.weights['time_sensitivity'] * 10, 2),
                'resource_contribution': round(min(10, metrics.resource_dependencies * 2) * self.weights['resource_dependencies'] * 10, 2)
            }
        }
    
    def update_weights(self, new_weights: Dict[str, float]):
        """Update scoring weights"""
        if abs(sum(new_weights.values()) - 1.0) > 0.01:
            raise ValueError("Weights must sum to 1.0")
        self.weights.update(new_weights)