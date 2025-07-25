"""
Unit tests for BackgroundService class.
"""

import unittest
import time
import threading
from unittest.mock import Mock, patch
from pathlib import Path
from datetime import datetime

from services.background_service import BackgroundService, ServiceState, ServiceStatus, ServiceStateError


class TestBackgroundService(unittest.TestCase):
    """Test cases for BackgroundService class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the dependencies
        self.mock_config_manager = Mock()
        self.mock_logger = Mock()
        self.mock_subtitle_service = Mock()
        
        # Configure mock config
        self.mock_config_manager.config = {
            'background_service': {
                'scan_interval_seconds': 300,
                'monitored_directories': ['/test/dir1', '/test/dir2']
            }
        }
        
        # Create service with mocked dependencies
        with patch('services.background_service.ConfigManager', return_value=self.mock_config_manager), \
             patch('services.background_service.SubtitleLogger', return_value=self.mock_logger), \
             patch('services.background_service.SubtitleService', return_value=self.mock_subtitle_service):
            
            self.service = BackgroundService()
    
    def test_initial_state(self):
        """Test that service starts in STOPPED state."""
        self.assertEqual(self.service.state, ServiceState.STOPPED)
        self.assertEqual(self.service.status.state, ServiceState.STOPPED)
    
    def test_valid_state_transitions(self):
        """Test valid state transitions."""
        # STOPPED -> STARTING
        self.assertTrue(self.service.can_transition_to(ServiceState.STARTING))
        
        # STOPPED -> RUNNING (invalid)
        self.assertFalse(self.service.can_transition_to(ServiceState.RUNNING))
        
        # STOPPED -> STOPPING (invalid)
        self.assertFalse(self.service.can_transition_to(ServiceState.STOPPING))
    
    def test_start_service_success(self):
        """Test successful service start."""
        # Mock directory existence
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            result = self.service.start()
            
            self.assertTrue(result)
            self.assertEqual(self.service.state, ServiceState.RUNNING)
            self.assertIsNotNone(self.service.status.start_time)
            self.assertIsNone(self.service.status.error_message)
            self.assertEqual(self.service.status.consecutive_errors, 0)
    
    def test_start_service_invalid_config(self):
        """Test service start with invalid configuration."""
        # Mock empty monitored directories
        self.mock_config_manager.config = {
            'background_service': {
                'scan_interval_seconds': 300,
                'monitored_directories': []
            }
        }
        
        result = self.service.start()
        
        self.assertFalse(result)
        self.assertEqual(self.service.state, ServiceState.ERROR)
        self.assertIsNotNone(self.service.status.error_message)
    
    def test_start_service_already_running(self):
        """Test starting service that is already running."""
        # Start the service first
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            self.service.start()
        
        # Try to start again
        result = self.service.start()
        
        self.assertFalse(result)
        self.assertEqual(self.service.state, ServiceState.RUNNING)
    
    def test_stop_service_success(self):
        """Test successful service stop."""
        # Start the service first
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            self.service.start()
        
        # Stop the service
        result = self.service.stop()
        
        self.assertTrue(result)
        self.assertEqual(self.service.state, ServiceState.STOPPED)
    
    def test_stop_service_already_stopped(self):
        """Test stopping service that is already stopped."""
        result = self.service.stop()
        
        self.assertTrue(result)
        self.assertEqual(self.service.state, ServiceState.STOPPED)
    
    def test_pause_and_resume_service(self):
        """Test pausing and resuming the service."""
        # Start the service first
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            self.service.start()
            self.assertEqual(self.service.state, ServiceState.RUNNING)
            
            # Pause the service
            result = self.service.pause()
            self.assertTrue(result)
            self.assertEqual(self.service.state, ServiceState.PAUSED)
            
            # Resume the service
            result = self.service.resume()
            self.assertTrue(result)
            self.assertEqual(self.service.state, ServiceState.RUNNING)
    
    def test_pause_service_not_running(self):
        """Test pausing service that is not running."""
        result = self.service.pause()
        self.assertFalse(result)
        self.assertEqual(self.service.state, ServiceState.STOPPED)
    
    def test_resume_service_not_paused(self):
        """Test resuming service that is not paused."""
        result = self.service.resume()
        self.assertFalse(result)
        self.assertEqual(self.service.state, ServiceState.STOPPED)
    
    def test_restart_service(self):
        """Test service restart functionality."""
        # Mock directory existence
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            # Start the service
            self.service.start()
            self.assertEqual(self.service.state, ServiceState.RUNNING)
            
            # Restart the service
            result = self.service.restart()
            
            self.assertTrue(result)
            self.assertEqual(self.service.state, ServiceState.RUNNING)
    
    def test_state_history(self):
        """Test state transition history tracking."""
        # Start and stop service to create history
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            self.service.start()
            self.service.stop()
        
        history = self.service.get_state_history()
        
        self.assertGreater(len(history), 0)
        self.assertIn('timestamp', history[0])
        self.assertIn('from_state', history[0])
        self.assertIn('to_state', history[0])
        self.assertIn('reason', history[0])
    
    def test_wait_for_state(self):
        """Test waiting for specific state."""
        # Start service in background
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            # Start service in a separate thread
            def start_service():
                time.sleep(0.1)  # Small delay
                self.service.start()
            
            thread = threading.Thread(target=start_service)
            thread.start()
            
            # Wait for running state
            result = self.service.wait_for_state(ServiceState.RUNNING, timeout=5.0)
            
            thread.join()
            
            self.assertTrue(result)
            self.assertEqual(self.service.state, ServiceState.RUNNING)
    
    def test_wait_for_state_timeout(self):
        """Test waiting for state with timeout."""
        result = self.service.wait_for_state(ServiceState.RUNNING, timeout=0.1)
        self.assertFalse(result)
    
    def test_is_in_state(self):
        """Test checking if service is in specific state."""
        self.assertTrue(self.service.is_in_state(ServiceState.STOPPED))
        self.assertFalse(self.service.is_in_state(ServiceState.RUNNING))
    
    def test_health_score_calculation(self):
        """Test health score calculation."""
        # Initial health should be 100
        self.assertEqual(self.service.status.health_score, 100.0)
        
        # Simulate errors
        self.service._update_status(consecutive_errors=2)
        self.assertEqual(self.service.status.health_score, 80.0)  # 100 - (2 * 10)
    
    def test_status_callback(self):
        """Test status callback functionality."""
        callback_called = False
        callback_status = None
        
        def status_callback(status: ServiceStatus):
            nonlocal callback_called, callback_status
            callback_called = True
            callback_status = status
        
        # Add callback
        self.service.add_status_callback(status_callback)
        
        # Start service to trigger callback
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            self.service.start()
        
        # Give some time for callback to be called
        time.sleep(0.1)
        
        self.assertTrue(callback_called)
        self.assertIsNotNone(callback_status)
        self.assertEqual(callback_status.state, ServiceState.RUNNING)
    
    def test_state_callback(self):
        """Test state callback functionality."""
        callback_called = False
        old_state = None
        new_state = None
        
        def state_callback(old: ServiceState, new: ServiceState):
            nonlocal callback_called, old_state, new_state
            callback_called = True
            old_state = old
            new_state = new
        
        # Add callback
        self.service.add_state_callback(state_callback)
        
        # Start service to trigger callback
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            self.service.start()
        
        # Give some time for callback to be called
        time.sleep(0.1)
        
        self.assertTrue(callback_called)
        self.assertEqual(old_state, ServiceState.STARTING)
        self.assertEqual(new_state, ServiceState.RUNNING)
    
    def test_remove_status_callback(self):
        """Test removing status callback."""
        callback_called = False
        
        def status_callback(status: ServiceStatus):
            nonlocal callback_called
            callback_called = True
        
        # Add and then remove callback
        self.service.add_status_callback(status_callback)
        self.service.remove_status_callback(status_callback)
        
        # Start service
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            self.service.start()
        
        # Give some time for callback to be called
        time.sleep(0.1)
        
        # Callback should not be called since it was removed
        self.assertFalse(callback_called)
    
    def test_get_status_summary(self):
        """Test getting status summary."""
        summary = self.service.get_status_summary()
        
        self.assertIsInstance(summary, dict)
        self.assertIn('state', summary)
        self.assertIn('start_time', summary)
        self.assertIn('last_scan_time', summary)
        self.assertIn('files_processed', summary)
        self.assertIn('files_failed', summary)
        self.assertIn('current_operation', summary)
        self.assertIn('error_message', summary)
        self.assertIn('uptime_seconds', summary)
        self.assertIn('health_score', summary)
        self.assertIn('consecutive_errors', summary)
        self.assertIn('monitored_directories', summary)
        self.assertIn('scan_interval', summary)
        self.assertIn('can_start', summary)
        self.assertIn('can_stop', summary)
        self.assertIn('can_pause', summary)
        self.assertIn('can_resume', summary)
        
        self.assertEqual(summary['state'], ServiceState.STOPPED.value)
        self.assertEqual(summary['files_processed'], 0)
        self.assertEqual(summary['files_failed'], 0)
        self.assertEqual(summary['health_score'], 100.0)
        self.assertTrue(summary['can_start'])
        self.assertFalse(summary['can_stop'])
    
    def test_thread_safety(self):
        """Test thread safety of service operations."""
        results = []
        errors = []
        
        def worker():
            try:
                # Multiple threads trying to start/stop service
                for i in range(10):
                    if i % 2 == 0:
                        result = self.service.start()
                    else:
                        result = self.service.stop()
                    results.append(result)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should not have any errors
        self.assertEqual(len(errors), 0)
        self.assertGreater(len(results), 0)
    
    def test_concurrent_callback_management(self):
        """Test concurrent callback management."""
        callback_count = 0
        
        def test_callback(status: ServiceStatus):
            nonlocal callback_count
            callback_count += 1
        
        # Add callbacks from multiple threads
        def add_callbacks():
            for _ in range(5):
                self.service.add_status_callback(test_callback)
                time.sleep(0.01)
        
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=add_callbacks)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have added callbacks without errors
        self.assertGreater(callback_count, 0)


if __name__ == '__main__':
    unittest.main() 