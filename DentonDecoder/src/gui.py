import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import os
import threading
from pathlib import Path
import sys
import csv
import random
import colorsys

# Add the parent directory to the path to find modules correctly
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import from the Denton modules - use relative or absolute imports based on your structure
from src.DentonDecoder import convertFile
from src.DentonGrapher import create_graph

class DentonGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Denton Toolkit")
        self.geometry("1000x700")
        self.minsize(800, 600)
        
        # Store file information as a list of dictionaries with original path, csv path, and columns
        self.files = []
        self.columns = []
        
        # Generate distinct colors for plots
        self.color_cycle = self.generate_distinct_colors(20)  # Generate 20 distinct colors
        
        # Track the selected file for time offset (index in file_data)
        self.selected_file_index = 0
        
        # Store per-file time offsets
        self.file_offsets = {}  # Map from file path to time offset
        
        # Store the current plot data for replotting when time offset changes
        self.current_file_data = []
        self.current_column = ""
        self.current_log_scale = False
        
        self.create_widgets()
        
    def generate_distinct_colors(self, n):
        """Generate n visually distinct colors with emphasis on primary colors"""
        # Start with high-contrast primary and secondary colors
        primary_colors = [
            '#FF0000',  # Red
            '#0000FF',  # Blue
            '#00CC00',  # Green 
            '#FF00FF',  # Magenta
            '#FFCC00',  # Yellow
            '#00CCFF',  # Cyan
            '#FF6600',  # Orange
            '#9900CC',  # Purple
            '#006600',  # Dark Green
            '#CC0000',  # Dark Red
            '#000099',  # Dark Blue
            '#FF9999',  # Light Red
            '#9999FF',  # Light Blue
            '#99FF99',  # Light Green
            '#FF99FF',  # Light Pink
            '#FFFF99',  # Light Yellow
            '#99FFFF'   # Light Cyan
        ]
        
        # If we need more colors than in our preset list, add generated ones
        if n <= len(primary_colors):
            return primary_colors[:n]
        
        # Add more generated colors using HSV space for the remaining colors
        colors = primary_colors.copy()
        remaining = n - len(colors)
        
        for i in range(remaining):
            # Use HSV color space to get evenly spaced hues
            h = i / remaining
            s = 0.85 if i % 2 else 0.7  # Alternate between high and medium saturation
            v = 0.9 if i % 4 < 2 else 0.7  # Alternate between high and medium value
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            colors.append(f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}')
        
        return colors
        
    def create_widgets(self):
        # Create main frame
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create file selection frame at the top
        file_frame = ttk.LabelFrame(main_frame, text="File Selection")
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create file list with scrollbar
        file_list_frame = ttk.Frame(file_frame)
        file_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        file_list_scrollbar = ttk.Scrollbar(file_list_frame)
        file_list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create a treeview for the file list
        columns = ("file", "type", "status")
        self.file_list = ttk.Treeview(file_list_frame, columns=columns, show="headings", 
                                      selectmode="extended", height=5)
        
        # Configure column headings
        self.file_list.heading("file", text="File Name")
        self.file_list.heading("type", text="File Type")
        self.file_list.heading("status", text="Status")
        
        # Configure column widths
        self.file_list.column("file", width=625, anchor="w")
        self.file_list.column("type", width=10, anchor="center")
        self.file_list.column("status", width=15, anchor="center")
        
        self.file_list.pack(fill=tk.BOTH, expand=True)
        self.file_list.config(yscrollcommand=file_list_scrollbar.set)
        file_list_scrollbar.config(command=self.file_list.yview)
        
        # File control buttons
        file_button_frame = ttk.Frame(file_frame)
        file_button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(file_button_frame, text="Add Files", command=self.add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_button_frame, text="Remove Selected", command=self.remove_selected_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_button_frame, text="Clear All Files", command=self.clear_all_files).pack(side=tk.LEFT, padx=5)
        
        # Create a horizontal paned window for side-by-side layout
        h_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        h_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create graph options frame (LEFT SIDE)
        options_frame = ttk.LabelFrame(h_paned, text="Graph Options")
        h_paned.add(options_frame, weight=1)  # weight=1 gives proportional space
        
        # Pad the options to make them look better
        options_inner_frame = ttk.Frame(options_frame)
        options_inner_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Column selection
        ttk.Label(options_inner_frame, text="Select column to graph:").pack(anchor="w", pady=(0, 5))
        self.column_var = tk.StringVar(value="Chamber Pressure (Torr)")
        self.column_dropdown = ttk.Combobox(options_inner_frame, textvariable=self.column_var, 
                                           width=30, state="readonly")
        self.column_dropdown.pack(fill=tk.X, pady=(0, 10))
        
        # Log scale option
        self.log_scale_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_inner_frame, text="Use logarithmic scale", 
                       variable=self.log_scale_var).pack(anchor="w", pady=(0, 10))
        
        # Auto-zoom toggle for the x-axis
        self.auto_zoom_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_inner_frame, text="Auto-zoom to active data", 
                       variable=self.auto_zoom_var).pack(anchor="w", pady=(0, 10))
        
        # Graph button
        ttk.Button(options_inner_frame, text="Generate Graph", 
                  command=self.generate_graph).pack(fill=tk.X, pady=(0, 20))
        
        # Create graph frame (RIGHT SIDE)
        graph_frame = ttk.LabelFrame(h_paned, text="Graph")
        h_paned.add(graph_frame, weight=3)  # weight=3 gives it more space than options
        
        # Add time offset slider frame ABOVE the chart
        time_offset_frame = ttk.LabelFrame(graph_frame, text="Time Alignment")
        time_offset_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Add file selector for time offset
        file_select_frame = ttk.Frame(time_offset_frame)
        file_select_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(file_select_frame, text="Select file to adjust:").pack(side=tk.LEFT, padx=5)
        self.file_selector_var = tk.StringVar()
        self.file_selector = ttk.Combobox(file_select_frame, textvariable=self.file_selector_var, 
                                         width=40, state="readonly")
        self.file_selector.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.file_selector.bind("<<ComboboxSelected>>", self.on_file_selected)
        
        # Slider frame
        slider_frame = ttk.Frame(time_offset_frame)
        slider_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(slider_frame, text="Time Offset (seconds):").pack(side=tk.LEFT, padx=5)
        
        # Time offset slider with a range of -300 to +300 seconds
        self.time_offset_var = tk.DoubleVar(value=0.0)
        self.time_offset_slider = ttk.Scale(
            slider_frame, 
            from_=-300.0, 
            to=300.0, 
            variable=self.time_offset_var, 
            orient=tk.HORIZONTAL,
            command=self.update_time_offset
        )
        self.time_offset_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Display the cur+rent offset value
        self.time_offset_label = ttk.Label(slider_frame, text="0.0")
        self.time_offset_label.pack(side=tk.LEFT, padx=5)
        
        # Reset button for time offset
        ttk.Button(slider_frame, text="Reset Offset", 
                  command=self.reset_time_offset).pack(side=tk.LEFT, padx=5)
        
        # Reset all files button
        ttk.Button(slider_frame, text="Reset All Files", 
                  command=self.reset_all_offsets).pack(side=tk.LEFT, padx=5)
        
        # Create matplotlib figure
        self.figure = plt.Figure(figsize=(8, 6))
        self.ax = self.figure.add_subplot(111)
        
        # Embed matplotlib figure in tkinter
        self.canvas = FigureCanvasTkAgg(self.figure, graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Add navigation toolbar for interactivity
        self.toolbar = NavigationToolbar2Tk(self.canvas, graph_frame)
        self.toolbar.update()
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def add_files(self):
        """Opens a file dialog to select multiple .dat or .csv files"""
        filetypes = [("Denton files", "*.dat"), ("CSV files", "*.csv"), ("All files", "*.*")]
        filenames = filedialog.askopenfilenames(filetypes=filetypes)
        
        if not filenames:
            return
            
        # Process each selected file
        for filename in filenames:
            # Check if file is already in the list
            if any(file_info['original_path'] == filename for file_info in self.files):
                messagebox.showinfo("Info", f"File already added: {os.path.basename(filename)}")
                continue
                
            file_info = {
                'original_path': filename,
                'csv_path': None,
                'columns': [],
                'tree_id': None
            }
            
            # Insert into the file list
            file_base = os.path.basename(filename)
            file_ext = os.path.splitext(filename)[1].lower()
            
            tree_id = self.file_list.insert('', tk.END, values=(file_base, file_ext, "Pending"))
            file_info['tree_id'] = tree_id
            
            self.files.append(file_info)
            
            # Process file based on its extension
            if file_ext == '.dat':
                # Convert .dat to .csv in a separate thread
                self.process_dat_file(file_info)
            elif file_ext == '.csv':
                file_info['csv_path'] = filename
                self.load_csv_columns(file_info)
                self.file_list.item(tree_id, values=(file_base, file_ext, "Ready"))
    
    def remove_selected_files(self):
        """Remove selected files from the list"""
        selected_items = self.file_list.selection()
        if not selected_items:
            return
            
        for item in selected_items:
            # Find and remove file from self.files
            file_info = next((f for f in self.files if f['tree_id'] == item), None)
            if file_info:
                self.files.remove(file_info)
            
            # Remove from treeview
            self.file_list.delete(item)
            
        # Update column dropdown in case removed files affected available columns
        self.update_common_columns()
    
    def clear_all_files(self):
        """Clear all files from the list"""
        self.file_list.delete(*self.file_list.get_children())
        self.files = []
        self.columns = []
        self.column_dropdown['values'] = []
    
    def process_dat_file(self, file_info):
        """Process a .dat file by converting it to CSV"""
        filename = file_info['original_path']
        tree_id = file_info['tree_id']
        
        self.file_list.item(tree_id, values=(os.path.basename(filename), 
                                            os.path.splitext(filename)[1], 
                                            "Converting..."))
        
        def conversion_thread():
            try:
                csv_file = convertFile(filename)
                file_info['csv_path'] = csv_file
                
                # Update UI from main thread
                self.after(10, lambda: self.conversion_complete(file_info))
            except Exception as e:
                self.after(10, lambda: self.file_list.item(tree_id, 
                                                         values=(os.path.basename(filename), 
                                                               os.path.splitext(filename)[1], 
                                                               f"Error: {str(e)[:20]}...")))
        
        threading.Thread(target=conversion_thread).start()
    
    def conversion_complete(self, file_info):
        """Called when DAT to CSV conversion is complete"""
        tree_id = file_info['tree_id']
        filename = file_info['original_path']
        
        self.file_list.item(tree_id, values=(os.path.basename(filename), 
                                            os.path.splitext(filename)[1], 
                                            "Converted"))
                                            
        # Load columns from the converted CSV
        self.load_csv_columns(file_info)
    
    def load_csv_columns(self, file_info):
        """Load column names from a CSV file"""
        try:
            with open(file_info['csv_path'], 'r', errors='replace') as f:
                reader = csv.reader(f)
                file_info['columns'] = next(reader)  # Get header row
                
                # Count rows to calculate duration
                row_count = sum(1 for _ in reader)
                # Calculate duration in seconds (0.85 times row count)
                file_info['duration'] = row_count / 0.85
                
            # Update common columns across all files
            self.update_common_columns()
            
            # Update status
            self.file_list.item(file_info['tree_id'], 
                              values=(os.path.basename(file_info['original_path']), 
                                    os.path.splitext(file_info['original_path'])[1], 
                                    "Ready"))
                                    
        except Exception as e:
            self.file_list.item(file_info['tree_id'], 
                              values=(os.path.basename(file_info['original_path']), 
                                    os.path.splitext(file_info['original_path'])[1], 
                                    f"Error: {str(e)[:20]}..."))
    
    def update_common_columns(self):
        """Update the dropdown with columns that exist in all files"""
        if not self.files:
            self.columns = []
            self.column_dropdown['values'] = []
            return
            
        # Get common columns across all ready files
        ready_files = [f for f in self.files if f['csv_path'] and f['columns']]
        
        if not ready_files:
            self.columns = []
            self.column_dropdown['values'] = []
            return
            
        # Start with all columns from the first file
        common_columns = set(ready_files[0]['columns'])
        
        # Find intersection with columns from other files
        for file_info in ready_files[1:]:
            common_columns &= set(file_info['columns'])
        
        self.columns = sorted(list(common_columns))
        self.column_dropdown['values'] = self.columns
        
        # Set default column if available
        default_column = "Chamber Pressure (Torr)"
        if default_column in self.columns:
            self.column_var.set(default_column)
        elif self.columns:
            self.column_var.set(self.columns[0])
    
    def generate_graph(self):
        """Generate and display graphs for selected files"""
        # Check if any files are ready
        ready_files = [f for f in self.files if f['csv_path'] and 'Ready' in self.file_list.item(f['tree_id'])['values'][2]]
        
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
        self.status_var.set(f"Generating graphs for {column}...")
        self.update_idletasks()
        
        # Process each file in separate threads to keep UI responsive
        file_data = []  # Will store (file_info, times, values) tuples
        lock = threading.Lock()
        threads = []
        
        def process_file_thread(file_info, file_index):
            try:
                # Extract data from the file
                csv_path = file_info['csv_path']
                
                # Read the CSV and extract the data for the selected column
                times, values = [], []
                row_count = 0
                
                with open(csv_path, 'r', errors='replace') as f:
                    csv_reader = csv.reader(f)
                    headers = next(csv_reader)
                    
                    try:
                        col_index = headers.index(column)
                        time_col = 0  # Assuming time is in the first column
                        
                        # Base time to convert timestamps to relative seconds
                        base_time = None
                        
                        for row in csv_reader:
                            row_count += 1
                            if not row or len(row) <= col_index:
                                continue
                                
                            # Extract timestamp
                            time_str = row[time_col]
                            try:
                                # Convert time string to datetime object
                                import datetime
                                time_obj = datetime.datetime.strptime(time_str, "%H:%M:%S")
                                
                                # Set base time if not set
                                if base_time is None:
                                    base_time = time_obj
                                
                                # Calculate seconds since base time
                                time_delta = (time_obj - base_time).total_seconds()
                                if time_delta < 0:  # Handle crossing midnight
                                    time_delta += 24 * 60 * 60
                                    
                                # Extract value
                                try:
                                    value = float(row[col_index])
                                    times.append(time_delta)
                                    values.append(value)
                                except ValueError:
                                    # Skip if value can't be converted to float
                                    continue
                            except ValueError:
                                # Skip if time can't be parsed
                                continue
                        
                        # Calculate duration from row count if not already set
                        if 'duration' not in file_info:
                            file_info['duration'] = row_count / 0.85
                        
                    except ValueError:
                        self.after(10, lambda: messagebox.showerror("Error", 
                                                                 f"Column '{column}' not found in {os.path.basename(csv_path)}"))
                        return
                
                with lock:
                    file_data.append((file_info, times, values))
                
            except Exception as e:
                self.after(10, lambda: messagebox.showerror("Error", 
                                                         f"Failed to process {os.path.basename(file_info['original_path'])}: {str(e)}"))
        
        # Start a thread for each file
        for i, file_info in enumerate(ready_files):
            thread = threading.Thread(target=process_file_thread, args=(file_info, i))
            threads.append(thread)
            thread.start()
        
        # Define function to update the plot when all threads complete
        def update_plot_when_ready():
            # Check if all threads are done
            if any(t.is_alive() for t in threads):
                self.after(100, update_plot_when_ready)  # Check again in 100ms
                return
            
            # All threads are done, update the plot
            self.update_plot(file_data, column, log_scale)
        
        # Start checking for thread completion
        update_plot_when_ready()

    def update_plot(self, file_data, column, log_scale, apply_offset=False):
        """Update the plot with data from multiple files"""
        if not file_data:
            self.status_var.set("No data to plot")
            return
        
        # Store current plot data for use with the slider
        if not apply_offset:
            self.current_file_data = file_data
            self.current_column = column
            self.current_log_scale = log_scale
            
            # Update file selector dropdown with file names
            file_names = [os.path.basename(info[0]['original_path']) for info in file_data]
            self.file_selector['values'] = file_names
            
            # Select first file by default
            if file_names:
                self.file_selector.current(0)
                self.selected_file_index = 0
                
                # Get dynamic slider range based on file durations
                selected_file_info = file_data[0][0]
                current_file_duration = selected_file_info.get('duration', 300.0)
                
                # Find the longest file duration
                max_duration = 300.0  # Default fallback
                for f_info, _, _ in file_data:
                    if 'duration' in f_info and f_info['duration'] > max_duration:
                        max_duration = f_info['duration']
                
                # Update slider range
                self.time_offset_slider.configure(
                    from_=-current_file_duration,
                    to=max_duration
                )
                
                # Show current offset for the selected file
                file_path = file_data[0][0]['original_path']
                current_offset = self.file_offsets.get(file_path, 0.0)
                self.time_offset_var.set(current_offset)
                self.time_offset_label.config(text=f"{current_offset:.1f}")
            
        try:
            # Clear previous graph
            self.ax.clear()
            
            # Define line styles and markers for additional distinctiveness
            line_styles = ['-', '--', '-.', ':']
            markers = ['o', 's', '^', 'D', 'v', '*', 'p', 'h', '+', 'x']
            
            # Track the full time range across all files
            all_min_time = float('inf')
            all_max_time = float('-inf')
            
            # Track time range of data points (not just endpoints)
            active_data_points = []
            
            # First pass - calculate time ranges and collect active data points
            for i, (file_info, times, values) in enumerate(file_data):
                if not times or not values:
                    continue
                    
                # Get the offset for this file
                file_path = file_info['original_path']
                offset = self.file_offsets.get(file_path, 0.0)
                
                # Calculate min and max times considering offset
                if times:
                    file_min = min(times) + offset
                    file_max = max(times) + offset
                    all_min_time = min(all_min_time, file_min)
                    all_max_time = max(all_max_time, file_max)
                    
                    # Collect all time points for active data calculation
                    active_data_points.extend([t + offset for t in times])
            
            # Plot each file's data
            for i, (file_info, times, values) in enumerate(file_data):
                if not times or not values:
                    continue
                    
                # Get the offset for this file (if any)
                file_path = file_info['original_path']
                offset = self.file_offsets.get(file_path, 0.0)
                
                # Apply time offset if needed
                adjusted_times = [t + offset for t in times]
                    
                filename = os.path.basename(file_info['original_path'])
                color = self.color_cycle[i % len(self.color_cycle)]
                line_style = line_styles[i % len(line_styles)]
                marker = markers[i % len(markers)]
                
                # Include duration in the label if available
                duration_text = ""
                if 'duration' in file_info:
                    duration_text = f" ({file_info['duration']:.1f}s)"
                
                # Use different marker frequency based on data length
                marker_every = max(len(times) // 20, 1) if len(times) > 20 else None
                
                self.ax.plot(
                    adjusted_times, 
                    values, 
                    label=f"{filename}{duration_text} [offset: {offset:.1f}s]" if offset != 0 else f"{filename}{duration_text}", 
                    color=color,
                    linestyle=line_style,
                    marker=marker,
                    markevery=marker_every,
                    markersize=5
                )
            
            # Configure plot
            self.ax.set_xlabel("Time (seconds since start)")
            self.ax.set_ylabel(column)
            self.ax.set_title(f"{column} vs Time")
            self.ax.grid(True)
            
            if log_scale:
                self.ax.set_yscale("log")
            else:
                self.ax.set_yscale("linear")
            
            # Add legend with smaller font if there are many files
            if len(file_data) > 5:
                self.ax.legend(fontsize='small', loc='best')
            else:
                self.ax.legend(loc='best')
            
            # Set x-axis limits with intelligent padding
            if active_data_points and all_min_time != float('inf') and all_max_time != float('-inf'):
                if hasattr(self, 'auto_zoom_var') and self.auto_zoom_var.get():
                    # Auto-zoom to focus on the data density
                    # Sort all data points and find 5th and 95th percentiles to focus on main data
                    sorted_times = sorted(active_data_points)
                    lower_idx = max(0, int(len(sorted_times) * 0.05))
                    upper_idx = min(len(sorted_times) - 1, int(len(sorted_times) * 0.95))
                    
                    focus_min = sorted_times[lower_idx]
                    focus_max = sorted_times[upper_idx]
                    focus_range = focus_max - focus_min
                    
                    # Add padding
                    padding = focus_range * 0.1
                    self.ax.set_xlim(focus_min - padding, focus_max + padding)
                    
                else:
                    # Show all data with padding
                    time_range = all_max_time - all_min_time
                    padding = max(time_range * 0.05, 1.0)  # At least 1 second padding
                    self.ax.set_xlim(all_min_time - padding, all_max_time + padding)
            
            # Force a complete redraw of the canvas
            self.figure.tight_layout()
            self.canvas.draw()
            self.canvas.flush_events()
            
            if not apply_offset:
                self.status_var.set(f"Graph generated for {column} with {len(file_data)} files")
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            messagebox.showerror("Error", f"Failed to update plot: {str(e)}\n\n{error_details}")
            self.status_var.set("Error: Plot update failed")

    def on_file_selected(self, event=None):
        """Handle file selection for time offset adjustment"""
        selected = self.file_selector_var.get()
        
        # Find the index of the selected file in current_file_data
        for i, (file_info, _, _) in enumerate(self.current_file_data):
            filename = os.path.basename(file_info['original_path'])
            if filename == selected:
                self.selected_file_index = i
                
                # Calculate dynamic slider range based on file durations
                current_file_duration = file_info.get('duration', 300.0)
                
                # Find the longest file duration
                max_duration = 300.0  # Default fallback
                for f_info, _, _ in self.current_file_data:
                    if 'duration' in f_info and f_info['duration'] > max_duration:
                        max_duration = f_info['duration']
                
                # Update slider range:
                # Negative range = current file duration (to allow sliding back to start)
                # Positive range = longest file duration (to allow aligning with end)
                self.time_offset_slider.configure(
                    from_=-current_file_duration,
                    to=max_duration
                )
                
                # Update slider to show current offset for this file
                current_offset = self.file_offsets.get(file_info['original_path'], 0.0)
                self.time_offset_var.set(current_offset)
                self.time_offset_label.config(text=f"{current_offset:.1f}")
                break
    
    def update_time_offset(self, event=None):
        """Update the time offset for the selected file"""
        if not self.current_file_data or self.selected_file_index >= len(self.current_file_data):
            return
            
        offset_value = self.time_offset_var.get()
        self.time_offset_label.config(text=f"{offset_value:.1f}")
        
        # Store the offset for this file
        file_info = self.current_file_data[self.selected_file_index][0]
        self.file_offsets[file_info['original_path']] = offset_value
        
        # Update the plot with new offsets
        self.update_plot(self.current_file_data, self.current_column, 
                        self.current_log_scale, apply_offset=True)
    
    def reset_time_offset(self):
        """Reset the time offset for the selected file"""
        if not self.current_file_data or self.selected_file_index >= len(self.current_file_data):
            return
            
        # Reset offset for the selected file
        file_info = self.current_file_data[self.selected_file_index][0]
        self.file_offsets[file_info['original_path']] = 0.0
        
        # Update slider
        self.time_offset_var.set(0.0)
        self.time_offset_label.config(text="0.0")
        
        # Update the plot
        self.update_plot(self.current_file_data, self.current_column, 
                        self.current_log_scale, apply_offset=True)
    
    def reset_all_offsets(self):
        """Reset time offsets for all files"""
        self.file_offsets.clear()
        self.time_offset_var.set(0.0)
        self.time_offset_label.config(text="0.0")
        
        # Update the plot
        if self.current_file_data:
            self.update_plot(self.current_file_data, self.current_column, 
                           self.current_log_scale, apply_offset=True)

if __name__ == "__main__":
    app = DentonGUI()
    app.mainloop()