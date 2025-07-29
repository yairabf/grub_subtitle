"""
Simple Health Monitor

A lightweight health monitoring system that tracks service status
and basic operational state.
"""

import threading
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from services.background_service import ServiceState
from logging_system.subtitle_logger import SubtitleLogger


class ServiceStatus(Enum):
    """Simple service status states."""
    IDLE = "idle"
    RUNNING = "running"
    SCANNING = "scanning"
    PROCESSING = "processing"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class SimpleHealthStatus:
    """Simple health status information."""
    timestamp: datetime
    service_status: ServiceStatus
    is_alive: bool
    uptime_seconds: int
    current_operation: Optional[str] = None
    last_activity: Optional[datetime] = None
    error_count: int = 0


class SimpleHealthMonitor:
    """
    Simple health monitor that tracks basic service status.
    
    Focuses on:
    - Is the service alive?
    - What is the current status?
    - Basic uptime and activity tracking
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the simple health monitor.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = SubtitleLogger(self.config)
        
        # Monitoring state
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Service state
        self._service_status = ServiceStatus.STOPPED
        self._is_alive = False
        self._start_time = None
        self._last_activity = None
        self._current_operation = None
        self._error_count = 0
        
        # Callbacks
        self._status_callbacks: list[Callable[[SimpleHealthStatus], None]] = []
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Heartbeat tracking
        self._last_heartbeat = time.time()
        self._heartbeat_interval = 30  # seconds
        
        self.logger.info("Simple health monitor initialized")
    
    def start_monitoring(self) -> bool:
        """
        Start health monitoring.
        
        Returns:
            True if started successfully, False otherwise
        """
        try:
            with self._lock:
                if self._monitoring_active:
                    self.logger.warning("Health monitoring already active")
                    return True
                
                self.logger.info("Starting simple health monitoring...")
                self._monitoring_active = True
                self._stop_event.clear()
                self._start_time = datetime.now()
                self._is_alive = True
                self._service_status = ServiceStatus.IDLE
                
                # Start monitoring thread
                self._monitor_thread = threading.Thread(
                    target=self._monitoring_loop,
                    name="SimpleHealthMonitor",
                    daemon=True
                )
                self._monitor_thread.start()
                
                self.logger.info("Simple health monitoring started successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to start health monitoring: {e}")
            return False
    
    def stop_monitoring(self) -> bool:
        """
        Stop health monitoring.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            with self._lock:
                self.logger.info("Stopping simple health monitoring...")
                self._monitoring_active = False
                self._stop_event.set()
                self._is_alive = False
                self._service_status = ServiceStatus.STOPPED
                
                # Wait for monitoring thread
                if self._monitor_thread and self._monitor_thread.is_alive():
                    self._monitor_thread.join(timeout=5.0)
                
                self.logger.info("Simple health monitoring stopped successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Error stopping health monitoring: {e}")
            return False
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        self.logger.info("Simple health monitoring loop started")
        
        try:
            while not self._stop_event.is_set():
                try:
                    # Update heartbeat
                    self._last_heartbeat = time.time()
                    
                    # Check if service is still alive
                    self._check_alive_status()
                    
                    # Get current health status
                    health_status = self._get_current_health_status()
                    
                    # Notify callbacks
                    self._notify_status_callbacks(health_status)
                    
                    # Wait before next check
                    self._stop_event.wait(30)  # Check every 30 seconds
                    
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                    self._stop_event.wait(60)  # Wait longer on error
                    
        except Exception as e:
            self.logger.error(f"Monitoring loop error: {e}")
        finally:
            self.logger.info("Simple health monitoring loop stopped")
    
    def _check_alive_status(self) -> None:
        """Check if the service is still alive."""
        current_time = time.time()
        
        # If no heartbeat for more than 2 intervals, consider service dead
        if current_time - self._last_heartbeat > self._heartbeat_interval * 2:
            with self._lock:
                self._is_alive = False
                self._service_status = ServiceStatus.ERROR
                self.logger.warning("Service appears to be unresponsive")
        else:
            with self._lock:
                self._is_alive = True
    
    def _get_current_health_status(self) -> SimpleHealthStatus:
        """Get current health status."""
        with self._lock:
            uptime_seconds = 0
            if self._start_time:
                uptime_seconds = int((datetime.now() - self._start_time).total_seconds())
            
            return SimpleHealthStatus(
                timestamp=datetime.now(),
                service_status=self._service_status,
                is_alive=self._is_alive,
                uptime_seconds=uptime_seconds,
                current_operation=self._current_operation,
                last_activity=self._last_activity,
                error_count=self._error_count
            )
    
    def update_status(self, status: ServiceStatus, operation: Optional[str] = None) -> None:
        """
        Update the service status.
        
        Args:
            status: New service status
            operation: Current operation description
        """
        with self._lock:
            self._service_status = status
            self._current_operation = operation
            self._last_activity = datetime.now()
            self._last_heartbeat = time.time()
            
            self.logger.debug(f"Status updated: {status.value} - {operation or 'No operation'}")
    
    def record_activity(self, operation: str) -> None:
        """
        Record service activity.
        
        Args:
            operation: Description of the activity
        """
        with self._lock:
            self._last_activity = datetime.now()
            self._last_heartbeat = time.time()
            self._current_operation = operation
            
            self.logger.debug(f"Activity recorded: {operation}")
    
    def record_error(self, error_message: str = "") -> None:
        """
        Record an error occurrence.
        
        Args:
            error_message: Error description
        """
        with self._lock:
            self._error_count += 1
            self._last_activity = datetime.now()
            self._last_heartbeat = time.time()
            
            self.logger.error(f"Error recorded: {error_message}")
    
    def get_status(self) -> SimpleHealthStatus:
        """
        Get current health status.
        
        Returns:
            Current health status
        """
        return self._get_current_health_status()
    
    def is_alive(self) -> bool:
        """
        Check if the service is alive.
        
        Returns:
            True if service is alive, False otherwise
        """
        with self._lock:
            return self._is_alive
    
    def get_uptime(self) -> int:
        """
        Get service uptime in seconds.
        
        Returns:
            Uptime in seconds
        """
        with self._lock:
            if self._start_time:
                return int((datetime.now() - self._start_time).total_seconds())
            return 0
    
    def _notify_status_callbacks(self, status: SimpleHealthStatus) -> None:
        """Notify status callbacks."""
        for callback in self._status_callbacks:
            try:
                callback(status)
            except Exception as e:
                self.logger.error(f"Error in status callback: {e}")
    
    def register_status_callback(self, callback: Callable[[SimpleHealthStatus], None]) -> None:
        """
        Register a status callback.
        
        Args:
            callback: Function to call when status changes
        """
        with self._lock:
            if callback not in self._status_callbacks:
                self._status_callbacks.append(callback)
    
    def unregister_status_callback(self, callback: Callable[[SimpleHealthStatus], None]) -> None:
        """
        Unregister a status callback.
        
        Args:
            callback: Function to unregister
        """
        with self._lock:
            if callback in self._status_callbacks:
                self._status_callbacks.remove(callback)
    
    def get_status_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current status.
        
        Returns:
            Status summary dictionary
        """
        status = self.get_status()
        
        return {
            'is_alive': status.is_alive,
            'status': status.service_status.value,
            'uptime_seconds': status.uptime_seconds,
            'current_operation': status.current_operation,
            'last_activity': status.last_activity.isoformat() if status.last_activity else None,
            'error_count': status.error_count,
            'timestamp': status.timestamp.isoformat()
        } 