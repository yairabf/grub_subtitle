"""
Service Logger Integration

Integrates the default Python logging system with the background service
to provide comprehensive logging capabilities.
"""

import logging
import logging.handlers
import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import threading

from services.background_service import ServiceState, ServiceStatus
from services.simple_health_monitor import SimpleHealthStatus


class ServiceLogger:
    """
    Service logger that integrates with Python's default logging system.
    
    Provides structured logging with proper formatting, log rotation,
    and integration with the background service components.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the service logger.
        
        Args:
            config: Configuration dictionary for logging settings
        """
        self.config = config or {}
        self._setup_logging()
        
        # Get logger instances
        self.logger = logging.getLogger('background_service')
        self.health_logger = logging.getLogger('health_monitor')
        self.file_logger = logging.getLogger('file_tracker')
        self.comm_logger = logging.getLogger('communication')
        
        # Thread safety
        self._lock = threading.RLock()
        
        self.logger.info("Service logger initialized")
    
    def _setup_logging(self) -> None:
        """Set up the logging configuration."""
        # Get logging configuration
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_file = log_config.get('file', 'logs/background_service.log')
        console_output = log_config.get('console_output', True)
        max_bytes = log_config.get('max_bytes', 10 * 1024 * 1024)  # 10MB
        backup_count = log_config.get('backup_count', 5)
        
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # Configure specific loggers
        self._configure_service_loggers()
    
    def _configure_service_loggers(self) -> None:
        """Configure specific loggers for different service components."""
        # Background service logger
        service_logger = logging.getLogger('background_service')
        service_logger.setLevel(logging.INFO)
        
        # Health monitor logger
        health_logger = logging.getLogger('health_monitor')
        health_logger.setLevel(logging.INFO)
        
        # File tracker logger
        file_logger = logging.getLogger('file_tracker')
        file_logger.setLevel(logging.INFO)
        
        # Communication logger
        comm_logger = logging.getLogger('communication')
        comm_logger.setLevel(logging.INFO)
    
    def log_service_start(self, service_name: str, config: Dict[str, Any]) -> None:
        """Log service startup."""
        self.logger.info(f"Starting {service_name} service")
        self.logger.debug(f"Service configuration: {json.dumps(config, indent=2)}")
    
    def log_service_stop(self, service_name: str, uptime_seconds: int) -> None:
        """Log service shutdown."""
        self.logger.info(f"Stopping {service_name} service (uptime: {uptime_seconds}s)")
    
    def log_service_state_change(self, old_state: ServiceState, new_state: ServiceState, reason: str = "") -> None:
        """Log service state changes."""
        self.logger.info(f"Service state changed: {old_state.value} -> {new_state.value}")
        if reason:
            self.logger.debug(f"State change reason: {reason}")
    
    def log_health_status(self, health_status: SimpleHealthStatus) -> None:
        """Log health status updates."""
        self.health_logger.info(
            f"Health status: {health_status.service_status.value} "
            f"(alive: {health_status.is_alive}, uptime: {health_status.uptime_seconds}s, "
            f"errors: {health_status.error_count})"
        )
        
        if health_status.current_operation:
            self.health_logger.debug(f"Current operation: {health_status.current_operation}")
    
    def log_file_processing(self, file_path: str, operation: str, status: str, duration: float = None) -> None:
        """Log file processing events."""
        message = f"File {operation}: {file_path} - {status}"
        if duration is not None:
            message += f" (duration: {duration:.2f}s)"
        
        self.file_logger.info(message)
    
    def log_scan_session(self, session_id: int, directories: list, files_found: int, 
                        files_processed: int, files_skipped: int, files_failed: int, 
                        duration: float) -> None:
        """Log scan session results."""
        self.file_logger.info(
            f"Scan session {session_id} completed: "
            f"{files_found} files found, {files_processed} processed, "
            f"{files_skipped} skipped, {files_failed} failed "
            f"(duration: {duration:.2f}s)"
        )
        
        self.file_logger.debug(f"Directories scanned: {directories}")
    
    def log_communication_event(self, event_type: str, message: str, data: Dict[str, Any] = None) -> None:
        """Log communication events."""
        self.comm_logger.info(f"Communication {event_type}: {message}")
        if data:
            self.comm_logger.debug(f"Event data: {json.dumps(data, indent=2)}")
    
    def log_error(self, error_type: str, error_message: str, exception: Exception = None) -> None:
        """Log errors with context."""
        self.logger.error(f"Error ({error_type}): {error_message}")
        if exception:
            self.logger.error(f"Exception details: {str(exception)}")
            self.logger.debug(f"Exception traceback: {self._get_traceback(exception)}")
    
    def log_warning(self, warning_type: str, warning_message: str) -> None:
        """Log warnings with context."""
        self.logger.warning(f"Warning ({warning_type}): {warning_message}")
    
    def log_info(self, info_type: str, message: str, data: Dict[str, Any] = None) -> None:
        """Log informational messages."""
        self.logger.info(f"Info ({info_type}): {message}")
        if data:
            self.logger.debug(f"Info data: {json.dumps(data, indent=2)}")
    
    def log_debug(self, debug_type: str, message: str, data: Dict[str, Any] = None) -> None:
        """Log debug messages."""
        self.logger.debug(f"Debug ({debug_type}): {message}")
        if data:
            self.logger.debug(f"Debug data: {json.dumps(data, indent=2)}")
    
    def log_performance(self, operation: str, duration: float, details: Dict[str, Any] = None) -> None:
        """Log performance metrics."""
        self.logger.info(f"Performance ({operation}): {duration:.2f}s")
        if details:
            self.logger.debug(f"Performance details: {json.dumps(details, indent=2)}")
    
    def log_configuration_change(self, component: str, old_value: Any, new_value: Any) -> None:
        """Log configuration changes."""
        self.logger.info(f"Configuration change ({component}): {old_value} -> {new_value}")
    
    def log_user_action(self, action: str, user: str = "system", details: Dict[str, Any] = None) -> None:
        """Log user actions."""
        self.logger.info(f"User action ({user}): {action}")
        if details:
            self.logger.debug(f"Action details: {json.dumps(details, indent=2)}")
    
    def log_system_event(self, event: str, severity: str = "info", details: Dict[str, Any] = None) -> None:
        """Log system events."""
        log_method = getattr(self.logger, severity.lower(), self.logger.info)
        log_method(f"System event: {event}")
        if details:
            self.logger.debug(f"Event details: {json.dumps(details, indent=2)}")
    
    def _get_traceback(self, exception: Exception) -> str:
        """Get formatted traceback for an exception."""
        import traceback
        return ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    
    def set_log_level(self, logger_name: str, level: str) -> None:
        """Set log level for a specific logger."""
        try:
            logger = logging.getLogger(logger_name)
            log_level = getattr(logging, level.upper())
            logger.setLevel(log_level)
            self.logger.info(f"Log level for {logger_name} set to {level}")
        except (AttributeError, ValueError) as e:
            self.logger.error(f"Failed to set log level for {logger_name}: {e}")
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics."""
        stats = {
            'loggers': {},
            'handlers': {},
            'total_handlers': 0
        }
        
        # Get root logger stats
        root_logger = logging.getLogger()
        stats['handlers']['root'] = len(root_logger.handlers)
        stats['total_handlers'] += len(root_logger.handlers)
        
        # Get specific logger stats
        for logger_name in ['background_service', 'health_monitor', 'file_tracker', 'communication']:
            logger = logging.getLogger(logger_name)
            stats['loggers'][logger_name] = {
                'level': logging.getLevelName(logger.level),
                'handlers': len(logger.handlers),
                'propagate': logger.propagate
            }
            stats['total_handlers'] += len(logger.handlers)
        
        return stats
    
    def rotate_logs(self) -> None:
        """Manually trigger log rotation."""
        try:
            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.doRollover()
                    self.logger.info("Log rotation completed")
                    break
        except Exception as e:
            self.logger.error(f"Failed to rotate logs: {e}")
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """Clean up old log files."""
        try:
            log_config = self.config.get('logging', {})
            log_file = log_config.get('file', 'logs/background_service.log')
            log_path = Path(log_file)
            
            if not log_path.parent.exists():
                return 0
            
            cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
            deleted_count = 0
            
            for log_file in log_path.parent.glob('*.log.*'):
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    deleted_count += 1
            
            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old log files")
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old logs: {e}")
            return 0 