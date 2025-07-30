from typing import Optional
import uuid
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QComboBox, QCheckBox,
    QGroupBox, QLabel, QMessageBox, QSplitter, QWidget, QSpinBox
)
from PyQt6.QtCore import Qt

from ..models.profile import Profile, MetadataField, FieldType


class FieldEditorWidget(QWidget):
    """Widget for editing a single metadata field"""
    
    def __init__(self, field: Optional[MetadataField] = None, parent=None):
        super().__init__(parent)
        self.field = field
        self.setup_ui()
        if field:
            self.load_field(field)
    
    def setup_ui(self):
        layout = QFormLayout(self)
        
        # Field name (internal identifier)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., 'title', 'author', 'tags'")
        layout.addRow("Field Name:", self.name_edit)
        
        # Display name (shown to user)
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("e.g., 'Title', 'Author', 'Tags'")
        layout.addRow("Display Name:", self.display_name_edit)
        
        # Field type
        self.type_combo = QComboBox()
        for field_type in FieldType:
            self.type_combo.addItem(field_type.value.title(), field_type)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        layout.addRow("Field Type:", self.type_combo)
        
        # Required checkbox
        self.required_checkbox = QCheckBox()
        layout.addRow("Required:", self.required_checkbox)
        
        # Default value
        self.default_value_edit = QLineEdit()
        self.default_value_edit.setPlaceholderText("Optional default value")
        layout.addRow("Default Value:", self.default_value_edit)
        
        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        self.description_edit.setPlaceholderText("Optional description for this field")
        layout.addRow("Description:", self.description_edit)
        
        # Options (for SELECT/MULTISELECT)
        self.options_edit = QTextEdit()
        self.options_edit.setMaximumHeight(80)
        self.options_edit.setPlaceholderText("One option per line (for select fields)")
        self.options_label = QLabel("Options:")
        layout.addRow(self.options_label, self.options_edit)
        
        # Validation pattern
        self.validation_edit = QLineEdit()
        self.validation_edit.setPlaceholderText("Optional regex pattern for validation")
        layout.addRow("Validation Pattern:", self.validation_edit)
        
        # Initially hide options field
        self.on_type_changed()
    
    def on_type_changed(self):
        """Show/hide options field based on selected type"""
        field_type = self.type_combo.currentData()
        show_options = field_type in [FieldType.SELECT, FieldType.MULTISELECT]
        self.options_label.setVisible(show_options)
        self.options_edit.setVisible(show_options)
    
    def load_field(self, field: MetadataField):
        """Load field data into the form"""
        self.name_edit.setText(field.name)
        self.display_name_edit.setText(field.display_name)
        
        # Set field type
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == field.field_type:
                self.type_combo.setCurrentIndex(i)
                break
        
        self.required_checkbox.setChecked(field.required)
        self.default_value_edit.setText(str(field.default_value) if field.default_value else "")
        self.description_edit.setPlainText(field.description or "")
        
        if field.options:
            self.options_edit.setPlainText("\n".join(field.options))
        
        self.validation_edit.setText(field.validation_pattern or "")
    
    def get_field(self) -> Optional[MetadataField]:
        """Create MetadataField from form data"""
        name = self.name_edit.text().strip()
        display_name = self.display_name_edit.text().strip()
        
        if not name or not display_name:
            return None
        
        field_type = self.type_combo.currentData()
        required = self.required_checkbox.isChecked()
        default_value = self.default_value_edit.text().strip() or None
        description = self.description_edit.toPlainText().strip() or None
        validation_pattern = self.validation_edit.text().strip() or None
        
        # Parse options
        options = None
        if field_type in [FieldType.SELECT, FieldType.MULTISELECT]:
            options_text = self.options_edit.toPlainText().strip()
            if options_text:
                options = [line.strip() for line in options_text.split('\n') if line.strip()]
        
        return MetadataField(
            name=name,
            display_name=display_name,
            field_type=field_type,
            required=required,
            default_value=default_value,
            options=options,
            description=description,
            validation_pattern=validation_pattern
        )
    
    def validate(self) -> tuple[bool, str]:
        """Validate the field data"""
        name = self.name_edit.text().strip()
        display_name = self.display_name_edit.text().strip()
        
        if not name:
            return False, "Field name is required"
        
        if not display_name:
            return False, "Display name is required"
        
        # Check field name format (should be valid identifier)
        if not name.replace('_', '').replace('-', '').isalnum():
            return False, "Field name should contain only letters, numbers, hyphens, and underscores"
        
        field_type = self.type_combo.currentData()
        if field_type in [FieldType.SELECT, FieldType.MULTISELECT]:
            options_text = self.options_edit.toPlainText().strip()
            if not options_text:
                return False, f"{field_type.value.title()} fields must have at least one option"
        
        return True, ""


class ProfileEditorDialog(QDialog):
    """Dialog for creating and editing profiles"""
    
    def __init__(self, profile: Optional[Profile] = None, existing_profiles: list = None, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.existing_profiles = existing_profiles or []
        self.is_editing = profile is not None
        
        self.setWindowTitle("Edit Profile" if self.is_editing else "Create Profile")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        
        if profile:
            self.load_profile(profile)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create splitter for main content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Left panel - Profile info and field list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Profile information
        info_group = QGroupBox("Profile Information")
        info_layout = QFormLayout(info_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., 'Documents', 'Photos', 'Research Papers'")
        info_layout.addRow("Profile Name:", self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Description of what this profile is used for...")
        info_layout.addRow("Description:", self.description_edit)
        
        left_layout.addWidget(info_group)
        
        # Fields list
        fields_group = QGroupBox("Metadata Fields")
        fields_layout = QVBoxLayout(fields_group)
        
        self.fields_list = QListWidget()
        self.fields_list.currentItemChanged.connect(self.on_field_selected)
        fields_layout.addWidget(self.fields_list)
        
        # Field buttons
        field_buttons = QHBoxLayout()
        
        self.add_field_button = QPushButton("Add Field")
        self.add_field_button.clicked.connect(self.add_field)
        field_buttons.addWidget(self.add_field_button)
        
        self.edit_field_button = QPushButton("Edit Field")
        self.edit_field_button.clicked.connect(self.edit_field)
        self.edit_field_button.setEnabled(False)
        field_buttons.addWidget(self.edit_field_button)
        
        self.remove_field_button = QPushButton("Remove Field")
        self.remove_field_button.clicked.connect(self.remove_field)
        self.remove_field_button.setEnabled(False)
        field_buttons.addWidget(self.remove_field_button)
        
        field_buttons.addStretch()
        fields_layout.addLayout(field_buttons)
        
        left_layout.addWidget(fields_group)
        splitter.addWidget(left_panel)
        
        # Right panel - Field editor
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        editor_group = QGroupBox("Field Editor")
        editor_layout = QVBoxLayout(editor_group)
        
        self.field_editor = FieldEditorWidget()
        editor_layout.addWidget(self.field_editor)
        
        # Field editor buttons
        editor_buttons = QHBoxLayout()
        
        self.save_field_button = QPushButton("Save Field")
        self.save_field_button.clicked.connect(self.save_current_field)
        editor_buttons.addWidget(self.save_field_button)
        
        self.cancel_field_button = QPushButton("Cancel")
        self.cancel_field_button.clicked.connect(self.cancel_field_edit)
        editor_buttons.addWidget(self.cancel_field_button)
        
        editor_buttons.addStretch()
        editor_layout.addLayout(editor_buttons)
        
        right_layout.addWidget(editor_group)
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([400, 400])
        
        # Dialog buttons
        dialog_buttons = QHBoxLayout()
        
        self.save_button = QPushButton("Save Profile")
        self.save_button.clicked.connect(self.save_profile)
        dialog_buttons.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        dialog_buttons.addWidget(self.cancel_button)
        
        dialog_buttons.addStretch()
        layout.addLayout(dialog_buttons)
        
        # Initially hide field editor
        self.field_editor.setEnabled(False)
        self.save_field_button.setEnabled(False)
        self.cancel_field_button.setEnabled(False)
    
    def load_profile(self, profile: Profile):
        """Load profile data into the dialog"""
        self.name_edit.setText(profile.name)
        self.description_edit.setPlainText(profile.description)
        
        # Load fields
        for field in profile.fields:
            self.add_field_to_list(field)
    
    def add_field_to_list(self, field: MetadataField):
        """Add a field to the fields list"""
        item = QListWidgetItem(f"{field.display_name} ({field.field_type.value})")
        item.setData(Qt.ItemDataRole.UserRole, field)
        self.fields_list.addItem(item)
    
    def on_field_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle field selection in the list"""
        if current:
            self.edit_field_button.setEnabled(True)
            self.remove_field_button.setEnabled(True)
        else:
            self.edit_field_button.setEnabled(False)
            self.remove_field_button.setEnabled(False)
    
    def add_field(self):
        """Start adding a new field"""
        self.field_editor.load_field(MetadataField("", "", FieldType.TEXT))
        self.field_editor.setEnabled(True)
        self.save_field_button.setEnabled(True)
        self.cancel_field_button.setEnabled(True)
        self.field_editor.name_edit.setFocus()
    
    def edit_field(self):
        """Edit the selected field"""
        current_item = self.fields_list.currentItem()
        if not current_item:
            return
        
        field = current_item.data(Qt.ItemDataRole.UserRole)
        self.field_editor.load_field(field)
        self.field_editor.setEnabled(True)
        self.save_field_button.setEnabled(True)
        self.cancel_field_button.setEnabled(True)
    
    def save_current_field(self):
        """Save the current field being edited"""
        # Validate field
        valid, error_msg = self.field_editor.validate()
        if not valid:
            QMessageBox.warning(self, "Invalid Field", error_msg)
            return
        
        field = self.field_editor.get_field()
        if not field:
            QMessageBox.warning(self, "Invalid Field", "Please fill in all required fields")
            return
        
        # Check for duplicate field names (excluding the current field being edited)
        current_item = self.fields_list.currentItem()
        for i in range(self.fields_list.count()):
            item = self.fields_list.item(i)
            if item == current_item:
                continue
            existing_field = item.data(Qt.ItemDataRole.UserRole)
            if existing_field.name == field.name:
                QMessageBox.warning(self, "Duplicate Field", f"A field with name '{field.name}' already exists")
                return
        
        # Update or add field
        if current_item:
            # Editing existing field
            current_item.setText(f"{field.display_name} ({field.field_type.value})")
            current_item.setData(Qt.ItemDataRole.UserRole, field)
        else:
            # Adding new field
            self.add_field_to_list(field)
        
        # Reset field editor
        self.cancel_field_edit()
    
    def cancel_field_edit(self):
        """Cancel field editing"""
        self.field_editor.setEnabled(False)
        self.save_field_button.setEnabled(False)
        self.cancel_field_button.setEnabled(False)
        self.fields_list.clearSelection()
    
    def remove_field(self):
        """Remove the selected field"""
        current_item = self.fields_list.currentItem()
        if not current_item:
            return
        
        field = current_item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "Remove Field",
            f"Are you sure you want to remove the field '{field.display_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            row = self.fields_list.row(current_item)
            self.fields_list.takeItem(row)
            self.cancel_field_edit()
    
    def save_profile(self):
        """Save the profile"""
        name = self.name_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        
        if not name:
            QMessageBox.warning(self, "Invalid Profile", "Profile name is required")
            return
        
        # Check for duplicate profile names (excluding current profile)
        for existing_profile in self.existing_profiles:
            if existing_profile.name == name and (not self.profile or existing_profile.id != self.profile.id):
                QMessageBox.warning(self, "Duplicate Profile", f"A profile with name '{name}' already exists")
                return
        
        # Collect fields
        fields = []
        for i in range(self.fields_list.count()):
            item = self.fields_list.item(i)
            field = item.data(Qt.ItemDataRole.UserRole)
            fields.append(field)
        
        # Create or update profile
        if self.profile:
            # Update existing profile
            self.profile.name = name
            self.profile.description = description
            self.profile.fields = fields
            self.profile.updated_at = datetime.now().isoformat()
        else:
            # Create new profile
            self.profile = Profile(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                fields=fields,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
        
        self.accept()
    
    def get_profile(self) -> Optional[Profile]:
        """Get the resulting profile"""
        return self.profile