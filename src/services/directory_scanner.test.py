"""
Unit tests for DirectoryScanner service.
"""

import os
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

import pytest

from .directory_scanner import (
    DirectoryScanner, ScanConfig, ScanResult, VideoFileInfo
)
from .file_tracker import FileInfo, ProcessingStatus
from .service_communication import ServiceCommunicationManager


class TestScanConfig:
    """Test ScanConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ScanConfig()
        
        assert config.scan_interval_minutes == 30
        assert config.max_scan_depth == 10
        assert '.mp4' in config.video_extensions
        assert '.avi' in config.video_extensions
        assert config.min_file_size_mb == 10
        assert config.max_file_size_gb == 50
        assert '*.tmp' in config.exclude_patterns
        assert config.include_hidden is False
        assert config.max_workers == 4
        
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ScanConfig(
            scan_interval_minutes=60,
            max_scan_depth=5,
            video_extensions={'.mp4', '.mkv'},
            min_file_size_mb=5,
            max_file_size_gb=100,
            exclude_patterns=['*.test'],
            include_hidden=True,
            max_workers=8
        )
        
        assert config.scan_interval_minutes == 60
        assert config.max_scan_depth == 5
        assert config.video_extensions == {'.mp4', '.mkv'}
        assert config.min_file_size_mb == 5
        assert config.max_file_size_gb == 100
        assert config.exclude_patterns == ['*.test']
        assert config.include_hidden is True
        assert config.max_workers == 8


class TestVideoFileInfo:
    """Test VideoFileInfo dataclass."""
    
    def test_video_file_info_creation(self):
        """Test VideoFileInfo creation."""
        path = Path("/test/video.mp4")
        mod_time = datetime.now()
        creation_time = datetime.now() - timedelta(hours=1)
        
        video_info = VideoFileInfo(
            path=path,
            size_bytes=1024 * 1024 * 100,  # 100MB
            modification_time=mod_time,
            creation_time=creation_time,
            file_hash="abc123"
        )
        
        assert video_info.path == path
        assert video_info.size_bytes == 1024 * 1024 * 100
        assert video_info.modification_time == mod_time
        assert video_info.creation_time == creation_time
        assert video_info.file_hash == "abc123"
        assert video_info.is_valid_video is True
        assert video_info.error_message is None


class TestDirectoryScanner:
    """Test DirectoryScanner class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
        
    @pytest.fixture
    def mock_file_tracker(self):
        """Create a mock file tracker."""
        tracker = Mock()
        tracker.calculate_file_hash.return_value = "test_hash"
        tracker.get_file_info.return_value = None
        return tracker
        
    @pytest.fixture
    def mock_communication_manager(self):
        """Create a mock communication manager."""
        return Mock(spec=ServiceCommunicationManager)
        
    @pytest.fixture
    def scanner(self, mock_file_tracker, mock_communication_manager):
        """Create a DirectoryScanner instance for testing."""
        config = ScanConfig(
            scan_interval_minutes=1,  # Short interval for testing
            max_scan_depth=3,
            min_file_size_mb=1,  # Small size for testing
            max_file_size_gb=1
        )
        
        return DirectoryScanner(
            config=config,
            file_tracker=mock_file_tracker,
            communication_manager=mock_communication_manager
        )
        
    def test_scanner_initialization(self, scanner):
        """Test scanner initialization."""
        assert scanner.config.scan_interval_minutes == 1
        assert scanner.config.max_scan_depth == 3
        assert scanner._total_scans == 0
        assert scanner._total_files_processed == 0
        assert scanner._total_new_files_found == 0
        assert scanner._is_scanning is False
        assert scanner._last_scan_time is None
        
    def test_start_scanning_no_directories(self, scanner):
        """Test starting scanning with no directories."""
        result = scanner.start_scanning([])
        assert result is False
        
    def test_start_scanning_invalid_directory(self, scanner):
        """Test starting scanning with invalid directory."""
        result = scanner.start_scanning(["/nonexistent/directory"])
        assert result is False
        
    def test_start_scanning_already_running(self, scanner, temp_dir):
        """Test starting scanning when already running."""
        # Create a test file
        test_file = Path(temp_dir) / "test.mp4"
        test_file.write_bytes(b"test content" * 1000)  # Make it large enough
        
        # Start scanning
        result1 = scanner.start_scanning([temp_dir])
        assert result1 is True
        
        # Try to start again
        result2 = scanner.start_scanning([temp_dir])
        assert result2 is False
        
        # Clean up
        scanner.stop_scanning()
        
    def test_stop_scanning_not_running(self, scanner):
        """Test stopping scanning when not running."""
        result = scanner.stop_scanning()
        assert result is False
        
    def test_scan_once_empty_directory(self, scanner, temp_dir):
        """Test scanning an empty directory."""
        result = scanner.scan_once([temp_dir])
        
        assert isinstance(result, ScanResult)
        assert result.total_files_found == 0
        assert len(result.new_files) == 0
        assert len(result.modified_files) == 0
        assert len(result.unchanged_files) == 0
        assert result.scan_duration_seconds > 0
        
    def test_scan_once_with_video_files(self, scanner, temp_dir, mock_file_tracker):
        """Test scanning directory with video files."""
        # Create test video files
        video_files = [
            ("video1.mp4", b"video content 1" * 1000),
            ("video2.avi", b"video content 2" * 1000),
            ("video3.mkv", b"video content 3" * 1000)
        ]
        
        for filename, content in video_files:
            file_path = Path(temp_dir) / filename
            file_path.write_bytes(content)
            
        # Mock file tracker to return different hashes for each file
        def mock_get_file_info(file_path):
            return None  # All files are new
            
        mock_file_tracker.get_file_info.side_effect = mock_get_file_info
        
        result = scanner.scan_once([temp_dir])
        
        assert result.total_files_found == 3
        assert len(result.new_files) == 3
        assert len(result.modified_files) == 0
        assert len(result.unchanged_files) == 0
        
        # Check that files were added to tracker
        assert mock_file_tracker.add_file.call_count == 3
        
    def test_scan_once_with_excluded_files(self, scanner, temp_dir):
        """Test scanning with files that should be excluded."""
        # Create files that should be excluded
        excluded_files = [
            ("video.tmp", b"temp content"),
            ("video.part", b"part content"),
            (".hidden.mp4", b"hidden content"),
            ("video.txt", b"text content")
        ]
        
        for filename, content in excluded_files:
            file_path = Path(temp_dir) / filename
            file_path.write_bytes(content)
            
        result = scanner.scan_once([temp_dir])
        
        assert result.total_files_found == 0
        assert len(result.new_files) == 0
        
    def test_scan_once_with_modified_files(self, scanner, temp_dir, mock_file_tracker):
        """Test scanning with modified files."""
        # Create a test video file
        video_file = Path(temp_dir) / "video.mp4"
        video_file.write_bytes(b"original content" * 1000)
        
        # Mock file tracker to return existing file info
        existing_file = FileInfo(
            file_path=str(video_file),
            file_hash="old_hash",
            file_size=1000,
            file_modified_time=datetime.now().timestamp() - 3600,  # 1 hour ago
            processing_status=ProcessingStatus.COMPLETED,
            created_at=datetime.now().timestamp() - 3600
        )
        
        def mock_get_file_info(file_path):
            if file_path == str(video_file):
                return existing_file
            return None
            
        mock_file_tracker.get_file_info.side_effect = mock_get_file_info
        
        result = scanner.scan_once([temp_dir])
        
        assert result.total_files_found == 1
        assert len(result.new_files) == 0
        assert len(result.modified_files) == 1
        assert len(result.unchanged_files) == 0
        
        # Check that file was updated in tracker
        assert mock_file_tracker.update_file.call_count == 1
        
    def test_scan_once_with_unchanged_files(self, scanner, temp_dir, mock_file_tracker):
        """Test scanning with unchanged files."""
        # Create a test video file
        video_file = Path(temp_dir) / "video.mp4"
        video_file.write_bytes(b"content" * 1000)
        
        # Mock file tracker to return existing file with same hash
        existing_file = FileInfo(
            file_path=str(video_file),
            file_hash="test_hash",  # Same hash as calculated
            file_size=1000,
            file_modified_time=datetime.now().timestamp(),
            processing_status=ProcessingStatus.COMPLETED,
            created_at=datetime.now().timestamp()
        )
        
        def mock_get_file_info(file_path):
            if file_path == str(video_file):
                return existing_file
            return None
            
        mock_file_tracker.get_file_info.side_effect = mock_get_file_info
        
        result = scanner.scan_once([temp_dir])
        
        assert result.total_files_found == 1
        assert len(result.new_files) == 0
        assert len(result.modified_files) == 0
        assert len(result.unchanged_files) == 1
        
    def test_scan_once_with_size_filters(self, scanner, temp_dir):
        """Test scanning with file size filters."""
        # Create files of different sizes
        files = [
            ("small.mp4", b"small" * 100),  # Too small
            ("large.mp4", b"large" * 1000000),  # Too large
            ("medium.mp4", b"medium" * 10000)  # Just right
        ]
        
        for filename, content in files:
            file_path = Path(temp_dir) / filename
            file_path.write_bytes(content)
            
        result = scanner.scan_once([temp_dir])
        
        # Only medium file should be included
        assert result.total_files_found == 1
        assert len(result.new_files) == 1
        assert result.new_files[0].file_path.endswith("medium.mp4")
        
    def test_scan_once_with_depth_limit(self, scanner, temp_dir):
        """Test scanning with depth limit."""
        # Create nested directories
        nested_dir = Path(temp_dir) / "level1" / "level2" / "level3" / "level4"
        nested_dir.mkdir(parents=True, exist_ok=True)
        
        # Create video file at different depths
        files = [
            (temp_dir, "root.mp4"),
            (Path(temp_dir) / "level1", "level1.mp4"),
            (Path(temp_dir) / "level1" / "level2", "level2.mp4"),
            (Path(temp_dir) / "level1" / "level2" / "level3", "level3.mp4"),
            (nested_dir, "level4.mp4")
        ]
        
        for directory, filename in files:
            file_path = directory / filename
            file_path.write_bytes(b"content" * 1000)
            
        result = scanner.scan_once([temp_dir])
        
        # Only files up to depth 3 should be included (max_scan_depth=3)
        # So root, level1, level2, and level3 files should be found
        # level4 should be excluded
        assert result.total_files_found == 4
        assert len(result.new_files) == 4
        
        found_files = [f.file_path for f in result.new_files]
        assert any("root.mp4" in f for f in found_files)
        assert any("level1.mp4" in f for f in found_files)
        assert any("level2.mp4" in f for f in found_files)
        assert any("level3.mp4" in f for f in found_files)
        assert not any("level4.mp4" in f for f in found_files)
        
    def test_should_include_directory(self, scanner):
        """Test directory inclusion logic."""
        # Test hidden directories
        assert scanner._should_include_directory(".hidden") is False
        assert scanner._should_include_directory("normal") is True
        
        # Test excluded patterns
        scanner.config.exclude_patterns = ["excluded_dir", "*.tmp"]
        assert scanner._should_include_directory("excluded_dir") is False
        assert scanner._should_include_directory("normal_dir") is True
        
    def test_should_include_file(self, scanner):
        """Test file inclusion logic."""
        # Test video extensions
        assert scanner._should_include_file("video.mp4") is True
        assert scanner._should_include_file("video.avi") is True
        assert scanner._should_include_file("video.txt") is False
        
        # Test hidden files
        assert scanner._should_include_file(".hidden.mp4") is False
        
        # Test excluded patterns
        scanner.config.exclude_patterns = ["*.tmp", "excluded.mp4"]
        assert scanner._should_include_file("video.tmp") is False
        assert scanner._should_include_file("excluded.mp4") is False
        assert scanner._should_include_file("normal.mp4") is True
        
    def test_analyze_video_file_valid(self, scanner, temp_dir):
        """Test analyzing a valid video file."""
        video_file = Path(temp_dir) / "video.mp4"
        video_file.write_bytes(b"content" * 1000)
        
        result = scanner._analyze_video_file(video_file)
        
        assert result is not None
        assert result.path == video_file
        assert result.size_bytes > 0
        assert result.file_hash == "test_hash"
        assert result.is_valid_video is True
        
    def test_analyze_video_file_too_small(self, scanner, temp_dir):
        """Test analyzing a file that's too small."""
        video_file = Path(temp_dir) / "small.mp4"
        video_file.write_bytes(b"small")
        
        result = scanner._analyze_video_file(video_file)
        
        assert result is None
        
    def test_analyze_video_file_nonexistent(self, scanner, temp_dir):
        """Test analyzing a nonexistent file."""
        video_file = Path(temp_dir) / "nonexistent.mp4"
        
        result = scanner._analyze_video_file(video_file)
        
        assert result is None
        
    def test_get_scan_statistics(self, scanner):
        """Test getting scan statistics."""
        stats = scanner.get_scan_statistics()
        
        assert 'total_scans' in stats
        assert 'total_files_processed' in stats
        assert 'total_new_files_found' in stats
        assert 'last_scan_time' in stats
        assert 'is_scanning' in stats
        assert 'scan_interval_minutes' in stats
        
        assert stats['total_scans'] == 0
        assert stats['total_files_processed'] == 0
        assert stats['total_new_files_found'] == 0
        assert stats['is_scanning'] is False
        assert stats['scan_interval_minutes'] == 1
        
    def test_is_scanning(self, scanner):
        """Test is_scanning method."""
        assert scanner.is_scanning() is False
        
        # Simulate scanning
        with scanner._scan_lock:
            scanner._is_scanning = True
            assert scanner.is_scanning() is True
            
        with scanner._scan_lock:
            scanner._is_scanning = False
            assert scanner.is_scanning() is False


if __name__ == "__main__":
    pytest.main([__file__]) 