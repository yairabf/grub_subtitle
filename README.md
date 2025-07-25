# TV Show Subtitle Service

This service automatically downloads and translates subtitles for TV show episodes. It first attempts to find Hebrew subtitles, and if none are available, it downloads English subtitles and translates them to Hebrew using OpenAI's translation capabilities.

## Features

- Automatically processes all video files in a directory
- Searches for Hebrew subtitles first
- Falls back to English subtitles with translation if Hebrew is not available
- **Hebrew subtitle validation and quality assurance**
- Supports multiple video formats (mp4, mkv, avi, mov, wmv, flv, webm)
- Maintains original subtitle timing and format
- Uses OpenSubtitles XML-RPC API for better quota access
- Hash-based subtitle matching for accurate results

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root with your credentials:
```
OPENSUBTITLES_USERNAME=your_opensubtitles_username
OPENSUBTITLES_PASSWORD=your_opensubtitles_password
OPENAI_API_KEY=your_openai_api_key
```

You'll need to:
- Create an OpenSubtitles account at [OpenSubtitles](https://www.opensubtitles.com/en/consumers) and use your username/password
- Get an OpenAI API key from [OpenAI](https://platform.openai.com/api-keys)

## Usage

### Process a directory of video files:
```bash
python -m src.main
```

### Process a single video file:
```bash
python -c "
from src.services.subtitle_service import SubtitleService
service = SubtitleService()
service.process_video_file('path/to/your/video.mp4')
"
```

### Process with Hebrew subtitle validation:
```bash
python -m src.main --validate path/to/your/video.mp4
```

### Validate an existing Hebrew subtitle file:
```bash
python -m src.main --validate-only path/to/subtitle.heb.srt
```

### Validate and attempt to fix issues:
```bash
python -m src.main --validate-only path/to/subtitle.heb.srt --fix
```

### Test the OpenSubtitles API:
```bash
python test_xmlrpc.py
```

### Test the validation functionality:
```bash
python test_validation_simple.py
python example_validation_only.py
```

## Hebrew Subtitle Validation

The service includes a comprehensive Hebrew subtitle validation layer that ensures quality and correctness of generated subtitles.

### Validation Features

- **Hebrew Text Detection**: Identifies Hebrew characters and validates Hebrew content ratio
- **SRT Format Validation**: Ensures proper subtitle timing and format compliance
- **Encoding Validation**: Checks for UTF-8 encoding and BOM issues
- **Content Quality Checks**: Detects mixed languages and translation issues
- **Automatic Fixes**: Attempts to fix common formatting and timing issues

### Translation Improvements

The translation service has been enhanced to ensure **complete translation of all subtitle blocks**:

- **SRT Block-Aware Chunking**: Preserves complete subtitle blocks during chunking
- **Translation Completeness Validation**: Verifies all blocks are translated
- **Improved Error Handling**: Better error reporting and recovery
- **Enhanced System Prompts**: More consistent and accurate translations
- **Block Count Verification**: Ensures no subtitle blocks are lost during translation

### Validation Methods

#### Standalone Validation
```python
from src.services.validation import SubtitleValidationService

validation_service = SubtitleValidationService()
result = validation_service.validate_subtitle_file('subtitle.heb.srt')

if result['is_valid']:
    print("✅ Hebrew subtitle is valid!")
else:
    print("❌ Validation errors found:")
    for error in result['errors']:
        print(f"  • {error}")
```

#### Validation with Subtitle Service
```python
from src.services.subtitle_service import SubtitleService

service = SubtitleService()

# Process video with validation
success = service.process_video_file_with_validation('video.mp4')

# Validate existing subtitle
validation_result = service.validate_hebrew_subtitle('subtitle.heb.srt')

# Validate and fix issues
success = service.validate_and_fix_hebrew_subtitle('subtitle.heb.srt')
```

#### Translation Completeness Check
```python
from src.services.translation import TranslationService

translation_service = TranslationService()

# Check if all blocks were translated
is_complete = translation_service.validate_translation_completeness(
    'original.srt', 'translated.heb.srt'
)

if is_complete:
    print("✅ All subtitle blocks translated successfully!")
else:
    print("❌ Some subtitle blocks were not translated!")
```

### Validation Criteria

The validation service checks for:

1. **Hebrew Content**: At least 50% of subtitles must contain Hebrew text
2. **SRT Format**: Proper subtitle numbering, timing, and structure
3. **Timing**: End times must be after start times
4. **Encoding**: UTF-8 encoding without BOM
5. **Content Quality**: Mixed language detection and translation quality

### Validation Output

The validation service provides detailed reports including:

- Overall validity status
- Statistics (total subtitles, Hebrew ratio, file size)
- Specific error messages
- Warning messages for potential issues
- Human-readable summary

Example output:
```
Validation Summary for subtitle.heb.srt
==================================================
✅ File is VALID

📊 Statistics:
   Total subtitles: 150
   Hebrew subtitles: 145
   Hebrew ratio: 96.7%
   File size: 12,450 characters
```

## How it works

1. **File Analysis**: Extracts show name, season, and episode from video filename
2. **Hash Search**: Uses OpenSubtitles hash-based search for exact file matching
3. **Query Search**: Falls back to text-based search if hash search fails
4. **Hebrew Priority**: Searches for Hebrew subtitles first
5. **English Fallback**: Downloads English subtitles if Hebrew not available
6. **Translation**: Uses OpenAI to translate English subtitles to Hebrew with **complete block preservation**
7. **Translation Validation**: Verifies all subtitle blocks were translated successfully
8. **Validation**: Validates Hebrew subtitle quality and format
9. **Smart Selection**: Chooses the most popular subtitle by download count

## File Naming Convention

The service expects video files to be named with season/episode information:
- `ShowName.S01E01.EpisodeTitle.mkv`
- `ShowName.S01E01.mkv`
- `ShowName.1x01.EpisodeTitle.mp4`

## Notes

- Subtitles are saved with the same name as the video file, with language suffix (e.g., `.heb.srt`)
- The XML-RPC API provides better quota access than the REST API
- Temporary English subtitle files are automatically cleaned up after translation
- The service reuses existing subtitles before downloading new ones 
- **Validation ensures Hebrew subtitle quality and can automatically fix common issues** 