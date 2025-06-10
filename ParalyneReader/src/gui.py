import tkinter as tk
from tkinter import ttk
from datetime import datetime
import os
import sys
from tkinter import messagebox
import calendar
from ParalyneReader import list_files, download_file
import logging

class ParalyneReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Paralyne Reader")
        self.root.geometry("800x600")
        self.root.resizable(True, True)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Title
        title_label = ttk.Label(main_frame, text="Paralyne File Reader", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(0, 10))

        # File list frame
        list_frame = ttk.LabelFrame(main_frame, text="Available Files", padding="5")
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Treeview for file list
        columns = ("filename", "size", "modified")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        
        # Define column headings and widths
        self.tree.heading("filename", text="Filename", anchor="w")
        self.tree.heading("size", text="Size", anchor="center")
        self.tree.heading("modified", text="Last Modified", anchor="center")
        
        self.tree.column("filename", width=300, anchor="w")
        self.tree.column("size", width=100, anchor="center")
        self.tree.column("modified", width=150, anchor="center")

        # Scrollbars for treeview
        v_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Grid treeview and scrollbars
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, pady=(10, 0), sticky=(tk.W, tk.E))
        button_frame.columnconfigure(1, weight=1)

        # Buttons
        self.refresh_btn = ttk.Button(button_frame, text="Refresh List", command=self.refresh_file_list)
        self.refresh_btn.grid(row=0, column=0, padx=(0, 10))

        self.download_btn = ttk.Button(button_frame, text="Download Selected", command=self.download_selected_file)
        self.download_btn.grid(row=0, column=2, padx=(10, 0))

        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready", foreground="green")
        self.status_label.grid(row=3, column=0, pady=(10, 0), sticky="w")

        # Load initial file list
        self.refresh_file_list()

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
                # Assuming list_files returns a list of dictionaries or tuples
                # with filename, size, and modified date
                if isinstance(file_info, dict):
                    filename = file_info.get('filename', 'Unknown')
                    size = self.format_file_size(file_info.get('size', 0))
                    modified = self.format_date(file_info.get('modified', ''))
                elif isinstance(file_info, (list, tuple)) and len(file_info) >= 3:
                    filename = file_info[0]
                    size = self.format_file_size(file_info[1])
                    modified = self.format_date(file_info[2])
                else:
                    # If format is unknown, just display as string
                    filename = str(file_info)
                    size = "Unknown"
                    modified = "Unknown"
                
                self.tree.insert("", "end", values=(filename, size, modified))
            
            self.status_label.config(text=f"Loaded {len(files)} files", foreground="green")
            
        except Exception as e:
            error_msg = f"Failed to load file list: {str(e)}"
            self.status_label.config(text=error_msg, foreground="red")
            messagebox.showerror("Error", error_msg)

    def download_selected_file(self):
        """Download the selected file"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to download.")
            return
        
        # Get the filename from the selected item
        item = self.tree.item(selection[0])
        filename = item['values'][0]
        
        try:
            self.status_label.config(text=f"Downloading {filename}...", foreground="blue")
            self.root.update()
            
            # Call download_file function
            download_file(filename)
            
            self.status_label.config(text=f"Successfully downloaded {filename}", foreground="green")
            messagebox.showinfo("Download Complete", f"File '{filename}' has been downloaded successfully.")
            
        except Exception as e:
            error_msg = f"Failed to download {filename}: {str(e)}"
            self.status_label.config(text=error_msg, foreground="red")
            messagebox.showerror("Download Error", error_msg)

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

if __name__ == "__main__":
    root = tk.Tk()
    app = ParalyneReaderApp(root)
    root.mainloop()