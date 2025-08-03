"""
Standalone Validation Service for subtitle validation operations.
Provides API-callable validation functionality with caching and comprehensive logging.
"""

import re
import os
import hashlib
import json
import time
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
from datetime import datetime
import logging

try:
    from ..config.config_manager import ConfigManager
    from ..exceptions.validation_exceptions import ValidationError, ValidationServiceError
except ImportError:
    # Fallback for direct script execution
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.config_manager import ConfigManager
    from exceptions.validation_exceptions import ValidationError, ValidationServiceError


class ValidationService:
    """
    Standalone validation service for subtitle files.
    
    Provides validation functionality that can be called independently
    via API or integrated with the main background service.
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the validation service.
        
        Args:
            config_manager: Configuration manager instance. If None, creates a new one.
        """
        self.config_manager = config_manager or ConfigManager()
        self.logger = self._setup_logger()
        self.cache = {}
        self.cache_ttl = self.config_manager.get('validation.cache_ttl', 3600)  # 1 hour default
        
        # Load validation settings from config
        self.validation_settings = self.config_manager.get('validation', {})
        self.target_language = self.validation_settings.get('target_language', 'he')
        
        self.logger.info("ValidationService initialized successfully")
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logging for validation operations."""
        logger = logging.getLogger('validation_service')
        logger.setLevel(logging.INFO)
        
        # Create handler if it doesn't exist
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def validate_subtitle_file(self, file_path: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Validate subtitle file by counting subtitle numbers.
        
        Args:
            file_path: Path to the subtitle file to validate
            use_cache: Whether to use cached results if available
            
        Returns:
            Dictionary with validation results including metadata
        """
        start_time = time.time()
        file_path = str(Path(file_path).resolve())
        
        self.logger.info(f"Starting validation for file: {file_path}")
        
        # Check cache first
        if use_cache:
            cached_result = self._get_cached_result(file_path)
            if cached_result:
                self.logger.info(f"Using cached validation result for: {file_path}")
                return cached_result
        
        try:
            # Validate file exists and is readable
            if not os.path.exists(file_path):
                raise ValidationError(f"File does not exist: {file_path}")
            
            if not os.access(file_path, os.R_OK):
                raise ValidationError(f"File is not readable: {file_path}")
            
            # Read and validate file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            validation_result = self._validate_subtitle_count(content, file_path)
            
            # Add metadata
            validation_result.update({
                'file_path': file_path,
                'validation_timestamp': datetime.now().isoformat(),
                'processing_time_ms': round((time.time() - start_time) * 1000, 2),
                'file_size_bytes': len(content),
                'file_hash': self._calculate_file_hash(file_path)
            })
            
            # Cache the result
            if use_cache:
                self._cache_result(file_path, validation_result)
            
            self.logger.info(f"Validation completed for {file_path}: {'Valid' if validation_result['is_valid'] else 'Invalid'}")
            
            return validation_result
            
        except Exception as e:
            error_result = {
                'is_valid': False,
                'errors': [f"Validation error: {str(e)}"],
                'warnings': [],
                'statistics': {
                    'total_subtitles': 0,
                    'file_size': 0
                },
                'file_path': file_path,
                'validation_timestamp': datetime.now().isoformat(),
                'processing_time_ms': round((time.time() - start_time) * 1000, 2),
                'error_type': type(e).__name__
            }
            
            self.logger.error(f"Validation failed for {file_path}: {str(e)}")
            return error_result
    
    def _validate_subtitle_count(self, content: str, file_path: str) -> Dict[str, Any]:
        """
        Validate subtitle file by counting subtitle numbers.
        
        Args:
            content: Subtitle file content
            file_path: Path to the subtitle file
            
        Returns:
            Dictionary with validation results
        """
        errors = []
        warnings = []
        
        # Extract all subtitle numbers (lines that are just numbers)
        lines = content.strip().split('\n')
        subtitle_numbers = []
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            # Check if line is just a number (subtitle number)
            if line.isdigit():
                subtitle_numbers.append(int(line))
        
        total_subtitles = len(subtitle_numbers)
        
        if total_subtitles == 0:
            return {
                'is_valid': False,
                'errors': ["No subtitle numbers found"],
                'warnings': [],
                'statistics': {
                    'total_subtitles': 0,
                    'file_size': len(content)
                }
            }
        
        # Check if numbers are sequential starting from 1
        expected_numbers = list(range(1, total_subtitles + 1))
        
        if subtitle_numbers != expected_numbers:
            errors.append(f"Subtitle numbers are not sequential. Expected 1 to {total_subtitles}, got: {subtitle_numbers[:10]}{'...' if len(subtitle_numbers) > 10 else ''}")
        
        # Check for duplicate numbers
        duplicates = [num for num in set(subtitle_numbers) if subtitle_numbers.count(num) > 1]
        if duplicates:
            errors.append(f"Duplicate subtitle numbers found: {duplicates}")
        
        # Check for gaps
        if subtitle_numbers and subtitle_numbers != expected_numbers:
            missing_numbers = set(expected_numbers) - set(subtitle_numbers)
            if missing_numbers:
                errors.append(f"Missing subtitle numbers: {sorted(missing_numbers)}")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'statistics': {
                'total_subtitles': total_subtitles,
                'file_size': len(content)
            }
        }
    
    def validate_batch(self, file_paths: List[str], use_cache: bool = True) -> Dict[str, Any]:
        """
        Validate multiple subtitle files in batch.
        
        Args:
            file_paths: List of file paths to validate
            use_cache: Whether to use cached results if available
            
        Returns:
            Dictionary with batch validation results
        """
        start_time = time.time()
        batch_id = self._generate_batch_id()
        
        self.logger.info(f"Starting batch validation (ID: {batch_id}) for {len(file_paths)} files")
        
        results = []
        valid_count = 0
        error_count = 0
        
        for file_path in file_paths:
            try:
                result = self.validate_subtitle_file(file_path, use_cache)
                results.append(result)
                
                if result['is_valid']:
                    valid_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                error_result = {
                    'is_valid': False,
                    'errors': [f"Batch validation error: {str(e)}"],
                    'file_path': file_path,
                    'validation_timestamp': datetime.now().isoformat(),
                    'error_type': type(e).__name__
                }
                results.append(error_result)
                error_count += 1
        
        batch_result = {
            'batch_id': batch_id,
            'total_files': len(file_paths),
            'valid_files': valid_count,
            'invalid_files': error_count,
            'success_rate': round((valid_count / len(file_paths)) * 100, 2) if file_paths else 0,
            'results': results,
            'batch_timestamp': datetime.now().isoformat(),
            'processing_time_ms': round((time.time() - start_time) * 1000, 2)
        }
        
        self.logger.info(f"Batch validation completed (ID: {batch_id}): {valid_count}/{len(file_paths)} files valid")
        
        return batch_result
    
    def compare_subtitle_counts(self, source_file: str, target_file: str) -> Dict[str, Any]:
        """
        Compare subtitle counts between source and target files.
        
        Args:
            source_file: Path to source subtitle file
            target_file: Path to target subtitle file
            
        Returns:
            Dictionary with comparison results
        """
        self.logger.info(f"Comparing subtitle counts: {source_file} vs {target_file}")
        
        try:
            # Get source count
            source_result = self.validate_subtitle_file(source_file)
            source_count = source_result['statistics']['total_subtitles']
            
            # Get target count
            target_result = self.validate_subtitle_file(target_file)
            target_count = target_result['statistics']['total_subtitles']
            
            is_match = source_count == target_count
            
            comparison_result = {
                'is_match': is_match,
                'source_count': source_count,
                'target_count': target_count,
                'difference': abs(source_count - target_count),
                'source_valid': source_result['is_valid'],
                'target_valid': target_result['is_valid'],
                'source_file': source_file,
                'target_file': target_file,
                'comparison_timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"Comparison result: {'Match' if is_match else 'Mismatch'} ({source_count} vs {target_count})")
            
            return comparison_result
            
        except Exception as e:
            self.logger.error(f"Comparison failed: {str(e)}")
            return {
                'is_match': False,
                'error': str(e),
                'source_count': 0,
                'target_count': 0,
                'difference': 0,
                'source_valid': False,
                'target_valid': False,
                'source_file': source_file,
                'target_file': target_file,
                'comparison_timestamp': datetime.now().isoformat(),
                'error_type': type(e).__name__
            }
    
    def fix_subtitle_numbering(self, file_path: str, backup: bool = True) -> Dict[str, Any]:
        """
        Fix subtitle numbering by renumbering from 1 to N.
        
        Args:
            file_path: Path to the subtitle file
            backup: Whether to create a backup before fixing
            
        Returns:
            Dictionary with fix operation results
        """
        start_time = time.time()
        file_path = str(Path(file_path).resolve())
        
        self.logger.info(f"Starting subtitle numbering fix for: {file_path}")
        
        try:
            # Validate file exists and is readable
            if not os.path.exists(file_path):
                raise ValidationError(f"File does not exist: {file_path}")
            
            if not os.access(file_path, os.R_OK | os.W_OK):
                raise ValidationError(f"File is not readable/writable: {file_path}")
            
            # Create backup if requested
            backup_path = None
            if backup:
                backup_path = f"{file_path}.backup.{int(time.time())}"
                with open(file_path, 'r', encoding='utf-8') as src, open(backup_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
                self.logger.info(f"Created backup: {backup_path}")
            
            # Read original content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.strip().split('\n')
            fixed_lines = []
            subtitle_counter = 1
            
            for line in lines:
                line = line.strip()
                # If line is just a number, replace with sequential number
                if line.isdigit():
                    fixed_lines.append(str(subtitle_counter))
                    subtitle_counter += 1
                else:
                    fixed_lines.append(line)
            
            # Write fixed content back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(fixed_lines))
            
            # Validate the fixed file
            validation_result = self.validate_subtitle_file(file_path, use_cache=False)
            
            fix_result = {
                'success': True,
                'file_path': file_path,
                'backup_path': backup_path,
                'subtitle_count': subtitle_counter - 1,
                'validation_after_fix': validation_result,
                'fix_timestamp': datetime.now().isoformat(),
                'processing_time_ms': round((time.time() - start_time) * 1000, 2)
            }
            
            self.logger.info(f"Subtitle numbering fix completed for {file_path}: {subtitle_counter - 1} subtitles")
            
            return fix_result
            
        except Exception as e:
            self.logger.error(f"Subtitle numbering fix failed for {file_path}: {str(e)}")
            return {
                'success': False,
                'file_path': file_path,
                'error': str(e),
                'fix_timestamp': datetime.now().isoformat(),
                'processing_time_ms': round((time.time() - start_time) * 1000, 2),
                'error_type': type(e).__name__
            }
    
    def get_validation_summary(self, validation_result: Dict[str, Any]) -> str:
        """
        Get a simple validation summary.
        
        Args:
            validation_result: Result from validate_subtitle_file
            
        Returns:
            Summary string
        """
        if validation_result.get('is_valid', False):
            total = validation_result.get('statistics', {}).get('total_subtitles', 0)
            return f"✅ Valid: {total} subtitles found"
        else:
            errors = validation_result.get('errors', [])
            return f"❌ Invalid: {len(errors)} errors - {', '.join(errors[:2])}{'...' if len(errors) > 2 else ''}"
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate a fast hash for the file using metadata."""
        try:
            stat = Path(file_path).stat()
            # Use file size + modification time as a fast hash
            fast_hash_data = f"{stat.st_size}_{stat.st_mtime}_{stat.st_ctime}"
            return hashlib.md5(fast_hash_data.encode()).hexdigest()
        except Exception as e:
            self.logger.warning(f"Error calculating file hash for {file_path}: {e}")
            return ""
    
    def _generate_batch_id(self) -> str:
        """Generate a unique batch ID."""
        timestamp = int(time.time() * 1000)
        return f"batch_{timestamp}"
    
    def _get_cached_result(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get cached validation result if available and not expired."""
        if file_path not in self.cache:
            return None
        
        cached_data = self.cache[file_path]
        if time.time() - cached_data['timestamp'] > self.cache_ttl:
            del self.cache[file_path]
            return None
        
        return cached_data['result']
    
    def _cache_result(self, file_path: str, result: Dict[str, Any]) -> None:
        """Cache validation result with timestamp."""
        self.cache[file_path] = {
            'result': result,
            'timestamp': time.time()
        }
    
    def clear_cache(self) -> None:
        """Clear all cached validation results."""
        self.cache.clear()
        self.logger.info("Validation cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        expired_count = 0
        
        for file_path, cached_data in list(self.cache.items()):
            if current_time - cached_data['timestamp'] > self.cache_ttl:
                del self.cache[file_path]
                expired_count += 1
        
        return {
            'total_cached': len(self.cache),
            'expired_removed': expired_count,
            'cache_ttl_seconds': self.cache_ttl
        } 