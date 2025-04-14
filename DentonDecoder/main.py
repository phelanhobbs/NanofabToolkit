import sys
import os
import traceback
import tkinter as tk
from tkinter import messagebox, scrolledtext

# Set matplotlib backend before any matplotlib imports
import matplotlib
matplotlib.use('TkAgg')  # Force TkAgg backend for compatibility

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
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    root.mainloop()
    sys.exit(1)  # Exit after showing error

def show_error(exception_type, exception_value, exception_traceback):
    """Global exception handler for showing errors in a windowed app"""
    err_msg = "".join(traceback.format_exception(exception_type, exception_value, exception_traceback))
    show_error_dialog("Unexpected Error", err_msg)
    return True  # Prevent default handler from running

def main():
    try:
        # Try to check environment information first
        env_info = f"Python version: {sys.version}\n"
        env_info += f"Executable path: {sys.executable}\n"
        env_info += f"Operating system: {sys.platform}\n"
        
        # Try importing required libraries with error checking
        try:
            import numpy
            env_info += f"NumPy version: {numpy.__version__}\n"
        except ImportError as e:
            env_info += f"NumPy import error: {str(e)}\n"
            
        try:
            import matplotlib
            env_info += f"Matplotlib version: {matplotlib.__version__}\n"
        except ImportError as e:
            env_info += f"Matplotlib import error: {str(e)}\n"
        
        # Add the current directory to sys.path if needed
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.append(current_dir)
            
        # Also add the src directory to sys.path if needed
        src_dir = os.path.join(current_dir, 'src')
        if os.path.exists(src_dir) and src_dir not in sys.path:
            sys.path.append(src_dir)

        # Now try running the actual application
        from src.gui import DentonGUI
        app = DentonGUI()
        app.mainloop()
        
    except Exception as e:
        # Get full traceback
        error_traceback = traceback.format_exc()
        
        # Create detailed error message
        error_message = "Denton Decoder application failed to start.\n\n"
        error_message += "Error details:\n"
        error_message += f"{str(e)}\n\n"
        error_message += "Environment information:\n"
        error_message += env_info + "\n\n"
        error_message += "Full traceback:\n"
        error_message += error_traceback
        
        # Show the error dialog
        show_error_dialog("Application Error", error_message)

if __name__ == "__main__":
    # Set up global exception handler for windowed mode
    sys.excepthook = show_error
    main()