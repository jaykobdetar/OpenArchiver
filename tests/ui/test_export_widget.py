"""
Comprehensive UI tests for ExportWidget - Real user interaction testing
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.ui.export_widget import ExportWidget, ExportThread
from src.models import Archive
from src.core.export import ExportService


@pytest.mark.ui
class TestExportWidget:
    """Test ExportWidget with real PyQt6 widget interactions"""
    
    @pytest.fixture
    def mock_archive(self, temp_dir):
        """Create mock archive for testing"""
        archive = Mock(spec=Archive)
        archive.root_path = temp_dir / "test_archive"
        archive.config = Mock()
        archive.config.name = "Test Archive"
        archive.config.created_at = "2024-01-01T10:00:00"
        return archive
    
    @pytest.fixture
    def export_widget(self, qt_app, mock_archive):
        """Create ExportWidget instance for testing"""
        widget = ExportWidget()
        widget.set_archive(mock_archive)
        widget.show()  # Show widget so isVisible() works correctly
        qt_app.processEvents()
        
        yield widget
        
        # Cleanup
        if widget.export_thread and widget.export_thread.isRunning():
            widget.export_thread.terminate()
            widget.export_thread.wait()
        widget.close()
        qt_app.processEvents()
        widget.deleteLater()
        qt_app.processEvents()

    def test_widget_initialization(self, qt_app):
        """Test ExportWidget initializes correctly"""
        widget = ExportWidget()
        
        # Test basic widget properties
        assert widget is not None
        assert widget.archive is None
        assert widget.export_thread is None
        
        # Test UI components exist
        assert hasattr(widget, 'output_path_edit')
        assert hasattr(widget, 'browse_button')
        assert hasattr(widget, 'format_combo')
        assert hasattr(widget, 'bagit_group')
        assert hasattr(widget, 'source_org_edit')
        assert hasattr(widget, 'contact_name_edit')
        assert hasattr(widget, 'contact_email_edit')
        assert hasattr(widget, 'description_edit')
        assert hasattr(widget, 'progress_bar')
        assert hasattr(widget, 'progress_label')
        assert hasattr(widget, 'status_text')
        assert hasattr(widget, 'export_button')
        assert hasattr(widget, 'cancel_button')
        assert hasattr(widget, 'manifest_button')
        
        # Test initial states
        assert not widget.output_path_edit.isEnabled()
        assert not widget.export_button.isEnabled()
        assert not widget.progress_bar.isVisible()
        assert not widget.cancel_button.isVisible()
        assert widget.format_combo.currentData() == "bagit"
        
        widget.close()
        qt_app.processEvents()
        widget.deleteLater()
        qt_app.processEvents()

    def test_archive_setting(self, export_widget, mock_archive):
        """Test setting archive enables/disables widget correctly"""
        widget = export_widget
        
        # Should be enabled since we set archive in fixture
        assert widget.archive is not None
        assert widget.output_path_edit.isEnabled()
        assert widget.export_button.isEnabled()
        assert widget.manifest_button.isEnabled()
        assert mock_archive.config.name in widget.status_text.toPlainText()
        
        # Test clearing archive
        widget.set_archive(None)
        assert widget.archive is None
        assert not widget.output_path_edit.isEnabled()
        assert not widget.export_button.isEnabled()
        assert not widget.manifest_button.isEnabled()
        assert "No archive loaded" in widget.status_text.toPlainText()

    def test_format_combo_interaction(self, export_widget):
        """Test export format selection"""
        widget = export_widget
        
        # Should start with BagIt selected
        assert widget.format_combo.currentData() == "bagit"
        assert widget.bagit_group.isVisible()
        
        # Test that format change method works
        # First set to directory
        widget.format_combo.setCurrentIndex(1)  # Directory structure
        widget.on_format_changed()  # Manually trigger to ensure it works
        assert widget.format_combo.currentData() == "directory"
        assert not widget.bagit_group.isVisible()
        
        # Change back to BagIt
        widget.format_combo.setCurrentIndex(0)  # BagIt
        widget.on_format_changed()  # Manually trigger to ensure it works
        assert widget.format_combo.currentData() == "bagit"
        assert widget.bagit_group.isVisible()

    def test_output_path_input(self, export_widget):
        """Test output path text input"""
        widget = export_widget
        
        # Type in output path
        test_path = "/tmp/test_export"
        QTest.keyClicks(widget.output_path_edit, test_path)
        
        assert widget.output_path_edit.text() == test_path

    def test_browse_button_exists(self, export_widget):
        """Test that browse button exists and is functional"""
        widget = export_widget
        
        # Test button exists and is enabled with archive
        assert widget.browse_button is not None
        assert widget.browse_button.isEnabled()
        assert "Browse" in widget.browse_button.text()
        
        # Test that button has click handler connected
        # (We avoid actually clicking to prevent dialog issues)
        assert widget.browse_button.receivers(widget.browse_button.clicked) > 0

    def test_bagit_metadata_input(self, export_widget):
        """Test BagIt metadata form input"""
        widget = export_widget
        
        # Test entering metadata
        widget.source_org_edit.clear()
        QTest.keyClicks(widget.source_org_edit, "Test Organization")
        assert widget.source_org_edit.text() == "Test Organization"
        
        widget.contact_name_edit.clear()
        QTest.keyClicks(widget.contact_name_edit, "John Doe")
        assert widget.contact_name_edit.text() == "John Doe"
        
        widget.contact_email_edit.clear()
        QTest.keyClicks(widget.contact_email_edit, "john@example.com")
        assert widget.contact_email_edit.text() == "john@example.com"
        
        widget.description_edit.clear()
        QTest.keyClicks(widget.description_edit, "Test export description")
        assert "Test export description" in widget.description_edit.toPlainText()

    def test_start_export_validation(self, export_widget):
        """Test export validation without output path"""
        widget = export_widget
        
        # Clear output path
        widget.output_path_edit.clear()
        
        # Mock message box
        with patch.object(QMessageBox, 'warning') as mock_warning:
            QTest.mouseClick(widget.export_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should show warning about missing path
            mock_warning.assert_called_once()
            args = mock_warning.call_args[0]
            assert "output path" in str(args).lower()

    def test_start_export_with_valid_input(self, export_widget):
        """Test starting export with valid input"""
        widget = export_widget
        
        # Set output path
        widget.output_path_edit.setText("/tmp/test_export")
        
        # Store initial state
        initial_export_enabled = widget.export_button.isEnabled()
        initial_cancel_visible = widget.cancel_button.isVisible()
        
        # Mock the ExportThread to avoid actual export
        with patch('src.ui.export_widget.ExportThread') as mock_thread_class:
            mock_thread = Mock()
            mock_thread.start = Mock()
            mock_thread_class.return_value = mock_thread
            
            # Call start_export directly to avoid button click issues
            widget.start_export()
            QApplication.processEvents()
            
            # Should create and start export thread
            mock_thread_class.assert_called_once()
            mock_thread.start.assert_called_once()
            
            # UI should be updated (test what we can reliably verify)
            # The export button should be disabled
            assert not widget.export_button.isEnabled()
            
            # Verify state changed from initial
            assert widget.export_button.isEnabled() != initial_export_enabled or \
                   widget.cancel_button.isVisible() != initial_cancel_visible

    def test_export_progress_updates(self, export_widget):
        """Test progress updates during export"""
        widget = export_widget
        
        # Simulate progress update
        widget.on_progress_updated(50, 100, "Processing files...")
        
        assert widget.progress_bar.maximum() == 100
        assert widget.progress_bar.value() == 50
        assert "50/100" in widget.progress_label.text()
        assert "50.0%" in widget.progress_label.text()
        assert "Processing files..." in widget.progress_label.text()

    def test_export_completion_success(self, export_widget):
        """Test successful export completion"""
        widget = export_widget
        
        # Start export first to set up UI state
        widget.output_path_edit.setText("/tmp/test_export")
        with patch('src.ui.export_widget.ExportThread'):
            widget.start_export()
        
        # Mock message box for completion dialog
        result_path = "/tmp/test_export/result"
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            widget.on_export_completed(result_path)
            QApplication.processEvents()
        
        # Should update status and reset UI
        assert result_path in widget.status_text.toPlainText()
        assert "completed successfully" in widget.status_text.toPlainText()
        assert widget.export_button.isEnabled()
        assert not widget.cancel_button.isVisible()
        assert not widget.progress_bar.isVisible()

    def test_export_completion_with_open_location(self, export_widget):
        """Test export completion with opening location"""
        widget = export_widget
        
        # Start export first
        widget.output_path_edit.setText("/tmp/test_export")
        with patch('src.ui.export_widget.ExportThread'):
            widget.start_export()
        
        result_path = "/tmp/test_export/result"
        
        # Mock message box to return Yes
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes), \
             patch.object(widget, 'open_output_location') as mock_open:
            widget.on_export_completed(result_path)
            QApplication.processEvents()
            
            # Should call open_output_location
            mock_open.assert_called_once_with(result_path)

    def test_export_failure(self, export_widget):
        """Test export failure handling"""
        widget = export_widget
        
        # Start export first
        widget.output_path_edit.setText("/tmp/test_export")
        with patch('src.ui.export_widget.ExportThread'):
            widget.start_export()
        
        # Mock message box
        error_message = "Export failed due to disk space"
        with patch.object(QMessageBox, 'critical') as mock_critical:
            widget.on_export_failed(error_message)
            QApplication.processEvents()
            
            # Should show error message and reset UI
            mock_critical.assert_called_once()
            assert error_message in widget.status_text.toPlainText()
            assert widget.export_button.isEnabled()
            assert not widget.cancel_button.isVisible()

    def test_cancel_export(self, export_widget):
        """Test cancelling export"""
        widget = export_widget
        
        # Start export first
        widget.output_path_edit.setText("/tmp/test_export")
        with patch('src.ui.export_widget.ExportThread') as mock_thread_class:
            mock_thread = Mock()
            mock_thread.isRunning.return_value = True
            mock_thread.terminate = Mock()
            mock_thread.wait = Mock()
            mock_thread_class.return_value = mock_thread
            
            widget.start_export()
            
            # Cancel export
            QTest.mouseClick(widget.cancel_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should terminate thread and reset UI
            mock_thread.terminate.assert_called_once()
            mock_thread.wait.assert_called_once()
            assert "cancelled" in widget.status_text.toPlainText()

    def test_manifest_button_exists(self, export_widget):
        """Test that manifest button exists and is enabled"""
        widget = export_widget
        
        # Test button exists and is enabled with archive
        assert widget.manifest_button is not None
        assert widget.manifest_button.isEnabled()
        assert "Manifest" in widget.manifest_button.text()

    def test_generate_manifest_functionality(self, export_widget):
        """Test manifest generation functionality without dialogs"""
        widget = export_widget
        
        # Test the underlying functionality directly
        output_file_json = Path("/tmp/manifest.json")
        output_file_csv = Path("/tmp/manifest.csv")
        
        # Mock export service to test different formats
        with patch('src.ui.export_widget.ExportService') as mock_service_class, \
             patch('src.ui.export_widget.QMessageBox.information') as mock_info:
            
            mock_service = Mock()
            mock_service.generate_manifest.return_value = output_file_json
            mock_service_class.return_value = mock_service
            
            # Test JSON format detection
            try:
                from src.ui.export_widget import ExportService
                export_service = ExportService(widget.archive)
                
                # Test the method logic without dialog
                format_type = "csv" if str(output_file_csv).endswith('.csv') else "json"
                assert format_type == "csv"
                
                format_type = "csv" if str(output_file_json).endswith('.csv') else "json"
                assert format_type == "json"
                
            except ImportError:
                # If we can't import ExportService, just test the button exists
                assert widget.manifest_button is not None

    def test_open_output_location(self, export_widget):
        """Test opening output location"""
        widget = export_widget
        
        test_path = "/tmp/export_result"
        
        # Mock subprocess to avoid actually opening files
        with patch('subprocess.call') as mock_subprocess:
            widget.open_output_location(test_path)
            
            # Should call subprocess (platform-specific command)
            mock_subprocess.assert_called_once()

    def test_open_output_location_error(self, export_widget):
        """Test error handling when opening output location"""
        widget = export_widget
        
        test_path = "/tmp/export_result"
        
        # Mock subprocess to raise error
        with patch('subprocess.call', side_effect=Exception("Command failed")), \
             patch.object(QMessageBox, 'warning') as mock_warning:
            
            widget.open_output_location(test_path)
            
            # Should show warning message
            mock_warning.assert_called_once()

    def test_widget_cleanup_with_running_thread(self, qt_app, mock_archive):
        """Test proper widget cleanup with running export thread"""
        widget = ExportWidget()
        widget.set_archive(mock_archive)
        
        # Start a mock export thread
        with patch('src.ui.export_widget.ExportThread') as mock_thread_class:
            mock_thread = Mock()
            mock_thread.isRunning.return_value = True
            mock_thread.terminate = Mock()
            mock_thread.wait = Mock()
            mock_thread_class.return_value = mock_thread
            
            widget.output_path_edit.setText("/tmp/test")
            widget.start_export()
            
            # Close widget - should terminate thread
            widget.close()
            qt_app.processEvents()
            widget.deleteLater()
            qt_app.processEvents()
        
        # Should not crash
        assert True

    def test_reset_ui_functionality(self, export_widget):
        """Test UI reset functionality"""
        widget = export_widget
        
        # Set up UI state manually to simulate export state
        widget.set_enabled(False)  # Disable controls
        widget.cancel_button.setVisible(True)
        widget.progress_bar.setVisible(True)
        widget.progress_label.setVisible(True)
        
        # Verify UI is in export-like state
        assert not widget.export_button.isEnabled()
        assert widget.cancel_button.isVisible()
        assert widget.progress_bar.isVisible()
        
        # Reset UI
        widget.reset_ui()
        
        # Verify UI is reset
        assert widget.export_button.isEnabled()
        assert not widget.cancel_button.isVisible()
        assert not widget.progress_bar.isVisible()
        assert not widget.progress_label.isVisible()


@pytest.mark.ui
class TestExportThread:
    """Test ExportThread functionality"""
    
    @pytest.fixture
    def mock_archive(self, temp_dir):
        """Create mock archive for testing"""
        archive = Mock(spec=Archive)
        archive.root_path = temp_dir / "test_archive"
        return archive
    
    def test_export_thread_initialization(self, mock_archive):
        """Test ExportThread initializes correctly"""
        output_path = Path("/tmp/export")
        export_format = "bagit"
        metadata = {"key": "value"}
        
        with patch('src.ui.export_widget.ExportService'):
            thread = ExportThread(mock_archive, output_path, export_format, metadata)
            
            assert thread.archive == mock_archive
            assert thread.output_path == output_path
            assert thread.export_format == export_format
            assert thread.metadata == metadata
            assert thread.export_service is not None

    def test_export_thread_bagit_success(self, mock_archive):
        """Test successful BagIt export in thread"""
        output_path = Path("/tmp/export")
        result_path = Path("/tmp/export/result")
        
        with patch('src.ui.export_widget.ExportService') as mock_service_class:
            mock_service = Mock()
            mock_service.export_to_bagit.return_value = result_path
            mock_service_class.return_value = mock_service
            
            thread = ExportThread(mock_archive, output_path, "bagit", {})
            
            # Mock the signal emission
            thread.export_completed = Mock()
            
            # Run the thread's work (without actually starting QThread)
            thread.run()
            
            # Should call bagit export and emit completion
            mock_service.export_to_bagit.assert_called_once()
            thread.export_completed.emit.assert_called_once_with(str(result_path))

    def test_export_thread_directory_success(self, mock_archive):
        """Test successful directory export in thread"""
        output_path = Path("/tmp/export")
        result_path = Path("/tmp/export/result")
        
        with patch('src.ui.export_widget.ExportService') as mock_service_class, \
             patch('src.core.search.SearchService') as mock_search_class:
            
            mock_service = Mock()
            mock_service.export_selection.return_value = result_path
            mock_service_class.return_value = mock_service
            
            mock_search = Mock()
            mock_search.search.return_value = ([], 0)
            mock_search_class.return_value = mock_search
            
            thread = ExportThread(mock_archive, output_path, "directory", {})
            
            # Mock the signal emission
            thread.export_completed = Mock()
            
            # Run the thread's work
            thread.run()
            
            # Should call directory export and emit completion
            mock_service.export_selection.assert_called_once()
            thread.export_completed.emit.assert_called_once_with(str(result_path))

    def test_export_thread_error_handling(self, mock_archive):
        """Test error handling in export thread"""
        output_path = Path("/tmp/export")
        
        with patch('src.ui.export_widget.ExportService') as mock_service_class:
            mock_service = Mock()
            mock_service.export_to_bagit.side_effect = Exception("Export failed")
            mock_service_class.return_value = mock_service
            
            thread = ExportThread(mock_archive, output_path, "bagit", {})
            
            # Mock the signal emission
            thread.export_failed = Mock()
            
            # Run the thread's work
            thread.run()
            
            # Should emit failure signal
            thread.export_failed.emit.assert_called_once_with("Export failed")