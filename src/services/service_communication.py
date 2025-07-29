"""
Service Communication System for Background Service.
Provides communication infrastructure for service components, enabling real-time status updates, progress tracking, and
command processing between different service modules.
"""

import queue
import threading
import time
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime

from logging_system.subtitle_logger import SubtitleLogger

class MessageType(Enum):
    """Types of messages for service communication."""
    STATUS_UPDATE = "status_update"
    PROGRESS_UPDATE = "progress_update"
    FILE_PROCESSED = "file_processed"
    SCAN_UPDATE = "scan_update"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    COMMAND = "command"
    HEALTH_UPDATE = "health_update"
    STATISTICS_UPDATE = "statistics_update"

class UserCommand(Enum):
    """User commands that can be sent to the service."""
    START_SERVICE = "start_service"
    STOP_SERVICE = "stop_service"
    RESTART_SERVICE = "restart_service"
    PAUSE_SERVICE = "pause_service"
    RESUME_SERVICE = "resume_service"
    SCAN_NOW = "scan_now"
    GET_STATUS = "get_status"
    GET_STATISTICS = "get_statistics"
    CLEAR_STATISTICS = "clear_statistics"
    UPDATE_CONFIG = "update_config"

@dataclass
class ServiceMessage:
    """Base message structure for service communication."""
    message_type: MessageType
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: f"msg_{int(time.time() * 1000)}")
    source: str = ""
    target: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # 0=low, 1=normal, 2=high, 3=urgent

@dataclass
class StatusMessage(ServiceMessage):
    """Status update message."""
    service_status: str = ""
    service_state: str = ""
    uptime_seconds: int = 0
    last_scan: Optional[str] = None
    is_scanning: bool = False
    is_processing: bool = False

@dataclass
class ProgressMessage(ServiceMessage):
    """Progress update message."""
    current_file: str = ""
    progress_percent: float = 0.0
    current_step: str = ""
    total_files: int = 0
    processed_files: int = 0
    remaining_files: int = 0

@dataclass
class FileProcessedMessage(ServiceMessage):
    """File processed notification message."""
    file_path: str = ""
    processing_result: str = ""
    processing_time: float = 0.0
    subtitle_found: bool = False
    subtitle_downloaded: bool = False
    subtitle_translated: bool = False
    error_message: Optional[str] = None

@dataclass
class ScanUpdateMessage(ServiceMessage):
    """Scan session update message."""
    scan_session_id: str = ""
    scan_type: str = ""  # "full", "incremental", "manual"
    total_files_found: int = 0
    new_files_found: int = 0
    modified_files_found: int = 0
    unchanged_files: int = 0
    scan_duration: float = 0.0
    scan_status: str = ""  # "running", "completed", "failed"
    directories: List[str] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    error_message: Optional[str] = None
    errors: List[str] = field(default_factory=list)

@dataclass
class ErrorMessage(ServiceMessage):
    """Error notification message."""
    error_type: str = ""
    error_message: str = ""
    error_details: Optional[str] = None
    stack_trace: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class CommandMessage(ServiceMessage):
    """Command message for service control."""
    command: UserCommand = UserCommand.GET_STATUS
    parameters: Dict[str, Any] = field(default_factory=dict)
    response_required: bool = True

class ServiceCommunicationManager:
    """
    Manages communication between background service components.
    Provides message passing, status updates, and command processing.
    """
    
    def __init__(self, config: Dict[str, Any], logger: Optional[SubtitleLogger] = None):
        """
        Initialize the communication manager.
        
        Args:
            config: Configuration dictionary
            logger: Logger instance
        """
        self.config = config
        self.logger = logger or SubtitleLogger(config)
        
        # Message queues
        self._service_queue = queue.Queue()
        self._command_queue = queue.Queue()
        
        # Message processors
        self._message_processors: Dict[MessageType, List[Callable]] = {}
        self._command_handlers: Dict[UserCommand, Callable] = {}
        
        # Communication state
        self._is_running = False
        self._service_thread: Optional[threading.Thread] = None
        self._command_thread: Optional[threading.Thread] = None
        
        # Statistics
        self._messages_sent = 0
        self._messages_received = 0
        self._commands_processed = 0
        self._errors_count = 0
        
        # Initialize
        self._setup_default_handlers()
    
    def start(self) -> None:
        """Start the communication manager."""
        if self._is_running:
            self.logger.warning("Communication manager already running")
            return
        
        self._is_running = True
        
        # Start service message processing thread
        self._service_thread = threading.Thread(
            target=self._service_message_processor,
            name="ServiceComm-Service",
            daemon=True
        )
        self._service_thread.start()
        
        # Start command processing thread
        self._command_thread = threading.Thread(
            target=self._command_processor,
            name="ServiceComm-Command",
            daemon=True
        )
        self._command_thread.start()
        
        self.logger.info("Service communication manager started")
    
    def stop(self) -> None:
        """Stop the communication manager."""
        if not self._is_running:
            return
        
        self._is_running = False
        
        # Stop service thread
        if self._service_thread and self._service_thread.is_alive():
            self._service_thread.join(timeout=5.0)
        
        # Stop command thread
        if self._command_thread and self._command_thread.is_alive():
            self._command_thread.join(timeout=5.0)
        
        self.logger.info("Service communication manager stopped")
    
    def send_message(self, message: ServiceMessage) -> bool:
        """
        Send a message to the service queue.
        
        Args:
            message: Message to send
            
        Returns:
            True if message was sent successfully
        """
        try:
            self._service_queue.put(message, timeout=1.0)
            self._messages_sent += 1
            self.logger.debug(f"Sent message: {message.message_type.value}")
            return True
        except queue.Full:
            self.logger.warning("Service message queue full, dropping message")
            return False
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            self._errors_count += 1
            return False
    
    def send_command(self, command: UserCommand, parameters: Dict[str, Any] = None) -> bool:
        """
        Send a command to the service.
        
        Args:
            command: Command to send
            parameters: Command parameters
            
        Returns:
            True if command was sent successfully
        """
        try:
            message = CommandMessage(
                message_type=MessageType.COMMAND,
                command=command,
                parameters=parameters or {},
                source="external",
                target="service"
            )
            self._command_queue.put(message, timeout=1.0)
            self.logger.debug(f"Sent command: {command.value}")
            return True
        except queue.Full:
            self.logger.warning("Command queue full, dropping command")
            return False
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            self._errors_count += 1
            return False
    
    def register_message_processor(self, message_type: MessageType, processor: Callable) -> None:
        """Register a message processor for a specific message type."""
        if message_type not in self._message_processors:
            self._message_processors[message_type] = []
        self._message_processors[message_type].append(processor)
        self.logger.debug(f"Registered processor for {message_type.value}")
    
    def register_command_handler(self, command: UserCommand, handler: Callable) -> None:
        """Register a command handler for a specific command."""
        self._command_handlers[command] = handler
        self.logger.debug(f"Registered handler for {command.value}")
    
    def _service_message_processor(self) -> None:
        """Process messages from service queue."""
        self.logger.info("Service message processor started")
        
        while self._is_running:
            try:
                message = self._service_queue.get(timeout=1.0)
                self._process_service_message(message)
                self._messages_received += 1
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing service message: {e}")
                self._errors_count += 1
        
        self.logger.info("Service message processor stopped")
    
    def _command_processor(self) -> None:
        """Process commands from command queue."""
        self.logger.info("Command processor started")
        
        while self._is_running:
            try:
                message = self._command_queue.get(timeout=1.0)
                self._process_command_message(message)
                self._commands_processed += 1
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing command: {e}")
                self._errors_count += 1
        
        self.logger.info("Command processor stopped")
    
    def _process_service_message(self, message: ServiceMessage) -> None:
        """Process a service message."""
        try:
            message_type = message.message_type
            
            if message_type in self._message_processors:
                for processor in self._message_processors[message_type]:
                    try:
                        processor(message)
                    except Exception as e:
                        self.logger.error(f"Error in message processor: {e}")
            else:
                self.logger.debug(f"No processors registered for {message_type.value}")
                
        except Exception as e:
            self.logger.error(f"Error processing service message: {e}")
            self._errors_count += 1
    
    def _process_command_message(self, message: CommandMessage) -> None:
        """Process a command message."""
        try:
            command = message.command
            
            if command in self._command_handlers:
                handler = self._command_handlers[command]
                try:
                    handler(message.parameters)
                    self.logger.info(f"Command executed: {command.value}")
                except Exception as e:
                    self.logger.error(f"Error executing command {command.value}: {e}")
                    self._errors_count += 1
            else:
                self.logger.warning(f"No handler registered for command: {command.value}")
                
        except Exception as e:
            self.logger.error(f"Error processing command message: {e}")
            self._errors_count += 1
    
    def _setup_default_handlers(self) -> None:
        """Setup default command handlers."""
        # Default handlers will be implemented by the service
        pass
    
    # Convenience methods for sending specific message types
    
    def send_status_update(self, status_data: Dict[str, Any]) -> bool:
        """Send a status update message."""
        message = StatusMessage(
            message_type=MessageType.STATUS_UPDATE,
            source="service",
            target="all",
            data=status_data,
            **status_data
        )
        return self.send_message(message)
    
    def send_progress_update(self, progress_data: Dict[str, Any]) -> bool:
        """Send a progress update message."""
        message = ProgressMessage(
            message_type=MessageType.PROGRESS_UPDATE,
            source="service",
            target="all",
            data=progress_data,
            **progress_data
        )
        return self.send_message(message)
    
    def send_file_processed(self, file_data: Dict[str, Any]) -> bool:
        """Send a file processed notification."""
        message = FileProcessedMessage(
            message_type=MessageType.FILE_PROCESSED,
            source="service",
            target="all",
            data=file_data,
            **file_data
        )
        return self.send_message(message)
    
    def send_scan_update(self, scan_data: Dict[str, Any]) -> bool:
        """Send a scan update message."""
        message = ScanUpdateMessage(
            message_type=MessageType.SCAN_UPDATE,
            source="service",
            target="all",
            data=scan_data,
            **scan_data
        )
        return self.send_message(message)
    
    def send_error(self, error_data: Dict[str, Any]) -> bool:
        """Send an error message."""
        message = ErrorMessage(
            message_type=MessageType.ERROR,
            source="service",
            target="all",
            data=error_data,
            **error_data
        )
        return self.send_message(message)
    
    def send_scan_started(self, scan_id: str, directories: List[str] = None, timestamp: datetime = None, **kwargs) -> bool:
        """Send scan started notification."""
        return self.send_scan_update({
            "scan_session_id": scan_id,
            "scan_type": "full",
            "scan_status": "running",
            "total_files_found": 0,
            "new_files_found": 0,
            "modified_files_found": 0,
            "unchanged_files": 0,
            "scan_duration": 0.0,
            "directories": directories or [],
            "timestamp": timestamp or datetime.now()
        })
    
    def send_scan_progress(self, scan_id: str, progress_data: Dict[str, Any], **kwargs) -> bool:
        """Send scan progress update."""
        return self.send_scan_update({
            "scan_session_id": scan_id,
            "scan_status": "running",
            **progress_data
        })
    
    def send_scan_completed(self, scan_id: str, total_files: int = 0, new_files: int = 0, modified_files: int = 0, unchanged_files: int = 0, scan_duration: float = 0.0, errors: List[str] = None, **kwargs) -> bool:
        """Send scan completed notification."""
        return self.send_scan_update({
            "scan_session_id": scan_id,
            "scan_status": "completed",
            "total_files_found": total_files,
            "new_files_found": new_files,
            "modified_files_found": modified_files,
            "unchanged_files": unchanged_files,
            "scan_duration": scan_duration,
            "errors": errors or []
        })
    
    def send_scan_error(self, scan_id: str, error_message: str, scan_duration: float = 0.0, **kwargs) -> bool:
        """Send scan error notification."""
        return self.send_scan_update({
            "scan_session_id": scan_id,
            "scan_status": "failed",
            "error_message": error_message,
            "scan_duration": scan_duration
        })
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get communication statistics."""
        return {
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "commands_processed": self._commands_processed,
            "errors_count": self._errors_count,
            "is_running": self._is_running,
            "queue_sizes": {
                "service_queue": self._service_queue.qsize(),
                "command_queue": self._command_queue.qsize()
            }
        } 