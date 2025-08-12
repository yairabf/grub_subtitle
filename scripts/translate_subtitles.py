#!/usr/bin/env python3
"""
Standalone subtitle translation script.
Translates existing English subtitle files to Hebrew using OpenAI.
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
from src.services.translation import TranslationService

def find_subtitles_to_translate(directory):
    """Find all subtitle files in the directory and subdirectories that need translation to Hebrew."""
    subtitle_files = []
    for file_path in Path(directory).rglob('*.srt'):
        # Skip Hebrew subtitles (they're already in Hebrew)
        if '.heb.srt' in file_path.name:
            continue
        
        # Check if Hebrew subtitle already exists for this file
        # Remove language code from filename to find Hebrew version
        base_name = file_path.stem
        # Remove common language codes from the end
        for lang_code in ['.eng', '.en', '.fr', '.es', '.de', '.it', '.pt', '.nl', '.sv', '.da', '.no', '.fi']:
            if base_name.endswith(lang_code):
                base_name = base_name[:-len(lang_code)]
                break
        
        heb_sub_path = file_path.parent / f"{base_name}.heb.srt"
        if heb_sub_path.exists():
            print(f"Skipping {file_path.name} - Hebrew subtitle already exists: {heb_sub_path.name}")
            continue
            
        # Include all other subtitle files (eng, fr, es, etc.) that don't have Hebrew versions
        subtitle_files.append(file_path)
    return subtitle_files

def translate_subtitles_in_directory(directory_path, translation_service):
    """Translate all subtitle files in a directory to Hebrew."""
    subtitle_files = find_subtitles_to_translate(directory_path)
    
    if not subtitle_files:
        print(f"No subtitle files found in {directory_path}")
        return
    
    print(f"Found {len(subtitle_files)} subtitle files to translate to Hebrew")
    
    success_count = 0
    failed_count = 0
    
    for sub_path in subtitle_files:
        # Create Hebrew subtitle path
        heb_sub_path = sub_path.parent / f"{sub_path.stem}.heb.srt"
        
        print(f"\nTranslating: {sub_path.name}")
        print(f"Output: {heb_sub_path.name}")
        
        try:
            if translation_service.translate_subtitle(str(sub_path), str(heb_sub_path)):
                if os.path.exists(heb_sub_path):
                    print(f"✓ Hebrew subtitle already exists or was created: {heb_sub_path.name}")
                else:
                    print(f"✓ Successfully translated {sub_path.name}")
                success_count += 1
            else:
                print(f"✗ Failed to translate {sub_path.name}")
                failed_count += 1
        except Exception as e:
            print(f"✗ Error translating {sub_path.name}: {e}")
            failed_count += 1
    
    print(f"\nTranslation complete!")
    print(f"Successfully translated: {success_count}")
    print(f"Failed: {failed_count}")

def main():
    parser = argparse.ArgumentParser(description='Translate English subtitle files to Hebrew')
    parser.add_argument('directory', nargs='?', help='Directory containing English subtitle files')
    parser.add_argument('--file', help='Translate a single subtitle file instead of scanning directory')
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    if not os.getenv('OPENAI_API_KEY'):
        print("Error: OPENAI_API_KEY not found in environment variables")
        print("Please set your OpenAI API key in the .env file")
        sys.exit(1)
    
    # Load configuration
    from src.config.config_manager import ConfigManager
    config_manager = ConfigManager()
    
    translation_service = TranslationService(config_manager=config_manager)
    
    if args.file:
        # Translate a single file
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        
        sub_path = Path(args.file)
        heb_sub_path = sub_path.parent / f"{sub_path.stem}.heb.srt"
        
        print(f"Translating single file: {sub_path.name}")
        if translation_service.translate_subtitle(str(sub_path), str(heb_sub_path)):
            print(f"✓ Successfully translated to {heb_sub_path.name}")
        else:
            print("✗ Translation failed")
            sys.exit(1)
    else:
        # Translate all files in directory
        if not args.directory:
            print("Error: Please specify either a directory or use --file option")
            sys.exit(1)
            
        if not os.path.exists(args.directory):
            print(f"Error: Directory not found: {args.directory}")
            sys.exit(1)
        
        translate_subtitles_in_directory(args.directory, translation_service)

if __name__ == "__main__":
    main() 