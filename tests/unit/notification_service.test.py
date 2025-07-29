"""
Unit tests for NotificationService

Tests all notification functionality including:
- System notifications (cross-platform)
- Email notifications
- Logging and audit trail
- Notification preferences
- Event history and statistics
"""

import unittest
import tempfile
import os
import sys
import json
import threading
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.notification_service import (
    NotificationService,
    NotificationType,
    NotificationChannel,
    NotificationEvent,
    NotificationPreferences
)


class TestNotificationService(unittest.TestCase):
    """Test cases for NotificationService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_config = {
            'notifications': {
                'enabled': True,
                'system_notifications': True,
                'email_notifications': False,
                'log_notifications': True,
                'console_notifications': False,
                'events': {
                    'service_started': True,
                    'file_processed': False,
                    'file_failed': True
                },
                'email': {
                    'smtp_server': 'smtp.test.com',
                    'smtp_port': 587,
                    'username': 'test@test.com',
                    'password': 'password',
                    'from_address': 'test@test.com',
                    'to_addresses': ['user@test.com']
                },
                'system': {
                    'timeout_seconds': 5,
                    'sound_enabled': False
                }
            }
        }
        
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Initialize notification service
        self.notification_service = NotificationService(self.test_config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test notification service initialization."""
        self.assertIsNotNone(self.notification_service)
        self.assertTrue(self.notification_service.preferences.enabled)
        self.assertTrue(self.notification_service.preferences.system_notifications)
        self.assertFalse(self.notification_service.preferences.email_notifications)
        self.assertTrue(self.notification_service.preferences.log_notifications)
    
    def test_preferences_loading(self):
        """Test notification preferences loading from config."""
        preferences = self.notification_service.preferences
        
        # Test basic settings
        self.assertTrue(preferences.enabled)
        self.assertTrue(preferences.system_notifications)
        self.assertFalse(preferences.email_notifications)
        
        # Test event-specific settings
        self.assertTrue(preferences.events['service_started'])
        self.assertFalse(preferences.events['file_processed'])
        self.assertTrue(preferences.events['file_failed'])
        
        # Test email settings
        self.assertEqual(preferences.email['smtp_server'], 'smtp.test.com')
        self.assertEqual(preferences.email['smtp_port'], 587)
        self.assertEqual(preferences.email['username'], 'test@test.com')
        
        # Test system settings
        self.assertEqual(preferences.system['timeout_seconds'], 5)
        self.assertFalse(preferences.system['sound_enabled'])
    
    def test_notification_creation(self):
        """Test notification event creation."""
        event = self.notification_service.notify(
            event_type="test_event",
            title="Test Title",
            message="Test message",
            notification_type=NotificationType.INFO
        )
        
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "test_event")
        self.assertEqual(event.title, "Test Title")
        self.assertEqual(event.message, "Test message")
        self.assertEqual(event.notification_type, NotificationType.INFO)
        self.assertIsInstance(event.timestamp, datetime)
        self.assertFalse(event.acknowledged)
    
    def test_notification_disabled(self):
        """Test that notifications are not sent when disabled."""
        # Disable notifications
        self.notification_service.preferences.enabled = False
        
        event = self.notification_service.notify(
            event_type="test_event",
            title="Test Title",
            message="Test message"
        )
        
        self.assertIsNone(event)
    
    def test_event_type_filtering(self):
        """Test that notifications are filtered by event type."""
        # Disable a specific event type
        self.notification_service.preferences.events['test_event'] = False
        
        event = self.notification_service.notify(
            event_type="test_event",
            title="Test Title",
            message="Test message"
        )
        
        self.assertIsNone(event)
    
    def test_default_channels(self):
        """Test default channel selection based on notification type."""
        # Test INFO notification
        event = self.notification_service.notify(
            event_type="test_info",
            title="Info",
            message="Info message",
            notification_type=NotificationType.INFO
        )
        
        # Should include LOG and CONSOLE by default
        expected_channels = {NotificationChannel.LOG}
        self.assertEqual(set(event.channels), expected_channels)
        
        # Test ERROR notification
        event = self.notification_service.notify(
            event_type="test_error",
            title="Error",
            message="Error message",
            notification_type=NotificationType.ERROR
        )
        
        # Should include LOG, CONSOLE, and SYSTEM
        expected_channels = {NotificationChannel.LOG, NotificationChannel.SYSTEM}
        self.assertEqual(set(event.channels), expected_channels)
    
    def test_custom_channels(self):
        """Test custom channel specification."""
        event = self.notification_service.notify(
            event_type="test_custom",
            title="Custom",
            message="Custom message",
            channels=[NotificationChannel.EMAIL, NotificationChannel.LOG]
        )
        
        expected_channels = {NotificationChannel.EMAIL, NotificationChannel.LOG}
        self.assertEqual(set(event.channels), expected_channels)
    
    def test_event_history(self):
        """Test event history management."""
        # Send multiple notifications
        for i in range(5):
            self.notification_service.notify(
                event_type=f"test_event_{i}",
                title=f"Title {i}",
                message=f"Message {i}"
            )
        
        # Check history
        history = self.notification_service.get_event_history()
        self.assertEqual(len(history), 5)
        
        # Test filtering by event type
        filtered_history = self.notification_service.get_event_history(event_type="test_event_0")
        self.assertEqual(len(filtered_history), 1)
        self.assertEqual(filtered_history[0].event_type, "test_event_0")
        
        # Test filtering by notification type
        error_history = self.notification_service.get_event_history(notification_type=NotificationType.ERROR)
        self.assertEqual(len(error_history), 0)  # No error notifications sent
        
        # Test limit
        limited_history = self.notification_service.get_event_history(limit=3)
        self.assertEqual(len(limited_history), 3)
    
    def test_history_size_limit(self):
        """Test that history size is limited."""
        # Send more notifications than the limit
        for i in range(1100):  # More than max_history_size (1000)
            self.notification_service.notify(
                event_type=f"test_event_{i}",
                title=f"Title {i}",
                message=f"Message {i}"
            )
        
        # Check that history is limited
        history = self.notification_service.get_event_history()
        self.assertLessEqual(len(history), 1000)
    
    def test_notification_acknowledgment(self):
        """Test notification acknowledgment."""
        event = self.notification_service.notify(
            event_type="test_ack",
            title="Ack Test",
            message="Test message",
            requires_acknowledgment=True
        )
        
        self.assertTrue(event.requires_acknowledgment)
        self.assertFalse(event.acknowledged)
        
        # Acknowledge the notification
        result = self.notification_service.acknowledge_notification(event, "test_user")
        self.assertTrue(result)
        self.assertTrue(event.acknowledged)
        self.assertEqual(event.acknowledged_by, "test_user")
        self.assertIsNotNone(event.acknowledged_at)
        
        # Try to acknowledge again (should return False)
        result = self.notification_service.acknowledge_notification(event, "test_user2")
        self.assertFalse(result)
    
    def test_notification_statistics(self):
        """Test notification statistics."""
        # Send various types of notifications
        self.notification_service.notify(
            event_type="test_info",
            title="Info",
            message="Info message",
            notification_type=NotificationType.INFO
        )
        
        self.notification_service.notify(
            event_type="test_error",
            title="Error",
            message="Error message",
            notification_type=NotificationType.ERROR
        )
        
        self.notification_service.notify(
            event_type="test_ack",
            title="Ack",
            message="Ack message",
            requires_acknowledgment=True
        )
        
        # Get statistics
        stats = self.notification_service.get_statistics()
        
        self.assertEqual(stats['total_events'], 3)
        self.assertEqual(stats['type_counts']['info'], 1)
        self.assertEqual(stats['type_counts']['error'], 1)
        self.assertEqual(stats['acknowledged_count'], 0)
        self.assertEqual(stats['pending_acknowledgment'], 1)
    
    def test_callback_registration(self):
        """Test notification callback registration."""
        callback_called = False
        callback_event = None
        
        def test_callback(event):
            nonlocal callback_called, callback_event
            callback_called = True
            callback_event = event
        
        # Register callback
        self.notification_service.add_notification_callback(test_callback)
        
        # Send notification
        event = self.notification_service.notify(
            event_type="test_callback",
            title="Callback Test",
            message="Test message"
        )
        
        # Check that callback was called
        self.assertTrue(callback_called)
        self.assertEqual(callback_event, event)
        
        # Remove callback
        self.notification_service.remove_notification_callback(test_callback)
        
        # Reset flags
        callback_called = False
        callback_event = None
        
        # Send another notification
        self.notification_service.notify(
            event_type="test_callback2",
            title="Callback Test 2",
            message="Test message 2"
        )
        
        # Check that callback was not called
        self.assertFalse(callback_called)
        self.assertIsNone(callback_event)
    
    def test_preferences_update(self):
        """Test notification preferences update."""
        # Update preferences
        new_preferences = {
            'enabled': False,
            'system_notifications': False,
            'events': {
                'test_event': True
            }
        }
        
        self.notification_service.update_preferences(new_preferences)
        
        # Check that preferences were updated
        self.assertFalse(self.notification_service.preferences.enabled)
        self.assertFalse(self.notification_service.preferences.system_notifications)
        self.assertTrue(self.notification_service.preferences.events['test_event'])
    
    def test_clear_history(self):
        """Test history clearing."""
        # Send some notifications
        for i in range(3):
            self.notification_service.notify(
                event_type=f"test_event_{i}",
                title=f"Title {i}",
                message=f"Message {i}"
            )
        
        # Check that history has events
        history = self.notification_service.get_event_history()
        self.assertEqual(len(history), 3)
        
        # Clear history
        self.notification_service.clear_history()
        
        # Check that history is empty
        history = self.notification_service.get_event_history()
        self.assertEqual(len(history), 0)
    
    @patch('smtplib.SMTP')
    def test_email_notification(self, mock_smtp):
        """Test email notification sending."""
        # Enable email notifications
        self.notification_service.preferences.email_notifications = True
        
        # Mock SMTP
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        # Send email notification
        event = self.notification_service.notify(
            event_type="test_email",
            title="Email Test",
            message="Test email message",
            notification_type=NotificationType.ERROR,
            channels=[NotificationChannel.EMAIL]
        )
        
        # Check that SMTP was called
        mock_smtp.assert_called_once_with('smtp.test.com', 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@test.com', 'password')
        mock_server.send_message.assert_called_once()
    
    @patch('subprocess.run')
    def test_linux_notification(self, mock_run):
        """Test Linux notification sending."""
        # Mock platform detection
        with patch('platform.system', return_value='Linux'):
            # Reinitialize service for Linux
            service = NotificationService(self.test_config)
            
            # Send system notification
            event = service.notify(
                event_type="test_linux",
                title="Linux Test",
                message="Test Linux message",
                channels=[NotificationChannel.SYSTEM]
            )
            
            # Check that notify-send was called
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            self.assertEqual(args[0], "notify-send")
            self.assertEqual(args[1], "-u")
            self.assertEqual(args[2], "normal")
    
    def test_metadata_handling(self):
        """Test notification metadata handling."""
        metadata = {
            'file_path': '/path/to/file.mp4',
            'processing_time': 5.2,
            'subtitle_found': True
        }
        
        event = self.notification_service.notify(
            event_type="test_metadata",
            title="Metadata Test",
            message="Test message",
            metadata=metadata
        )
        
        self.assertEqual(event.metadata, metadata)
    
    def test_priority_handling(self):
        """Test notification priority handling."""
        event = self.notification_service.notify(
            event_type="test_priority",
            title="Priority Test",
            message="Test message",
            priority=2  # Urgent
        )
        
        self.assertEqual(event.priority, 2)
    
    def test_thread_safety(self):
        """Test notification service thread safety."""
        events_sent = []
        
        def worker(worker_id):
            for i in range(10):
                event = self.notification_service.notify(
                    event_type=f"worker_{worker_id}_event_{i}",
                    title=f"Worker {worker_id} Event {i}",
                    message=f"Message from worker {worker_id}"
                )
                events_sent.append(event)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that all events were created
        self.assertEqual(len(events_sent), 50)
        
        # Check that history contains all events
        history = self.notification_service.get_event_history()
        self.assertEqual(len(history), 50)
    
    def test_test_notification(self):
        """Test test notification functionality."""
        # Test system notification
        result = self.notification_service.test_notification(NotificationChannel.SYSTEM)
        # Should return True (even if platform doesn't support it, it won't fail)
        self.assertTrue(result)
        
        # Test log notification
        result = self.notification_service.test_notification(NotificationChannel.LOG)
        self.assertTrue(result)
        
        # Test console notification
        result = self.notification_service.test_notification(NotificationChannel.CONSOLE)
        self.assertTrue(result)


class TestNotificationPreferences(unittest.TestCase):
    """Test cases for NotificationPreferences."""
    
    def test_default_preferences(self):
        """Test default notification preferences."""
        preferences = NotificationPreferences()
        
        self.assertTrue(preferences.enabled)
        self.assertTrue(preferences.system_notifications)
        self.assertFalse(preferences.email_notifications)
        self.assertTrue(preferences.log_notifications)
        self.assertFalse(preferences.console_notifications)
        
        # Check default events
        self.assertTrue(preferences.events['service_started'])
        self.assertTrue(preferences.events['file_failed'])
        self.assertFalse(preferences.events['file_processed'])
    
    def test_email_settings(self):
        """Test email settings defaults."""
        preferences = NotificationPreferences()
        
        self.assertEqual(preferences.email['smtp_server'], 'smtp.gmail.com')
        self.assertEqual(preferences.email['smtp_port'], 587)
        self.assertTrue(preferences.email['use_tls'])
    
    def test_system_settings(self):
        """Test system notification settings defaults."""
        preferences = NotificationPreferences()
        
        self.assertEqual(preferences.system['timeout_seconds'], 10)
        self.assertTrue(preferences.system['sound_enabled'])
        self.assertTrue(preferences.system['show_icon'])


class TestNotificationEvent(unittest.TestCase):
    """Test cases for NotificationEvent."""
    
    def test_event_creation(self):
        """Test notification event creation."""
        event = NotificationEvent(
            event_type="test",
            title="Test Title",
            message="Test message",
            notification_type=NotificationType.INFO,
            channels=[NotificationChannel.LOG]
        )
        
        self.assertEqual(event.event_type, "test")
        self.assertEqual(event.title, "Test Title")
        self.assertEqual(event.message, "Test message")
        self.assertEqual(event.notification_type, NotificationType.INFO)
        self.assertEqual(event.channels, [NotificationChannel.LOG])
        self.assertIsInstance(event.timestamp, datetime)
        self.assertFalse(event.acknowledged)
    
    def test_event_with_metadata(self):
        """Test notification event with metadata."""
        metadata = {'key': 'value', 'number': 42}
        
        event = NotificationEvent(
            event_type="test",
            title="Test Title",
            message="Test message",
            notification_type=NotificationType.INFO,
            channels=[NotificationChannel.LOG],
            metadata=metadata
        )
        
        self.assertEqual(event.metadata, metadata)
    
    def test_event_acknowledgment(self):
        """Test notification event acknowledgment."""
        event = NotificationEvent(
            event_type="test",
            title="Test Title",
            message="Test message",
            notification_type=NotificationType.INFO,
            channels=[NotificationChannel.LOG],
            requires_acknowledgment=True
        )
        
        self.assertTrue(event.requires_acknowledgment)
        self.assertFalse(event.acknowledged)
        self.assertIsNone(event.acknowledged_at)
        self.assertIsNone(event.acknowledged_by)


if __name__ == '__main__':
    unittest.main() 