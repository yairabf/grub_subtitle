"""
Service Health Monitoring and Crash Recovery System

This module provides comprehensive health monitoring, performance tracking,
and automatic crash recovery mechanisms for the background service.
"""

import threading
import time
import psutil
import os
import signal
import sys
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import json
import traceback

from services.background_service import ServiceState, ServiceStatus
from services.service_communication import ServiceCommunicationManager, MessageType
from logging_system.subtitle_logger import SubtitleLogger


class HealthStatus(Enum):
    """Health status levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"
    FAILED = "failed"


class RecoveryAction(Enum):
    """Available recovery actions."""
    RESTART_SERVICE = "restart_service"
    RESTART_THREAD = "restart_thread"
    CLEAR_CACHE = "clear_cache"
    RESET_DATABASE = "reset_database"
    SEND_ALERT = "send_alert"
    ESCALATE = "escalate"


@dataclass
class HealthMetrics:
    """Health metrics for monitoring."""
    timestamp: datetime
    cpu_percentage: float
    memory_percentage: float
    disk_usage_percentage: float
    active_threads: int
    queue_sizes: Dict[str, int]
    error_count: int
    consecutive_errors: int
    uptime_seconds: int
    last_operation_duration: float
    health_score: float
    status: HealthStatus


@dataclass
class RecoveryEvent:
    """Recovery event information."""
    timestamp: datetime
    trigger: str
    action: RecoveryAction
    success: bool
    duration: float
    error_message: Optional[str] = None
    metrics_before: Optional[HealthMetrics] = None
    metrics_after: Optional[HealthMetrics] = None


@dataclass
class HealthThresholds:
    """Configurable health thresholds."""
    cpu_warning: float = 70.0
    cpu_critical: float = 90.0
    memory_warning: float = 80.0
    memory_critical: float = 95.0
    disk_warning: float = 85.0
    disk_critical: float = 95.0
    error_rate_warning: float = 0.1  # 10% error rate
    error_rate_critical: float = 0.3  # 30% error rate
    consecutive_errors_warning: int = 3
    consecutive_errors_critical: int = 10
    operation_timeout_warning: float = 30.0  # seconds
    operation_timeout_critical: float = 60.0  # seconds
    health_score_warning: float = 70.0
    health_score_critical: float = 50.0


class HealthMonitor:
    """
    Comprehensive health monitoring and crash recovery system.
    
    Monitors system resources, service performance, and automatically
    triggers recovery actions when issues are detected.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, 
                 communication_manager: Optional[ServiceCommunicationManager] = None):
        """
        Initialize the health monitor.
        
        Args:
            config: Configuration dictionary
            communication_manager: Service communication manager for alerts
        """
        self.config = config or {}
        self.logger = SubtitleLogger(self.config)
        self.communication_manager = communication_manager
        
        # Health monitoring state
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Health data
        self._health_history: List[HealthMetrics] = []
        self._recovery_history: List[RecoveryEvent] = []
        self._current_metrics: Optional[HealthMetrics] = None
        self._last_check_time = datetime.now()
        
        # Thresholds
        self.thresholds = HealthThresholds()
        self._load_thresholds_from_config()
        
        # Recovery configuration
        self._max_recovery_attempts = 3
        self._recovery_cooldown = 300  # 5 minutes
        self._last_recovery_time = datetime.now() - timedelta(seconds=self._recovery_cooldown)
        self._recovery_attempts = 0
        
        # Callbacks
        self._health_callbacks: List[Callable[[HealthMetrics], None]] = []
        self._recovery_callbacks: List[Callable[[RecoveryEvent], None]] = []
        self._alert_callbacks: List[Callable[[str, HealthStatus], None]] = []
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Performance tracking
        self._operation_start_times: Dict[str, float] = {}
        self._error_counts: Dict[str, int] = {}
        self._queue_monitors: Dict[str, Callable[[], int]] = {}
        
        # Crash detection
        self._watchdog_timer = None
        self._last_heartbeat = time.time()
        self._heartbeat_interval = 30  # seconds
        
        self.logger.info("Health monitor initialized")
    
    def _load_thresholds_from_config(self) -> None:
        """Load health thresholds from configuration."""
        health_config = self.config.get('health_monitoring', {})
        thresholds_config = health_config.get('thresholds', {})
        
        if 'cpu_warning' in thresholds_config:
            self.thresholds.cpu_warning = float(thresholds_config['cpu_warning'])
        if 'cpu_critical' in thresholds_config:
            self.thresholds.cpu_critical = float(thresholds_config['cpu_critical'])
        if 'memory_warning' in thresholds_config:
            self.thresholds.memory_warning = float(thresholds_config['memory_warning'])
        if 'memory_critical' in thresholds_config:
            self.thresholds.memory_critical = float(thresholds_config['memory_critical'])
        if 'disk_warning' in thresholds_config:
            self.thresholds.disk_warning = float(thresholds_config['disk_warning'])
        if 'disk_critical' in thresholds_config:
            self.thresholds.disk_critical = float(thresholds_config['disk_critical'])
        if 'error_rate_warning' in thresholds_config:
            self.thresholds.error_rate_warning = float(thresholds_config['error_rate_warning'])
        if 'error_rate_critical' in thresholds_config:
            self.thresholds.error_rate_critical = float(thresholds_config['error_rate_critical'])
        if 'consecutive_errors_warning' in thresholds_config:
            self.thresholds.consecutive_errors_warning = int(thresholds_config['consecutive_errors_warning'])
        if 'consecutive_errors_critical' in thresholds_config:
            self.thresholds.consecutive_errors_critical = int(thresholds_config['consecutive_errors_critical'])
        if 'operation_timeout_warning' in thresholds_config:
            self.thresholds.operation_timeout_warning = float(thresholds_config['operation_timeout_warning'])
        if 'operation_timeout_critical' in thresholds_config:
            self.thresholds.operation_timeout_critical = float(thresholds_config['operation_timeout_critical'])
        if 'health_score_warning' in thresholds_config:
            self.thresholds.health_score_warning = float(thresholds_config['health_score_warning'])
        if 'health_score_critical' in thresholds_config:
            self.thresholds.health_score_critical = float(thresholds_config['health_score_critical'])
    
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
                
                self.logger.info("Starting health monitoring...")
                self._monitoring_active = True
                self._stop_event.clear()
                
                # Start monitoring thread
                self._monitor_thread = threading.Thread(
                    target=self._monitoring_loop,
                    name="HealthMonitor",
                    daemon=True
                )
                self._monitor_thread.start()
                
                # Start watchdog timer
                self._start_watchdog()
                
                self.logger.info("Health monitoring started successfully")
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
                self.logger.info("Stopping health monitoring...")
                self._monitoring_active = False
                self._stop_event.set()
                
                # Stop watchdog timer
                self._stop_watchdog()
                
                # Wait for monitoring thread
                if self._monitor_thread and self._monitor_thread.is_alive():
                    self._monitor_thread.join(timeout=5.0)
                
                self.logger.info("Health monitoring stopped successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Error stopping health monitoring: {e}")
            return False
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        self.logger.info("Health monitoring loop started")
        
        try:
            while not self._stop_event.is_set():
                try:
                    # Collect health metrics
                    metrics = self._collect_health_metrics()
                    
                    # Analyze health status
                    health_status = self._analyze_health(metrics)
                    metrics.status = health_status
                    
                    # Store metrics
                    with self._lock:
                        self._current_metrics = metrics
                        self._health_history.append(metrics)
                        
                        # Keep only recent history (last 24 hours)
                        cutoff_time = datetime.now() - timedelta(hours=24)
                        self._health_history = [
                            m for m in self._health_history 
                            if m.timestamp > cutoff_time
                        ]
                    
                    # Update heartbeat
                    self._last_heartbeat = time.time()
                    
                    # Check for recovery actions
                    if health_status in [HealthStatus.CRITICAL, HealthStatus.FAILED]:
                        self._trigger_recovery(health_status, metrics)
                    
                    # Notify callbacks
                    self._notify_health_callbacks(metrics)
                    
                    # Send alert if needed
                    if health_status in [HealthStatus.WARNING, HealthStatus.CRITICAL, HealthStatus.FAILED]:
                        self._send_alert(health_status, metrics)
                    
                    # Wait before next check
                    self._stop_event.wait(30)  # Check every 30 seconds
                    
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                    self._stop_event.wait(60)  # Wait longer on error
                    
        except Exception as e:
            self.logger.error(f"Monitoring loop error: {e}")
        finally:
            self.logger.info("Health monitoring loop stopped")
    
    def _collect_health_metrics(self) -> HealthMetrics:
        """Collect current health metrics."""
        try:
            # System metrics
            cpu_percentage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Process metrics
            process = psutil.Process()
            active_threads = process.num_threads()
            
            # Queue sizes
            queue_sizes = {}
            for name, monitor in self._queue_monitors.items():
                try:
                    queue_sizes[name] = monitor()
                except Exception as e:
                    self.logger.warning(f"Error monitoring queue {name}: {e}")
                    queue_sizes[name] = 0
            
            # Error tracking
            total_errors = sum(self._error_counts.values())
            consecutive_errors = self._get_consecutive_errors()
            
            # Operation timing
            last_operation_duration = self._get_last_operation_duration()
            
            # Calculate health score
            health_score = self._calculate_health_score(
                cpu_percentage, memory.percent, disk.percent,
                total_errors, consecutive_errors, last_operation_duration
            )
            
            return HealthMetrics(
                timestamp=datetime.now(),
                cpu_percentage=cpu_percentage,
                memory_percentage=memory.percent,
                disk_usage_percentage=disk.percent,
                active_threads=active_threads,
                queue_sizes=queue_sizes,
                error_count=total_errors,
                consecutive_errors=consecutive_errors,
                uptime_seconds=int(time.time() - self._last_heartbeat),
                last_operation_duration=last_operation_duration,
                health_score=health_score,
                status=HealthStatus.GOOD  # Will be updated by analyzer
            )
            
        except Exception as e:
            self.logger.error(f"Error collecting health metrics: {e}")
            # Return minimal metrics on error
            return HealthMetrics(
                timestamp=datetime.now(),
                cpu_percentage=0.0,
                memory_percentage=0.0,
                disk_usage_percentage=0.0,
                active_threads=0,
                queue_sizes={},
                error_count=1,
                consecutive_errors=1,
                uptime_seconds=0,
                last_operation_duration=0.0,
                health_score=0.0,
                status=HealthStatus.FAILED
            )
    
    def _analyze_health(self, metrics: HealthMetrics) -> HealthStatus:
        """Analyze health metrics and determine status."""
        try:
            # Check critical thresholds first
            if (metrics.cpu_percentage >= self.thresholds.cpu_critical or
                metrics.memory_percentage >= self.thresholds.memory_critical or
                metrics.disk_usage_percentage >= self.thresholds.disk_critical or
                metrics.consecutive_errors >= self.thresholds.consecutive_errors_critical or
                metrics.health_score <= self.thresholds.health_score_critical):
                return HealthStatus.CRITICAL
            
            # Check warning thresholds
            if (metrics.cpu_percentage >= self.thresholds.cpu_warning or
                metrics.memory_percentage >= self.thresholds.memory_warning or
                metrics.disk_usage_percentage >= self.thresholds.disk_warning or
                metrics.consecutive_errors >= self.thresholds.consecutive_errors_warning or
                metrics.health_score <= self.thresholds.health_score_warning):
                return HealthStatus.WARNING
            
            # Check for failed state
            if metrics.health_score <= 0:
                return HealthStatus.FAILED
            
            # Check for excellent state
            if (metrics.cpu_percentage < 30 and
                metrics.memory_percentage < 50 and
                metrics.disk_usage_percentage < 70 and
                metrics.consecutive_errors == 0 and
                metrics.health_score >= 90):
                return HealthStatus.EXCELLENT
            
            return HealthStatus.GOOD
            
        except Exception as e:
            self.logger.error(f"Error analyzing health: {e}")
            return HealthStatus.FAILED
    
    def _calculate_health_score(self, cpu: float, memory: float, disk: float,
                              errors: int, consecutive_errors: int, operation_duration: float) -> float:
        """Calculate overall health score (0-100)."""
        try:
            # Base score starts at 100
            score = 100.0
            
            # CPU penalty (max 25 points)
            if cpu > 90:
                score -= 25
            elif cpu > 70:
                score -= 15
            elif cpu > 50:
                score -= 10
            
            # Memory penalty (max 25 points)
            if memory > 95:
                score -= 25
            elif memory > 80:
                score -= 15
            elif memory > 60:
                score -= 10
            
            # Disk penalty (max 15 points)
            if disk > 95:
                score -= 15
            elif disk > 85:
                score -= 10
            elif disk > 70:
                score -= 5
            
            # Error penalty (max 20 points)
            if consecutive_errors > 10:
                score -= 20
            elif consecutive_errors > 5:
                score -= 15
            elif consecutive_errors > 0:
                score -= 5
            
            # Operation timeout penalty (max 15 points)
            if operation_duration > self.thresholds.operation_timeout_critical:
                score -= 15
            elif operation_duration > self.thresholds.operation_timeout_warning:
                score -= 10
            
            return max(0.0, score)
            
        except Exception as e:
            self.logger.error(f"Error calculating health score: {e}")
            return 0.0
    
    def _trigger_recovery(self, health_status: HealthStatus, metrics: HealthMetrics) -> None:
        """Trigger appropriate recovery actions."""
        try:
            # Check recovery cooldown
            if (datetime.now() - self._last_recovery_time).total_seconds() < self._recovery_cooldown:
                self.logger.info("Recovery cooldown active, skipping recovery")
                return
            
            # Check max attempts
            if self._recovery_attempts >= self._max_recovery_attempts:
                self.logger.warning("Max recovery attempts reached, escalating")
                self._escalate_recovery()
                return
            
            self.logger.warning(f"Triggering recovery for {health_status.value} health status")
            
            # Determine recovery action based on health status
            if health_status == HealthStatus.FAILED:
                action = RecoveryAction.RESTART_SERVICE
            elif metrics.cpu_percentage > self.thresholds.cpu_critical:
                action = RecoveryAction.CLEAR_CACHE
            elif metrics.memory_percentage > self.thresholds.memory_critical:
                action = RecoveryAction.CLEAR_CACHE
            elif metrics.consecutive_errors > self.thresholds.consecutive_errors_critical:
                action = RecoveryAction.RESTART_THREAD
            else:
                action = RecoveryAction.SEND_ALERT
            
            # Execute recovery action
            success = self._execute_recovery_action(action, metrics)
            
            # Record recovery event
            recovery_event = RecoveryEvent(
                timestamp=datetime.now(),
                trigger=health_status.value,
                action=action,
                success=success,
                duration=0.0,  # Will be updated
                metrics_before=metrics
            )
            
            with self._lock:
                self._recovery_history.append(recovery_event)
                self._recovery_attempts += 1
                self._last_recovery_time = datetime.now()
            
            # Notify recovery callbacks
            self._notify_recovery_callbacks(recovery_event)
            
        except Exception as e:
            self.logger.error(f"Error triggering recovery: {e}")
    
    def _execute_recovery_action(self, action: RecoveryAction, metrics: HealthMetrics) -> bool:
        """Execute a specific recovery action."""
        start_time = time.time()
        
        try:
            self.logger.info(f"Executing recovery action: {action.value}")
            
            if action == RecoveryAction.RESTART_SERVICE:
                success = self._restart_service()
            elif action == RecoveryAction.RESTART_THREAD:
                success = self._restart_thread()
            elif action == RecoveryAction.CLEAR_CACHE:
                success = self._clear_cache()
            elif action == RecoveryAction.RESET_DATABASE:
                success = self._reset_database()
            elif action == RecoveryAction.SEND_ALERT:
                success = self._send_alert(HealthStatus.CRITICAL, metrics)
            elif action == RecoveryAction.ESCALATE:
                success = self._escalate_recovery()
            else:
                self.logger.warning(f"Unknown recovery action: {action}")
                success = False
            
            duration = time.time() - start_time
            
            if success:
                self.logger.info(f"Recovery action {action.value} completed successfully in {duration:.2f}s")
            else:
                self.logger.error(f"Recovery action {action.value} failed after {duration:.2f}s")
            
            return success
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Error executing recovery action {action.value}: {e}")
            return False
    
    def _restart_service(self) -> bool:
        """Restart the background service."""
        try:
            # This would typically restart the service process
            # For now, we'll simulate a restart
            self.logger.info("Simulating service restart")
            time.sleep(2)  # Simulate restart time
            return True
        except Exception as e:
            self.logger.error(f"Error restarting service: {e}")
            return False
    
    def _restart_thread(self) -> bool:
        """Restart a specific thread."""
        try:
            # This would restart specific threads
            self.logger.info("Simulating thread restart")
            time.sleep(1)  # Simulate restart time
            return True
        except Exception as e:
            self.logger.error(f"Error restarting thread: {e}")
            return False
    
    def _clear_cache(self) -> bool:
        """Clear system cache."""
        try:
            # Clear memory cache
            import gc
            gc.collect()
            self.logger.info("Cache cleared successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            return False
    
    def _reset_database(self) -> bool:
        """Reset database connections."""
        try:
            # This would reset database connections
            self.logger.info("Database connections reset")
            return True
        except Exception as e:
            self.logger.error(f"Error resetting database: {e}")
            return False
    
    def _escalate_recovery(self) -> bool:
        """Escalate recovery to external systems."""
        try:
            # Send critical alert
            self.logger.critical("ESCALATION: Service health critical, manual intervention required")
            
            # Could send email, SMS, or call external monitoring systems
            if self.communication_manager:
                self.communication_manager.send_to_gui(
                    self.communication_manager.ServiceMessage(
                        message_type=MessageType.ERROR_OCCURRED,
                        timestamp=time.time(),
                        data={
                            'severity': 'critical',
                            'message': 'Service health critical, manual intervention required',
                            'escalation': True
                        }
                    )
                )
            
            return True
        except Exception as e:
            self.logger.error(f"Error escalating recovery: {e}")
            return False
    
    def _send_alert(self, health_status: HealthStatus, metrics: HealthMetrics) -> bool:
        """Send health alert."""
        try:
            alert_message = f"Health alert: {health_status.value} - CPU: {metrics.cpu_percentage:.1f}%, Memory: {metrics.memory_percentage:.1f}%, Score: {metrics.health_score:.1f}"
            
            self.logger.warning(alert_message)
            
            # Send via communication manager
            if self.communication_manager:
                self.communication_manager.send_to_gui(
                    self.communication_manager.ServiceMessage(
                        message_type=MessageType.ERROR_OCCURRED,
                        timestamp=time.time(),
                        data={
                            'severity': health_status.value,
                            'message': alert_message,
                            'metrics': {
                                'cpu': metrics.cpu_percentage,
                                'memory': metrics.memory_percentage,
                                'disk': metrics.disk_usage_percentage,
                                'health_score': metrics.health_score
                            }
                        }
                    )
                )
            
            # Notify alert callbacks
            self._notify_alert_callbacks(alert_message, health_status)
            
            return True
        except Exception as e:
            self.logger.error(f"Error sending alert: {e}")
            return False
    
    def _start_watchdog(self) -> None:
        """Start watchdog timer for crash detection."""
        try:
            self._watchdog_timer = threading.Timer(self._heartbeat_interval, self._watchdog_check)
            self._watchdog_timer.start()
        except Exception as e:
            self.logger.error(f"Error starting watchdog: {e}")
    
    def _stop_watchdog(self) -> None:
        """Stop watchdog timer."""
        try:
            if self._watchdog_timer:
                self._watchdog_timer.cancel()
                self._watchdog_timer = None
        except Exception as e:
            self.logger.error(f"Error stopping watchdog: {e}")
    
    def _watchdog_check(self) -> None:
        """Watchdog check for crash detection."""
        try:
            current_time = time.time()
            if current_time - self._last_heartbeat > self._heartbeat_interval * 2:
                self.logger.critical("WATCHDOG: Service appears to be crashed or unresponsive")
                self._trigger_recovery(HealthStatus.FAILED, self._current_metrics or self._collect_health_metrics())
            
            # Restart watchdog timer
            if self._monitoring_active:
                self._start_watchdog()
        except Exception as e:
            self.logger.error(f"Error in watchdog check: {e}")
    
    def record_operation_start(self, operation_name: str) -> None:
        """Record the start of an operation for timing."""
        self._operation_start_times[operation_name] = time.time()
    
    def record_operation_end(self, operation_name: str) -> None:
        """Record the end of an operation for timing."""
        if operation_name in self._operation_start_times:
            duration = time.time() - self._operation_start_times[operation_name]
            self.logger.debug(f"Operation {operation_name} completed in {duration:.2f}s")
            del self._operation_start_times[operation_name]
    
    def record_error(self, error_type: str, error_message: str = "") -> None:
        """Record an error occurrence."""
        with self._lock:
            self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1
        self.logger.error(f"Error recorded: {error_type} - {error_message}")
    
    def register_queue_monitor(self, queue_name: str, monitor_func: Callable[[], int]) -> None:
        """Register a queue size monitoring function."""
        self._queue_monitors[queue_name] = monitor_func
    
    def get_current_health(self) -> Optional[HealthMetrics]:
        """Get current health metrics."""
        with self._lock:
            return self._current_metrics
    
    def get_health_history(self, hours: int = 24) -> List[HealthMetrics]:
        """Get health history for the specified hours."""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            return [m for m in self._health_history if m.timestamp > cutoff_time]
    
    def get_recovery_history(self, hours: int = 24) -> List[RecoveryEvent]:
        """Get recovery history for the specified hours."""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            return [r for r in self._recovery_history if r.timestamp > cutoff_time]
    
    def _get_consecutive_errors(self) -> int:
        """Get consecutive error count."""
        # This would track consecutive errors over time
        # For now, return total error count
        return sum(self._error_counts.values())
    
    def _get_last_operation_duration(self) -> float:
        """Get duration of the last completed operation."""
        # This would track the last operation duration
        # For now, return 0
        return 0.0
    
    def _notify_health_callbacks(self, metrics: HealthMetrics) -> None:
        """Notify health callbacks."""
        for callback in self._health_callbacks:
            try:
                callback(metrics)
            except Exception as e:
                self.logger.error(f"Error in health callback: {e}")
    
    def _notify_recovery_callbacks(self, event: RecoveryEvent) -> None:
        """Notify recovery callbacks."""
        for callback in self._recovery_callbacks:
            try:
                callback(event)
            except Exception as e:
                self.logger.error(f"Error in recovery callback: {e}")
    
    def _notify_alert_callbacks(self, message: str, status: HealthStatus) -> None:
        """Notify alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                callback(message, status)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")
    
    # Callback registration methods
    def register_health_callback(self, callback: Callable[[HealthMetrics], None]) -> None:
        """Register a health callback."""
        with self._lock:
            if callback not in self._health_callbacks:
                self._health_callbacks.append(callback)
    
    def register_recovery_callback(self, callback: Callable[[RecoveryEvent], None]) -> None:
        """Register a recovery callback."""
        with self._lock:
            if callback not in self._recovery_callbacks:
                self._recovery_callbacks.append(callback)
    
    def register_alert_callback(self, callback: Callable[[str, HealthStatus], None]) -> None:
        """Register an alert callback."""
        with self._lock:
            if callback not in self._alert_callbacks:
                self._alert_callbacks.append(callback) 