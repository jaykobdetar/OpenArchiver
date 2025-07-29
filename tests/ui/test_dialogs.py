"""
UI tests for Dialog components - Testing actual functionality
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.ui.dialogs import NewArchiveDialog, OpenArchiveDialog


@pytest.fixture
def qt_app():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


@pytest.fixture
def new_archive_dialog(qt_app):
    """Create NewArchiveDialog instance for tests"""
    dialog = NewArchiveDialog()
    yield dialog
    dialog.close()


@pytest.fixture
def open_archive_dialog(qt_app):
    """Create OpenArchiveDialog instance for tests"""
    dialog = OpenArchiveDialog()
    yield dialog
    dialog.close()


@pytest.mark.ui
class TestNewArchiveDialog:
    """Test NewArchiveDialog functionality based on actual implementation"""
    
    def test_dialog_initialization(self, new_archive_dialog):
        """Test that NewArchiveDialog initializes with correct title and components"""
        assert new_archive_dialog.windowTitle() == "Create New Archive"
        
        # Check actual UI components exist (based on real implementation)
        assert hasattr(new_archive_dialog, 'path_edit')
        assert hasattr(new_archive_dialog, 'name_edit')
        assert hasattr(new_archive_dialog, 'description_edit')
        
        # Check placeholder texts are set
        assert "location" in new_archive_dialog.path_edit.placeholderText().lower()
        assert "name" in new_archive_dialog.name_edit.placeholderText().lower()
    
    def test_form_validation_empty_fields(self, new_archive_dialog):
        """Test form validation prevents OK button when fields are empty"""
        # Initially, OK button should be disabled (empty fields)
        button_box = new_archive_dialog.findChild(QDialogButtonBox)
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        
        # With empty fields, OK should be disabled
        assert not ok_button.isEnabled()
    
    def test_form_validation_enables_button(self, new_archive_dialog):
        """Test form validation enables OK button when valid data is entered"""
        # Fill required fields
        new_archive_dialog.path_edit.setText("/tmp")
        new_archive_dialog.name_edit.setText("test_archive")
        
        # Trigger validation
        new_archive_dialog.validate_input()
        
        # OK button should now be enabled
        button_box = new_archive_dialog.findChild(QDialogButtonBox)
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button.isEnabled()
    
    def test_browse_button_functionality(self, new_archive_dialog):
        """Test browse button opens directory dialog and sets path"""
        with patch('PyQt6.QtWidgets.QFileDialog.getExistingDirectory') as mock_dialog:
            mock_dialog.return_value = "/selected/path"
            
            # Trigger browse
            new_archive_dialog.browse_path()
            
            # Verify dialog was called and path was set
            mock_dialog.assert_called_once()
            assert new_archive_dialog.path_edit.text() == "/selected/path"
    
    def test_get_values_returns_correct_data(self, new_archive_dialog):
        """Test get_values returns properly formatted archive information"""
        # Set test data
        new_archive_dialog.path_edit.setText("/test/path")
        new_archive_dialog.name_edit.setText("My Archive")
        new_archive_dialog.description_edit.setPlainText("Test description")
        
        # Get values
        archive_path, name, description = new_archive_dialog.get_values()
        
        # Verify correct formatting
        assert archive_path == Path("/test/path/My Archive")
        assert name == "My Archive"
        assert description == "Test description"
    
    def test_accept_with_existing_directory_warning(self, new_archive_dialog):
        """Test that accept() shows warning for existing directories"""
        # Set up existing directory scenario
        new_archive_dialog.path_edit.setText("/tmp")
        new_archive_dialog.name_edit.setText("existing_dir")
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('PyQt6.QtWidgets.QMessageBox.question') as mock_question:
            
            mock_question.return_value = QMessageBox.StandardButton.No
            
            # Call accept
            new_archive_dialog.accept()
            
            # Should show confirmation dialog
            mock_question.assert_called_once()
            assert "already exists" in mock_question.call_args[0][1]


@pytest.mark.ui
class TestOpenArchiveDialog:
    """Test OpenArchiveDialog functionality based on actual implementation"""
    
    def test_dialog_initialization(self, open_archive_dialog):
        """Test that OpenArchiveDialog initializes correctly"""
        assert open_archive_dialog.windowTitle() == "Open Archive"
        
        # Check actual UI components exist
        assert hasattr(open_archive_dialog, 'path_edit')
        
        # Check description label exists
        assert open_archive_dialog.findChild(QLabel) is not None
    
    def test_browse_for_archive(self, open_archive_dialog):
        """Test browsing for archive directory"""
        with patch('PyQt6.QtWidgets.QFileDialog.getExistingDirectory') as mock_dialog:
            mock_dialog.return_value = "/test/archive"
            
            # Trigger browse
            open_archive_dialog.browse_path()
            
            # Verify dialog was called and path was set
            mock_dialog.assert_called_once()
            assert open_archive_dialog.path_edit.text() == "/test/archive"
    
    def test_path_validation_invalid_path(self, open_archive_dialog):
        """Test archive path validation with invalid path"""
        # Set invalid path (no archive.json)
        open_archive_dialog.path_edit.setText("/invalid/path")
        
        with patch('pathlib.Path.exists', return_value=False):
            open_archive_dialog.validate_input()
            
            # OK button should be disabled
            button_box = open_archive_dialog.findChild(QDialogButtonBox)
            ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
            assert not ok_button.isEnabled()
    
    def test_path_validation_valid_archive(self, open_archive_dialog, tmp_path):
        """Test archive path validation with valid archive"""
        # Create test archive directory with archive.json
        archive_dir = tmp_path / "test_archive"
        archive_dir.mkdir()
        (archive_dir / "archive.json").write_text('{"name": "Test"}')
        
        # Set valid path
        open_archive_dialog.path_edit.setText(str(archive_dir))
        
        # Validation should pass
        open_archive_dialog.validate_input()
        
        # OK button should be enabled
        button_box = open_archive_dialog.findChild(QDialogButtonBox)
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button.isEnabled()
    
    def test_get_path_returns_correct_path(self, open_archive_dialog):
        """Test get_path returns correct Path object"""
        test_path = "/test/archive"
        open_archive_dialog.path_edit.setText(test_path)
        
        result = open_archive_dialog.get_path()
        assert result == Path(test_path)
    
    def test_validation_triggers_on_text_change(self, open_archive_dialog):
        """Test that validation is triggered when path text changes"""
        # Mock the validate_input method to verify it's called
        with patch.object(open_archive_dialog, 'validate_input') as mock_validate:
            # Change text should trigger validation
            open_archive_dialog.path_edit.setText("/some/path")
            
            # Validation should be called due to textChanged signal
            mock_validate.assert_called()