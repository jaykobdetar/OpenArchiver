"""
UI tests for SearchWidget component
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.ui.search_widget import SearchWidget
from src.models import Archive
from src.core.search import SearchService, SearchResult


@pytest.fixture
def qt_app():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


@pytest.fixture
def search_widget(qt_app):
    """Create SearchWidget instance for tests"""
    widget = SearchWidget()
    yield widget


@pytest.fixture
def mock_archive():
    """Create mock archive for testing"""
    archive = Mock(spec=Archive)
    archive.name = "Test Archive"
    return archive


@pytest.fixture
def mock_search_service():
    """Create mock search service for testing"""
    service = Mock(spec=SearchService)
    return service


@pytest.fixture
def sample_search_results():
    """Create sample search results for testing"""
    return [
        SearchResult(
            asset_id="asset1",
            archive_path="docs/file1.txt",
            file_name="file1.txt",
            file_size=1024,
            mime_type="text/plain",
            checksum_sha256="abc123",
            profile_id="documents",
            created_at="2024-01-01T00:00:00",
            custom_metadata={"title": "Document 1", "tags": ["important"]}
        ),
        SearchResult(
            asset_id="asset2",
            archive_path="images/photo.jpg",
            file_name="photo.jpg",
            file_size=2048,
            mime_type="image/jpeg",
            checksum_sha256="def456",
            profile_id="photos",
            created_at="2024-01-02T00:00:00",
            custom_metadata={"title": "Photo 1", "location": "Paris"}
        )
    ]


class TestSearchWidget:
    """Test SearchWidget functionality"""
    
    def test_widget_initialization(self, search_widget):
        """Test that SearchWidget initializes correctly"""
        assert search_widget.archive is None
        assert search_widget.search_service is None
        
        # Check UI components exist
        assert search_widget.search_input is not None
        assert search_widget.search_button is not None
        assert search_widget.mime_filter is not None
        assert search_widget.results_table is not None
        assert search_widget.status_label is not None
    
    def test_set_archive(self, search_widget, mock_archive):
        """Test setting archive updates search service"""
        with patch('src.core.search.SearchService') as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service
            
            search_widget.set_archive(mock_archive)
            
            assert search_widget.archive == mock_archive
            assert search_widget.search_service == mock_service
            mock_service_class.assert_called_once_with(mock_archive)
    
    def test_search_input_placeholder(self, search_widget):
        """Test search input has correct placeholder text"""
        placeholder = search_widget.search_input.placeholderText()
        assert "search query" in placeholder.lower()
    
    def test_search_button_click(self, search_widget, mock_archive, sample_search_results):
        """Test search button click performs search"""
        # Setup widget with archive
        search_widget.set_archive(mock_archive)
        search_widget.search_service.search.return_value = (sample_search_results, 2)
        
        # Enter search query
        search_widget.search_input.setText("test query")
        
        # Click search button
        QTest.mouseClick(search_widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Verify search was performed
        search_widget.search_service.search.assert_called_once()
        
        # Verify results are displayed
        assert search_widget.results_table.rowCount() == 2
    
    def test_search_input_return_key(self, search_widget, mock_archive, sample_search_results):
        """Test pressing return in search input performs search"""
        # Setup widget with archive
        search_widget.set_archive(mock_archive)
        search_widget.search_service.search.return_value = (sample_search_results, 2)
        
        # Enter search query and press return
        search_widget.search_input.setText("test query")
        QTest.keyPress(search_widget.search_input, Qt.Key.Key_Return)
        QApplication.processEvents()
        
        # Verify search was performed
        search_widget.search_service.search.assert_called_once()
    
    def test_search_with_filters(self, search_widget, mock_archive, sample_search_results):
        """Test search with filters applied"""
        # Setup widget with archive
        search_widget.set_archive(mock_archive)
        search_widget.search_service.search.return_value = (sample_search_results, 1)
        
        # Set filters
        search_widget.mime_filter.setCurrentText("text/plain")
        search_widget.size_min_input.setValue(500)
        search_widget.size_max_input.setValue(2000)
        
        # Perform search
        search_widget.search_input.setText("document")
        search_widget.perform_search()
        
        # Verify search was called with filters
        search_widget.search_service.search.assert_called_once()
        call_args = search_widget.search_service.search.call_args
        
        # Check that filters were included
        assert 'filters' in call_args.kwargs
        filters = call_args.kwargs['filters']
        assert 'mime_type' in filters
        assert 'file_size_min' in filters
        assert 'file_size_max' in filters
    
    def test_results_table_population(self, search_widget, mock_archive, sample_search_results):
        """Test that search results populate the table correctly"""
        # Setup widget
        search_widget.set_archive(mock_archive)
        search_widget.search_service.search.return_value = (sample_search_results, 2)
        
        # Perform search
        search_widget.perform_search()
        
        # Check table contents
        table = search_widget.results_table
        assert table.rowCount() == 2
        
        # Check first row
        assert table.item(0, 0).text() == "file1.txt"  # File name column
        assert table.item(0, 1).text() == "text/plain"  # MIME type column
        assert "1024" in table.item(0, 2).text()  # Size column
        
        # Check second row
        assert table.item(1, 0).text() == "photo.jpg"
        assert table.item(1, 1).text() == "image/jpeg"
        assert "2048" in table.item(1, 2).text()
    
    def test_results_table_sorting(self, search_widget, mock_archive, sample_search_results):
        """Test that results table can be sorted by columns"""
        # Setup widget with results
        search_widget.set_archive(mock_archive)
        search_widget.search_service.search.return_value = (sample_search_results, 2)
        search_widget.perform_search()
        
        table = search_widget.results_table
        
        # Test sorting by file name column
        table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        QApplication.processEvents()
        
        # Verify sort order (file1.txt should come before photo.jpg)
        first_item = table.item(0, 0).text()
        second_item = table.item(1, 0).text()
        assert first_item < second_item  # Alphabetical order
    
    def test_clear_search(self, search_widget, mock_archive, sample_search_results):
        """Test clearing search results"""
        # Setup widget with results
        search_widget.set_archive(mock_archive)
        search_widget.search_service.search.return_value = (sample_search_results, 2)
        search_widget.perform_search()
        
        # Verify results exist
        assert search_widget.results_table.rowCount() == 2
        
        # Clear search
        search_widget.clear_search()
        
        # Verify results are cleared
        assert search_widget.results_table.rowCount() == 0
        assert search_widget.search_input.text() == ""
    
    def test_status_message_updates(self, search_widget, mock_archive, sample_search_results):
        """Test that status messages update correctly"""
        # Setup widget
        search_widget.set_archive(mock_archive)
        search_widget.search_service.search.return_value = (sample_search_results, 2)
        
        # Perform search
        search_widget.perform_search()
        
        # Check status message shows result count
        status_text = search_widget.status_label.text()
        assert "2" in status_text
        assert "result" in status_text.lower()
    
    def test_empty_search_results(self, search_widget, mock_archive):
        """Test handling of empty search results"""
        # Setup widget
        search_widget.set_archive(mock_archive)
        search_widget.search_service.search.return_value = ([], 0)
        
        # Perform search
        search_widget.search_input.setText("nonexistent")
        search_widget.perform_search()
        
        # Verify empty results are handled
        assert search_widget.results_table.rowCount() == 0
        status_text = search_widget.status_label.text()
        assert "0" in status_text or "no results" in status_text.lower()
    
    def test_search_error_handling(self, search_widget, mock_archive):
        """Test error handling during search"""
        # Setup widget
        search_widget.set_archive(mock_archive)
        search_widget.search_service.search.side_effect = Exception("Search error")
        
        # Perform search
        with patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_warning:
            search_widget.perform_search()
            
            # Verify error message was shown
            mock_warning.assert_called_once()
            
            # Verify table is cleared on error
            assert search_widget.results_table.rowCount() == 0
    
    def test_mime_type_filter_population(self, search_widget, mock_archive):
        """Test that MIME type filter is populated from archive"""
        # Mock metadata fields with MIME types
        mock_fields = [
            {'name': 'mime_type', 'values': ['text/plain', 'image/jpeg', 'application/pdf']}
        ]
        
        search_widget.set_archive(mock_archive)
        search_widget.search_service.get_metadata_fields.return_value = mock_fields
        
        # Trigger filter population
        search_widget.populate_filters()
        
        # Check that MIME types were added to filter
        mime_filter = search_widget.mime_filter
        assert mime_filter.count() > 1  # Should have "All Types" plus actual types
        
        # Check for specific MIME types
        items = [mime_filter.itemText(i) for i in range(mime_filter.count())]
        assert "text/plain" in items
        assert "image/jpeg" in items
    
    def test_search_signal_emission(self, search_widget, mock_archive, sample_search_results):
        """Test that search_performed signal is emitted"""
        # Setup widget
        search_widget.set_archive(mock_archive)
        search_widget.search_service.search.return_value = (sample_search_results, 2)
        
        # Connect signal to test slot
        signal_received = []
        search_widget.search_performed.connect(lambda query: signal_received.append(query))
        
        # Perform search
        test_query = "test search"
        search_widget.search_input.setText(test_query)
        search_widget.perform_search()
        
        # Verify signal was emitted
        assert len(signal_received) == 1
        assert signal_received[0] == test_query
    
    def test_no_archive_search_attempt(self, search_widget):
        """Test search attempt with no archive set"""
        # Attempt search without archive
        search_widget.search_input.setText("test")
        
        with patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_warning:
            search_widget.perform_search()
            
            # Should show warning about no archive
            mock_warning.assert_called_once()
            args, kwargs = mock_warning.call_args
            assert "no archive" in args[2].lower() or "archive" in args[2].lower()
    
    def test_results_table_context_menu(self, search_widget, mock_archive, sample_search_results):
        """Test context menu on results table"""
        # Setup widget with results
        search_widget.set_archive(mock_archive)
        search_widget.search_service.search.return_value = (sample_search_results, 2)
        search_widget.perform_search()
        
        # Get table widget
        table = search_widget.results_table
        
        # Select first row
        table.selectRow(0)
        
        # Right-click to show context menu
        with patch('PyQt6.QtWidgets.QMenu.exec') as mock_exec:
            # Simulate right-click
            QTest.mouseClick(table.viewport(), Qt.MouseButton.RightButton)
            QApplication.processEvents()
            
            # Context menu should be created (may not show in test environment)
            # This tests that the context menu creation doesn't crash