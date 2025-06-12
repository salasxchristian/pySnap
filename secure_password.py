"""
Secure Password Module

Cross-platform secure password storage that minimizes memory exposure.
This module provides a SecurePassword class that stores passwords as byte arrays
and provides automatic clearing functionality to reduce security risks.
"""

import os
import time
from typing import Optional


class SecurePassword:
    """Cross-platform secure password storage that minimizes memory exposure."""
    
    def __init__(self, password: str = ""):
        """
        Initialize secure password storage.
        
        Args:
            password (str): The password to store securely
        """
        self._data = bytearray(password.encode('utf-8')) if password else bytearray()
        self._created_at = time.time()
        
    def get_password(self) -> str:
        """
        Get password as string (use sparingly and clear quickly).
        
        Returns:
            str: The password as a plaintext string
            
        Warning:
            This method returns plaintext - use sparingly and clear the returned
            string immediately after use to minimize memory exposure.
        """
        if not self._data:
            return ""
        return bytes(self._data).decode('utf-8')
    
    def clear(self):
        """Securely clear password from memory."""
        if self._data:
            # Overwrite with random data first, then zeros
            for i in range(len(self._data)):
                self._data[i] = os.urandom(1)[0]
            for i in range(len(self._data)):
                self._data[i] = 0
            self._data.clear()
    
    def is_empty(self) -> bool:
        """
        Check if password is empty.
        
        Returns:
            bool: True if password is empty
        """
        return len(self._data) == 0
    
    def __len__(self):
        """Return length of password."""
        return len(self._data)
        
    def __del__(self):
        """Ensure password is cleared when object is destroyed."""
        self.clear()
        
    def __bool__(self):
        """Return True if password is not empty."""
        return not self.is_empty()
        
    def __str__(self):
        """Return masked representation for debugging."""
        if self.is_empty():
            return "SecurePassword(empty)"
        return f"SecurePassword({len(self._data)} chars)"
        
    def __repr__(self):
        """Return masked representation for debugging."""
        return self.__str__()