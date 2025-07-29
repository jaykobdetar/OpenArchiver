from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QFileDialog, QPushButton,
    QDialogButtonBox, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt


class NewArchiveDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Archive")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Path selection
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Choose location for archive...")
        path_button = QPushButton("Browse...")
        path_button.clicked.connect(self.browse_path)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(path_button)
        form_layout.addRow("Location:", path_layout)
        
        # Name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter archive name...")
        form_layout.addRow("Name:", self.name_edit)
        
        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Optional description...")
        form_layout.addRow("Description:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Connect validation
        self.path_edit.textChanged.connect(self.validate_input)
        self.name_edit.textChanged.connect(self.validate_input)
        
        # Initial validation
        self.validate_input()
    
    def browse_path(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Archive Location"
        )
        if path:
            self.path_edit.setText(path)
    
    def validate_input(self):
        path = self.path_edit.text().strip()
        name = self.name_edit.text().strip()
        
        valid = bool(path and name)
        
        button_box = self.findChild(QDialogButtonBox)
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(valid)
    
    def accept(self):
        path = Path(self.path_edit.text().strip())
        name = self.name_edit.text().strip()
        
        # Create full archive path
        archive_path = path / name
        
        if archive_path.exists():
            reply = QMessageBox.question(
                self, "Directory Exists",
                f"Directory '{archive_path}' already exists. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        super().accept()
    
    def get_values(self):
        path = Path(self.path_edit.text().strip())
        name = self.name_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        
        archive_path = path / name
        return archive_path, name, description


class OpenArchiveDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Archive")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Description
        description = QLabel(
            "Select an archive directory containing an 'archive.json' file."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Path selection
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Choose archive directory...")
        path_button = QPushButton("Browse...")
        path_button.clicked.connect(self.browse_path)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(path_button)
        layout.addLayout(path_layout)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Connect validation
        self.path_edit.textChanged.connect(self.validate_input)
        
        # Initial validation
        self.validate_input()
    
    def browse_path(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Archive Directory"
        )
        if path:
            self.path_edit.setText(path)
    
    def validate_input(self):
        path_text = self.path_edit.text().strip()
        valid = False
        
        if path_text:
            path = Path(path_text)
            config_file = path / "archive.json"
            valid = path.exists() and config_file.exists()
        
        button_box = self.findChild(QDialogButtonBox)
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(valid)
    
    def get_path(self):
        return Path(self.path_edit.text().strip())