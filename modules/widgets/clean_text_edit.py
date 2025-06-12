"""
Clean Text Edit Widget

This module contains a text edit widget that cleans pasted text.
"""

from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import QMimeData


class CleanTextEdit(QTextEdit):
    def insertFromMimeData(self, source):
        """Override paste behavior to clean up text"""
        if source.hasText():
            # Get text and clean it
            text = source.text()
            
            # Split into lines, strip whitespace, and filter out empty lines
            lines = [line.strip() for line in text.splitlines()]
            clean_lines = [line for line in lines if line]
            
            # Join back together and set as plain text
            clean_text = '\n'.join(clean_lines)
            
            # Create new mime data with clean text
            clean_mime = QMimeData()
            clean_mime.setText(clean_text)
            
            # Call parent method with clean data
            super().insertFromMimeData(clean_mime)
        else:
            super().insertFromMimeData(source)