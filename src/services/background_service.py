"""
Background Service for Automatic Media Library Processing

This module provides the core background service functionality that monitors
media library directories and automatically processes new video files to ensure
Hebrew subtitles are available.
"""

import threading
import time
import logging
from enum import Enum
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager

from config.config_manager import ConfigManager
from logging_system.subtitle_logger import SubtitleLogger
from services.subtitle_service import SubtitleService


class ServiceState(Enum):
    """Service states for lifecycle management."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    PAUSED = "paused"


@dataclass
class ServiceStatus:
    """Service status information."""
    state: ServiceState
    start_time: Optional[datetime] = None
    last_scan_time: Optional[datetime] = None
    files_processed: int = 0
    files_failed: int = 0
    current_operation: Optional[str] = None
    error_message: Optional[str] = None
    uptime_seconds: int = 0
    last_error_time: Optional[datetime] = None
    consecutive_errors: int = 0
    health_score: float = 100.0  # 0-100, 100 being perfect health


class ServiceStateError(Exception):
    """Exception raised for invalid state transitions."""
    pass


class BackgroundService:
    """
    Background service for automatic media library processing.
    
    This service monitors specified directories for new video files and
    automatically processes them to ensure Hebrew subtitles are available.
    """
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        ServiceState.STOPPED: [ServiceState.STARTING],
        ServiceState.STARTING: [ServiceState.RUNNING, ServiceState.ERROR],
        ServiceState.RUNNING: [ServiceState.STOPPING, ServiceState.PAUSED, ServiceState.ERROR],
        ServiceState.STOPPING: [ServiceState.STOPPED, ServiceState.ERROR],
        ServiceState.PAUSED: [ServiceState.RUNNING, ServiceState.STOPPING, ServiceState.ERROR],
        ServiceState.ERROR: [ServiceState.STOPPED, ServiceState.STARTING]
    }
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the background service.
        
        Args:
            config_manager: Configuration manager instance. If None, creates a new one.
        """
        self.config_manager = config_manager or ConfigManager()
        
        # Initialize logger with config
        config = self.config_manager.config
        self.logger = SubtitleLogger(config)
        self.subtitle_service = SubtitleService()
        
        # Service state management with enhanced thread safety
        self._state = ServiceState.STOPPED
        self._status = ServiceStatus(state=ServiceState.STOPPED)
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._state_condition = threading.Condition(self._lock)  # Condition for state changes
        
        # Service threads
        self._main_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        
        # Callbacks for status updates
        self._status_callbacks: List[Callable[[ServiceStatus], None]] = []
        self._state_callbacks: List[Callable[[ServiceState, ServiceState], None]] = []
        
        # Service configuration
        self._scan_interval = 300  # 5 minutes default
        self._monitored_directories: List[Path] = []
        
        # Health monitoring
        self._health_check_interval = 60  # 1 minute
        self._last_health_check = datetime.now()
        self._max_consecutive_errors = 5
        
        # State history for debugging
        self._state_history: List[Dict[str, Any]] = []
        self._max_history_size = 100
        
        self.logger.info("Background service initialized")
    
    @property
    def state(self) -> ServiceState:
        """Get current service state."""
        with self._lock:
            return self._state
    
    @property
    def status(self) -> ServiceStatus:
        """Get current service status."""
        with self._lock:
            return self._status
    
    def _transition_to_state(self, new_state: ServiceState, reason: str = "") -> bool:
        """
        Safely transition to a new state with validation.
        
        Args:
            new_state: The target state to transition to
            reason: Optional reason for the state transition
            
        Returns:
            True if transition was successful, False otherwise
            
        Raises:
            ServiceStateError: If the transition is invalid
        """
        with self._lock:
            current_state = self._state
            
            # Check if transition is valid
            if new_state not in self.VALID_TRANSITIONS.get(current_state, []):
                error_msg = f"Invalid state transition: {current_state} -> {new_state}"
                self.logger.error(error_msg)
                raise ServiceStateError(error_msg)
            
            # Record state transition
            transition_record = {
                'timestamp': datetime.now(),
                'from_state': current_state.value,
                'to_state': new_state.value,
                'reason': reason
            }
            self._state_history.append(transition_record)
            
            # Keep history size manageable
            if len(self._state_history) > self._max_history_size:
                self._state_history.pop(0)
            
            # Update state
            old_state = self._state
            self._state = new_state
            self._status.state = new_state
            
            # Update status based on new state
            if new_state == ServiceState.RUNNING:
                if not self._status.start_time:
                    self._status.start_time = datetime.now()
                self._status.error_message = None
                self._status.consecutive_errors = 0
            elif new_state == ServiceState.ERROR:
                self._status.last_error_time = datetime.now()
                self._status.consecutive_errors += 1
            elif new_state == ServiceState.STOPPED:
                self._status.start_time = None
                self._status.current_operation = None
            
            # Notify state change callbacks
            state_callbacks = self._state_callbacks.copy()
            
            # Notify all callbacks
            self._notify_callbacks()
            
            # Signal condition for any waiting threads
            self._state_condition.notify_all()
            
            self.logger.info(f"State transition: {old_state.value} -> {new_state.value} ({reason})")
            
            # Call state change callbacks outside of lock
            for callback in state_callbacks:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    self.logger.error(f"Error in state callback: {e}")
            
            return True
    
    def _notify_callbacks(self) -> None:
        """Notify all status callbacks with current status."""
        callbacks = self._status_callbacks.copy()
        status_copy = ServiceStatus(
            state=self._status.state,
            start_time=self._status.start_time,
            last_scan_time=self._status.last_scan_time,
            files_processed=self._status.files_processed,
            files_failed=self._status.files_failed,
            current_operation=self._status.current_operation,
            error_message=self._status.error_message,
            uptime_seconds=self._status.uptime_seconds,
            last_error_time=self._status.last_error_time,
            consecutive_errors=self._status.consecutive_errors,
            health_score=self._status.health_score
        )
        
        # Call callbacks outside of lock to avoid deadlocks
        for callback in callbacks:
            try:
                callback(status_copy)
            except Exception as e:
                self.logger.error(f"Error in status callback: {e}")
    
    def add_status_callback(self, callback: Callable[[ServiceStatus], None]) -> None:
        """
        Add a callback function to be called when service status changes.
        
        Args:
            callback: Function to call with service status updates
        """
        with self._lock:
            if callback not in self._status_callbacks:
                self._status_callbacks.append(callback)
    
    def remove_status_callback(self, callback: Callable[[ServiceStatus], None]) -> None:
        """
        Remove a status callback function.
        
        Args:
            callback: Function to remove from callbacks list
        """
        with self._lock:
            if callback in self._status_callbacks:
                self._status_callbacks.remove(callback)
    
    def add_state_callback(self, callback: Callable[[ServiceState, ServiceState], None]) -> None:
        """
        Add a callback function to be called when service state changes.
        
        Args:
            callback: Function to call with old and new state
        """
        with self._lock:
            if callback not in self._state_callbacks:
                self._state_callbacks.append(callback)
    
    def remove_state_callback(self, callback: Callable[[ServiceState, ServiceState], None]) -> None:
        """
        Remove a state callback function.
        
        Args:
            callback: Function to remove from callbacks list
        """
        with self._lock:
            if callback in self._state_callbacks:
                self._state_callbacks.remove(callback)
    
    def wait_for_state(self, target_state: ServiceState, timeout: float = 30.0) -> bool:
        """
        Wait for the service to reach a specific state.
        
        Args:
            target_state: The state to wait for
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if state was reached, False if timeout occurred
        """
        with self._state_condition:
            start_time = time.time()
            while self._state != target_state:
                remaining_time = timeout - (time.time() - start_time)
                if remaining_time <= 0:
                    return False
                
                if not self._state_condition.wait(timeout=remaining_time):
                    return False
            
            return True
    
    def is_in_state(self, state: ServiceState) -> bool:
        """
        Check if service is in a specific state.
        
        Args:
            state: The state to check for
            
        Returns:
            True if service is in the specified state
        """
        with self._lock:
            return self._state == state
    
    def can_transition_to(self, target_state: ServiceState) -> bool:
        """
        Check if service can transition to a specific state.
        
        Args:
            target_state: The target state to check
            
        Returns:
            True if transition is valid
        """
        with self._lock:
            return target_state in self.VALID_TRANSITIONS.get(self._state, [])
    
    def _update_status(self, **kwargs) -> None:
        """
        Update service status and notify callbacks.
        
        Args:
            **kwargs: Status fields to update
        """
        with self._lock:
            # Update status fields
            for key, value in kwargs.items():
                if hasattr(self._status, key):
                    setattr(self._status, key, value)
            
            # Update uptime if service is running
            if self._status.start_time and self._state in [ServiceState.RUNNING, ServiceState.PAUSED]:
                self._status.uptime_seconds = int((datetime.now() - self._status.start_time).total_seconds())
            
            # Update health score
            self._update_health_score()
            
            # Notify callbacks
            self._notify_callbacks()
    
    def _update_health_score(self) -> None:
        """Update service health score based on various factors."""
        health_score = 100.0
        
        # Reduce score for consecutive errors
        if self._status.consecutive_errors > 0:
            health_score -= (self._status.consecutive_errors * 10)
        
        # Reduce score for recent errors
        if self._status.last_error_time:
            time_since_error = (datetime.now() - self._status.last_error_time).total_seconds()
            if time_since_error < 300:  # 5 minutes
                health_score -= 20
        
        # Ensure score is within bounds
        health_score = max(0.0, min(100.0, health_score))
        self._status.health_score = health_score
    
    def start(self) -> bool:
        """
        Start the background service.
        
        Returns:
            True if service started successfully, False otherwise
        """
        try:
            with self._lock:
                if not self.can_transition_to(ServiceState.STARTING):
                    self.logger.warning(f"Cannot start service: current state is {self._state}")
                    return False
                
                self.logger.info("Starting background service...")
                self._transition_to_state(ServiceState.STARTING, "Manual start request")
                
                # Load configuration
                self._load_configuration()
                
                # Validate configuration
                if not self._validate_configuration():
                    self._transition_to_state(ServiceState.ERROR, "Invalid configuration")
                    return False
                
                # Reset events
                self._stop_event.clear()
                self._pause_event.clear()
                
                # Start main service thread
                self._main_thread = threading.Thread(
                    target=self._service_main_loop,
                    name="BackgroundService-Main",
                    daemon=True
                )
                self._main_thread.start()
                
                # Transition to running state
                self._transition_to_state(ServiceState.RUNNING, "Service started successfully")
                
                self.logger.info("Background service started successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to start background service: {e}")
            self._transition_to_state(ServiceState.ERROR, f"Start failed: {str(e)}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the background service.
        
        Returns:
            True if service stopped successfully, False otherwise
        """
        try:
            with self._lock:
                if not self.can_transition_to(ServiceState.STOPPING):
                    self.logger.warning(f"Cannot stop service: current state is {self._state}")
                    return True  # Already stopped or stopping
                
                self.logger.info("Stopping background service...")
                self._transition_to_state(ServiceState.STOPPING, "Manual stop request")
                
                # Signal stop event
                self._stop_event.set()
                
                # Wait for main thread to finish (with timeout)
                if self._main_thread and self._main_thread.is_alive():
                    self._main_thread.join(timeout=10.0)
                    
                    if self._main_thread.is_alive():
                        self.logger.warning("Service thread did not stop within timeout")
                        self._transition_to_state(ServiceState.ERROR, "Stop timeout")
                        return False
                
                self._transition_to_state(ServiceState.STOPPED, "Service stopped successfully")
                self.logger.info("Background service stopped successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Error stopping background service: {e}")
            self._transition_to_state(ServiceState.ERROR, f"Stop failed: {str(e)}")
            return False
    
    def pause(self) -> bool:
        """
        Pause the background service.
        
        Returns:
            True if service paused successfully, False otherwise
        """
        try:
            with self._lock:
                if not self.can_transition_to(ServiceState.PAUSED):
                    self.logger.warning(f"Cannot pause service: current state is {self._state}")
                    return False
                
                self.logger.info("Pausing background service...")
                self._pause_event.set()
                self._transition_to_state(ServiceState.PAUSED, "Manual pause request")
                return True
                
        except Exception as e:
            self.logger.error(f"Error pausing background service: {e}")
            return False
    
    def resume(self) -> bool:
        """
        Resume the background service from paused state.
        
        Returns:
            True if service resumed successfully, False otherwise
        """
        try:
            with self._lock:
                if not self.can_transition_to(ServiceState.RUNNING):
                    self.logger.warning(f"Cannot resume service: current state is {self._state}")
                    return False
                
                self.logger.info("Resuming background service...")
                self._pause_event.clear()
                self._transition_to_state(ServiceState.RUNNING, "Manual resume request")
                return True
                
        except Exception as e:
            self.logger.error(f"Error resuming background service: {e}")
            return False
    
    def restart(self) -> bool:
        """
        Restart the background service.
        
        Returns:
            True if service restarted successfully, False otherwise
        """
        self.logger.info("Restarting background service...")
        
        # Stop the service
        if not self.stop():
            return False
        
        # Wait a moment for cleanup
        time.sleep(1.0)
        
        # Start the service
        return self.start()
    
    def get_state_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get the state transition history.
        
        Args:
            limit: Maximum number of history entries to return
            
        Returns:
            List of state transition records
        """
        with self._lock:
            history = self._state_history.copy()
            if limit:
                history = history[-limit:]
            return history
    
    def _load_configuration(self) -> None:
        """Load service configuration from config manager."""
        try:
            config = self.config_manager.config
            service_config = config.get('background_service', {})
            
            # Load scan interval (default: 5 minutes)
            self._scan_interval = service_config.get('scan_interval_seconds', 300)
            
            # Load monitored directories
            directories = service_config.get('monitored_directories', [])
            self._monitored_directories = []
            
            for dir_path in directories:
                path = Path(dir_path)
                if path.exists() and path.is_dir():
                    self._monitored_directories.append(path)
                else:
                    self.logger.warning(f"Invalid monitored directory: {dir_path}")
            
            self.logger.info(f"Loaded configuration: {len(self._monitored_directories)} directories, "
                           f"{self._scan_interval}s scan interval")
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise
    
    def _validate_configuration(self) -> bool:
        """
        Validate service configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        if not self._monitored_directories:
            self.logger.error("No valid monitored directories configured")
            return False
        
        if self._scan_interval < 60:  # Minimum 1 minute
            self.logger.error("Scan interval too short (minimum 60 seconds)")
            return False
        
        return True
    
    def _service_main_loop(self) -> None:
        """Main service loop that runs in background thread."""
        self.logger.info("Background service main loop started")
        
        try:
            while not self._stop_event.is_set():
                # Check if service is paused
                if self._pause_event.is_set():
                    self._update_status(current_operation="Paused")
                    time.sleep(1.0)
                    continue
                
                self._update_status(current_operation="Scanning directories")
                
                # TODO: Implement directory scanning and file processing
                # This will be implemented in Task 2.0
                
                # Update last scan time
                self._update_status(last_scan_time=datetime.now())
                
                # Wait for next scan interval or stop signal
                if self._stop_event.wait(timeout=self._scan_interval):
                    break
                
        except Exception as e:
            self.logger.error(f"Error in service main loop: {e}")
            self._transition_to_state(ServiceState.ERROR, f"Main loop error: {str(e)}")
        
        finally:
            self.logger.info("Background service main loop ended")
    
    def get_status_summary(self) -> Dict[str, Any]:
        """
        Get a summary of service status for display.
        
        Returns:
            Dictionary with status summary information
        """
        with self._lock:
            return {
                'state': self._status.state.value,
                'start_time': self._status.start_time.isoformat() if self._status.start_time else None,
                'last_scan_time': self._status.last_scan_time.isoformat() if self._status.last_scan_time else None,
                'files_processed': self._status.files_processed,
                'files_failed': self._status.files_failed,
                'current_operation': self._status.current_operation,
                'error_message': self._status.error_message,
                'uptime_seconds': self._status.uptime_seconds,
                'health_score': self._status.health_score,
                'consecutive_errors': self._status.consecutive_errors,
                'monitored_directories': [str(d) for d in self._monitored_directories],
                'scan_interval': self._scan_interval,
                'can_start': self.can_transition_to(ServiceState.STARTING),
                'can_stop': self.can_transition_to(ServiceState.STOPPING),
                'can_pause': self.can_transition_to(ServiceState.PAUSED),
                'can_resume': self.can_transition_to(ServiceState.RUNNING)
            } 