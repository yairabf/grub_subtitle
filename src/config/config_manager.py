"""
Configuration manager for Hebrew Subtitle Service.
Handles loading, validation, and management of configuration settings.
"""

import os
import yaml
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet
import json
import logging

class ConfigurationError(Exception):
    """Raised when there's an error with configuration."""
    pass

class ConfigManager:
    """Manages configuration loading, validation, and secure storage."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to configuration file. If None, uses default location.
        """
        self.config_path = config_path or self._get_default_config_path()
        self.config: Dict[str, Any] = {}
        self.encryption_key: Optional[bytes] = None
        self._load_encryption_key()
        self.load_config()
    
    def _get_default_config_path(self) -> str:
        """Get the default configuration file path."""
        # Look for config in current directory, then in config subdirectory
        possible_paths = [
            "config.yaml",
            "config/config.yaml",
            "src/config/config.yaml"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # If no config exists, create one in the current directory
        return "config.yaml"
    
    def _load_encryption_key(self):
        """Load or create encryption key for secure storage."""
        key_file = Path("secure/encryption.key")
        key_file.parent.mkdir(exist_ok=True)
        
        if key_file.exists():
            with open(key_file, "rb") as f:
                key_data = f.read()
                if key_data:
                    self.encryption_key = key_data
                else:
                    new_key = Fernet.generate_key()
                    self.encryption_key = new_key
                    with open(key_file, "wb") as f:
                        f.write(new_key)
        else:
            new_key = Fernet.generate_key()
            self.encryption_key = new_key
            with open(key_file, "wb") as f:
                f.write(new_key)
    
    def _substitute_environment_variables(self, value: str) -> str:
        """Substitute environment variables in configuration values."""
        if not isinstance(value, str):
            return value
        
        # Pattern to match ${VARIABLE_NAME}
        pattern = r'\$\{([^}]+)\}'
        
        def replace_var(match):
            var_name = match.group(1)
            env_value = os.getenv(var_name)
            if env_value is None:
                raise ConfigurationError(f"Environment variable {var_name} not found")
            return env_value
        
        return re.sub(pattern, replace_var, value)
    
    def _recursive_substitute(self, data: Any) -> Any:
        """Recursively substitute environment variables in configuration data."""
        if isinstance(data, dict):
            return {key: self._recursive_substitute(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._recursive_substitute(item) for item in data]
        elif isinstance(data, str):
            return self._substitute_environment_variables(data)
        else:
            return data
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file with environment variable substitution.
        
        Returns:
            Loaded configuration dictionary.
        
        Raises:
            ConfigurationError: If configuration file cannot be loaded or validated.
        """
        try:
            if not os.path.exists(self.config_path):
                # Create default configuration
                self._create_default_config()
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if config_data is None:
                raise ConfigurationError("Configuration file is empty or invalid")
            
            # Substitute environment variables
            self.config = self._recursive_substitute(config_data)
            
            # Validate configuration
            self._validate_config()
            
            logging.info(f"Configuration loaded successfully from {self.config_path}")
            return self.config
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading configuration: {e}")
    
    def _create_default_config(self):
        """Create a default configuration file."""
        default_config = {
            'api': {
                'opensubtitles': {
                    'username': '${OPENSUBTITLES_USERNAME}',
                    'password': '${OPENSUBTITLES_PASSWORD}',
                    'base_url': 'https://api.opensubtitles.com/xml-rpc',
                    'user_agent': 'HebrewSubtitleService/1.0',
                    'timeout': 30,
                    'max_retries': 3
                },
                'openai': {
                    'api_key': '${OPENAI_API_KEY}',
                    'model': 'gpt-4o-mini',  # Model defined in config only
                    'temperature': 0.3,
                    'max_tokens': 4000,
                    'timeout': 60,
                    'max_retries': 3
                }
            },
            'processing': {
                'chunk_size': 3000,
                'max_blocks_per_chunk': 10,
                'supported_video_formats': ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'],
                'max_concurrent_processes': 3,
                'temp_directory': './temp'
            },
            'validation': {
                'min_hebrew_ratio': 0.5,
                'max_timestamp_error': 0.1,
                'auto_fix': True,
                'strict_mode': False
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/subtitle_service.log',
                'max_size': '10MB',
                'backup_count': 5,
                'format': 'json',
                'console_output': True
            },
            'security': {
                'encrypt_api_keys': True,
                'key_rotation_days': 90,
                'secure_storage_path': './secure',
                'audit_logging': True
            },
            'ui': {
                'theme': 'default',
                'language': 'en',
                'auto_save_config': True,
                'show_advanced_options': False
            },
            'paths': {
                'default_output_dir': './subtitles',
                'log_directory': './logs',
                'config_directory': './config',
                'cache_directory': './cache'
            }
        }
        
        # Ensure config directory exists
        config_dir = os.path.dirname(self.config_path)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)
        
        logging.info(f"Default configuration created at {self.config_path}")
    
    def _validate_config(self):
        """Validate the loaded configuration."""
        required_sections = ['api', 'processing', 'validation', 'logging', 'security', 'ui', 'paths']
        
        for section in required_sections:
            if section not in self.config:
                raise ConfigurationError(f"Missing required configuration section: {section}")
        
        # Validate API configuration
        api_config = self.config.get('api', {})
        if 'opensubtitles' not in api_config:
            raise ConfigurationError("Missing OpenSubtitles API configuration")
        if 'openai' not in api_config:
            raise ConfigurationError("Missing OpenAI API configuration")
        
        # Validate processing configuration
        processing_config = self.config.get('processing', {})
        if processing_config.get('chunk_size', 0) <= 0:
            raise ConfigurationError("chunk_size must be greater than 0")
        if processing_config.get('max_blocks_per_chunk', 0) <= 0:
            raise ConfigurationError("max_blocks_per_chunk must be greater than 0")
        
        # Validate validation configuration
        validation_config = self.config.get('validation', {})
        if not 0 <= validation_config.get('min_hebrew_ratio', 0) <= 1:
            raise ConfigurationError("min_hebrew_ratio must be between 0 and 1")
        
        # Validate service configuration if present
        if 'service' in self.config:
            self._validate_service_config()
    
    def _validate_service_config(self):
        """Validate service configuration."""
        if 'service' not in self.config:
            return
        
        service_config = self.config['service']
        directories = service_config.get('directories', [])
        
        for i, directory in enumerate(directories):
            # Validate required fields
            if 'path' not in directory:
                raise ConfigurationError(f"Directory {i}: missing required field 'path'")
            
            # Validate path exists or is accessible (don't try to create in Docker)
            path = directory.get('path')
            if not os.path.exists(path):
                # In Docker, we should just check if the path is accessible via mount
                # Don't try to create directories that are mounted from host
                logging.warning(f"Directory {i}: path {path} does not exist, but may be accessible via Docker mount")
            
            # Validate scan interval
            scan_interval = directory.get('scan_interval_minutes', 30)
            if scan_interval < 1:
                raise ConfigurationError(f"Directory {i}: scan_interval_minutes must be at least 1")
            
            # Validate file size limit
            file_size_limit = directory.get('file_size_limit_mb', 10000)
            if file_size_limit <= 0:
                raise ConfigurationError(f"Directory {i}: file_size_limit_mb must be greater than 0")
        
        # Validate scanning configuration
        scanning_config = service_config.get('scanning', {})
        if scanning_config.get('scan_timeout_seconds', 300) <= 0:
            raise ConfigurationError("scan_timeout_seconds must be greater than 0")
        if scanning_config.get('max_files_per_scan', 1000) <= 0:
            raise ConfigurationError("max_files_per_scan must be greater than 0")
        if scanning_config.get('scan_workers', 2) <= 0:
            raise ConfigurationError("scan_workers must be greater than 0")
        
        # Validate processing configuration
        processing_config = service_config.get('processing', {})
        if processing_config.get('queue_size', 100) <= 0:
            raise ConfigurationError("queue_size must be greater than 0")
        if processing_config.get('worker_threads', 3) <= 0:
            raise ConfigurationError("worker_threads must be greater than 0")
        if processing_config.get('processing_timeout_seconds', 600) <= 0:
            raise ConfigurationError("processing_timeout_seconds must be greater than 0")
        
        # Validate performance configuration
        performance_config = service_config.get('performance', {})
        if not 0 <= performance_config.get('cpu_limit_percent', 80) <= 100:
            raise ConfigurationError("cpu_limit_percent must be between 0 and 100")
        if performance_config.get('memory_limit_mb', 2048) <= 0:
            raise ConfigurationError("memory_limit_mb must be greater than 0")
        
        # Validate health configuration
        health_config = service_config.get('health', {})
        if health_config.get('health_check_interval_seconds', 60) <= 0:
            raise ConfigurationError("health_check_interval_seconds must be greater than 0")
        if health_config.get('heartbeat_interval_seconds', 30) <= 0:
            raise ConfigurationError("heartbeat_interval_seconds must be greater than 0")
        if not 0 <= health_config.get('health_score_threshold', 50.0) <= 100:
            raise ConfigurationError("health_score_threshold must be between 0 and 100")
        
        # Validate database configuration
        database_config = service_config.get('database', {})
        db_path = database_config.get('file_path', './data/service_database.db')
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except OSError:
                raise ConfigurationError(f"Cannot create database directory: {db_dir}")
        
        # Validate logging configuration
        logging_config = service_config.get('logging', {})
        log_file = logging_config.get('service_log_file', 'logs/background_service.log')
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except OSError:
                raise ConfigurationError(f"Cannot create log directory: {log_dir}")
    
    def validate_service_directories(self) -> Dict[str, List[str]]:
        """
        Validate that all configured service directories are accessible.
        
        Returns:
            Dictionary with 'valid' and 'invalid' directory lists
        """
        if 'service' not in self.config:
            return {'valid': [], 'invalid': []}
        
        directories = self.config.get('service', {}).get('directories', [])
        valid_dirs = []
        invalid_dirs = []
        
        for directory in directories:
            path = directory.get('path', '')
            if not path:
                invalid_dirs.append(f"Empty path in directory config")
                continue
            
            try:
                # Check if path exists (don't try to create in Docker)
                if not os.path.exists(path):
                    # In Docker, just log a warning but don't fail
                    logging.warning(f"Path does not exist but may be accessible via Docker mount: {path}")
                    valid_dirs.append(path)  # Assume it's valid for Docker
                    continue
                
                # Check if path is readable
                if not os.access(path, os.R_OK):
                    invalid_dirs.append(f"Path not readable: {path}")
                else:
                    valid_dirs.append(path)
                    
            except Exception as e:
                invalid_dirs.append(f"Error accessing path {path}: {e}")
        
        return {'valid': valid_dirs, 'invalid': invalid_dirs}
    
    def get_service_config(self) -> Dict[str, Any]:
        """
        Get the service configuration section.
        
        Returns:
            Service configuration dictionary
        """
        return self.config.get('service', {})
    
    def update_service_config(self, updates: Dict[str, Any]) -> None:
        """
        Update service configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
        """
        if 'service' not in self.config:
            self.config['service'] = {}
        
        # Recursively update nested configuration
        self._update_nested_config(self.config['service'], updates)
        
        # Validate the updated configuration
        self._validate_service_config()
    
    def _update_nested_config(self, config: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """Recursively update nested configuration."""
        for key, value in updates.items():
            if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                self._update_nested_config(config[key], value)
            else:
                config[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'api.openai.model')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any):
        """
        Set a configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'api.openai.model')
            value: Value to set
        """
        keys = key.split('.')
        config = self.config
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
    
    def save_config(self, path: Optional[str] = None):
        """
        Save the current configuration to file.
        
        Args:
            path: Path to save configuration. If None, uses current config_path.
        """
        save_path = path or self.config_path
        
        # Ensure directory exists
        save_dir = os.path.dirname(save_path)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False, indent=2)
        
        logging.info(f"Configuration saved to {save_path}")
    
    def encrypt_value(self, value: str) -> str:
        """Encrypt a sensitive value."""
        if not self.encryption_key:
            return value
        
        fernet = Fernet(self.encryption_key)
        encrypted = fernet.encrypt(value.encode())
        return encrypted.decode()
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a sensitive value."""
        if not self.encryption_key:
            return encrypted_value
        
        try:
            fernet = Fernet(self.encryption_key)
            decrypted = fernet.decrypt(encrypted_value.encode())
            return decrypted.decode()
        except Exception as e:
            logging.warning(f"Failed to decrypt value: {e}")
            return encrypted_value
    
    def store_secure_value(self, key: str, value: str):
        """Store a value securely."""
        secure_dir = Path(self.get('security.secure_storage_path', './secure'))
        secure_dir.mkdir(exist_ok=True)
        
        secure_file = secure_dir / f"{key}.enc"
        encrypted_value = self.encrypt_value(value)
        
        with open(secure_file, 'w') as f:
            f.write(encrypted_value)
    
    def get_secure_value(self, key: str) -> Optional[str]:
        """Retrieve a securely stored value."""
        secure_dir = Path(self.get('security.secure_storage_path', './secure'))
        secure_file = secure_dir / f"{key}.enc"
        
        if not secure_file.exists():
            return None
        
        try:
            with open(secure_file, 'r') as f:
                encrypted_value = f.read().strip()
            return self.decrypt_value(encrypted_value)
        except Exception as e:
            logging.error(f"Failed to retrieve secure value {key}: {e}")
            return None
    
    def validate_api_keys(self) -> Dict[str, bool]:
        """
        Validate that all required API keys are present.
        
        Returns:
            Dictionary mapping API names to validation status
        """
        validation_results = {}
        
        # Check OpenSubtitles credentials
        opensubtitles_username = self.get('api.opensubtitles.username')
        opensubtitles_password = self.get('api.opensubtitles.password')
        validation_results['opensubtitles'] = bool(opensubtitles_username and opensubtitles_password)
        
        # Check OpenAI API key
        openai_api_key = self.get('api.openai.api_key')
        validation_results['openai'] = bool(openai_api_key)
        
        return validation_results
    
    def get_missing_environment_variables(self) -> List[str]:
        """
        Get list of missing environment variables.
        
        Returns:
            List of missing environment variable names
        """
        missing_vars = []
        required_vars = ['OPENSUBTITLES_USERNAME', 'OPENSUBTITLES_PASSWORD', 'OPENAI_API_KEY']
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        return missing_vars 