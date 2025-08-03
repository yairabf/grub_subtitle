import os
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv
from .services.subtitle_service import SubtitleService

def main():
    load_dotenv()
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Hebrew Subtitle Grabber and Validator')
    parser.add_argument('path', nargs='?', help='Path to video file or directory')
    parser.add_argument('--validate', action='store_true', help='Enable Hebrew subtitle validation')
    parser.add_argument('--validate-only', metavar='SUBTITLE_FILE', help='Validate an existing Hebrew subtitle file')
    parser.add_argument('--fix', action='store_true', help='Attempt to fix validation issues automatically')
    parser.add_argument('--output-dir', help='Output directory for subtitles')
    
    args = parser.parse_args()
    
    # Check for required environment variables
    opensubtitles_username = os.getenv('OPENSUBTITLES_USERNAME')
    opensubtitles_password = os.getenv('OPENSUBTITLES_PASSWORD')
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if not opensubtitles_username or not opensubtitles_password:
        print("Please set OPENSUBTITLES_USERNAME and OPENSUBTITLES_PASSWORD in your .env file")
        return
    
    if not openai_api_key:
        print("Please set OPENAI_API_KEY in your .env file")
        return

    # Get target language from environment or config
    target_language = os.getenv('TARGET_LANGUAGE', 'he')
    
    service = SubtitleService(
        opensubtitles_username=opensubtitles_username, 
        opensubtitles_password=opensubtitles_password, 
        openai_api_key=openai_api_key,
        target_language=target_language
    )
    
    # Handle validation-only mode
    if args.validate_only:
        subtitle_file = args.validate_only
        if not os.path.exists(subtitle_file):
            print(f"Subtitle file not found: {subtitle_file}")
            return
        
        print(f"🔍 Validating Hebrew subtitle: {subtitle_file}")
        if args.fix:
            success = service.validate_and_fix_subtitle(subtitle_file)
            if success:
                print("✅ Validation and fix completed successfully!")
            else:
                print("❌ Validation and fix failed!")
        else:
            validation_result = service.validate_subtitle(subtitle_file)
            if validation_result['is_valid']:
                print("✅ Hebrew subtitle is valid!")
            else:
                print("❌ Hebrew subtitle has validation errors!")
        return
    
    # Handle path processing
    if not args.path:
        # Default directory if no path provided
        directory_path = "/Volumes/prox-share/mediatools/kids-media/tvshows/X-Men.The.Animated.Series/Season.2"
        if os.path.exists(directory_path):
            args.path = directory_path
        else:
            print("Please provide a path to a video file or directory")
            parser.print_help()
            return
    
    path = Path(args.path)
    
    if not path.exists():
        print(f"Path does not exist: {path}")
        return
    
    if path.is_file():
        # Process single file
        if args.validate:
            success = service.process_video_file_with_validation(str(path), args.output_dir)
        else:
            success = service.process_video_file(str(path), args.output_dir)
        
        if success:
            print("✅ File processed successfully!")
        else:
            print("❌ File processing failed!")
    
    elif path.is_dir():
        # Process directory
        if args.validate:
            print("⚠️  Validation mode is not yet implemented for directory processing")
            print("Processing directory without validation...")
        
        service.process_directory(str(path), args.output_dir)
    
    else:
        print(f"Invalid path: {path}")

if __name__ == "__main__":
    main() 