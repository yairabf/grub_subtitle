#!/usr/bin/env python3
"""
Manual test script for Background Service.

This script runs the background service manually for testing.
"""

import os
import sys
import time
import signal
import threading
from pathlib import Path
from dotenv import load_dotenv

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.background_service import BackgroundService, ServiceState
from config.config_manager import ConfigManager

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
    if hasattr(signal_handler, 'service') and signal_handler.service:
        signal_handler.service.stop()
    sys.exit(0)

def main():
    """Main function to run the background service."""
    print("🚀 Starting Background Service")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Check for required environment variables
    opensubtitles_username = os.getenv('OPENSUBTITLES_USERNAME')
    opensubtitles_password = os.getenv('OPENSUBTITLES_PASSWORD')
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if not opensubtitles_username or not opensubtitles_password:
        print("❌ Please set OPENSUBTITLES_USERNAME and OPENSUBTITLES_PASSWORD in your .env file")
        return
    
    if not openai_api_key:
        print("❌ Please set OPENAI_API_KEY in your .env file")
        return
    
    print("✅ Environment variables loaded successfully from .env file")
    
    # Create test directories
    test_video_dir = Path("./test_videos")
    test_video_dir.mkdir(exist_ok=True)
    
    # Create some test video files
    test_files = [
        "test_movie_1.mp4",
        "test_movie_2.mkv", 
        "test_series_episode_1.avi",
        "corrupted_video.mp4"
    ]
    
    for test_file in test_files:
        test_file_path = test_video_dir / test_file
        if not test_file_path.exists():
            # Create empty files for testing
            test_file_path.touch()
            print(f"📁 Created test file: {test_file}")
    
    # Initialize configuration manager
    config_manager = ConfigManager()
    
    # Use actual directory from environment, just adjust processing settings for testing
    test_config = {
        'service': {
            'processing': {
                'worker_threads': 2,  # Fewer workers for testing
                'queue_size': 10
            }
        }
    }
    
    # Update configuration using the set method
    for key, value in test_config.items():
        config_manager.set(key, value)
    
    print("✅ Configuration loaded successfully")
    
    # Initialize background service
    service = BackgroundService(config_manager)
    
    # Store service reference for signal handler
    signal_handler.service = service
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Add status callback to monitor service
    def status_callback(status):
        print(f"📊 Service Status: {status.state.value} | "
              f"Processed: {status.files_processed} | "
              f"Failed: {status.files_failed} | "
              f"Health: {status.health_score:.1f}")
    
    service.add_status_callback(status_callback)
    
    # Add state change callback
    def state_callback(old_state, new_state):
        print(f"🔄 State Change: {old_state.value} → {new_state.value}")
    
    service.add_state_callback(state_callback)
    
    print("✅ Service initialized successfully")
    print("\n🚀 Starting service...")
    
    # Start the service
    if service.start():
        print("✅ Service started successfully!")
        print("\n📋 Service is now running. Press Ctrl+C to stop.")
        
        # Monitor service for a while
        try:
            while service.is_in_state(ServiceState.RUNNING):
                time.sleep(5)
                
                # Print statistics every 30 seconds
                if int(time.time()) % 30 == 0:
                    stats = service.get_processing_statistics()
                    print(f"\n📈 Statistics: Queue: {stats['queue_size']} | "
                          f"Active Workers: {stats['active_workers']} | "
                          f"Completed: {stats['tasks_completed']} | "
                          f"Failed: {stats['tasks_failed']}")
        
        except KeyboardInterrupt:
            print("\n🛑 Keyboard interrupt received, stopping service...")
    
    else:
        print("❌ Failed to start service!")
        return
    
    # Stop the service
    print("🛑 Stopping service...")
    service.stop()
    
    # Wait for service to stop
    if service.wait_for_state(ServiceState.STOPPED, timeout=10.0):
        print("✅ Service stopped successfully!")
    else:
        print("⚠️ Service did not stop within timeout")
    
    # Print final statistics
    final_stats = service.get_processing_statistics()
    print(f"\n📊 Final Statistics:")
    print(f"   - Tasks Completed: {final_stats['tasks_completed']}")
    print(f"   - Tasks Failed: {final_stats['tasks_failed']}")
    print(f"   - Tasks Retried: {final_stats['tasks_retried']}")
    print(f"   - Queue Size: {final_stats['queue_size']}")
    
    print("\n🎉 Background service test completed!")

if __name__ == "__main__":
    main() 