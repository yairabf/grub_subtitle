"""
Directory Scanner Service

Handles recursive directory scanning, video file detection, and change tracking
for the background subtitle service.
"""

import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .file_tracker import FileTracker, FileInfo, ProcessingStatus
from datetime import datetime, timedelta
from .service_communication import ServiceCommunicationManager, MessageType


@dataclass
class ScanConfig:
    """Configuration for directory scanning."""
    scan_interval_minutes: int = 30
    max_scan_depth: int = 10
    video_extensions: Set[str] = field(default_factory=lambda: {
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp'
    })
    min_file_size_mb: int = 10
    max_file_size_gb: int = 50
    exclude_patterns: List[str] = field(default_factory=lambda: [
        '*.tmp', '*.temp', '*.part', '*.download', '*.crdownload',
        'System Volume Information', '.DS_Store', 'Thumbs.db'
    ])
    include_hidden: bool = False
    max_workers: int = 4


@dataclass
class ScanResult:
    """Result of a directory scan."""
    scan_id: str
    timestamp: datetime
    total_files_found: int
    new_files: List[FileInfo]
    modified_files: List[FileInfo]
    unchanged_files: List[FileInfo]
    scan_duration_seconds: float
    errors: List[str] = field(default_factory=list)


@dataclass
class VideoFileInfo:
    """Information about a detected video file."""
    path: Path
    size_bytes: int
    modification_time: datetime
    creation_time: datetime
    file_hash: str
    is_valid_video: bool = True
    error_message: Optional[str] = None


class DirectoryScanner:
    """
    Recursive directory scanner for video files with configurable scan intervals.
    
    Features:
    - Configurable scan intervals and depth
    - Video file detection and validation
    - Efficient change detection using file tracking
    - Multi-threaded scanning for performance
    - Progress reporting and error handling
    """
    
    def __init__(
        self,
        config: ScanConfig,
        file_tracker: FileTracker,
        communication_manager: ServiceCommunicationManager,
        logger: Optional[logging.Logger] = None
    ):
        self.config = config
        self.file_tracker = file_tracker
        self.communication_manager = communication_manager
        self.logger = logger or logging.getLogger(__name__)
        
        self._scan_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_scanning = False
        self._last_scan_time: Optional[datetime] = None
        self._scan_lock = threading.Lock()
        
        # Statistics
        self._total_scans = 0
        self._total_files_processed = 0
        self._total_new_files_found = 0
        
    def start_scanning(self, directories: List[str]) -> bool:
        """
        Start continuous scanning of the specified directories.
        
        Args:
            directories: List of directory paths to scan
            
        Returns:
            True if scanning started successfully, False otherwise
        """
        if self._scan_thread and self._scan_thread.is_alive():
            self.logger.warning("Scanning already in progress")
            return False
            
        if not directories:
            self.logger.error("No directories specified for scanning")
            return False
            
        # Validate directories exist
        valid_directories = []
        for directory in directories:
            if os.path.exists(directory) and os.path.isdir(directory):
                valid_directories.append(directory)
            else:
                self.logger.warning(f"Directory does not exist or is not accessible: {directory}")
                
        if not valid_directories:
            self.logger.error("No valid directories to scan")
            return False
            
        self._stop_event.clear()
        self._scan_thread = threading.Thread(
            target=self._scan_loop,
            args=(valid_directories,),
            daemon=True,
            name="DirectoryScanner"
        )
        self._scan_thread.start()
        
        self.logger.info(f"Started directory scanning for {len(valid_directories)} directories")
        self.communication_manager.send_status_update(
            f"Directory scanning started for {len(valid_directories)} directories"
        )
        return True
        
    def stop_scanning(self) -> bool:
        """
        Stop continuous scanning.
        
        Returns:
            True if scanning stopped successfully, False otherwise
        """
        if not self._scan_thread or not self._scan_thread.is_alive():
            self.logger.warning("No scanning in progress")
            return False
            
        self._stop_event.set()
        self._scan_thread.join(timeout=10)
        
        if self._scan_thread.is_alive():
            self.logger.warning("Scan thread did not stop gracefully")
            return False
            
        self.logger.info("Directory scanning stopped")
        self.communication_manager.send_status_update("Directory scanning stopped")
        return True
        
    def scan_once(self, directories: List[str]) -> ScanResult:
        """
        Perform a single scan of the specified directories.
        
        Args:
            directories: List of directory paths to scan
            
        Returns:
            ScanResult containing scan information
        """
        start_time = time.time()
        scan_id = f"scan_{int(start_time)}"
        
        self.logger.info(f"Starting single scan {scan_id} for {len(directories)} directories")
        
        with self._scan_lock:
            self._is_scanning = True
            
        try:
            # Send scan start notification
            self.communication_manager.send_scan_started(
                scan_id=scan_id,
                directories=directories,
                timestamp=datetime.now()
            )
            
            # Find all video files with progress reporting
            all_video_files = self._find_video_files_with_progress(directories, scan_id)
            
            # Compare with tracked files
            new_files, modified_files, unchanged_files = self._compare_with_tracked_files(all_video_files)
            
            # Update file tracker
            self._update_file_tracker(new_files, modified_files)
            
            scan_duration = time.time() - start_time
            self._last_scan_time = datetime.now()
            self._total_scans += 1
            self._total_files_processed += len(all_video_files)
            self._total_new_files_found += len(new_files)
            
            result = ScanResult(
                scan_id=scan_id,
                timestamp=self._last_scan_time,
                total_files_found=len(all_video_files),
                new_files=new_files,
                modified_files=modified_files,
                unchanged_files=unchanged_files,
                scan_duration_seconds=scan_duration
            )
            
            self.logger.info(
                f"Scan {scan_id} completed in {scan_duration:.2f}s: "
                f"{len(new_files)} new, {len(modified_files)} modified, "
                f"{len(unchanged_files)} unchanged files"
            )
            
            # Send scan completion notification
            self.communication_manager.send_scan_completed(
                scan_id=scan_id,
                total_files=len(all_video_files),
                new_files=len(new_files),
                modified_files=len(modified_files),
                unchanged_files=len(unchanged_files),
                scan_duration=scan_duration,
                errors=result.errors
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error during scan {scan_id}: {e}")
            error_result = ScanResult(
                scan_id=scan_id,
                timestamp=datetime.now(),
                total_files_found=0,
                new_files=[],
                modified_files=[],
                unchanged_files=[],
                scan_duration_seconds=time.time() - start_time,
                errors=[str(e)]
            )
            
            # Send scan error notification
            self.communication_manager.send_scan_error(
                scan_id=scan_id,
                error_message=str(e),
                scan_duration=error_result.scan_duration_seconds
            )
            
            return error_result
        finally:
            with self._scan_lock:
                self._is_scanning = False
                
    def _scan_loop(self, directories: List[str]) -> None:
        """Main scanning loop that runs continuously."""
        self.logger.info(f"Starting scan loop for directories: {directories}")
        
        while not self._stop_event.is_set():
            try:
                # Perform scan
                result = self.scan_once(directories)
                
                # Send results if there are new/modified files
                if result.new_files or result.modified_files:
                    self.communication_manager.send_scan_results(
                        scan_id=result.scan_id,
                        new_files=result.new_files,
                        modified_files=result.modified_files,
                        total_files=result.total_files_found
                    )
                
                # Wait for next scan interval
                self._stop_event.wait(self.config.scan_interval_minutes * 60)
                
            except Exception as e:
                self.logger.error(f"Error in scan loop: {e}")
                # Wait a shorter time before retrying
                self._stop_event.wait(60)  # 1 minute
                
        self.logger.info("Scan loop stopped")
        
    def _find_video_files(self, directories: List[str]) -> List[VideoFileInfo]:
        """Find all video files in the specified directories."""
        video_files = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_dir = {
                executor.submit(self._scan_directory, directory): directory
                for directory in directories
            }
            
            for future in as_completed(future_to_dir):
                directory = future_to_dir[future]
                try:
                    files = future.result()
                    video_files.extend(files)
                except Exception as e:
                    self.logger.error(f"Error scanning directory {directory}: {e}")
                    
        return video_files
        
    def _find_video_files_with_progress(self, directories: List[str], scan_id: str) -> List[VideoFileInfo]:
        """Find all video files with progress reporting."""
        video_files = []
        total_directories = len(directories)
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_dir = {
                executor.submit(self._scan_directory, directory): directory
                for directory in directories
            }
            
            completed_dirs = 0
            for future in as_completed(future_to_dir):
                directory = future_to_dir[future]
                completed_dirs += 1
                
                try:
                    files = future.result()
                    video_files.extend(files)
                    
                    # Send progress update
                    progress_percent = (completed_dirs / total_directories) * 100
                    self.communication_manager.send_scan_progress(
                        scan_id=scan_id,
                        directories_completed=completed_dirs,
                        total_directories=total_directories,
                        files_found=len(video_files),
                        progress_percent=progress_percent
                    )
                    
                except Exception as e:
                    self.logger.error(f"Error scanning directory {directory}: {e}")
                    
        return video_files
        
    def _scan_directory(self, directory: str) -> List[VideoFileInfo]:
        """Scan a single directory for video files."""
        video_files = []
        
        try:
            for root, dirs, files in os.walk(directory):
                # Check scan depth
                depth = root.replace(directory, '').count(os.sep)
                if depth > self.config.max_scan_depth:
                    continue
                    
                # Filter directories
                dirs[:] = [d for d in dirs if self._should_include_directory(d)]
                
                for file in files:
                    if self._should_include_file(file):
                        file_path = Path(root) / file
                        video_info = self._analyze_video_file(file_path)
                        if video_info:
                            video_files.append(video_info)
                            
        except Exception as e:
            self.logger.error(f"Error scanning directory {directory}: {e}")
            
        return video_files
        
    def _should_include_directory(self, dirname: str) -> bool:
        """Check if a directory should be included in scanning."""
        if not self.config.include_hidden and dirname.startswith('.'):
            return False
            
        for pattern in self.config.exclude_patterns:
            if pattern.startswith('*'):
                if dirname.endswith(pattern[1:]):
                    return False
            elif pattern == dirname:
                return False
                
        return True
        
    def _should_include_file(self, filename: str) -> bool:
        """Check if a file should be included in scanning."""
        if not self.config.include_hidden and filename.startswith('.'):
            return False
            
        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.config.video_extensions:
            return False
            
        # Check exclude patterns
        for pattern in self.config.exclude_patterns:
            if pattern.startswith('*'):
                if filename.endswith(pattern[1:]):
                    return False
            elif pattern == filename:
                return False
                
        return True
        
    def _analyze_video_file(self, file_path: Path) -> Optional[VideoFileInfo]:
        """Analyze a video file and return information about it with validation."""
        try:
            stat = file_path.stat()
            
            # Check file size
            size_mb = stat.st_size / (1024 * 1024)
            if size_mb < self.config.min_file_size_mb:
                return None
                
            size_gb = size_mb / 1024
            if size_gb > self.config.max_file_size_gb:
                return None
                
            # Validate video file format
            if not self._validate_video_file(file_path):
                self.logger.warning(f"Invalid video file format: {file_path}")
                return None
                
            # Calculate file hash
            file_hash = self.file_tracker.calculate_file_hash(str(file_path))
            
            return VideoFileInfo(
                path=file_path,
                size_bytes=stat.st_size,
                modification_time=datetime.fromtimestamp(stat.st_mtime),
                creation_time=datetime.fromtimestamp(stat.st_ctime),
                file_hash=file_hash,
                is_valid_video=True
            )
            
        except Exception as e:
            self.logger.warning(f"Error analyzing file {file_path}: {e}")
            return None
            
    def _validate_video_file(self, file_path: Path) -> bool:
        """Validate that a file is actually a valid video file."""
        try:
            # Check file extension
            extension = file_path.suffix.lower()
            if extension not in self.config.video_extensions:
                return False
                
            # Read file header to validate format
            with open(file_path, 'rb') as f:
                header = f.read(16)  # Read first 16 bytes
                
                if not header:
                    return False
                    
                # Check for common video file signatures
                if extension == '.mp4' or extension == '.m4v':
                    # MP4 files start with 'ftyp' box
                    if b'ftyp' not in header[4:8]:
                        return False
                        
                elif extension == '.avi':
                    # AVI files start with 'RIFF' and 'AVI '
                    if not (header.startswith(b'RIFF') and header[8:12] == b'AVI '):
                        return False
                        
                elif extension == '.mkv':
                    # MKV files start with EBML header
                    if not header.startswith(b'\x1a\x45\xdf\xa3'):
                        return False
                        
                elif extension == '.mov':
                    # MOV files start with 'ftyp' box
                    if b'ftyp' not in header[4:8]:
                        return False
                        
                elif extension == '.wmv':
                    # WMV files start with ASF header
                    if not header.startswith(b'\x30\x26\xb2\x75'):
                        return False
                        
                elif extension == '.flv':
                    # FLV files start with 'FLV'
                    if not header.startswith(b'FLV'):
                        return False
                        
                elif extension == '.webm':
                    # WebM files start with EBML header
                    if not header.startswith(b'\x1a\x45\xdf\xa3'):
                        return False
                        
                elif extension == '.3gp':
                    # 3GP files start with 'ftyp' box
                    if b'ftyp' not in header[4:8]:
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.warning(f"Error validating video file {file_path}: {e}")
            return False
        
    def _compare_with_tracked_files(self, video_files: List[VideoFileInfo]) -> tuple[List[FileInfo], List[FileInfo], List[FileInfo]]:
        """Compare found video files with tracked files using efficient change detection."""
        new_files = []
        modified_files = []
        unchanged_files = []
        
        # Batch get file info for efficiency
        file_paths = [str(vf.path) for vf in video_files]
        tracked_files_dict = self.file_tracker.get_files_batch(file_paths)
        
        for video_file in video_files:
            file_path = str(video_file.path)
            tracked_file = tracked_files_dict.get(file_path)
            
            if not tracked_file:
                # New file - check if it's actually new or just not tracked
                if self._is_file_new(video_file):
                    file_info = FileInfo(
                        file_path=file_path,
                        file_hash=video_file.file_hash,
                        file_size=video_file.size_bytes,
                        file_modified_time=video_file.modification_time.timestamp(),
                        processing_status=ProcessingStatus.PENDING,
                        created_at=datetime.now().timestamp()
                    )
                    new_files.append(file_info)
                else:
                    # File exists but not tracked - add to tracker
                    file_info = FileInfo(
                        file_path=file_path,
                        file_hash=video_file.file_hash,
                        file_size=video_file.size_bytes,
                        file_modified_time=video_file.modification_time.timestamp(),
                        processing_status=ProcessingStatus.PENDING,
                        created_at=datetime.now().timestamp()
                    )
                    new_files.append(file_info)
                    
            elif self._has_file_changed(tracked_file, video_file):
                # Modified file - use efficient change detection
                tracked_file.file_hash = video_file.file_hash
                tracked_file.file_size = video_file.size_bytes
                tracked_file.file_modified_time = video_file.modification_time.timestamp()
                tracked_file.processing_status = ProcessingStatus.PENDING
                modified_files.append(tracked_file)
                
            else:
                # Unchanged file
                unchanged_files.append(tracked_file)
                
        return new_files, modified_files, unchanged_files
        
    def _is_file_new(self, video_file: VideoFileInfo) -> bool:
        """Check if a file is actually new based on multiple criteria."""
        # A file is considered new if it meets these basic criteria:
        
        # 1. It's not a temporary or partial file
        filename = video_file.path.name.lower()
        is_not_temp = not any(pattern in filename for pattern in [
            '.tmp', '.temp', '.part', '.download', '.crdownload', '.partial'
        ])
        
        # 2. It has a valid video extension
        has_valid_extension = video_file.path.suffix.lower() in self.config.video_extensions
        
        # 3. It's a reasonable size for a video file (not a small fragment)
        is_reasonable_size = video_file.size_bytes > self.config.min_file_size_mb * 1024 * 1024
        
        # 4. It's a valid video file (not corrupted or invalid)
        is_valid_video = video_file.is_valid_video
        
        # File is new if it meets all the basic criteria
        # We don't check age anymore since files in a new directory might be older
        return (is_not_temp and has_valid_extension and is_reasonable_size and is_valid_video)
        
    def _has_file_changed(self, tracked_file: FileInfo, video_file: VideoFileInfo) -> bool:
        """Efficiently check if a file has changed using multiple criteria."""
        # Quick check: modification time changed significantly
        tracked_time = datetime.fromtimestamp(tracked_file.file_modified_time)
        time_diff = abs((tracked_time - video_file.modification_time).total_seconds())
        if time_diff > 1:  # More than 1 second difference
            return True
            
        # Size check
        if tracked_file.file_size != video_file.size_bytes:
            return True
            
        # Hash check (most reliable but expensive)
        if tracked_file.file_hash != video_file.file_hash:
            return True
            
        return False
        
    def _update_file_tracker(self, new_files: List[FileInfo], modified_files: List[FileInfo]) -> None:
        """Update the file tracker with new and modified files."""
        for file_info in new_files:
            self.file_tracker.add_file(file_info)
            
        for file_info in modified_files:
            self.file_tracker.update_file(file_info)
            
    def get_scan_statistics(self) -> Dict:
        """Get scanning statistics."""
        return {
            'total_scans': self._total_scans,
            'total_files_processed': self._total_files_processed,
            'total_new_files_found': self._total_new_files_found,
            'last_scan_time': self._last_scan_time.isoformat() if self._last_scan_time else None,
            'is_scanning': self._is_scanning,
            'scan_interval_minutes': self.config.scan_interval_minutes
        }
        
    def is_scanning(self) -> bool:
        """Check if scanner is currently scanning."""
        return self._is_scanning
    
    def get_files_batch(self, max_files: int = 100) -> List[FileInfo]:
        """
        Get a batch of files that need processing.
        
        Args:
            max_files: Maximum number of files to return
            
        Returns:
            List of FileInfo objects for files that need processing
        """
        try:
            # Use FileTracker to get pending files
            files_to_process = self.file_tracker.get_pending_files(max_files)
            self.logger.debug(f"Retrieved {len(files_to_process)} files for processing")
            return files_to_process
            
        except Exception as e:
            self.logger.error(f"Error getting files batch: {e}")
            return []
    
    def get_new_files_for_processing(self, directories: List[str], max_files: int = 100) -> List[FileInfo]:
        """
        Get files that need processing from the database or scan if database is empty.
        
        Args:
            directories: List of directories to scan
            max_files: Maximum number of files to return
            
        Returns:
            List of FileInfo objects for files that need processing
        """
        try:
            # First try to get pending files from the database
            pending_files = self.file_tracker.get_pending_files(max_files)
            
            # If no pending files in database, perform a scan to discover new files
            if not pending_files:
                self.logger.info("No pending files in database, performing initial scan...")
                scan_result = self.scan_once(directories)
                pending_files = scan_result.new_files[:max_files]
                self.logger.info(f"Initial scan found {len(pending_files)} new files")
            else:
                self.logger.info(f"Found {len(pending_files)} files for processing from database")
            
            return pending_files
            
        except Exception as e:
            self.logger.error(f"Error getting new files for processing: {e}")
            return [] 