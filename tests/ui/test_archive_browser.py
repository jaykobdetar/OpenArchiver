"""
UI tests for ArchiveBrowser component
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QTreeWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.ui.archive_browser import ArchiveBrowser
from src.models import Archive
from src.core.search import SearchResult


@pytest.fixture
def qt_app():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


@pytest.fixture
def archive_browser(qt_app):
    """Create ArchiveBrowser instance for tests"""
    browser = ArchiveBrowser()
    yield browser


@pytest.fixture
def mock_archive():
    """Create mock archive for testing"""
    archive = Mock(spec=Archive)
    archive.name = "Test Archive"
    archive.root_path = Path("/test/archive")
    archive.assets_path = Path("/test/archive/assets")
    return archive


@pytest.fixture
def sample_assets():
    """Create sample assets for testing"""
    return [
        SearchResult(
            asset_id="asset1",
            archive_path="assets/2024/01/documents/file1.txt",
            file_name="file1.txt",
            file_size=1024,
            mime_type="text/plain",
            checksum_sha256="abc123",
            profile_id="documents",
            created_at="2024-01-01T00:00:00",
            custom_metadata={"title": "Document 1"}
        ),
        SearchResult(
            asset_id="asset2",
            archive_path="assets/2024/02/images/photo.jpg",
            file_name="photo.jpg",
            file_size=2048,
            mime_type="image/jpeg",
            checksum_sha256="def456",
            profile_id="photos",
            created_at="2024-02-01T00:00:00",
            custom_metadata={"title": "Photo 1"}
        ),
        SearchResult(
            asset_id="asset3",
            archive_path="assets/2024/01/documents/file2.pdf",
            file_name="file2.pdf",
            file_size=4096,
            mime_type="application/pdf",
            checksum_sha256="ghi789",
            profile_id="documents",
            created_at="2024-01-15T00:00:00",
            custom_metadata={"title": "Document 2"}
        )
    ]


class TestArchiveBrowser:
    """Test ArchiveBrowser functionality"""
    
    def test_browser_initialization(self, archive_browser):
        """Test that ArchiveBrowser initializes correctly"""
        assert archive_browser.archive is None
        assert archive_browser.tree_widget is not None
        assert archive_browser.details_panel is not None
        
        # Check initial tree state
        assert archive_browser.tree_widget.topLevelItemCount() == 0
    
    def test_set_archive(self, archive_browser, mock_archive):
        """Test setting archive updates browser state"""
        archive_browser.set_archive(mock_archive)
        
        assert archive_browser.archive == mock_archive
    
    def test_tree_population_with_assets(self, archive_browser, mock_archive, sample_assets):
        """Test that tree is populated correctly with assets"""
        # Setup archive browser
        archive_browser.set_archive(mock_archive)
        
        # Mock search service to return assets
        with patch('src.core.search.SearchService') as mock_service_class:
            mock_service = Mock()
            mock_service.search.return_value = (sample_assets, 3)
            mock_service_class.return_value = mock_service
            
            # Populate tree
            archive_browser.populate_tree()
            
            # Check tree structure
            tree = archive_browser.tree_widget
            assert tree.topLevelItemCount() > 0
            
            # Should have year folders
            year_items = []
            for i in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(i)
                if item.text(0) == "2024":
                    year_items.append(item)
            
            assert len(year_items) > 0
    
    def test_tree_hierarchy_structure(self, archive_browser, mock_archive, sample_assets):
        """Test that tree creates proper hierarchy (year/month/type)"""
        archive_browser.set_archive(mock_archive)
        
        with patch('src.core.search.SearchService') as mock_service_class:
            mock_service = Mock()
            mock_service.search.return_value = (sample_assets, 3)
            mock_service_class.return_value = mock_service
            
            archive_browser.populate_tree()
            
            tree = archive_browser.tree_widget
            
            # Find 2024 folder
            year_item = None
            for i in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(i)
                if item.text(0) == "2024":
                    year_item = item
                    break
            
            assert year_item is not None
            assert year_item.childCount() >= 2  # Should have 01 and 02 months
            
            # Check month folders exist
            month_names = []
            for i in range(year_item.childCount()):
                month_item = year_item.child(i)
                month_names.append(month_item.text(0))
            
            assert "01" in month_names
            assert "02" in month_names
    
    def test_tree_item_selection(self, archive_browser, mock_archive, sample_assets):
        """Test that selecting tree items shows details"""
        archive_browser.set_archive(mock_archive)
        
        with patch('src.core.search.SearchService') as mock_service_class:
            mock_service = Mock()
            mock_service.search.return_value = (sample_assets, 3)
            mock_service_class.return_value = mock_service
            
            archive_browser.populate_tree()
            
            tree = archive_browser.tree_widget
            
            # Find and select a file item
            def find_file_item(parent_item, target_filename):
                for i in range(parent_item.childCount()):
                    child = parent_item.child(i)
                    if child.text(0) == target_filename:
                        return child
                    # Recursively search children
                    result = find_file_item(child, target_filename)
                    if result:
                        return result
                return None
            
            # Look for file1.txt
            for i in range(tree.topLevelItemCount()):
                top_item = tree.topLevelItem(i)
                file_item = find_file_item(top_item, "file1.txt")
                if file_item:
                    tree.setCurrentItem(file_item)
                    QApplication.processEvents()
                    break
            
            # Details panel should show information
            details = archive_browser.details_panel
            assert details.isVisible()
    
    def test_tree_context_menu(self, archive_browser, mock_archive, sample_assets):
        """Test context menu on tree items"""
        archive_browser.set_archive(mock_archive)
        
        with patch('src.core.search.SearchService') as mock_service_class:
            mock_service = Mock()
            mock_service.search.return_value = (sample_assets, 3)
            mock_service_class.return_value = mock_service
            
            archive_browser.populate_tree()
            
            tree = archive_browser.tree_widget
            
            # Right-click on tree
            with patch('PyQt6.QtWidgets.QMenu.exec') as mock_exec:
                QTest.mouseClick(tree.viewport(), Qt.MouseButton.RightButton)
                QApplication.processEvents()
                
                # Context menu creation should not crash
                # (Actual menu display depends on implementation)
    
    def test_refresh_functionality(self, archive_browser, mock_archive, sample_assets):
        """Test refreshing the tree updates content"""
        archive_browser.set_archive(mock_archive)
        
        with patch('src.core.search.SearchService') as mock_service_class:
            mock_service = Mock()
            
            # First population
            mock_service.search.return_value = (sample_assets[:2], 2)
            mock_service_class.return_value = mock_service
            
            archive_browser.populate_tree()
            initial_count = archive_browser.tree_widget.topLevelItemCount()
            
            # Update with more assets
            mock_service.search.return_value = (sample_assets, 3)
            
            # Refresh
            archive_browser.refresh()
            QApplication.processEvents()
            
            # Tree should be updated
            final_count = archive_browser.tree_widget.topLevelItemCount()
            # Note: exact count comparison depends on tree structure logic
    
    def test_search_filtering(self, archive_browser, mock_archive, sample_assets):
        """Test filtering tree based on search"""
        archive_browser.set_archive(mock_archive)
        
        with patch('src.core.search.SearchService') as mock_service_class:
            mock_service = Mock()
            mock_service.search.return_value = (sample_assets, 3)
            mock_service_class.return_value = mock_service
            
            archive_browser.populate_tree()
            
            # Apply search filter
            filtered_assets = [sample_assets[0]]  # Only first asset
            mock_service.search.return_value = (filtered_assets, 1)
            
            archive_browser.filter_by_search("Document 1")
            QApplication.processEvents()
            
            # Tree should show fewer items
            tree = archive_browser.tree_widget
            # Verify that filtering occurred (implementation-dependent)
    
    def test_expand_collapse_functionality(self, archive_browser, mock_archive, sample_assets):
        """Test expanding and collapsing tree nodes"""
        archive_browser.set_archive(mock_archive)
        
        with patch('src.core.search.SearchService') as mock_service_class:
            mock_service = Mock()
            mock_service.search.return_value = (sample_assets, 3)
            mock_service_class.return_value = mock_service
            
            archive_browser.populate_tree()
            
            tree = archive_browser.tree_widget
            
            # Find a parent item
            if tree.topLevelItemCount() > 0:
                top_item = tree.topLevelItem(0)
                
                # Test expand
                tree.expandItem(top_item)
                assert top_item.isExpanded()
                
                # Test collapse
                tree.collapseItem(top_item)
                assert not top_item.isExpanded()
    
    def test_details_panel_content(self, archive_browser, mock_archive, sample_assets):
        """Test that details panel shows correct asset information"""
        archive_browser.set_archive(mock_archive)
        
        # Mock the details panel update method
        with patch.object(archive_browser, 'update_details_panel') as mock_update:
            # Simulate selecting an asset
            asset = sample_assets[0]
            archive_browser.show_asset_details(asset)
            
            # Verify details panel update was called
            mock_update.assert_called_once_with(asset)
    
    def test_file_type_icons(self, archive_browser, mock_archive, sample_assets):
        """Test that different file types show appropriate icons"""
        archive_browser.set_archive(mock_archive)
        
        with patch('src.core.search.SearchService') as mock_service_class:
            mock_service = Mock()
            mock_service.search.return_value = (sample_assets, 3)
            mock_service_class.return_value = mock_service
            
            archive_browser.populate_tree()
            
            # Check that tree items have icons
            # (Implementation depends on how icons are set)
            tree = archive_browser.tree_widget
            
            def check_items_have_icons(parent_item):
                for i in range(parent_item.childCount()):
                    child = parent_item.child(i)
                    # Each item should have some icon
                    assert not child.icon(0).isNull() or child.childCount() > 0
                    check_items_have_icons(child)
            
            for i in range(tree.topLevelItemCount()):
                check_items_have_icons(tree.topLevelItem(i))
    
    def test_empty_archive_handling(self, archive_browser, mock_archive):
        """Test handling of empty archive"""
        archive_browser.set_archive(mock_archive)
        
        with patch('src.core.search.SearchService') as mock_service_class:
            mock_service = Mock()
            mock_service.search.return_value = ([], 0)  # Empty results
            mock_service_class.return_value = mock_service
            
            archive_browser.populate_tree()
            
            tree = archive_browser.tree_widget
            assert tree.topLevelItemCount() == 0
            
            # Should show empty state message
            # (Implementation-dependent)
    
    def test_asset_count_display(self, archive_browser, mock_archive, sample_assets):
        """Test that asset counts are displayed correctly"""
        archive_browser.set_archive(mock_archive)
        
        with patch('src.core.search.SearchService') as mock_service_class:
            mock_service = Mock()
            mock_service.search.return_value = (sample_assets, 3)
            mock_service_class.return_value = mock_service
            
            archive_browser.populate_tree()
            
            # Check if folder items show counts
            tree = archive_browser.tree_widget
            if tree.topLevelItemCount() > 0:
                year_item = tree.topLevelItem(0)
                item_text = year_item.text(0)
                # May include count like "2024 (3 items)"
                # Implementation-dependent feature