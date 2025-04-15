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
        
        self.create_widgets()
        
    def generate_distinct_colors(self, n):
        """Generate n visually distinct colors"""
        colors = []
        for i in range(n):
            # Use HSV color space to get evenly spaced hues
            h = i / n
            s = 0.7 + 0.3 * (i % 3) / 2  # Vary saturation slightly
            v = 0.8 + 0.2 * ((i // 3) % 2)  # Vary value slightly
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            colors.append(f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}')
        return colors
        
    def create_widgets(self):
        # Create main frame
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create file selection frame
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
        self.file_list.column("file", width=400, anchor="w")
        self.file_list.column("type", width=100, anchor="center")
        self.file_list.column("status", width=150, anchor="center")
        
        self.file_list.pack(fill=tk.BOTH, expand=True)
        self.file_list.config(yscrollcommand=file_list_scrollbar.set)
        file_list_scrollbar.config(command=self.file_list.yview)
        
        # File control buttons
        file_button_frame = ttk.Frame(file_frame)
        file_button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(file_button_frame, text="Add Files", command=self.add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_button_frame, text="Remove Selected", command=self.remove_selected_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_button_frame, text="Clear All Files", command=self.clear_all_files).pack(side=tk.LEFT, padx=5)
        
        # Create graph options frame
        options_frame = ttk.LabelFrame(main_frame, text="Graph Options")
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Column selection
        ttk.Label(options_frame, text="Select column to graph:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.column_var = tk.StringVar(value="Chamber Pressure (Torr)")
        self.column_dropdown = ttk.Combobox(options_frame, textvariable=self.column_var, width=40, state="readonly")
        self.column_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        # Log scale option
        self.log_scale_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Use logarithmic scale", variable=self.log_scale_var).grid(
            row=1, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        
        # Graph button
        ttk.Button(options_frame, text="Generate Graph", command=self.generate_graph).grid(
            row=2, column=0, columnspan=2, padx=5, pady=5)
        
        # Create graph frame
        graph_frame = ttk.LabelFrame(main_frame, text="Graph")
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
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
                
                with open(csv_path, 'r', errors='replace') as f:
                    csv_reader = csv.reader(f)
                    headers = next(csv_reader)
                    
                    try:
                        col_index = headers.index(column)
                        time_col = 0  # Assuming time is in the first column
                        
                        # Base time to convert timestamps to relative seconds
                        base_time = None
                        
                        for row in csv_reader:
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

    def update_plot(self, file_data, column, log_scale):
        """Update the plot with data from multiple files"""
        if not file_data:
            self.status_var.set("No data to plot")
            return
            
        try:
            # Plot each file's data
            for i, (file_info, times, values) in enumerate(file_data):
                if not times or not values:
                    continue
                    
                filename = os.path.basename(file_info['original_path'])
                color = self.color_cycle[i % len(self.color_cycle)]  # Use cycling colors
                
                self.ax.plot(times, values, label=filename, color=color)
            
            # Configure plot
            self.ax.set_xlabel("Time (seconds since start)")
            self.ax.set_ylabel(column)
            self.ax.set_title(f"{column} vs Time (Multiple Files)")
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
            
            # Force a complete redraw of the canvas
            self.figure.tight_layout()
            self.canvas.draw()
            self.canvas.flush_events()
            
            self.status_var.set(f"Graph generated for {column} with {len(file_data)} files")
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            messagebox.showerror("Error", f"Failed to update plot: {str(e)}\n\n{error_details}")
            self.status_var.set("Error: Plot update failed")

if __name__ == "__main__":
    app = DentonGUI()
    app.mainloop()