"""
Feature Flag System - Simple and Lightweight
Following Simplicity First principle with minimal complexity
"""

import json
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class FlagType(Enum):
    """Types of feature flags"""
    BOOLEAN = "boolean"
    STRING = "string"
    NUMBER = "number"
    JSON = "json"


@dataclass
class FeatureFlag:
    """Simple feature flag definition"""
    name: str
    enabled: bool
    value: Any = None
    description: str = ""
    flag_type: FlagType = FlagType.BOOLEAN
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "value": self.value,
            "description": self.description,
            "flag_type": self.flag_type.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureFlag':
        """Create from dictionary"""
        return cls(
            name=data["name"],
            enabled=data["enabled"],
            value=data.get("value"),
            description=data.get("description", ""),
            flag_type=FlagType(data.get("flag_type", "boolean"))
        )


class FeatureFlagStorage:
    """Simple file-based storage for feature flags"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize storage with optional config path"""
        self.config_path = Path(config_path or "feature_flags.json")
        self._flags: Dict[str, FeatureFlag] = {}
        self._load_flags()
    
    def _load_flags(self):
        """Load flags from storage"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    for flag_data in data.get("flags", []):
                        flag = FeatureFlag.from_dict(flag_data)
                        self._flags[flag.name] = flag
                logger.info(f"Loaded {len(self._flags)} feature flags")
            else:
                logger.info("No feature flags file found, starting with empty flags")
        except Exception as e:
            logger.error(f"Error loading feature flags: {e}")
            self._flags = {}
    
    def _save_flags(self):
        """Save flags to storage"""
        try:
            data = {
                "flags": [flag.to_dict() for flag in self._flags.values()]
            }
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self._flags)} feature flags")
        except Exception as e:
            logger.error(f"Error saving feature flags: {e}")
    
    def get_flag(self, name: str) -> Optional[FeatureFlag]:
        """Get a specific flag"""
        return self._flags.get(name)
    
    def set_flag(self, flag: FeatureFlag):
        """Set a flag and save to storage"""
        self._flags[flag.name] = flag
        self._save_flags()
    
    def delete_flag(self, name: str) -> bool:
        """Delete a flag"""
        if name in self._flags:
            del self._flags[name]
            self._save_flags()
            return True
        return False
    
    def list_flags(self) -> Dict[str, FeatureFlag]:
        """List all flags"""
        return self._flags.copy()


class FeatureFlagEvaluator:
    """Simple flag evaluation logic"""
    
    def __init__(self, storage: FeatureFlagStorage):
        self.storage = storage
    
    def is_enabled(self, flag_name: str, default: bool = False) -> bool:
        """Check if a flag is enabled"""
        flag = self.storage.get_flag(flag_name)
        if flag is None:
            logger.debug(f"Flag '{flag_name}' not found, returning default: {default}")
            return default
        return flag.enabled
    
    def get_value(self, flag_name: str, default: Any = None) -> Any:
        """Get flag value"""
        flag = self.storage.get_flag(flag_name)
        if flag is None:
            logger.debug(f"Flag '{flag_name}' not found, returning default: {default}")
            return default
        
        if not flag.enabled:
            logger.debug(f"Flag '{flag_name}' is disabled, returning default: {default}")
            return default
        
        return flag.value if flag.value is not None else flag.enabled
    
    def get_string(self, flag_name: str, default: str = "") -> str:
        """Get string flag value"""
        value = self.get_value(flag_name, default)
        return str(value) if value is not None else default
    
    def get_number(self, flag_name: str, default: Union[int, float] = 0) -> Union[int, float]:
        """Get numeric flag value"""
        value = self.get_value(flag_name, default)
        if isinstance(value, (int, float)):
            return value
        try:
            return float(value) if '.' in str(value) else int(value)
        except (ValueError, TypeError):
            return default
    
    def get_json(self, flag_name: str, default: Any = None) -> Any:
        """Get JSON flag value"""
        value = self.get_value(flag_name, default)
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default
        return default


class FeatureFlagManager:
    """Main feature flag manager - Simple facade"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the feature flag manager"""
        self.storage = FeatureFlagStorage(config_path)
        self.evaluator = FeatureFlagEvaluator(self.storage)
    
    def is_enabled(self, flag_name: str, default: bool = False) -> bool:
        """Check if a feature flag is enabled"""
        return self.evaluator.is_enabled(flag_name, default)
    
    def get_value(self, flag_name: str, default: Any = None) -> Any:
        """Get feature flag value"""
        return self.evaluator.get_value(flag_name, default)
    
    def get_string(self, flag_name: str, default: str = "") -> str:
        """Get string flag value"""
        return self.evaluator.get_string(flag_name, default)
    
    def get_number(self, flag_name: str, default: Union[int, float] = 0) -> Union[int, float]:
        """Get numeric flag value"""
        return self.evaluator.get_number(flag_name, default)
    
    def get_json(self, flag_name: str, default: Any = None) -> Any:
        """Get JSON flag value"""
        return self.evaluator.get_json(flag_name, default)
    
    def create_flag(self, name: str, enabled: bool = False, value: Any = None, 
                   description: str = "", flag_type: FlagType = FlagType.BOOLEAN):
        """Create a new feature flag"""
        flag = FeatureFlag(
            name=name,
            enabled=enabled,
            value=value,
            description=description,
            flag_type=flag_type
        )
        self.storage.set_flag(flag)
        logger.info(f"Created flag '{name}' (enabled: {enabled})")
    
    def update_flag(self, name: str, enabled: Optional[bool] = None, 
                   value: Optional[Any] = None, description: Optional[str] = None):
        """Update an existing feature flag"""
        flag = self.storage.get_flag(name)
        if flag is None:
            logger.warning(f"Flag '{name}' not found for update")
            return False
        
        if enabled is not None:
            flag.enabled = enabled
        if value is not None:
            flag.value = value
        if description is not None:
            flag.description = description
        
        self.storage.set_flag(flag)
        logger.info(f"Updated flag '{name}'")
        return True
    
    def delete_flag(self, name: str) -> bool:
        """Delete a feature flag"""
        result = self.storage.delete_flag(name)
        if result:
            logger.info(f"Deleted flag '{name}'")
        else:
            logger.warning(f"Flag '{name}' not found for deletion")
        return result
    
    def list_flags(self) -> Dict[str, Dict[str, Any]]:
        """List all feature flags"""
        flags = self.storage.list_flags()
        return {name: flag.to_dict() for name, flag in flags.items()}
    
    def reload(self):
        """Reload flags from storage"""
        self.storage._load_flags()
        logger.info("Reloaded feature flags from storage")


# Global instance for easy access
_global_flag_manager: Optional[FeatureFlagManager] = None


def get_flag_manager(config_path: Optional[str] = None) -> FeatureFlagManager:
    """Get or create the global feature flag manager"""
    global _global_flag_manager
    if _global_flag_manager is None:
        _global_flag_manager = FeatureFlagManager(config_path)
    return _global_flag_manager


def is_enabled(flag_name: str, default: bool = False) -> bool:
    """Convenience function to check if a flag is enabled"""
    return get_flag_manager().is_enabled(flag_name, default)


def get_value(flag_name: str, default: Any = None) -> Any:
    """Convenience function to get flag value"""
    return get_flag_manager().get_value(flag_name, default)


def get_string(flag_name: str, default: str = "") -> str:
    """Convenience function to get string flag value"""
    return get_flag_manager().get_string(flag_name, default)


def get_number(flag_name: str, default: Union[int, float] = 0) -> Union[int, float]:
    """Convenience function to get numeric flag value"""
    return get_flag_manager().get_number(flag_name, default)


def get_json(flag_name: str, default: Any = None) -> Any:
    """Convenience function to get JSON flag value"""
    return get_flag_manager().get_json(flag_name, default)