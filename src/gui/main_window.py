"""
Main window for Hebrew Subtitle Service GUI.
Provides the primary application interface with modern design.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import json

from config.config_manager import ConfigManager
from logging_system.subtitle_logger import SubtitleLogger
from security.security_manager import SecurityManager
from services.subtitle_service import SubtitleService
from gui.components import FileSelector, ProgressPanel, ResultsPanel, ConfigurationPanel

class MainWindow:
    """Main application window with modern design and responsive layout."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the main window.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path or 'config/config.yaml'
        self.config_manager = None
        self.logger = None
        self.security_manager = None
        
        # Initialize GUI
        self.root = tk.Tk()
        self.setup_window()
        self.setup_styles()
        self.create_widgets()
        self.setup_menu()
        self.setup_status_bar()
        
        # Processing queue for background tasks
        self.processing_queue = queue.Queue()
        self.processing_thread = None
        self.is_processing = False
        
        # Load configuration
        self.load_configuration()
        
        # Initialize subtitle service
        self.subtitle_service = None
        self.initialize_subtitle_service()
        
        # Start background processing
        self.start_background_processing()
    
    def setup_window(self):
        """Setup main window properties."""
        self.root.title("Hebrew Subtitle Service")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Center window on screen
        self.center_window()
        
        # Set window icon (if available)
        try:
            # self.root.iconbitmap('assets/icon.ico')  # Windows
            # self.root.iconbitmap('@assets/icon.xbm')  # Linux
            pass
        except:
            pass
    
    def center_window(self):
        """Center the window on the screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def setup_styles(self):
        """Setup modern ttk styles."""
        style = ttk.Style()
        
        # Configure modern theme
        try:
            style.theme_use('clam')  # or 'vista' on Windows
        except:
            pass
        
        # Custom styles
        style.configure('Title.TLabel', font=('Segoe UI', 16, 'bold'))
        style.configure('Subtitle.TLabel', font=('Segoe UI', 12))
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
        style.configure('Warning.TLabel', foreground='orange')
        
        # Button styles
        style.configure('Primary.TButton', 
                       font=('Segoe UI', 10, 'bold'),
                       padding=(10, 5))
        style.configure('Secondary.TButton',
                       font=('Segoe UI', 10),
                       padding=(8, 4))
        
        # Frame styles
        style.configure('Card.TFrame', relief='solid', borderwidth=1)
        style.configure('Header.TFrame', background='#f0f0f0')
    
    def create_widgets(self):
        """Create and layout all GUI widgets."""
        # Main container
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
        
        # Header
        self.create_header()
        
        # Main content area
        self.create_main_content()
        
        # Sidebar
        self.create_sidebar()
    
    def create_header(self):
        """Create the application header."""
        header_frame = ttk.Frame(self.main_frame, style='Header.TFrame')
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(header_frame, 
                               text="Hebrew Subtitle Service", 
                               style='Title.TLabel')
        title_label.grid(row=0, column=0, sticky=tk.W, padx=(10, 20))
        
        # Status indicator
        self.status_label = ttk.Label(header_frame, 
                                     text="Ready", 
                                     style='Success.TLabel')
        self.status_label.grid(row=0, column=1, sticky=tk.E, padx=(0, 10))
        
        # Action buttons
        button_frame = ttk.Frame(header_frame)
        button_frame.grid(row=0, column=2, sticky=tk.E, padx=(0, 10))
        
        self.start_button = ttk.Button(button_frame, 
                                      text="Start Processing", 
                                      style='Primary.TButton',
                                      command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_button = ttk.Button(button_frame, 
                                     text="Stop", 
                                     style='Secondary.TButton',
                                     command=self.stop_processing,
                                     state='disabled')
        self.stop_button.pack(side=tk.LEFT)
    
    def create_main_content(self):
        """Create the main content area with notebook."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))
        
        # File Selection Tab
        self.file_selector = FileSelector(self.notebook, self.on_files_selected)
        self.notebook.add(self.file_selector.frame, text="File Selection")
        
        # Progress Tab
        self.progress_panel = ProgressPanel(self.notebook, self.on_progress_update)
        self.notebook.add(self.progress_panel.frame, text="Progress")
        
        # Results Tab
        self.results_panel = ResultsPanel(self.notebook)
        self.notebook.add(self.results_panel.frame, text="Results")
        
        # Configuration Tab
        self.config_panel = ConfigurationPanel(self.notebook, self.on_config_save)
        self.notebook.add(self.config_panel.frame, text="Configuration")
    
    def create_sidebar(self):
        """Create the sidebar with quick actions and info."""
        sidebar_frame = ttk.Frame(self.main_frame, style='Card.TFrame', padding="10")
        sidebar_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        sidebar_frame.configure(width=250)
        
        # Quick Actions
        actions_label = ttk.Label(sidebar_frame, text="Quick Actions", style='Subtitle.TLabel')
        actions_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Add file button
        add_file_btn = ttk.Button(sidebar_frame, 
                                 text="Add Files", 
                                 style='Secondary.TButton',
                                 command=self.add_files)
        add_file_btn.pack(fill=tk.X, pady=(0, 5))
        
        # Add folder button
        add_folder_btn = ttk.Button(sidebar_frame, 
                                   text="Add Folder", 
                                   style='Secondary.TButton',
                                   command=self.add_folder)
        add_folder_btn.pack(fill=tk.X, pady=(0, 5))
        
        # Clear all button
        clear_btn = ttk.Button(sidebar_frame, 
                              text="Clear All", 
                              style='Secondary.TButton',
                              command=self.clear_files)
        clear_btn.pack(fill=tk.X, pady=(0, 20))
        
        # Statistics
        stats_label = ttk.Label(sidebar_frame, text="Statistics", style='Subtitle.TLabel')
        stats_label.pack(anchor=tk.W, pady=(0, 10))
        
        # File count
        self.file_count_label = ttk.Label(sidebar_frame, text="Files: 0")
        self.file_count_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Processing status
        self.processing_status_label = ttk.Label(sidebar_frame, text="Status: Idle")
        self.processing_status_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Last processed
        self.last_processed_label = ttk.Label(sidebar_frame, text="Last: None")
        self.last_processed_label.pack(anchor=tk.W, pady=(0, 20))
        
        # Security Status
        security_label = ttk.Label(sidebar_frame, text="Security Status", style='Subtitle.TLabel')
        security_label.pack(anchor=tk.W, pady=(0, 10))
        
        self.security_status_label = ttk.Label(sidebar_frame, text="Status: Unknown", style='Warning.TLabel')
        self.security_status_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Security report button
        security_report_btn = ttk.Button(sidebar_frame, 
                                        text="Security Report", 
                                        style='Secondary.TButton',
                                        command=self.show_security_report)
        security_report_btn.pack(fill=tk.X, pady=(0, 5))
    
    def setup_menu(self):
        """Setup application menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Add Files...", command=self.add_files)
        file_menu.add_command(label="Add Folder...", command=self.add_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Export Results...", command=self.export_results)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Processing menu
        processing_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Processing", menu=processing_menu)
        processing_menu.add_command(label="Start Processing", command=self.start_processing)
        processing_menu.add_command(label="Stop Processing", command=self.stop_processing)
        processing_menu.add_separator()
        processing_menu.add_command(label="Clear Results", command=self.clear_results)
        
        # Configuration menu
        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configuration", menu=config_menu)
        config_menu.add_command(label="Open Config", command=self.open_config)
        config_menu.add_command(label="Reload Config", command=self.reload_config)
        config_menu.add_separator()
        config_menu.add_command(label="Security Settings", command=self.open_security_settings)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        help_menu.add_command(label="About", command=self.show_about)
    
    def setup_status_bar(self):
        """Setup status bar at bottom of window."""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Status message
        self.status_message = ttk.Label(self.status_bar, text="Ready")
        self.status_message.pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.status_progress = ttk.Progressbar(self.status_bar, mode='indeterminate')
        self.status_progress.pack(side=tk.RIGHT, padx=5)
    
    def load_configuration(self):
        """Load application configuration."""
        try:
            self.config_manager = ConfigManager(self.config_path)
            self.logger = SubtitleLogger(self.config_manager.config)
            self.security_manager = SecurityManager(self.config_manager.config)
            
            # Update security status
            self.update_security_status()
            
            # Load configuration into UI
            if self.config_panel:
                self.config_panel.load_config(self.config_manager.config)
            
            self.logger.info("Configuration loaded successfully")
            self.update_status("Configuration loaded", "success")
            
        except Exception as e:
            messagebox.showerror("Configuration Error", 
                               f"Failed to load configuration:\n{str(e)}")
            self.update_status("Configuration error", "error")
    
    def initialize_subtitle_service(self):
        """Initialize the subtitle service with configuration."""
        try:
            if self.config_manager:
                config = self.config_manager.config
                api_config = config.get('api', {})
                
                opensubtitles_config = api_config.get('opensubtitles', {})
                openai_config = api_config.get('openai', {})
                
                self.subtitle_service = SubtitleService(
                    opensubtitles_username=opensubtitles_config.get('username'),
                    opensubtitles_password=opensubtitles_config.get('password'),
                    openai_api_key=openai_config.get('api_key')
                )
                
                if self.logger:
                    self.logger.info("Subtitle service initialized successfully")
                self.update_status("Subtitle service ready", "success")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize subtitle service: {e}")
            self.update_status("Subtitle service error", "error")
            messagebox.showerror("Service Error", 
                               f"Failed to initialize subtitle service:\n{str(e)}")
    
    def update_security_status(self):
        """Update security status display."""
        if self.security_manager:
            try:
                report = self.security_manager.get_security_report()
                status = report.get('security_status', 'unknown')
                
                if status == 'secure':
                    self.security_status_label.config(text="Status: Secure", style='Success.TLabel')
                elif status == 'warning':
                    self.security_status_label.config(text="Status: Warning", style='Warning.TLabel')
                else:
                    self.security_status_label.config(text="Status: Unknown", style='Error.TLabel')
                    
            except Exception as e:
                self.security_status_label.config(text="Status: Error", style='Error.TLabel')
    
    def start_background_processing(self):
        """Start background processing thread."""
        self.processing_thread = threading.Thread(target=self.background_processor, daemon=True)
        self.processing_thread.start()
    
    def background_processor(self):
        """Background thread for processing tasks."""
        while True:
            try:
                task = self.processing_queue.get(timeout=1)
                if task is None:  # Shutdown signal
                    break
                
                # Process the task
                self.process_task(task)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Background processing error: {e}")
    
    def process_task(self, task: Dict[str, Any]):
        """Process a background task."""
        task_type = task.get('type')
        
        if task_type == 'process_files':
            self.process_files_task(task)
        elif task_type == 'update_progress':
            self.update_progress_task(task)
        elif task_type == 'update_results':
            self.update_results_task(task)
    
    def process_files_task(self, task: Dict[str, Any]):
        """Process files in background."""
        files = task.get('files', [])
        
        if not self.subtitle_service:
            self.processing_queue.put({
                'type': 'update_results',
                'status': 'error',
                'message': 'Subtitle service not initialized'
            })
            return
        
        # Use None as output_dir to save files in the same directory as video files
        # This is the preferred behavior - subtitles should be next to their videos
        output_dir = None
        
        # Process each file
        for i, file_path in enumerate(files):
            if not self.is_processing:
                break
            
            try:
                # Update progress
                progress = (i + 1) / len(files) * 100
                self.processing_queue.put({
                    'type': 'update_progress',
                    'file': file_path,
                    'progress': progress,
                    'current': i + 1,
                    'total': len(files)
                })
                
                # Process the file with subtitle service
                if self.logger:
                    self.logger.info(f"Processing file: {file_path}")
                
                # Check if it's a directory
                if os.path.isdir(file_path):
                    success = self.subtitle_service.process_directory(file_path, output_dir)
                else:
                    success = self.subtitle_service.process_video_file_with_validation(file_path, output_dir)
                
                # Add result
                result = {
                    'file': file_path,
                    'status': 'Success' if success else 'Error',
                    'type': 'Directory' if os.path.isdir(file_path) else 'Video File',
                    'size': 'N/A',
                    'time': 'N/A'
                }
                
                self.processing_queue.put({
                    'type': 'update_results',
                    'result': result
                })
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error processing {file_path}: {e}")
                
                # Add error result
                result = {
                    'file': file_path,
                    'status': 'Error',
                    'type': 'Directory' if os.path.isdir(file_path) else 'Video File',
                    'size': 'N/A',
                    'time': 'N/A',
                    'error': str(e)
                }
                
                self.processing_queue.put({
                    'type': 'update_results',
                    'result': result
                })
        
        # Mark as complete
        self.processing_queue.put({
            'type': 'update_results',
            'status': 'completed',
            'files_processed': len(files)
        })
    
    def update_progress_task(self, task: Dict[str, Any]):
        """Update progress in main thread."""
        self.root.after(0, lambda: self.progress_panel.update_progress(
            task.get('file'),
            task.get('progress', 0),
            task.get('current', 0),
            task.get('total', 0)
        ))
    
    def update_results_task(self, task: Dict[str, Any]):
        """Update results in main thread."""
        if task.get('type') == 'update_results':
            if 'result' in task:
                # Single result update
                self.root.after(0, lambda: self.results_panel.add_result(task['result']))
            elif 'status' in task:
                # Status update (completed, error, etc.)
                if task['status'] == 'completed':
                    self.root.after(0, lambda: self.progress_panel.add_status_message(
                        f"Processing completed. {task.get('files_processed', 0)} files processed.", 
                        "success"
                    ))
                elif task['status'] == 'error':
                    self.root.after(0, lambda: self.progress_panel.add_status_message(
                        f"Processing error: {task.get('message', 'Unknown error')}", 
                        "error"
                    ))
    
    # Event handlers
    def on_files_selected(self, files: List[str]):
        """Handle file selection."""
        self.file_count_label.config(text=f"Files: {len(files)}")
        self.update_status(f"Selected {len(files)} files")
    
    def on_progress_update(self, file: str, progress: float):
        """Handle progress updates."""
        self.processing_status_label.config(text=f"Status: Processing {file}")
    
    def on_config_save(self, config: Dict[str, Any]):
        """Handle configuration save."""
        try:
            self.config_manager.save_config(config)
            self.reload_config()
            messagebox.showinfo("Success", "Configuration saved successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {e}")
    
    def add_files(self):
        """Add files via file dialog."""
        files = filedialog.askopenfilenames(
            title="Select Video Files",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mkv *.mov *.wmv"),
                ("All files", "*.*")
            ]
        )
        if files:
            self.file_selector.add_files(files)
    
    def add_folder(self):
        """Add folder via folder dialog."""
        folder = filedialog.askdirectory(title="Select Folder")
        if folder:
            self.file_selector.add_folder(folder)
    
    def clear_files(self):
        """Clear all selected files."""
        self.file_selector.clear_files()
    
    def start_processing(self):
        """Start processing selected files."""
        files = self.file_selector.get_selected_files()
        if not files:
            messagebox.showwarning("Warning", "No files selected for processing")
            return
        
        self.is_processing = True
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.status_progress.start()
        
        # Add processing task to queue
        self.processing_queue.put({
            'type': 'process_files',
            'files': files
        })
        
        self.update_status("Processing started")
    
    def stop_processing(self):
        """Stop processing."""
        self.is_processing = False
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.status_progress.stop()
        
        self.update_status("Processing stopped")
    
    def clear_results(self):
        """Clear all results."""
        self.results_panel.clear_results()
    
    def export_results(self):
        """Export results to file."""
        results = self.results_panel.get_results()
        if not results:
            messagebox.showwarning("Warning", "No results to export")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Export Results",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(results, f, indent=2)
                messagebox.showinfo("Success", f"Results exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export results: {e}")
    
    def open_config(self):
        """Open configuration file."""
        try:
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                subprocess.run(["notepad", self.config_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", self.config_path])
            else:  # Linux
                subprocess.run(["xdg-open", self.config_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open config file: {e}")
    
    def reload_config(self):
        """Reload configuration."""
        self.load_configuration()
    
    def open_security_settings(self):
        """Open security settings dialog."""
        # This would open a security settings dialog
        messagebox.showinfo("Security Settings", "Security settings dialog would open here")
    
    def show_security_report(self):
        """Show security report dialog."""
        if self.security_manager:
            report = self.security_manager.get_security_report()
            
            # Create a simple dialog to show the report
            dialog = tk.Toplevel(self.root)
            dialog.title("Security Report")
            dialog.geometry("600x400")
            
            text_widget = tk.Text(dialog, wrap=tk.WORD)
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            text_widget.insert(tk.END, json.dumps(report, indent=2))
            text_widget.config(state=tk.DISABLED)
    
    def show_user_guide(self):
        """Show user guide."""
        messagebox.showinfo("User Guide", "User guide would open here")
    
    def show_about(self):
        """Show about dialog."""
        messagebox.showinfo("About", 
                          "Hebrew Subtitle Service\n"
                          "Version 1.0\n\n"
                          "A modern application for downloading and translating subtitles.")
    
    def update_status(self, message: str, level: str = "info"):
        """Update status bar message."""
        self.status_message.config(text=message)
        
        if level == "error":
            self.status_message.config(style='Error.TLabel')
        elif level == "success":
            self.status_message.config(style='Success.TLabel')
        else:
            self.status_message.config(style='TLabel')
    
    def on_closing(self):
        """Handle application closing."""
        if self.is_processing:
            if messagebox.askokcancel("Quit", "Processing is in progress. Do you want to quit?"):
                self.stop_processing()
                self.root.quit()
        else:
            self.root.quit()
    
    def run(self):
        """Start the GUI application."""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop() 