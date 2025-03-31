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
        self.root.geometry("1000x700")
        
        # Store selected files and results
        self.selected_files = []
        self.results = []
        
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
    
    def clear_files(self):
        self.selected_files = []
        self.file_list.delete(0, tk.END)
        self.results_text.delete(1.0, tk.END)
        self.fig.clear()
        self.canvas.draw()
    
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
            
            # Plot the pressure data
            label = f"{os.path.basename(filename)} ({peak_count} peaks)"
            ax.plot(pressure_times, pressures, label=label, color=color, alpha=0.7)
            
            # Plot the peaks as points
            if peaks is not None and len(peaks) > 0:
                ax.plot(pressure_times[peaks], pressures[peaks], marker=marker, 
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