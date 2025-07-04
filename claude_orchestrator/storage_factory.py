"""Storage factory for creating feedback storage backends based on configuration."""

import logging
from typing import Dict, Any, Optional

from .feedback_storage import FeedbackStorage, JSONFeedbackStorage, FeedbackStorageInterface
from .database_storage import (
    DatabaseFeedbackStorage, SQLiteFeedbackStorage, PostgreSQLFeedbackStorage
)


logger = logging.getLogger(__name__)


class StorageFactory:
    """Factory for creating storage backends based on configuration."""
    
    # Registry of available storage backends
    _backends = {
        'json': JSONFeedbackStorage,
        'sqlite': SQLiteFeedbackStorage,
        'postgresql': PostgreSQLFeedbackStorage,
        'database': DatabaseFeedbackStorage,  # Generic database backend
        # Future backends can be added here:
        # 'mongodb': MongoDBFeedbackStorage,
        # 'redis': RedisFeedbackStorage,
    }
    
    @classmethod
    def register_backend(cls, name: str, backend_class: type):
        """Register a new storage backend.
        
        Args:
            name: Name identifier for the backend
            backend_class: Class implementing FeedbackStorageInterface
        """
        if not issubclass(backend_class, FeedbackStorageInterface):
            raise ValueError(f"{backend_class} must implement FeedbackStorageInterface")
        
        cls._backends[name] = backend_class
        logger.info(f"Registered storage backend: {name}")
    
    @classmethod
    def create_storage(cls, config: Dict[str, Any]) -> FeedbackStorage:
        """Create a feedback storage instance based on configuration.
        
        Args:
            config: Storage configuration dictionary
            
        Returns:
            Configured FeedbackStorage instance
        """
        # Get backend type from config
        backend_type = config.get('storage_backend', 'json').lower()
        
        if backend_type not in cls._backends:
            logger.warning(f"Unknown storage backend '{backend_type}', falling back to 'json'")
            backend_type = 'json'
        
        # Create backend instance
        backend_class = cls._backends[backend_type]
        
        # Extract backend-specific configuration
        backend_config = cls._get_backend_config(backend_type, config)
        
        try:
            backend = backend_class(**backend_config)
            logger.info(f"Created {backend_type} storage backend")
        except Exception as e:
            logger.error(f"Failed to create {backend_type} backend: {e}")
            # Fallback to JSON backend
            backend = JSONFeedbackStorage()
            logger.info("Fallback to JSON storage backend")
        
        # Create main storage with caching
        cache_size = config.get('cache_size', 1000)
        storage = FeedbackStorage(backend=backend)
        storage._cache_size = cache_size
        
        return storage
    
    @classmethod
    def _get_backend_config(cls, backend_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract backend-specific configuration.
        
        Args:
            backend_type: Type of backend
            config: Full configuration dictionary
            
        Returns:
            Backend-specific configuration
        """
        if backend_type == 'json':
            return {
                'storage_path': config.get('storage_path', '.feedback')
            }
        
        elif backend_type == 'sqlite':
            return {
                'db_path': config.get('db_path', '.feedback/feedback.db')
            }
        
        elif backend_type == 'postgresql':
            return {
                'host': config.get('db_host', 'localhost'),
                'port': config.get('db_port', 5432),
                'database': config.get('db_name', 'feedback'),
                'user': config.get('db_user', 'postgres'),
                'password': config.get('db_password', '')
            }
        
        elif backend_type == 'database':
            return {
                'connection_string': config.get('connection_string', 'sqlite:///.feedback/feedback.db'),
                'table_prefix': config.get('table_prefix', 'feedback')
            }
        
        return {}
    
    @classmethod
    def create_from_env(cls) -> FeedbackStorage:
        """Create storage instance from environment variables.
        
        Returns:
            Configured FeedbackStorage instance
        """
        import os
        
        config = {
            'storage_backend': os.environ.get('FEEDBACK_STORAGE_BACKEND', 'json'),
            'storage_path': os.environ.get('FEEDBACK_STORAGE_PATH', '.feedback'),
            'cache_size': int(os.environ.get('FEEDBACK_CACHE_SIZE', '1000'))
        }
        
        return cls.create_storage(config)


def create_feedback_storage(config: Optional[Dict[str, Any]] = None) -> FeedbackStorage:
    """Convenience function to create feedback storage.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured FeedbackStorage instance
    """
    if config is None:
        # Try to load from environment
        return StorageFactory.create_from_env()
    
    return StorageFactory.create_storage(config)