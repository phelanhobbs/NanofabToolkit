import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
import threading
from pathlib import Path
import sys

# Add the current directory to the path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import from the Denton modules
from DentonDecoder import convertFile
from DentonGrapher import create_graph

class DentonGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Denton Toolkit")
        self.geometry("1000x700")
        self.minsize(800, 600)
        
        self.current_file = None
        self.csv_file = None
        self.columns = []
        
        self.create_widgets()
        
    def create_widgets(self):
        # Create main frame
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create file selection frame
        file_frame = ttk.LabelFrame(main_frame, text="File Selection")
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # File path display
        self.file_path_var = tk.StringVar(value="No file selected")
        ttk.Label(file_frame, textvariable=self.file_path_var, width=70).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Browse button
        ttk.Button(file_frame, text="Browse", command=self.browse_file).pack(side=tk.RIGHT, padx=5, pady=5)
        
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
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def browse_file(self):
        """Opens a file dialog to select a .dat or .csv file"""
        filetypes = [("Denton files", "*.dat"), ("CSV files", "*.csv"), ("All files", "*.*")]
        filename = filedialog.askopenfilename(filetypes=filetypes)
        
        if filename:
            self.current_file = filename
            self.file_path_var.set(filename)
            
            # Process file depending on its extension
            if filename.lower().endswith('.dat'):
                # Convert .dat to .csv
                self.process_dat_file(filename)
            elif filename.lower().endswith('.csv'):
                # Directly use .csv
                self.csv_file = filename
                self.load_csv_columns()
            else:
                messagebox.showerror("Error", "Selected file must be a .dat or .csv file")
                self.current_file = None
                self.file_path_var.set("No file selected")
    
    def process_dat_file(self, filename):
        """Process a .dat file by converting it to CSV"""
        self.status_var.set("Converting .dat file to CSV...")
        self.update_idletasks()
        
        def conversion_thread():
            try:
                self.csv_file = convertFile(filename)
                self.after(10, lambda: self.status_var.set(f"Converted to {os.path.basename(self.csv_file)}"))
                self.after(10, self.load_csv_columns)
            except Exception as e:
                self.after(10, lambda: messagebox.showerror("Error", f"Failed to convert file: {str(e)}"))
                self.after(10, lambda: self.status_var.set("Error: Conversion failed"))
        
        threading.Thread(target=conversion_thread).start()
    
    def load_csv_columns(self):
        """Load column names from the CSV file into the dropdown"""
        try:
            import csv
            with open(self.csv_file, 'r', errors='replace') as f:
                reader = csv.reader(f)
                self.columns = next(reader)  # Get the header row
            
            self.column_dropdown['values'] = self.columns
            
            # Set default to "Chamber Pressure (Torr)" if it exists
            default_column = "Chamber Pressure (Torr)"
            if default_column in self.columns:
                self.column_var.set(default_column)
            else:
                self.column_var.set(self.columns[0])
                
            self.status_var.set(f"Loaded columns from {os.path.basename(self.csv_file)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load columns: {str(e)}")
            self.status_var.set("Error: Failed to load columns")
    
    def generate_graph(self):
        """Generate and display the graph based on the selected options"""
        if not self.csv_file:
            messagebox.showerror("Error", "No CSV file loaded")
            return
        
        column = self.column_var.get()
        log_scale = self.log_scale_var.get()
        
        self.status_var.set(f"Generating graph for {column}...")
        self.update_idletasks()
        
        # Clear previous graph
        self.ax.clear()
        
        def graph_thread():
            try:
                # Use the existing create_graph function but capture the figure
                temp_output = os.path.join(os.path.dirname(self.csv_file), "temp_graph.png")
                success = create_graph(
                    self.csv_file,
                    column_name=column,
                    output_file=temp_output,
                    show_graph=False,
                    log_scale=log_scale
                )
                
                if success:
                    # Load the graph from the file and display it in our canvas
                    img = plt.imread(temp_output)
                    self.ax.imshow(img)
                    self.ax.axis('off')  # Hide axes
                    self.canvas.draw()
                    
                    # Clean up the temporary file
                    try:
                        os.remove(temp_output)
                    except:
                        pass
                    
                    self.after(10, lambda: self.status_var.set(f"Graph generated for {column}"))
                else:
                    self.after(10, lambda: self.status_var.set("Error: Failed to generate graph"))
            except Exception as e:
                self.after(10, lambda: messagebox.showerror("Error", f"Failed to generate graph: {str(e)}"))
                self.after(10, lambda: self.status_var.set("Error: Graph generation failed"))
        
        threading.Thread(target=graph_thread).start()

if __name__ == "__main__":
    app = DentonGUI()
    app.mainloop()