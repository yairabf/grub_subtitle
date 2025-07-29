"""
File Tracking System for Background Service

This module provides a SQLite-based file tracking system that monitors
which video files have been processed for Hebrew subtitles, tracks
processing status, and prevents unnecessary reprocessing.
"""

import sqlite3
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from logging_system.subtitle_logger import SubtitleLogger


class ProcessingStatus(Enum):
    """Processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class OperationType(Enum):
    """Subtitle operation types."""
    DOWNLOAD = "download"
    TRANSLATE = "translate"
    VALIDATE = "validate"


@dataclass
class FileInfo:
    """File information for tracking."""
    file_path: str
    file_hash: str
    file_size: int
    file_modified_time: float
    processing_status: ProcessingStatus
    processing_start_time: Optional[float] = None
    processing_end_time: Optional[float] = None
    processing_duration: Optional[float] = None
    error_message: Optional[str] = None
    created_at: Optional[float] = None
    updated_at: Optional[float] = None


@dataclass
class SubtitleOperation:
    """Subtitle operation tracking information."""
    file_id: int
    operation_type: OperationType
    operation_status: ProcessingStatus
    subtitle_language: Optional[str] = None
    subtitle_path: Optional[str] = None
    subtitle_source: Optional[str] = None
    operation_start_time: Optional[float] = None
    operation_end_time: Optional[float] = None
    operation_duration: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class ScanSession:
    """Scan session tracking information."""
    session_start_time: float
    directories_scanned: List[str]
    files_found: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    scan_duration: Optional[float] = None


class FileTracker:
    """
    SQLite-based file tracking system for background service.
    
    Tracks processed files, processing status, and prevents unnecessary
    reprocessing of files that already have Hebrew subtitles.
    """
    
    def __init__(self, db_path: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the file tracker.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location.
            config: Configuration dictionary for logging and other settings.
        """
        self.config = config or {}
        self.logger = SubtitleLogger(self.config)
        
        # Set up database path
        if db_path is None:
            home_dir = Path.home()
            db_dir = home_dir / ".grab_sub"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "file_tracking.db")
        
        self.db_path = db_path
        self.logger.info(f"Initializing file tracker with database: {db_path}")
        
        # Initialize database
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the database with all required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Create processed_files table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS processed_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT UNIQUE NOT NULL,
                        file_hash TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        file_modified_time REAL NOT NULL,
                        processing_status TEXT NOT NULL,
                        processing_start_time REAL,
                        processing_end_time REAL,
                        processing_duration REAL,
                        error_message TEXT,
                        created_at REAL DEFAULT (unixepoch()),
                        updated_at REAL DEFAULT (unixepoch())
                    )
                """)
                
                # Create subtitle_operations table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS subtitle_operations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id INTEGER NOT NULL,
                        operation_type TEXT NOT NULL,
                        operation_status TEXT NOT NULL,
                        subtitle_language TEXT,
                        subtitle_path TEXT,
                        subtitle_source TEXT,
                        operation_start_time REAL,
                        operation_end_time REAL,
                        operation_duration REAL,
                        error_message TEXT,
                        created_at REAL DEFAULT (unixepoch()),
                        FOREIGN KEY (file_id) REFERENCES processed_files (id)
                    )
                """)
                
                # Create scan_sessions table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS scan_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_start_time REAL NOT NULL,
                        session_end_time REAL,
                        directories_scanned TEXT NOT NULL,  -- JSON array of directories
                        files_found INTEGER DEFAULT 0,
                        files_processed INTEGER DEFAULT 0,
                        files_skipped INTEGER DEFAULT 0,
                        files_failed INTEGER DEFAULT 0,
                        scan_duration REAL,
                        created_at REAL DEFAULT (unixepoch())
                    )
                """)
                
                # Create indexes for better performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON processed_files(file_path)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON processed_files(file_hash)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_processing_status ON processed_files(processing_status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_file_id ON subtitle_operations(file_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_operation_type ON subtitle_operations(operation_type)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_session_start ON scan_sessions(session_start_time)")
                
                conn.commit()
                self.logger.info("Database initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise

    def _init_enhanced_database(self) -> None:
        """
        Initialize enhanced database schema for multi-directory support.
        This is a future enhancement that provides better organization.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Create directories table for tracking monitored directories
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS monitored_directories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        directory_path TEXT UNIQUE NOT NULL,
                        display_name TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        scan_recursive BOOLEAN DEFAULT 1,
                        scan_interval_minutes INTEGER DEFAULT 30,
                        last_scan_time REAL,
                        files_count INTEGER DEFAULT 0,
                        created_at REAL DEFAULT (unixepoch()),
                        updated_at REAL DEFAULT (unixepoch())
                    )
                """)
                
                # Create directory_groups table for organizing directories
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS directory_groups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at REAL DEFAULT (unixepoch())
                    )
                """)
                
                # Create directory_group_members table for many-to-many relationship
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS directory_group_members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER NOT NULL,
                        directory_id INTEGER NOT NULL,
                        created_at REAL DEFAULT (unixepoch()),
                        FOREIGN KEY (group_id) REFERENCES directory_groups (id),
                        FOREIGN KEY (directory_id) REFERENCES monitored_directories (id),
                        UNIQUE(group_id, directory_id)
                    )
                """)
                
                # Enhanced processed_files table with directory tracking
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS processed_files_enhanced (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT UNIQUE NOT NULL,
                        directory_id INTEGER NOT NULL,
                        relative_path TEXT NOT NULL,  -- Path relative to monitored directory
                        file_name TEXT NOT NULL,
                        file_hash TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        file_modified_time REAL NOT NULL,
                        processing_status TEXT NOT NULL,
                        processing_start_time REAL,
                        processing_end_time REAL,
                        processing_duration REAL,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        last_retry_time REAL,
                        created_at REAL DEFAULT (unixepoch()),
                        updated_at REAL DEFAULT (unixepoch()),
                        FOREIGN KEY (directory_id) REFERENCES monitored_directories (id)
                    )
                """)
                
                # Enhanced subtitle_operations table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS subtitle_operations_enhanced (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id INTEGER NOT NULL,
                        operation_type TEXT NOT NULL,
                        operation_status TEXT NOT NULL,
                        subtitle_language TEXT,
                        subtitle_path TEXT,
                        subtitle_source TEXT,
                        subtitle_quality_score REAL,  -- 0-100 quality score
                        operation_start_time REAL,
                        operation_end_time REAL,
                        operation_duration REAL,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        created_at REAL DEFAULT (unixepoch()),
                        FOREIGN KEY (file_id) REFERENCES processed_files_enhanced (id)
                    )
                """)
                
                # Enhanced scan_sessions table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS scan_sessions_enhanced (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_start_time REAL NOT NULL,
                        session_end_time REAL,
                        directory_id INTEGER NOT NULL,
                        scan_type TEXT NOT NULL,  -- 'full', 'incremental', 'manual'
                        files_found INTEGER DEFAULT 0,
                        files_new INTEGER DEFAULT 0,
                        files_modified INTEGER DEFAULT 0,
                        files_processed INTEGER DEFAULT 0,
                        files_skipped INTEGER DEFAULT 0,
                        files_failed INTEGER DEFAULT 0,
                        scan_duration REAL,
                        error_count INTEGER DEFAULT 0,
                        created_at REAL DEFAULT (unixepoch()),
                        FOREIGN KEY (directory_id) REFERENCES monitored_directories (id)
                    )
                """)
                
                # Create indexes for enhanced schema
                conn.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_file_path ON processed_files_enhanced(file_path)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_directory_id ON processed_files_enhanced(directory_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_relative_path ON processed_files_enhanced(relative_path)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_status ON processed_files_enhanced(processing_status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_enhanced_retry_count ON processed_files_enhanced(retry_count)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_directory_path ON monitored_directories(directory_path)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_directory_active ON monitored_directories(is_active)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_group_name ON directory_groups(group_name)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_session_directory ON scan_sessions_enhanced(directory_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_session_start_enhanced ON scan_sessions_enhanced(session_start_time)")
                
                conn.commit()
                self.logger.info("Enhanced database schema initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Error initializing enhanced database: {e}")
            raise
    
    def _get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA-256 hash of file for change detection.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA-256 hash of the file
        """
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating file hash for {file_path}: {e}")
            return ""
            
    def calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of file for change detection.
        
        Args:
            file_path: Path to the file as string
            
        Returns:
            SHA-256 hash of the file
        """
        return self._calculate_file_hash(Path(file_path))
    
    def _get_file_info(self, file_path: Path) -> Optional[FileInfo]:
        """
        Get file information from database.
        
        Args:
            file_path: Path to the file
            
        Returns:
            FileInfo object if found, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM processed_files WHERE file_path = ?",
                    (str(file_path),)
                )
                row = cursor.fetchone()
                
                if row:
                    return FileInfo(
                        file_path=row['file_path'],
                        file_hash=row['file_hash'],
                        file_size=row['file_size'],
                        file_modified_time=row['file_modified_time'],
                        processing_status=ProcessingStatus(row['processing_status']),
                        processing_start_time=row['processing_start_time'],
                        processing_end_time=row['processing_end_time'],
                        processing_duration=row['processing_duration'],
                        error_message=row['error_message'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting file info for {file_path}: {e}")
            return None
            
    def get_files_batch(self, file_paths: List[str]) -> Dict[str, FileInfo]:
        """
        Get file information for multiple files in a single database query.
        
        Args:
            file_paths: List of file paths to look up
            
        Returns:
            Dictionary mapping file paths to FileInfo objects
        """
        if not file_paths:
            return {}
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Create placeholders for the IN clause
                placeholders = ','.join(['?' for _ in file_paths])
                query = f"SELECT * FROM processed_files WHERE file_path IN ({placeholders})"
                
                cursor = conn.execute(query, file_paths)
                rows = cursor.fetchall()
                
                result = {}
                for row in rows:
                    file_info = FileInfo(
                        file_path=row['file_path'],
                        file_hash=row['file_hash'],
                        file_size=row['file_size'],
                        file_modified_time=row['file_modified_time'],
                        processing_status=ProcessingStatus(row['processing_status']),
                        processing_start_time=row['processing_start_time'],
                        processing_end_time=row['processing_end_time'],
                        processing_duration=row['processing_duration'],
                        error_message=row['error_message'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    result[file_info.file_path] = file_info
                    
                return result
                
        except Exception as e:
            self.logger.error(f"Error getting batch file info: {e}")
            return {}
            
    def add_file(self, file_info: FileInfo) -> bool:
        """
        Add a new file to the tracking database.
        
        Args:
            file_info: FileInfo object containing file details
            
        Returns:
            True if file was added successfully, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO processed_files (
                        file_path, file_hash, file_size, file_modified_time,
                        processing_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_info.file_path,
                    file_info.file_hash,
                    file_info.file_size,
                    file_info.file_modified_time,
                    file_info.processing_status.value,
                    file_info.created_at,
                    file_info.created_at  # updated_at same as created_at for new files
                ))
                conn.commit()
                self.logger.info(f"Added file to tracking: {file_info.file_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error adding file {file_info.file_path}: {e}")
            return False
            
    def update_file(self, file_info: FileInfo) -> bool:
        """
        Update an existing file in the tracking database.
        
        Args:
            file_info: FileInfo object containing updated file details
            
        Returns:
            True if file was updated successfully, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    UPDATE processed_files SET
                        file_hash = ?, file_size = ?, file_modified_time = ?,
                        processing_status = ?, updated_at = ?
                    WHERE file_path = ?
                """, (
                    file_info.file_hash,
                    file_info.file_size,
                    file_info.file_modified_time,
                    file_info.processing_status.value,
                    datetime.now().timestamp(),
                    file_info.file_path
                ))
                conn.commit()
                self.logger.info(f"Updated file in tracking: {file_info.file_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating file {file_info.file_path}: {e}")
            return False
    
    def should_process_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be processed.
        
        Args:
            file_path: Path to the video file
            
        Returns:
            True if file should be processed, False otherwise
        """
        try:
            # Check if file exists
            if not file_path.exists():
                return False
            
            # Get file stats
            stat = file_path.stat()
            file_size = stat.st_size
            file_modified_time = stat.st_mtime
            
            # Get existing file info from database
            existing_info = self._get_file_info(file_path)
            
            if existing_info is None:
                # File never processed before
                self.logger.info(f"File {file_path} never processed before")
                return True
            
            # Check if file has changed
            if (existing_info.file_size != file_size or 
                existing_info.file_modified_time != file_modified_time):
                self.logger.info(f"File {file_path} has changed, needs reprocessing")
                return True
            
            # Check processing status
            if existing_info.processing_status == ProcessingStatus.FAILED:
                self.logger.info(f"File {file_path} previously failed, retrying")
                return True
            
            if existing_info.processing_status == ProcessingStatus.SUCCESS:
                self.logger.info(f"File {file_path} already successfully processed")
                return False
            
            # For other statuses (PENDING, PROCESSING, SKIPPED), process
            self.logger.info(f"File {file_path} has status {existing_info.processing_status}, processing")
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking if file should be processed {file_path}: {e}")
            return True  # Process on error to be safe
    
    def add_file_record(self, file_path: Path) -> int:
        """
        Add a new file record to the database.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Database ID of the new record
        """
        try:
            stat = file_path.stat()
            file_hash = self._calculate_file_hash(file_path)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO processed_files 
                    (file_path, file_hash, file_size, file_modified_time, processing_status)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    str(file_path),
                    file_hash,
                    stat.st_size,
                    stat.st_mtime,
                    ProcessingStatus.PENDING.value
                ))
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            self.logger.error(f"Error adding file record for {file_path}: {e}")
            raise
    
    def update_file_status(self, file_path: Path, status: ProcessingStatus, 
                          error_message: Optional[str] = None) -> bool:
        """
        Update file processing status.
        
        Args:
            file_path: Path to the file
            status: New processing status
            error_message: Error message if status is FAILED
            
        Returns:
            True if update was successful
        """
        try:
            current_time = datetime.now().timestamp()
            
            with sqlite3.connect(self.db_path) as conn:
                if status == ProcessingStatus.PROCESSING:
                    # Set start time
                    conn.execute("""
                        UPDATE processed_files 
                        SET processing_status = ?, processing_start_time = ?, updated_at = ?
                        WHERE file_path = ?
                    """, (status.value, current_time, current_time, str(file_path)))
                elif status in [ProcessingStatus.SUCCESS, ProcessingStatus.FAILED, ProcessingStatus.SKIPPED]:
                    # Set end time and calculate duration
                    conn.execute("""
                        UPDATE processed_files 
                        SET processing_status = ?, processing_end_time = ?, 
                            processing_duration = processing_end_time - processing_start_time,
                            error_message = ?, updated_at = ?
                        WHERE file_path = ?
                    """, (status.value, current_time, error_message, current_time, str(file_path)))
                else:
                    # Just update status
                    conn.execute("""
                        UPDATE processed_files 
                        SET processing_status = ?, updated_at = ?
                        WHERE file_path = ?
                    """, (status.value, current_time, str(file_path)))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating file status for {file_path}: {e}")
            return False
    
    def record_subtitle_operation(self, file_id: int, operation: SubtitleOperation) -> int:
        """
        Record a subtitle operation.
        
        Args:
            file_id: Database ID of the file
            operation: Subtitle operation information
            
        Returns:
            Database ID of the operation record
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO subtitle_operations 
                    (file_id, operation_type, operation_status, subtitle_language,
                     subtitle_path, subtitle_source, operation_start_time,
                     operation_end_time, operation_duration, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_id,
                    operation.operation_type.value,
                    operation.operation_status.value,
                    operation.subtitle_language,
                    operation.subtitle_path,
                    operation.subtitle_source,
                    operation.operation_start_time,
                    operation.operation_end_time,
                    operation.operation_duration,
                    operation.error_message
                ))
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            self.logger.error(f"Error recording subtitle operation: {e}")
            raise
    
    def start_scan_session(self, directories: List[str]) -> int:
        """
        Start a new scan session.
        
        Args:
            directories: List of directories being scanned
            
        Returns:
            Database ID of the scan session
        """
        try:
            session_start_time = datetime.now().timestamp()
            directories_json = json.dumps(directories)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO scan_sessions 
                    (session_start_time, directories_scanned)
                    VALUES (?, ?)
                """, (session_start_time, directories_json))
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            self.logger.error(f"Error starting scan session: {e}")
            raise
    
    def end_scan_session(self, session_id: int, files_found: int, files_processed: int,
                        files_skipped: int, files_failed: int) -> bool:
        """
        End a scan session with results.
        
        Args:
            session_id: Database ID of the scan session
            files_found: Number of files found
            files_processed: Number of files processed
            files_skipped: Number of files skipped
            files_failed: Number of files that failed
            
        Returns:
            True if update was successful
        """
        try:
            session_end_time = datetime.now().timestamp()
            
            with sqlite3.connect(self.db_path) as conn:
                # Get session start time to calculate duration
                cursor = conn.execute(
                    "SELECT session_start_time FROM scan_sessions WHERE id = ?",
                    (session_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    scan_duration = session_end_time - row[0]
                    
                    conn.execute("""
                        UPDATE scan_sessions 
                        SET session_end_time = ?, scan_duration = ?,
                            files_found = ?, files_processed = ?, 
                            files_skipped = ?, files_failed = ?
                        WHERE id = ?
                    """, (
                        session_end_time, scan_duration,
                        files_found, files_processed, files_skipped, files_failed,
                        session_id
                    ))
                    conn.commit()
                    return True
                
                return False
                
        except Exception as e:
            self.logger.error(f"Error ending scan session {session_id}: {e}")
            return False
    
    def get_processing_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get processing statistics for the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
            
            with sqlite3.connect(self.db_path) as conn:
                # File processing statistics
                cursor = conn.execute("""
                    SELECT processing_status, COUNT(*) as count
                    FROM processed_files 
                    WHERE created_at >= ?
                    GROUP BY processing_status
                """, (cutoff_time,))
                
                status_counts = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Operation statistics
                cursor = conn.execute("""
                    SELECT operation_type, operation_status, COUNT(*) as count
                    FROM subtitle_operations 
                    WHERE created_at >= ?
                    GROUP BY operation_type, operation_status
                """, (cutoff_time,))
                
                operation_counts = {}
                for row in cursor.fetchall():
                    op_type = row[0]
                    op_status = row[1]
                    count = row[2]
                    
                    if op_type not in operation_counts:
                        operation_counts[op_type] = {}
                    operation_counts[op_type][op_status] = count
                
                # Scan session statistics
                cursor = conn.execute("""
                    SELECT COUNT(*) as session_count,
                           AVG(scan_duration) as avg_scan_duration,
                           SUM(files_found) as total_files_found,
                           SUM(files_processed) as total_files_processed,
                           SUM(files_skipped) as total_files_skipped,
                           SUM(files_failed) as total_files_failed
                    FROM scan_sessions 
                    WHERE session_start_time >= ?
                """, (cutoff_time,))
                
                scan_stats = cursor.fetchone()
                
                return {
                    'period_days': days,
                    'file_status_counts': status_counts,
                    'operation_counts': operation_counts,
                    'scan_sessions': scan_stats[0] if scan_stats else 0,
                    'avg_scan_duration': scan_stats[1] if scan_stats else 0,
                    'total_files_found': scan_stats[2] if scan_stats else 0,
                    'total_files_processed': scan_stats[3] if scan_stats else 0,
                    'total_files_skipped': scan_stats[4] if scan_stats else 0,
                    'total_files_failed': scan_stats[5] if scan_stats else 0
                }
                
        except Exception as e:
            self.logger.error(f"Error getting processing statistics: {e}")
            return {}
    
    def cleanup_old_records(self, days_to_keep: int = 90) -> int:
        """
        Clean up old records to prevent database bloat.
        
        Args:
            days_to_keep: Number of days of records to keep
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
            
            with sqlite3.connect(self.db_path) as conn:
                # Delete old scan sessions
                cursor = conn.execute(
                    "DELETE FROM scan_sessions WHERE session_start_time < ?",
                    (cutoff_time,)
                )
                sessions_deleted = cursor.rowcount
                
                # Delete old subtitle operations (keep successful ones longer)
                cursor = conn.execute("""
                    DELETE FROM subtitle_operations 
                    WHERE created_at < ? AND operation_status != 'success'
                """, (cutoff_time,))
                operations_deleted = cursor.rowcount
                
                # Delete old file records (keep successful ones longer)
                cursor = conn.execute("""
                    DELETE FROM processed_files 
                    WHERE created_at < ? AND processing_status != 'success'
                """, (cutoff_time,))
                files_deleted = cursor.rowcount
                
                conn.commit()
                
                total_deleted = sessions_deleted + operations_deleted + files_deleted
                self.logger.info(f"Cleaned up {total_deleted} old records")
                return total_deleted
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old records: {e}")
            return 0
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get database information and statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get table sizes
                cursor = conn.execute("SELECT COUNT(*) FROM processed_files")
                total_files = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM subtitle_operations")
                total_operations = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM scan_sessions")
                total_sessions = cursor.fetchone()[0]
                
                # Get status distribution
                cursor = conn.execute("""
                    SELECT processing_status, COUNT(*) 
                    FROM processed_files 
                    GROUP BY processing_status
                """)
                status_distribution = dict(cursor.fetchall())
                
                # Get database file size
                db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
                
                return {
                    'database_path': self.db_path,
                    'database_size_bytes': db_size,
                    'database_size_mb': round(db_size / (1024 * 1024), 2),
                    'total_files_tracked': total_files,
                    'total_operations': total_operations,
                    'total_scan_sessions': total_sessions,
                    'status_distribution': status_distribution
                }
                
        except Exception as e:
            self.logger.error(f"Error getting database info: {e}")
            return {}
    
    def get_pending_files(self, max_files: int = 100) -> List[FileInfo]:
        """
        Get files that are pending processing (including failed files for retry).
        
        Args:
            max_files: Maximum number of files to return
            
        Returns:
            List of FileInfo objects for pending and failed files
        """
        try:
            files_to_process = []
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT file_path, file_hash, file_size, file_modified_time,
                           processing_start_time, processing_end_time, processing_duration,
                           error_message, created_at, updated_at, processing_status
                    FROM processed_files 
                    WHERE processing_status IN (?, ?)
                    ORDER BY 
                        CASE 
                            WHEN processing_status = ? THEN 0  -- PENDING first
                            WHEN processing_status = ? THEN 1  -- FAILED second
                        END,
                        created_at ASC 
                    LIMIT ?
                """, (ProcessingStatus.PENDING.value, ProcessingStatus.FAILED.value, 
                      ProcessingStatus.PENDING.value, ProcessingStatus.FAILED.value, max_files))
                
                for row in cursor.fetchall():
                    file_info = FileInfo(
                        file_path=row[0],
                        file_hash=row[1],
                        file_size=row[2],
                        file_modified_time=row[3],
                        processing_status=ProcessingStatus(row[10]),  # Use actual status from DB
                        processing_start_time=row[4],
                        processing_end_time=row[5],
                        processing_duration=row[6],
                        error_message=row[7],
                        created_at=row[8],
                        updated_at=row[9]
                    )
                    files_to_process.append(file_info)
            
            self.logger.debug(f"Retrieved {len(files_to_process)} pending/failed files")
            return files_to_process
            
        except Exception as e:
            self.logger.error(f"Error getting pending files: {e}")
            return [] 