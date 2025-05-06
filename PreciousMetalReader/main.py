import tkinter as tk
import sys
import os

# Get the absolute path of the current script's directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add the current directory and src directory to the Python path
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Add the src directory to the Python path
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.append(src_dir)

# Now import the GUI class
from src.gui import PreciousMetalReaderGui

def main():
    """Main entry point for the Precious Metal Reader application."""
    # Create the root Tkinter window
    root = tk.Tk()
    
    # Create the GUI application
    app = PreciousMetalReaderGui(root)
    
    # Start the main event loop
    root.mainloop()

if __name__ == "__main__":
    main()