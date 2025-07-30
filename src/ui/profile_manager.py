from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QGroupBox, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt

from ..models import Archive
from .profile_editor_dialog import ProfileEditorDialog


class ProfileManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.archive: Optional[Archive] = None
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        # Left panel - Profile list
        list_group = QGroupBox("Profiles")
        list_layout = QVBoxLayout(list_group)
        
        self.profile_list = QListWidget()
        self.profile_list.currentItemChanged.connect(self.on_profile_selected)
        list_layout.addWidget(self.profile_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.new_button = QPushButton("New...")
        self.new_button.clicked.connect(self.new_profile)
        button_layout.addWidget(self.new_button)
        
        self.edit_button = QPushButton("Edit...")
        self.edit_button.clicked.connect(self.edit_profile)
        self.edit_button.setEnabled(False)
        button_layout.addWidget(self.edit_button)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_profile)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)
        
        list_layout.addLayout(button_layout)
        layout.addWidget(list_group)
        
        # Right panel - Profile details
        details_group = QGroupBox("Profile Details")
        details_layout = QVBoxLayout(details_group)
        
        self.details_label = QLabel("Select a profile to view details")
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.details_label.setWordWrap(True)
        details_layout.addWidget(self.details_label)
        
        layout.addWidget(details_group)
        
        # Initially disable everything
        self.set_enabled(False)
    
    def set_archive(self, archive: Optional[Archive]):
        self.archive = archive
        if archive:
            self.set_enabled(True)
            self.refresh_profiles()
        else:
            self.set_enabled(False)
            self.profile_list.clear()
            self.details_label.setText("No archive loaded")
    
    def set_enabled(self, enabled: bool):
        self.new_button.setEnabled(enabled)
        self.profile_list.setEnabled(enabled)
    
    def refresh_profiles(self):
        if not self.archive:
            return
        
        self.profile_list.clear()
        
        try:
            profile_files = self.archive.get_profiles()
            
            for profile_file in profile_files:
                from ..models import Profile
                profile = Profile.load_from_file(profile_file)
                
                item = QListWidgetItem(profile.name)
                item.setData(Qt.ItemDataRole.UserRole, profile)
                self.profile_list.addItem(item)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load profiles:\n{e}")
    
    def on_profile_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current:
            profile = current.data(Qt.ItemDataRole.UserRole)
            self.show_profile_details(profile)
            self.edit_button.setEnabled(True)
            self.delete_button.setEnabled(True)
        else:
            self.details_label.setText("Select a profile to view details")
            self.edit_button.setEnabled(False)
            self.delete_button.setEnabled(False)
    
    def show_profile_details(self, profile):
        details = f"<h3>{profile.name}</h3>"
        details += f"<p><b>ID:</b> {profile.id}</p>"
        details += f"<p><b>Description:</b> {profile.description or 'None'}</p>"
        details += f"<p><b>Created:</b> {profile.created_at[:10] if profile.created_at else 'Unknown'}</p>"
        details += f"<p><b>Fields:</b> {len(profile.fields)}</p>"
        
        if profile.fields:
            details += "<h4>Metadata Fields:</h4><ul>"
            for field in profile.fields:
                required = " (required)" if field.required else ""
                details += f"<li><b>{field.display_name}</b> ({field.field_type.value}){required}</li>"
            details += "</ul>"
        
        self.details_label.setText(details)
    
    def new_profile(self):
        """Create a new profile"""
        if not self.archive:
            return
        
        try:
            # Get existing profiles for duplicate checking
            existing_profiles = []
            profile_files = self.archive.get_profiles()
            for profile_file in profile_files:
                from ..models import Profile
                existing_profiles.append(Profile.load_from_file(profile_file))
            
            # Open profile editor dialog
            dialog = ProfileEditorDialog(existing_profiles=existing_profiles, parent=self)
            if dialog.exec() == ProfileEditorDialog.DialogCode.Accepted:
                profile = dialog.get_profile()
                if profile:
                    # Save profile to file
                    profile_file = self.archive.profiles_path / f"{profile.id}.json"
                    profile.save_to_file(profile_file)
                    
                    # Refresh the list
                    self.refresh_profiles()
                    
                    # Select the new profile
                    for i in range(self.profile_list.count()):
                        item = self.profile_list.item(i)
                        item_profile = item.data(Qt.ItemDataRole.UserRole)
                        if item_profile.id == profile.id:
                            self.profile_list.setCurrentItem(item)
                            break
                    
                    QMessageBox.information(self, "Success", f"Profile '{profile.name}' created successfully.")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create profile:\n{e}")
    
    def edit_profile(self):
        """Edit the selected profile"""
        current_item = self.profile_list.currentItem()
        if not current_item or not self.archive:
            return
        
        try:
            profile = current_item.data(Qt.ItemDataRole.UserRole)
            
            # Get existing profiles for duplicate checking (excluding current one)
            existing_profiles = []
            profile_files = self.archive.get_profiles()
            for profile_file in profile_files:
                from ..models import Profile
                existing_profile = Profile.load_from_file(profile_file)
                if existing_profile.id != profile.id:
                    existing_profiles.append(existing_profile)
            
            # Open profile editor dialog
            dialog = ProfileEditorDialog(profile=profile, existing_profiles=existing_profiles, parent=self)
            if dialog.exec() == ProfileEditorDialog.DialogCode.Accepted:
                updated_profile = dialog.get_profile()
                if updated_profile:
                    # Save updated profile to file
                    profile_file = self.archive.profiles_path / f"{updated_profile.id}.json"
                    updated_profile.save_to_file(profile_file)
                    
                    # Refresh the list
                    self.refresh_profiles()
                    
                    # Select the updated profile
                    for i in range(self.profile_list.count()):
                        item = self.profile_list.item(i)
                        item_profile = item.data(Qt.ItemDataRole.UserRole)
                        if item_profile.id == updated_profile.id:
                            self.profile_list.setCurrentItem(item)
                            break
                    
                    QMessageBox.information(self, "Success", f"Profile '{updated_profile.name}' updated successfully.")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to edit profile:\n{e}")
    
    def delete_profile(self):
        current_item = self.profile_list.currentItem()
        if not current_item:
            return
        
        profile = current_item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Are you sure you want to delete the profile '{profile.name}'?\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                profile_file = self.archive.profiles_path / f"{profile.id}.json"
                profile_file.unlink()
                self.refresh_profiles()
                QMessageBox.information(self, "Success", f"Profile '{profile.name}' deleted.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete profile:\n{e}")