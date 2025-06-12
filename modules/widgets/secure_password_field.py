"""
Secure Password Field Widget

This module contains a secure password field that stores data securely.
"""

from PyQt6.QtWidgets import QLineEdit
from secure_password import SecurePassword


class SecurePasswordField(QLineEdit):
    """Password field that stores data securely and clears on demand."""
    
    def __init__(self):
        super().__init__()
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self._secure_password = SecurePassword()
        
        # Update secure storage whenever text changes
        self.textChanged.connect(self._update_secure_storage)
    
    def _update_secure_storage(self):
        """Update internal secure storage when text changes."""
        self._secure_password.clear()
        self._secure_password = SecurePassword(super().text())
    
    def get_secure_password(self) -> SecurePassword:
        """Get the secure password object."""
        return self._secure_password
    
    def clear_secure(self):
        """Securely clear both display and internal storage."""
        self._secure_password.clear()
        self.clear()
    
    def setText(self, text: str):
        """Override setText to update secure storage."""
        super().setText(text)
        self._update_secure_storage()