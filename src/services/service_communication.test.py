"""
Unit tests for ServiceCommunicationManager class.
"""

import unittest
import time
import threading
from unittest.mock import Mock, patch
from pathlib import Path
from datetime import datetime

from services.service_communication import (
    ServiceCommunicationManager, ServiceMessage, MessageType, UserCommand,
    StatusUpdateMessage, ProgressUpdateMessage, FileProcessedMessage,
    ScanSessionMessage, UserCommandMessage
)
from services.background_service import ServiceState, ServiceStatus
from services.file_tracker import ProcessingStatus, OperationType


class TestServiceCommunicationManager(unittest.TestCase):
    """Test cases for ServiceCommunicationManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock configuration
        self.mock_config = {
            'logging': {
                'level': 'DEBUG',
                'file': '/tmp/test.log',
                'console_output': False
            }
        }
        
        # Create communication manager
        self.comm_manager = ServiceCommunicationManager(self.mock_config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Stop communication manager if running
        if self.comm_manager:
            self.comm_manager.stop()
    
    def test_initialization(self):
        """Test communication manager initialization."""
        self.assertIsNotNone(self.comm_manager)
        self.assertEqual(len(self.comm_manager._status_callbacks), 0)
        self.assertEqual(len(self.comm_manager._progress_callbacks), 0)
        self.assertEqual(len(self.comm_manager._file_callbacks), 0)
    
    def test_start_stop(self):
        """Test starting and stopping the communication manager."""
        # Start manager
        result = self.comm_manager.start()
        self.assertTrue(result)
        self.assertIsNotNone(self.comm_manager._gui_thread)
        self.assertIsNotNone(self.comm_manager._service_thread)
        self.assertTrue(self.comm_manager._gui_thread.is_alive())
        self.assertTrue(self.comm_manager._service_thread.is_alive())
        
        # Stop manager
        result = self.comm_manager.stop()
        self.assertTrue(result)
        
        # Give threads time to stop
        time.sleep(0.1)
        
        # Check threads are stopped
        self.assertFalse(self.comm_manager._gui_thread.is_alive())
        self.assertFalse(self.comm_manager._service_thread.is_alive())
    
    def test_message_id_generation(self):
        """Test unique message ID generation."""
        id1 = self.comm_manager._generate_message_id()
        id2 = self.comm_manager._generate_message_id()
        
        self.assertIsInstance(id1, str)
        self.assertIsInstance(id2, str)
        self.assertNotEqual(id1, id2)
        self.assertTrue(id1.startswith("msg_"))
        self.assertTrue(id2.startswith("msg_"))
    
    def test_send_to_gui(self):
        """Test sending messages to GUI."""
        # Start manager
        self.comm_manager.start()
        
        # Create test message
        message = ServiceMessage(
            message_type=MessageType.STATUS_UPDATE,
            timestamp=time.time(),
            data={'test': 'data'}
        )
        
        # Send message
        result = self.comm_manager.send_to_gui(message)
        self.assertTrue(result)
        self.assertIsNotNone(message.message_id)
        
        # Check queue size
        self.assertEqual(self.comm_manager._service_to_gui_queue.qsize(), 1)
    
    def test_send_to_service(self):
        """Test sending messages to service."""
        # Start manager
        self.comm_manager.start()
        
        # Create test message
        message = ServiceMessage(
            message_type=MessageType.USER_COMMAND,
            timestamp=time.time(),
            data={'test': 'data'}
        )
        
        # Send message
        result = self.comm_manager.send_to_service(message)
        self.assertTrue(result)
        self.assertIsNotNone(message.message_id)
        
        # Check queue size
        self.assertEqual(self.comm_manager._gui_to_service_queue.qsize(), 1)
    
    def test_status_callback_registration(self):
        """Test status callback registration and unregistration."""
        callback_called = False
        received_status = None
        
        def status_callback(status: ServiceStatus):
            nonlocal callback_called, received_status
            callback_called = True
            received_status = status
        
        # Register callback
        self.comm_manager.register_status_callback(status_callback)
        self.assertEqual(len(self.comm_manager._status_callbacks), 1)
        
        # Unregister callback
        self.comm_manager.unregister_status_callback(status_callback)
        self.assertEqual(len(self.comm_manager._status_callbacks), 0)
    
    def test_progress_callback_registration(self):
        """Test progress callback registration and unregistration."""
        callback_called = False
        received_progress = None
        
        def progress_callback(progress: ProgressUpdateMessage):
            nonlocal callback_called, received_progress
            callback_called = True
            received_progress = progress
        
        # Register callback
        self.comm_manager.register_progress_callback(progress_callback)
        self.assertEqual(len(self.comm_manager._progress_callbacks), 1)
        
        # Unregister callback
        self.comm_manager.unregister_progress_callback(progress_callback)
        self.assertEqual(len(self.comm_manager._progress_callbacks), 0)
    
    def test_file_callback_registration(self):
        """Test file callback registration and unregistration."""
        callback_called = False
        received_file = None
        
        def file_callback(file_msg: FileProcessedMessage):
            nonlocal callback_called, received_file
            callback_called = True
            received_file = file_msg
        
        # Register callback
        self.comm_manager.register_file_callback(file_callback)
        self.assertEqual(len(self.comm_manager._file_callbacks), 1)
        
        # Unregister callback
        self.comm_manager.unregister_file_callback(file_callback)
        self.assertEqual(len(self.comm_manager._file_callbacks), 0)
    
    def test_scan_callback_registration(self):
        """Test scan callback registration and unregistration."""
        callback_called = False
        received_scan = None
        
        def scan_callback(scan_msg: ScanSessionMessage):
            nonlocal callback_called, received_scan
            callback_called = True
            received_scan = scan_msg
        
        # Register callback
        self.comm_manager.register_scan_callback(scan_callback)
        self.assertEqual(len(self.comm_manager._scan_callbacks), 1)
        
        # Unregister callback
        self.comm_manager.unregister_scan_callback(scan_callback)
        self.assertEqual(len(self.comm_manager._scan_callbacks), 0)
    
    def test_error_callback_registration(self):
        """Test error callback registration and unregistration."""
        callback_called = False
        received_error = None
        
        def error_callback(error_msg: ServiceMessage):
            nonlocal callback_called, received_error
            callback_called = True
            received_error = error_msg
        
        # Register callback
        self.comm_manager.register_error_callback(error_callback)
        self.assertEqual(len(self.comm_manager._error_callbacks), 1)
        
        # Unregister callback
        self.comm_manager.unregister_error_callback(error_callback)
        self.assertEqual(len(self.comm_manager._error_callbacks), 0)
    
    def test_command_callback_registration(self):
        """Test command callback registration and unregistration."""
        callback_called = False
        received_command = None
        
        def command_callback(cmd_msg: UserCommandMessage):
            nonlocal callback_called, received_command
            callback_called = True
            received_command = cmd_msg
            
            def response_callback(success: bool, data: dict, error: str = None):
                pass
            
            return response_callback
        
        # Register callback
        self.comm_manager.register_command_callback(command_callback)
        self.assertEqual(len(self.comm_manager._command_callbacks), 1)
        
        # Unregister callback
        self.comm_manager.unregister_command_callback(command_callback)
        self.assertEqual(len(self.comm_manager._command_callbacks), 0)
    
    def test_convenience_methods(self):
        """Test convenience methods for sending common messages."""
        # Start manager
        self.comm_manager.start()
        
        # Test send_status_update
        service_status = ServiceStatus(state=ServiceState.RUNNING)
        result = self.comm_manager.send_status_update(service_status)
        self.assertTrue(result)
        
        # Test send_progress_update
        result = self.comm_manager.send_progress_update(
            current_file="test.mkv",
            total_files=10,
            processed_files=5,
            failed_files=1,
            current_operation="Processing"
        )
        self.assertTrue(result)
        
        # Test send_file_processed
        result = self.comm_manager.send_file_processed(
            file_path="/path/to/test.mkv",
            processing_status=ProcessingStatus.SUCCESS,
            processing_duration=5.0,
            subtitle_operations=[{"type": "download", "status": "success"}]
        )
        self.assertTrue(result)
        
        # Test send_scan_session
        result = self.comm_manager.send_scan_session(
            session_id=1,
            directories_scanned=["/test/dir"],
            files_found=10,
            files_processed=5,
            files_skipped=3,
            files_failed=2,
            scan_duration=10.0
        )
        self.assertTrue(result)
        
        # Test send_user_command
        result = self.comm_manager.send_user_command(
            command=UserCommand.START_SERVICE,
            parameters={"force": True}
        )
        self.assertTrue(result)
        
        # Test send_command_response
        result = self.comm_manager.send_command_response(
            original_command=UserCommand.START_SERVICE,
            success=True,
            response_data={"status": "started"},
            error_message=None
        )
        self.assertTrue(result)
    
    def test_message_processing(self):
        """Test message processing with callbacks."""
        # Start manager
        self.comm_manager.start()
        
        # Set up callbacks
        status_received = False
        progress_received = False
        file_received = False
        scan_received = False
        error_received = False
        command_received = False
        
        def status_callback(status: ServiceStatus):
            nonlocal status_received
            status_received = True
        
        def progress_callback(progress: ProgressUpdateMessage):
            nonlocal progress_received
            progress_received = True
        
        def file_callback(file_msg: FileProcessedMessage):
            nonlocal file_received
            file_received = True
        
        def scan_callback(scan_msg: ScanSessionMessage):
            nonlocal scan_received
            scan_received = True
        
        def error_callback(error_msg: ServiceMessage):
            nonlocal error_received
            error_received = True
        
        def command_callback(cmd_msg: UserCommandMessage):
            nonlocal command_received
            command_received = True
            return lambda success, data, error: None
        
        # Register callbacks
        self.comm_manager.register_status_callback(status_callback)
        self.comm_manager.register_progress_callback(progress_callback)
        self.comm_manager.register_file_callback(file_callback)
        self.comm_manager.register_scan_callback(scan_callback)
        self.comm_manager.register_error_callback(error_callback)
        self.comm_manager.register_command_callback(command_callback)
        
        # Send test messages
        self.comm_manager.send_status_update(ServiceStatus(state=ServiceState.RUNNING))
        self.comm_manager.send_progress_update("test.mkv", 10, 5, 1, "Processing")
        self.comm_manager.send_file_processed("/test.mkv", ProcessingStatus.SUCCESS, 5.0, [])
        self.comm_manager.send_scan_session(1, ["/test"], 10, 5, 3, 2, 10.0)
        self.comm_manager.send_user_command(UserCommand.START_SERVICE)
        
        # Wait for message processing
        time.sleep(0.2)
        
        # Check callbacks were called
        self.assertTrue(status_received)
        self.assertTrue(progress_received)
        self.assertTrue(file_received)
        self.assertTrue(scan_received)
        self.assertTrue(command_received)
    
    def test_concurrent_message_sending(self):
        """Test concurrent message sending."""
        # Start manager
        self.comm_manager.start()
        
        # Create multiple threads sending messages
        def send_messages():
            for i in range(10):
                message = ServiceMessage(
                    message_type=MessageType.STATUS_UPDATE,
                    timestamp=time.time(),
                    data={'thread_id': i}
                )
                self.comm_manager.send_to_gui(message)
                time.sleep(0.01)
        
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=send_messages)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check all messages were sent
        total_messages = (self.comm_manager._service_to_gui_queue.qsize() + 
                         self.comm_manager._gui_to_service_queue.qsize())
        self.assertEqual(total_messages, 50)  # 5 threads * 10 messages each
    
    def test_queue_overflow_handling(self):
        """Test handling of queue overflow."""
        # Start manager
        self.comm_manager.start()
        
        # Fill up the queue
        for i in range(1000):  # More than queue capacity
            message = ServiceMessage(
                message_type=MessageType.STATUS_UPDATE,
                timestamp=time.time(),
                data={'index': i}
            )
            result = self.comm_manager.send_to_gui(message)
            if not result:
                break  # Queue is full
        
        # Should handle overflow gracefully
        self.assertIsInstance(result, bool)
    
    def test_message_id_assignment(self):
        """Test automatic message ID assignment."""
        # Start manager
        self.comm_manager.start()
        
        # Create message without ID
        message = ServiceMessage(
            message_type=MessageType.STATUS_UPDATE,
            timestamp=time.time(),
            data={'test': 'data'},
            message_id=None
        )
        
        # Send message
        result = self.comm_manager.send_to_gui(message)
        self.assertTrue(result)
        self.assertIsNotNone(message.message_id)
        self.assertTrue(message.message_id.startswith("msg_"))
    
    def test_error_handling(self):
        """Test error handling in message processing."""
        # Start manager
        self.comm_manager.start()
        
        # Create callback that raises exception
        def error_callback(status: ServiceStatus):
            raise Exception("Test error")
        
        # Register callback
        self.comm_manager.register_status_callback(error_callback)
        
        # Send message (should not crash)
        result = self.comm_manager.send_status_update(ServiceStatus(state=ServiceState.RUNNING))
        self.assertTrue(result)
        
        # Wait for processing
        time.sleep(0.1)
        
        # Manager should still be running
        self.assertTrue(self.comm_manager._gui_thread.is_alive())
        self.assertTrue(self.comm_manager._service_thread.is_alive())


if __name__ == '__main__':
    unittest.main() 