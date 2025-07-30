from pathlib import Path
from typing import List, Optional, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QFileDialog, QPushButton,
    QDialogButtonBox, QLabel, QMessageBox, QComboBox,
    QCheckBox, QSpinBox, QDateEdit, QDateTimeEdit,
    QListWidget, QScrollArea, QWidget, QGroupBox, QListWidgetItem
)
from PyQt6.QtCore import Qt, QDate, QDateTime
from ..models import Profile, MetadataField, FieldType
from ..utils.settings import settings


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
        # Start from default archive location
        default_location = settings.get_default_archive_location()
        path = QFileDialog.getExistingDirectory(
            self, "Select Archive Location", str(default_location)
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
        self.selected_path = None
        self.setWindowTitle("Open Archive")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Recent Archives Section
        recent_group = QGroupBox("Recent Archives")
        recent_layout = QVBoxLayout(recent_group)
        
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(150)
        self.recent_list.currentItemChanged.connect(self.on_recent_selected)
        recent_layout.addWidget(self.recent_list)
        
        # Populate recent archives
        self.populate_recent_archives()
        
        layout.addWidget(recent_group)
        
        # Browse Section
        browse_group = QGroupBox("Browse for Archive")
        browse_layout = QVBoxLayout(browse_group)
        
        # Description
        description = QLabel(
            "Select an archive directory containing an 'archive.json' file."
        )
        description.setWordWrap(True)
        browse_layout.addWidget(description)
        
        # Path selection
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Choose archive directory...")
        self.path_edit.textChanged.connect(self.on_path_changed)
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_path)
        
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_button)
        browse_layout.addLayout(path_layout)
        
        layout.addWidget(browse_group)
        
        # Selected path display
        self.selected_label = QLabel("No archive selected")
        self.selected_label.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(self.selected_label)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Store button box for validation
        self.button_box = buttons
        
        # Initial validation
        self.validate_selection()
    
    def populate_recent_archives(self):
        """Populate the recent archives list."""
        self.recent_list.clear()
        recent_archives = settings.get_recent_archives()
        
        for archive_path in recent_archives:
            if archive_path.exists() and (archive_path / "archive.json").exists():
                # Try to get archive name from config
                try:
                    import json
                    with open(archive_path / "archive.json", 'r') as f:
                        config = json.load(f)
                        name = config.get("name", archive_path.name)
                except:
                    name = archive_path.name
                
                item_text = f"{name} ({archive_path})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, str(archive_path))
                self.recent_list.addItem(item)
        
        if self.recent_list.count() == 0:
            item = QListWidgetItem("No recent archives")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.recent_list.addItem(item)
    
    def on_recent_selected(self, current, previous):
        """Handle selection of a recent archive."""
        if current and current.data(Qt.ItemDataRole.UserRole):
            archive_path = current.data(Qt.ItemDataRole.UserRole)
            self.path_edit.setText(archive_path)
            self.selected_path = Path(archive_path)
            self.selected_label.setText(f"Selected: {self.selected_path}")
            self.validate_selection()
    
    def on_path_changed(self):
        """Handle manual path entry."""
        path_text = self.path_edit.text().strip()
        if path_text:
            self.selected_path = Path(path_text)
        else:
            self.selected_path = None
        self.validate_selection()
    
    def browse_path(self):
        """Browse for an archive directory."""
        # Start from default archive location
        default_location = settings.get_default_archive_location()
        path = QFileDialog.getExistingDirectory(
            self, "Select Archive Directory", str(default_location)
        )
        if path:
            self.path_edit.setText(path)
            self.selected_path = Path(path)
            self.selected_label.setText(f"Selected: {self.selected_path}")
            self.validate_selection()
    
    def validate_selection(self):
        """Validate the selected archive path."""
        valid = False
        
        if self.selected_path and self.selected_path.exists():
            config_file = self.selected_path / "archive.json"
            valid = config_file.exists()
            
            if valid:
                self.selected_label.setText(f"✓ Valid archive: {self.selected_path}")
                self.selected_label.setStyleSheet("font-weight: bold; padding: 10px; color: green;")
            else:
                self.selected_label.setText(f"✗ Invalid archive (no archive.json): {self.selected_path}")
                self.selected_label.setStyleSheet("font-weight: bold; padding: 10px; color: red;")
        elif self.selected_path:
            self.selected_label.setText(f"✗ Path does not exist: {self.selected_path}")
            self.selected_label.setStyleSheet("font-weight: bold; padding: 10px; color: red;")
        else:
            self.selected_label.setText("No archive selected")
            self.selected_label.setStyleSheet("font-weight: bold; padding: 10px; color: gray;")
        
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(valid)
    
    def get_path(self):
        return self.selected_path


class ProfileSelectionDialog(QDialog):
    def __init__(self, profiles: List[Profile], parent=None, file_info: str = None):
        super().__init__(parent)
        self.profiles = profiles
        self.file_info = file_info
        self.selected_profile: Optional[Profile] = None
        
        self.setWindowTitle("Select Profile")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # File info section (if provided)
        if self.file_info:
            file_group = QGroupBox("Current File")
            file_layout = QVBoxLayout(file_group)
            file_label = QLabel(self.file_info)
            file_label.setWordWrap(True)
            file_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    color: #2196F3;
                    background-color: #E3F2FD;
                    padding: 10px;
                    border-radius: 5px;
                    border: 2px solid #2196F3;
                }
            """)
            file_layout.addWidget(file_label)
            layout.addWidget(file_group)
        
        # Description  
        description = QLabel(
            "Select a profile to use for the metadata of this file."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Profile list
        self.profile_list = QListWidget()
        self.profile_list.currentItemChanged.connect(self.on_profile_selected)
        
        for profile in self.profiles:
            item_text = f"{profile.name}"
            if profile.description:
                item_text += f" - {profile.description}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, profile)
            self.profile_list.addItem(item)
        
        layout.addWidget(self.profile_list)
        
        # Profile details
        self.details_label = QLabel("Select a profile to view details")
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.details_label.setWordWrap(True)
        self.details_label.setMaximumHeight(100)
        layout.addWidget(self.details_label)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Set initial state
        self.validate_selection()
    
    def on_profile_selected(self, current, previous):
        if current:
            self.selected_profile = current.data(Qt.ItemDataRole.UserRole)
            self.show_profile_details(self.selected_profile)
        else:
            self.selected_profile = None
            self.details_label.setText("Select a profile to view details")
        
        self.validate_selection()
    
    def show_profile_details(self, profile: Profile):
        details = f"<b>{profile.name}</b><br>"
        if profile.description:
            details += f"{profile.description}<br>"
        details += f"Fields: {len(profile.fields)}"
        
        if profile.fields:
            field_names = [f.display_name for f in profile.fields[:3]]
            if len(profile.fields) > 3:
                field_names.append(f"... and {len(profile.fields) - 3} more")
            details += f" ({', '.join(field_names)})"
        
        self.details_label.setText(details)
    
    def validate_selection(self):
        valid = self.selected_profile is not None
        
        button_box = self.findChild(QDialogButtonBox)
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(valid)
    
    def get_selected_profile(self) -> Optional[Profile]:
        return self.selected_profile


class MetadataCollectionDialog(QDialog):
    def __init__(self, profile: Profile, parent=None, file_info: str = None):
        super().__init__(parent)
        self.profile = profile
        self.file_info = file_info
        self.metadata_values: Dict[str, Any] = {}
        self.field_widgets: Dict[str, Any] = {}
        
        self.setWindowTitle(f"Metadata - {profile.name}")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMaximumWidth(700)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # File info section (if provided)
        if self.file_info:
            file_group = QGroupBox("Current File")
            file_layout = QVBoxLayout(file_group)
            file_label = QLabel(self.file_info)
            file_label.setWordWrap(True)
            file_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    color: #4CAF50;
                    background-color: #E8F5E8;
                    padding: 10px;
                    border-radius: 5px;
                    border: 2px solid #4CAF50;
                }
            """)
            file_layout.addWidget(file_label)
            layout.addWidget(file_group)
        
        # Description
        description = QLabel(f"Fill in the metadata fields for profile '{self.profile.name}':")
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Scroll area for form
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        
        form_layout = QFormLayout(scroll_widget)
        
        # Create form fields based on profile
        for field in self.profile.fields:
            label_text = field.display_name
            if field.required:
                label_text += " *"
            
            widget = self.create_field_widget(field)
            self.field_widgets[field.name] = widget
            
            form_layout.addRow(QLabel(label_text), widget)
            
            if field.description:
                desc_label = QLabel(field.description)
                desc_label.setStyleSheet("color: gray; font-size: 10pt;")
                desc_label.setWordWrap(True)
                form_layout.addRow("", desc_label)
        
        layout.addWidget(scroll_area)
        
        # Required fields note
        if any(f.required for f in self.profile.fields):
            required_note = QLabel("* Required fields")
            required_note.setStyleSheet("color: red; font-size: 10pt;")
            layout.addWidget(required_note)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def create_field_widget(self, field: MetadataField):
        if field.field_type == FieldType.TEXT:
            widget = QLineEdit()
            if field.default_value:
                widget.setText(str(field.default_value))
            return widget
        
        elif field.field_type == FieldType.TEXTAREA:
            widget = QTextEdit()
            widget.setMaximumHeight(100)
            if field.default_value:
                widget.setPlainText(str(field.default_value))
            return widget
        
        elif field.field_type == FieldType.NUMBER:
            widget = QSpinBox()
            widget.setRange(-999999, 999999)
            if field.default_value:
                widget.setValue(int(field.default_value))
            return widget
        
        elif field.field_type == FieldType.DATE:
            widget = QDateEdit()
            widget.setCalendarPopup(True)
            if field.default_value:
                widget.setDate(QDate.fromString(str(field.default_value), Qt.DateFormat.ISODate))
            else:
                widget.setDate(QDate.currentDate())
            return widget
        
        elif field.field_type == FieldType.DATETIME:
            widget = QDateTimeEdit()
            widget.setCalendarPopup(True)
            if field.default_value:
                widget.setDateTime(QDateTime.fromString(str(field.default_value), Qt.DateFormat.ISODate))
            else:
                widget.setDateTime(QDateTime.currentDateTime())
            return widget
        
        elif field.field_type == FieldType.BOOLEAN:
            widget = QCheckBox()
            if field.default_value:
                widget.setChecked(bool(field.default_value))
            return widget
        
        elif field.field_type == FieldType.SELECT:
            widget = QComboBox()
            if field.options:
                widget.addItems(field.options)
                if field.default_value and field.default_value in field.options:
                    widget.setCurrentText(str(field.default_value))
            return widget
        
        elif field.field_type == FieldType.MULTISELECT:
            widget = QListWidget()
            widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            widget.setMaximumHeight(100)
            if field.options:
                for option in field.options:
                    item = QListWidgetItem(option)
                    widget.addItem(item)
                    if field.default_value and option in field.default_value:
                        item.setSelected(True)
            return widget
        
        elif field.field_type == FieldType.TAGS:
            widget = QLineEdit()
            widget.setPlaceholderText("Enter tags separated by commas")
            if field.default_value:
                if isinstance(field.default_value, list):
                    widget.setText(", ".join(field.default_value))
                else:
                    widget.setText(str(field.default_value))
            return widget
        
        else:
            # Fallback to text field
            widget = QLineEdit()
            if field.default_value:
                widget.setText(str(field.default_value))
            return widget
    
    def get_field_value(self, field: MetadataField, widget):
        if field.field_type == FieldType.TEXT:
            return widget.text().strip()
        
        elif field.field_type == FieldType.TEXTAREA:
            return widget.toPlainText().strip()
        
        elif field.field_type == FieldType.NUMBER:
            return widget.value()
        
        elif field.field_type == FieldType.DATE:
            return widget.date().toString(Qt.DateFormat.ISODate)
        
        elif field.field_type == FieldType.DATETIME:
            return widget.dateTime().toString(Qt.DateFormat.ISODate)
        
        elif field.field_type == FieldType.BOOLEAN:
            return widget.isChecked()
        
        elif field.field_type == FieldType.SELECT:
            return widget.currentText()
        
        elif field.field_type == FieldType.MULTISELECT:
            selected_items = []
            for i in range(widget.count()):
                item = widget.item(i)
                if item.isSelected():
                    selected_items.append(item.text())
            return selected_items
        
        elif field.field_type == FieldType.TAGS:
            text = widget.text().strip()
            if text:
                return [tag.strip() for tag in text.split(",") if tag.strip()]
            return []
        
        else:
            return widget.text().strip()
    
    def accept(self):
        # Validate required fields and collect values
        for field in self.profile.fields:
            widget = self.field_widgets[field.name]
            value = self.get_field_value(field, widget)
            
            # Check required fields
            if field.required:
                if field.field_type in [FieldType.TEXT, FieldType.TEXTAREA, FieldType.SELECT]:
                    if not value or (isinstance(value, str) and not value.strip()):
                        QMessageBox.warning(
                            self, "Required Field Missing",
                            f"Please fill in the required field: {field.display_name}"
                        )
                        return
                elif field.field_type in [FieldType.MULTISELECT, FieldType.TAGS]:
                    if not value or len(value) == 0:
                        QMessageBox.warning(
                            self, "Required Field Missing",
                            f"Please fill in the required field: {field.display_name}"
                        )
                        return
            
            # Store the value
            self.metadata_values[field.name] = value
        
        super().accept()
    
    def get_metadata(self) -> Dict[str, Any]:
        return self.metadata_values


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Default archive location
        location_layout = QHBoxLayout()
        self.location_edit = QLineEdit()
        self.location_edit.setText(str(settings.get_default_archive_location()))
        self.location_edit.setReadOnly(True)
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_location)
        
        location_layout.addWidget(self.location_edit)
        location_layout.addWidget(browse_button)
        form_layout.addRow("Default Archive Location:", location_layout)
        
        # Max recent archives
        self.max_recent_spin = QSpinBox()
        self.max_recent_spin.setRange(1, 50)
        self.max_recent_spin.setValue(settings.get("max_recent_archives", 10))
        form_layout.addRow("Max Recent Archives:", self.max_recent_spin)
        
        layout.addLayout(form_layout)
        
        # Clear recent archives button
        clear_button = QPushButton("Clear Recent Archives")
        clear_button.clicked.connect(self.clear_recent_archives)
        layout.addWidget(clear_button)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def browse_location(self):
        """Browse for default archive location."""
        current_location = self.location_edit.text()
        path = QFileDialog.getExistingDirectory(
            self, "Select Default Archive Location", current_location
        )
        if path:
            self.location_edit.setText(path)
    
    def clear_recent_archives(self):
        """Clear the recent archives list."""
        reply = QMessageBox.question(
            self, "Clear Recent Archives",
            "Are you sure you want to clear all recent archives?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            settings.set("recent_archives", [])
            settings.save_settings()
            QMessageBox.information(self, "Success", "Recent archives cleared.")
    
    def accept(self):
        """Save settings and close dialog."""
        # Save default location
        new_location = Path(self.location_edit.text())
        settings.set_default_archive_location(new_location)
        
        # Save max recent archives
        settings.set("max_recent_archives", self.max_recent_spin.value())
        settings.save_settings()
        
        super().accept()