import tkinter as tk
from tkinter import ttk
from datetime import datetime
import os
import sys
from tkinter import messagebox
import calendar
from RetrieveMonthsMetals import download_Metal


class PreciousMetalReaderGui:
    def __init__(self, root):
        self.root = root
        self.root.title("Precious Metal Reader")
        self.root.geometry("800x600")
        self.root.resizable(True, True)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        #main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid for main frame
        for i in range(8):  # Reduced by 1 since month and year are on the same line now
            main_frame.rowconfigure(i, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=3)

        #select machine
        self.machine_label = ttk.Label(main_frame, text="Select Machine:")
        self.machine_label.grid(row=0, column=0, sticky=tk.W, pady=5)
        self.machine_choice = tk.StringVar()
        machine_combo = ttk.Combobox(main_frame, textvariable=self.machine_choice, state="readonly")
        machine_combo['values'] = ("Denton635", "Denton18")
        machine_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        machine_combo.bind("<<ComboboxSelected>>", self.update_metal_options)

        #Metal selection
        ttk.Label(main_frame, text="Select Metal:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.metal_choice = tk.StringVar()
        self.metal_combo = ttk.Combobox(main_frame, textvariable=self.metal_choice, state="readonly")
        self.metal_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Date selection - Month and Year on the same line
        date_frame = ttk.Frame(main_frame)
        date_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Month selection (using names instead of numbers)
        ttk.Label(date_frame, text="Select Date:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.month_choice = tk.StringVar()
        month_names = list(calendar.month_name)[1:]  # Get month names, skip first empty string
        month_combo = ttk.Combobox(date_frame, textvariable=self.month_choice, state="readonly", width=10)
        month_combo['values'] = month_names
        month_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        # Year as a text box
        ttk.Label(date_frame, text="Year:").pack(side=tk.LEFT, padx=(10, 5))
        current_year = datetime.now().year
        self.year_choice = tk.StringVar(value=str(current_year))
        year_entry = ttk.Entry(date_frame, textvariable=self.year_choice, width=6)
        year_entry.pack(side=tk.LEFT)
        
        # Download button
        self.download_button = ttk.Button(main_frame, text="Download Data", command=self.download_data)
        self.download_button.grid(row=3, column=0, columnspan=2, pady=20)
        
        # Add the "Download All" button below the "Download Data" button
        self.download_all_button = ttk.Button(main_frame, text="Download All", command=self.download_all_data)
        self.download_all_button.grid(row=3, column=1, columnspan=2, pady=20)

        # Status area
        ttk.Label(main_frame, text="Status:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.status_text = tk.StringVar(value="Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_text)
        status_label.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # File list
        ttk.Label(main_frame, text="Downloaded Files:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.file_listbox = tk.Listbox(main_frame, width=50, height=10)
        self.file_listbox.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Scrollbar for listbox
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.file_listbox.yview)
        scrollbar.grid(row=6, column=2, sticky=(tk.N, tk.S))
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        
        # Open file button
        self.open_button = ttk.Button(main_frame, text="Open Selected File", command=self.open_file)
        self.open_button.grid(row=7, column=0, columnspan=2, pady=10)
        
        # Set default values
        machine_combo.set("Denton635")
        self.update_metal_options(None)  # Initialize metal options
        
        # Set current month as default
        current_month_name = calendar.month_name[datetime.now().month]
        month_combo.set(current_month_name)
        
        # Refresh file list at startup
        self.refresh_file_list()

    def update_metal_options(self, event):
        """Update the metal options based on the selected machine"""
        machine = self.machine_choice.get()
        if machine == "Denton635":
            self.metal_combo['values'] = ("Gold", "Iridium", "Palladium", "Platinum")
        elif machine == "Denton18":
            self.metal_combo['values'] = ("Gold", "Iridium", "Palladium", "Platinum")
        
        # Select the first metal by default
        if self.metal_combo['values']:
            self.metal_combo.set(self.metal_combo['values'][0])
    
    def get_endpoint(self):
        """Convert machine and metal selection to the appropriate endpoint"""
        machine = self.machine_choice.get()
        metal = self.metal_choice.get()
        
        if machine == "Denton635":
            if metal == "Gold":
                return "768"
            elif metal == "Iridium":
                return "808"
            elif metal == "Palladium":
                return "809"
            elif metal == "Platinum":
                return "810"
        elif machine == "Denton18":
            if metal == "Gold":
                return "811"
            elif metal == "Iridium":
                return "812"
            elif metal == "Palladium":
                return "813"
            elif metal == "Platinum":
                return "814"
        
        return None
    
    def get_month_number(self):
        """Convert month name to month number (1-12)"""
        month_name = self.month_choice.get()
        month_names = list(calendar.month_name)[1:]  # Skip the empty string at index 0
        try:
            month = month_names.index(month_name) + 1  # +1 because index starts at 0
            return month
        except ValueError:
            messagebox.showerror("Error", f"Invalid month: {month_name}")
            return None
    
    def download_data(self):
        """Download data based on user selection"""
        try:
            endpoint = self.get_endpoint()
            if not endpoint:
                messagebox.showerror("Error", "Invalid machine/metal combination")
                return
            
            # Get the month number from the month name
            month = self.get_month_number()
            if not month:
                return
            
            # Get and validate the year
            try:
                year = int(self.year_choice.get())
                if year < 1900 or year > 2100:  # Basic validation
                    raise ValueError("Year must be between 1900 and 2100")
            except ValueError as e:
                messagebox.showerror("Error", str(e))
                return
                
            self.status_text.set(f"Downloading data for {self.month_choice.get()} {year}...")
            
            downloaded_file = download_Metal(int(endpoint), month, year)
            
            if downloaded_file:
                self.status_text.set(f"Downloaded to: {downloaded_file}")
                
                # Get the list of files after refresh
                files = self.refresh_file_list()
                
                # Get the basename of the downloaded file
                basename = os.path.basename(downloaded_file)
                
                # Debug output
                print(f"Looking for {basename} in file list...")
                print(f"Available files: {files}")
                
                # Find and select the file in the listbox
                for idx, filename in enumerate(files):
                    if filename == basename:
                        self.file_listbox.selection_clear(0, tk.END)
                        self.file_listbox.selection_set(idx)
                        self.file_listbox.see(idx)
                        break
                else:
                    self.status_text.set(f"Warning: {basename} not found in file list")
            else:
                self.status_text.set("Download failed or no data available.")
            
        except Exception as e:
            self.status_text.set(f"Error: {str(e)}")
            messagebox.showerror("Error", str(e))
    
    def download_all_data(self):
        """Download all data for the selected month and year and combine into one CSV"""
        try:
            # Get the month number from the month name
            month = self.get_month_number()
            if not month:
                return
            
            # Get and validate the year
            try:
                year = int(self.year_choice.get())
                if year < 1900 or year > 2100:  # Basic validation
                    raise ValueError("Year must be between 1900 and 2100")
            except ValueError as e:
                messagebox.showerror("Error", str(e))
                return
            
            self.status_text.set(f"Downloading all data for {self.month_choice.get()} {year}...")
            
            # Use a special indicator to download all endpoints at once
            # Pass "all" as the endpoint to indicate combined download
            downloaded_file = download_Metal("all", month, year)
            
            if downloaded_file:
                self.status_text.set(f"All data downloaded to: {downloaded_file}")
                
                # Refresh the file list
                files = self.refresh_file_list()
                
                # Get the basename of the downloaded file
                basename = os.path.basename(downloaded_file)
                
                # Find and select the file in the listbox
                for idx, filename in enumerate(files):
                    if filename == basename:
                        self.file_listbox.selection_clear(0, tk.END)
                        self.file_listbox.selection_set(idx)
                        self.file_listbox.see(idx)
                        break
                else:
                    self.status_text.set(f"Warning: {basename} not found in listbox")
            else:
                self.status_text.set("Download failed or no data available.")
                
        except Exception as e:
            self.status_text.set(f"Error during bulk download: {str(e)}")
            messagebox.showerror("Error", str(e))
        
    def refresh_file_list(self):
        """Update the list of downloaded files"""
        try:
            self.file_listbox.delete(0, tk.END)
            
            # Determine downloads folder path
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                # Running as compiled executable
                base_dir = os.path.dirname(sys.executable)
                download_dir = os.path.join(base_dir, 'downloads')
            else:
                # Running in a normal Python environment
                current_file = os.path.abspath(__file__)
                src_dir = os.path.dirname(current_file)
                precious_metal_dir = os.path.dirname(src_dir)
                project_dir = os.path.dirname(precious_metal_dir)
                download_dir = os.path.join(project_dir, 'downloads')
            
            # Create directory if it doesn't exist
            if not os.path.exists(download_dir):
                os.makedirs(download_dir, exist_ok=True)
                self.status_text.set(f"Created downloads directory: {download_dir}")
            
            # List all CSV files in the downloads directory
            files = []
            if os.path.exists(download_dir):
                files = [f for f in os.listdir(download_dir) if f.endswith('.csv')]
                files.sort(key=lambda x: os.path.getmtime(os.path.join(download_dir, x)), reverse=True)
                
                if files:
                    for file in files:
                        self.file_listbox.insert(tk.END, file)
                    self.status_text.set(f"Found {len(files)} CSV files")
                else:
                    self.status_text.set(f"No CSV files found in downloads directory")
            else:
                self.status_text.set(f"Downloads directory not found: {download_dir}")
            
            return files  # Return the list of files for debugging
        except Exception as e:
            self.status_text.set(f"Error refreshing file list: {str(e)}")
            messagebox.showerror("Error", f"Failed to refresh file list: {str(e)}")
            return []
    
    def open_file(self):
        """Open the selected file"""
        try:
            selection = self.file_listbox.curselection()
            if not selection:
                messagebox.showinfo("Information", "No file selected")
                return
                
            filename = self.file_listbox.get(selection[0])
            
            # Use a more robust way to find the downloads folder
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                # Running as compiled executable
                base_dir = os.path.dirname(sys.executable)
                filepath = os.path.join(base_dir, 'downloads', filename)
            else:
                # Running in a normal Python environment
                filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'downloads', filename)
            
            if os.path.exists(filepath):
                # Open the file with the default application
                os.startfile(filepath)
            else:
                messagebox.showerror("Error", f"File not found: {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")

# For testing the GUI independently
if __name__ == "__main__":
    root = tk.Tk()
    app = PreciousMetalReaderGui(root)
    root.mainloop()

