import re
import os
from typing import List, Dict, Tuple, Optional
from pathlib import Path

class SubtitleValidationService:
    def __init__(self, target_language: str = "he", config_manager=None):
        self.target_language = target_language
        self.config_manager = config_manager

    def validate_subtitle_file(self, file_path: str) -> Dict[str, any]:
        """
        Validate subtitle file by counting subtitle numbers.
        
        Args:
            file_path: Path to the subtitle file to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self._validate_subtitle_count(content, file_path)
            
        except Exception as e:
            return {
                'is_valid': False,
                'errors': [f"Error reading file: {str(e)}"],
                'warnings': [],
                'statistics': {
                    'total_subtitles': 0,
                    'file_size': 0
                }
            }

    def _validate_subtitle_count(self, content: str, file_path: str) -> Dict[str, any]:
        """
        Validate subtitle file by counting subtitle numbers (a values).
        
        Subtitle format:
        a) 1
        b) 00:00:01,667 --> 00:00:04,068
        c) <i>♪♪ [ רוק ]</i>
        
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
        
        for line in lines:
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

    def get_validation_summary(self, validation_result: Dict[str, any]) -> str:
        """
        Get a simple validation summary.
        
        Args:
            validation_result: Result from validate_subtitle_file
            
        Returns:
            Summary string
        """
        if validation_result['is_valid']:
            total = validation_result['statistics']['total_subtitles']
            return f"✅ Valid: {total} subtitles found"
        else:
            errors = validation_result['errors']
            return f"❌ Invalid: {len(errors)} errors - {', '.join(errors[:2])}{'...' if len(errors) > 2 else ''}"

    def fix_subtitle_numbering(self, file_path: str) -> bool:
        """
        Fix subtitle numbering by renumbering from 1 to N.
        
        Args:
            file_path: Path to the subtitle file
            
        Returns:
            True if successful, False otherwise
        """
        try:
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
            
            return True
            
        except Exception as e:
            print(f"Error fixing subtitle numbering: {e}")
            return False

    def compare_subtitle_counts(self, source_file: str, target_file: str) -> Dict[str, any]:
        """
        Compare subtitle counts between source and target files.
        
        Args:
            source_file: Path to source subtitle file
            target_file: Path to target subtitle file
            
        Returns:
            Dictionary with comparison results
        """
        try:
            # Get source count
            source_result = self.validate_subtitle_file(source_file)
            source_count = source_result['statistics']['total_subtitles']
            
            # Get target count
            target_result = self.validate_subtitle_file(target_file)
            target_count = target_result['statistics']['total_subtitles']
            
            is_match = source_count == target_count
            
            return {
                'is_match': is_match,
                'source_count': source_count,
                'target_count': target_count,
                'difference': abs(source_count - target_count),
                'source_valid': source_result['is_valid'],
                'target_valid': target_result['is_valid']
            }
            
        except Exception as e:
            return {
                'is_match': False,
                'error': str(e),
                'source_count': 0,
                'target_count': 0,
                'difference': 0,
                'source_valid': False,
                'target_valid': False
            } 