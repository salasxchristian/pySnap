"""
Create Snapshots Dialog

This module contains the dialog for creating snapshots in bulk.
"""

from PyQt6.QtWidgets import (QDialog, QLabel, QLineEdit, QVBoxLayout,
                            QCheckBox, QHBoxLayout, QPushButton, 
                            QTextEdit, QApplication)
from PyQt6.QtCore import Qt, QSettings
from ..widgets import CleanTextEdit


class CreateSnapshotsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Snapshots")
        self.setModal(True)
        self.resize(500, 400)
        
        # Load last window position
        settings = QSettings()
        self.saved_geometry = settings.value("CreateSnapshotsDialogGeometry")
        
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel("Enter server names (one per line):")
        layout.addWidget(instructions)
        
        # Text area for server names with plain text settings
        self.server_list = CleanTextEdit()
        self.server_list.setAcceptRichText(False)
        self.server_list.setPlaceholderText("server1\nserver2\nserver3")
        
        # Force plain text paste
        self.server_list.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.server_list.setAutoFormatting(QTextEdit.AutoFormattingFlag.AutoNone)
        
        # Set a monospace font for better readability
        font = self.server_list.font()
        font.setFamily("Monospace")
        self.server_list.setFont(font)
        
        layout.addWidget(self.server_list)
        
        # Description field
        desc_layout = QHBoxLayout()
        desc_label = QLabel("Snapshot Description:")
        self.desc_input = QLineEdit("Monthly OS Patching")
        desc_layout.addWidget(desc_label)
        desc_layout.addWidget(self.desc_input)
        layout.addLayout(desc_layout)
        
        # Memory snapshot option with warning
        self.memory_check = QCheckBox("Include memory in snapshot (Not Recommended)")
        self.memory_check.setChecked(False)
        layout.addWidget(self.memory_check)
        
        # Warning label for memory option
        memory_warning = QLabel(
            "⚠️ Warning: Including memory will significantly increase snapshot size and\n"
            "creation time. This may impact system performance and storage usage.\n"
            "Only use this option if specifically required."
        )
        memory_warning.setStyleSheet("color: #FF6B6B; font-style: italic;")  # Red warning text
        layout.addWidget(memory_warning)
        
        # Buttons
        button_box = QHBoxLayout()
        create_btn = QPushButton("Create Snapshots")
        create_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_box.addWidget(create_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box)

    def showEvent(self, event):
        """Handle window show event"""
        super().showEvent(event)
        
        # Apply saved position or center the window
        if self.saved_geometry:
            self.restoreGeometry(self.saved_geometry)
        else:
            # Center on screen
            screen = QApplication.primaryScreen().geometry()
            window_size = self.geometry()
            x = (screen.width() - window_size.width()) // 2
            y = (screen.height() - window_size.height()) // 2
            self.move(x, y)

    def get_data(self):
        servers = [s.strip() for s in self.server_list.toPlainText().split('\n') if s.strip()]
        return {
            'servers': servers,
            'description': self.desc_input.text(),
            'memory': self.memory_check.isChecked()
        }

    def closeEvent(self, event):
        """Save window position when closing"""
        settings = QSettings()
        settings.setValue("CreateSnapshotsDialogGeometry", self.saveGeometry())
        super().closeEvent(event)