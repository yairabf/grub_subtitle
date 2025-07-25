"""
Structured logging system for Hebrew Subtitle Service.
Provides JSON logging, log rotation, and contextual logging capabilities.
"""

import logging
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union
from logging.handlers import RotatingFileHandler
import threading

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present (using getattr to avoid linter issues)
        extra_fields = getattr(record, 'extra_fields', None)
        if extra_fields:
            log_entry.update(extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)
    
    def formatException(self, exc_info):
        """Format exception information."""
        return ''.join(self.formatException(exc_info))

class SubtitleLogger:
    """Enhanced logger for subtitle processing with structured logging and rotation."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the subtitle logger.
        
        Args:
            config: Configuration dictionary containing logging settings
        """
        self.config = config
        self.logger = logging.getLogger('subtitle_service')
        self.logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        self._setup_handlers()
        self._setup_formatters()
        
        # Thread-local storage for contextual information
        self._context = threading.local()
    
    def _setup_handlers(self):
        """Set up logging handlers based on configuration."""
        log_config = self.config.get('logging', {})
        
        # File handler with rotation
        log_file = log_config.get('file', 'logs/subtitle_service.log')
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        max_size = self._parse_size(log_config.get('max_size', '10MB'))
        backup_count = log_config.get('backup_count', 5)
        
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self._get_log_level(log_config.get('level', 'INFO')))
        self.logger.addHandler(file_handler)
        
        # Console handler
        if log_config.get('console_output', True):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self._get_log_level(log_config.get('level', 'INFO')))
            self.logger.addHandler(console_handler)
    
    def _setup_formatters(self):
        """Set up log formatters based on configuration."""
        log_format = self.config.get('logging', {}).get('format', 'json')
        
        if log_format == 'json':
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        for handler in self.logger.handlers:
            handler.setFormatter(formatter)
    
    def _get_log_level(self, level_str: str) -> int:
        """Convert string log level to logging constant."""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return level_map.get(level_str.upper(), logging.INFO)
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string (e.g., '10MB') to bytes."""
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def set_context(self, **kwargs):
        """Set contextual information for the current thread."""
        if not hasattr(self._context, 'data'):
            self._context.data = {}
        self._context.data.update(kwargs)
    
    def clear_context(self):
        """Clear contextual information for the current thread."""
        if hasattr(self._context, 'data'):
            self._context.data.clear()
    
    def _get_context_data(self) -> Dict[str, Any]:
        """Get contextual data for the current thread."""
        if hasattr(self._context, 'data'):
            return self._context.data.copy()
        return {}
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """Log message with contextual information."""
        # Add contextual data to the log record
        extra_fields = {**self._get_context_data(), **kwargs}
        
        # Use the logger's log method with extra parameter
        self.logger.log(level, message, extra={'extra_fields': extra_fields})
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        self._log_with_context(logging.CRITICAL, message, **kwargs)
    
    def log_processing_start(self, file_path: str, file_info: Dict[str, Any]):
        """Log the start of file processing."""
        self.info("Processing started", 
                  file_path=file_path,
                  file_info=file_info,
                  event_type="processing_start")
    
    def log_processing_complete(self, file_path: str, success: bool, duration: float):
        """Log the completion of file processing."""
        self.info("Processing completed",
                  file_path=file_path,
                  success=success,
                  duration_seconds=duration,
                  event_type="processing_complete")
    
    def log_subtitle_search(self, search_type: str, query: str, results_count: int):
        """Log subtitle search operations."""
        self.info("Subtitle search performed",
                  search_type=search_type,
                  query=query,
                  results_count=results_count,
                  event_type="subtitle_search")
    
    def log_translation_progress(self, chunk_num: int, total_chunks: int, success: bool):
        """Log translation progress."""
        self.info("Translation progress",
                  chunk_number=chunk_num,
                  total_chunks=total_chunks,
                  success=success,
                  progress_percent=round((chunk_num / total_chunks) * 100, 1),
                  event_type="translation_progress")
    
    def log_api_call(self, api_name: str, endpoint: str, success: bool, duration: float):
        """Log API call information."""
        self.info("API call made",
                  api_name=api_name,
                  endpoint=endpoint,
                  success=success,
                  duration_seconds=duration,
                  event_type="api_call")
    
    def log_validation_result(self, file_path: str, is_valid: bool, errors: list):
        """Log validation results."""
        self.info("Validation completed",
                  file_path=file_path,
                  is_valid=is_valid,
                  error_count=len(errors),
                  errors=errors,
                  event_type="validation_result")
    
    def log_error(self, error_type: str, message: str, file_path: Optional[str] = None, **kwargs):
        """Log error with context."""
        self.error(f"{error_type}: {message}",
                   error_type=error_type,
                   file_path=file_path,
                   event_type="error",
                   **kwargs)
    
    def log_performance_metric(self, metric_name: str, value: Union[int, float], unit: str = ""):
        """Log performance metrics."""
        self.info("Performance metric",
                  metric_name=metric_name,
                  value=value,
                  unit=unit,
                  event_type="performance_metric")
    
    def get_log_file_path(self) -> str:
        """Get the current log file path."""
        log_config = self.config.get('logging', {})
        return log_config.get('file', 'logs/subtitle_service.log')
    
    def rotate_logs(self):
        """Manually trigger log rotation."""
        for handler in self.logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                handler.doRollover()
                self.info("Log rotation triggered manually", event_type="log_rotation")
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics."""
        log_file = Path(self.get_log_file_path())
        stats = {
            'log_file_exists': log_file.exists(),
            'log_file_size': log_file.stat().st_size if log_file.exists() else 0,
            'log_file_size_mb': round(log_file.stat().st_size / (1024 * 1024), 2) if log_file.exists() else 0,
            'backup_files': []
        }
        
        # Count backup files
        if log_file.exists():
            backup_pattern = f"{log_file.name}.*"
            for backup_file in log_file.parent.glob(backup_pattern):
                if backup_file != log_file:
                    stats['backup_files'].append({
                        'name': backup_file.name,
                        'size_mb': round(backup_file.stat().st_size / (1024 * 1024), 2)
                    })
        
        return stats 