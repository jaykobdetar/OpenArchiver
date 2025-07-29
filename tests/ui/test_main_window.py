"""
UI tests for MainWindow component
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest

from src.ui.main_window import MainWindow
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
def main_window(qt_app):
    """Create MainWindow instance for tests"""
    window = MainWindow()
    window.show()
    yield window
    window.close()


@pytest.fixture
def sample_archive_path(tmp_path):
    """Create a sample archive for testing"""
    archive_path = tmp_path / "test_archive"
    archive_path.mkdir()
    
    # Create archive structure
    (archive_path / "assets").mkdir()
    (archive_path / "profiles").mkdir()
    (archive_path / ".index").mkdir()
    
    # Create archive.json
    archive_config = {
        "name": "Test Archive",
        "description": "Test archive for UI testing",
        "version": "1.0",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
    }
    
    import json
    with open(archive_path / "archive.json", "w") as f:
        json.dump(archive_config, f)
    
    return archive_path


class TestMainWindow:
    """Test MainWindow functionality"""
    
    def test_main_window_initialization(self, main_window):
        """Test that MainWindow initializes correctly"""
        assert main_window.windowTitle() == "Archive Tool"
        assert main_window.minimumSize().width() == 1200
        assert main_window.minimumSize().height() == 800
        assert main_window.current_archive is None
        
        # Check that main UI components exist
        assert main_window.tab_widget is not None
        assert main_window.archive_browser is not None
        assert main_window.search_widget is not None
        assert main_window.profile_manager is not None
        assert main_window.integrity_widget is not None
        assert main_window.export_widget is not None
    
    def test_menu_creation(self, main_window):
        """Test that menus are created correctly"""
        menubar = main_window.menuBar()
        assert menubar is not None
        
        # Check for expected menus
        menu_titles = []
        for action in menubar.actions():
            if action.menu():
                menu_titles.append(action.menu().title())
        
        expected_menus = ["&File", "&Edit", "&View", "&Tools", "&Help"]
        for menu_title in expected_menus:
            assert menu_title in menu_titles
    
    def test_toolbar_creation(self, main_window):
        """Test that toolbar is created with expected actions"""
        toolbar = main_window.findChild(type(main_window.toolbar))
        assert toolbar is not None
        
        # Check that toolbar has actions
        actions = toolbar.actions()
        assert len(actions) > 0
        
        # Check for expected action types (non-separator actions)
        action_texts = [action.text() for action in actions if not action.isSeparator()]
        expected_actions = ["New Archive", "Open Archive", "Search", "Verify Integrity"]
        
        for expected_action in expected_actions:
            assert expected_action in action_texts
    
    def test_statusbar_creation(self, main_window):
        """Test that status bar is created"""
        statusbar = main_window.statusBar()
        assert statusbar is not None
        
        # Check for status label and progress bar
        assert hasattr(main_window, 'status_label')
        assert hasattr(main_window, 'progress_bar')
    
    @patch('src.ui.dialogs.NewArchiveDialog')
    def test_new_archive_action(self, mock_dialog, main_window):
        """Test new archive action"""
        # Setup mock dialog
        mock_dialog_instance = Mock()
        mock_dialog_instance.exec.return_value = 1  # QDialog.Accepted
        mock_dialog_instance.get_archive_info.return_value = {
            'name': 'Test Archive',
            'path': '/tmp/test_archive',
            'description': 'Test description'
        }
        mock_dialog.return_value = mock_dialog_instance
        
        # Mock Archive.create
        with patch('src.models.Archive.create') as mock_create:
            mock_archive = Mock()
            mock_create.return_value = mock_archive
            
            # Trigger new archive action
            main_window.new_archive()
            
            # Verify dialog was shown
            mock_dialog.assert_called_once()
            mock_dialog_instance.exec.assert_called_once()
            
            # Verify archive was created
            mock_create.assert_called_once()
    
    @patch('src.ui.dialogs.OpenArchiveDialog')
    def test_open_archive_action(self, mock_dialog, main_window):
        """Test open archive action"""
        # Setup mock dialog
        mock_dialog_instance = Mock()
        mock_dialog_instance.exec.return_value = 1  # QDialog.Accepted
        mock_dialog_instance.get_selected_path.return_value = '/tmp/test_archive'
        mock_dialog.return_value = mock_dialog_instance
        
        # Mock Archive.load
        with patch('src.models.Archive.load') as mock_load:
            mock_archive = Mock()
            mock_archive.exists.return_value = True
            mock_load.return_value = mock_archive
            
            # Trigger open archive action
            main_window.open_archive()
            
            # Verify dialog was shown
            mock_dialog.assert_called_once()
            mock_dialog_instance.exec.assert_called_once()
            
            # Verify archive was loaded
            mock_load.assert_called_once_with(Path('/tmp/test_archive'))
    
    def test_archive_changed_signal(self, main_window, sample_archive_path):
        """Test that archive_changed signal works correctly"""
        # Create a real archive
        archive = Archive.load(sample_archive_path)
        
        # Connect signal to test slot
        signal_received = []
        main_window.archive_changed.connect(lambda a: signal_received.append(a))
        
        # Set archive
        main_window.set_archive(archive)
        
        # Process events to ensure signal is emitted
        QApplication.processEvents()
        
        # Verify signal was emitted
        assert len(signal_received) == 1
        assert signal_received[0] == archive
        assert main_window.current_archive == archive
    
    def test_status_message_display(self, main_window):
        """Test status message display functionality"""
        test_message = "Test status message"
        main_window.show_status_message(test_message)
        
        # Process events
        QApplication.processEvents()
        
        # Check status bar shows message
        statusbar = main_window.statusBar()
        assert test_message in statusbar.currentMessage()
    
    def test_progress_bar_functionality(self, main_window):
        """Test progress bar show/hide functionality"""
        # Show progress
        main_window.show_progress("Testing progress", 0, 100)
        
        # Process events
        QApplication.processEvents()
        
        # Verify progress bar is visible
        assert main_window.progress_bar.isVisible()
        assert main_window.progress_bar.minimum() == 0
        assert main_window.progress_bar.maximum() == 100
        
        # Update progress
        main_window.update_progress(50)
        assert main_window.progress_bar.value() == 50
        
        # Hide progress
        main_window.hide_progress()
        assert not main_window.progress_bar.isVisible()
    
    def test_tab_switching(self, main_window):
        """Test tab switching functionality"""
        tab_widget = main_window.tab_widget
        
        # Test switching to each tab
        for i in range(tab_widget.count()):
            tab_widget.setCurrentIndex(i)
            QApplication.processEvents()
            assert tab_widget.currentIndex() == i
    
    @patch('PyQt6.QtWidgets.QMessageBox.question')
    def test_close_with_unsaved_changes(self, mock_question, main_window, sample_archive_path):
        """Test close behavior with unsaved changes"""
        # Set up archive with unsaved changes
        archive = Archive.load(sample_archive_path)
        main_window.set_archive(archive)
        main_window.has_unsaved_changes = True
        
        # Mock user clicking "Yes" to save
        mock_question.return_value = QMessageBox.StandardButton.Yes
        
        # Attempt to close
        event = Mock()
        main_window.closeEvent(event)
        
        # Verify confirmation dialog was shown
        mock_question.assert_called_once()
    
    def test_keyboard_shortcuts(self, main_window):
        """Test keyboard shortcuts work correctly"""
        # Test Ctrl+N for new archive
        with patch.object(main_window, 'new_archive') as mock_new:
            QTest.keySequence(main_window, "Ctrl+N")
            QApplication.processEvents()
            mock_new.assert_called_once()
        
        # Test Ctrl+O for open archive
        with patch.object(main_window, 'open_archive') as mock_open:
            QTest.keySequence(main_window, "Ctrl+O")
            QApplication.processEvents()
            mock_open.assert_called_once()
        
        # Test Ctrl+F for search
        with patch.object(main_window, 'focus_search') as mock_search:
            QTest.keySequence(main_window, "Ctrl+F")
            QApplication.processEvents()
            mock_search.assert_called_once()
    
    def test_window_state_persistence(self, main_window):
        """Test that window state can be saved and restored"""
        # Set window properties
        main_window.resize(1400, 900)
        main_window.move(100, 100)
        
        # Save settings
        main_window.save_settings()
        
        # Create new window and load settings
        new_window = MainWindow()
        new_window.load_settings()
        
        # Verify settings were restored (approximately)
        # Note: exact pixel matching may be unreliable in different environments
        assert abs(new_window.width() - 1400) < 50
        assert abs(new_window.height() - 900) < 50
        
        new_window.close()
    
    def test_error_handling_display(self, main_window):
        """Test error message display"""
        error_message = "Test error message"
        
        with patch('PyQt6.QtWidgets.QMessageBox.critical') as mock_critical:
            main_window.show_error(error_message)
            mock_critical.assert_called_once()
            
            # Check the message contains our error
            args, kwargs = mock_critical.call_args
            assert error_message in args[2]  # message is third argument
    
    def test_about_dialog(self, main_window):
        """Test about dialog display"""
        with patch('PyQt6.QtWidgets.QMessageBox.about') as mock_about:
            main_window.show_about()
            mock_about.assert_called_once()
            
            # Check the about message contains app info
            args, kwargs = mock_about.call_args
            about_text = args[2]  # message is third argument
            assert "Archive Tool" in about_text