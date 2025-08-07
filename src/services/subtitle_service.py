import os
import re
from pathlib import Path
from dotenv import load_dotenv
from api.opensubtitles import OpenSubtitlesAPI
from services.translation import TranslationService
from services.validation_service import ValidationService
from utils.file_utils import calculate_opensubtitles_hash, get_episode_info
from typing import Dict, Optional, Any
from enum import Enum

class LanguageCodeMapping(Enum):
    """Language code mappings for subtitle file extensions."""
    ENGLISH = ["en", "eng", "english"]
    HEBREW = ["he", "heb", "hebrew"]
    SPANISH = ["es", "spa", "spanish"]
    FRENCH = ["fr", "fre", "french"]
    GERMAN = ["de", "ger", "german"]
    ITALIAN = ["it", "ita", "italian"]
    PORTUGUESE = ["pt", "por", "portuguese"]
    RUSSIAN = ["ru", "rus", "russian"]
    JAPANESE = ["ja", "jpn", "japanese"]
    KOREAN = ["ko", "kor", "korean"]
    CHINESE = ["zh", "chi", "chinese"]
    ARABIC = ["ar", "ara", "arabic"]
    
    @classmethod
    def get_codes_for_language(cls, language: str) -> list:
        """Get all possible codes for a given language."""
        language = language.lower()
        for mapping in cls:
            if language in mapping.value:
                return mapping.value
        # If not found, return the original language code
        return [language]

class SubtitleService:
    def __init__(self, opensubtitles_username=None, opensubtitles_password=None, openai_api_key=None, target_language="he", config_manager=None):
        load_dotenv()
        self.opensubtitles = OpenSubtitlesAPI(opensubtitles_username, opensubtitles_password)
        self.translation_service = TranslationService()
        self.target_language = target_language
        self.config_manager = config_manager
        
        # Initialize validation service
        self.validation_service = ValidationService(config_manager=config_manager)
        
        # Get language configuration
        self.language_config = self._get_language_config()
        
        # Language codes mapping for OpenSubtitles
        self.language_codes = {
            "he": ["heb", "he"],  # Hebrew
            "es": ["spa", "es"],  # Spanish
            "fr": ["fre", "fr"],  # French
            "de": ["ger", "de"],  # German
            "it": ["ita", "it"],  # Italian
            "pt": ["por", "pt"],  # Portuguese
            "ru": ["rus", "ru"],  # Russian
            "ja": ["jpn", "ja"],  # Japanese
            "ko": ["kor", "ko"],  # Korean
            "zh": ["chi", "zh"],  # Chinese
            "ar": ["ara", "ar"],  # Arabic
        }
    
    @property
    def language_name(self) -> str:
        """Safely get the language name with fallback."""
        if self.language_config and isinstance(self.language_config, dict):
            return self.language_config.get('name', 'Unknown')
        return 'Unknown'

    def _get_language_config(self):
        """Get language configuration from config manager or use defaults."""
        if self.config_manager:
            try:
                config = self.config_manager.get(f'languages.{self.target_language}', {})
                # Ensure we have a valid dictionary with required keys
                if config and isinstance(config, dict) and 'name' in config:
                    return config
            except Exception as e:
                print(f"Warning: Could not get language config from config manager: {e}")
        
        # Default language configurations
        default_configs = {
            "he": {"name": "Hebrew", "direction": "rtl"},
            "es": {"name": "Spanish", "direction": "ltr"},
            "fr": {"name": "French", "direction": "ltr"},
            "de": {"name": "German", "direction": "ltr"},
            "it": {"name": "Italian", "direction": "ltr"},
            "pt": {"name": "Portuguese", "direction": "ltr"},
            "ru": {"name": "Russian", "direction": "ltr"},
            "ja": {"name": "Japanese", "direction": "ltr"},
            "ko": {"name": "Korean", "direction": "ltr"},
            "zh": {"name": "Chinese", "direction": "ltr"},
            "ar": {"name": "Arabic", "direction": "rtl"},
        }
        
        return default_configs.get(self.target_language, {"name": "Unknown", "direction": "ltr"})

    def search_subtitle(self, episode_info, language='eng'):
        """Search for subtitles on OpenSubtitles by hash first, then by show name."""
        show_name = episode_info['show_name']
        season = episode_info.get('season')
        episode = episode_info.get('episode')
        file_hash = episode_info.get('hash')

        # Try hash search first (most accurate)
        if file_hash:
            print(f"[DEBUG] Trying hash search for {show_name}")
            search_results = self.opensubtitles.search_subtitles_by_hash(file_hash, language)
            if search_results:
                print(f"[DEBUG] Hash search successful, found {len(search_results)} results")
                # Return the result with highest download count
                best_result = max(search_results, key=lambda x: x.get('attributes', {}).get('download_count', 0))
                print(f"[DEBUG] Selected subtitle with {best_result.get('attributes', {}).get('download_count', 0)} downloads")
                return [best_result]
            else:
                print(f"[DEBUG] Hash search failed, falling back to query search")

        # Fall back to query search with show name, season, and episode
        print(f"[DEBUG] Trying query search for {show_name}")
        search_results = self.opensubtitles.search_subtitles(
            query=show_name,
            language=language,
            season=season,
            episode=episode
        )
        if not search_results:
            return None

        # Filter results by season and episode
        matching_results = []
        for result in search_results:
            attrs = result.get('attributes', {})
            details = attrs.get('feature_details', {})
            if (
                details.get('season_number') == season and
                details.get('episode_number') == episode
            ):
                matching_results.append(result)

        if matching_results:
            # Return the result with highest download count
            best_result = max(matching_results, key=lambda x: x.get('attributes', {}).get('download_count', 0))
            print(f"[DEBUG] Selected subtitle with {best_result.get('attributes', {}).get('download_count', 0)} downloads")
            return [best_result]

        return None

    def search_subtitle_aggressive_target_language(self, episode_info):
        """Aggressively search for target language subtitles using multiple strategies."""
        show_name = episode_info['show_name']
        season = episode_info.get('season')
        episode = episode_info.get('episode')
        file_hash = episode_info.get('hash')
        
        # Get language codes to try for target language
        target_codes = self.language_codes.get(self.target_language, [self.target_language])
        
        print(f"🔍 Aggressively searching for {self.language_name} subtitles for: {show_name}")
        
        for lang_code in target_codes:
            print(f"  Trying {self.language_name} code: {lang_code}")
            
            # Try hash search first (most accurate)
            if file_hash:
                print(f"    Searching by hash with {lang_code}...")
                search_results = self.opensubtitles.search_subtitles_by_hash(file_hash, lang_code)
                if search_results:
                    print(f"    ✅ Found {len(search_results)} {self.language_name} subtitles by hash with {lang_code}")
                    # Return the result with highest download count
                    best_result = max(search_results, key=lambda x: x.get('attributes', {}).get('download_count', 0))
                    print(f"    Selected subtitle with {best_result.get('attributes', {}).get('download_count', 0)} downloads")
                    return [best_result]
                else:
                    print(f"    ❌ No results by hash with {lang_code}")
            
            # Try query search with show name, season, and episode
            print(f"    Searching by query with {lang_code}...")
            search_results = self.opensubtitles.search_subtitles(
                query=show_name,
                language=lang_code,
                season=season,
                episode=episode
            )
            
            if search_results:
                # Filter results by season and episode
                matching_results = []
                for result in search_results:
                    attrs = result.get('attributes', {})
                    details = attrs.get('feature_details', {})
                    if (
                        details.get('season_number') == season and
                        details.get('episode_number') == episode
                    ):
                        matching_results.append(result)
                
                if matching_results:
                    print(f"    ✅ Found {len(matching_results)} {self.language_name} subtitles by query with {lang_code}")
                    # Return the result with highest download count
                    best_result = max(matching_results, key=lambda x: x.get('attributes', {}).get('download_count', 0))
                    print(f"    Selected subtitle with {best_result.get('attributes', {}).get('download_count', 0)} downloads")
                    return [best_result]
                else:
                    print(f"    ❌ No matching season/episode results with {lang_code}")
            else:
                print(f"    ❌ No results by query with {lang_code}")
        
        print(f"    ❌ No {self.language_name} subtitles found with any language code")
        return None

    def search_subtitle_aggressive_english(self, video_path, show_name, season, episode):
        """Aggressively search for English subtitles using multiple strategies."""
        file_hash = calculate_opensubtitles_hash(video_path)
        
        # English language codes to try (in order of preference)
        english_codes = ['eng', 'en']
        
        print(f"🔍 Aggressively searching for English subtitles for: {show_name}")
        
        for english_code in english_codes:
            print(f"  Trying English code: {english_code}")
            
            # Try hash search first (most accurate)
            if file_hash:
                print(f"    Searching by hash with {english_code}...")
                search_results = self.opensubtitles.search_subtitles_by_hash(file_hash, english_code)
                if search_results:
                    print(f"    ✅ Found {len(search_results)} English subtitles by hash with {english_code}")
                    # Return the result with highest download count
                    best_result = max(search_results, key=lambda x: x.get('attributes', {}).get('download_count', 0))
                    print(f"    Selected subtitle with {best_result.get('attributes', {}).get('download_count', 0)} downloads")
                    return [best_result]
                else:
                    print(f"    ❌ No results by hash with {english_code}")
            
            # Try query search with show name, season, and episode
            print(f"    Searching by query with {english_code}...")
            search_results = self.opensubtitles.search_subtitles(
                query=show_name,
                language=english_code,
                season=season,
                episode=episode
            )
            
            if search_results:
                # Filter results by season and episode
                matching_results = []
                for result in search_results:
                    attrs = result.get('attributes', {})
                    details = attrs.get('feature_details', {})
                    if (
                        details.get('season_number') == season and
                        details.get('episode_number') == episode
                    ):
                        matching_results.append(result)
                
                if matching_results:
                    print(f"    ✅ Found {len(matching_results)} English subtitles by query with {english_code}")
                    # Return the result with highest download count
                    best_result = max(matching_results, key=lambda x: x.get('attributes', {}).get('download_count', 0))
                    print(f"    Selected subtitle with {best_result.get('attributes', {}).get('download_count', 0)} downloads")
                    return [best_result]
                else:
                    print(f"    ❌ No matching season/episode results with {english_code}")
            else:
                print(f"    ❌ No results by query with {english_code}")
        
        print(f"    ❌ No English subtitles found with any language code")
        return None

    def process_episode(self, episode_path):
        """Process a single episode file with aggressive Hebrew search."""
        episode_info = get_episode_info(episode_path)
        episode_dir = os.path.dirname(episode_path)
        base_name = os.path.splitext(os.path.basename(episode_path))[0]
        
        print(f"\n🎬 Processing episode: {episode_info['title']}")
        print(f"📁 Directory: {episode_dir}")
        
        # Aggressively try to get Hebrew subtitle first
        hebrew_subtitle = self.search_subtitle_aggressive_target_language(episode_info)
        if hebrew_subtitle and len(hebrew_subtitle) > 0:
            output_path = os.path.join(episode_dir, f"{base_name}.{self.target_language}.srt")
            # Get the file_id from the first file in the files array
            file_id = hebrew_subtitle[0].get('attributes', {}).get('files', [{}])[0].get('file_id')
            if file_id and self.opensubtitles.download_subtitle(file_id, output_path):
                print(f"✅ Successfully downloaded {self.language_name} subtitle for {episode_info['title']}")
                return True
            else:
                print(f"❌ Failed to download {self.language_name} subtitle for {episode_info['title']}")

        # Fallback: Check if English subtitle already exists
        existing_eng_path = os.path.join(episode_dir, f"{base_name}.eng.srt")
        if os.path.exists(existing_eng_path):
            print(f"📝 English subtitle already exists for {episode_info['title']}")
            # Translate existing English subtitle to Hebrew
            output_path = os.path.join(episode_dir, f"{base_name}.{self.target_language}.srt")
            if self.translation_service.translate_subtitle(existing_eng_path, output_path):
                print(f"✅ Translated existing English subtitle to {self.language_name} for {episode_info['title']}")
                return True
        else:
            # Last resort: Try English and translate
            print(f"🔍 No {self.language_name} subtitle found, trying English subtitle...")
            english_subtitle = self.search_subtitle(episode_info, 'eng')
            if english_subtitle and len(english_subtitle) > 0:
                temp_path = os.path.join(episode_dir, f"{base_name}.eng.srt")
                # Get the file_id from the first file in the files array
                file_id = english_subtitle[0].get('attributes', {}).get('files', [{}])[0].get('file_id')
                if file_id and self.opensubtitles.download_subtitle(file_id, temp_path):
                    print(f"✅ Downloaded English subtitle for {episode_info['title']}")
                    # Translate to Hebrew
                    output_path = os.path.join(episode_dir, f"{base_name}.{self.target_language}.srt")
                    if self.translation_service.translate_subtitle(temp_path, output_path):
                        print(f"✅ Translated subtitle to {self.language_name} for {episode_info['title']}")
                        # Clean up temporary English subtitle
                        os.remove(temp_path)
                        return True
                else:
                    print(f"❌ Failed to download English subtitle for {episode_info['title']}")

        print(f"❌ Could not find or process subtitles for {episode_info['title']}")
        return False

    def process_video_file(self, video_path, output_dir=None):
        """Process a single video file to find or create Hebrew subtitles."""
        video_path = Path(video_path)
        
        if not video_path.exists():
            print(f"Error: Video file not found: {video_path}")
            return False
            
        print(f"\n=== Processing video: {video_path.name} ===")
        
        # Extract show information from filename
        episode_info = get_episode_info(str(video_path))
        if not episode_info:
            print(f"Could not extract show information from filename: {video_path.name}")
            return False
            
        show_name = episode_info['show_name']
        season = episode_info.get('season')
        episode = episode_info.get('episode')
        
        print(f"Show: {show_name}")
        print(f"Season: {season}")
        print(f"Episode: {episode}")
        
        # Determine output directory
        if output_dir is None:
            output_dir = video_path.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Check if there is a Hebrew subtitle - if so move to next file
        hebrew_subtitle_path = self._find_existing_subtitle(video_path, self.target_language, output_dir)
        if hebrew_subtitle_path:
            print(f"✅ {self.language_name} subtitle already exists: {hebrew_subtitle_path}")
            return True
        
        # 2. If missing Hebrew subtitle, try to download Hebrew subtitle. If download was successful, move to next file
        print(f"🔍 Searching for {self.language_name} subtitle to download...")
        hebrew_subtitle = self.search_subtitle_aggressive_target_language(episode_info)
        
        if hebrew_subtitle:
            # Verify this is actually a Hebrew subtitle by checking the language attribute
            subtitle_lang = hebrew_subtitle[0].get('attributes', {}).get('language', '').lower()
            print(f"✅ Found subtitle: {hebrew_subtitle[0]['attributes']['release']}")
            print(f"   Language code: {subtitle_lang}")
            
            # Check if it's actually Hebrew
            if subtitle_lang in ['heb', 'he', 'hebrew']:
                print(f"✅ Confirmed {self.language_name} subtitle")
                if self._download_subtitle(hebrew_subtitle[0], video_path, output_dir, force_language=self.target_language):
                    print(f"✅ Successfully downloaded {self.language_name} subtitle")
                    return True
                else:
                    print(f"❌ Failed to download {self.language_name} subtitle, will try English")
            else:
                print(f"❌ Found subtitle but it's not {self.language_name} (language: {subtitle_lang}), will try English")
        
        # 3. If there is no Hebrew sub to download, check for existing source language subtitle
        print(f"🔍 No {self.language_name} subtitle available, checking for existing source language subtitle...")
        
        # Get source language from config or default to English
        source_language = "en"  # Default
        if self.config_manager:
            try:
                source_language = self.config_manager.get('translation.source_language', 'en')
            except:
                pass
        
        # Check if source language subtitle already exists
        source_subtitle_path = self._find_existing_subtitle(video_path, source_language, output_dir)
        if source_subtitle_path:
            print(f"✅ {source_language.upper()} subtitle already exists: {source_subtitle_path}")
            print(f"🔄 Translating existing {source_language.upper()} subtitle to {self.language_name}...")
            if self._translate_existing_subtitle(source_subtitle_path, output_dir):
                print(f"✅ Successfully translated existing {source_language.upper()} subtitle to {self.language_name}")
                return True
            else:
                print(f"❌ Failed to translate existing {source_language.upper()} subtitle to {self.language_name}")
                return False
        
        # Also check for English subtitle as fallback (in case source language is different)
        if source_language != "en":
            english_subtitle_path = self._find_existing_subtitle(video_path, 'eng', output_dir)
            if english_subtitle_path:
                print(f"✅ English subtitle already exists: {english_subtitle_path}")
                print(f"🔄 Translating existing English subtitle to {self.language_name}...")
                if self._translate_existing_subtitle(english_subtitle_path, output_dir):
                    print(f"✅ Successfully translated existing English subtitle to {self.language_name}")
                    return True
                else:
                    print(f"❌ Failed to translate existing English subtitle to {self.language_name}")
                    return False
        
        # If no existing source subtitle, search and download
        print(f"🔍 No existing source subtitle found, searching for {source_language.upper()} subtitle to download...")
        english_subtitle = self._find_subtitle_aggressive_english(
            video_path, show_name, season, episode
        )
        
        if english_subtitle:
            print(f"📝 Found English subtitle: {english_subtitle['attributes']['release']}")
            if self._download_subtitle(english_subtitle, video_path, output_dir):
                print(f"✅ Successfully downloaded English subtitle")
                
                # 4. After download the English translate it
                downloaded_english_path = self._find_existing_subtitle(video_path, 'eng', output_dir)
                if downloaded_english_path:
                    print(f"🔄 Translating downloaded English subtitle to {self.language_name}...")
                    if self._translate_existing_subtitle(downloaded_english_path, output_dir):
                        print(f"✅ Successfully translated English subtitle to {self.language_name}")
                        return True
                    else:
                        print(f"❌ Failed to translate English subtitle to {self.language_name}")
                        return False
                else:
                    print(f"❌ Could not locate downloaded English subtitle file")
                    return False
            else:
                print(f"❌ Failed to download English subtitle")
                return False
        else:
            print(f"❌ No English subtitle found to download")
        return False
    
    def _find_existing_subtitle(self, video_path, language, output_dir):
        """Find existing subtitle file for the video using multiple language code variations."""
        video_stem = video_path.stem
        possible_extensions = ['.srt', '.sub', '.ssa', '.ass']
        
        # Get all possible language codes for this language
        language_codes = LanguageCodeMapping.get_codes_for_language(language)
        
        print(f"🔍 Checking for existing {language.upper()} subtitle with codes: {language_codes}")
        
        # Check each language code variation
        for lang_code in language_codes:
            for ext in possible_extensions:
                subtitle_path = output_dir / f"{video_stem}.{lang_code}{ext}"
                if subtitle_path.exists():
                    print(f"✅ Found existing subtitle: {subtitle_path}")
                    return subtitle_path
        
        print(f"❌ No existing {language.upper()} subtitle found with any code variation")
        return None
    
    def _find_subtitle_aggressive_english(self, video_path, show_name, season, episode):
        """Find English subtitle on OpenSubtitles trying multiple English language codes."""
        print(f"🔍 Aggressively searching for English subtitles for: {show_name}")
        
        # Get all possible English language codes
        english_codes = LanguageCodeMapping.get_codes_for_language("en")
        print(f"  Trying English codes: {english_codes}")
        
        # Try each English language code
        for lang_code in english_codes:
            print(f"  Trying English code: {lang_code}")
            
            # Try hash-based search first (most accurate)
            file_hash = calculate_opensubtitles_hash(str(video_path))
            if file_hash:
                print(f"    Searching by hash with {lang_code}...")
                results = self.opensubtitles.search_subtitles_by_hash(file_hash, lang_code)
                if results:
                    # Return the most popular subtitle
                    best_result = max(results, key=lambda x: x['attributes']['download_count'])
                    print(f"    ✅ Found {len(results)} results by hash with {lang_code}")
                    return best_result
                else:
                    print(f"    ❌ No results by hash with {lang_code}")
            
            # Fall back to query-based search
            print(f"    Searching by query with {lang_code}...")
            results = self.opensubtitles.search_subtitles(show_name, lang_code, season, episode)
            if results:
                # Filter results to match season/episode if provided
                if season and episode:
                    filtered_results = []
                    for result in results:
                        result_season = result['attributes']['feature_details'].get('season_number')
                        result_episode = result['attributes']['feature_details'].get('episode_number')
                        if result_season == season and result_episode == episode:
                            filtered_results.append(result)
                    
                    if filtered_results:
                        results = filtered_results
                        print(f"    Filtered to {len(results)} results matching season {season}, episode {episode}")
                
                # Return the most popular subtitle
                best_result = max(results, key=lambda x: x['attributes']['download_count'])
                print(f"    ✅ Found {len(results)} results by query with {lang_code}")
                return best_result
            else:
                print(f"    ❌ No results by query with {lang_code}")
        
        print(f"  ❌ No English subtitles found with any English language code")
        return None

    def _find_subtitle_on_opensubtitles(self, video_path, show_name, season, episode, language):
        """Find subtitle on OpenSubtitles using hash first, then query search."""
        # Try hash-based search first (most accurate)
        file_hash = calculate_opensubtitles_hash(str(video_path))
        if file_hash:
            print(f"Searching by file hash: {file_hash}")
            results = self.opensubtitles.search_subtitles_by_hash(file_hash, language)
            if results:
                # Return the most popular subtitle
                best_result = max(results, key=lambda x: x['attributes']['download_count'])
                print(f"Found {len(results)} results by hash, selecting most popular")
                return best_result
        
        # Fall back to query-based search
        print(f"Hash search failed, trying query search for: {show_name}")
        results = self.opensubtitles.search_subtitles(show_name, language, season, episode)
        
        if results:
            # Filter results to match season/episode if provided
            if season and episode:
                filtered_results = []
                for result in results:
                    result_season = result['attributes']['feature_details'].get('season_number')
                    result_episode = result['attributes']['feature_details'].get('episode_number')
                    if result_season == season and result_episode == episode:
                        filtered_results.append(result)
                
                if filtered_results:
                    results = filtered_results
                    print(f"Filtered to {len(results)} results matching season {season}, episode {episode}")
            
            # Return the most popular subtitle
            best_result = max(results, key=lambda x: x['attributes']['download_count'])
            print(f"Found {len(results)} results by query, selecting most popular")
            return best_result
        
        return None
    
    def _download_subtitle(self, subtitle, video_path, output_dir, force_language=None):
        """Download subtitle file."""
        try:
            # Determine the output filename
            video_stem = video_path.stem
            language = force_language if force_language else subtitle['attributes']['language']
            output_filename = f"{video_stem}.{language}.srt"
            output_path = output_dir / output_filename
            
            # Download the subtitle
            success = self.opensubtitles.download_subtitle(subtitle['id'], str(output_path))
            
            if success:
                print(f"Successfully downloaded subtitle to: {output_path}")
                
                # If this was supposed to be Hebrew, verify the content
                if force_language == self.target_language:
                    if not self._verify_hebrew_content(str(output_path)):
                        print(f"❌ Downloaded file does not contain {self.language_name} text, removing it")
                        output_path.unlink()  # Delete the file
                        return False
                    else:
                        print(f"✅ Verified {self.language_name} content in downloaded file")
                
                return True
            else:
                print("Failed to download subtitle")
                return False
                
        except Exception as e:
            print(f"Error downloading subtitle: {e}")
            return False
    
    def _verify_hebrew_content(self, subtitle_path):
        """Verify that a subtitle file contains Hebrew text."""
        try:
            with open(subtitle_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Hebrew Unicode range: \u0590-\u05FF
            hebrew_chars = re.findall(r'[\u0590-\u05FF]', content)
            
            # Check if we have at least some Hebrew characters
            if len(hebrew_chars) > 10:  # At least 10 Hebrew characters
                return True
            
            return False
            
        except Exception as e:
            print(f"Error verifying Hebrew content: {e}")
            return False
    
    def _translate_existing_subtitle(self, english_subtitle_path, output_dir):
        """Translate existing English subtitle to Hebrew."""
        try:
            print(f"Translating subtitle: {english_subtitle_path}")
            
            # Determine output filename
            english_stem = english_subtitle_path.stem
            # Remove language suffix if present
            if english_stem.endswith('.eng'):
                base_stem = english_stem[:-4]
            else:
                base_stem = english_stem
            
            hebrew_output_path = output_dir / f"{base_stem}.{self.target_language}.srt"
            
            # Translate the subtitle
            success = self.translation_service.translate_subtitle(
                str(english_subtitle_path), 
                str(hebrew_output_path)
            )
            
            if success:
                print(f"Successfully translated subtitle to: {hebrew_output_path}")
                return True
            else:
                print("Failed to translate subtitle")
                return False
                
        except Exception as e:
            print(f"Error translating subtitle: {e}")
            return False
    
    def process_directory(self, directory_path, output_dir=None):
        """Process all video files in a directory and its subdirectories."""
        directory_path = Path(directory_path)
        
        if not directory_path.exists() or not directory_path.is_dir():
            print(f"Error: Directory not found: {directory_path}")
            return
        
        # Find all video files recursively
        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
        video_files = []
        
        for ext in video_extensions:
            video_files.extend(directory_path.rglob(f"*{ext}"))
            video_files.extend(directory_path.rglob(f"*{ext.upper()}"))
        
        if not video_files:
            print(f"No video files found in directory: {directory_path}")
            return
        
        print(f"Found {len(video_files)} video files to process")
        
        # Process each video file
        success_count = 0
        for video_file in video_files:
            try:
                if self.process_video_file(video_file, output_dir):
                    success_count += 1
            except Exception as e:
                print(f"Error processing {video_file.name}: {e}")
        
        print(f"\n=== Processing complete ===")
        print(f"Successfully processed: {success_count}/{len(video_files)} files") 

    def validate_subtitle(self, subtitle_path: str) -> Dict[str, Any]:
        """Validate subtitle file focusing on numbering sequence."""
        print(f"\n🔍 Validating subtitle: {os.path.basename(subtitle_path)}")
        
        validation_result = self.validation_service.validate_subtitle_file(subtitle_path)
        
        # Print validation summary
        summary = self.validation_service.get_validation_summary(validation_result)
        print(summary)
        
        return validation_result

    def validate_and_fix_subtitle(self, subtitle_path: str) -> bool:
        """Validate subtitle file and attempt to fix numbering issues."""
        validation_result = self.validate_subtitle(subtitle_path)
        
        if validation_result['is_valid']:
            print(f"✅ Subtitle is valid!")
            return True
        
        # Try to fix numbering issues
        print(f"\n🔧 Attempting to fix subtitle numbering...")
        
        if self.validation_service.fix_subtitle_numbering(subtitle_path):
            print(f"✅ Applied fixes to subtitle file")
            
            # Re-validate after fixes
            new_validation = self.validate_subtitle(subtitle_path)
            return new_validation['is_valid']
        else:
            print(f"❌ Failed to apply fixes to subtitle file")
            return False

    def _fix_common_issues(self, content: str) -> str:
        """Fix common subtitle formatting issues."""
        lines = content.split('\n')
        fixed_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Check if this is a subtitle number
            if line.isdigit():
                fixed_lines.append(line)
                i += 1
                
                # Next line should be timestamp
                if i < len(lines):
                    timestamp_line = lines[i].strip()
                    if self._is_valid_timestamp(timestamp_line):
                        fixed_lines.append(timestamp_line)
                    else:
                        # Try to fix timestamp format
                        fixed_timestamp = self._fix_timestamp_format(timestamp_line)
                        if fixed_timestamp:
                            fixed_lines.append(fixed_timestamp)
                        else:
                            # Skip this subtitle block
                            while i < len(lines) and lines[i].strip():
                                i += 1
                            continue
                    i += 1
                
                # Collect subtitle text
                text_lines = []
                while i < len(lines) and lines[i].strip():
                    text_line = lines[i].strip()
                    # Fix common Hebrew text issues
                    fixed_text = self._fix_hebrew_text(text_line)
                    text_lines.append(fixed_text)
                    i += 1
                
                fixed_lines.extend(text_lines)
                fixed_lines.append('')  # Add empty line between subtitles
            else:
                i += 1
        
        return '\n'.join(fixed_lines)

    def _is_valid_timestamp(self, timestamp: str) -> bool:
        """Check if timestamp is in valid SRT format."""
        pattern = r'^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}$'
        return bool(re.match(pattern, timestamp))

    def _fix_timestamp_format(self, timestamp: str) -> Optional[str]:
        """Attempt to fix timestamp format issues."""
        # Remove extra spaces and normalize arrow
        timestamp = re.sub(r'\s+', ' ', timestamp.strip())
        timestamp = timestamp.replace('->', ' --> ')
        timestamp = timestamp.replace('--', ' --> ')
        
        # Try to match and fix common patterns
        patterns = [
            r'(\d{1,2}):(\d{1,2}):(\d{1,2})[.,](\d{1,3})\s*-->\s*(\d{1,2}):(\d{1,2}):(\d{1,2})[.,](\d{1,3})',
            r'(\d{1,2}):(\d{1,2}):(\d{1,2})\s*-->\s*(\d{1,2}):(\d{1,2}):(\d{1,2})',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, timestamp)
            if match:
                groups = match.groups()
                if len(groups) == 8:  # With milliseconds
                    return f"{groups[0].zfill(2)}:{groups[1].zfill(2)}:{groups[2].zfill(2)},{groups[3].ljust(3, '0')} --> {groups[4].zfill(2)}:{groups[5].zfill(2)}:{groups[6].zfill(2)},{groups[7].ljust(3, '0')}"
                elif len(groups) == 6:  # Without milliseconds
                    return f"{groups[0].zfill(2)}:{groups[1].zfill(2)}:{groups[2].zfill(2)},000 --> {groups[3].zfill(2)}:{groups[4].zfill(2)}:{groups[5].zfill(2)},000"
        
        return None

    def _fix_hebrew_text(self, text: str) -> str:
        """Fix common Hebrew text issues."""
        # Remove excessive spaces
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Fix common Hebrew punctuation issues
        text = text.replace(' ,', ',')
        text = text.replace(' .', '.')
        text = text.replace(' !', '!')
        text = text.replace(' ?', '?')
        
        # Fix Hebrew quote marks
        text = text.replace('"', '"')
        text = text.replace('"', '"')
        text = text.replace("'", "'")
        text = text.replace("'", "'")
        
        return text

    def process_episode_with_validation(self, episode_path: str) -> bool:
        """Process an episode with Hebrew subtitle validation."""
        print(f"\n🎬 Processing episode with validation: {os.path.basename(episode_path)}")
        
        # Process the episode normally
        self.process_episode(episode_path)
        
        # Find the generated Hebrew subtitle
        episode_dir = os.path.dirname(episode_path)
        base_name = os.path.splitext(os.path.basename(episode_path))[0]
        hebrew_subtitle_path = os.path.join(episode_dir, f"{base_name}.{self.target_language}.srt")
        
        if os.path.exists(hebrew_subtitle_path):
            print(f"\n🔍 Validating generated {self.language_name} subtitle...")
            return self.validate_and_fix_subtitle(hebrew_subtitle_path)
        else:
            print(f"❌ No {self.language_name} subtitle was generated for validation")
            return False

    def process_video_file_with_validation(self, video_path: str, output_dir=None) -> bool:
        """Process a video file with Hebrew subtitle validation."""
        print(f"\n🎬 Processing video with validation: {os.path.basename(video_path)}")
        
        # Process the video normally
        success = self.process_video_file(video_path, output_dir)
        
        if success:
            # Find the generated Hebrew subtitle
            video_path_obj = Path(video_path)
            if output_dir is None:
                output_dir = video_path_obj.parent
            else:
                output_dir = Path(output_dir)
            
            hebrew_subtitle_path = self._find_existing_subtitle(video_path_obj, self.target_language, output_dir)
            
            if hebrew_subtitle_path:
                print(f"\n🔍 Validating generated {self.language_name} subtitle...")
                return self.validate_and_fix_subtitle(str(hebrew_subtitle_path))
            else:
                print(f"❌ No {self.language_name} subtitle was generated for validation")
                return False
        
        return False 