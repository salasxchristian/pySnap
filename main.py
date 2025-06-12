#!/usr/bin/env python3
"""
pySnap

Main entry point for the application.
"""

import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon

from modules.core import SnapshotManagerWindow
from version import __version__

# Built by Christian Salas


def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # Log the exception
    logger = logging.getLogger('pySnap')
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    
    # Show simple error dialog
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("Application Error")
    msg.setText("An unexpected error occurred. Check the log file ~/pysnap.log for details.")
    msg.exec()


def main():
    """Main application entry point"""
    try:
        # Set up global exception handler
        sys.excepthook = handle_exception
        
        # Fix for macOS focus issues
        # os.environ['QT_MAC_WANTS_LAYER'] = '1'
        
        app = QApplication(sys.argv)
        app.setApplicationName("pySnap")
        app.setApplicationDisplayName("pySnap")
        # app.setOrganizationName("Your Organization")
        # app.setOrganizationDomain("your-domain.com")
        
        # Set application icon
        icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'app_icon.png')
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        
        window = SnapshotManagerWindow()
        window.show()
        
        sys.exit(app.exec())
        
    except Exception as e:
        # Fallback error handling
        print(f"Critical error during startup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()