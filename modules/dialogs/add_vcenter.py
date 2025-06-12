"""
Add vCenter Dialog

This module contains the dialog for adding new vCenter connections.
"""

import sys
from PyQt6.QtWidgets import (QDialog, QLabel, QLineEdit, QGridLayout,
                            QCheckBox, QComboBox, QHBoxLayout, QPushButton)
from PyQt6.QtCore import Qt, QSettings
from ..widgets import SecurePasswordField


class AddVCenterDialog(QDialog):
    def __init__(self, saved_servers, config_manager, parent=None):
        super().__init__(parent)
        self.saved_servers = saved_servers
        self.config_manager = config_manager
        self.result = None
        
        self.setWindowTitle("Add vCenter Connection")
        self.setModal(True)
        self.resize(400, 250)
        
        # Load and apply last window position
        settings = QSettings()
        geometry = settings.value("AddVCenterDialogGeometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            # Center relative to parent if no saved position
            if parent:
                parent_geo = parent.geometry()
                x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
                y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
                self.move(x, y)
        
        # Fix for macOS focus issues
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, True)
        if sys.platform == "darwin":  # macOS specific
            self.setWindowModality(Qt.WindowModality.WindowModal)
        
        layout = QGridLayout(self)
        
        # Server selection
        layout.addWidget(QLabel("Saved Servers:"), 0, 0)
        self.server_combo = QComboBox()
        self.server_combo.addItems([''] + list(saved_servers.keys()))  # Add empty option
        self.server_combo.currentTextChanged.connect(self.on_server_selected)
        layout.addWidget(self.server_combo, 0, 1)
        
        # Connection details
        layout.addWidget(QLabel("Hostname:"), 1, 0)
        self.hostname = QLineEdit()
        layout.addWidget(self.hostname, 1, 1)
        
        layout.addWidget(QLabel("Username:"), 2, 0)
        self.username = QLineEdit()
        layout.addWidget(self.username, 2, 1)
        
        layout.addWidget(QLabel("Password:"), 3, 0)
        self.password = SecurePasswordField()
        layout.addWidget(self.password, 3, 1)
        
        # SSL verification checkbox
        self.verify_ssl_check = QCheckBox("Verify SSL Certificate")
        self.verify_ssl_check.setChecked(False)  # Default to disabled for compatibility
        self.verify_ssl_check.setToolTip("Enable this for trusted certificates. Disable for self-signed certs or SSL decryption.")
        layout.addWidget(self.verify_ssl_check, 4, 0, 1, 2)
        
        # Remember checkbox
        self.save_check = QCheckBox("Remember server credentials (passwords stored securely in encrypted database)")
        self.save_check.setChecked(True)
        layout.addWidget(self.save_check, 5, 0, 1, 2)
        
        # Add info label about security
        info_text = ("Note: Passwords are encrypted and stored securely in the application database\n"
                    "Database encryption key is stored in your system's keychain")
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label, 6, 0, 1, 2)
        
        # Buttons
        button_box = QHBoxLayout()
        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_box.addWidget(connect_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box, 7, 0, 1, 2)

    def on_server_selected(self, hostname):
        """Auto-fill saved server details and password"""
        if hostname and hostname in self.saved_servers:
            server_data = self.saved_servers[hostname]
            
            # Handle both old format (string) and new format (dict)
            if isinstance(server_data, str):
                username = server_data
                verify_ssl = False  # Default for old format
            else:
                username = server_data.get('username', '')
                verify_ssl = server_data.get('verify_ssl', False)
            
            self.hostname.setText(hostname)
            self.username.setText(username)
            self.verify_ssl_check.setChecked(verify_ssl)
            
            # Try to get saved password
            secure_password = self.config_manager.get_password(hostname, username)
            if secure_password and not secure_password.is_empty():
                # Get string briefly, set it, then clear
                password_str = secure_password.get_password()
                self.password.setText(password_str)
                # Clear the temporary string
                password_str = '\0' * len(password_str)
                del password_str
            
            self.password.setFocus()

    def get_data(self):
        return {
            'hostname': self.hostname.text(),
            'username': self.username.text(),
            'password': self.password.get_secure_password(),
            'save': self.save_check.isChecked(),
            'verify_ssl': self.verify_ssl_check.isChecked()
        }

    def closeEvent(self, event):
        """Save window position when closing"""
        settings = QSettings()
        settings.setValue("AddVCenterDialogGeometry", self.saveGeometry())
        super().closeEvent(event)