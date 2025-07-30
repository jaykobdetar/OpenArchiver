"""
Comprehensive UI tests for ArchiveBrowser - Real user interaction testing
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QContextMenuEvent

from src.ui.archive_browser import ArchiveBrowser
from src.models import Archive
from src.core.search import SearchResult, SearchService


@pytest.mark.ui
class TestArchiveBrowser:
    """Test ArchiveBrowser with real PyQt6 widget interactions"""
    
    @pytest.fixture
    def mock_archive(self, temp_dir):
        """Create mock archive for testing"""
        archive = Mock(spec=Archive)
        archive.root_path = temp_dir / "test_archive"
        archive.config = Mock()
        archive.config.name = "Test Archive"
        return archive
    
    @pytest.fixture
    def archive_browser(self, qt_app, mock_archive):
        """Create ArchiveBrowser instance for testing"""
        widget = ArchiveBrowser()
        
        # Mock the SearchService to avoid database operations
        with patch('src.ui.archive_browser.SearchService') as mock_service_class:
            mock_service = Mock(spec=SearchService)
            mock_service.search.return_value = ([], 0)
            mock_service_class.return_value = mock_service
            
            widget.set_archive(mock_archive)
            
            yield widget, mock_service
        
        # Cleanup
        widget.close()
        qt_app.processEvents()
        widget.deleteLater()
        qt_app.processEvents()
    
    @pytest.fixture
    def sample_search_results(self):
        """Create sample search results for testing"""
        return [
            SearchResult(
                asset_id="asset1",
                archive_path="assets/2024/01/documents/doc1.txt",
                file_name="doc1.txt",
                file_size=1024,
                mime_type="text/plain",
                checksum_sha256="abc123def456",
                profile_id="documents",
                created_at="2024-01-01T10:00:00",
                custom_metadata={"title": "Document 1"}
            ),
            SearchResult(
                asset_id="asset2",
                archive_path="assets/2024/01/images/photo1.jpg",
                file_name="photo1.jpg",
                file_size=2048000,
                mime_type="image/jpeg",
                checksum_sha256="def456ghi789",
                profile_id="images",
                created_at="2024-01-15T14:30:00",
                custom_metadata={"title": "Photo 1"}
            ),
            SearchResult(
                asset_id="asset3",
                archive_path="assets/2024/02/documents/doc2.txt",
                file_name="doc2.txt",
                file_size=512,
                mime_type="text/plain",
                checksum_sha256="ghi789jkl012",
                profile_id="documents",
                created_at="2024-02-01T09:15:00",
                custom_metadata={"title": "Document 2"}
            ),
            SearchResult(
                asset_id="asset4",
                archive_path="assets/2024/02/images/photo2.png",
                file_name="photo2.png",
                file_size=1536000,
                mime_type="image/png",
                checksum_sha256="jkl012mno345",
                profile_id="images",
                created_at="2024-02-10T16:45:00",
                custom_metadata={"title": "Photo 2"}
            )
        ]

    def test_widget_initialization(self, qt_app):
        """Test ArchiveBrowser initializes correctly"""
        widget = ArchiveBrowser()
        
        # Test basic widget properties
        assert widget is not None
        assert widget.archive is None
        assert widget.search_service is None
        
        # Test UI components exist
        assert hasattr(widget, 'tree')
        assert widget.tree is not None
        
        # Test tree widget properties
        assert widget.tree.columnCount() == 4
        assert widget.tree.headerItem().text(0) == "Name"
        assert widget.tree.headerItem().text(1) == "Size"
        assert widget.tree.headerItem().text(2) == "Type"
        assert widget.tree.headerItem().text(3) == "Modified"
        
        # Test initial state
        assert widget.tree.topLevelItemCount() == 0
        
        widget.close()
        qt_app.processEvents()
        widget.deleteLater()
        qt_app.processEvents()

    def test_archive_setting(self, archive_browser):
        """Test setting archive enables/disables widget correctly"""
        widget, mock_service = archive_browser
        
        # Should be enabled since we set archive in fixture
        assert widget.archive is not None
        assert widget.search_service is not None
        
        # Test clearing archive
        widget.set_archive(None)
        assert widget.archive is None
        assert widget.search_service is None
        assert widget.tree.topLevelItemCount() == 0

    def test_tree_population_with_results(self, archive_browser, sample_search_results):
        """Test tree population from search results"""
        widget, mock_service = archive_browser
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        # Trigger refresh
        widget.refresh()
        QApplication.processEvents()
        
        # Verify tree was populated
        assert widget.tree.topLevelItemCount() > 0
        
        # Check that assets folder exists
        assets_item = None
        for i in range(widget.tree.topLevelItemCount()):
            item = widget.tree.topLevelItem(i)
            if item.text(0) == "assets":
                assets_item = item
                break
        
        assert assets_item is not None
        assert assets_item.text(2) == "Folder"
        assert assets_item.childCount() > 0  # Should have year folders

    def test_tree_structure_hierarchy(self, archive_browser, sample_search_results):
        """Test hierarchical tree structure matches file paths"""
        widget, mock_service = archive_browser
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        widget.refresh()
        QApplication.processEvents()
        
        # Navigate the tree structure: assets -> 2024 -> 01 -> documents
        assets_item = widget.tree.topLevelItem(0)  # Should be "assets"
        assert assets_item.text(0) == "assets"
        
        # Find 2024 folder
        year_2024_item = None
        for i in range(assets_item.childCount()):
            child = assets_item.child(i)
            if child.text(0) == "2024":
                year_2024_item = child
                break
        
        assert year_2024_item is not None
        assert year_2024_item.text(2) == "Folder"

    def test_file_items_have_correct_data(self, archive_browser, sample_search_results):
        """Test file items display correct information"""
        widget, mock_service = archive_browser
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        widget.refresh()
        QApplication.processEvents()
        
        # Find a file item (need to navigate through the tree)
        def find_file_item(parent_item, filename):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.text(0) == filename:
                    return child
                # Recursively search in subdirectories
                found = find_file_item(child, filename)
                if found:
                    return found
            return None
        
        # Look for doc1.txt
        doc1_item = find_file_item(widget.tree.invisibleRootItem(), "doc1.txt")
        assert doc1_item is not None
        
        # Check file item properties
        assert doc1_item.text(0) == "doc1.txt"
        assert "1.0 KB" in doc1_item.text(1)  # Size formatted
        assert doc1_item.text(2) == "text/plain"
        assert doc1_item.text(3) == "2024-01-01"  # Date part
        
        # Check that search result is stored in item data
        search_result = doc1_item.data(0, Qt.ItemDataRole.UserRole)
        assert search_result is not None
        assert search_result.file_name == "doc1.txt"

    def test_size_formatting(self, archive_browser):
        """Test file size formatting"""
        widget, mock_service = archive_browser
        
        # Test different size formats
        assert widget._format_size(0) == "0 B"
        assert widget._format_size(512) == "512.0 B"
        assert widget._format_size(1024) == "1.0 KB"
        assert widget._format_size(1048576) == "1.0 MB"
        assert widget._format_size(2048000) == "2.0 MB"

    def test_item_selection_signal_emission(self, archive_browser, sample_search_results):
        """Test file selection emits signal"""
        widget, mock_service = archive_browser
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        # Connect signal to mock
        signal_mock = Mock()
        widget.file_selected.connect(signal_mock)
        
        widget.refresh()
        QApplication.processEvents()
        
        # Find and select a file item
        def find_and_select_file(parent_item, filename):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.text(0) == filename:
                    widget.tree.setCurrentItem(child)
                    return True
                if find_and_select_file(child, filename):
                    return True
            return False
        
        # Select doc1.txt
        found = find_and_select_file(widget.tree.invisibleRootItem(), "doc1.txt")
        assert found
        QApplication.processEvents()
        
        # Verify signal was emitted
        signal_mock.assert_called_once()
        # Check the emitted path
        call_args = signal_mock.call_args[0]
        assert "doc1.txt" in call_args[0]

    def test_item_double_click_handling(self, archive_browser, sample_search_results):
        """Test double-click on file items"""
        widget, mock_service = archive_browser
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        widget.refresh()
        QApplication.processEvents()
        
        # Find a file item
        def find_file_item(parent_item, filename):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.text(0) == filename:
                    return child
                found = find_file_item(child, filename)
                if found:
                    return found
            return None
        
        doc1_item = find_file_item(widget.tree.invisibleRootItem(), "doc1.txt")
        assert doc1_item is not None
        
        # Mock subprocess to avoid actually opening files
        # Also mock file existence since we're using fake paths
        with patch('subprocess.call') as mock_subprocess, \
             patch('pathlib.Path.exists', return_value=True):
            # Call the double-click handler directly instead of simulating clicks
            widget.on_item_double_clicked(doc1_item, 0)
            
            # Verify subprocess was called to open the file
            mock_subprocess.assert_called_once()

    def test_refresh_with_empty_results(self, archive_browser):
        """Test refresh with no search results"""
        widget, mock_service = archive_browser
        mock_service.search.return_value = ([], 0)
        
        widget.refresh()
        QApplication.processEvents()
        
        # Tree should be empty
        assert widget.tree.topLevelItemCount() == 0

    def test_refresh_with_search_service_error(self, archive_browser):
        """Test refresh handles search service errors gracefully"""
        widget, mock_service = archive_browser
        mock_service.search.side_effect = Exception("Search failed")
        
        # Mock QMessageBox to avoid actual dialog
        with patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_warning:
            widget.refresh()
            QApplication.processEvents()
            
            # Should show warning dialog
            mock_warning.assert_called_once()
            # Tree should remain empty
            assert widget.tree.topLevelItemCount() == 0

    def test_context_menu_functionality(self, archive_browser, sample_search_results):
        """Test context menu functionality without actually displaying menu"""
        widget, mock_service = archive_browser
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        widget.refresh()
        QApplication.processEvents()
        
        # Find a file item
        def find_file_item(parent_item, filename):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.text(0) == filename:
                    return child
                found = find_file_item(child, filename)
                if found:
                    return found
            return None
        
        doc1_item = find_file_item(widget.tree.invisibleRootItem(), "doc1.txt")
        assert doc1_item is not None
        
        # Test the underlying methods that context menu would call
        search_result = doc1_item.data(0, Qt.ItemDataRole.UserRole)
        assert search_result is not None
        
        # Test show_in_file_manager functionality
        # Mock the file path existence check since we're using fake paths
        with patch('subprocess.call') as mock_subprocess, \
             patch('pathlib.Path.exists', return_value=True):
            widget.show_in_file_manager(search_result)
            mock_subprocess.assert_called_once()
        
        # Test copy_to_clipboard functionality
        with patch('PyQt6.QtWidgets.QApplication.clipboard') as mock_clipboard_func:
            mock_clipboard = Mock()
            mock_clipboard_func.return_value = mock_clipboard
            
            # Test copying path
            widget.copy_to_clipboard(search_result.archive_path)
            mock_clipboard.setText.assert_called_with(search_result.archive_path)
            
            # Test copying checksum
            widget.copy_to_clipboard(search_result.checksum_sha256)
            mock_clipboard.setText.assert_called_with(search_result.checksum_sha256)

    def test_copy_to_clipboard_functionality(self, archive_browser):
        """Test copying text to clipboard"""
        widget, mock_service = archive_browser
        
        test_text = "test/path/to/file.txt"
        
        # Mock QApplication.clipboard
        with patch('PyQt6.QtWidgets.QApplication.clipboard') as mock_clipboard_func:
            mock_clipboard = Mock()
            mock_clipboard_func.return_value = mock_clipboard
            
            widget.copy_to_clipboard(test_text)
            
            # Verify clipboard was used
            mock_clipboard.setText.assert_called_once_with(test_text)

    def test_tree_expansion_after_refresh(self, archive_browser, sample_search_results):
        """Test that first level of tree is expanded after refresh"""
        widget, mock_service = archive_browser
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        widget.refresh()
        QApplication.processEvents()
        
        # Check that top-level items are expanded
        for i in range(widget.tree.topLevelItemCount()):
            item = widget.tree.topLevelItem(i)
            assert item.isExpanded()

    def test_widget_cleanup(self, archive_browser):
        """Test proper widget cleanup"""
        widget, mock_service = archive_browser
        
        # Test that widget can be closed without issues
        # (The fixture already handles proper cleanup)
        assert widget is not None
        assert hasattr(widget, 'tree')
        
        # Test clearing archive
        widget.set_archive(None)
        assert widget.archive is None
        assert widget.search_service is None
        
        # Should not crash
        assert True

    def test_multiple_refresh_operations(self, archive_browser, sample_search_results):
        """Test multiple refresh operations in sequence"""
        widget, mock_service = archive_browser
        
        # First refresh with results
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        widget.refresh()
        QApplication.processEvents()
        
        first_count = widget.tree.topLevelItemCount()
        assert first_count > 0
        
        # Second refresh with fewer results
        mock_service.search.return_value = (sample_search_results[:2], 2)
        widget.refresh()
        QApplication.processEvents()
        
        # Tree should be repopulated
        second_count = widget.tree.topLevelItemCount()
        assert second_count > 0
        # Structure might be the same even with fewer files
        
        # Third refresh with no results
        mock_service.search.return_value = ([], 0)
        widget.refresh()
        QApplication.processEvents()
        
        assert widget.tree.topLevelItemCount() == 0

    def test_file_vs_directory_item_distinction(self, archive_browser, sample_search_results):
        """Test that files and directories are properly distinguished in the tree"""
        widget, mock_service = archive_browser
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        widget.refresh()
        QApplication.processEvents()
        
        # Find directory and file items
        assets_item = widget.tree.topLevelItem(0)  # Should be "assets" directory
        assert assets_item.text(2) == "Folder"
        assert assets_item.text(1) == ""  # No size for directories
        
        # Find a file item
        def find_file_item(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) is not None:
                    return child
                found = find_file_item(child)
                if found:
                    return found
            return None
        
        file_item = find_file_item(widget.tree.invisibleRootItem())
        assert file_item is not None
        assert file_item.text(2) != "Folder"  # Should have actual MIME type
        assert file_item.text(1) != ""  # Should have size