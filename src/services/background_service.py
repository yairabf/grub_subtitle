"""
Background Service for Automatic Media Library Processing

This module provides the core background service functionality that monitors
media library directories and automatically processes new video files to ensure
Hebrew subtitles are available.
"""

import threading
import time
import logging
import queue
from enum import Enum
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager

from config.config_manager import ConfigManager
from logging_system.subtitle_logger import SubtitleLogger
from services.subtitle_service import SubtitleService
from services.file_tracker import FileTracker, ProcessingStatus
from services.directory_scanner import DirectoryScanner


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


@dataclass
class ProcessingTask:
    """Represents a file processing task."""
    file_path: str
    task_id: str
    priority: int = 0  # 0=normal, 1=high, 2=urgent
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    processing_started: Optional[datetime] = None
    processing_completed: Optional[datetime] = None
    status: str = "pending"  # pending, processing, completed, failed, retry
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


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
        
        # Initialize services
        self.subtitle_service = SubtitleService()
        self.file_tracker = FileTracker(config)
        self.directory_scanner = DirectoryScanner(config, self.file_tracker)
        
        # Service state management with enhanced thread safety
        self._state = ServiceState.STOPPED
        self._status = ServiceStatus(state=ServiceState.STOPPED)
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._state_condition = threading.Condition(self._lock)  # Condition for state changes
        
        # Service threads
        self._main_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        
        # File processing queue and workers
        self._processing_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._worker_threads: List[threading.Thread] = []
        self._worker_stop_events: List[threading.Event] = []
        
        # Processing statistics
        self._processing_stats = {
            'tasks_queued': 0,
            'tasks_processing': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'tasks_retried': 0
        }
        
        # Callbacks for status updates
        self._status_callbacks: List[Callable[[ServiceStatus], None]] = []
        self._state_callbacks: List[Callable[[ServiceState, ServiceState], None]] = []
        
        # State history for debugging
        self._state_history: List[Dict[str, Any]] = []
        
        # Load configuration
        self._load_configuration()
        
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
                
                # Start worker threads
                self._start_worker_threads()
                
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
                
                # Stop worker threads
                self._stop_worker_threads()
                
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
            service_config = self.config_manager.get_service_config()
            
            # Load processing configuration
            processing_config = service_config.get('processing', {})
            self._queue_size = processing_config.get('queue_size', 100)
            self._worker_threads_count = processing_config.get('worker_threads', 3)
            self._processing_timeout = processing_config.get('processing_timeout_seconds', 600)
            self._retry_failed_files = processing_config.get('retry_failed_files', True)
            self._max_retry_attempts = processing_config.get('max_retry_attempts', 3)
            self._retry_delay = processing_config.get('retry_delay_seconds', 60)
            self._prioritize_new_files = processing_config.get('prioritize_new_files', True)
            self._skip_existing_subtitles = processing_config.get('skip_existing_subtitles', True)
            
            # Load scanning configuration
            scanning_config = service_config.get('scanning', {})
            self._scan_interval = scanning_config.get('scan_timeout_seconds', 300)
            self._max_files_per_scan = scanning_config.get('max_files_per_scan', 1000)
            self._parallel_scanning = scanning_config.get('parallel_scanning', True)
            
            self.logger.info(f"Loaded processing configuration: {self._worker_threads_count} workers, "
                           f"queue size {self._queue_size}, timeout {self._processing_timeout}s")
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise
    
    def _validate_configuration(self) -> bool:
        """
        Validate service configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        if self._worker_threads_count <= 0:
            self.logger.error("Worker threads count must be greater than 0")
            return False
        
        if self._queue_size <= 0:
            self.logger.error("Queue size must be greater than 0")
            return False
        
        if self._processing_timeout <= 0:
            self.logger.error("Processing timeout must be greater than 0")
            return False
        
        return True
    
    def _start_worker_threads(self) -> None:
        """Start worker threads for file processing."""
        self.logger.info(f"Starting {self._worker_threads_count} worker threads")
        
        for i in range(self._worker_threads_count):
            stop_event = threading.Event()
            worker_thread = threading.Thread(
                target=self._worker_loop,
                args=(i, stop_event),
                name=f"Worker-{i}",
                daemon=True
            )
            
            self._worker_stop_events.append(stop_event)
            self._worker_threads.append(worker_thread)
            worker_thread.start()
        
        self.logger.info("All worker threads started")
    
    def _stop_worker_threads(self) -> None:
        """Stop all worker threads."""
        self.logger.info("Stopping worker threads")
        
        # Signal all workers to stop
        for stop_event in self._worker_stop_events:
            stop_event.set()
        
        # Wait for workers to finish
        for i, worker_thread in enumerate(self._worker_threads):
            if worker_thread.is_alive():
                worker_thread.join(timeout=5.0)
                if worker_thread.is_alive():
                    self.logger.warning(f"Worker thread {i} did not stop gracefully")
        
        self._worker_threads.clear()
        self._worker_stop_events.clear()
        self.logger.info("All worker threads stopped")
    
    def _worker_loop(self, worker_id: int, stop_event: threading.Event) -> None:
        """Main loop for worker threads."""
        self.logger.info(f"Worker {worker_id} started")
        
        try:
            while not stop_event.is_set():
                try:
                    # Get task from queue with timeout
                    priority, task = self._processing_queue.get(timeout=1.0)
                    
                    # Process the task
                    self._process_task(task, worker_id)
                    
                    # Mark task as done
                    self._processing_queue.task_done()
                    
                except queue.Empty:
                    # No tasks available, continue loop
                    continue
                except Exception as e:
                    self.logger.error(f"Worker {worker_id} error: {e}")
                    time.sleep(1.0)  # Brief pause before continuing
                    
        except Exception as e:
            self.logger.error(f"Worker {worker_id} fatal error: {e}")
        finally:
            self.logger.info(f"Worker {worker_id} stopped")
    
    def _process_task(self, task: ProcessingTask, worker_id: int) -> None:
        """Process a single file processing task."""
        self.logger.info(f"Worker {worker_id} processing: {task.file_path}")
        
        # Update task status
        task.status = "processing"
        task.processing_started = datetime.now()
        self._processing_stats['tasks_processing'] += 1
        
        try:
            # Check if file still exists
            if not Path(task.file_path).exists():
                raise FileNotFoundError(f"File no longer exists: {task.file_path}")
            
            # Check if we should skip existing subtitles
            if self._skip_existing_subtitles:
                existing_subtitle = self._find_existing_subtitle(task.file_path)
                if existing_subtitle:
                    self.logger.info(f"Skipping {task.file_path} - subtitle already exists: {existing_subtitle}")
                    task.status = "completed"
                    task.result = {"skipped": True, "reason": "subtitle_exists", "existing_subtitle": existing_subtitle}
                    self._processing_stats['tasks_completed'] += 1
                    return
            
            # Process the file using SubtitleService
            result = self._process_video_file(task.file_path)
            
            # Update task with result
            task.status = "completed"
            task.processing_completed = datetime.now()
            task.result = result
            self._processing_stats['tasks_completed'] += 1
            
            # Update file tracker
            self.file_tracker.update_file_status(
                task.file_path, 
                ProcessingStatus.COMPLETED if result.get('success') else ProcessingStatus.FAILED,
                result
            )
            
            # Update service status
            if result.get('success'):
                self._update_status(files_processed=self._status.files_processed + 1)
            else:
                self._update_status(files_failed=self._status.files_failed + 1)
            
            self.logger.info(f"Worker {worker_id} completed: {task.file_path}")
            
        except Exception as e:
            self.logger.error(f"Worker {worker_id} failed to process {task.file_path}: {e}")
            
            # Handle retry logic
            if task.retry_count < task.max_retries and self._retry_failed_files:
                task.retry_count += 1
                task.status = "retry"
                task.error_message = str(e)
                self._processing_stats['tasks_retried'] += 1
                
                # Re-queue with lower priority and delay
                time.sleep(self._retry_delay)
                self._queue_file_for_processing(task.file_path, priority=task.priority - 1)
                
            else:
                # Final failure
                task.status = "failed"
                task.error_message = str(e)
                task.processing_completed = datetime.now()
                self._processing_stats['tasks_failed'] += 1
                
                # Update file tracker
                self.file_tracker.update_file_status(task.file_path, ProcessingStatus.FAILED, {"error": str(e)})
                
                # Update service status
                self._update_status(files_failed=self._status.files_failed + 1)
        
        finally:
            self._processing_stats['tasks_processing'] -= 1
    
    def _process_video_file(self, file_path: str) -> Dict[str, Any]:
        """Process a video file using SubtitleService."""
        try:
            self.logger.info(f"Processing video file: {file_path}")
            
            # Use SubtitleService to process the file
            # The service will try to find Hebrew subtitles first, then translate if needed
            success = self.subtitle_service.process_video_file_with_validation(file_path)
            
            if success:
                return {
                    "success": True,
                    "message": "File processed successfully",
                    "subtitle_found": True,
                    "subtitle_downloaded": True,
                    "subtitle_translated": False  # Will be determined by actual processing
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to process file",
                    "subtitle_found": False,
                    "subtitle_downloaded": False,
                    "subtitle_translated": False
                }
                
        except Exception as e:
            self.logger.error(f"Error processing video file {file_path}: {e}")
            return {
                "success": False,
                "message": str(e),
                "subtitle_found": False,
                "subtitle_downloaded": False,
                "subtitle_translated": False
            }
    
    def _find_existing_subtitle(self, video_path: str) -> Optional[str]:
        """Check if a subtitle file already exists for the video."""
        video_path = Path(video_path)
        video_dir = video_path.parent
        video_name = video_path.stem
        
        # Check for Hebrew subtitle files
        hebrew_patterns = [
            f"{video_name}.heb.srt",
            f"{video_name}.he.srt",
            f"{video_name}.Hebrew.srt",
            f"{video_name}.heb",
            f"{video_name}.he"
        ]
        
        for pattern in hebrew_patterns:
            subtitle_path = video_dir / pattern
            if subtitle_path.exists():
                return str(subtitle_path)
        
        return None
    
    def _queue_file_for_processing(self, file_path: str, priority: int = 0) -> bool:
        """Add a file to the processing queue."""
        try:
            # Create processing task
            task = ProcessingTask(
                file_path=file_path,
                task_id=f"task_{int(time.time() * 1000)}",
                priority=priority,
                max_retries=self._max_retry_attempts
            )
            
            # Add to queue (priority queue uses negative priority for higher priority first)
            self._processing_queue.put((-priority, task))
            self._processing_stats['tasks_queued'] += 1
            
            self.logger.debug(f"Queued file for processing: {file_path} (priority: {priority})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to queue file {file_path}: {e}")
            return False
    
    def _scan_and_queue_files(self) -> None:
        """Scan directories for new files and queue them for processing."""
        try:
            self.logger.info("Starting directory scan for new files")
            
            # Get files that need processing
            files_to_process = self.directory_scanner.get_files_batch(
                max_files=self._max_files_per_scan
            )
            
            if not files_to_process:
                self.logger.info("No new files found for processing")
                return
            
            self.logger.info(f"Found {len(files_to_process)} files to process")
            
            # Queue files for processing
            for file_info in files_to_process:
                priority = 1 if self._prioritize_new_files and file_info.is_new else 0
                self._queue_file_for_processing(file_info.file_path, priority=priority)
            
            self.logger.info(f"Queued {len(files_to_process)} files for processing")
            
        except Exception as e:
            self.logger.error(f"Error during directory scan: {e}")
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            'queue_size': self._processing_queue.qsize(),
            'active_workers': len([w for w in self._worker_threads if w.is_alive()]),
            'total_workers': self._worker_threads_count,
            'tasks_queued': self._processing_stats['tasks_queued'],
            'tasks_processing': self._processing_stats['tasks_processing'],
            'tasks_completed': self._processing_stats['tasks_completed'],
            'tasks_failed': self._processing_stats['tasks_failed'],
            'tasks_retried': self._processing_stats['tasks_retried']
        } 