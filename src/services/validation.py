import re
import os
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import unicodedata

class SubtitleValidationService:
    def __init__(self, target_language: str = "he", config_manager=None):
        self.target_language = target_language
        self.config_manager = config_manager
        
        # Language-specific Unicode ranges and validation settings
        self.language_configs = {
            "he": {  # Hebrew
                "name": "Hebrew",
                "ranges": [
                    (0x0590, 0x05FF),  # Hebrew
                    (0xFB1D, 0xFB4F),  # Hebrew Presentation Forms
                    (0x200F, 0x200F),  # Right-to-Left Mark
                    (0x202B, 0x202B),  # Right-to-Left Embedding
                    (0x202E, 0x202E),  # Right-to-Left Override
                ],
                "indicators": [
                    'את', 'של', 'על', 'ב', 'ל', 'מ', 'אל', 'עם', 'אין', 'יש',
                    'זה', 'זו', 'הזה', 'הזו', 'אני', 'אתה', 'את', 'הוא', 'היא',
                    'אנחנו', 'אתם', 'אתן', 'הם', 'הן', 'זה', 'זאת', 'אלה', 'אלו'
                ],
                "direction": "rtl",
                "character_set": "hebrew"
            },
            "es": {  # Spanish
                "name": "Spanish",
                "ranges": [
                    (0x0041, 0x005A),  # Basic Latin (A-Z)
                    (0x0061, 0x007A),  # Basic Latin (a-z)
                    (0x00C0, 0x00FF),  # Latin-1 Supplement
                    (0x0100, 0x017F),  # Latin Extended-A
                    (0x0180, 0x024F),  # Latin Extended-B
                ],
                "indicators": [
                    'el', 'la', 'de', 'en', 'y', 'a', 'con', 'por', 'para', 'sin',
                    'yo', 'tú', 'él', 'ella', 'nosotros', 'vosotros', 'ellos', 'ellas',
                    'este', 'esta', 'eso', 'esa', 'aquello', 'aquella'
                ],
                "direction": "ltr",
                "character_set": "latin"
            },
            "fr": {  # French
                "name": "French",
                "ranges": [
                    (0x0041, 0x005A),  # Basic Latin (A-Z)
                    (0x0061, 0x007A),  # Basic Latin (a-z)
                    (0x00C0, 0x00FF),  # Latin-1 Supplement
                    (0x0100, 0x017F),  # Latin Extended-A
                ],
                "indicators": [
                    'le', 'la', 'de', 'en', 'et', 'à', 'avec', 'pour', 'sans', 'sur',
                    'je', 'tu', 'il', 'elle', 'nous', 'vous', 'ils', 'elles',
                    'ce', 'cette', 'ces', 'mon', 'ma', 'mes'
                ],
                "direction": "ltr",
                "character_set": "latin"
            },
            "de": {  # German
                "name": "German",
                "ranges": [
                    (0x0041, 0x005A),  # Basic Latin (A-Z)
                    (0x0061, 0x007A),  # Basic Latin (a-z)
                    (0x00C0, 0x00FF),  # Latin-1 Supplement
                    (0x0100, 0x017F),  # Latin Extended-A
                ],
                "indicators": [
                    'der', 'die', 'das', 'von', 'in', 'und', 'mit', 'für', 'ohne', 'auf',
                    'ich', 'du', 'er', 'sie', 'wir', 'ihr', 'sie', 'es',
                    'dieser', 'diese', 'dieses', 'mein', 'meine', 'mein'
                ],
                "direction": "ltr",
                "character_set": "latin"
            },
            "ru": {  # Russian
                "name": "Russian",
                "ranges": [
                    (0x0400, 0x04FF),  # Cyrillic
                    (0x0500, 0x052F),  # Cyrillic Supplement
                ],
                "indicators": [
                    'я', 'ты', 'он', 'она', 'мы', 'вы', 'они', 'это', 'тот', 'та',
                    'мой', 'твой', 'наш', 'ваш', 'их', 'его', 'её', 'их'
                ],
                "direction": "ltr",
                "character_set": "cyrillic"
            },
            "ja": {  # Japanese
                "name": "Japanese",
                "ranges": [
                    (0x3040, 0x309F),  # Hiragana
                    (0x30A0, 0x30FF),  # Katakana
                    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
                ],
                "indicators": [
                    '私', 'あなた', '彼', '彼女', '私たち', 'あなたたち', '彼ら', 'これ', 'それ', 'あれ',
                    '私の', 'あなたの', '彼の', '彼女の', '私たちの'
                ],
                "direction": "ltr",
                "character_set": "japanese"
            },
            "ko": {  # Korean
                "name": "Korean",
                "ranges": [
                    (0xAC00, 0xD7AF),  # Hangul Syllables
                    (0x1100, 0x11FF),  # Hangul Jamo
                    (0x3130, 0x318F),  # Hangul Compatibility Jamo
                ],
                "indicators": [
                    '나', '너', '그', '그녀', '우리', '너희', '그들', '이것', '그것', '저것',
                    '내', '네', '그의', '그녀의', '우리의'
                ],
                "direction": "ltr",
                "character_set": "korean"
            },
            "zh": {  # Chinese
                "name": "Chinese",
                "ranges": [
                    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
                    (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
                ],
                "indicators": [
                    '我', '你', '他', '她', '我们', '你们', '他们', '这个', '那个', '这些',
                    '我的', '你的', '他的', '她的', '我们的'
                ],
                "direction": "ltr",
                "character_set": "chinese"
            },
            "ar": {  # Arabic
                "name": "Arabic",
                "ranges": [
                    (0x0600, 0x06FF),  # Arabic
                    (0x0750, 0x077F),  # Arabic Supplement
                    (0x08A0, 0x08FF),  # Arabic Extended-A
                    (0x200F, 0x200F),  # Right-to-Left Mark
                    (0x202B, 0x202B),  # Right-to-Left Embedding
                    (0x202E, 0x202E),  # Right-to-Left Override
                ],
                "indicators": [
                    'أنا', 'أنت', 'هو', 'هي', 'نحن', 'أنتم', 'هم', 'هذا', 'ذلك', 'هذه',
                    'لي', 'لك', 'له', 'لها', 'لنا'
                ],
                "direction": "rtl",
                "character_set": "arabic"
            }
        }
        
        # Default to Hebrew if language not supported
        if target_language not in self.language_configs:
            self.target_language = "he"
            print(f"Warning: Language '{target_language}' not supported, defaulting to Hebrew")
        
        self.language_config = self.language_configs[self.target_language]
        self.unicode_ranges = self.language_config["ranges"]
        self.language_indicators = self.language_config["indicators"]

    def is_language_character(self, char: str) -> bool:
        """Check if a character belongs to the target language."""
        if not char:
            return False
        
        code_point = ord(char)
        return any(start <= code_point <= end for start, end in self.unicode_ranges)

    def contains_language_text(self, text: str, threshold: float = 0.3) -> bool:
        """Check if text contains target language characters above a threshold."""
        if not text:
            return False
        
        language_chars = sum(1 for char in text if self.is_language_character(char))
        total_chars = len([char for char in text if char.isalpha()])
        
        if total_chars == 0:
            return False
        
        language_ratio = language_chars / total_chars
        return language_ratio >= threshold

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
        
        return True, errors

    def _validate_timestamp_format(self, timestamp: str) -> bool:
        """Validate SRT timestamp format (HH:MM:SS,mmm --> HH:MM:SS,mmm)."""
        pattern = r'^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}$'
        return bool(re.match(pattern, timestamp))

    def _timestamp_to_seconds(self, timestamp: str) -> float:
        """Convert SRT timestamp to seconds."""
        time_part = timestamp.split(' --> ')[0]
        hours, minutes, seconds_ms = time_part.split(':')
        seconds, milliseconds = seconds_ms.split(',')
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000

    def validate_language_content(self, content: str) -> Tuple[bool, List[str]]:
        """Validate target language content in subtitle file."""
        errors = []
        
        # Get language-specific validation settings
        min_ratio = 0.5
        if self.config_manager:
            try:
                language_settings = self.config_manager.get(f'languages.{self.target_language}.validation', {})
                min_ratio = language_settings.get('min_content_ratio', 0.5)
            except:
                pass
        
        # Parse subtitle blocks
        subtitle_blocks = self._parse_subtitle_blocks(content)
        
        if not subtitle_blocks:
            errors.append(f"No valid subtitle blocks found")
            return False, errors
        
        total_subtitles = len(subtitle_blocks)
        language_subtitles = 0
        
        for i, block in enumerate(subtitle_blocks, 1):
            text = block.get('text', '')
            
            if self.contains_language_text(text, threshold=min_ratio):
                language_subtitles += 1
            else:
                errors.append(f"Subtitle {i}: Insufficient {self.language_config['name']} content")
        
        language_ratio = language_subtitles / total_subtitles if total_subtitles > 0 else 0
        
        if language_ratio < min_ratio:
            errors.append(f"Insufficient {self.language_config['name']} content: {language_ratio:.1%} (minimum {min_ratio:.1%})")
        
        # Check for common issues
        for i, block in enumerate(subtitle_blocks, 1):
            text = block.get('text', '')
            
            if self._has_common_language_issues(text):
                errors.append(f"Subtitle {i}: Common {self.language_config['name']} issues detected")
            
            # Note: Mixed language validation removed as per user request
        
        return len(errors) == 0, errors

    def _parse_subtitle_blocks(self, content: str) -> List[Dict]:
        """Parse subtitle content into blocks."""
        blocks = []
        lines = content.strip().split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # Check if line is a number (subtitle index)
            if not line.isdigit():
                i += 1
                continue
            
            # Parse subtitle block
            try:
                subtitle_number = int(line)
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
                        'number': subtitle_number,
                        'timestamp': timestamp,
                        'text': ' '.join(text_lines)
                    })
                
                # Skip empty lines
                while i < len(lines) and not lines[i].strip():
                    i += 1
                    
            except (ValueError, IndexError):
                i += 1
        
        return blocks

    def _has_common_language_issues(self, text: str) -> bool:
        """Check for common issues in target language text."""
        # Check for excessive punctuation
        if text.count('!') + text.count('?') + text.count('.') > len(text) * 0.3:
            return True
        
        # Check for repeated characters
        for char in text:
            if text.count(char) > len(text) * 0.4:
                return True
        
        # Check for very short or very long lines
        if len(text) < 2 or len(text) > 200:
            return True
        
        return False

    def validate_encoding(self, file_path: str) -> Tuple[bool, List[str]]:
        """Validate file encoding."""
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check for BOM
            if content.startswith('\ufeff'):
                errors.append("File contains BOM (Byte Order Mark)")
            
            # Check for encoding issues
            try:
                content.encode('utf-8')
            except UnicodeEncodeError:
                errors.append("File contains invalid UTF-8 characters")
                
        except UnicodeDecodeError:
            errors.append("File is not UTF-8 encoded")
        except Exception as e:
            errors.append(f"Error reading file: {str(e)}")
        
        return len(errors) == 0, errors

    def validate_subtitle_file(self, file_path: str) -> Dict[str, any]:
        """Comprehensive subtitle file validation."""
        result = {
            'is_valid': False,
            'errors': [],
            'warnings': [],
            'statistics': {},
            'language': self.language_config['name']
        }
        
        if not os.path.exists(file_path):
            result['errors'].append(f"File not found: {file_path}")
            return result
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic statistics
            lines = content.split('\n')
            result['statistics'] = {
                'total_lines': len(lines),
                'file_size': len(content),
                'file_size_kb': len(content) / 1024
            }
            
            # Validate SRT format
            format_valid, format_errors = self.validate_srt_format(content)
            if not format_valid:
                result['errors'].extend(format_errors)
            
            # Validate encoding
            encoding_valid, encoding_errors = self.validate_encoding(file_path)
            if not encoding_valid:
                result['errors'].extend(encoding_errors)
            
            # Validate language content
            language_valid, language_errors = self.validate_language_content(content)
            if not language_valid:
                result['errors'].extend(language_errors)
            
            # Parse subtitle blocks for statistics
            subtitle_blocks = self._parse_subtitle_blocks(content)
            if subtitle_blocks:
                language_count = sum(1 for block in subtitle_blocks 
                                   if self.contains_language_text(block.get('text', '')))
                
                result['statistics'].update({
                    'total_subtitles': len(subtitle_blocks),
                    f'{self.target_language}_subtitles': language_count,
                    f'{self.target_language}_ratio': language_count / len(subtitle_blocks) if subtitle_blocks else 0
                })
            
            # Determine overall validity
            result['is_valid'] = format_valid and encoding_valid and language_valid
            
        except Exception as e:
            result['errors'].append(f"Validation error: {str(e)}")
        
        return result

    def get_validation_summary(self, validation_result: Dict[str, any]) -> str:
        """Generate a human-readable validation summary."""
        if not validation_result:
            return "No validation result provided"
        
        summary = []
        summary.append(f"Validation Summary for {self.language_config['name']} Subtitle")
        summary.append("=" * 50)
        
        if validation_result['is_valid']:
            summary.append("✅ File is VALID")
        else:
            summary.append("❌ File has validation errors")
        
        # Statistics
        stats = validation_result.get('statistics', {})
        if stats:
            summary.append("")
            summary.append("📊 Statistics:")
            summary.append(f"   Total subtitles: {stats.get('total_subtitles', 0)}")
            summary.append(f"   {self.language_config['name']} subtitles: {stats.get(f'{self.target_language}_subtitles', 0)}")
            summary.append(f"   {self.language_config['name']} ratio: {stats.get(f'{self.target_language}_ratio', 0):.1%}")
            summary.append(f"   File size: {stats.get('file_size_kb', 0):.1f} KB")
        
        # Errors
        errors = validation_result.get('errors', [])
        if errors:
            summary.append("")
            summary.append("❌ Errors:")
            for error in errors:
                summary.append(f"   • {error}")
        
        # Warnings
        warnings = validation_result.get('warnings', [])
        if warnings:
            summary.append("")
            summary.append("⚠️  Warnings:")
            for warning in warnings:
                summary.append(f"   • {warning}")
        
        return "\n".join(summary) 