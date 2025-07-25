"""
Unit tests for FileTracker class.
"""

import unittest
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from services.file_tracker import (
    FileTracker, FileInfo, SubtitleOperation, ScanSession,
    ProcessingStatus, OperationType
)


class TestFileTracker(unittest.TestCase):
    """Test cases for FileTracker class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test database
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_file_tracking.db"
        
        # Mock configuration
        self.mock_config = {
            'logging': {
                'level': 'DEBUG',
                'file': str(Path(self.temp_dir) / 'test.log'),
                'console_output': False
            }
        }
        
        # Create file tracker
        self.file_tracker = FileTracker(str(self.db_path), self.mock_config)
        
        # Create test video file
        self.test_video_path = Path(self.temp_dir) / "test_video.mkv"
        self.test_video_path.write_text("mock video content")
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test file tracker initialization."""
        self.assertIsNotNone(self.file_tracker)
        self.assertEqual(self.file_tracker.db_path, str(self.db_path))
        self.assertTrue(self.db_path.exists())
    
    def test_default_database_path(self):
        """Test default database path creation."""
        with patch('pathlib.Path.home', return_value=Path(self.temp_dir)):
            tracker = FileTracker(config=self.mock_config)
            expected_path = Path(self.temp_dir) / ".grab_sub" / "file_tracking.db"
            self.assertEqual(tracker.db_path, str(expected_path))
            self.assertTrue(expected_path.parent.exists())
    
    def test_should_process_file_new_file(self):
        """Test should_process_file for new file."""
        result = self.file_tracker.should_process_file(self.test_video_path)
        self.assertTrue(result)
    
    def test_should_process_file_existing_success(self):
        """Test should_process_file for existing successfully processed file."""
        # Add file record with success status
        file_id = self.file_tracker.add_file_record(self.test_video_path)
        self.file_tracker.update_file_status(self.test_video_path, ProcessingStatus.SUCCESS)
        
        # Should not process again
        result = self.file_tracker.should_process_file(self.test_video_path)
        self.assertFalse(result)
    
    def test_should_process_file_existing_failed(self):
        """Test should_process_file for existing failed file."""
        # Add file record with failed status
        file_id = self.file_tracker.add_file_record(self.test_video_path)
        self.file_tracker.update_file_status(self.test_video_path, ProcessingStatus.FAILED, "Test error")
        
        # Should process again (retry)
        result = self.file_tracker.should_process_file(self.test_video_path)
        self.assertTrue(result)
    
    def test_should_process_file_changed(self):
        """Test should_process_file for changed file."""
        # Add file record
        file_id = self.file_tracker.add_file_record(self.test_video_path)
        self.file_tracker.update_file_status(self.test_video_path, ProcessingStatus.SUCCESS)
        
        # Modify file
        time.sleep(0.1)  # Ensure different timestamp
        self.test_video_path.write_text("modified content")
        
        # Should process again (file changed)
        result = self.file_tracker.should_process_file(self.test_video_path)
        self.assertTrue(result)
    
    def test_add_file_record(self):
        """Test adding file record."""
        file_id = self.file_tracker.add_file_record(self.test_video_path)
        self.assertIsInstance(file_id, int)
        self.assertGreater(file_id, 0)
    
    def test_update_file_status(self):
        """Test updating file status."""
        # Add file record
        file_id = self.file_tracker.add_file_record(self.test_video_path)
        
        # Update to processing
        result = self.file_tracker.update_file_status(self.test_video_path, ProcessingStatus.PROCESSING)
        self.assertTrue(result)
        
        # Update to success
        result = self.file_tracker.update_file_status(self.test_video_path, ProcessingStatus.SUCCESS)
        self.assertTrue(result)
        
        # Update to failed
        result = self.file_tracker.update_file_status(self.test_video_path, ProcessingStatus.FAILED, "Test error")
        self.assertTrue(result)
    
    def test_record_subtitle_operation(self):
        """Test recording subtitle operation."""
        # Add file record
        file_id = self.file_tracker.add_file_record(self.test_video_path)
        
        # Create subtitle operation
        operation = SubtitleOperation(
            file_id=file_id,
            operation_type=OperationType.DOWNLOAD,
            operation_status=ProcessingStatus.SUCCESS,
            subtitle_language="heb",
            subtitle_path="/path/to/subtitle.srt",
            subtitle_source="opensubtitles",
            operation_start_time=time.time(),
            operation_end_time=time.time() + 5.0,
            operation_duration=5.0
        )
        
        # Record operation
        op_id = self.file_tracker.record_subtitle_operation(file_id, operation)
        self.assertIsInstance(op_id, int)
        self.assertGreater(op_id, 0)
    
    def test_scan_session_tracking(self):
        """Test scan session tracking."""
        directories = ["/test/dir1", "/test/dir2"]
        
        # Start scan session
        session_id = self.file_tracker.start_scan_session(directories)
        self.assertIsInstance(session_id, int)
        self.assertGreater(session_id, 0)
        
        # End scan session
        result = self.file_tracker.end_scan_session(
            session_id, 
            files_found=10, 
            files_processed=5, 
            files_skipped=3, 
            files_failed=2
        )
        self.assertTrue(result)
    
    def test_get_processing_statistics(self):
        """Test getting processing statistics."""
        # Add some test data
        file_id1 = self.file_tracker.add_file_record(self.test_video_path)
        self.file_tracker.update_file_status(self.test_video_path, ProcessingStatus.SUCCESS)
        
        # Create another test file
        test_video2 = Path(self.temp_dir) / "test_video2.mkv"
        test_video2.write_text("mock video content 2")
        file_id2 = self.file_tracker.add_file_record(test_video2)
        self.file_tracker.update_file_status(test_video2, ProcessingStatus.FAILED, "Test error")
        
        # Record some operations
        operation1 = SubtitleOperation(
            file_id=file_id1,
            operation_type=OperationType.DOWNLOAD,
            operation_status=ProcessingStatus.SUCCESS,
            subtitle_language="heb"
        )
        self.file_tracker.record_subtitle_operation(file_id1, operation1)
        
        operation2 = SubtitleOperation(
            file_id=file_id2,
            operation_type=OperationType.TRANSLATE,
            operation_status=ProcessingStatus.FAILED,
            error_message="Translation failed"
        )
        self.file_tracker.record_subtitle_operation(file_id2, operation2)
        
        # Get statistics
        stats = self.file_tracker.get_processing_statistics(days=30)
        
        self.assertIn('file_status_counts', stats)
        self.assertIn('operation_counts', stats)
        self.assertIn('scan_sessions', stats)
        
        # Check file status counts
        status_counts = stats['file_status_counts']
        self.assertIn('success', status_counts)
        self.assertIn('failed', status_counts)
        self.assertEqual(status_counts['success'], 1)
        self.assertEqual(status_counts['failed'], 1)
    
    def test_cleanup_old_records(self):
        """Test cleanup of old records."""
        # Add some test data
        file_id = self.file_tracker.add_file_record(self.test_video_path)
        self.file_tracker.update_file_status(self.test_video_path, ProcessingStatus.SUCCESS)
        
        # Record operation
        operation = SubtitleOperation(
            file_id=file_id,
            operation_type=OperationType.DOWNLOAD,
            operation_status=ProcessingStatus.SUCCESS,
            subtitle_language="heb"
        )
        self.file_tracker.record_subtitle_operation(file_id, operation)
        
        # Start scan session
        session_id = self.file_tracker.start_scan_session(["/test/dir"])
        self.file_tracker.end_scan_session(session_id, 1, 1, 0, 0)
        
        # Cleanup with very short retention (should keep recent records)
        deleted_count = self.file_tracker.cleanup_old_records(days_to_keep=1)
        self.assertEqual(deleted_count, 0)  # Should not delete recent records
    
    def test_get_database_info(self):
        """Test getting database information."""
        # Add some test data
        file_id = self.file_tracker.add_file_record(self.test_video_path)
        operation = SubtitleOperation(
            file_id=file_id,
            operation_type=OperationType.DOWNLOAD,
            operation_status=ProcessingStatus.SUCCESS,
            subtitle_language="heb"
        )
        self.file_tracker.record_subtitle_operation(file_id, operation)
        session_id = self.file_tracker.start_scan_session(["/test/dir"])
        
        # Get database info
        info = self.file_tracker.get_database_info()
        
        self.assertIn('database_path', info)
        self.assertIn('database_size_bytes', info)
        self.assertIn('files_tracked', info)
        self.assertIn('operations_recorded', info)
        self.assertIn('scan_sessions', info)
        
        self.assertEqual(info['files_tracked'], 1)
        self.assertEqual(info['operations_recorded'], 1)
        self.assertEqual(info['scan_sessions'], 1)
        self.assertGreater(info['database_size_bytes'], 0)
    
    def test_file_hash_calculation(self):
        """Test file hash calculation."""
        # Create test file with known content
        test_file = Path(self.temp_dir) / "hash_test.txt"
        test_content = "test content for hashing"
        test_file.write_text(test_content)
        
        # Calculate hash
        hash1 = self.file_tracker._calculate_file_hash(test_file)
        self.assertIsInstance(hash1, str)
        self.assertEqual(len(hash1), 64)  # SHA-256 hex length
        
        # Hash should be consistent
        hash2 = self.file_tracker._calculate_file_hash(test_file)
        self.assertEqual(hash1, hash2)
        
        # Hash should change with content
        test_file.write_text("different content")
        hash3 = self.file_tracker._calculate_file_hash(test_file)
        self.assertNotEqual(hash1, hash3)
    
    def test_error_handling(self):
        """Test error handling in file tracker."""
        # Test with non-existent file
        non_existent_file = Path(self.temp_dir) / "non_existent.mkv"
        result = self.file_tracker.should_process_file(non_existent_file)
        self.assertFalse(result)
        
        # Test with invalid file path
        with self.assertRaises(Exception):
            self.file_tracker.add_file_record(Path("/invalid/path/file.mkv"))
    
    def test_concurrent_access(self):
        """Test concurrent database access."""
        import threading
        
        def add_file_record():
            test_file = Path(self.temp_dir) / f"concurrent_test_{threading.get_ident()}.mkv"
            test_file.write_text("test content")
            return self.file_tracker.add_file_record(test_file)
        
        # Create multiple threads
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(target=lambda: results.append(add_file_record()))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All operations should succeed
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertIsInstance(result, int)
            self.assertGreater(result, 0)


if __name__ == '__main__':
    unittest.main() 