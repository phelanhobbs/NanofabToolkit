import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

# Import your peak counter module
from .peakCount import count_peaks, multi_file_plot

class PeakCounterGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Peak Counter")
        self.root.geometry("1000x800")  # Increased height to accommodate offset controls
        
        # Store selected files and results
        self.selected_files = []
        self.results = []
        self.time_offsets = {}  # Store time offsets for each file
        
        # Parameters for peak detection
        self.height_var = tk.DoubleVar(value=0.0)
        self.prominence_var = tk.DoubleVar(value=0.01)
        self.distance_var = tk.IntVar(value=10)
        self.width_var = tk.DoubleVar(value=0.0)
        
        self._create_widgets()
        
    def _create_widgets(self):
        # Create main frames
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill=tk.X, side=tk.TOP)
        
        files_frame = ttk.Frame(self.root, padding=10)
        files_frame.pack(fill=tk.BOTH, side=tk.TOP, expand=True)
        
        # New frame for time offset controls
        self.offset_frame = ttk.LabelFrame(self.root, text="Time Alignment Controls", padding=10)
        self.offset_frame.pack(fill=tk.X, side=tk.TOP, padx=10, pady=5)
        
        # Container for offset sliders (will be populated dynamically)
        self.offset_controls_frame = ttk.Frame(self.offset_frame)
        self.offset_controls_frame.pack(fill=tk.X, expand=True)
        
        # Reset offsets button
        ttk.Button(self.offset_frame, text="Reset All Offsets", 
                  command=self.reset_offsets).pack(pady=5)
        
        plot_frame = ttk.Frame(self.root, padding=10)
        plot_frame.pack(fill=tk.BOTH, side=tk.BOTTOM, expand=True)
        
        # File selection controls
        file_controls = ttk.Frame(control_frame)
        file_controls.pack(fill=tk.X, pady=5)
        
        ttk.Button(file_controls, text="Add Files", command=self.add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_controls, text="Clear Files", command=self.clear_files).pack(side=tk.LEFT, padx=5)
        
        # Parameter controls
        param_frame = ttk.LabelFrame(control_frame, text="Peak Detection Parameters")
        param_frame.pack(fill=tk.X, pady=10)
        
        # Create parameter inputs
        params = [
            ("Min Height:", self.height_var),
            ("Prominence:", self.prominence_var),
            ("Min Distance:", self.distance_var),
            ("Min Width:", self.width_var)
        ]
        
        for i, (label, var) in enumerate(params):
            ttk.Label(param_frame, text=label).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Entry(param_frame, textvariable=var, width=10).grid(row=i, column=1, padx=5, pady=2)
        
        # Process Button
        ttk.Button(control_frame, text="Process Files", command=self.process_files).pack(pady=10)
        
        # File list (with scrollbar)
        self.file_list = tk.Listbox(files_frame, height=6)
        scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scrollbar.set)
        
        self.file_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Results section
        self.results_text = tk.Text(files_frame, height=10)
        self.results_text.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Plot area
        self.fig = plt.Figure(figsize=(9, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def add_files(self):
        files = filedialog.askopenfilenames(
            title="Select Data Files",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if files:
            for file in files:
                if file not in self.selected_files:
                    self.selected_files.append(file)
                    self.file_list.insert(tk.END, os.path.basename(file))
                    # Initialize time offset for this file
                    self.time_offsets[file] = 0.0
    
    def clear_files(self):
        self.selected_files = []
        self.file_list.delete(0, tk.END)
        self.results_text.delete(1.0, tk.END)
        self.time_offsets = {}
        self.fig.clear()
        self.canvas.draw()
        self._clear_offset_controls()
    
    def _clear_offset_controls(self):
        # Clear all offset controls
        for widget in self.offset_controls_frame.winfo_children():
            widget.destroy()
    
    def create_offset_controls(self):
        # First clear existing controls
        self._clear_offset_controls()
        
        # Create new offset controls for each file
        for i, file_path in enumerate(self.selected_files):
            basename = os.path.basename(file_path)
            
            # Create a frame for this file's offset control
            file_frame = ttk.Frame(self.offset_controls_frame)
            file_frame.pack(fill=tk.X, pady=2)
            
            # Create a label with the filename
            ttk.Label(file_frame, text=f"{basename}:", width=20, 
                     anchor=tk.W).pack(side=tk.LEFT, padx=5)
            
            # Create offset variable and link it to the time_offsets dictionary
            offset_var = tk.DoubleVar(value=self.time_offsets[file_path])
            
            # Create numeric entry for precise control
            entry = ttk.Entry(file_frame, textvariable=offset_var, width=8)
            entry.pack(side=tk.LEFT, padx=5)
            
            # Create a slider for time offset adjustment (-50 to 50)
            slider = ttk.Scale(file_frame, from_=-50, to=50, 
                             orient=tk.HORIZONTAL, length=200,
                             variable=offset_var)
            slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            # Add "Apply" button
            apply_btn = ttk.Button(file_frame, text="Apply", 
                                 command=lambda fp=file_path, ov=offset_var: self.apply_offset(fp, ov))
            apply_btn.pack(side=tk.LEFT, padx=5)
            
            # Add "Zero" button to reset just this file
            zero_btn = ttk.Button(file_frame, text="Zero", 
                                command=lambda fp=file_path, ov=offset_var: self.zero_offset(fp, ov))
            zero_btn.pack(side=tk.LEFT, padx=5)
            
    def apply_offset(self, file_path, offset_var):
        # Update the offset in our dictionary
        self.time_offsets[file_path] = offset_var.get()
        # Update the plot with the new offset
        self.update_plot()
        
    def zero_offset(self, file_path, offset_var):
        # Reset this file's offset to zero
        offset_var.set(0.0)
        self.time_offsets[file_path] = 0.0
        self.update_plot()
        
    def reset_offsets(self):
        # Reset all time offsets to zero
        for file_path in self.time_offsets:
            self.time_offsets[file_path] = 0.0
        
        # Update offset controls
        self.create_offset_controls()
        
        # Update the plot
        self.update_plot()
    
    def process_files(self):
        if not self.selected_files:
            messagebox.showinfo("No Files", "Please select at least one data file to process.")
            return
        
        # Clear previous results
        self.results_text.delete(1.0, tk.END)
        self.results = []
        
        # Get parameters
        params = {
            'height': None if self.height_var.get() == 0 else self.height_var.get(),
            'prominence': self.prominence_var.get(),
            'distance': self.distance_var.get(),
            'width': None if self.width_var.get() == 0 else self.width_var.get(),
        }
        
        # Process each file
        for file_path in self.selected_files:
            peak_count, pressure_times, pressures, peaks = count_peaks(
                file_path, 
                **params,
                plot=False,
                quiet=True
            )
            self.results.append((file_path, peak_count, pressure_times, pressures, peaks))
            
            # Add results to text area
            basename = os.path.basename(file_path)
            self.results_text.insert(tk.END, f"{basename}: {peak_count} peaks\n")
            
            if peaks is not None and len(peaks) > 0:
                self.results_text.insert(tk.END, f"  Peak times: {', '.join([f'{t:.2f}' for t in pressure_times[peaks]])}\n\n")
        
        # Create offset controls for the files
        self.create_offset_controls()
        
        # Plot the results
        self.update_plot()
    
    def update_plot(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        
        # Use a different color for each file
        colors = plt.cm.tab10.colors
        marker_styles = ['o', 's', '^', 'd', 'x', '+', '*', 'v', '<', '>']
        
        for i, (filename, peak_count, pressure_times, pressures, peaks) in enumerate(self.results):
            if pressure_times is None or pressures is None:
                continue
                
            color = colors[i % len(colors)]
            marker = marker_styles[i % len(marker_styles)]
            
            # Apply the time offset to the pressure times
            offset = self.time_offsets.get(filename, 0.0)
            adjusted_times = pressure_times + offset
            
            # Plot the pressure data
            basename = os.path.basename(filename)
            offset_text = f" (offset: {offset:.2f})" if offset != 0 else ""
            label = f"{basename} ({peak_count} peaks){offset_text}"
            
            ax.plot(adjusted_times, pressures, label=label, color=color, alpha=0.7)
            
            # Plot the peaks as points
            if peaks is not None and len(peaks) > 0:
                ax.plot(adjusted_times[peaks], pressures[peaks], marker=marker, 
                        linestyle='None', color=color, markersize=8)
        
        ax.set_title("Pressure vs Time")
        ax.set_xlabel("Pressure Time")
        ax.set_ylabel("Pressure")
        ax.grid(True)
        ax.legend()
        
        self.canvas.draw()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = PeakCounterGUI()
    app.run()