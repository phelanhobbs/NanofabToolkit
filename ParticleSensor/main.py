import sys
import os
import traceback
import tkinter as tk
from tkinter import messagebox, scrolledtext

def show_error_dialog(title, message):
    """Display a scrollable error dialog with the full traceback"""
    # Create a root window
    root = tk.Tk()
    root.title(title)
    root.geometry("800x600")  # Larger window for error details
    
    # Add instruction label
    tk.Label(root, text="An error occurred. Please send this information to the developer:", 
             pady=10).pack(fill=tk.X)
    
    # Create a scrolled text area for the error message
    error_text = scrolledtext.ScrolledText(root, width=100, height=30)
    error_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    error_text.insert(tk.END, message)
    error_text.config(state=tk.DISABLED)  # Make read-only
    
    # Add a close button
    tk.Button(root, text="Close", command=root.destroy, padx=20).pack(pady=10)
    
    # Center the window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 2
    root.geometry(f"+{x}+{y}")
    
    root.mainloop()

def get_directory():
    """Get the directory containing this script"""
    if getattr(sys, 'frozen', False):
        # Running in a PyInstaller bundle
        return os.path.dirname(sys.executable)
    else:
        # Running as a regular Python script
        return os.path.dirname(os.path.abspath(__file__))

def main():
    """Main entry point for the Particle Sensor application"""
    try:
        # Get the script directory and add src to the path
        script_dir = get_directory()
        src_dir = os.path.join(script_dir, 'src')
        
        # Add the src directory to Python path
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        
        # Change to the script directory
        os.chdir(script_dir)
        
        # Import and run the GUI
        from src.gui import main as gui_main
        gui_main()
        
    except ImportError as e:
        error_message = f"Import Error: {str(e)}\n\nFull traceback:\n{traceback.format_exc()}"
        print(error_message)
        show_error_dialog("Import Error", error_message)
        sys.exit(1)
        
    except Exception as e:
        error_message = f"Unexpected Error: {str(e)}\n\nFull traceback:\n{traceback.format_exc()}"
        print(error_message)
        show_error_dialog("Application Error", error_message)
        sys.exit(1)

if __name__ == "__main__":
    main()