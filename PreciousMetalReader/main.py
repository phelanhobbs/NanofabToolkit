import tkinter as tk
import sys
import os
import logging  # Add logging import

# Set up logging first thing
def setup_logging():
    """Configure logging for the application"""
    # Determine base directory based on whether we're frozen or not
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as compiled executable
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running in a normal Python environment
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create logs directory
    log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Set up log file path
    log_file = os.path.join(log_dir, 'precious_metal_reader.log')
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # This will still log to console during development
        ]
    )
    
    logging.info("Logging initialized")
    return log_file

# Set up logging at the start
log_file = setup_logging()

# Get the absolute path of the current script's directory
current_dir = os.path.dirname(os.path.abspath(__file__))
logging.info(f"Current directory: {current_dir}")

# Add the current directory and src directory to the Python path
if current_dir not in sys.path:
    sys.path.append(current_dir)
    logging.info(f"Added {current_dir} to sys.path")

# Add the src directory to the Python path
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.append(src_dir)
    logging.info(f"Added {src_dir} to sys.path")

# Now import the GUI class
try:
    from src.gui import PreciousMetalReaderGui
    logging.info("Successfully imported PreciousMetalReaderGui")
except ImportError as e:
    logging.error(f"Failed to import PreciousMetalReaderGui: {e}")
    # Show error dialog if possible
    try:
        import tkinter.messagebox
        tkinter.messagebox.showerror("Import Error", 
                                    f"Failed to import required modules: {e}\nPlease check the installation.")
    except:
        print(f"Critical error: {e}")  # Fallback if tkinter fails
    sys.exit(1)

def main():
    """Main entry point for the Precious Metal Reader application."""
    logging.info("Starting Precious Metal Reader application")
    
    try:
        # Create the root Tkinter window
        root = tk.Tk()
        logging.info("Created Tkinter root window")
        
        # Create the GUI application
        app = PreciousMetalReaderGui(root)
        logging.info("Initialized GUI application")
        
        # Start the main event loop
        logging.info("Entering main event loop")
        root.mainloop()
        logging.info("Exited main event loop")
    except Exception as e:
        logging.exception("Unhandled exception in main function")
        try:
            import tkinter.messagebox
            tkinter.messagebox.showerror("Error", 
                                       f"An unexpected error occurred: {e}\n\nDetails have been written to the log file.")
        except:
            print(f"Critical error: {e}")  # Fallback if tkinter fails

if __name__ == "__main__":
    main()