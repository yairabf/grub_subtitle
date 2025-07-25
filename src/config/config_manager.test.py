#!/usr/bin/env python3
"""
Unit tests for ConfigManager.
"""

import unittest
import tempfile
import os
import yaml
from unittest.mock import patch, mock_open
import shutil

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.config_manager import ConfigManager, ConfigurationError

class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.yaml")
        
        # Create a basic test configuration
        self.test_config = {
            'api': {
                'opensubtitles': {
                    'username': 'test_user',
                    'password': 'test_pass',
                    'base_url': 'https://api.opensubtitles.com/xml-rpc',
                    'user_agent': 'TestAgent/1.0',
                    'timeout': 30,
                    'max_retries': 3
                },
                'openai': {
                    'api_key': 'test_key',
                    'model': 'gpt-3.5-turbo',
                    'temperature': 0.3,
                    'max_tokens': 4000,
                    'timeout': 60,
                    'max_retries': 3
                }
            },
            'processing': {
                'chunk_size': 3000,
                'max_blocks_per_chunk': 10,
                'supported_video_formats': ['.mp4', '.mkv', '.avi'],
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
                'file': 'logs/test.log',
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
                'cache_directory': './cache',
                'data_directory': './data',
                'temp_directory': './temp'
            }
        }
        
        # Write test config to file
        with open(self.config_path, 'w') as f:
            yaml.dump(self.test_config, f)
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test ConfigManager initialization."""
        config_manager = ConfigManager(self.config_path)
        self.assertIsNotNone(config_manager)
        self.assertEqual(config_manager.config_path, self.config_path)
    
    def test_load_config(self):
        """Test configuration loading."""
        config_manager = ConfigManager(self.config_path)
        config = config_manager.load_config()
        
        self.assertIn('api', config)
        self.assertIn('processing', config)
        self.assertIn('validation', config)
        self.assertIn('logging', config)
        self.assertIn('security', config)
        self.assertIn('ui', config)
        self.assertIn('paths', config)
    
    def test_get_config_value(self):
        """Test getting configuration values."""
        config_manager = ConfigManager(self.config_path)
        
        # Test getting nested values
        model = config_manager.get('api.openai.model')
        self.assertEqual(model, 'gpt-3.5-turbo')
        
        # Test getting with default
        non_existent = config_manager.get('non.existent.key', 'default_value')
        self.assertEqual(non_existent, 'default_value')
    
    def test_set_config_value(self):
        """Test setting configuration values."""
        config_manager = ConfigManager(self.config_path)
        
        # Set a new value
        config_manager.set('api.openai.model', 'gpt-4')
        model = config_manager.get('api.openai.model')
        self.assertEqual(model, 'gpt-4')
        
        # Set a nested value
        config_manager.set('new.section.value', 'test_value')
        value = config_manager.get('new.section.value')
        self.assertEqual(value, 'test_value')
    
    def test_environment_variable_substitution(self):
        """Test environment variable substitution."""
        with patch.dict(os.environ, {'TEST_VAR': 'test_value'}):
            config_manager = ConfigManager(self.config_path)
            config_manager.load_config()
            
            # Test substitution in string
            config_manager.set('test.path', '${TEST_VAR}/subpath')
            result = config_manager.get('test.path')
            self.assertEqual(result, 'test_value/subpath')
    
    def test_missing_environment_variable(self):
        """Test handling of missing environment variables."""
        config_manager = ConfigManager(self.config_path)
        config_manager.load_config()
        
        # Set a value with missing environment variable
        config_manager.set('test.path', '${MISSING_VAR}/subpath')
        
        # Should raise ConfigurationError when accessed
        with self.assertRaises(ConfigurationError):
            config_manager.get('test.path')
    
    def test_validation(self):
        """Test configuration validation."""
        config_manager = ConfigManager(self.config_path)
        
        # Should not raise any errors for valid config
        try:
            config_manager.load_config()
        except ConfigurationError:
            self.fail("Valid configuration should not raise ConfigurationError")
    
    def test_invalid_config(self):
        """Test validation of invalid configuration."""
        # Create invalid config
        invalid_config = self.test_config.copy()
        del invalid_config['api']['opensubtitles']  # Remove required section
        
        invalid_config_path = os.path.join(self.temp_dir, "invalid_config.yaml")
        with open(invalid_config_path, 'w') as f:
            yaml.dump(invalid_config, f)
        
        # Should raise ConfigurationError during initialization
        with self.assertRaises(ConfigurationError):
            ConfigManager(invalid_config_path)
    
    def test_service_config_validation(self):
        """Test service configuration validation."""
        # Add service configuration to test config
        service_config = {
            'service': {
                'directories': [
                    {
                        'path': self.temp_dir,
                        'enabled': True,
                        'recursive': True,
                        'scan_interval_minutes': 30,
                        'file_size_limit_mb': 10000,
                        'exclude_patterns': ['*.tmp'],
                        'include_patterns': ['*.mp4', '*.mkv']
                    }
                ],
                'scanning': {
                    'initial_scan_delay_seconds': 10,
                    'incremental_scan_enabled': True,
                    'full_scan_interval_hours': 24,
                    'scan_timeout_seconds': 300,
                    'max_files_per_scan': 1000,
                    'parallel_scanning': True,
                    'scan_workers': 2
                },
                'processing': {
                    'queue_size': 100,
                    'worker_threads': 3,
                    'processing_timeout_seconds': 600,
                    'retry_failed_files': True,
                    'max_retry_attempts': 3,
                    'retry_delay_seconds': 60,
                    'prioritize_new_files': True,
                    'skip_existing_subtitles': True
                },
                'performance': {
                    'cpu_limit_percent': 80,
                    'memory_limit_mb': 2048,
                    'disk_io_limit_mbps': 100,
                    'network_limit_mbps': 50,
                    'adaptive_processing': True,
                    'low_power_mode': False
                },
                'health': {
                    'monitoring_enabled': True,
                    'health_check_interval_seconds': 60,
                    'heartbeat_interval_seconds': 30,
                    'crash_detection_enabled': True,
                    'auto_recovery_enabled': True,
                    'health_score_threshold': 50.0,
                    'cpu_warning_percent': 70,
                    'cpu_critical_percent': 90,
                    'memory_warning_percent': 80,
                    'memory_critical_percent': 95,
                    'disk_warning_percent': 85,
                    'disk_critical_percent': 95
                },
                'database': {
                    'file_path': os.path.join(self.temp_dir, 'service_database.db'),
                    'backup_enabled': True,
                    'backup_interval_hours': 24,
                    'backup_retention_days': 7,
                    'vacuum_interval_hours': 168,
                    'max_database_size_mb': 100
                },
                'logging': {
                    'service_log_file': os.path.join(self.temp_dir, 'background_service.log'),
                    'debug_mode': False,
                    'verbose_logging': False,
                    'log_rotation': {
                        'max_size_mb': 10,
                        'backup_count': 5,
                        'compress': True
                    },
                    'levels': {
                        'background_service': 'INFO',
                        'directory_scanner': 'INFO',
                        'file_tracker': 'INFO',
                        'health_monitor': 'WARNING',
                        'communication': 'INFO',
                        'processing': 'INFO'
                    }
                }
            }
        }
        
        self.test_config.update(service_config)
        
        # Write updated config
        with open(self.config_path, 'w') as f:
            yaml.dump(self.test_config, f)
        
        config_manager = ConfigManager(self.config_path)
        
        # Should not raise any errors for valid service config
        try:
            config_manager.load_config()
        except ConfigurationError:
            self.fail("Valid service configuration should not raise ConfigurationError")
    
    def test_service_config_validation_errors(self):
        """Test service configuration validation errors."""
        # Add invalid service configuration
        invalid_service_config = {
            'service': {
                'directories': [
                    {
                        'path': '',  # Empty path
                        'enabled': True,
                        'scan_interval_minutes': 0  # Invalid interval
                    }
                ],
                'scanning': {
                    'scan_timeout_seconds': -1  # Invalid timeout
                },
                'processing': {
                    'queue_size': 0  # Invalid queue size
                },
                'performance': {
                    'cpu_limit_percent': 150  # Invalid percentage
                },
                'health': {
                    'health_score_threshold': 150.0  # Invalid threshold
                }
            }
        }
        
        self.test_config.update(invalid_service_config)
        
        # Write invalid config
        with open(self.config_path, 'w') as f:
            yaml.dump(self.test_config, f)
        
        # Should raise ConfigurationError for invalid service config
        with self.assertRaises(ConfigurationError):
            ConfigManager(self.config_path)
    
    def test_validate_service_directories(self):
        """Test service directory validation."""
        # Add service configuration with directories
        service_config = {
            'service': {
                'directories': [
                    {
                        'path': self.temp_dir,  # Valid directory
                        'enabled': True
                    },
                    {
                        'path': os.path.join(self.temp_dir, 'non_existent'),  # Invalid directory
                        'enabled': True
                    }
                ]
            }
        }
        
        self.test_config.update(service_config)
        
        # Write config
        with open(self.config_path, 'w') as f:
            yaml.dump(self.test_config, f)
        
        config_manager = ConfigManager(self.config_path)
        config_manager.load_config()
        
        # Validate directories
        result = config_manager.validate_service_directories()
        
        self.assertIn('valid', result)
        self.assertIn('invalid', result)
        self.assertIn(self.temp_dir, result['valid'])
        self.assertTrue(len(result['invalid']) > 0)
    
    def test_get_service_config(self):
        """Test getting service configuration."""
        service_config = {
            'service': {
                'directories': [
                    {
                        'path': self.temp_dir,
                        'enabled': True
                    }
                ]
            }
        }
        
        self.test_config.update(service_config)
        
        # Write config
        with open(self.config_path, 'w') as f:
            yaml.dump(self.test_config, f)
        
        config_manager = ConfigManager(self.config_path)
        config_manager.load_config()
        
        # Get service config
        service_config_result = config_manager.get_service_config()
        
        self.assertIn('directories', service_config_result)
        self.assertEqual(len(service_config_result['directories']), 1)
        self.assertEqual(service_config_result['directories'][0]['path'], self.temp_dir)
    
    def test_update_service_config(self):
        """Test updating service configuration."""
        service_config = {
            'service': {
                'directories': [
                    {
                        'path': self.temp_dir,
                        'enabled': True
                    }
                ]
            }
        }
        
        self.test_config.update(service_config)
        
        # Write config
        with open(self.config_path, 'w') as f:
            yaml.dump(self.test_config, f)
        
        config_manager = ConfigManager(self.config_path)
        config_manager.load_config()
        
        # Update service config
        updates = {
            'scanning': {
                'scan_timeout_seconds': 600
            },
            'processing': {
                'worker_threads': 5
            }
        }
        
        config_manager.update_service_config(updates)
        
        # Verify updates
        service_config_result = config_manager.get_service_config()
        self.assertEqual(service_config_result['scanning']['scan_timeout_seconds'], 600)
        self.assertEqual(service_config_result['processing']['worker_threads'], 5)
    
    def test_save_config(self):
        """Test saving configuration."""
        config_manager = ConfigManager(self.config_path)
        config_manager.load_config()
        
        # Modify config
        config_manager.set('api.openai.model', 'gpt-4')
        
        # Save to new file
        new_config_path = os.path.join(self.temp_dir, "saved_config.yaml")
        config_manager.save_config(new_config_path)
        
        # Verify file was created
        self.assertTrue(os.path.exists(new_config_path))
        
        # Load and verify
        new_config_manager = ConfigManager(new_config_path)
        new_config_manager.load_config()
        model = new_config_manager.get('api.openai.model')
        self.assertEqual(model, 'gpt-4')
    
    def test_encryption_decryption(self):
        """Test encryption and decryption of values."""
        config_manager = ConfigManager(self.config_path)
        
        original_value = "sensitive_data"
        
        # Encrypt value
        encrypted = config_manager.encrypt_value(original_value)
        self.assertNotEqual(encrypted, original_value)
        
        # Decrypt value
        decrypted = config_manager.decrypt_value(encrypted)
        self.assertEqual(decrypted, original_value)
    
    def test_secure_storage(self):
        """Test secure value storage."""
        config_manager = ConfigManager(self.config_path)
        
        # Store secure value
        config_manager.store_secure_value('test_key', 'secure_value')
        
        # Retrieve secure value
        value = config_manager.get_secure_value('test_key')
        self.assertEqual(value, 'secure_value')
        
        # Test non-existent key
        non_existent = config_manager.get_secure_value('non_existent_key')
        self.assertIsNone(non_existent)

if __name__ == "__main__":
    unittest.main() 