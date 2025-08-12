"""
Model configuration utilities for the subtitle translation service.
Centralizes model selection and configuration.
"""

import os
from typing import Optional
from .config_manager import ConfigManager


class ModelConfig:
    """Centralized model configuration management."""
    
    # Default model configuration
    DEFAULT_MODEL = "gpt-4o-mini"
    
    # Available models with their characteristics
    AVAILABLE_MODELS = {
        "gpt-4o-mini": {
            "name": "GPT-4o Mini",
            "cost_per_1k_tokens": 0.00075,
            "quality": "excellent",
            "speed": "fast",
            "description": "Best balance of quality and cost"
        },
    }
    
    @classmethod
    def get_model(cls, config_manager: Optional[ConfigManager] = None) -> str:
        """
        Get the configured model name.
        
        Args:
            config_manager: Configuration manager instance
            
        Returns:
            Model name string
        """
        # Priority order: config manager > environment variable > default
        if config_manager:
            model = config_manager.get('api.openai.model', cls.DEFAULT_MODEL)
            if model and model in cls.AVAILABLE_MODELS:
                return model
        
        # Fallback to environment variable
        env_model = os.getenv('OPENAI_MODEL')
        if env_model and env_model in cls.AVAILABLE_MODELS:
            return env_model
        
        # Final fallback to default
        return cls.DEFAULT_MODEL
    
    @classmethod
    def get_model_info(cls, model_name: str) -> dict:
        """
        Get information about a specific model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Dictionary with model information
        """
        return cls.AVAILABLE_MODELS.get(model_name, {
            "name": model_name,
            "cost_per_1k_tokens": 0.0,
            "quality": "unknown",
            "speed": "unknown",
            "description": "Unknown model"
        })
    
    @classmethod
    def list_available_models(cls) -> dict:
        """
        Get list of all available models.
        
        Returns:
            Dictionary of available models
        """
        return cls.AVAILABLE_MODELS.copy()
    
    @classmethod
    def validate_model(cls, model_name: str) -> bool:
        """
        Validate if a model name is supported.
        
        Args:
            model_name: Name of the model to validate
            
        Returns:
            True if model is supported, False otherwise
        """
        return model_name in cls.AVAILABLE_MODELS
    
    @classmethod
    def get_cost_estimate(cls, model_name: str, token_count: int) -> float:
        """
        Get cost estimate for a given number of tokens.
        
        Args:
            model_name: Name of the model
            token_count: Number of tokens
            
        Returns:
            Estimated cost in USD
        """
        model_info = cls.get_model_info(model_name)
        cost_per_1k = model_info.get('cost_per_1k_tokens', 0.0)
        return (token_count / 1000) * cost_per_1k
