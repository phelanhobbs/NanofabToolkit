import tkinter as tk
from tkinter import ttk
from datetime import datetime
import os
import sys
from tkinter import messagebox
import calendar
from RetrieveMonthsMetals import download_Metal, summarize_metal_charges, save_summary_to_csv
import logging

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
        for i in range(9):  # Added one more row for the new option
            main_frame.rowconfigure(i, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=3)

        # Date selection - Month and Year at the top
        date_frame = ttk.Frame(main_frame)
        date_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
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
        
        # Download option selection (specific tool/metal or all)
        option_frame = ttk.Frame(main_frame)
        option_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.download_option = tk.StringVar(value="specific")
        specific_radio = ttk.Radiobutton(option_frame, text="Specific Tool/Metal", 
                                        variable=self.download_option, value="specific",
                                        command=self.toggle_selection_mode)
        specific_radio.pack(side=tk.LEFT, padx=(0, 20))
        
        all_radio = ttk.Radiobutton(option_frame, text="All Tools/Metals", 
                                   variable=self.download_option, value="all",
                                   command=self.toggle_selection_mode)
        all_radio.pack(side=tk.LEFT)

        # Select machine
        self.machine_label = ttk.Label(main_frame, text="Select Machine:")
        self.machine_label.grid(row=2, column=0, sticky=tk.W, pady=5)
        self.machine_choice = tk.StringVar()
        self.machine_combo = ttk.Combobox(main_frame, textvariable=self.machine_choice, state="readonly")
        self.machine_combo['values'] = ("Denton635", "Denton18", "TMV")
        self.machine_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        self.machine_combo.bind("<<ComboboxSelected>>", self.update_metal_options)

        # Metal selection
        ttk.Label(main_frame, text="Select Metal:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.metal_choice = tk.StringVar()
        self.metal_combo = ttk.Combobox(main_frame, textvariable=self.metal_choice, state="readonly")
        self.metal_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Download button
        self.download_button = ttk.Button(main_frame, text="Download Data", command=self.download_data)
        self.download_button.grid(row=4, column=0, pady=20)
        
        # Add the "Download All" button next to the "Download Data" button
        self.download_all_button = ttk.Button(main_frame, text="Download All", command=self.download_all_data)
        self.download_all_button.grid(row=4, column=1, pady=20)

        # Status area
        ttk.Label(main_frame, text="Status:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.status_text = tk.StringVar(value="Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_text)
        status_label.grid(row=5, column=1, sticky=tk.W, pady=5)
        
        # File list
        ttk.Label(main_frame, text="Downloaded Files:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.file_listbox = tk.Listbox(main_frame, width=50, height=10)
        self.file_listbox.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Scrollbar for listbox
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.file_listbox.yview)
        scrollbar.grid(row=7, column=2, sticky=(tk.N, tk.S))
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        
        # Open file button
        self.open_button = ttk.Button(main_frame, text="Open Selected File", command=self.open_file)
        self.open_button.grid(row=8, column=0, columnspan=2, pady=10)
        
        # Set default values
        self.machine_combo.set("Denton635")
        self.update_metal_options(None)  # Initialize metal options
        
        # Set current month as default
        current_month_name = calendar.month_name[datetime.now().month]
        month_combo.set(current_month_name)
        
        # Initialize UI state based on download option
        self.toggle_selection_mode()
        
        # Refresh file list at startup
        self.refresh_file_list()

    def toggle_selection_mode(self):
        """Toggle between specific tool/metal mode and all mode"""
        mode = self.download_option.get()
        if mode == "specific":
            # Enable machine and metal selection
            self.machine_combo.config(state="readonly")
            self.metal_combo.config(state="readonly")
        else:  # mode == "all"
            # Disable machine and metal selection
            self.machine_combo.config(state="disabled")
            self.metal_combo.config(state="disabled")

    def update_metal_options(self, event):
        """Update the metal options based on the selected machine"""
        machine = self.machine_choice.get()
        if machine == "Denton635":
            self.metal_combo['values'] = ("Gold", "Iridium", "Palladium", "Platinum")
        elif machine == "Denton18":
            self.metal_combo['values'] = ("Gold", "Iridium", "Palladium", "Platinum")
        elif machine == "TMV":
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
        elif machine == "TMV":
            if metal == "Gold":
                return "815"
            elif metal == "Iridium":
                return "816"
            elif metal == "Palladium":
                return "817"
            elif metal == "Platinum":
                return "818"
            
        
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
            # Check if we're in "all" mode
            if self.download_option.get() == "all":
                self.download_all_data()
                return
                
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
                # Generate summary after download
                self.status_text.set(f"Generating summary from {downloaded_file}...")
                summary = summarize_metal_charges(downloaded_file)
                
                if summary:
                    # Save the summary to CSV
                    summary_file = save_summary_to_csv(summary, downloaded_file)
                    if summary_file:
                        self.status_text.set(f"Downloaded to: {downloaded_file}\nSummary saved to: {os.path.basename(summary_file)}")
                    else:
                        self.status_text.set(f"Downloaded to: {downloaded_file}\nFailed to create summary file")
                else:
                    self.status_text.set(f"Downloaded to: {downloaded_file}\nNo summary data available")
                
                # Refresh file list to include the new summary file
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
            logging.exception("An error occurred")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
    
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
                # Generate summary after download
                self.status_text.set(f"Generating summary from {downloaded_file}...")
                summary = summarize_metal_charges(downloaded_file)
                
                if summary:
                    # Save the summary to CSV
                    summary_file = save_summary_to_csv(summary, downloaded_file)
                    if summary_file:
                        self.status_text.set(f"All data downloaded to: {downloaded_file}\nSummary saved to: {os.path.basename(summary_file)}")
                    else:
                        self.status_text.set(f"All data downloaded to: {downloaded_file}\nFailed to create summary file")
                else:
                    self.status_text.set(f"All data downloaded to: {downloaded_file}\nNo summary data available")
                
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
            logging.exception("An error occurred")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
        
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
            summary_files = []
            if os.path.exists(download_dir):
                all_files = [f for f in os.listdir(download_dir) if f.endswith('.csv')]
                all_files.sort(key=lambda x: os.path.getmtime(os.path.join(download_dir, x)), reverse=True)
                
                # Separate summary files and regular files
                for file in all_files:
                    if file.endswith('_summary.csv'):
                        summary_files.append(file)
                    else:
                        files.append(file)
                
                # Add files to listbox with special formatting for summaries
                if files or summary_files:
                    # First add regular data files
                    for file in files:
                        self.file_listbox.insert(tk.END, file)
                    
                    # Add a separator if we have both types
                    if files and summary_files:
                        self.file_listbox.insert(tk.END, "-" * 30)
                    
                    # Add summary files with prefix
                    for file in summary_files:
                        self.file_listbox.insert(tk.END, f"📊 {file}")
                    
                    self.status_text.set(f"Found {len(files)} data files and {len(summary_files)} summary files")
                else:
                    self.status_text.set(f"No CSV files found in downloads directory")
            else:
                self.status_text.set(f"Downloads directory not found: {download_dir}")
            
            return files + summary_files  # Return the list of all files
        except Exception as e:
            logging.exception("An error occurred")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            return []
    
    def open_file(self):
        """Open the selected file"""
        try:
            selection = self.file_listbox.curselection()
            if not selection:
                messagebox.showinfo("Information", "No file selected")
                return
                
            filename = self.file_listbox.get(selection[0])
            
            # Remove the summary emoji prefix if present
            if filename.startswith("📊 "):
                filename = filename[2:]
            
            # Skip separator lines
            if filename.startswith("-"):
                messagebox.showinfo("Information", "Please select a file, not a separator")
                return
            
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
            logging.exception("An error occurred")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

# For testing the GUI independently
if __name__ == "__main__":
    root = tk.Tk()
    app = PreciousMetalReaderGui(root)
    root.mainloop()

