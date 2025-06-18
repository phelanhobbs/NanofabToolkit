#!/usr/bin/env python3
"""
ParalyneReader Main Application

A GUI application for downloading, processing, and visualizing Paralyne analog data files.
This application connects to the nanofab history API to fetch and analyze Paralyne process data.

Features:
- Download files from the Paralyne analog data API
- Load and parse CSV data files
- Apply various smoothing and normalization techniques
- Generate interactive plots with matplotlib
- Time alignment and data comparison capabilities

Author: Nanofab Toolkit
Date: 2025
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox
import logging

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def setup_logging():
    """Setup logging configuration for the application"""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'paralyne_reader.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("ParalyneReader application starting...")
    return logger

def main():
    """Main entry point for the ParalyneReader application"""
    logger = setup_logging()
    
    try:
        # Import the GUI module
        from gui import ParalyneReaderApp
        
        # Create the root tkinter window
        root = tk.Tk()
        
        # Set application icon if available
        try:
            # Look for icon file in assets directory
            icon_path = os.path.join(os.path.dirname(__file__), 'src', 'assets', 'icon.ico')
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
        except Exception as e:
            logger.warning(f"Could not load application icon: {e}")
        
        # Configure the root window
        root.title("ParalyneReader - Nanofab Data Analysis Tool")
        
        # Center the window on screen
        root.update_idletasks()
        width = root.winfo_reqwidth()
        height = root.winfo_reqheight()
        pos_x = (root.winfo_screenwidth() // 2) - (width // 2)
        pos_y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"+{pos_x}+{pos_y}")
        
        # Create the application instance
        app = ParalyneReaderApp(root)
        
        logger.info("ParalyneReader GUI initialized successfully")
        
        # Handle application close
        def on_closing():
            """Handle application shutdown"""
            logger.info("ParalyneReader application closing...")
            try:
                # Clean up any resources if needed
                if hasattr(app, 'thread_pool'):
                    app.thread_pool.shutdown(wait=False)
                root.destroy()
            except Exception as e:
                logger.error(f"Error during application shutdown: {e}")
                root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Start the GUI event loop
        root.mainloop()
        
    except ImportError as e:
        error_msg = f"Failed to import required modules: {e}\n\nPlease ensure all dependencies are installed:\npip install -r requirements.txt"
        logger.error(error_msg)
        
        # Show error dialog if tkinter is available
        try:
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            messagebox.showerror("Import Error", error_msg)
        except:
            print(error_msg)
        
        sys.exit(1)
        
    except Exception as e:
        error_msg = f"An unexpected error occurred: {e}"
        logger.error(error_msg, exc_info=True)
        
        # Show error dialog
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Application Error", error_msg)
        except:
            print(error_msg)
        
        sys.exit(1)

def check_dependencies():
    """Check if all required dependencies are available"""
    required_modules = [
        'tkinter',
        'requests', 
        'matplotlib',
        'numpy',
        'scipy'
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print("Missing required dependencies:")
        for module in missing_modules:
            print(f"  - {module}")
        print("\nPlease install missing dependencies using:")
        print("pip install -r requirements.txt")
        return False
    
    return True

if __name__ == "__main__":
    # Check dependencies before starting
    if not check_dependencies():
        sys.exit(1)
    
    # Start the application
    main()