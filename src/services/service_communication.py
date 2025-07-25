"""
Service-GUI Communication System

This module provides a communication bridge between the background service
and the GUI, enabling real-time status updates, progress tracking, and
user control.
"""

import threading
import queue
import time
import json
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from services.background_service import ServiceState, ServiceStatus
from services.file_tracker import ProcessingStatus, OperationType
from logging_system.subtitle_logger import SubtitleLogger


class MessageType(Enum):
    """Types of messages for service-GUI communication."""
    STATUS_UPDATE = "status_update"
    PROGRESS_UPDATE = "progress_update"
    FILE_PROCESSED = "file_processed"
    FILE_FAILED = "file_failed"
    SCAN_STARTED = "scan_started"
    SCAN_COMPLETED = "scan_completed"
    ERROR_OCCURRED = "error_occurred"
    SERVICE_STATE_CHANGE = "service_state_change"
    STATISTICS_UPDATE = "statistics_update"
    CONFIGURATION_UPDATE = "configuration_update"
    USER_COMMAND = "user_command"
    COMMAND_RESPONSE = "command_response"


class UserCommand(Enum):
    """User commands that can be sent to the service."""
    START_SERVICE = "start_service"
    STOP_SERVICE = "stop_service"
    PAUSE_SERVICE = "pause_service"
    RESUME_SERVICE = "resume_service"
    RESTART_SERVICE = "restart_service"
    GET_STATUS = "get_status"
    GET_STATISTICS = "get_statistics"
    UPDATE_CONFIG = "update_config"
    FORCE_SCAN = "force_scan"
    CLEANUP_DATABASE = "cleanup_database"


@dataclass
class ServiceMessage:
    """Base message structure for service-GUI communication."""
    message_type: MessageType
    timestamp: float
    data: Dict[str, Any]
    message_id: Optional[str] = None


@dataclass
class StatusUpdateMessage:
    """Status update message with service status information."""
    message_type: MessageType
    timestamp: float
    data: Dict[str, Any]
    service_status: ServiceStatus
    message_id: Optional[str] = None


@dataclass
class ProgressUpdateMessage:
    """Progress update message for file processing."""
    message_type: MessageType
    timestamp: float
    data: Dict[str, Any]
    current_file: str
    total_files: int
    processed_files: int
    failed_files: int
    current_operation: str
    progress_percentage: float
    message_id: Optional[str] = None


@dataclass
class FileProcessedMessage:
    """Message when a file has been processed."""
    message_type: MessageType
    timestamp: float
    data: Dict[str, Any]
    file_path: str
    processing_status: ProcessingStatus
    processing_duration: float
    subtitle_operations: List[Dict[str, Any]]
    error_message: Optional[str] = None
    message_id: Optional[str] = None


@dataclass
class ScanSessionMessage:
    """Message for scan session updates."""
    message_type: MessageType
    timestamp: float
    data: Dict[str, Any]
    session_id: int
    directories_scanned: List[str]
    files_found: int
    files_processed: int
    files_skipped: int
    files_failed: int
    scan_duration: float
    message_id: Optional[str] = None


@dataclass
class UserCommandMessage:
    """Message for user commands."""
    message_type: MessageType
    timestamp: float
    data: Dict[str, Any]
    command: UserCommand
    parameters: Dict[str, Any]
    message_id: Optional[str] = None


@dataclass
class CommandResponseMessage:
    """Response to user commands."""
    message_type: MessageType
    timestamp: float
    data: Dict[str, Any]
    original_command: UserCommand
    success: bool
    response_data: Dict[str, Any]
    error_message: Optional[str] = None
    message_id: Optional[str] = None


class ServiceCommunicationManager:
    """
    Manages communication between background service and GUI.
    
    Provides a thread-safe message passing system with callbacks
    for real-time updates and user control.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the communication manager.
        
        Args:
            config: Configuration dictionary for logging and other settings.
        """
        self.config = config or {}
        self.logger = SubtitleLogger(self.config)
        
        # Message queues
        self._gui_to_service_queue = queue.Queue()
        self._service_to_gui_queue = queue.Queue()
        
        # Callback registries
        self._status_callbacks: List[Callable[[ServiceStatus], None]] = []
        self._progress_callbacks: List[Callable[[ProgressUpdateMessage], None]] = []
        self._file_callbacks: List[Callable[[FileProcessedMessage], None]] = []
        self._scan_callbacks: List[Callable[[ScanSessionMessage], None]] = []
        self._error_callbacks: List[Callable[[ServiceMessage], None]] = []
        self._command_callbacks: List[Callable[[UserCommandMessage], Callable[[bool, Dict[str, Any], Optional[str]], None]]] = []
        
        # Communication threads
        self._gui_thread: Optional[threading.Thread] = None
        self._service_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Message ID counter
        self._message_id_counter = 0
        
        self.logger.info("Service communication manager initialized")
    
    def start(self) -> bool:
        """
        Start the communication manager.
        
        Returns:
            True if started successfully, False otherwise
        """
        try:
            with self._lock:
                if self._gui_thread is not None and self._gui_thread.is_alive():
                    self.logger.warning("Communication manager already running")
                    return True
                
                self.logger.info("Starting service communication manager...")
                self._stop_event.clear()
                
                # Start GUI message processing thread
                self._gui_thread = threading.Thread(
                    target=self._gui_message_processor,
                    name="ServiceComm-GUI",
                    daemon=True
                )
                self._gui_thread.start()
                
                # Start service message processing thread
                self._service_thread = threading.Thread(
                    target=self._service_message_processor,
                    name="ServiceComm-Service",
                    daemon=True
                )
                self._service_thread.start()
                
                self.logger.info("Service communication manager started successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to start communication manager: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the communication manager.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            with self._lock:
                self.logger.info("Stopping service communication manager...")
                self._stop_event.set()
                
                # Wait for threads to finish
                if self._gui_thread and self._gui_thread.is_alive():
                    self._gui_thread.join(timeout=5.0)
                
                if self._service_thread and self._service_thread.is_alive():
                    self._service_thread.join(timeout=5.0)
                
                self.logger.info("Service communication manager stopped successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Error stopping communication manager: {e}")
            return False
    
    def _generate_message_id(self) -> str:
        """Generate a unique message ID."""
        with self._lock:
            self._message_id_counter += 1
            return f"msg_{self._message_id_counter}_{int(time.time())}"
    
    def send_to_gui(self, message: ServiceMessage) -> bool:
        """
        Send a message from service to GUI.
        
        Args:
            message: Message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if not message.message_id:
                message.message_id = self._generate_message_id()
            
            self._service_to_gui_queue.put(message, timeout=1.0)
            self.logger.debug(f"Sent message to GUI: {message.message_type.value}")
            return True
            
        except queue.Full:
            self.logger.warning("GUI message queue full, dropping message")
            return False
        except Exception as e:
            self.logger.error(f"Error sending message to GUI: {e}")
            return False
    
    def send_to_service(self, message: ServiceMessage) -> bool:
        """
        Send a message from GUI to service.
        
        Args:
            message: Message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if not message.message_id:
                message.message_id = self._generate_message_id()
            
            self._gui_to_service_queue.put(message, timeout=1.0)
            self.logger.debug(f"Sent message to service: {message.message_type.value}")
            return True
            
        except queue.Full:
            self.logger.warning("Service message queue full, dropping message")
            return False
        except Exception as e:
            self.logger.error(f"Error sending message to service: {e}")
            return False
    
    def _gui_message_processor(self) -> None:
        """Process messages from service to GUI."""
        self.logger.info("GUI message processor started")
        
        try:
            while not self._stop_event.is_set():
                try:
                    # Get message with timeout
                    message = self._service_to_gui_queue.get(timeout=1.0)
                    
                    # Process message based on type
                    self._process_gui_message(message)
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Error processing GUI message: {e}")
                    
        except Exception as e:
            self.logger.error(f"GUI message processor error: {e}")
        finally:
            self.logger.info("GUI message processor stopped")
    
    def _service_message_processor(self) -> None:
        """Process messages from GUI to service."""
        self.logger.info("Service message processor started")
        
        try:
            while not self._stop_event.is_set():
                try:
                    # Get message with timeout
                    message = self._gui_to_service_queue.get(timeout=1.0)
                    
                    # Process message based on type
                    self._process_service_message(message)
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Error processing service message: {e}")
                    
        except Exception as e:
            self.logger.error(f"Service message processor error: {e}")
        finally:
            self.logger.info("Service message processor stopped")
    
    def _process_gui_message(self, message: ServiceMessage) -> None:
        """Process a message received by the GUI."""
        try:
            if message.message_type == MessageType.STATUS_UPDATE:
                # Extract status data
                status_data = message.data.get('status', {})
                service_status = ServiceStatus(
                    state=ServiceState(status_data.get('state', 'stopped')),
                    start_time=datetime.fromisoformat(status_data['start_time']) if status_data.get('start_time') else None,
                    last_scan_time=datetime.fromisoformat(status_data['last_scan_time']) if status_data.get('last_scan_time') else None,
                    files_processed=status_data.get('files_processed', 0),
                    files_failed=status_data.get('files_failed', 0),
                    current_operation=status_data.get('current_operation'),
                    error_message=status_data.get('error_message'),
                    uptime_seconds=status_data.get('uptime_seconds', 0),
                    last_error_time=datetime.fromisoformat(status_data['last_error_time']) if status_data.get('last_error_time') else None,
                    consecutive_errors=status_data.get('consecutive_errors', 0),
                    health_score=status_data.get('health_score', 100.0)
                )
                
                # Notify status callbacks
                for callback in self._status_callbacks:
                    try:
                        callback(service_status)
                    except Exception as e:
                        self.logger.error(f"Error in status callback: {e}")
            
            elif message.message_type == MessageType.PROGRESS_UPDATE:
                # Create progress update message
                progress_msg = ProgressUpdateMessage(
                    message_type=message.message_type,
                    timestamp=message.timestamp,
                    data=message.data,
                    message_id=message.message_id,
                    current_file=message.data.get('current_file', ''),
                    total_files=message.data.get('total_files', 0),
                    processed_files=message.data.get('processed_files', 0),
                    failed_files=message.data.get('failed_files', 0),
                    current_operation=message.data.get('current_operation', ''),
                    progress_percentage=message.data.get('progress_percentage', 0.0)
                )
                
                # Notify progress callbacks
                for callback in self._progress_callbacks:
                    try:
                        callback(progress_msg)
                    except Exception as e:
                        self.logger.error(f"Error in progress callback: {e}")
            
            elif message.message_type == MessageType.FILE_PROCESSED:
                # Create file processed message
                file_msg = FileProcessedMessage(
                    message_type=message.message_type,
                    timestamp=message.timestamp,
                    data=message.data,
                    message_id=message.message_id,
                    file_path=message.data.get('file_path', ''),
                    processing_status=ProcessingStatus(message.data.get('processing_status', 'failed')),
                    processing_duration=message.data.get('processing_duration', 0.0),
                    subtitle_operations=message.data.get('subtitle_operations', []),
                    error_message=message.data.get('error_message')
                )
                
                # Notify file callbacks
                for callback in self._file_callbacks:
                    try:
                        callback(file_msg)
                    except Exception as e:
                        self.logger.error(f"Error in file callback: {e}")
            
            elif message.message_type == MessageType.SCAN_STARTED or message.message_type == MessageType.SCAN_COMPLETED:
                # Create scan session message
                scan_msg = ScanSessionMessage(
                    message_type=message.message_type,
                    timestamp=message.timestamp,
                    data=message.data,
                    message_id=message.message_id,
                    session_id=message.data.get('session_id', 0),
                    directories_scanned=message.data.get('directories_scanned', []),
                    files_found=message.data.get('files_found', 0),
                    files_processed=message.data.get('files_processed', 0),
                    files_skipped=message.data.get('files_skipped', 0),
                    files_failed=message.data.get('files_failed', 0),
                    scan_duration=message.data.get('scan_duration', 0.0)
                )
                
                # Notify scan callbacks
                for callback in self._scan_callbacks:
                    try:
                        callback(scan_msg)
                    except Exception as e:
                        self.logger.error(f"Error in scan callback: {e}")
            
            elif message.message_type == MessageType.ERROR_OCCURRED:
                # Notify error callbacks
                for callback in self._error_callbacks:
                    try:
                        callback(message)
                    except Exception as e:
                        self.logger.error(f"Error in error callback: {e}")
            
        except Exception as e:
            self.logger.error(f"Error processing GUI message: {e}")
    
    def _process_service_message(self, message: ServiceMessage) -> None:
        """Process a message received by the service."""
        try:
            if message.message_type == MessageType.USER_COMMAND:
                # Extract command data
                command_data = message.data.get('command', {})
                command = UserCommand(command_data.get('type', ''))
                parameters = command_data.get('parameters', {})
                
                # Create user command message
                cmd_msg = UserCommandMessage(
                    message_type=message.message_type,
                    timestamp=message.timestamp,
                    data=message.data,
                    message_id=message.message_id,
                    command=command,
                    parameters=parameters
                )
                
                # Notify command callbacks and get response callback
                for callback in self._command_callbacks:
                    try:
                        response_callback = callback(cmd_msg)
                        if response_callback:
                            # Store response callback for later use
                            # In a real implementation, you'd want to track this properly
                            pass
                    except Exception as e:
                        self.logger.error(f"Error in command callback: {e}")
            
        except Exception as e:
            self.logger.error(f"Error processing service message: {e}")
    
    # Callback registration methods
    def register_status_callback(self, callback: Callable[[ServiceStatus], None]) -> None:
        """Register a callback for status updates."""
        with self._lock:
            if callback not in self._status_callbacks:
                self._status_callbacks.append(callback)
    
    def unregister_status_callback(self, callback: Callable[[ServiceStatus], None]) -> None:
        """Unregister a status callback."""
        with self._lock:
            if callback in self._status_callbacks:
                self._status_callbacks.remove(callback)
    
    def register_progress_callback(self, callback: Callable[[ProgressUpdateMessage], None]) -> None:
        """Register a callback for progress updates."""
        with self._lock:
            if callback not in self._progress_callbacks:
                self._progress_callbacks.append(callback)
    
    def unregister_progress_callback(self, callback: Callable[[ProgressUpdateMessage], None]) -> None:
        """Unregister a progress callback."""
        with self._lock:
            if callback in self._progress_callbacks:
                self._progress_callbacks.remove(callback)
    
    def register_file_callback(self, callback: Callable[[FileProcessedMessage], None]) -> None:
        """Register a callback for file processing updates."""
        with self._lock:
            if callback not in self._file_callbacks:
                self._file_callbacks.append(callback)
    
    def unregister_file_callback(self, callback: Callable[[FileProcessedMessage], None]) -> None:
        """Unregister a file callback."""
        with self._lock:
            if callback in self._file_callbacks:
                self._file_callbacks.remove(callback)
    
    def register_scan_callback(self, callback: Callable[[ScanSessionMessage], None]) -> None:
        """Register a callback for scan session updates."""
        with self._lock:
            if callback not in self._scan_callbacks:
                self._scan_callbacks.append(callback)
    
    def unregister_scan_callback(self, callback: Callable[[ScanSessionMessage], None]) -> None:
        """Unregister a scan callback."""
        with self._lock:
            if callback in self._scan_callbacks:
                self._scan_callbacks.remove(callback)
    
    def register_error_callback(self, callback: Callable[[ServiceMessage], None]) -> None:
        """Register a callback for error messages."""
        with self._lock:
            if callback not in self._error_callbacks:
                self._error_callbacks.append(callback)
    
    def unregister_error_callback(self, callback: Callable[[ServiceMessage], None]) -> None:
        """Unregister an error callback."""
        with self._lock:
            if callback in self._error_callbacks:
                self._error_callbacks.remove(callback)
    
    def register_command_callback(self, callback: Callable[[UserCommandMessage], Callable[[bool, Dict[str, Any], Optional[str]], None]]) -> None:
        """Register a callback for user commands."""
        with self._lock:
            if callback not in self._command_callbacks:
                self._command_callbacks.append(callback)
    
    def unregister_command_callback(self, callback: Callable[[UserCommandMessage], Callable[[bool, Dict[str, Any], Optional[str]], None]]) -> None:
        """Unregister a command callback."""
        with self._lock:
            if callback in self._command_callbacks:
                self._command_callbacks.remove(callback)
    
    # Convenience methods for sending common messages
    def send_status_update(self, service_status: ServiceStatus) -> bool:
        """Send a status update to the GUI."""
        message = ServiceMessage(
            message_type=MessageType.STATUS_UPDATE,
            timestamp=time.time(),
            data={'status': asdict(service_status)}
        )
        return self.send_to_gui(message)
    
    def send_progress_update(self, current_file: str, total_files: int, processed_files: int,
                           failed_files: int, current_operation: str) -> bool:
        """Send a progress update to the GUI."""
        progress_percentage = (processed_files / total_files * 100) if total_files > 0 else 0.0
        
        message = ServiceMessage(
            message_type=MessageType.PROGRESS_UPDATE,
            timestamp=time.time(),
            data={
                'current_file': current_file,
                'total_files': total_files,
                'processed_files': processed_files,
                'failed_files': failed_files,
                'current_operation': current_operation,
                'progress_percentage': progress_percentage
            }
        )
        return self.send_to_gui(message)
    
    def send_file_processed(self, file_path: str, processing_status: ProcessingStatus,
                          processing_duration: float, subtitle_operations: List[Dict[str, Any]],
                          error_message: Optional[str] = None) -> bool:
        """Send a file processed notification to the GUI."""
        message = ServiceMessage(
            message_type=MessageType.FILE_PROCESSED,
            timestamp=time.time(),
            data={
                'file_path': file_path,
                'processing_status': processing_status.value,
                'processing_duration': processing_duration,
                'subtitle_operations': subtitle_operations,
                'error_message': error_message
            }
        )
        return self.send_to_gui(message)
    
    def send_scan_session(self, session_id: int, directories_scanned: List[str],
                         files_found: int, files_processed: int, files_skipped: int,
                         files_failed: int, scan_duration: float) -> bool:
        """Send a scan session update to the GUI."""
        message = ServiceMessage(
            message_type=MessageType.SCAN_COMPLETED,
            timestamp=time.time(),
            data={
                'session_id': session_id,
                'directories_scanned': directories_scanned,
                'files_found': files_found,
                'files_processed': files_processed,
                'files_skipped': files_skipped,
                'files_failed': files_failed,
                'scan_duration': scan_duration
            }
        )
        return self.send_to_gui(message)
    
    def send_user_command(self, command: UserCommand, parameters: Dict[str, Any] = None) -> bool:
        """Send a user command to the service."""
        if parameters is None:
            parameters = {}
        
        message = ServiceMessage(
            message_type=MessageType.USER_COMMAND,
            timestamp=time.time(),
            data={
                'command': {
                    'type': command.value,
                    'parameters': parameters
                }
            }
        )
        return self.send_to_service(message)
    
    def send_command_response(self, original_command: UserCommand, success: bool,
                            response_data: Dict[str, Any] = None, error_message: Optional[str] = None) -> bool:
        """Send a response to a user command."""
        if response_data is None:
            response_data = {}
        
        message = ServiceMessage(
            message_type=MessageType.COMMAND_RESPONSE,
            timestamp=time.time(),
            data={
                'original_command': original_command.value,
                'success': success,
                'response_data': response_data,
                'error_message': error_message
            }
        )
        return self.send_to_gui(message) 