"""
UI tests for IntegrityWidget component - Testing real functionality
"""

import pytest
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.ui.integrity_widget import IntegrityWidget
from src.models import Archive
from src.core.integrity import IntegrityReport


@pytest.fixture
def qt_app():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


@pytest.fixture
def integrity_widget(qt_app):
    """Create IntegrityWidget instance for tests"""
    widget = IntegrityWidget()
    yield widget


@pytest.fixture
def mock_archive():
    """Create mock archive for testing"""
    archive = Mock(spec=Archive)
    archive.name = "Test Archive"
    return archive


@pytest.fixture
def sample_integrity_report():
    """Create sample integrity report for testing"""
    report = IntegrityReport()
    report.total_assets = 100
    report.verified_assets = 95
    report.corrupted_assets = ["assets/corrupted1.txt", "assets/corrupted2.jpg"]
    report.missing_assets = ["assets/missing1.pdf"]
    report.missing_metadata = ["assets/no_metadata.doc"]
    return report


@pytest.mark.ui
class TestIntegrityWidget:
    """Test IntegrityWidget functionality based on actual implementation"""
    
    def test_widget_initialization(self, integrity_widget):
        """Test that IntegrityWidget initializes with correct components"""
        assert integrity_widget.archive is None
        assert integrity_widget.verification_thread is None
        
        # Check actual UI components exist (based on real implementation)
        assert hasattr(integrity_widget, 'verify_button')
        assert hasattr(integrity_widget, 'progress_bar')
        assert hasattr(integrity_widget, 'results_text')
        assert hasattr(integrity_widget, 'info_label')
        
        # Check initial state
        assert not integrity_widget.progress_bar.isVisible()
        assert integrity_widget.verify_button.isEnabled()
    
    def test_set_archive(self, integrity_widget, mock_archive):
        """Test setting archive updates widget state"""
        integrity_widget.set_archive(mock_archive)
        
        assert integrity_widget.archive == mock_archive
    
    def test_verify_button_click_no_archive(self, integrity_widget):
        """Test verify button click with no archive shows warning"""
        with patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_warning:
            QTest.mouseClick(integrity_widget.verify_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should show warning about no archive
            mock_warning.assert_called_once()
    
    def test_verify_button_click_with_archive(self, integrity_widget, mock_archive):
        """Test verify button click with archive starts verification"""
        integrity_widget.set_archive(mock_archive)
        
        with patch('src.ui.integrity_widget.IntegrityVerificationThread') as mock_thread_class:
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread
            
            # Click verify button
            QTest.mouseClick(integrity_widget.verify_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Should create and start verification thread
            mock_thread_class.assert_called_once_with(mock_archive)
            mock_thread.start.assert_called_once()
    
    def test_progress_display_during_verification(self, integrity_widget):
        """Test progress display shows during verification"""
        # Simulate verification start
        integrity_widget.on_verification_started()
        
        # Progress bar should be visible and verify button disabled
        assert integrity_widget.progress_bar.isVisible()
        assert not integrity_widget.verify_button.isEnabled()
    
    def test_progress_updates(self, integrity_widget):
        """Test progress updates work correctly"""
        integrity_widget.on_verification_started()
        
        # Simulate progress update
        integrity_widget.on_progress_updated(50, 100, "Verifying file 50/100")
        
        # Progress should be updated
        assert integrity_widget.progress_bar.value() == 50
        assert integrity_widget.progress_bar.maximum() == 100
    
    def test_verification_completion_with_report(self, integrity_widget, sample_integrity_report):
        """Test verification completion displays results"""
        integrity_widget.on_verification_started()
        
        # Simulate completion with report
        integrity_widget.on_verification_completed(sample_integrity_report)
        
        # Progress should be hidden and button re-enabled
        assert not integrity_widget.progress_bar.isVisible()
        assert integrity_widget.verify_button.isEnabled()
        
        # Results should be displayed
        results_text = integrity_widget.results_text.toPlainText()
        assert "100" in results_text  # Total assets
        assert "95" in results_text   # Verified assets
    
    def test_verification_error_handling(self, integrity_widget):
        """Test verification error handling"""
        integrity_widget.on_verification_started()
        
        # Simulate error
        error = Exception("Verification failed")
        
        with patch('PyQt6.QtWidgets.QMessageBox.critical') as mock_error:
            integrity_widget.on_verification_completed(error)
            
            # Should show error message
            mock_error.assert_called_once()
            assert "error" in mock_error.call_args[0][2].lower()
    
    def test_results_display_format(self, integrity_widget, sample_integrity_report):
        """Test that results are displayed in readable format"""
        integrity_widget.display_results(sample_integrity_report)
        
        results_text = integrity_widget.results_text.toPlainText()
        
        # Should show key statistics
        assert "Total Assets: 100" in results_text
        assert "Verified: 95" in results_text
        assert "Success Rate: 95.0%" in results_text
        
        # Should show issues if any
        assert "corrupted1.txt" in results_text
        assert "missing1.pdf" in results_text
    
    def test_clear_results(self, integrity_widget, sample_integrity_report):
        """Test clearing verification results"""
        # Display some results first
        integrity_widget.display_results(sample_integrity_report)
        assert len(integrity_widget.results_text.toPlainText()) > 0
        
        # Clear results
        integrity_widget.clear_results()
        
        # Results should be empty
        assert integrity_widget.results_text.toPlainText().strip() == ""