#!/usr/bin/env python3
"""
Unit tests for Background Service with SubtitleService integration.
"""

import unittest
import tempfile
import os
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import shutil

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.background_service import BackgroundService, ServiceState, ProcessingTask
from config.config_manager import ConfigManager
from services.file_tracker import ProcessingStatus


class TestBackgroundServiceIntegration(unittest.TestCase):
    """Test cases for BackgroundService with SubtitleService integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.yaml")
        
        # Create test configuration with service settings
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
                'level': 'DEBUG',
                'file': os.path.join(self.temp_dir, 'test.log'),
                'max_size': '10MB',
                'backup_count': 5,
                'format': 'json',
                'console_output': True
            },
            'security': {
                'encrypt_api_keys': False,
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
            },
            'service': {
                'directories': [
                    {
                        'path': self.temp_dir,
                        'enabled': True,
                        'recursive': True,
                        'scan_interval_minutes': 1,
                        'file_size_limit_mb': 1000,
                        'exclude_patterns': ['*.tmp'],
                        'include_patterns': ['*.mp4', '*.mkv', '*.avi']
                    }
                ],
                'scanning': {
                    'initial_scan_delay_seconds': 1,
                    'incremental_scan_enabled': True,
                    'full_scan_interval_hours': 24,
                    'scan_timeout_seconds': 60,
                    'max_files_per_scan': 10,
                    'parallel_scanning': False,
                    'scan_workers': 1
                },
                'processing': {
                    'queue_size': 10,
                    'worker_threads': 2,
                    'processing_timeout_seconds': 30,
                    'retry_failed_files': True,
                    'max_retry_attempts': 2,
                    'retry_delay_seconds': 1,
                    'prioritize_new_files': True,
                    'skip_existing_subtitles': True
                },
                'performance': {
                    'cpu_limit_percent': 80,
                    'memory_limit_mb': 1024,
                    'disk_io_limit_mbps': 50,
                    'network_limit_mbps': 25,
                    'adaptive_processing': True,
                    'low_power_mode': False
                },
                'health': {
                    'monitoring_enabled': True,
                    'health_check_interval_seconds': 30,
                    'heartbeat_interval_seconds': 15,
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
                    'backup_enabled': False,
                    'backup_interval_hours': 24,
                    'backup_retention_days': 7,
                    'vacuum_interval_hours': 168,
                    'max_database_size_mb': 100
                },
                'logging': {
                    'service_log_file': os.path.join(self.temp_dir, 'background_service.log'),
                    'debug_mode': True,
                    'verbose_logging': True,
                    'log_rotation': {
                        'max_size_mb': 10,
                        'backup_count': 5,
                        'compress': True
                    },
                    'levels': {
                        'background_service': 'DEBUG',
                        'directory_scanner': 'DEBUG',
                        'file_tracker': 'DEBUG',
                        'health_monitor': 'WARNING',
                        'communication': 'DEBUG',
                        'processing': 'DEBUG'
                    }
                }
            }
        }
        
        # Write test config to file
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(self.test_config, f)
        
        # Create test video files
        self.test_video_files = []
        for i in range(3):
            video_path = os.path.join(self.temp_dir, f"test_video_{i}.mp4")
            with open(video_path, 'w') as f:
                f.write(f"fake video content {i}")
            self.test_video_files.append(video_path)
    
    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test background service initialization with SubtitleService integration."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.subtitle_service)
        self.assertIsNotNone(service.file_tracker)
        self.assertIsNotNone(service.directory_scanner)
        self.assertEqual(service.state, ServiceState.STOPPED)
    
    def test_configuration_loading(self):
        """Test that service configuration is loaded correctly."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        # Check that processing configuration is loaded
        self.assertEqual(service._worker_threads_count, 2)
        self.assertEqual(service._queue_size, 10)
        self.assertEqual(service._processing_timeout, 30)
        self.assertTrue(service._retry_failed_files)
        self.assertEqual(service._max_retry_attempts, 2)
    
    def test_worker_thread_management(self):
        """Test worker thread start and stop functionality."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        # Start worker threads
        service._start_worker_threads()
        
        # Check that workers are started
        self.assertEqual(len(service._worker_threads), 2)
        self.assertTrue(all(worker.is_alive() for worker in service._worker_threads))
        
        # Stop worker threads
        service._stop_worker_threads()
        
        # Check that workers are stopped
        self.assertEqual(len(service._worker_threads), 0)
    
    def test_file_processing_queue(self):
        """Test file processing queue functionality."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        # Queue files for processing
        for video_file in self.test_video_files:
            success = service._queue_file_for_processing(video_file, priority=1)
            self.assertTrue(success)
        
        # Check queue statistics
        stats = service.get_processing_statistics()
        self.assertEqual(stats['tasks_queued'], 3)
        self.assertEqual(stats['queue_size'], 3)
    
    def test_existing_subtitle_detection(self):
        """Test detection of existing subtitle files."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        video_path = self.test_video_files[0]
        
        # Test with no existing subtitle
        existing_subtitle = service._find_existing_subtitle(video_path)
        self.assertIsNone(existing_subtitle)
        
        # Create a fake subtitle file
        video_name = Path(video_path).stem
        subtitle_path = os.path.join(self.temp_dir, f"{video_name}.heb.srt")
        with open(subtitle_path, 'w') as f:
            f.write("fake subtitle content")
        
        # Test with existing subtitle
        existing_subtitle = service._find_existing_subtitle(video_path)
        self.assertEqual(existing_subtitle, subtitle_path)
    
    @patch('services.subtitle_service.SubtitleService.process_video_file_with_validation')
    def test_video_file_processing(self, mock_process):
        """Test video file processing with mocked SubtitleService."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        # Mock successful processing
        mock_process.return_value = True
        
        video_path = self.test_video_files[0]
        result = service._process_video_file(video_path)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['subtitle_found'])
        self.assertTrue(result['subtitle_downloaded'])
        mock_process.assert_called_once_with(video_path)
    
    @patch('services.subtitle_service.SubtitleService.process_video_file_with_validation')
    def test_video_file_processing_failure(self, mock_process):
        """Test video file processing failure handling."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        # Mock failed processing
        mock_process.return_value = False
        
        video_path = self.test_video_files[0]
        result = service._process_video_file(video_path)
        
        self.assertFalse(result['success'])
        self.assertFalse(result['subtitle_found'])
        self.assertFalse(result['subtitle_downloaded'])
        mock_process.assert_called_once_with(video_path)
    
    @patch('services.subtitle_service.SubtitleService.process_video_file_with_validation')
    def test_video_file_processing_exception(self, mock_process):
        """Test video file processing exception handling."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        # Mock processing exception
        mock_process.side_effect = Exception("Processing failed")
        
        video_path = self.test_video_files[0]
        result = service._process_video_file(video_path)
        
        self.assertFalse(result['success'])
        self.assertIn("Processing failed", result['message'])
        mock_process.assert_called_once_with(video_path)
    
    def test_processing_task_creation(self):
        """Test ProcessingTask creation and management."""
        task = ProcessingTask(
            file_path="/path/to/video.mp4",
            task_id="test_task_001",
            priority=1
        )
        
        self.assertEqual(task.file_path, "/path/to/video.mp4")
        self.assertEqual(task.task_id, "test_task_001")
        self.assertEqual(task.priority, 1)
        self.assertEqual(task.status, "pending")
        self.assertEqual(task.retry_count, 0)
        self.assertEqual(task.max_retries, 3)
    
    @patch('services.directory_scanner.DirectoryScanner.get_files_batch')
    def test_scan_and_queue_files(self, mock_get_files):
        """Test directory scanning and file queuing."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        # Mock file batch results
        from services.file_tracker import FileInfo
        mock_files = [
            FileInfo(
                file_path=self.test_video_files[0],
                file_size=1024,
                modification_time=time.time(),
                is_new=True,
                needs_processing=True
            ),
            FileInfo(
                file_path=self.test_video_files[1],
                file_size=2048,
                modification_time=time.time(),
                is_new=False,
                needs_processing=True
            )
        ]
        mock_get_files.return_value = mock_files
        
        # Test scanning and queuing
        service._scan_and_queue_files()
        
        # Check that files were queued
        stats = service.get_processing_statistics()
        self.assertEqual(stats['tasks_queued'], 2)
        mock_get_files.assert_called_once_with(max_files=10)
    
    def test_service_start_stop_with_workers(self):
        """Test service start and stop with worker threads."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        # Start service
        success = service.start()
        self.assertTrue(success)
        self.assertEqual(service.state, ServiceState.RUNNING)
        
        # Wait a moment for threads to start
        time.sleep(0.1)
        
        # Check that workers are running
        self.assertEqual(len(service._worker_threads), 2)
        self.assertTrue(all(worker.is_alive() for worker in service._worker_threads))
        
        # Stop service
        success = service.stop()
        self.assertTrue(success)
        self.assertEqual(service.state, ServiceState.STOPPED)
        
        # Check that workers are stopped
        self.assertEqual(len(service._worker_threads), 0)
    
    def test_processing_statistics(self):
        """Test processing statistics tracking."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        # Initial statistics
        stats = service.get_processing_statistics()
        self.assertEqual(stats['queue_size'], 0)
        self.assertEqual(stats['active_workers'], 0)
        self.assertEqual(stats['total_workers'], 2)
        self.assertEqual(stats['tasks_queued'], 0)
        self.assertEqual(stats['tasks_completed'], 0)
        self.assertEqual(stats['tasks_failed'], 0)
        
        # Queue some files
        for video_file in self.test_video_files:
            service._queue_file_for_processing(video_file)
        
        # Check updated statistics
        stats = service.get_processing_statistics()
        self.assertEqual(stats['queue_size'], 3)
        self.assertEqual(stats['tasks_queued'], 3)
    
    def test_priority_queue_ordering(self):
        """Test that priority queue orders tasks correctly."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        # Queue files with different priorities
        service._queue_file_for_processing(self.test_video_files[0], priority=0)  # Normal
        service._queue_file_for_processing(self.test_video_files[1], priority=2)  # High
        service._queue_file_for_processing(self.test_video_files[2], priority=1)  # Medium
        
        # Get tasks from queue (should be in priority order)
        tasks = []
        while not service._processing_queue.empty():
            priority, task = service._processing_queue.get()
            tasks.append((priority, task.file_path))
        
        # Check priority ordering (higher priority numbers should come first)
        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks[0][0], -2)  # Highest priority (2) becomes -2
        self.assertEqual(tasks[1][0], -1)  # Medium priority (1) becomes -1
        self.assertEqual(tasks[2][0], 0)   # Normal priority (0) becomes 0
    
    def test_retry_logic(self):
        """Test retry logic for failed tasks."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        # Create a task that will fail
        task = ProcessingTask(
            file_path=self.test_video_files[0],
            task_id="retry_test",
            max_retries=2
        )
        
        # Simulate processing failure
        with patch.object(service, '_process_video_file') as mock_process:
            mock_process.side_effect = Exception("Processing error")
            
            # Process the task
            service._process_task(task, worker_id=0)
            
            # Check that task was marked for retry
            self.assertEqual(task.status, "retry")
            self.assertEqual(task.retry_count, 1)
            self.assertIsNotNone(task.error_message)
    
    def test_skip_existing_subtitles(self):
        """Test skipping files that already have subtitles."""
        config_manager = ConfigManager(self.config_path)
        service = BackgroundService(config_manager)
        
        video_path = self.test_video_files[0]
        
        # Create existing subtitle file
        video_name = Path(video_path).stem
        subtitle_path = os.path.join(self.temp_dir, f"{video_name}.heb.srt")
        with open(subtitle_path, 'w') as f:
            f.write("existing subtitle content")
        
        # Create task
        task = ProcessingTask(
            file_path=video_path,
            task_id="skip_test"
        )
        
        # Process task (should be skipped)
        service._process_task(task, worker_id=0)
        
        # Check that task was skipped
        self.assertEqual(task.status, "completed")
        self.assertTrue(task.result['skipped'])
        self.assertEqual(task.result['reason'], "subtitle_exists")
        self.assertEqual(task.result['existing_subtitle'], subtitle_path)


if __name__ == "__main__":
    unittest.main() 