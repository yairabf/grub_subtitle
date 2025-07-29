"""
Notification Service for Background Service

This module provides comprehensive notification capabilities including:
- System notifications (toast/desktop alerts)
- Email notifications
- Logging and audit trail
- Notification preferences management
"""

import os
import sys
import smtplib
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

# Platform-specific imports
try:
    import platform
    if platform.system() == "Darwin":  # macOS
        from Foundation import NSUserNotification, NSUserNotificationCenter
        from AppKit import NSApplication, NSApp
    elif platform.system() == "Windows":
        from win10toast import ToastNotifier
    elif platform.system() == "Linux":
        import subprocess
except ImportError:
    pass


class NotificationType(Enum):
    """Types of notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    """Notification channels."""
    SYSTEM = "system"
    EMAIL = "email"
    LOG = "log"
    CONSOLE = "console"


@dataclass
class NotificationEvent:
    """Represents a notification event."""
    event_type: str
    title: str
    message: str
    notification_type: NotificationType
    channels: List[NotificationChannel]
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # 0=normal, 1=high, 2=urgent
    requires_acknowledgment: bool = False
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


@dataclass
class NotificationPreferences:
    """Notification preferences configuration."""
    enabled: bool = True
    system_notifications: bool = True
    email_notifications: bool = False
    log_notifications: bool = True
    console_notifications: bool = False
    
    # Event-specific settings
    events: Dict[str, bool] = field(default_factory=lambda: {
        "service_started": True,
        "service_stopped": True,
        "scan_started": False,
        "scan_completed": True,
        "file_processed": True,  # Enable email notifications for successful processing
        "file_failed": True,
        "file_skipped": False,
        "processing_started": False,
        "processing_completed": True,
        "health_warning": True,
        "health_critical": True,
        "error_occurred": True,
        "retry_attempt": False,
        "batch_completed": True,
        "daily_summary": True
    })
    
    # Email settings
    email: Dict[str, Any] = field(default_factory=lambda: {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "",
        "password": "",
        "from_address": "",
        "to_addresses": [],
        "use_tls": True
    })
    
    # System notification settings
    system: Dict[str, Any] = field(default_factory=lambda: {
        "timeout_seconds": 10,
        "sound_enabled": True,
        "show_icon": True
    })


class NotificationService:
    """
    Comprehensive notification service for background service events.
    
    Supports multiple notification channels:
    - System notifications (toast/desktop alerts)
    - Email notifications
    - Logging and audit trail
    - Console output
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the notification service."""
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Initialize preferences
        self.preferences = self._load_preferences()
        
        # Event history
        self.event_history: List[NotificationEvent] = []
        self.max_history_size = 1000
        
        # Callbacks for external notification handlers
        self.notification_callbacks: List[Callable[[NotificationEvent], None]] = []
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Platform detection
        self.platform = self._detect_platform()
        
        # Initialize platform-specific notification systems
        self._init_platform_notifications()
        
        self.logger.info(f"Notification service initialized for platform: {self.platform}")
    
    def _detect_platform(self) -> str:
        """Detect the current platform."""
        import platform
        return platform.system()
    
    def _init_platform_notifications(self) -> None:
        """Initialize platform-specific notification systems."""
        try:
            if self.platform == "Darwin":  # macOS
                # Initialize macOS notification center
                try:
                    NSApplication.sharedApplication()
                    self._notification_center = NSUserNotificationCenter.defaultUserNotificationCenter()
                except NameError:
                    self.logger.warning("macOS notification classes not available")
                    self._notification_center = None
            elif self.platform == "Windows":
                # Initialize Windows toast notifier
                self._toast_notifier = ToastNotifier()
            elif self.platform == "Linux":
                # Linux notifications will use subprocess calls
                pass
        except Exception as e:
            self.logger.warning(f"Failed to initialize platform notifications: {e}")
    
    def _load_preferences(self) -> NotificationPreferences:
        """Load notification preferences from configuration."""
        try:
            # Extract notification settings from config
            notification_config = self.config.get('notifications', {})
            
            preferences = NotificationPreferences()
            
            # Basic settings
            preferences.enabled = notification_config.get('enabled', True)
            preferences.system_notifications = notification_config.get('system_notifications', True)
            preferences.email_notifications = notification_config.get('email_notifications', False)
            preferences.log_notifications = notification_config.get('log_notifications', True)
            preferences.console_notifications = notification_config.get('console_notifications', False)
            
            # Event-specific settings
            events_config = notification_config.get('events', {})
            for event_name, enabled in events_config.items():
                if event_name in preferences.events:
                    preferences.events[event_name] = enabled
            
            # Email settings
            email_config = notification_config.get('email', {})
            preferences.email.update(email_config)
            
            # System notification settings
            system_config = notification_config.get('system', {})
            preferences.system.update(system_config)
            
            return preferences
            
        except Exception as e:
            self.logger.error(f"Failed to load notification preferences: {e}")
            return NotificationPreferences()
    
    def add_notification_callback(self, callback: Callable[[NotificationEvent], None]) -> None:
        """Add a callback for notification events."""
        with self._lock:
            self.notification_callbacks.append(callback)
    
    def remove_notification_callback(self, callback: Callable[[NotificationEvent], None]) -> None:
        """Remove a notification callback."""
        with self._lock:
            if callback in self.notification_callbacks:
                self.notification_callbacks.remove(callback)
    
    def notify(self, 
               event_type: str,
               title: str,
               message: str,
               notification_type: NotificationType = NotificationType.INFO,
               channels: Optional[List[NotificationChannel]] = None,
               metadata: Optional[Dict[str, Any]] = None,
               priority: int = 0,
               requires_acknowledgment: bool = False) -> NotificationEvent:
        """
        Send a notification through specified channels.
        
        Args:
            event_type: Type of event (e.g., 'service_started', 'file_processed')
            title: Notification title
            message: Notification message
            notification_type: Type of notification (info, success, warning, error, critical)
            channels: List of channels to use (default: based on preferences)
            metadata: Additional metadata for the notification
            priority: Priority level (0=normal, 1=high, 2=urgent)
            requires_acknowledgment: Whether the notification requires acknowledgment
            
        Returns:
            NotificationEvent object
        """
        if not self.preferences.enabled:
            return None
        
        # Check if this event type is enabled
        if not self.preferences.events.get(event_type, True):
            return None
        
        # Create notification event
        event = NotificationEvent(
            event_type=event_type,
            title=title,
            message=message,
            notification_type=notification_type,
            channels=channels or self._get_default_channels(notification_type),
            metadata=metadata or {},
            priority=priority,
            requires_acknowledgment=requires_acknowledgment
        )
        
        # Add to history
        with self._lock:
            self.event_history.append(event)
            if len(self.event_history) > self.max_history_size:
                self.event_history.pop(0)
        
        # Send notifications through channels
        self._send_notifications(event)
        
        # Notify callbacks
        self._notify_callbacks(event)
        
        return event
    
    def _get_default_channels(self, notification_type: NotificationType) -> List[NotificationChannel]:
        """Get default channels based on notification type and preferences."""
        channels = []
        
        if self.preferences.log_notifications:
            channels.append(NotificationChannel.LOG)
        
        if self.preferences.console_notifications:
            channels.append(NotificationChannel.CONSOLE)
        
        # System notifications for important events
        if (self.preferences.system_notifications and 
            notification_type in [NotificationType.WARNING, NotificationType.ERROR, NotificationType.CRITICAL]):
            channels.append(NotificationChannel.SYSTEM)
        
        # Email notifications for critical events
        if (self.preferences.email_notifications and 
            notification_type in [NotificationType.ERROR, NotificationType.CRITICAL]):
            channels.append(NotificationChannel.EMAIL)
        
        return channels
    
    def _send_notifications(self, event: NotificationEvent) -> None:
        """Send notifications through all specified channels."""
        for channel in event.channels:
            try:
                if channel == NotificationChannel.SYSTEM:
                    self._send_system_notification(event)
                elif channel == NotificationChannel.EMAIL:
                    self._send_email_notification(event)
                elif channel == NotificationChannel.LOG:
                    self._send_log_notification(event)
                elif channel == NotificationChannel.CONSOLE:
                    self._send_console_notification(event)
            except Exception as e:
                self.logger.error(f"Failed to send notification through {channel.value}: {e}")
    
    def _send_system_notification(self, event: NotificationEvent) -> None:
        """Send system notification (toast/desktop alert)."""
        try:
            if self.platform == "Darwin":  # macOS
                self._send_macos_notification(event)
            elif self.platform == "Windows":
                self._send_windows_notification(event)
            elif self.platform == "Linux":
                self._send_linux_notification(event)
        except Exception as e:
            self.logger.error(f"Failed to send system notification: {e}")
    
    def _send_macos_notification(self, event: NotificationEvent) -> None:
        """Send macOS notification."""
        try:
            # Check if NSUserNotification is available
            if not hasattr(self, '_notification_center') or self._notification_center is None:
                self.logger.warning("macOS notification center not available")
                return
                
            if 'NSUserNotification' not in globals():
                self.logger.warning("NSUserNotification not available")
                return
                
            notification = NSUserNotification.alloc().init()
            notification.setTitle_(event.title)
            notification.setInformativeText_(event.message)
            notification.setSoundName_("NSUserNotificationDefaultSoundName" if self.preferences.system['sound_enabled'] else None)
            
            # Set timeout
            timeout = self.preferences.system.get('timeout_seconds', 10)
            notification.setDeliveryDate_(datetime.now().timestamp() + timeout)
            
            self._notification_center.deliverNotification_(notification)
            
        except NameError as e:
            self.logger.warning(f"macOS notification classes not available: {e}")
        except Exception as e:
            self.logger.error(f"Failed to send macOS notification: {e}")
    
    def _send_windows_notification(self, event: NotificationEvent) -> None:
        """Send Windows notification."""
        try:
            duration = self.preferences.system.get('timeout_seconds', 10)
            self._toast_notifier.show_toast(
                event.title,
                event.message,
                duration=duration,
                threaded=True
            )
        except Exception as e:
            self.logger.error(f"Failed to send Windows notification: {e}")
    
    def _send_linux_notification(self, event: NotificationEvent) -> None:
        """Send Linux notification using notify-send."""
        try:
            # Map notification types to urgency levels
            urgency_map = {
                NotificationType.INFO: "normal",
                NotificationType.SUCCESS: "normal",
                NotificationType.WARNING: "normal",
                NotificationType.ERROR: "critical",
                NotificationType.CRITICAL: "critical"
            }
            
            urgency = urgency_map.get(event.notification_type, "normal")
            
            # Use notify-send command
            subprocess.run([
                "notify-send",
                "-u", urgency,
                "-t", str(self.preferences.system.get('timeout_seconds', 10) * 1000),
                event.title,
                event.message
            ], check=True)
            
        except Exception as e:
            self.logger.error(f"Failed to send Linux notification: {e}")
    
    def _send_email_notification(self, event: NotificationEvent) -> None:
        """Send email notification with enhanced formatting for processing results and errors."""
        try:
            if not self.preferences.email.get('username') or not self.preferences.email.get('to_addresses'):
                return
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.preferences.email['from_address']
            msg['To'] = ', '.join(self.preferences.email['to_addresses'])
            msg['Subject'] = f"[{event.notification_type.value.upper()}] {event.title}"
            
            # Create enhanced email body based on event type
            body = self._create_email_body(event)
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(self.preferences.email['smtp_server'], self.preferences.email['smtp_port']) as server:
                if self.preferences.email.get('use_tls', True):
                    server.starttls()
                
                server.login(self.preferences.email['username'], self.preferences.email['password'])
                server.send_message(msg)
            
            self.logger.info(f"Email notification sent for event: {event.event_type}")
            
        except Exception as e:
            self.logger.error(f"Failed to send email notification: {e}")
    
    def _create_email_body(self, event: NotificationEvent) -> str:
        """Create formatted email body based on event type."""
        timestamp = event.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # Base template
        body = f"""
Hebrew Subtitle Service - Notification
=====================================

Event Type: {event.event_type}
Notification Type: {event.notification_type.value.upper()}
Timestamp: {timestamp}
Priority: {event.priority}

"""
        
        # Add event-specific formatting
        if event.event_type in ['file_processed', 'file_failed', 'file_skipped']:
            body += self._format_file_processing_email(event)
        elif event.event_type in ['processing_completed', 'batch_completed']:
            body += self._format_batch_summary_email(event)
        elif event.event_type == 'daily_summary':
            body += self._format_daily_summary_email(event)
        elif event.event_type in ['health_warning', 'health_critical']:
            body += self._format_health_email(event)
        elif event.event_type == 'error_occurred':
            body += self._format_error_email(event)
        else:
            body += f"Message: {event.message}\n"
        
        # Add metadata if available
        if event.metadata:
            body += f"\nAdditional Information:\n"
            for key, value in event.metadata.items():
                body += f"  {key}: {value}\n"
        
        body += f"""
---
Hebrew Subtitle Service
Generated at: {timestamp}
        """
        
        return body
    
    def _format_file_processing_email(self, event: NotificationEvent) -> str:
        """Format email body for file processing events."""
        file_path = event.metadata.get('file_path', 'Unknown')
        file_name = Path(file_path).name if file_path != 'Unknown' else 'Unknown'
        
        body = f"File: {file_name}\n"
        body += f"Path: {file_path}\n"
        
        if event.event_type == 'file_processed':
            subtitle_path = event.metadata.get('subtitle_path', 'N/A')
            processing_time = event.metadata.get('processing_time', 'N/A')
            subtitle_count = event.metadata.get('subtitle_count', 'N/A')
            
            body += f"Status: Successfully processed\n"
            body += f"Subtitle file: {subtitle_path}\n"
            body += f"Processing time: {processing_time}\n"
            body += f"Subtitles found: {subtitle_count}\n"
            
        elif event.event_type == 'file_failed':
            error_message = event.metadata.get('error', 'Unknown error')
            retry_count = event.metadata.get('retry_count', 0)
            
            body += f"Status: Processing failed\n"
            body += f"Error: {error_message}\n"
            body += f"Retry attempts: {retry_count}\n"
            
        elif event.event_type == 'file_skipped':
            reason = event.metadata.get('reason', 'Unknown reason')
            
            body += f"Status: Skipped\n"
            body += f"Reason: {reason}\n"
        
        body += f"\nDetails: {event.message}\n"
        return body
    
    def _format_batch_summary_email(self, event: NotificationEvent) -> str:
        """Format email body for batch completion events."""
        total_files = event.metadata.get('total_files', 0)
        successful = event.metadata.get('successful', 0)
        failed = event.metadata.get('failed', 0)
        skipped = event.metadata.get('skipped', 0)
        processing_time = event.metadata.get('processing_time', 'N/A')
        
        body = f"Batch Processing Summary\n"
        body += f"======================\n\n"
        body += f"Total files processed: {total_files}\n"
        body += f"Successfully processed: {successful}\n"
        body += f"Failed: {failed}\n"
        body += f"Skipped: {skipped}\n"
        body += f"Total processing time: {processing_time}\n"
        
        if failed > 0:
            failed_files = event.metadata.get('failed_files', [])
            body += f"\nFailed files:\n"
            for file_info in failed_files[:5]:  # Show first 5 failed files
                body += f"  - {file_info.get('file', 'Unknown')}: {file_info.get('error', 'Unknown error')}\n"
            if len(failed_files) > 5:
                body += f"  ... and {len(failed_files) - 5} more\n"
        
        body += f"\nDetails: {event.message}\n"
        return body
    
    def _format_daily_summary_email(self, event: NotificationEvent) -> str:
        """Format email body for daily summary events."""
        date = event.metadata.get('date', 'Unknown')
        total_files = event.metadata.get('total_files', 0)
        successful = event.metadata.get('successful', 0)
        failed = event.metadata.get('failed', 0)
        skipped = event.metadata.get('skipped', 0)
        total_processing_time = event.metadata.get('total_processing_time', 'N/A')
        
        body = f"Daily Processing Summary - {date}\n"
        body += f"================================\n\n"
        body += f"Files processed today: {total_files}\n"
        body += f"Successfully processed: {successful}\n"
        body += f"Failed: {failed}\n"
        body += f"Skipped: {skipped}\n"
        body += f"Total processing time: {total_processing_time}\n"
        
        # Add success rate
        if total_files > 0:
            success_rate = (successful / total_files) * 100
            body += f"Success rate: {success_rate:.1f}%\n"
        
        body += f"\nDetails: {event.message}\n"
        return body
    
    def _format_health_email(self, event: NotificationEvent) -> str:
        """Format email body for health monitoring events."""
        health_score = event.metadata.get('health_score', 'N/A')
        cpu_usage = event.metadata.get('cpu_usage', 'N/A')
        memory_usage = event.metadata.get('memory_usage', 'N/A')
        disk_usage = event.metadata.get('disk_usage', 'N/A')
        
        body = f"System Health Alert\n"
        body += f"==================\n\n"
        body += f"Health Score: {health_score}\n"
        body += f"CPU Usage: {cpu_usage}\n"
        body += f"Memory Usage: {memory_usage}\n"
        body += f"Disk Usage: {disk_usage}\n"
        
        if event.event_type == 'health_critical':
            body += f"\n⚠️  CRITICAL: Immediate attention required!\n"
        else:
            body += f"\n⚠️  WARNING: System performance may be affected\n"
        
        body += f"\nDetails: {event.message}\n"
        return body
    
    def _format_error_email(self, event: NotificationEvent) -> str:
        """Format email body for error events."""
        error_type = event.metadata.get('error_type', 'Unknown')
        component = event.metadata.get('component', 'Unknown')
        stack_trace = event.metadata.get('stack_trace', '')
        
        body = f"Service Error Report\n"
        body += f"===================\n\n"
        body += f"Error Type: {error_type}\n"
        body += f"Component: {component}\n"
        body += f"Timestamp: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        body += f"\nError Details:\n{event.message}\n"
        
        if stack_trace:
            body += f"\nStack Trace:\n{stack_trace}\n"
        
        body += f"\n⚠️  This error requires immediate attention!\n"
        return body
    
    def _send_log_notification(self, event: NotificationEvent) -> None:
        """Send log notification."""
        log_level_map = {
            NotificationType.INFO: logging.INFO,
            NotificationType.SUCCESS: logging.INFO,
            NotificationType.WARNING: logging.WARNING,
            NotificationType.ERROR: logging.ERROR,
            NotificationType.CRITICAL: logging.CRITICAL
        }
        
        level = log_level_map.get(event.notification_type, logging.INFO)
        
        # Create log message
        log_message = f"[{event.event_type}] {event.title}: {event.message}"
        if event.metadata:
            log_message += f" | Metadata: {json.dumps(event.metadata)}"
        
        self.logger.log(level, log_message)
    
    def _send_console_notification(self, event: NotificationEvent) -> None:
        """Send console notification."""
        # Color codes for different notification types
        color_map = {
            NotificationType.INFO: "\033[36m",      # Cyan
            NotificationType.SUCCESS: "\033[32m",   # Green
            NotificationType.WARNING: "\033[33m",   # Yellow
            NotificationType.ERROR: "\033[31m",     # Red
            NotificationType.CRITICAL: "\033[35m"   # Magenta
        }
        
        color = color_map.get(event.notification_type, "\033[0m")
        reset = "\033[0m"
        
        timestamp = event.timestamp.strftime('%H:%M:%S')
        console_message = f"{color}[{timestamp}] {event.title}: {event.message}{reset}"
        
        print(console_message, file=sys.stderr)
    
    def _notify_callbacks(self, event: NotificationEvent) -> None:
        """Notify registered callbacks."""
        with self._lock:
            callbacks = self.notification_callbacks.copy()
        
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                self.logger.error(f"Error in notification callback: {e}")
    
    def acknowledge_notification(self, event: NotificationEvent, acknowledged_by: str = "user") -> bool:
        """Acknowledge a notification that requires acknowledgment."""
        if not event.requires_acknowledgment:
            return False
        
        with self._lock:
            event.acknowledged = True
            event.acknowledged_at = datetime.now()
            event.acknowledged_by = acknowledged_by
        
        self.logger.info(f"Notification acknowledged: {event.event_type} by {acknowledged_by}")
        return True
    
    def get_event_history(self, 
                         event_type: Optional[str] = None,
                         notification_type: Optional[NotificationType] = None,
                         limit: Optional[int] = None) -> List[NotificationEvent]:
        """Get notification event history with optional filtering."""
        with self._lock:
            history = self.event_history.copy()
        
        # Apply filters
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        
        if notification_type:
            history = [e for e in history if e.notification_type == notification_type]
        
        # Apply limit
        if limit:
            history = history[-limit:]
        
        return history
    
    def clear_history(self) -> None:
        """Clear notification history."""
        with self._lock:
            self.event_history.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get notification statistics."""
        with self._lock:
            total_events = len(self.event_history)
            
            # Count by type
            type_counts = {}
            for event_type in NotificationType:
                type_counts[event_type.value] = len([e for e in self.event_history if e.notification_type == event_type])
            
            # Count by event type
            event_counts = {}
            for event in self.event_history:
                event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
            
            # Count acknowledgments
            acknowledged_count = len([e for e in self.event_history if e.acknowledged])
            
            return {
                'total_events': total_events,
                'type_counts': type_counts,
                'event_counts': event_counts,
                'acknowledged_count': acknowledged_count,
                'pending_acknowledgment': len([e for e in self.event_history if e.requires_acknowledgment and not e.acknowledged])
            }
    
    def update_preferences(self, new_preferences: Dict[str, Any]) -> None:
        """Update notification preferences."""
        with self._lock:
            # Update basic settings
            for key, value in new_preferences.items():
                if hasattr(self.preferences, key):
                    setattr(self.preferences, key, value)
                elif key == 'events' and isinstance(value, dict):
                    self.preferences.events.update(value)
                elif key == 'email' and isinstance(value, dict):
                    self.preferences.email.update(value)
                elif key == 'system' and isinstance(value, dict):
                    self.preferences.system.update(value)
        
        self.logger.info("Notification preferences updated")
    
    def test_notification(self, channel: NotificationChannel) -> bool:
        """Test notification through a specific channel."""
        try:
            test_event = NotificationEvent(
                event_type="test",
                title="Test Notification",
                message="This is a test notification from the Hebrew Subtitle Service",
                notification_type=NotificationType.INFO,
                channels=[channel]
            )
            
            self._send_notifications(test_event)
            return True
            
        except Exception as e:
            self.logger.error(f"Test notification failed: {e}")
            return False
    
    # Convenience methods for specific notification types
    
    def notify_file_processed(self, file_path: str, subtitle_path: str, processing_time: str, subtitle_count: int) -> None:
        """Send notification for successfully processed file."""
        self.notify(
            event_type="file_processed",
            title="File Successfully Processed",
            message=f"Successfully processed {Path(file_path).name}",
            notification_type=NotificationType.SUCCESS,
            channels=[NotificationChannel.EMAIL, NotificationChannel.SYSTEM],
            metadata={
                "file_path": file_path,
                "subtitle_path": subtitle_path,
                "processing_time": processing_time,
                "subtitle_count": subtitle_count
            }
        )
    
    def notify_file_failed(self, file_path: str, error: str, retry_count: int = 0) -> None:
        """Send notification for failed file processing."""
        self.notify(
            event_type="file_failed",
            title="File Processing Failed",
            message=f"Failed to process {Path(file_path).name}: {error}",
            notification_type=NotificationType.ERROR,
            channels=[NotificationChannel.EMAIL, NotificationChannel.SYSTEM],
            metadata={
                "file_path": file_path,
                "error": error,
                "retry_count": retry_count
            }
        )
    
    def notify_file_skipped(self, file_path: str, reason: str) -> None:
        """Send notification for skipped file."""
        self.notify(
            event_type="file_skipped",
            title="File Skipped",
            message=f"Skipped {Path(file_path).name}: {reason}",
            notification_type=NotificationType.WARNING,
            channels=[NotificationChannel.EMAIL],
            metadata={
                "file_path": file_path,
                "reason": reason
            }
        )
    
    def notify_batch_completed(self, total_files: int, successful: int, failed: int, skipped: int, processing_time: str, failed_files: List[Dict[str, str]] = None) -> None:
        """Send notification for batch processing completion."""
        self.notify(
            event_type="batch_completed",
            title="Batch Processing Completed",
            message=f"Processed {total_files} files: {successful} successful, {failed} failed, {skipped} skipped",
            notification_type=NotificationType.SUCCESS if failed == 0 else NotificationType.WARNING,
            channels=[NotificationChannel.EMAIL],
            metadata={
                "total_files": total_files,
                "successful": successful,
                "failed": failed,
                "skipped": skipped,
                "processing_time": processing_time,
                "failed_files": failed_files or []
            }
        )
    
    def notify_daily_summary(self, date: str, total_files: int, successful: int, failed: int, skipped: int, total_processing_time: str) -> None:
        """Send daily processing summary notification."""
        self.notify(
            event_type="daily_summary",
            title="Daily Processing Summary",
            message=f"Daily summary for {date}: {total_files} files processed",
            notification_type=NotificationType.INFO,
            channels=[NotificationChannel.EMAIL],
            metadata={
                "date": date,
                "total_files": total_files,
                "successful": successful,
                "failed": failed,
                "skipped": skipped,
                "total_processing_time": total_processing_time
            }
        )
    
    def notify_health_warning(self, health_score: float, cpu_usage: float, memory_usage: float, disk_usage: float, message: str) -> None:
        """Send health warning notification."""
        self.notify(
            event_type="health_warning",
            title="System Health Warning",
            message=message,
            notification_type=NotificationType.WARNING,
            channels=[NotificationChannel.EMAIL, NotificationChannel.SYSTEM],
            metadata={
                "health_score": health_score,
                "cpu_usage": f"{cpu_usage:.1f}%",
                "memory_usage": f"{memory_usage:.1f}%",
                "disk_usage": f"{disk_usage:.1f}%"
            }
        )
    
    def notify_health_critical(self, health_score: float, cpu_usage: float, memory_usage: float, disk_usage: float, message: str) -> None:
        """Send critical health notification."""
        self.notify(
            event_type="health_critical",
            title="System Health Critical",
            message=message,
            notification_type=NotificationType.CRITICAL,
            channels=[NotificationChannel.EMAIL, NotificationChannel.SYSTEM],
            priority=2,
            metadata={
                "health_score": health_score,
                "cpu_usage": f"{cpu_usage:.1f}%",
                "memory_usage": f"{memory_usage:.1f}%",
                "disk_usage": f"{disk_usage:.1f}%"
            }
        )
    
    def notify_error(self, error_type: str, component: str, message: str, stack_trace: str = "") -> None:
        """Send error notification."""
        self.notify(
            event_type="error_occurred",
            title=f"Service Error: {error_type}",
            message=message,
            notification_type=NotificationType.ERROR,
            channels=[NotificationChannel.EMAIL, NotificationChannel.SYSTEM],
            priority=2,
            metadata={
                "error_type": error_type,
                "component": component,
                "stack_trace": stack_trace
            }
        ) 