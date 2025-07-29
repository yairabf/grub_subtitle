# Multi-Language Support

## Overview

The Grab Subtitle service now supports multiple target languages, making it a truly international subtitle solution. Instead of being limited to Hebrew, you can now configure the service to work with any of 11 supported languages.

## Supported Languages

| Language Code | Language Name | Character Set | Text Direction |
|---------------|---------------|---------------|----------------|
| `he` | Hebrew | Hebrew | RTL |
| `es` | Spanish | Latin | LTR |
| `fr` | French | Latin | LTR |
| `de` | German | Latin | LTR |
| `it` | Italian | Latin | LTR |
| `pt` | Portuguese | Latin | LTR |
| `ru` | Russian | Cyrillic | LTR |
| `ja` | Japanese | Japanese | LTR |
| `ko` | Korean | Korean | LTR |
| `zh` | Chinese | Chinese | LTR |
| `ar` | Arabic | Arabic | RTL |

## Configuration

### Environment Variable

Set the target language in your `.env` file:

```bash
# Target language for subtitles
TARGET_LANGUAGE=es  # For Spanish subtitles
```

### Configuration File

You can also configure language-specific settings in `config/config.yaml`:

```yaml
# Translation Settings
translation:
  target_language: "es"  # Spanish
  source_language: "en"  # English (default)
  fallback_languages: ["en"]  # Languages to try if target language not found
  language_priority: ["es", "en"]  # Priority order for subtitle search

# Language-specific settings
languages:
  es:  # Spanish
    name: "Spanish"
    validation:
      min_content_ratio: 0.5
      character_set: "latin"
      direction: "ltr"
```

## How It Works

### 1. Subtitle Search Priority

The service follows this search order:

1. **Target Language Direct**: Search for subtitles in your target language
2. **Target Language Variants**: Try different language codes (e.g., "spa", "es" for Spanish)
3. **English Fallback**: If no target language subtitles found, search for English
4. **Translation**: Translate English subtitles to your target language

### 2. Language-Specific Validation

Each language has its own validation rules:

- **Character Detection**: Validates that subtitles contain the correct character set
- **Content Ratio**: Ensures sufficient content in the target language
- **Direction Support**: Handles RTL languages (Hebrew, Arabic) correctly
- **Quality Checks**: Language-specific quality validation

### 3. Translation

When translating from English to your target language:

- **AI-Powered**: Uses OpenAI GPT models for high-quality translation
- **Format Preservation**: Maintains exact SRT timing and formatting
- **Language-Specific Prompts**: Optimized prompts for each target language
- **Quality Control**: Validates translation quality and completeness

## Usage Examples

### Spanish Subtitles

```bash
# Set in .env file
TARGET_LANGUAGE=es

# Run the service
python run_background_service.py
```

The service will:
1. Search for Spanish subtitles first
2. Fall back to English if needed
3. Translate English to Spanish
4. Validate Spanish content quality

### French Subtitles

```bash
# Set in .env file
TARGET_LANGUAGE=fr

# Run the service
python run_background_service.py
```

### Japanese Subtitles

```bash
# Set in .env file
TARGET_LANGUAGE=ja

# Run the service
python run_background_service.py
```

## File Naming

Subtitles are saved with language-specific extensions:

- Spanish: `.es.srt`
- French: `.fr.srt`
- Japanese: `.ja.srt`
- Hebrew: `.he.srt`
- Arabic: `.ar.srt`

## Validation Features

### Language-Specific Validation

Each language has customized validation:

- **Hebrew/Arabic**: RTL text direction, specific character ranges
- **Japanese**: Hiragana, Katakana, and Kanji detection
- **Korean**: Hangul character detection
- **Chinese**: CJK Unified Ideographs
- **Russian**: Cyrillic character detection
- **European Languages**: Latin character sets with language-specific indicators

### Quality Metrics

- **Content Ratio**: Minimum percentage of target language content
- **Character Validation**: Ensures proper character set usage
- **Format Compliance**: SRT format validation
- **Encoding Check**: UTF-8 encoding validation

## Advanced Configuration

### Custom Language Settings

You can customize validation for each language:

```yaml
languages:
  es:  # Spanish
    name: "Spanish"
    validation:
      min_content_ratio: 0.6  # Require 60% Spanish content
      character_set: "latin"
      direction: "ltr"
```

### Translation Settings

Configure translation behavior:

```yaml
translation:
  target_language: "es"
  source_language: "en"
  fallback_languages: ["en", "fr"]  # Try English, then French
  language_priority: ["es", "en", "fr"]  # Search order
```

## Benefits

### 1. **International Support**
- Support for 11 major languages
- Proper handling of different writing systems
- RTL language support (Hebrew, Arabic)

### 2. **Flexible Configuration**
- Easy language switching via environment variable
- Language-specific validation rules
- Customizable quality thresholds

### 3. **Quality Assurance**
- Language-specific character detection
- Content ratio validation
- Format and encoding checks

### 4. **Seamless Integration**
- Same API and workflow for all languages
- Consistent file naming conventions
- Unified validation and error handling

## Migration from Hebrew-Only

If you were previously using the Hebrew-only version:

1. **No Breaking Changes**: Hebrew (`he`) remains the default
2. **Easy Migration**: Just change `TARGET_LANGUAGE` in your `.env` file
3. **Backward Compatibility**: All existing Hebrew functionality preserved
4. **Enhanced Features**: Better validation and error handling

## Troubleshooting

### Language Not Supported

If you need a language not in the supported list:

1. Check if the language code is correct
2. The service will default to Hebrew if language is not supported
3. Consider requesting support for additional languages

### Validation Issues

If validation fails for your target language:

1. Check the `min_content_ratio` setting
2. Verify the subtitle file contains the correct character set
3. Ensure proper UTF-8 encoding

### Translation Quality

If translation quality is poor:

1. Check your OpenAI API key and quota
2. Verify the source English subtitles are good quality
3. Consider adjusting the translation temperature setting

## Future Enhancements

Planned improvements for multi-language support:

1. **Additional Languages**: Support for more languages
2. **Language Detection**: Automatic source language detection
3. **Quality Scoring**: Language-specific quality metrics
4. **Custom Dictionaries**: User-defined translation preferences
5. **Regional Variants**: Support for regional language variants 