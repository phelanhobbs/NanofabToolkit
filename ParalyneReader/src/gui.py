import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import os
import sys
from tkinter import messagebox
import csv
import threading
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import random
import colorsys
import numpy as np
from scipy import stats
from scipy.signal import savgol_filter, medfilt
from scipy.ndimage import gaussian_filter1d
from ParalyneReader import list_files, download_file, return_selected
import logging
from concurrent.futures import ThreadPoolExecutor
import queue
import time

class ParalyneReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Paralyne Reader")
        self.root.geometry("1400x900")
        self.root.resizable(True, True)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)        # Store downloaded files for graphing
        self.downloaded_files = []
        self.columns = []
        
        # Generate distinct colors for plots
        self.color_cycle = self.generate_distinct_colors(20)
        
        # Track the selected file for time offset
        self.selected_file_index = 0
        
        # Store per-file time offsets
        self.file_offsets = {}
        
        # Store current plot data
        self.current_file_data = []
        self.current_column = ""
        self.current_log_scale = False

        # Performance optimization: Add data caching and threading
        self.raw_data_cache = {}  # Cache raw file data
        self.processed_data_cache = {}  # Cache processed data
        self.loading_threads = {}  # Track active loading threads
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        self.load_queue = queue.Queue()
        
        # Performance settings
        self.max_plot_points = 2000  # Downsample for plotting
        self.chunk_size = 10000  # Process files in chunks

        # Create main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Title
        title_label = ttk.Label(main_frame, text="Paralyne File Reader", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(0, 10))

        # Create horizontal paned window for the main content
        h_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        h_paned.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Left side - File management
        self.create_file_management_frame(h_paned)
        
        # Right side - Graph and controls
        self.create_graph_frame(h_paned)

        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready", foreground="green")
        self.status_label.grid(row=2, column=0, pady=(10, 0), sticky="w")

        # Load initial file list
        self.refresh_file_list()

    def generate_distinct_colors(self, n):
        """Generate n visually distinct colors"""
        primary_colors = [
            '#FF0000', '#0000FF', '#00CC00', '#FF00FF', '#FFCC00', '#00CCFF',
            '#FF6600', '#9900CC', '#006600', '#CC0000', '#000099', '#FF9999',
            '#9999FF', '#99FF99', '#FF99FF', '#FFFF99', '#99FFFF'
        ]
        
        if n <= len(primary_colors):
            return primary_colors[:n]
        
        colors = primary_colors.copy()
        remaining = n - len(colors)
        
        for i in range(remaining):
            h = i / remaining
            s = 0.85 if i % 2 else 0.7
            v = 0.9 if i % 4 < 2 else 0.7
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            colors.append(f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}')
        
        return colors

    def create_file_management_frame(self, parent):
        """Create the file management frame"""
        file_frame = ttk.Frame(parent)
        parent.add(file_frame, weight=1)
        
        file_frame.columnconfigure(0, weight=1)
        file_frame.rowconfigure(1, weight=1)
        file_frame.rowconfigure(3, weight=1)

        # File list frame
        list_frame = ttk.LabelFrame(file_frame, text="Available Files", padding="5")
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Treeview for file list
        columns = ("filename", "size", "modified")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        
        # Configure tags for different file states
        self.tree.tag_configure("downloaded", foreground="gray", font=("TkDefaultFont", 9, "italic"))
        
        # Define column headings and widths
        self.tree.heading("filename", text="Filename", anchor="w")
        self.tree.heading("size", text="Size", anchor="center")
        self.tree.heading("modified", text="Last Modified", anchor="center")
        
        self.tree.column("filename", width=250, anchor="w")
        self.tree.column("size", width=80, anchor="center")
        self.tree.column("modified", width=120, anchor="center")

        # Scrollbars for treeview
        v_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Grid treeview and scrollbars
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Button frame
        button_frame = ttk.Frame(file_frame)
        button_frame.grid(row=1, column=0, pady=(5, 0), sticky=(tk.W, tk.E))
        button_frame.columnconfigure(1, weight=1)

        # Buttons
        self.refresh_btn = ttk.Button(button_frame, text="Refresh List", command=self.refresh_file_list)
        self.refresh_btn.grid(row=0, column=0, padx=(0, 10))

        self.download_btn = ttk.Button(button_frame, text="Download Selected", command=self.download_selected_file)
        self.download_btn.grid(row=0, column=2, padx=(10, 0))

        # Downloaded files frame
        downloaded_frame = ttk.LabelFrame(file_frame, text="Downloaded Files", padding="5")
        downloaded_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))
        downloaded_frame.columnconfigure(0, weight=1)
        downloaded_frame.rowconfigure(0, weight=1)

        # Treeview for downloaded files
        downloaded_columns = ("filename", "status", "columns")
        self.downloaded_tree = ttk.Treeview(downloaded_frame, columns=downloaded_columns, show="headings", height=6)
        
        self.downloaded_tree.heading("filename", text="Downloaded File", anchor="w")
        self.downloaded_tree.heading("status", text="Status", anchor="center")
        self.downloaded_tree.heading("columns", text="Columns Available", anchor="center")
        
        self.downloaded_tree.column("filename", width=250, anchor="w")
        self.downloaded_tree.column("status", width=80, anchor="center")
        self.downloaded_tree.column("columns", width=120, anchor="center")

        # Scrollbar for downloaded files
        downloaded_scrollbar = ttk.Scrollbar(downloaded_frame, orient="vertical", command=self.downloaded_tree.yview)
        self.downloaded_tree.configure(yscrollcommand=downloaded_scrollbar.set)

        self.downloaded_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        downloaded_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Downloaded files buttons
        downloaded_button_frame = ttk.Frame(downloaded_frame)
        downloaded_button_frame.grid(row=1, column=0, pady=(5, 0), sticky=(tk.W, tk.E))

        ttk.Button(downloaded_button_frame, text="Remove Selected", command=self.remove_downloaded_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(downloaded_button_frame, text="Clear All", command=self.clear_downloaded_files).pack(side=tk.LEFT, padx=5)

    def create_graph_frame(self, parent):
        """Create the graphing frame"""
        graph_frame = ttk.Frame(parent)
        parent.add(graph_frame, weight=2)
        
        graph_frame.columnconfigure(0, weight=1)
        graph_frame.rowconfigure(3, weight=1)

        # Graph options frame
        options_frame = ttk.LabelFrame(graph_frame, text="Graph Options")
        options_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        options_frame.columnconfigure(0, weight=1)

        options_inner_frame = ttk.Frame(options_frame)
        options_inner_frame.pack(fill=tk.X, padx=10, pady=5)
        options_inner_frame.columnconfigure(1, weight=1)

        # Column selection
        ttk.Label(options_inner_frame, text="Column:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.column_var = tk.StringVar()
        self.column_dropdown = ttk.Combobox(options_inner_frame, textvariable=self.column_var, 
                                           width=20, state="readonly")
        self.column_dropdown.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        # Options in second row
        options_row2 = ttk.Frame(options_inner_frame)
        options_row2.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        # Log scale option
        self.log_scale_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_row2, text="Log scale", 
                       variable=self.log_scale_var).pack(side=tk.LEFT, padx=(0, 10))

        # Auto-zoom toggle
        self.auto_zoom_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_row2, text="Auto-zoom", 
                       variable=self.auto_zoom_var).pack(side=tk.LEFT, padx=(0, 10))

        # Show normalized data option
        self.show_normalized_var = tk.BooleanVar(value=True)
        normalized_check = ttk.Checkbutton(options_row2, text="Show normalized", 
                       variable=self.show_normalized_var, command=self.on_normalization_change)
        normalized_check.pack(side=tk.LEFT, padx=(0, 10))

        # Graph button
        ttk.Button(options_row2, text="Generate Graph", 
                  command=self.generate_graph).pack(side=tk.RIGHT)

        # Normalization options frame
        norm_frame = ttk.LabelFrame(graph_frame, text="Noise Reduction & Normalization")
        norm_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        norm_inner = ttk.Frame(norm_frame)
        norm_inner.pack(fill=tk.X, padx=10, pady=5)
        norm_inner.columnconfigure(1, weight=1)

        # Smoothing method selection
        ttk.Label(norm_inner, text="Smoothing:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.smoothing_var = tk.StringVar(value="moving_average")
        smoothing_combo = ttk.Combobox(norm_inner, textvariable=self.smoothing_var, 
                                      values=["none", "moving_average", "savgol", "gaussian", "median"], 
                                      width=15, state="readonly")
        smoothing_combo.grid(row=0, column=1, sticky="w", padx=(0, 10))
        smoothing_combo.bind("<<ComboboxSelected>>", self.on_processing_change)

        # Window size for smoothing
        ttk.Label(norm_inner, text="Window:").grid(row=0, column=2, sticky="w", padx=(10, 5))
        self.window_size_var = tk.IntVar(value=2500)
        window_spin = ttk.Spinbox(norm_inner, from_=3, to=10000, increment=2, 
                                 textvariable=self.window_size_var, width=8, 
                                 command=self.on_processing_change)
        window_spin.grid(row=0, column=3, sticky="w", padx=(0, 10))

        # Normalization method
        ttk.Label(norm_inner, text="Normalize:").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(5, 0))
        self.normalize_var = tk.StringVar(value="none")
        normalize_combo = ttk.Combobox(norm_inner, textvariable=self.normalize_var, 
                                      values=["none", "minmax", "zscore", "robust"], 
                                      width=15, state="readonly")
        normalize_combo.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(5, 0))
        normalize_combo.bind("<<ComboboxSelected>>", self.on_processing_change)

        # Time offset controls - HIDDEN FOR NOW
        # time_offset_frame = ttk.LabelFrame(graph_frame, text="Time Alignment")
        # time_offset_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        # time_offset_frame.columnconfigure(1, weight=1)

        # # File selector for time offset
        # ttk.Label(time_offset_frame, text="File:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        # self.file_selector_var = tk.StringVar()
        # self.file_selector = ttk.Combobox(time_offset_frame, textvariable=self.file_selector_var, 
        #                                  width=30, state="readonly")
        # self.file_selector.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        # self.file_selector.bind("<<ComboboxSelected>>", self.on_file_selected)

        # # Slider frame
        # ttk.Label(time_offset_frame, text="Offset (s):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        
        # slider_frame = ttk.Frame(time_offset_frame)
        # slider_frame.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        # slider_frame.columnconfigure(1, weight=1)

        # self.time_offset_var = tk.DoubleVar(value=0.0)
        # self.time_offset_slider = ttk.Scale(
        #     slider_frame, 
        #     from_=-300.0, 
        #     to=300.0, 
        #     variable=self.time_offset_var, 
        #     orient=tk.HORIZONTAL,
        #     command=self.update_time_offset
        # )
        # self.time_offset_slider.grid(row=0, column=1, sticky="ew", padx=5)

        # # Fine adjustment buttons
        # ttk.Button(slider_frame, text="◄", width=2, 
        #           command=lambda: self.adjust_time_offset(-1.0)).grid(row=0, column=0)

        # self.time_offset_entry = ttk.Entry(slider_frame, width=8, 
        #                                  textvariable=self.time_offset_var)
        # self.time_offset_entry.grid(row=0, column=2, padx=5)
        # self.time_offset_entry.bind("<Return>", self.on_offset_entry)
        # self.time_offset_entry.bind("<FocusOut>", self.on_offset_entry)

        # ttk.Button(slider_frame, text="►", width=2, 
        #           command=lambda: self.adjust_time_offset(1.0)).grid(row=0, column=3)

        # # Reset buttons frame
        # reset_frame = ttk.Frame(time_offset_frame)
        # reset_frame.grid(row=2, column=0, columnspan=2, pady=5)

        # ttk.Button(reset_frame, text="Reset Offset", 
        #           command=self.reset_time_offset).pack(side=tk.LEFT, padx=5)
        # ttk.Button(reset_frame, text="Reset All Files", 
        #           command=self.reset_all_offsets).pack(side=tk.LEFT, padx=5)
        
        # Initialize variables for compatibility
        self.file_selector_var = tk.StringVar()
        self.time_offset_var = tk.DoubleVar(value=0.0)
        self.file_selector = None
        
        # Graph display frame
        display_frame = ttk.LabelFrame(graph_frame, text="Graph")
        display_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Progress bar for file loading
        self.progress_frame = ttk.Frame(display_frame)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, 
            variable=self.progress_var, 
            maximum=100,
            mode='determinate'
        )
        self.progress_label = ttk.Label(self.progress_frame, text="")
        
        # Initially hide progress bar
        self.progress_frame.pack_forget()

        # Create matplotlib figure
        self.figure = plt.Figure(figsize=(8, 6))
        self.ax = self.figure.add_subplot(111)

        # Embed matplotlib figure
        self.canvas = FigureCanvasTkAgg(self.figure, display_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Navigation toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, display_frame)
        self.toolbar.update()
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X)

    def refresh_file_list(self):
        """Refresh the file list by calling list_files()"""
        try:
            self.status_label.config(text="Loading file list...", foreground="blue")
            self.root.update()
            
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Get files from ParalyneReader
            files = list_files()
            
            # Populate treeview
            for file_info in files:
                if isinstance(file_info, dict):
                    filename = file_info.get('filename', 'Unknown')
                    size = self.format_file_size(file_info.get('size', 0))
                    modified = self.format_date(file_info.get('modified', ''))
                elif isinstance(file_info, (list, tuple)) and len(file_info) >= 3:
                    filename = file_info[0]
                    size = self.format_file_size(file_info[1])
                    modified = self.format_date(file_info[2])
                else:
                    filename = str(file_info)
                    size = "Unknown"
                    modified = "Unknown"
                
                # Insert item and check if already downloaded
                item_id = self.tree.insert("", "end", values=(filename, size, modified))
                
                # Mark already downloaded files with different tag
                if self.is_file_already_downloaded(filename):
                    self.tree.set(item_id, "filename", f"{filename} (Downloaded)")
                    self.tree.item(item_id, tags=("downloaded",))
            
            self.status_label.config(text=f"Loaded {len(files)} files", foreground="green")
            
        except Exception as e:
            error_msg = f"Failed to load file list: {str(e)}"
            self.status_label.config(text=error_msg, foreground="red")
            messagebox.showerror("Error", error_msg)

    def is_file_already_downloaded(self, filename):
        """Check if a file with the given name is already in the downloaded files list"""
        return any(file_info['filename'] == filename for file_info in self.downloaded_files)

    def download_selected_file(self):
        """Download the selected file"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to download.")
            return
        
        item = self.tree.item(selection[0])
        filename = item['values'][0]
        
        # Remove " (Downloaded)" suffix if present for the actual filename
        if filename.endswith(" (Downloaded)"):
            actual_filename = filename.replace(" (Downloaded)", "")
        else:
            actual_filename = filename
        
        # Check if file is already downloaded
        if self.is_file_already_downloaded(actual_filename):
            messagebox.showwarning("File Already Downloaded", 
                                 f"The file '{actual_filename}' has already been downloaded.\n"
                                 f"Remove it from the downloaded files list if you want to download it again.")
            return
        
        try:
            self.status_label.config(text=f"Downloading {actual_filename}...", foreground="blue")
            self.root.update()
            
            # Call download_file function
            downloaded_path = download_file(actual_filename)
            
            # Add to downloaded files list
            file_info = {
                'filename': actual_filename,
                'path': downloaded_path,
                'columns': [],
                'tree_id': None
            }
            
            # Add to downloaded files treeview FIRST
            status = "Loading..." if actual_filename.lower().endswith('.csv') else "Unknown format"
            tree_id = self.downloaded_tree.insert('', tk.END, 
                                             values=(actual_filename, status, 0))
            file_info['tree_id'] = tree_id
            
            # Load columns if it's a CSV file AFTER setting tree_id
            if actual_filename.lower().endswith('.csv'):
                self.load_csv_columns(file_info)
            
            self.downloaded_files.append(file_info)
            self.update_common_columns()
            
            # Refresh the file list to show the downloaded status
            self.refresh_file_list()
            
            self.status_label.config(text=f"Successfully downloaded {actual_filename}", foreground="green")
            messagebox.showinfo("Download Complete", f"File '{actual_filename}' has been downloaded successfully.")
            
        except Exception as e:
            error_msg = f"Failed to download {actual_filename}: {str(e)}"
            self.status_label.config(text=error_msg, foreground="red")
            messagebox.showerror("Download Error", error_msg)

    def load_csv_columns(self, file_info):
        """Load column names from a CSV file"""
        try:
            with open(file_info['path'], 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                # Get the first row as header
                header = next(reader, None)
                
                if header:
                    file_info['columns'] = header
                    # Update status in treeview
                    self.downloaded_tree.item(file_info['tree_id'], 
                                             values=(file_info['filename'], "Ready", len(header)))
                else:
                    file_info['columns'] = []
                    self.downloaded_tree.item(file_info['tree_id'], 
                                             values=(file_info['filename'], "Empty file", 0))
        except Exception as e:
            logging.error(f"Error loading CSV columns for {file_info['filename']}: {str(e)}")
            file_info['columns'] = []
            self.downloaded_tree.item(file_info['tree_id'], 
                                     values=(file_info['filename'], "Error loading columns", 0))

    def update_common_columns(self):
        """Update the list of common columns across downloaded files"""
        if not self.downloaded_files:
            self.columns = []
            self.column_dropdown['values'] = ()
            self.column_var.set("")
            return
        
        # Find files that have columns loaded
        files_with_columns = [f for f in self.downloaded_files if f['columns']]
        
        if not files_with_columns:
            self.columns = []
            self.column_dropdown['values'] = ()
            self.column_var.set("")
            return
        
        # Initialize with columns from the first file with columns
        common_columns = set(files_with_columns[0]['columns'])
        
        # Find intersection of all column sets
        for file_info in files_with_columns[1:]:
            common_columns.intersection_update(file_info['columns'])
        
        self.columns = sorted(list(common_columns))
        
        # Update dropdown values
        self.column_dropdown['values'] = self.columns
        
        if self.columns:
            # Try to set default to pressure column if available
            pressure_columns = [col for col in self.columns if 'pressure' in col.lower()]
            if pressure_columns:
                self.column_var.set(pressure_columns[0])
            else:
                self.column_var.set(self.columns[0])
        else:
            self.column_var.set("")
        
        # Auto-generate graph if files are ready
        self.auto_generate_graph()

    def auto_generate_graph(self):
        """Automatically generate graph when files are downloaded"""
        # Check if any files are ready and we have a column selected
        ready_files = [f for f in self.downloaded_files if f['columns']]
        
        if ready_files and self.column_var.get():
            # Small delay to ensure UI is updated
            self.root.after(100, self.generate_graph)

    def remove_downloaded_file(self):
        """Remove selected downloaded file"""
        selection = self.downloaded_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a downloaded file to remove.")
            return
        
        for item in selection:
            # Find and remove from downloaded_files list
            file_info = next((f for f in self.downloaded_files if f['tree_id'] == item), None)
            if file_info:
                self.downloaded_files.remove(file_info)
                # Remove the file from disk if it exists
                try:
                    if os.path.exists(file_info['path']):
                        os.remove(file_info['path'])
                except Exception as e:
                    logging.warning(f"Could not remove file {file_info['path']}: {str(e)}")
            
            # Remove from treeview
            self.downloaded_tree.delete(item)
        
        # Update common columns
        self.update_common_columns()
        
        # Refresh the file list to update download status
        self.refresh_file_list()
        
        # Clear graph if no files remain
        if not self.downloaded_files:
            self.ax.clear()
            self.canvas.draw()

    def clear_downloaded_files(self):
        """Clear all downloaded files"""
        # Remove all files from disk
        for file_info in self.downloaded_files:
            try:
                if os.path.exists(file_info['path']):
                    os.remove(file_info['path'])
            except Exception as e:
                logging.warning(f"Could not remove file {file_info['path']}: {str(e)}")
        
        # Clear the list and treeview
        self.downloaded_files.clear()
        self.downloaded_tree.delete(*self.downloaded_tree.get_children())
        
        # Update columns and clear graph
        self.update_common_columns()
        
        # Refresh the file list to update download status
        self.refresh_file_list()
        
        self.ax.clear()
        self.canvas.draw()

    def apply_smoothing(self, values, method, window_size):
        """Apply smoothing to data values with adaptive window sizing"""
        if method == "none" or len(values) < 3:
            return values
        
        values_array = np.array(values)
        
        # For moving average, use adaptive window size
        if method == "moving_average":
            # If data has less than 2500 points, use the full length
            # Otherwise use the specified window size
            if len(values) < 2500:
                adaptive_window = len(values)
            else:
                adaptive_window = min(window_size, len(values))
        else:
            # For other methods, use the original logic
            adaptive_window = min(window_size, len(values))
        
        try:
            if method == "moving_average":
                # Simple moving average
                window = adaptive_window
                if window % 2 == 0:
                    window += 1  # Ensure odd window size
                
                # Don't smooth if window is too large relative to data
                if window >= len(values):
                    return values
                
                # Pad the array to handle edges
                pad_width = window // 2
                padded = np.pad(values_array, pad_width, mode='edge')
                
                # Apply convolution
                kernel = np.ones(window) / window
                smoothed = np.convolve(padded, kernel, mode='valid')
                return smoothed.tolist()
                
            elif method == "savgol":
                # Savitzky-Golay filter
                window = adaptive_window
                if window % 2 == 0:
                    window += 1  # Ensure odd window size
                if window < 3:
                    window = 3
                
                poly_order = min(3, window - 1)
                smoothed = savgol_filter(values_array, window, poly_order)
                return smoothed.tolist()
                
            elif method == "gaussian":
                # Gaussian filter
                sigma = adaptive_window / 6.0  # Convert window size to sigma
                smoothed = gaussian_filter1d(values_array, sigma)
                return smoothed.tolist()
                
            elif method == "median":
                # Median filter
                window = adaptive_window
                if window % 2 == 0:
                    window += 1  # Ensure odd window size
                
                smoothed = medfilt(values_array, kernel_size=window)
                return smoothed.tolist()
                
        except Exception as e:
            logging.warning(f"Error applying smoothing method {method}: {str(e)}")
            return values
        
        return values

    def apply_normalization(self, values, method):
        """Apply normalization to data values"""
        if method == "none" or len(values) == 0:
            return values
        
        values_array = np.array(values)
        
        try:
            if method == "minmax":
                # Min-max normalization (0 to 1)
                min_val = np.min(values_array)
                max_val = np.max(values_array)
                if max_val != min_val:
                    normalized = (values_array - min_val) / (max_val - min_val)
                else:
                    normalized = np.zeros_like(values_array)
                return normalized.tolist()
                
            elif method == "zscore":
                # Z-score normalization (mean=0, std=1)
                mean_val = np.mean(values_array)
                std_val = np.std(values_array)
                if std_val != 0:
                    normalized = (values_array - mean_val) / std_val
                else:
                    normalized = np.zeros_like(values_array)
                return normalized.tolist()
                
            elif method == "robust":
                # Robust normalization using median and IQR
                median_val = np.median(values_array)
                q75, q25 = np.percentile(values_array, [75, 25])
                iqr = q75 - q25
                if iqr != 0:
                    normalized = (values_array - median_val) / iqr
                else:
                    normalized = np.zeros_like(values_array)
                return normalized.tolist()
                
        except Exception as e:
            logging.warning(f"Error applying normalization method {method}: {str(e)}")
            return values
        
        return values

    def process_data(self, values):
        """Apply smoothing and normalization to data"""
        # First apply smoothing
        smoothing_method = self.smoothing_var.get()
        window_size = self.window_size_var.get()
        processed_values = self.apply_smoothing(values, smoothing_method, window_size)
        
        # Then apply normalization
        normalize_method = self.normalize_var.get()
        processed_values = self.apply_normalization(processed_values, normalize_method)
        
        return processed_values

    def on_normalization_change(self):
        """Called when the normalization checkbox is toggled"""
        # Regenerate the graph if we have data
        if self.current_file_data:
            self.generate_graph()

    def on_processing_change(self, event=None):
        """Called when smoothing or normalization settings change"""
        # Only regenerate if normalization is enabled and we have data
        if self.show_normalized_var.get() and self.current_file_data:
            self.generate_graph()    
    def generate_graph(self):
        """Generate and display graphs for selected files (optimized with threading)"""
        # Check if any files are ready
        ready_files = [f for f in self.downloaded_files if f['columns']]
        
        if not ready_files:
            messagebox.showerror("Error", "No files ready for graphing")
            return
        
        column = self.column_var.get()
        if not column:
            messagebox.showerror("Error", "No column selected")
            return
            
        log_scale = self.log_scale_var.get()
        
        # Clear previous graph
        self.ax.clear()
        self.canvas.draw()
        
        # Show progress for large files
        total_size = sum(os.path.getsize(f['path']) for f in ready_files if os.path.exists(f['path']))
        if total_size > 5 * 1024 * 1024:  # 5MB threshold
            self.show_progress("Loading files...")
        
        self.status_label.config(text=f"Generating graphs for {column}...", foreground="blue")
        self.root.update()
        
        # Store current settings
        self.current_column = column
        self.current_log_scale = log_scale
        
        # Use threading for large files
        if total_size > 5 * 1024 * 1024:
            self.generate_graph_threaded(ready_files, column, log_scale)
        else:
            self.generate_graph_sync(ready_files, column, log_scale)

    def generate_graph_sync(self, ready_files, column, log_scale):
        """Generate graph synchronously for smaller files"""
        file_data = []
        
        for i, file_info in enumerate(ready_files):
            try:
                # Load raw data (without time offset)
                raw_times, values = self.load_file_data(file_info, column)
                if raw_times and values:
                    # Store raw times and values so we can re-apply offsets later
                    file_data.append((file_info, raw_times, values))
            except Exception as e:
                logging.error(f"Error processing file {file_info['filename']}: {str(e)}")
                continue
        
        self.finish_graph_generation(file_data, column, log_scale)

    def generate_graph_threaded(self, ready_files, column, log_scale):
        """Generate graph using threading for large files"""
        def load_files_worker():
            file_data = []
            total_files = len(ready_files)
            
            for i, file_info in enumerate(ready_files):
                try:
                    self.root.after(0, lambda i=i, total=total_files: self.update_progress(
                        (i / total) * 100, f"Loading file {i+1}/{total}: {file_info['filename']}"
                    ))
                      # Load raw data (without time offset)
                    raw_times, values = self.load_file_data(file_info, column)
                    if raw_times and values:
                        # Store raw times and values so we can re-apply offsets later
                        file_data.append((file_info, raw_times, values))
                except Exception as e:
                    logging.error(f"Error processing file {file_info['filename']}: {str(e)}")
                    continue
            
            # Update UI on main thread
            self.root.after(0, lambda: self.finish_graph_generation(file_data, column, log_scale))
        
        # Run in background thread
        thread = threading.Thread(target=load_files_worker)
        thread.daemon = True
        thread.start()

    def finish_graph_generation(self, file_data, column, log_scale):
        """Complete graph generation on main thread"""
        self.hide_progress()
        
        if file_data:
            self.current_file_data = file_data
            self.update_plot(file_data, column, log_scale)
            
            # Update file selector dropdown (only if it exists)
            if hasattr(self, 'file_selector') and self.file_selector is not None:
                file_names = [info[0]['filename'] for info in file_data]
                self.file_selector['values'] = file_names
                if file_names:
                    self.file_selector_var.set(file_names[0])
                    self.selected_file_index = 0
        else:
            messagebox.showerror("Error", "No valid data found to plot")

    def load_file_data(self, file_info, column):
        """Load data from a file for the specified column (optimized version - NO offset applied here)"""
        cache_key = self.get_cache_key(file_info, column)
        
        # Check cache first (cache stores data WITHOUT time offset)
        if cache_key in self.raw_data_cache:
            return self.raw_data_cache[cache_key]
        
        times = []
        values = []
        
        try:
            file_size = os.path.getsize(file_info['path'])
            is_large_file = file_size > 1024 * 1024  # 1MB threshold
            
            with open(file_info['path'], 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader, None)
                
                if not header or column not in header:
                    return times, values
                
                column_index = header.index(column)
                # Find timestamp column (assume first column or look for time-related names)
                time_column_index = 0
                time_columns = ['timestamp', 'time', 'datetime', 'date']
                for i, col in enumerate(header):
                    if any(time_col in col.lower() for time_col in time_columns):
                        time_column_index = i
                        break
                
                if is_large_file:
                    # Process large files in chunks
                    chunk = []
                    total_rows = 0
                    processed_rows = 0
                    
                    # Count total rows for progress
                    csvfile.seek(0)
                    next(csv.reader(csvfile))  # Skip header
                    total_rows = sum(1 for _ in csv.reader(csvfile))
                    csvfile.seek(0)
                    next(csv.reader(csvfile))  # Skip header again
                    
                    reader = csv.reader(csvfile)
                    
                    for row in reader:
                        chunk.append(row)
                        processed_rows += 1
                        
                        if len(chunk) >= self.chunk_size:
                            chunk_times, chunk_values = self.process_chunk(
                                chunk, header, column, time_column_index, column_index, file_info, apply_offset=False
                            )
                            times.extend(chunk_times)
                            values.extend(chunk_values)
                            chunk = []
                            
                            # Update progress
                            progress = (processed_rows / total_rows) * 100
                            self.root.after(0, lambda p=progress: self.update_progress(
                                p, f"Processing {file_info['filename']}: {processed_rows}/{total_rows} rows"
                            ))
                        
                        # Allow GUI to update
                        if processed_rows % 1000 == 0:
                            self.root.update()
                    
                    # Process remaining rows
                    if chunk:
                        chunk_times, chunk_values = self.process_chunk(
                            chunk, header, column, time_column_index, column_index, file_info, apply_offset=False
                        )
                        times.extend(chunk_times)
                        values.extend(chunk_values)
                else:
                    # Process smaller files normally
                    for row in reader:
                        if len(row) > max(column_index, time_column_index):                        
                            try:
                                # Parse time from the determined time column
                                if len(row[time_column_index]) > 0:
                                    time_val = self.parse_time(row[time_column_index])
                                    value = float(row[column_index])
                                    
                                    # Convert pico value to machine value
                                    converted_value = self.convert_pico_to_machine_value(value)
                                    
                                    # DO NOT apply time offset here - store raw times
                                    times.append(time_val)
                                    values.append(converted_value)
                            except (ValueError, TypeError):
                                continue
            
            # Cache the loaded data (WITHOUT time offset applied)
            self.raw_data_cache[cache_key] = (times, values)
            
        except Exception as e:
            logging.error(f"Error loading file {file_info['filename']}: {str(e)}")
        
        return times, values
    def convert_pico_to_machine_value(self, pico_value):
        """Convert pico reading (a) to machine value (b) using: a = 174.96 * b + 1202.88"""
        # Rearranging: b = (a - 1202.88) / 174.96
        return (pico_value - 1202.88) / 174.96

    def parse_time(self, time_str):
        """Parse time string into datetime or float"""
        # Try common datetime formats first
        time_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%H:%M:%S"
        ]
        
        for fmt in time_formats:
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        
        # Try parsing as float (seconds)
        try:
            return float(time_str)
        except ValueError:
            # If all else fails, return the string
            return time_str

    def update_plot(self, file_data, column, log_scale):
        """Update the plot with data from multiple files"""
        if not file_data:
            self.status_label.config(text="No data to plot", foreground="red")
            return
        
        try:
            # Clear previous graph
            self.ax.clear()
              # Define line styles and markers for additional distinctiveness
            line_styles = ['-', '--', '-.', ':']
            markers = ['o', 's', '^', 'D', 'v', '*', 'p', 'h', '+', 'x']
            
            for i, (file_info, raw_times, values) in enumerate(file_data):
                if not raw_times or not values:
                    continue
                
                # Apply time offset to raw times
                times = self.apply_time_offset_to_data(raw_times, file_info)
                
                # Process values if normalization is enabled
                plot_values = values
                if self.show_normalized_var.get():
                    plot_values = self.process_data(values)
                
                # Downsample data for better performance
                plot_times, plot_values = self.downsample_data(times, plot_values)
                
                color = self.color_cycle[i % len(self.color_cycle)]
                style = line_styles[i % len(line_styles)]
                marker = markers[i % len(markers)]
                
                # Create label with processing info
                label = os.path.basename(file_info['filename'])
                if len(values) != len(plot_values):
                    label += f" (sampled: {len(plot_values)}/{len(values)})"
                if self.show_normalized_var.get():
                    processing_info = []
                    if self.smoothing_var.get() != "none":
                        processing_info.append(f"S:{self.smoothing_var.get()}")
                    if self.normalize_var.get() != "none":
                        processing_info.append(f"N:{self.normalize_var.get()}")
                    if processing_info:
                        label += f" [{', '.join(processing_info)}]"
                
                # Plot with style variations - use markers only for small datasets
                if len(plot_values) > 500:  # Don't use markers for large datasets
                    self.ax.plot(plot_times, plot_values, color=color, linestyle=style, 
                               label=label, linewidth=1.5)
                else:
                    self.ax.plot(plot_times, plot_values, color=color, linestyle=style, 
                               marker=marker, markersize=3, label=label, 
                               linewidth=1.5, markevery=max(1, len(plot_values)//50))
            
            # Set labels and title with better defaults
            self.ax.set_xlabel("Timestamp")
              # Set y-axis label based on column name and processing
            y_label = column
            if self.show_normalized_var.get():
                # Add processing information to y-label
                processing_parts = []
                if self.smoothing_var.get() != "none":
                    processing_parts.append(f"Smoothed ({self.smoothing_var.get()})")
                if self.normalize_var.get() != "none":
                    norm_labels = {
                        "minmax": "Min-Max Normalized",
                        "zscore": "Z-Score Normalized", 
                        "robust": "Robust Normalized"
                    }
                    processing_parts.append(norm_labels.get(self.normalize_var.get(), "Normalized"))
                
                if processing_parts:
                    y_label = f"{column} ({', '.join(processing_parts)}) - Machine Values"
            elif 'pressure' in column.lower():
                # Try to determine pressure units
                if any(unit in column.lower() for unit in ['torr', 'mbar', 'pa', 'psi']):
                    y_label = f"{column} - Machine Values"
                else:
                    y_label = f"{column} (Pressure) - Machine Values"
            else:
                y_label = f"{column} - Machine Values"
            
            self.ax.set_ylabel(y_label)
            
            # Set title with processing information
            title = f"{column} vs Time"
            if self.show_normalized_var.get():
                title += " (Processed)"
            self.ax.set_title(title)
            self.ax.legend()
            self.ax.grid(True, alpha=0.3)
            
            # Add horizontal threshold line at y=15
            self.ax.axhline(y=15, color='red', linestyle='--', linewidth=2, alpha=0.8, label='Threshold (y=15)')
            
            # Set log scale if enabled
            if log_scale:
                self.ax.set_yscale("log")
            
            # Auto-zoom if enabled
            if self.auto_zoom_var.get():
                self.ax.relim()
                self.ax.autoscale_view()
            
            # Format x-axis for datetime if applicable
            if file_data and isinstance(file_data[0][1][0], datetime):
                self.figure.autofmt_xdate()
            
            self.canvas.draw()
            self.status_label.config(text=f"Graph generated successfully for {len(file_data)} files", foreground="green")
            
        except Exception as e:
            error_msg = f"Failed to update plot: {str(e)}"
            self.status_label.config(text=error_msg, foreground="red")
            messagebox.showerror("Plot Error", error_msg)

    def on_file_selected(self, event):
        """Event handler for file selection change"""
        try:
            selected_file = self.file_selector_var.get()
            if not selected_file:
                return
            
            # Find the corresponding file info in current_file_data
            for i, (file_info, _, _) in enumerate(self.current_file_data):
                if file_info['filename'] == selected_file:
                    self.selected_file_index = i
                    break
            
            # Set the slider to the current offset for this file
            offset = self.file_offsets.get(selected_file, 0.0)
            self.time_offset_var.set(offset)
            
        except Exception as e:
            logging.error(f"Error in file selection: {str(e)}")

    def update_time_offset(self, value):
        """Update the time offset for the selected file (optimized)"""
        try:
            if not self.current_file_data or self.selected_file_index >= len(self.current_file_data):
                return
            
            offset_value = float(value)
            file_info = self.current_file_data[self.selected_file_index][0]
            old_offset = self.file_offsets.get(file_info['filename'], 0.0)
            
            # Only update if offset actually changed
            if abs(offset_value - old_offset) < 0.01:  # Avoid micro-updates
                return
                
            self.file_offsets[file_info['filename']] = offset_value
            
            # Update the plot immediately for better responsiveness
            self.update_plot_with_offsets()
            
        except Exception as e:
            logging.error(f"Error updating time offset: {str(e)}")

    def _delayed_graph_update(self):
        """Delayed graph update for smoother time offset changes"""
        try:
            self._updating_offset = False
            if self.current_file_data and self.current_column:
                self.generate_graph()
        except Exception as e:
            logging.error(f"Error in delayed graph update: {str(e)}")
            self._updating_offset = False

    def adjust_time_offset(self, increment):
        """Adjust the time offset by the given increment"""
        current_value = self.time_offset_var.get()
        new_value = current_value + increment
        
        # Ensure value is within slider range
        min_val = self.time_offset_slider.cget('from')
        max_val = self.time_offset_slider.cget('to')
        new_value = max(min_val, min(max_val, new_value))
        
        self.time_offset_var.set(new_value)

    def on_offset_entry(self, event):
        """Handle manual entry of time offset value"""
        try:
            value = float(self.time_offset_entry.get())
            min_val = self.time_offset_slider.cget('from')
            max_val = self.time_offset_slider.cget('to')
            value = max(min_val, min(max_val, value))
            self.time_offset_var.set(value)
        except ValueError:
            # Reset to current slider value if invalid input
            self.time_offset_entry.delete(0, tk.END)
            self.time_offset_entry.insert(0, str(self.time_offset_var.get()))

    def reset_time_offset(self):
        """Reset the time offset for the selected file"""
        if not self.current_file_data or self.selected_file_index >= len(self.current_file_data):
            return
        
        file_info = self.current_file_data[self.selected_file_index][0]
        self.file_offsets[file_info['filename']] = 0.0
        self.time_offset_var.set(0.0)
        self.update_plot_with_offsets()

    def reset_all_offsets(self):
        """Reset time offsets for all files"""
        self.file_offsets.clear()
        self.time_offset_var.set(0.0)
        if self.current_file_data:
            self.update_plot_with_offsets()

    def format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if isinstance(size_bytes, str):
            return size_bytes
        
        try:
            size_bytes = int(size_bytes)
        except (ValueError, TypeError):
            return "Unknown"
        
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"

    def format_date(self, date_input):
        """Format date in readable format"""
        if isinstance(date_input, str):
            return date_input
        
        try:
            if isinstance(date_input, datetime):
                return date_input.strftime("%Y-%m-%d %H:%M")
            elif isinstance(date_input, (int, float)):
                # Assume it's a timestamp
                dt = datetime.fromtimestamp(date_input)
                return dt.strftime("%Y-%m-%d %H:%M")
            else:
                return str(date_input)
        except Exception:
            return "Unknown"
    
    def show_progress(self, message="Loading..."):
        """Show progress bar with message"""
        self.progress_label.config(text=message)
        self.progress_var.set(0)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)
        self.progress_label.pack(pady=2)
        self.progress_frame.pack(fill=tk.X, pady=5)
        self.root.update()

    def update_progress(self, value, message=""):
        """Update progress bar value and message"""
        self.progress_var.set(value)
        if message:
            self.progress_label.config(text=message)
        self.root.update()

    def hide_progress(self):
        """Hide progress bar"""
        self.progress_frame.pack_forget()
        self.root.update()

    def get_cache_key(self, file_info, column):
        """Generate cache key for file data"""
        return f"{file_info['filename']}_{column}_{file_info.get('size', 0)}"

    def downsample_data(self, times, values, max_points=None):
        """Downsample data for efficient plotting"""
        if max_points is None:
            max_points = self.max_plot_points
            
        if len(values) <= max_points:
            return times, values
        
        # Use every nth point for downsampling
        step = max(1, len(values) // max_points)
        return times[::step], values[::step]

    def process_chunk(self, chunk, header, column, time_column_index, column_index, file_info, apply_offset=True):
        """Process a chunk of CSV rows"""
        times = []
        values = []
        
        for row in chunk:
            if len(row) > max(column_index, time_column_index):
                try:
                    # Parse time from the determined time column
                    if len(row[time_column_index]) > 0:
                        time_val = self.parse_time(row[time_column_index])
                        value = float(row[column_index])
                        
                        # Convert pico value to machine value
                        converted_value = self.convert_pico_to_machine_value(value)
                        
                        # Apply time offset only if requested
                        if apply_offset:
                            offset = self.file_offsets.get(file_info['filename'], 0.0)
                            if isinstance(time_val, datetime):
                                time_val = time_val + timedelta(seconds=offset)
                            else:
                                time_val += offset
                        
                        times.append(time_val)
                        values.append(converted_value)
                except (ValueError, TypeError):
                    continue
        
        return times, values

    def clear_caches(self):
        """Clear all cached data"""
        self.raw_data_cache.clear()
        self.processed_data_cache.clear()
        
    def clear_cache_for_file(self, filename):
        """Clear cache for a specific file"""
        keys_to_remove = [key for key in self.raw_data_cache.keys() if key.startswith(filename)]
        for key in keys_to_remove:
            del self.raw_data_cache[key]
        
        keys_to_remove = [key for key in self.processed_data_cache.keys() if key.startswith(filename)]
        for key in keys_to_remove:
            del self.processed_data_cache[key]

    def apply_time_offset_to_data(self, times, file_info):
        """Apply time offset to time data without modifying cached data"""
        offset = self.file_offsets.get(file_info['filename'], 0.0)
        if offset == 0.0:
            return times
        
        offset_times = []
        for time_val in times:
            if isinstance(time_val, datetime):
                offset_times.append(time_val + timedelta(seconds=offset))
            else:
                offset_times.append(time_val + offset)
        
        return offset_times

    def update_plot_with_offsets(self):
        """Update the existing plot with new time offsets without regenerating everything"""
        try:
            if not self.current_file_data or not hasattr(self, 'ax'):
                return
            
            # Clear the plot
            self.ax.clear()
            
            # Track if we have datetime objects for formatting
            has_datetime = False
            
            # Re-plot all files with updated offsets
            for i, (file_info, raw_times, values) in enumerate(self.current_file_data):
                try:
                    # Apply current offset to the raw times
                    times = self.apply_time_offset_to_data(raw_times, file_info)
                    
                    # Check if we have datetime objects
                    if times and isinstance(times[0], datetime):
                        has_datetime = True
                    
                    # Apply any processing (smoothing, normalization)
                    processed_times, processed_values = self.apply_processing(times, values, file_info)
                    
                    # Plot the data
                    color = self.color_cycle[i % len(self.color_cycle)]
                    label = self.create_label(file_info)
                    
                    self.ax.plot(processed_times, processed_values, 
                               color=color, label=label, linewidth=1.5)
                    
                except Exception as e:
                    logging.error(f"Error plotting file {file_info['filename']}: {str(e)}")
                    continue
            
            # Update plot formatting
            self.format_plot()
            
            # Format x-axis for datetime if applicable
            if has_datetime:
                self.figure.autofmt_xdate()
            
            # Refresh the canvas
            self.canvas.draw()
            
        except Exception as e:
            logging.error(f"Error updating plot with offsets: {str(e)}")

    def apply_processing(self, times, values, file_info):
        """Apply smoothing and normalization to data"""
        try:
            processed_values = values.copy()
            
            # Apply smoothing if enabled
            smoothing_method = self.smoothing_var.get()
            if smoothing_method != "none":
                window_size = self.window_size_var.get()
                processed_values = self.apply_smoothing(processed_values, smoothing_method, window_size)
            
            # Apply normalization if enabled
            if self.show_normalized_var.get():
                normalize_method = self.normalize_var.get()
                processed_values = self.apply_normalization(processed_values, normalize_method)
            
            return times, processed_values
            
        except Exception as e:
            logging.error(f"Error applying processing: {str(e)}")
            return times, values

    def format_plot(self):
        """Format the plot with labels, legend, etc."""
        try:
            # Set labels
            self.ax.set_xlabel('Time')
            
            # Set y-label based on column type
            column = self.current_column or 'Value'
            if hasattr(self, 'show_normalized_var') and self.show_normalized_var.get():
                if "pressure" in column.lower() or "pico" in column.lower():
                    y_label = f"{column} (Pressure) - Normalized Machine Values"
                else:
                    y_label = f"{column} - Normalized Values"
            else:
                if "pressure" in column.lower() or "pico" in column.lower():
                    y_label = f"{column} (Pressure) - Machine Values"
                else:
                    y_label = f"{column}"
            
            self.ax.set_ylabel(y_label)
            
            # Set log scale if enabled
            if hasattr(self, 'current_log_scale') and self.current_log_scale:
                self.ax.set_yscale('log')
            else:
                self.ax.set_yscale('linear')
            
            # Set title with processing information
            title = f"{column} vs Time"
            if hasattr(self, 'show_normalized_var') and self.show_normalized_var.get():
                title += " (Processed)"
            self.ax.set_title(title)
            
            # Add legend
            self.ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            
            # Add grid
            self.ax.grid(True, alpha=0.3)
            
            # Add horizontal threshold line at y=15
            self.ax.axhline(y=15, color='red', linestyle='--', linewidth=2, alpha=0.8, label='Threshold (y=15)')
            
            # Auto-zoom if enabled
            if hasattr(self, 'auto_zoom_var') and self.auto_zoom_var.get():
                self.ax.relim()
                self.ax.autoscale_view()
            
            # Tight layout
            self.figure.tight_layout()
            
        except Exception as e:
            logging.error(f"Error formatting plot: {str(e)}")

    def create_label(self, file_info):
        """Create a label for the plot line"""
        try:
            filename = file_info['filename']
            # Truncate long filenames
            if len(filename) > 30:
                filename = filename[:27] + "..."
            return filename
        except:
            return "Unknown File"

if __name__ == "__main__":
    root = tk.Tk()
    app = ParalyneReaderApp(root)
    root.mainloop()