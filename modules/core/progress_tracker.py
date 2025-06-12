"""
Progress Tracker

This module contains the standardized progress tracking class.
"""


class ProgressTracker:
    """Standardized progress tracking for all operations"""
    @staticmethod
    def emit_progress(signal, current, total, operation, details=""):
        """Emit standardized progress signal"""
        if details:
            message = f"{operation}: {details} ({current}/{total})"
        else:
            message = f"{operation} ({current}/{total})"
        signal.emit(current, total, message)