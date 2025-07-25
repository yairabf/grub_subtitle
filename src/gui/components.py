"""
GUI components for Hebrew Subtitle Service.
Provides reusable UI components with modern design.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Any, Callable, Optional
from pathlib import Path
import json

class FileSelector:
    """File selection component with drag-and-drop support."""
    
    def __init__(self, parent, on_files_selected: Callable[[List[str]], None]):
        """
        Initialize file selector.
        
        Args:
            parent: Parent widget
            on_files_selected: Callback when files are selected
        """
        self.parent = parent
        self.on_files_selected = on_files_selected
        self.selected_files: List[str] = []
        
        self.frame = ttk.Frame(parent, padding="10")
        self.create_widgets()
    
    def create_widgets(self):
        """Create file selector widgets."""
        # Header
        header_label = ttk.Label(self.frame, text="Select Video Files", style='Title.TLabel')
        header_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Drop zone
        self.drop_frame = ttk.Frame(self.frame, style='Card.TFrame', padding="20")
        self.drop_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        drop_label = ttk.Label(self.drop_frame, 
                              text="Drag and drop video files here\nor click to browse",
                              style='Subtitle.TLabel',
                              justify=tk.CENTER)
        drop_label.pack(expand=True)
        
        # Bind click event
        self.drop_frame.bind("<Button-1>", self.browse_files)
        drop_label.bind("<Button-1>", self.browse_files)
        
        # File list
        list_frame = ttk.Frame(self.frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Listbox with scrollbar
        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        self.file_listbox = tk.Listbox(listbox_frame, selectmode=tk.EXTENDED)
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        button_frame = ttk.Frame(self.frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        add_btn = ttk.Button(button_frame, text="Add Files", command=self.browse_files)
        add_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        add_folder_btn = ttk.Button(button_frame, text="Add Folder", command=self.browse_folder)
        add_folder_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        clear_btn = ttk.Button(button_frame, text="Clear All", command=self.clear_files)
        clear_btn.pack(side=tk.LEFT)
        
        # File count
        self.file_count_label = ttk.Label(button_frame, text="0 files selected")
        self.file_count_label.pack(side=tk.RIGHT)
    
    def browse_files(self, event=None):
        """Open file browser dialog."""
        files = filedialog.askopenfilenames(
            title="Select Video Files",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mkv *.mov *.wmv"),
                ("All files", "*.*")
            ]
        )
        if files:
            self.add_files(files)
    
    def browse_folder(self):
        """Open folder browser dialog."""
        folder = filedialog.askdirectory(title="Select Folder")
        if folder:
            self.add_folder(folder)
    
    def add_files(self, files: List[str]):
        """Add files to the list."""
        for file_path in files:
            if file_path not in self.selected_files:
                self.selected_files.append(file_path)
                self.file_listbox.insert(tk.END, Path(file_path).name)
        
        self.update_file_count()
        self.on_files_selected(self.selected_files)
    
    def add_folder(self, folder_path: str):
        """Add all video files from a folder."""
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv'}
        folder = Path(folder_path)
        
        video_files = []
        for file_path in folder.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                video_files.append(str(file_path))
        
        if video_files:
            self.add_files(video_files)
        else:
            messagebox.showinfo("No Files", "No video files found in the selected folder")
    
    def clear_files(self):
        """Clear all selected files."""
        self.selected_files.clear()
        self.file_listbox.delete(0, tk.END)
        self.update_file_count()
        self.on_files_selected(self.selected_files)
    
    def update_file_count(self):
        """Update file count display."""
        count = len(self.selected_files)
        self.file_count_label.config(text=f"{count} file{'s' if count != 1 else ''} selected")
    
    def get_selected_files(self) -> List[str]:
        """Get list of selected files."""
        return self.selected_files.copy()


class ProgressPanel:
    """Progress tracking component with detailed status."""
    
    def __init__(self, parent, on_progress_update: Callable[[str, float], None]):
        """
        Initialize progress panel.
        
        Args:
            parent: Parent widget
            on_progress_update: Callback for progress updates
        """
        self.parent = parent
        self.on_progress_update = on_progress_update
        
        self.frame = ttk.Frame(parent, padding="10")
        self.create_widgets()
    
    def create_widgets(self):
        """Create progress panel widgets."""
        # Header
        header_label = ttk.Label(self.frame, text="Processing Progress", style='Title.TLabel')
        header_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Overall progress
        overall_frame = ttk.LabelFrame(self.frame, text="Overall Progress", padding="10")
        overall_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.overall_progress = ttk.Progressbar(overall_frame, mode='determinate')
        self.overall_progress.pack(fill=tk.X, pady=(0, 5))
        
        self.overall_label = ttk.Label(overall_frame, text="0% complete")
        self.overall_label.pack(anchor=tk.W)
        
        # Current file progress
        current_frame = ttk.LabelFrame(self.frame, text="Current File", padding="10")
        current_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.current_file_label = ttk.Label(current_frame, text="No file selected")
        self.current_file_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.current_progress = ttk.Progressbar(current_frame, mode='determinate')
        self.current_progress.pack(fill=tk.X, pady=(0, 5))
        
        self.current_label = ttk.Label(current_frame, text="0% complete")
        self.current_label.pack(anchor=tk.W)
        
        # Processing queue
        queue_frame = ttk.LabelFrame(self.frame, text="Processing Queue", padding="10")
        queue_frame.pack(fill=tk.BOTH, expand=True)
        
        # Queue listbox
        self.queue_listbox = tk.Listbox(queue_frame, height=10)
        queue_scrollbar = ttk.Scrollbar(queue_frame, orient=tk.VERTICAL, command=self.queue_listbox.yview)
        self.queue_listbox.configure(yscrollcommand=queue_scrollbar.set)
        
        self.queue_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        queue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status messages
        status_frame = ttk.LabelFrame(self.frame, text="Status Messages", padding="10")
        status_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.status_text = tk.Text(status_frame, height=6, wrap=tk.WORD)
        status_scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_scrollbar.set)
        
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def update_progress(self, file_path: str, progress: float, current: int, total: int):
        """Update progress display."""
        # Update overall progress
        overall_progress = (current / total) * 100 if total > 0 else 0
        self.overall_progress['value'] = overall_progress
        self.overall_label.config(text=f"{overall_progress:.1f}% complete ({current}/{total})")
        
        # Update current file progress
        self.current_file_label.config(text=Path(file_path).name)
        self.current_progress['value'] = progress
        self.current_label.config(text=f"{progress:.1f}% complete")
        
        # Call callback
        self.on_progress_update(file_path, progress)
    
    def add_status_message(self, message: str, level: str = "info"):
        """Add status message to the log."""
        import datetime
        
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if level == "error":
            prefix = f"[{timestamp}] ERROR: "
            tag = "error"
        elif level == "warning":
            prefix = f"[{timestamp}] WARNING: "
            tag = "warning"
        elif level == "success":
            prefix = f"[{timestamp}] SUCCESS: "
            tag = "success"
        else:
            prefix = f"[{timestamp}] INFO: "
            tag = "info"
        
        self.status_text.insert(tk.END, prefix + message + "\n")
        
        # Apply tags for coloring
        self.status_text.tag_config("error", foreground="red")
        self.status_text.tag_config("warning", foreground="orange")
        self.status_text.tag_config("success", foreground="green")
        self.status_text.tag_config("info", foreground="black")
        
        # Scroll to bottom
        self.status_text.see(tk.END)
    
    def clear_progress(self):
        """Clear all progress displays."""
        self.overall_progress['value'] = 0
        self.overall_label.config(text="0% complete")
        self.current_file_label.config(text="No file selected")
        self.current_progress['value'] = 0
        self.current_label.config(text="0% complete")
        self.status_text.delete(1.0, tk.END)


class ResultsPanel:
    """Results display component with detailed information."""
    
    def __init__(self, parent):
        """
        Initialize results panel.
        
        Args:
            parent: Parent widget
        """
        self.parent = parent
        self.results: List[Dict[str, Any]] = []
        
        self.frame = ttk.Frame(parent, padding="10")
        self.create_widgets()
    
    def create_widgets(self):
        """Create results panel widgets."""
        # Header
        header_frame = ttk.Frame(self.frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        header_label = ttk.Label(header_frame, text="Processing Results", style='Title.TLabel')
        header_label.pack(side=tk.LEFT)
        
        # Summary
        self.summary_label = ttk.Label(header_frame, text="0 files processed")
        self.summary_label.pack(side=tk.RIGHT)
        
        # Results treeview
        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview
        columns = ('File', 'Status', 'Type', 'Size', 'Time')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        self.tree.heading('File', text='File Name')
        self.tree.heading('Status', text='Status')
        self.tree.heading('Type', text='Type')
        self.tree.heading('Size', text='Size')
        self.tree.heading('Time', text='Processing Time')
        
        self.tree.column('File', width=200)
        self.tree.column('Status', width=100)
        self.tree.column('Type', width=100)
        self.tree.column('Size', width=100)
        self.tree.column('Time', width=100)
        
        # Scrollbars
        tree_scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scrollbar_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scrollbar_y.set, xscrollcommand=tree_scrollbar_x.set)
        
        # Pack treeview and scrollbars
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Buttons
        button_frame = ttk.Frame(self.frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        export_btn = ttk.Button(button_frame, text="Export Results", command=self.export_results)
        export_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        clear_btn = ttk.Button(button_frame, text="Clear Results", command=self.clear_results)
        clear_btn.pack(side=tk.LEFT)
        
        # Details panel
        details_frame = ttk.LabelFrame(self.frame, text="Details", padding="10")
        details_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.details_text = tk.Text(details_frame, height=8, wrap=tk.WORD)
        details_scrollbar = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scrollbar.set)
        
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection event
        self.tree.bind('<<TreeviewSelect>>', self.on_item_selected)
    
    def add_result(self, result: Dict[str, Any]):
        """Add a result to the display."""
        self.results.append(result)
        
        # Add to treeview
        file_name = Path(result.get('file', 'Unknown')).name
        status = result.get('status', 'Unknown')
        result_type = result.get('type', 'Unknown')
        size = result.get('size', 'Unknown')
        time_taken = result.get('time', 'Unknown')
        
        item = self.tree.insert('', tk.END, values=(file_name, status, result_type, size, time_taken))
        
        # Color code based on status
        if status == 'Success':
            self.tree.tag_configure('success', foreground='green')
            self.tree.item(item, tags=('success',))
        elif status == 'Error':
            self.tree.tag_configure('error', foreground='red')
            self.tree.item(item, tags=('error',))
        elif status == 'Warning':
            self.tree.tag_configure('warning', foreground='orange')
            self.tree.item(item, tags=('warning',))
        
        # Update summary
        self.update_summary()
    
    def update_summary(self):
        """Update summary display."""
        total = len(self.results)
        successful = len([r for r in self.results if r.get('status') == 'Success'])
        failed = len([r for r in self.results if r.get('status') == 'Error'])
        
        self.summary_label.config(text=f"{total} files processed ({successful} successful, {failed} failed)")
    
    def on_item_selected(self, event):
        """Handle item selection in treeview."""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            values = self.tree.item(item, 'values')
            
            # Find corresponding result
            file_name = values[0]
            result = next((r for r in self.results if Path(r.get('file', '')).name == file_name), None)
            
            if result:
                # Display details
                details = json.dumps(result, indent=2)
                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(tk.END, details)
    
    def clear_results(self):
        """Clear all results."""
        self.results.clear()
        self.tree.delete(*self.tree.get_children())
        self.details_text.delete(1.0, tk.END)
        self.update_summary()
    
    def export_results(self):
        """Export results to file."""
        if not self.results:
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
                    json.dump(self.results, f, indent=2)
                messagebox.showinfo("Success", f"Results exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export results: {e}")
    
    def get_results(self) -> List[Dict[str, Any]]:
        """Get all results."""
        return self.results.copy()


class ConfigurationPanel:
    """Configuration management component."""
    
    def __init__(self, parent, on_config_save: Callable[[Dict[str, Any]], None]):
        """
        Initialize configuration panel.
        
        Args:
            parent: Parent widget
            on_config_save: Callback when configuration is saved
        """
        self.parent = parent
        self.on_config_save = on_config_save
        self.config: Dict[str, Any] = {}
        
        self.frame = ttk.Frame(parent, padding="10")
        self.create_widgets()
    
    def create_widgets(self):
        """Create configuration panel widgets."""
        # Header
        header_label = ttk.Label(self.frame, text="Configuration", style='Title.TLabel')
        header_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Create notebook for different config sections
        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # API Configuration
        self.create_api_config()
        
        # Processing Configuration
        self.create_processing_config()
        
        # Security Configuration
        self.create_security_config()
        
        # UI Configuration
        self.create_ui_config()
        
        # Buttons
        button_frame = ttk.Frame(self.frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        save_btn = ttk.Button(button_frame, text="Save Configuration", 
                             style='Primary.TButton',
                             command=self.save_configuration)
        save_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        reset_btn = ttk.Button(button_frame, text="Reset to Defaults", 
                              command=self.reset_configuration)
        reset_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        test_btn = ttk.Button(button_frame, text="Test Configuration", 
                             command=self.test_configuration)
        test_btn.pack(side=tk.LEFT)
    
    def create_api_config(self):
        """Create API configuration section."""
        api_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(api_frame, text="API Settings")
        
        # OpenSubtitles Configuration
        opensubtitles_frame = ttk.LabelFrame(api_frame, text="OpenSubtitles API", padding="10")
        opensubtitles_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(opensubtitles_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.opensubtitles_username = ttk.Entry(opensubtitles_frame, width=30)
        self.opensubtitles_username.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        ttk.Label(opensubtitles_frame, text="Password:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.opensubtitles_password = ttk.Entry(opensubtitles_frame, width=30, show="*")
        self.opensubtitles_password.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        ttk.Label(opensubtitles_frame, text="Base URL:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.opensubtitles_url = ttk.Entry(opensubtitles_frame, width=30)
        self.opensubtitles_url.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        # OpenAI Configuration
        openai_frame = ttk.LabelFrame(api_frame, text="OpenAI API", padding="10")
        openai_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(openai_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.openai_api_key = ttk.Entry(openai_frame, width=50, show="*")
        self.openai_api_key.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        ttk.Label(openai_frame, text="Model:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.openai_model = ttk.Combobox(openai_frame, values=['gpt-3.5-turbo', 'gpt-4'], width=20)
        self.openai_model.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        # Configure grid weights
        opensubtitles_frame.columnconfigure(1, weight=1)
        openai_frame.columnconfigure(1, weight=1)
    
    def create_processing_config(self):
        """Create processing configuration section."""
        processing_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(processing_frame, text="Processing")
        
        # Chunking settings
        chunking_frame = ttk.LabelFrame(processing_frame, text="Translation Chunking", padding="10")
        chunking_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(chunking_frame, text="Chunk Size:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.chunk_size = ttk.Spinbox(chunking_frame, from_=1000, to=5000, width=10)
        self.chunk_size.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        ttk.Label(chunking_frame, text="Max Blocks per Chunk:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.max_blocks = ttk.Spinbox(chunking_frame, from_=5, to=20, width=10)
        self.max_blocks.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        # Validation settings
        validation_frame = ttk.LabelFrame(processing_frame, text="Validation", padding="10")
        validation_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(validation_frame, text="Min Hebrew Ratio:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.min_hebrew_ratio = ttk.Spinbox(validation_frame, from_=0.1, to=1.0, increment=0.1, width=10)
        self.min_hebrew_ratio.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        # Configure grid weights
        chunking_frame.columnconfigure(1, weight=1)
        validation_frame.columnconfigure(1, weight=1)
    
    def create_security_config(self):
        """Create security configuration section."""
        security_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(security_frame, text="Security")
        
        # Encryption settings
        encryption_frame = ttk.LabelFrame(security_frame, text="Encryption", padding="10")
        encryption_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.encrypt_api_keys = tk.BooleanVar()
        ttk.Checkbutton(encryption_frame, text="Encrypt API Keys", 
                       variable=self.encrypt_api_keys).pack(anchor=tk.W, pady=2)
        
        self.audit_logging = tk.BooleanVar()
        ttk.Checkbutton(encryption_frame, text="Enable Audit Logging", 
                       variable=self.audit_logging).pack(anchor=tk.W, pady=2)
        
        # Secure storage
        storage_frame = ttk.LabelFrame(security_frame, text="Secure Storage", padding="10")
        storage_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(storage_frame, text="Secure Storage Path:").pack(anchor=tk.W, pady=2)
        self.secure_storage_path = ttk.Entry(storage_frame, width=50)
        self.secure_storage_path.pack(fill=tk.X, pady=2)
    
    def create_ui_config(self):
        """Create UI configuration section."""
        ui_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(ui_frame, text="User Interface")
        
        # Theme settings
        theme_frame = ttk.LabelFrame(ui_frame, text="Theme", padding="10")
        theme_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(theme_frame, text="Theme:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.theme = ttk.Combobox(theme_frame, values=['default', 'dark', 'light'], width=20)
        self.theme.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        # Paths
        paths_frame = ttk.LabelFrame(ui_frame, text="Paths", padding="10")
        paths_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(paths_frame, text="Default Output Directory:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.default_output_dir = ttk.Entry(paths_frame, width=50)
        self.default_output_dir.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        ttk.Label(paths_frame, text="Log Directory:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.log_directory = ttk.Entry(paths_frame, width=50)
        self.log_directory.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        # Configure grid weights
        theme_frame.columnconfigure(1, weight=1)
        paths_frame.columnconfigure(1, weight=1)
    
    def load_config(self, config: Dict[str, Any]):
        """Load configuration into the UI."""
        self.config = config.copy()
        
        # API settings
        api_config = config.get('api', {})
        
        opensubtitles_config = api_config.get('opensubtitles', {})
        self.opensubtitles_username.delete(0, tk.END)
        self.opensubtitles_username.insert(0, opensubtitles_config.get('username', ''))
        
        self.opensubtitles_password.delete(0, tk.END)
        self.opensubtitles_password.insert(0, opensubtitles_config.get('password', ''))
        
        self.opensubtitles_url.delete(0, tk.END)
        self.opensubtitles_url.insert(0, opensubtitles_config.get('base_url', ''))
        
        openai_config = api_config.get('openai', {})
        self.openai_api_key.delete(0, tk.END)
        self.openai_api_key.insert(0, openai_config.get('api_key', ''))
        
        self.openai_model.set(openai_config.get('model', 'gpt-3.5-turbo'))
        
        # Processing settings
        processing_config = config.get('processing', {})
        self.chunk_size.set(processing_config.get('chunk_size', 3000))
        self.max_blocks.set(processing_config.get('max_blocks_per_chunk', 10))
        
        validation_config = config.get('validation', {})
        self.min_hebrew_ratio.set(validation_config.get('min_hebrew_ratio', 0.5))
        
        # Security settings
        security_config = config.get('security', {})
        self.encrypt_api_keys.set(security_config.get('encrypt_api_keys', True))
        self.audit_logging.set(security_config.get('audit_logging', True))
        self.secure_storage_path.delete(0, tk.END)
        self.secure_storage_path.insert(0, security_config.get('secure_storage_path', './secure'))
        
        # UI settings
        ui_config = config.get('ui', {})
        self.theme.set(ui_config.get('theme', 'default'))
        
        paths_config = config.get('paths', {})
        self.default_output_dir.delete(0, tk.END)
        self.default_output_dir.insert(0, paths_config.get('default_output_dir', './output'))
        
        self.log_directory.delete(0, tk.END)
        self.log_directory.insert(0, paths_config.get('log_directory', './logs'))
    
    def save_configuration(self):
        """Save configuration from UI."""
        config = {
            'api': {
                'opensubtitles': {
                    'username': self.opensubtitles_username.get(),
                    'password': self.opensubtitles_password.get(),
                    'base_url': self.opensubtitles_url.get()
                },
                'openai': {
                    'api_key': self.openai_api_key.get(),
                    'model': self.openai_model.get()
                }
            },
            'processing': {
                'chunk_size': int(self.chunk_size.get()),
                'max_blocks_per_chunk': int(self.max_blocks.get())
            },
            'validation': {
                'min_hebrew_ratio': float(self.min_hebrew_ratio.get())
            },
            'security': {
                'encrypt_api_keys': self.encrypt_api_keys.get(),
                'audit_logging': self.audit_logging.get(),
                'secure_storage_path': self.secure_storage_path.get()
            },
            'ui': {
                'theme': self.theme.get()
            },
            'paths': {
                'default_output_dir': self.default_output_dir.get(),
                'log_directory': self.log_directory.get()
            }
        }
        
        self.on_config_save(config)
    
    def reset_configuration(self):
        """Reset configuration to defaults."""
        if messagebox.askyesno("Reset Configuration", 
                              "Are you sure you want to reset all configuration to defaults?"):
            # Load default configuration
            default_config = {
                'api': {
                    'opensubtitles': {
                        'username': '',
                        'password': '',
                        'base_url': 'https://api.opensubtitles.com/xml-rpc'
                    },
                    'openai': {
                        'api_key': '',
                        'model': 'gpt-3.5-turbo'
                    }
                },
                'processing': {
                    'chunk_size': 3000,
                    'max_blocks_per_chunk': 10
                },
                'validation': {
                    'min_hebrew_ratio': 0.5
                },
                'security': {
                    'encrypt_api_keys': True,
                    'audit_logging': True,
                    'secure_storage_path': './secure'
                },
                'ui': {
                    'theme': 'default'
                },
                'paths': {
                    'default_output_dir': './output',
                    'log_directory': './logs'
                }
            }
            
            self.load_config(default_config)
    
    def test_configuration(self):
        """Test the current configuration."""
        # This would test API connections and validate settings
        messagebox.showinfo("Test Configuration", 
                          "Configuration testing would be implemented here.\n"
                          "This would test API connections and validate all settings.") 