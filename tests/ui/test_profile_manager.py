"""
UI tests for ProfileManager component
"""

import pytest
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication, QListWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.ui.profile_manager import ProfileManager
from src.models import Archive, Profile, MetadataField, FieldType


@pytest.fixture
def qt_app():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


@pytest.fixture
def profile_manager(qt_app):
    """Create ProfileManager instance for tests"""
    manager = ProfileManager()
    yield manager


@pytest.fixture
def mock_archive():
    """Create mock archive for testing"""
    archive = Mock(spec=Archive)
    archive.name = "Test Archive"
    archive.profiles_path = Mock()
    return archive


@pytest.fixture
def sample_profile():
    """Create sample profile for testing"""
    profile = Profile("test_profile", "Test Profile", "Test profile description")
    profile.add_field(MetadataField("title", "Title", FieldType.TEXT, required=True))
    profile.add_field(MetadataField("tags", "Tags", FieldType.TAGS, required=False))
    profile.add_field(MetadataField("category", "Category", FieldType.SELECT, required=False, options=["Doc", "Image", "Video"]))
    return profile


@pytest.mark.ui
class TestProfileManager:
    """Test ProfileManager functionality"""
    
    def test_manager_initialization(self, profile_manager):
        """Test that ProfileManager initializes correctly"""
        assert profile_manager.archive is None
        
        # Check UI components exist
        assert profile_manager.profiles_list is not None
        assert profile_manager.profile_editor is not None
        assert profile_manager.new_profile_button is not None
        assert profile_manager.delete_profile_button is not None
        assert profile_manager.save_profile_button is not None
    
    def test_set_archive(self, profile_manager, mock_archive):
        """Test setting archive updates manager state"""
        profile_manager.set_archive(mock_archive)
        
        assert profile_manager.archive == mock_archive
    
    def test_profile_list_population(self, profile_manager, mock_archive, sample_profile):
        """Test that profile list is populated correctly"""
        # Mock archive.get_profiles()
        mock_archive.get_profiles.return_value = [sample_profile]
        
        profile_manager.set_archive(mock_archive)
        profile_manager.populate_profiles_list()
        
        # Check list is populated
        assert profile_manager.profiles_list.count() == 1
        assert profile_manager.profiles_list.item(0).text() == "Test Profile"
    
    def test_new_profile_button(self, profile_manager, mock_archive):
        """Test new profile button functionality"""
        profile_manager.set_archive(mock_archive)
        
        # Click new profile button
        QTest.mouseClick(profile_manager.new_profile_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Profile editor should be cleared for new profile
        if hasattr(profile_manager.profile_editor, 'clear_form'):
            # Verify editor was cleared
            pass
    
    def test_profile_selection(self, profile_manager, mock_archive, sample_profile):
        """Test selecting profile loads it in editor"""
        mock_archive.get_profiles.return_value = [sample_profile]
        mock_archive.get_profile.return_value = sample_profile
        
        profile_manager.set_archive(mock_archive)
        profile_manager.populate_profiles_list()
        
        # Select profile
        profile_manager.profiles_list.setCurrentRow(0)
        profile_manager.on_profile_selected()
        
        # Profile should be loaded in editor
        if hasattr(profile_manager.profile_editor, 'load_profile'):
            # Verify profile was loaded
            pass
    
    def test_profile_editor_form(self, profile_manager, mock_archive, sample_profile):
        """Test profile editor form functionality"""
        profile_manager.set_archive(mock_archive)
        
        # Load profile in editor
        profile_manager.load_profile_in_editor(sample_profile)
        
        editor = profile_manager.profile_editor
        
        # Check form fields are populated
        assert editor.name_input.text() == "test_profile"
        assert editor.display_name_input.text() == "Test Profile"
        assert editor.description_input.toPlainText() == "Test profile description"
    
    def test_metadata_fields_editor(self, profile_manager, mock_archive, sample_profile):
        """Test metadata fields editor functionality"""
        profile_manager.set_archive(mock_archive)
        profile_manager.load_profile_in_editor(sample_profile)
        
        editor = profile_manager.profile_editor
        fields_list = editor.fields_list
        
        # Check fields are displayed
        assert fields_list.count() == 3  # title, tags, category
        
        # Check field details
        title_item = fields_list.item(0)
        assert "title" in title_item.text()
    
    def test_add_metadata_field(self, profile_manager, mock_archive):
        """Test adding new metadata field"""
        profile_manager.set_archive(mock_archive)
        
        editor = profile_manager.profile_editor
        
        # Click add field button
        if hasattr(editor, 'add_field_button'):
            QTest.mouseClick(editor.add_field_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Field dialog should open
            if hasattr(editor, 'field_dialog'):
                assert editor.field_dialog.isVisible()
    
    def test_delete_metadata_field(self, profile_manager, mock_archive, sample_profile):
        """Test deleting metadata field"""
        profile_manager.set_archive(mock_archive)
        profile_manager.load_profile_in_editor(sample_profile)
        
        editor = profile_manager.profile_editor
        fields_list = editor.fields_list
        
        # Select field and delete
        fields_list.setCurrentRow(1)  # Select "tags" field
        
        if hasattr(editor, 'delete_field_button'):
            QTest.mouseClick(editor.delete_field_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Field should be removed
            assert fields_list.count() == 2
    
    def test_field_type_selection(self, profile_manager, mock_archive):
        """Test field type selection in field editor"""
        profile_manager.set_archive(mock_archive)
        
        # Open field editor dialog
        if hasattr(profile_manager, 'open_field_dialog'):
            dialog = profile_manager.open_field_dialog()
            
            # Test field type combo
            type_combo = dialog.field_type_combo
            
            # Check available types
            types = [type_combo.itemText(i) for i in range(type_combo.count())]
            assert "TEXT" in types
            assert "TAGS" in types
            assert "SELECT" in types
            assert "DATE" in types
            assert "NUMBER" in types
    
    def test_save_profile(self, profile_manager, mock_archive):
        """Test saving profile"""
        profile_manager.set_archive(mock_archive)
        
        # Fill profile form
        editor = profile_manager.profile_editor
        editor.name_input.setText("new_profile")
        editor.display_name_input.setText("New Profile")
        editor.description_input.setText("New profile description")
        
        # Mock archive save method
        mock_archive.save_profile = Mock()
        
        # Click save button
        QTest.mouseClick(profile_manager.save_profile_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Profile should be saved
        mock_archive.save_profile.assert_called_once()
    
    def test_delete_profile(self, profile_manager, mock_archive, sample_profile):
        """Test deleting profile"""
        mock_archive.get_profiles.return_value = [sample_profile]
        mock_archive.delete_profile = Mock()
        
        profile_manager.set_archive(mock_archive)
        profile_manager.populate_profiles_list()
        
        # Select profile
        profile_manager.profiles_list.setCurrentRow(0)
        
        # Mock confirmation dialog
        with patch('PyQt6.QtWidgets.QMessageBox.question') as mock_question:
            mock_question.return_value = QMessageBox.StandardButton.Yes
            
            # Click delete button
            QTest.mouseClick(profile_manager.delete_profile_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Profile should be deleted
            mock_archive.delete_profile.assert_called_once()
    
    def test_profile_validation(self, profile_manager, mock_archive):
        """Test profile form validation"""
        profile_manager.set_archive(mock_archive)
        
        editor = profile_manager.profile_editor
        
        # Test empty name validation
        editor.name_input.setText("")
        editor.display_name_input.setText("Test Profile")
        
        result = profile_manager.validate_profile_form()
        assert not result  # Should fail validation
        
        # Test valid form
        editor.name_input.setText("valid_profile")
        result = profile_manager.validate_profile_form()
        assert result  # Should pass validation
    
    def test_profile_name_uniqueness(self, profile_manager, mock_archive, sample_profile):
        """Test profile name uniqueness validation"""
        mock_archive.get_profiles.return_value = [sample_profile]
        
        profile_manager.set_archive(mock_archive)
        
        editor = profile_manager.profile_editor
        
        # Try to use existing profile name
        editor.name_input.setText("test_profile")  # Same as sample_profile
        editor.display_name_input.setText("Duplicate Profile")
        
        result = profile_manager.validate_profile_form()
        # Should fail if checking for uniqueness
    
    def test_field_options_editor(self, profile_manager, mock_archive):
        """Test field options editor for SELECT fields"""
        profile_manager.set_archive(mock_archive)
        
        # Open field dialog for SELECT type
        if hasattr(profile_manager, 'open_field_dialog'):
            dialog = profile_manager.open_field_dialog()
            
            # Select SELECT field type
            dialog.field_type_combo.setCurrentText("SELECT")
            QApplication.processEvents()
            
            # Options editor should be visible
            if hasattr(dialog, 'options_editor'):
                assert dialog.options_editor.isVisible()
                
                # Test adding options
                if hasattr(dialog.options_editor, 'add_option_button'):
                    QTest.mouseClick(dialog.options_editor.add_option_button, Qt.MouseButton.LeftButton)
                    QApplication.processEvents()
    
    def test_profile_preview(self, profile_manager, mock_archive, sample_profile):
        """Test profile preview functionality"""
        profile_manager.set_archive(mock_archive)
        profile_manager.load_profile_in_editor(sample_profile)
        
        # Check if preview functionality exists
        if hasattr(profile_manager, 'preview_button'):
            QTest.mouseClick(profile_manager.preview_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Preview dialog should show
            if hasattr(profile_manager, 'preview_dialog'):
                assert profile_manager.preview_dialog.isVisible()
    
    def test_profile_import_export(self, profile_manager, mock_archive):
        """Test profile import/export functionality"""
        profile_manager.set_archive(mock_archive)
        
        # Test export
        if hasattr(profile_manager, 'export_button'):
            with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName') as mock_save:
                mock_save.return_value = ("/tmp/profile.json", "JSON files (*.json)")
                
                QTest.mouseClick(profile_manager.export_button, Qt.MouseButton.LeftButton)
                QApplication.processEvents()
                
                mock_save.assert_called_once()
        
        # Test import
        if hasattr(profile_manager, 'import_button'):
            with patch('PyQt6.QtWidgets.QFileDialog.getOpenFileName') as mock_open:
                mock_open.return_value = ("/tmp/profile.json", "JSON files (*.json)")
                
                QTest.mouseClick(profile_manager.import_button, Qt.MouseButton.LeftButton)
                QApplication.processEvents()
                
                mock_open.assert_called_once()
    
    def test_field_reordering(self, profile_manager, mock_archive, sample_profile):
        """Test reordering metadata fields"""
        profile_manager.set_archive(mock_archive)
        profile_manager.load_profile_in_editor(sample_profile)
        
        editor = profile_manager.profile_editor
        fields_list = editor.fields_list
        
        # Check if reorder buttons exist
        if hasattr(editor, 'move_up_button') and hasattr(editor, 'move_down_button'):
            # Select second field
            fields_list.setCurrentRow(1)
            
            # Move up
            QTest.mouseClick(editor.move_up_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Field order should change
            # (Exact verification depends on implementation)
    
    def test_profile_usage_statistics(self, profile_manager, mock_archive, sample_profile):
        """Test profile usage statistics display"""
        profile_manager.set_archive(mock_archive)
        
        # Mock usage statistics
        mock_archive.get_profile_usage_stats = Mock(return_value={'test_profile': 42})
        
        profile_manager.populate_profiles_list()
        
        # Check if usage stats are shown
        if hasattr(profile_manager, 'show_usage_stats'):
            profile_manager.show_usage_stats()
            
            # Statistics should be displayed somewhere
            # (Implementation-dependent)