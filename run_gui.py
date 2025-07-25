#!/usr/bin/env python3
"""
GUI Launcher for Hebrew Subtitle Service.
Starts the main GUI application.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def main():
    """Launch the GUI application."""
    try:
        # Check if tkinter is available
        try:
            import tkinter as tk
        except ImportError:
            print("❌ Error: tkinter is not available.")
            print("Please install tkinter for your system:")
            print("  - Ubuntu/Debian: sudo apt-get install python3-tk")
            print("  - macOS: brew install python-tk")
            print("  - Windows: tkinter should be included with Python")
            return 1
        
        # Import and run the main window
        from gui.main_window import MainWindow
        
        print("🚀 Starting Hebrew Subtitle Service GUI...")
        
        # Create and run the main window
        app = MainWindow()
        app.run()
        
        return 0
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Please ensure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        return 1
        
    except Exception as e:
        print(f"❌ Error starting GUI: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 