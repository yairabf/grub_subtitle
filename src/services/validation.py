import re
import os
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import unicodedata

class SubtitleValidationService:
    def __init__(self):
        # Hebrew Unicode ranges
        self.hebrew_ranges = [
            (0x0590, 0x05FF),  # Hebrew
            (0xFB1D, 0xFB4F),  # Hebrew Presentation Forms
            (0x200F, 0x200F),  # Right-to-Left Mark
            (0x202B, 0x202B),  # Right-to-Left Embedding
            (0x202E, 0x202E),  # Right-to-Left Override
        ]
        
        # Common Hebrew words and patterns for validation
        self.hebrew_indicators = [
            'את', 'של', 'על', 'ב', 'ל', 'מ', 'אל', 'עם', 'אין', 'יש',
            'זה', 'זו', 'הזה', 'הזו', 'אני', 'אתה', 'את', 'הוא', 'היא',
            'אנחנו', 'אתם', 'אתן', 'הם', 'הן', 'זה', 'זאת', 'אלה', 'אלו'
        ]

    def is_hebrew_character(self, char: str) -> bool:
        """Check if a character is Hebrew."""
        if not char:
            return False
        
        code_point = ord(char)
        return any(start <= code_point <= end for start, end in self.hebrew_ranges)

    def contains_hebrew_text(self, text: str, threshold: float = 0.3) -> bool:
        """Check if text contains Hebrew characters above a threshold."""
        if not text:
            return False
        
        hebrew_chars = sum(1 for char in text if self.is_hebrew_character(char))
        total_chars = len([char for char in text if char.isalpha()])
        
        if total_chars == 0:
            return False
        
        hebrew_ratio = hebrew_chars / total_chars
        return hebrew_ratio >= threshold

    def validate_srt_format(self, content: str) -> Tuple[bool, List[str]]:
        """Validate SRT subtitle format."""
        errors = []
        lines = content.strip().split('\n')
        
        if not lines:
            errors.append("Empty subtitle file")
            return False, errors
        
        i = 0
        subtitle_count = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Check subtitle number
            if not line.isdigit():
                errors.append(f"Line {i+1}: Expected subtitle number, got '{line}'")
                return False, errors
            
            subtitle_count += 1
            i += 1
            
            if i >= len(lines):
                errors.append(f"Subtitle {subtitle_count}: Missing timestamp")
                break
            
            # Check timestamp format
            timestamp_line = lines[i].strip()
            if not self._validate_timestamp_format(timestamp_line):
                errors.append(f"Subtitle {subtitle_count}: Invalid timestamp format '{timestamp_line}'")
                return False, errors
            
            i += 1
            
            # Collect subtitle text
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            
            if not text_lines:
                errors.append(f"Subtitle {subtitle_count}: No subtitle text")
                return False, errors
            
            # Skip empty lines after text
            while i < len(lines) and not lines[i].strip():
                i += 1
        
        if subtitle_count == 0:
            errors.append("No subtitles found in file")
            return False, errors
        
        return True, errors

    def _validate_timestamp_format(self, timestamp: str) -> bool:
        """Validate SRT timestamp format (HH:MM:SS,mmm --> HH:MM:SS,mmm)."""
        pattern = r'^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}$'
        if not re.match(pattern, timestamp):
            return False
        
        # Extract start and end times
        times = timestamp.split(' --> ')
        start_time = times[0]
        end_time = times[1]
        
        # Validate that end time is after start time
        start_seconds = self._timestamp_to_seconds(start_time)
        end_seconds = self._timestamp_to_seconds(end_time)
        
        return end_seconds > start_seconds

    def _timestamp_to_seconds(self, timestamp: str) -> float:
        """Convert SRT timestamp to seconds."""
        hours, minutes, seconds_ms = timestamp.split(':')
        seconds, milliseconds = seconds_ms.split(',')
        
        total_seconds = (
            int(hours) * 3600 +
            int(minutes) * 60 +
            int(seconds) +
            int(milliseconds) / 1000
        )
        return total_seconds

    def validate_hebrew_content(self, content: str) -> Tuple[bool, List[str]]:
        """Validate Hebrew content quality."""
        errors = []
        warnings = []
        
        # Split into subtitle blocks
        subtitle_blocks = self._parse_subtitle_blocks(content)
        
        if not subtitle_blocks:
            errors.append("No subtitle blocks found")
            return False, errors
        
        hebrew_subtitles = 0
        total_subtitles = len(subtitle_blocks)
        
        for i, block in enumerate(subtitle_blocks):
            subtitle_text = block.get('text', '')
            
            if self.contains_hebrew_text(subtitle_text):
                hebrew_subtitles += 1
                
                # Check for common Hebrew translation issues
                if self._has_common_hebrew_issues(subtitle_text):
                    warnings.append(f"Subtitle {i+1}: Potential translation quality issues")
                
                # Check for mixed languages
                if self._has_mixed_languages(subtitle_text):
                    warnings.append(f"Subtitle {i+1}: Mixed Hebrew and other languages detected")
            else:
                errors.append(f"Subtitle {i+1}: No Hebrew text detected")
        
        # Check Hebrew content ratio
        hebrew_ratio = hebrew_subtitles / total_subtitles if total_subtitles > 0 else 0
        if hebrew_ratio < 0.5:
            errors.append(f"Low Hebrew content ratio: {hebrew_ratio:.2%} ({hebrew_subtitles}/{total_subtitles})")
        
        return len(errors) == 0, errors + warnings

    def _parse_subtitle_blocks(self, content: str) -> List[Dict]:
        """Parse SRT content into subtitle blocks."""
        blocks = []
        lines = content.strip().split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # Skip subtitle number
            if not line.isdigit():
                i += 1
                continue
            
            i += 1
            if i >= len(lines):
                break
            
            # Get timestamp
            timestamp = lines[i].strip()
            i += 1
            
            # Get subtitle text
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            
            if text_lines:
                blocks.append({
                    'timestamp': timestamp,
                    'text': ' '.join(text_lines)
                })
            
            # Skip empty lines
            while i < len(lines) and not lines[i].strip():
                i += 1
        
        return blocks

    def _has_common_hebrew_issues(self, text: str) -> bool:
        """Check for common Hebrew translation issues."""
        # Check for excessive English words
        english_words = re.findall(r'\b[a-zA-Z]+\b', text)
        hebrew_words = re.findall(r'[\u0590-\u05FF]+', text)
        
        if len(english_words) > len(hebrew_words) * 0.3:
            return True
        
        # Check for missing Hebrew indicators
        has_hebrew_indicators = any(indicator in text for indicator in self.hebrew_indicators)
        if len(hebrew_words) > 5 and not has_hebrew_indicators:
            return True
        
        return False

    def _has_mixed_languages(self, text: str) -> bool:
        """Check if text contains mixed languages."""
        hebrew_chars = len([char for char in text if self.is_hebrew_character(char)])
        english_chars = len([char for char in text if char.isalpha() and ord(char) < 128])
        
        return hebrew_chars > 0 and english_chars > 0

    def validate_encoding(self, file_path: str) -> Tuple[bool, List[str]]:
        """Validate file encoding."""
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            errors.append("File encoding is not UTF-8")
            return False, errors
        except Exception as e:
            errors.append(f"Error reading file: {e}")
            return False, errors
        
        # Check for BOM
        if content.startswith('\ufeff'):
            errors.append("File contains BOM (Byte Order Mark)")
        
        # Check for invalid characters
        invalid_chars = []
        for i, char in enumerate(content):
            if unicodedata.category(char) == 'Cn':  # Unassigned
                invalid_chars.append(f"Position {i}: Invalid character U+{ord(char):04X}")
        
        if invalid_chars:
            errors.extend(invalid_chars[:5])  # Limit to first 5 errors
            if len(invalid_chars) > 5:
                errors.append(f"... and {len(invalid_chars) - 5} more invalid characters")
        
        return len(errors) == 0, errors

    def validate_subtitle_file(self, file_path: str) -> Dict[str, any]:
        """Comprehensive validation of a Hebrew subtitle file."""
        result = {
            'file_path': file_path,
            'is_valid': False,
            'errors': [],
            'warnings': [],
            'statistics': {}
        }
        
        # Check if file exists
        if not os.path.exists(file_path):
            result['errors'].append("File does not exist")
            return result
        
        # Validate encoding
        encoding_valid, encoding_errors = self.validate_encoding(file_path)
        result['errors'].extend(encoding_errors)
        
        if not encoding_valid:
            return result
        
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            result['errors'].append(f"Error reading file: {e}")
            return result
        
        # Validate SRT format
        format_valid, format_errors = self.validate_srt_format(content)
        result['errors'].extend(format_errors)
        
        # Validate Hebrew content
        content_valid, content_issues = self.validate_hebrew_content(content)
        
        # Separate errors and warnings
        for issue in content_issues:
            if issue.startswith('Subtitle') and 'Potential' in issue:
                result['warnings'].append(issue)
            else:
                result['errors'].append(issue)
        
        # Calculate statistics
        subtitle_blocks = self._parse_subtitle_blocks(content)
        hebrew_subtitles = sum(1 for block in subtitle_blocks 
                             if self.contains_hebrew_text(block.get('text', '')))
        
        result['statistics'] = {
            'total_subtitles': len(subtitle_blocks),
            'hebrew_subtitles': hebrew_subtitles,
            'hebrew_ratio': hebrew_subtitles / len(subtitle_blocks) if subtitle_blocks else 0,
            'file_size': len(content)
        }
        
        # Determine overall validity
        result['is_valid'] = format_valid and content_valid and encoding_valid
        
        return result

    def get_validation_summary(self, validation_result: Dict[str, any]) -> str:
        """Generate a human-readable validation summary."""
        summary = f"Validation Summary for {os.path.basename(validation_result['file_path'])}\n"
        summary += "=" * 50 + "\n"
        
        if validation_result['is_valid']:
            summary += "✅ File is VALID\n"
        else:
            summary += "❌ File has VALIDATION ERRORS\n"
        
        # Statistics
        stats = validation_result['statistics']
        summary += f"\n📊 Statistics:\n"
        summary += f"   Total subtitles: {stats['total_subtitles']}\n"
        summary += f"   Hebrew subtitles: {stats['hebrew_subtitles']}\n"
        summary += f"   Hebrew ratio: {stats['hebrew_ratio']:.1%}\n"
        summary += f"   File size: {stats['file_size']:,} characters\n"
        
        # Errors
        if validation_result['errors']:
            summary += f"\n❌ Errors ({len(validation_result['errors'])}):\n"
            for error in validation_result['errors']:
                summary += f"   • {error}\n"
        
        # Warnings
        if validation_result['warnings']:
            summary += f"\n⚠️  Warnings ({len(validation_result['warnings'])}):\n"
            for warning in validation_result['warnings']:
                summary += f"   • {warning}\n"
        
        return summary 