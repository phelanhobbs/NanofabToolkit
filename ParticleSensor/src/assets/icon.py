"""
Icon module for Particle Sensor application
"""

from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QApplication
import os


def get_icon_path():
    """Get the path to the application icon"""
    # Get the directory containing this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(current_dir, "icon.png")
    return icon_path


def load_icon():
    """
    Load the application icon for PyQt5.
    
    Returns:
        QIcon: The loaded icon image, or None if not found.
    """
    try:
        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        else:
            # Return a default system icon if custom icon not found
            return QApplication.style().standardIcon(QApplication.style().SP_ComputerIcon)
    except Exception:
        # Return None if any error occurs
        return None


def set_window_icon(window):
    """
    Set the window icon for a QMainWindow or QWidget.
    
    Args:
        window: The window to set the icon for
    """
    try:
        icon = load_icon()
        if icon:
            window.setWindowIcon(icon)
    except Exception:
        # Silently ignore icon loading errors
        pass


def create_pixmap(size=(32, 32)):
    """
    Create a QPixmap from the icon file.
    
    Args:
        size: Tuple of (width, height) for the pixmap size
        
    Returns:
        QPixmap: The loaded pixmap, or None if not found
    """
    try:
        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                return pixmap.scaled(size[0], size[1])
        return None
    except Exception:
        return None