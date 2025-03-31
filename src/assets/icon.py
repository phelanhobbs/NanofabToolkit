from tkinter import PhotoImage

def load_icon():
    """
    Load the application icon.
    
    Returns:
        PhotoImage: The loaded icon image.
    """
    icon_path = "src/assets/icon.png"  # Update with the actual path to your icon file
    return PhotoImage(file=icon_path)