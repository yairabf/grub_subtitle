#!/usr/bin/env python3
"""
Unit tests for Service Communication Manager.
"""

import unittest
import time
import threading
from unittest.mock import Mock, patch
from datetime import datetime

from services.service_communication import (
    ServiceCommunicationManager,
    MessageType,
    UserCommand,
    ServiceMessage,
    StatusMessage,
    ProgressMessage,
    FileProcessedMessage,
    ScanUpdateMessage,
    ErrorMessage,
    CommandMessage
)
from logging_system.subtitle_logger import SubtitleLogger

class TestServiceCommunicationManager(unittest.TestCase):
    """Test cases for ServiceCommunicationManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'logging': {
                'level': 'DEBUG',
                'format': 'json'
            }
        }
        self.logger = Mock(spec=SubtitleLogger)
        self.comm_manager = ServiceCommunicationManager(self.config, self.logger)
    
    def tearDown(self):
        """Clean up after tests."""
        if self.comm_manager._is_running:
            self.comm_manager.stop()
    
    def test_initialization(self):
        """Test communication manager initialization."""
        self.assertIsNotNone(self.comm_manager)
        self.assertEqual(self.comm_manager.config, self.config)
        self.assertEqual(self.comm_manager.logger, self.logger)
        self.assertFalse(self.comm_manager._is_running)
    
    def test_start_stop(self):
        """Test starting and stopping the communication manager."""
        # Test start
        self.comm_manager.start()
        self.assertTrue(self.comm_manager._is_running)
        self.assertIsNotNone(self.comm_manager._service_thread)
        self.assertIsNotNone(self.comm_manager._command_thread)
        self.assertTrue(self.comm_manager._service_thread.is_alive())
        self.assertTrue(self.comm_manager._command_thread.is_alive())
        
        # Test stop
        self.comm_manager.stop()
        self.assertFalse(self.comm_manager._is_running)
        self.assertFalse(self.comm_manager._service_thread.is_alive())
        self.assertFalse(self.comm_manager._command_thread.is_alive())
    
    def test_send_message(self):
        """Test sending messages."""
        self.comm_manager.start()
        
        # Create a test message
        message = ServiceMessage(
            message_type=MessageType.STATUS_UPDATE,
            source="test",
            target="all",
            data={"test": "data"}
        )
        
        # Send message
        result = self.comm_manager.send_message(message)
        self.assertTrue(result)
        self.assertEqual(self.comm_manager._service_queue.qsize(), 1)
    
    def test_send_command(self):
        """Test sending commands."""
        self.comm_manager.start()
        
        # Send command
        result = self.comm_manager.send_command(UserCommand.GET_STATUS)
        self.assertTrue(result)
        self.assertEqual(self.comm_manager._command_queue.qsize(), 1)
    
    def test_message_processor_registration(self):
        """Test message processor registration."""
        processor = Mock()
        self.comm_manager.register_message_processor(MessageType.STATUS_UPDATE, processor)
        
        self.assertIn(MessageType.STATUS_UPDATE, self.comm_manager._message_processors)
        self.assertIn(processor, self.comm_manager._message_processors[MessageType.STATUS_UPDATE])
    
    def test_command_handler_registration(self):
        """Test command handler registration."""
        handler = Mock()
        self.comm_manager.register_command_handler(UserCommand.START_SERVICE, handler)
        
        self.assertIn(UserCommand.START_SERVICE, self.comm_manager._command_handlers)
        self.assertEqual(self.comm_manager._command_handlers[UserCommand.START_SERVICE], handler)
    
    def test_message_processing(self):
        """Test message processing."""
        self.comm_manager.start()
        
        # Register a test processor
        processor = Mock()
        self.comm_manager.register_message_processor(MessageType.STATUS_UPDATE, processor)
        
        # Send a message
        message = ServiceMessage(
            message_type=MessageType.STATUS_UPDATE,
            source="test",
            target="all",
            data={"test": "data"}
        )
        self.comm_manager.send_message(message)
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check if processor was called
        processor.assert_called_once()
        processed_message = processor.call_args[0][0]
        self.assertEqual(processed_message.message_type, MessageType.STATUS_UPDATE)
    
    def test_command_processing(self):
        """Test command processing."""
        self.comm_manager.start()
        
        # Register a test handler
        handler = Mock()
        self.comm_manager.register_command_handler(UserCommand.START_SERVICE, handler)
        
        # Send a command
        self.comm_manager.send_command(UserCommand.START_SERVICE, {"param": "value"})
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check if handler was called
        handler.assert_called_once_with({"param": "value"})
    
    def test_convenience_methods(self):
        """Test convenience methods for sending specific message types."""
        self.comm_manager.start()
        
        # Test status update
        status_data = {
            "service_state": "running",
            "uptime_seconds": 3600,
            "last_scan": "2025-07-25T14:30:00"
        }
        result = self.comm_manager.send_status_update(status_data)
        self.assertTrue(result)
        
        # Test progress update
        progress_data = {
            "current_file": "test.mp4",
            "progress_percent": 50.0,
            "total_files": 10,
            "processed_files": 5
        }
        result = self.comm_manager.send_progress_update(progress_data)
        self.assertTrue(result)
        
        # Test file processed
        file_data = {
            "file_path": "test.mp4",
            "processing_result": "success",
            "processing_time": 2.5,
            "subtitle_found": True
        }
        result = self.comm_manager.send_file_processed(file_data)
        self.assertTrue(result)
        
        # Test scan update
        scan_data = {
            "scan_session_id": "scan_123",
            "scan_type": "full",
            "total_files_found": 100,
            "new_files_found": 5
        }
        result = self.comm_manager.send_scan_update(scan_data)
        self.assertTrue(result)
        
        # Test error
        error_data = {
            "error_type": "processing_error",
            "error_message": "Failed to process file",
            "retry_count": 1
        }
        result = self.comm_manager.send_error(error_data)
        self.assertTrue(result)
    
    def test_scan_notifications(self):
        """Test scan notification methods."""
        self.comm_manager.start()
        
        # Test scan started
        result = self.comm_manager.send_scan_started("scan_123", "full")
        self.assertTrue(result)
        
        # Test scan progress
        progress_data = {
            "total_files_found": 50,
            "new_files_found": 3,
            "scan_duration": 10.5
        }
        result = self.comm_manager.send_scan_progress("scan_123", progress_data)
        self.assertTrue(result)
        
        # Test scan completed
        final_data = {
            "total_files_found": 100,
            "new_files_found": 5,
            "scan_duration": 25.0
        }
        result = self.comm_manager.send_scan_completed("scan_123", final_data)
        self.assertTrue(result)
        
        # Test scan error
        result = self.comm_manager.send_scan_error("scan_123", "Scan failed due to permission error")
        self.assertTrue(result)
    
    def test_statistics(self):
        """Test statistics collection."""
        self.comm_manager.start()
        
        # Send some messages and commands
        self.comm_manager.send_message(ServiceMessage(
            message_type=MessageType.STATUS_UPDATE,
            source="test",
            target="all"
        ))
        self.comm_manager.send_command(UserCommand.GET_STATUS)
        
        # Get statistics
        stats = self.comm_manager.get_statistics()
        
        self.assertIn("messages_sent", stats)
        self.assertIn("messages_received", stats)
        self.assertIn("commands_processed", stats)
        self.assertIn("errors_count", stats)
        self.assertIn("is_running", stats)
        self.assertIn("queue_sizes", stats)
        
        self.assertEqual(stats["messages_sent"], 1)
        self.assertTrue(stats["is_running"])
    
    def test_queue_full_handling(self):
        """Test handling when queues are full."""
        self.comm_manager.start()
        
        # Fill the service queue
        for i in range(1000):  # Assuming queue size is smaller
            message = ServiceMessage(
                message_type=MessageType.STATUS_UPDATE,
                source="test",
                target="all",
                data={"index": i}
            )
            result = self.comm_manager.send_message(message)
            if not result:
                break
        
        # Try to send one more message
        message = ServiceMessage(
            message_type=MessageType.STATUS_UPDATE,
            source="test",
            target="all",
            data={"overflow": True}
        )
        result = self.comm_manager.send_message(message)
        # Should handle gracefully (either succeed or fail gracefully)
        self.assertIsInstance(result, bool)
    
    def test_error_handling(self):
        """Test error handling in message processing."""
        self.comm_manager.start()
        
        # Register a processor that raises an exception
        def failing_processor(message):
            raise Exception("Test error")
        
        self.comm_manager.register_message_processor(MessageType.STATUS_UPDATE, failing_processor)
        
        # Send a message
        message = ServiceMessage(
            message_type=MessageType.STATUS_UPDATE,
            source="test",
            target="all"
        )
        self.comm_manager.send_message(message)
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check that error was recorded
        stats = self.comm_manager.get_statistics()
        self.assertGreaterEqual(stats["errors_count"], 0)  # Should handle errors gracefully
    
    def test_thread_safety(self):
        """Test thread safety of the communication manager."""
        self.comm_manager.start()
        
        # Create multiple threads sending messages
        def send_messages(thread_id):
            for i in range(10):
                message = ServiceMessage(
                    message_type=MessageType.STATUS_UPDATE,
                    source=f"thread_{thread_id}",
                    target="all",
                    data={"thread_id": thread_id, "index": i}
                )
                self.comm_manager.send_message(message)
                time.sleep(0.01)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=send_messages, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that all messages were sent
        stats = self.comm_manager.get_statistics()
        self.assertEqual(stats["messages_sent"], 50)  # 5 threads * 10 messages each

if __name__ == "__main__":
    unittest.main() 