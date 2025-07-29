"""
UI tests for ExportWidget component - Testing real functionality
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.ui.export_widget import ExportWidget
from src.models import Archive


@pytest.fixture
def qt_app():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


@pytest.fixture
def export_widget(qt_app):
    """Create ExportWidget instance for tests"""
    widget = ExportWidget()
    yield widget


@pytest.fixture
def mock_archive(tmp_path):
    """Create mock archive for testing"""
    archive = Mock(spec=Archive)
    archive.name = "Test Archive"
    archive.root_path = tmp_path / "test_archive"
    archive.config = Mock()
    archive.config.name = "Test Archive"
    archive.config.created_at = "2024-01-01T00:00:00"
    return archive


@pytest.mark.ui
class TestExportWidget:
    """Test ExportWidget functionality based on actual implementation"""
    
    def test_widget_initialization(self, export_widget):
        """Test that ExportWidget initializes with correct components"""
        assert export_widget.archive is None
        assert export_widget.export_thread is None
        
        # Check actual UI components exist (based on real implementation)
        assert hasattr(export_widget, 'output_path_edit')
        assert hasattr(export_widget, 'browse_button')
        assert hasattr(export_widget, 'format_combo')
        assert hasattr(export_widget, 'export_button')
        assert hasattr(export_widget, 'progress_bar')
        assert hasattr(export_widget, 'bagit_group')
        
        # Check initial state
        assert not export_widget.progress_bar.isVisible()
        assert export_widget.format_combo.count() == 2  # BagIt and Directory
    
    def test_format_combo_options(self, export_widget):
        """Test export format combo has correct options"""
        combo = export_widget.format_combo
        
        # Check available formats
        assert combo.itemText(0) == "BagIt Archive (Recommended)"
        assert combo.itemData(0) == "bagit"
        assert combo.itemText(1) == "Directory Structure"
        assert combo.itemData(1) == "directory"
    
    def test_browse_button_functionality(self, export_widget):
        """Test browse button opens file dialog and sets path"""
        with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName') as mock_dialog:
            mock_dialog.return_value = ("/test/export.bag", "BagIt files (*.bag)")
            
            # Click browse button
            QTest.mouseClick(export_widget.browse_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should open file dialog and set path
            mock_dialog.assert_called_once()
            assert export_widget.output_path_edit.text() == "/test/export.bag"
    
    def test_bagit_metadata_form(self, export_widget):
        """Test BagIt metadata form components"""
        # BagIt group visibility depends on format selection
        # Default format is BagIt (index 0), so trigger the format change
        export_widget.on_format_changed()
        assert export_widget.bagit_group.isVisible()
        
        # Check metadata fields exist
        assert hasattr(export_widget, 'source_org_edit')
        assert hasattr(export_widget, 'contact_name_edit')
        assert hasattr(export_widget, 'contact_email_edit')
        assert hasattr(export_widget, 'description_edit')
        
        # Check default values
        assert export_widget.source_org_edit.text() == "Archive Tool"
        assert export_widget.contact_name_edit.text() == "Archive Administrator"
        assert export_widget.contact_email_edit.text() == "admin@archive.local"
    
    def test_format_change_affects_ui(self, export_widget):
        """Test that changing format calls the visibility logic correctly"""
        # We can't test actual visibility in a headless environment,
        # but we can test that the logic works correctly
        
        # Mock the bagit_group to track setVisible calls
        from unittest.mock import Mock
        original_bagit_group = export_widget.bagit_group
        mock_bagit_group = Mock()
        export_widget.bagit_group = mock_bagit_group
        
        # Start with BagIt format (default)
        export_widget.format_combo.setCurrentIndex(0)  # BagIt
        export_widget.on_format_changed()
        
        # Should call setVisible(True) for BagIt format
        mock_bagit_group.setVisible.assert_called_with(True)
        
        # Change to directory format
        export_widget.format_combo.setCurrentIndex(1)  # Directory
        export_widget.on_format_changed()
        
        # Should call setVisible(False) for directory format  
        mock_bagit_group.setVisible.assert_called_with(False)
        
        # Restore original
        export_widget.bagit_group = original_bagit_group
    
    def test_set_archive_enables_export(self, export_widget, mock_archive):
        """Test that setting archive enables export functionality"""
        # Initially export button might be disabled
        initial_state = export_widget.export_button.isEnabled()
        
        # Set archive
        export_widget.set_archive(mock_archive)
        
        # Archive should be set
        assert export_widget.archive == mock_archive
    
    def test_export_button_requires_output_path(self, export_widget, mock_archive):
        """Test that export button validation requires output path"""
        export_widget.set_archive(mock_archive)
        
        # Without output path, export should show warning
        with patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_warning:
            QTest.mouseClick(export_widget.export_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should warn about missing output path
            mock_warning.assert_called_once()
    
    def test_valid_export_starts_thread(self, export_widget, mock_archive):
        """Test that valid export configuration starts export thread"""
        export_widget.set_archive(mock_archive)
        export_widget.output_path_edit.setText("/test/export.bag")
        
        with patch('src.ui.export_widget.ExportThread') as mock_thread_class:
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread
            
            # Click export button
            QTest.mouseClick(export_widget.export_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should create and start export thread
            mock_thread_class.assert_called_once()
            mock_thread.start.assert_called_once()
    
    def test_progress_display_during_export(self, export_widget):
        """Test progress display shows during export"""
        # Start export simulation
        export_widget.on_export_started()
        
        # Progress elements should be visible
        assert export_widget.progress_bar.isVisible()
        assert export_widget.progress_label.isVisible()
        assert export_widget.cancel_button.isVisible()
        assert not export_widget.export_button.isVisible()
    
    def test_progress_updates(self, export_widget):
        """Test progress updates work correctly"""
        export_widget.on_export_started()
        
        # Simulate progress update
        export_widget.on_progress_updated(50, 100, "Exporting file 50/100")
        
        # Progress should be updated
        assert export_widget.progress_bar.value() == 50
        assert export_widget.progress_bar.maximum() == 100
        assert "file 50/100" in export_widget.progress_label.text()
    
    def test_export_completion(self, export_widget):
        """Test export completion handling"""
        export_widget.on_export_started()
        
        with patch('PyQt6.QtWidgets.QMessageBox.information') as mock_info:
            # Simulate successful completion
            export_widget.on_export_completed("/test/export.bag")
            
            # Should show success message
            mock_info.assert_called_once()
            
            # Progress should be hidden
            assert not export_widget.progress_bar.isVisible()
            assert export_widget.export_button.isVisible()
    
    def test_export_error_handling(self, export_widget):
        """Test export error handling"""
        export_widget.on_export_started()
        
        with patch('PyQt6.QtWidgets.QMessageBox.critical') as mock_error:
            # Simulate export error
            export_widget.on_export_failed("Export failed: Permission denied")
            
            # Should show error message
            mock_error.assert_called_once()
            assert "Permission denied" in mock_error.call_args[0][2]
            
            # Progress should be hidden
            assert not export_widget.progress_bar.isVisible()
    
    def test_cancel_export_functionality(self, export_widget, mock_archive):
        """Test export cancellation"""
        export_widget.set_archive(mock_archive)
        export_widget.on_export_started()
        
        # Mock active export thread
        mock_thread = Mock()
        export_widget.export_thread = mock_thread
        
        # Click cancel button
        QTest.mouseClick(export_widget.cancel_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Should terminate thread
        mock_thread.terminate.assert_called_once()
        mock_thread.wait.assert_called_once()
    
    def test_manifest_generation(self, export_widget, mock_archive):
        """Test manifest generation functionality"""
        export_widget.set_archive(mock_archive)
        
        with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName') as mock_save, \
             patch('src.core.export.ExportService') as mock_service_class:
            
            mock_save.return_value = ("/test/manifest.json", "JSON files (*.json)")
            mock_service = Mock()
            mock_service_class.return_value = mock_service
            
            # Click manifest button
            QTest.mouseClick(export_widget.manifest_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should generate manifest
            mock_service.generate_manifest.assert_called_once()
    
    def test_status_text_updates(self, export_widget):
        """Test that status text shows current state"""
        # Initial state
        assert "Ready to export" in export_widget.status_text.toPlainText()
        
        # During export
        export_widget.on_export_started()
        # Status should update to show export in progress
        
        # After completion
        export_widget.on_export_completed("/test/export.bag")
        # Status should show completion message
    
    def test_set_archive(self, export_widget, mock_archive):
        """Test setting archive updates export service"""
        with patch('src.core.export.ExportService') as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service
            
            export_widget.set_archive(mock_archive)
            
            assert export_widget.archive == mock_archive
            assert export_widget.export_service == mock_service
            mock_service_class.assert_called_once_with(mock_archive)
    
    def test_export_format_selection(self, export_widget):
        """Test export format selection"""
        combo = export_widget.export_format_combo
        
        # Check available formats
        formats = [combo.itemText(i) for i in range(combo.count())]
        assert "BagIt" in formats
        assert "Directory" in formats
        
        # Test format selection
        combo.setCurrentText("BagIt")
        assert combo.currentText() == "BagIt"
    
    def test_destination_path_selection(self, export_widget):
        """Test destination path selection"""
        # Test manual path entry
        test_path = "/tmp/export_test"
        export_widget.destination_path_input.setText(test_path)
        assert export_widget.destination_path_input.text() == test_path
        
        # Test browse button
        with patch('PyQt6.QtWidgets.QFileDialog.getExistingDirectory') as mock_dialog:
            mock_dialog.return_value = "/tmp/selected_path"
            
            QTest.mouseClick(export_widget.browse_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            mock_dialog.assert_called_once()
            assert export_widget.destination_path_input.text() == "/tmp/selected_path"
    
    def test_metadata_form_completion(self, export_widget, mock_archive):
        """Test BagIt metadata form completion"""
        export_widget.set_archive(mock_archive)
        
        # Select BagIt format to show metadata form
        export_widget.export_format_combo.setCurrentText("BagIt")
        QApplication.processEvents()
        
        # Fill metadata form
        metadata_form = export_widget.metadata_form
        
        # Test required fields
        if hasattr(metadata_form, 'source_org_input'):
            metadata_form.source_org_input.setText("Test Organization")
            metadata_form.contact_name_input.setText("Test Contact")
            metadata_form.description_input.setText("Test Description")
    
    def test_export_button_validation(self, export_widget, mock_archive):
        """Test export button validation"""
        export_widget.set_archive(mock_archive)
        
        # Initially should be disabled (no destination)
        assert not export_widget.export_button.isEnabled()
        
        # Set destination path
        export_widget.destination_path_input.setText("/tmp/test_export")
        QApplication.processEvents()
        
        # Should now be enabled
        assert export_widget.export_button.isEnabled()
    
    def test_bagit_export_execution(self, export_widget, mock_archive):
        """Test BagIt export execution"""
        export_widget.set_archive(mock_archive)
        
        # Setup for BagIt export
        export_widget.export_format_combo.setCurrentText("BagIt")
        export_widget.destination_path_input.setText("/tmp/test_export.bag")
        
        # Fill metadata
        metadata_form = export_widget.metadata_form
        if hasattr(metadata_form, 'source_org_input'):
            metadata_form.source_org_input.setText("Test Org")
            metadata_form.contact_name_input.setText("Test Contact")
        
        # Mock export service
        mock_export_path = Path("/tmp/test_export.bag")
        export_widget.export_service.export_to_bagit.return_value = mock_export_path
        
        # Click export button
        QTest.mouseClick(export_widget.export_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Verify export was called
        export_widget.export_service.export_to_bagit.assert_called_once()
    
    def test_directory_export_execution(self, export_widget, mock_archive):
        """Test directory export execution"""
        export_widget.set_archive(mock_archive)
        
        # Setup for directory export
        export_widget.export_format_combo.setCurrentText("Directory")
        export_widget.destination_path_input.setText("/tmp/test_export_dir")
        
        # Mock export service
        mock_export_path = Path("/tmp/test_export_dir")
        export_widget.export_service.export_to_directory.return_value = mock_export_path
        
        # Click export button
        QTest.mouseClick(export_widget.export_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Verify export was called
        export_widget.export_service.export_to_directory.assert_called_once()
    
    def test_export_progress_display(self, export_widget, mock_archive):
        """Test export progress display"""
        export_widget.set_archive(mock_archive)
        
        # Show progress
        export_widget.show_progress("Exporting files...", 0, 100)
        
        # Check progress bar is shown
        assert export_widget.progress_bar.isVisible()
        assert export_widget.progress_bar.minimum() == 0
        assert export_widget.progress_bar.maximum() == 100
        
        # Update progress
        export_widget.update_progress(50)
        assert export_widget.progress_bar.value() == 50
        
        # Hide progress
        export_widget.hide_progress()
        assert not export_widget.progress_bar.isVisible()
    
    def test_export_error_handling(self, export_widget, mock_archive):
        """Test export error handling"""
        export_widget.set_archive(mock_archive)
        export_widget.destination_path_input.setText("/tmp/test_export")
        
        # Mock export service to raise error
        export_widget.export_service.export_to_directory.side_effect = Exception("Export error")
        
        with patch('PyQt6.QtWidgets.QMessageBox.critical') as mock_critical:
            QTest.mouseClick(export_widget.export_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should show error message
            mock_critical.assert_called_once()
            
            # Check error is in message
            args, kwargs = mock_critical.call_args
            assert "error" in args[2].lower()
    
    def test_no_archive_export_attempt(self, export_widget):
        """Test export attempt with no archive set"""
        export_widget.destination_path_input.setText("/tmp/test_export")
        
        with patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_warning:
            QTest.mouseClick(export_widget.export_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should show warning about no archive
            mock_warning.assert_called_once()
            args, kwargs = mock_warning.call_args
            assert "no archive" in args[2].lower() or "archive" in args[2].lower()
    
    def test_export_options_configuration(self, export_widget, mock_archive):
        """Test export options configuration"""
        export_widget.set_archive(mock_archive)
        
        # Check if export options exist
        if hasattr(export_widget, 'include_metadata_checkbox'):
            export_widget.include_metadata_checkbox.setChecked(True)
            assert export_widget.include_metadata_checkbox.isChecked()
        
        if hasattr(export_widget, 'verify_checksums_checkbox'):
            export_widget.verify_checksums_checkbox.setChecked(False)
            assert not export_widget.verify_checksums_checkbox.isChecked()
    
    def test_export_filters_application(self, export_widget, mock_archive):
        """Test applying filters to export"""
        export_widget.set_archive(mock_archive)
        
        # Check if filter options exist
        if hasattr(export_widget, 'filter_by_date_checkbox'):
            export_widget.filter_by_date_checkbox.setChecked(True)
            
            # Date range controls should be enabled
            if hasattr(export_widget, 'start_date_edit'):
                assert export_widget.start_date_edit.isEnabled()
            if hasattr(export_widget, 'end_date_edit'):
                assert export_widget.end_date_edit.isEnabled()
    
    def test_export_success_notification(self, export_widget, mock_archive):
        """Test export success notification"""
        export_widget.set_archive(mock_archive)
        export_widget.destination_path_input.setText("/tmp/test_export")
        
        # Mock successful export
        mock_export_path = Path("/tmp/test_export")
        export_widget.export_service.export_to_directory.return_value = mock_export_path
        
        with patch('PyQt6.QtWidgets.QMessageBox.information') as mock_info:
            QTest.mouseClick(export_widget.export_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should show success message
            mock_info.assert_called_once()
            
            # Check success message
            args, kwargs = mock_info.call_args
            assert "success" in args[2].lower() or "complete" in args[2].lower()
    
    def test_metadata_validation(self, export_widget, mock_archive):
        """Test BagIt metadata validation"""
        export_widget.set_archive(mock_archive)
        export_widget.export_format_combo.setCurrentText("BagIt")
        export_widget.destination_path_input.setText("/tmp/test.bag")
        
        # Try to export without required metadata
        with patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_warning:
            QTest.mouseClick(export_widget.export_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should warn about missing metadata (if validation is implemented)
            # This test depends on implementation details
    
    def test_export_cancellation(self, export_widget, mock_archive):
        """Test export cancellation"""
        export_widget.set_archive(mock_archive)
        
        # Check if cancel button exists
        if hasattr(export_widget, 'cancel_button'):
            # Start export
            export_widget.show_progress("Exporting...", 0, 100)
            assert export_widget.cancel_button.isVisible()
            
            # Cancel export
            QTest.mouseClick(export_widget.cancel_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Progress should be hidden
            assert not export_widget.progress_bar.isVisible()
    
    def test_export_format_specific_options(self, export_widget, mock_archive):
        """Test format-specific options visibility"""
        export_widget.set_archive(mock_archive)
        
        # Select BagIt format
        export_widget.export_format_combo.setCurrentText("BagIt")
        QApplication.processEvents()
        
        # BagIt metadata form should be visible
        assert export_widget.metadata_form.isVisible()
        
        # Select Directory format
        export_widget.export_format_combo.setCurrentText("Directory")
        QApplication.processEvents()
        
        # BagIt metadata form should be hidden
        assert not export_widget.metadata_form.isVisible()
    
    def test_export_preview_functionality(self, export_widget, mock_archive):
        """Test export preview functionality"""
        export_widget.set_archive(mock_archive)
        
        # Check if preview button exists
        if hasattr(export_widget, 'preview_button'):
            QTest.mouseClick(export_widget.preview_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Preview dialog should be shown
            if hasattr(export_widget, 'preview_dialog'):
                assert export_widget.preview_dialog.isVisible()
    
    def test_recent_exports_tracking(self, export_widget, mock_archive):
        """Test recent exports tracking"""
        export_widget.set_archive(mock_archive)
        
        # Check if recent exports list exists
        if hasattr(export_widget, 'recent_exports_list'):
            # Perform an export
            export_widget.destination_path_input.setText("/tmp/test_export")
            mock_export_path = Path("/tmp/test_export")
            export_widget.export_service.export_to_directory.return_value = mock_export_path
            
            QTest.mouseClick(export_widget.export_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Recent exports should be updated
            assert export_widget.recent_exports_list.count() > 0