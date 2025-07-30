"""
Comprehensive UI tests for SearchWidget - Real user interaction testing
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.ui.search_widget import SearchWidget
from src.models import Archive
from src.core.search import SearchResult, SearchService


@pytest.mark.ui
class TestSearchWidget:
    """Test SearchWidget with real PyQt6 widget interactions"""
    
    @pytest.fixture
    def mock_archive(self, temp_dir):
        """Create mock archive for testing"""
        archive = Mock(spec=Archive)
        archive.root_path = temp_dir / "test_archive"
        archive.index_path = temp_dir / "test_archive" / ".index"
        archive.config = Mock()
        archive.config.name = "Test Archive"
        return archive
    
    @pytest.fixture
    def search_widget(self, qt_app, mock_archive):
        """Create SearchWidget instance for testing"""
        widget = SearchWidget()
        
        # Mock the SearchService to avoid database operations
        with patch('src.ui.search_widget.SearchService') as mock_service_class:
            mock_service = Mock(spec=SearchService)
            mock_service.search.return_value = ([], 0)
            mock_service.get_statistics.return_value = {
                'by_type': {
                    'text/plain': {'count': 5, 'size': 1024},
                    'image/jpeg': {'count': 3, 'size': 2048}
                }
            }
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
                archive_path="assets/2024/01/document1.txt",
                file_name="document1.txt",
                file_size=1024,
                mime_type="text/plain",
                checksum_sha256="abc123def456",
                profile_id="documents",
                created_at="2024-01-01T00:00:00",
                custom_metadata={"title": "Test Document 1", "tags": ["test", "document"]}
            ),
            SearchResult(
                asset_id="asset2",
                archive_path="assets/2024/02/image1.jpg",
                file_name="image1.jpg",
                file_size=2048,
                mime_type="image/jpeg",
                checksum_sha256="def456ghi789",
                profile_id="images",
                created_at="2024-02-01T00:00:00",
                custom_metadata={"title": "Test Image 1", "location": "Test Location"}
            ),
            SearchResult(
                asset_id="asset3",
                archive_path="assets/2024/03/document2.txt",
                file_name="document2.txt",
                file_size=512,
                mime_type="text/plain",
                checksum_sha256="ghi789jkl012",
                profile_id="documents",
                created_at="2024-03-01T00:00:00",
                custom_metadata={"title": "Test Document 2", "tags": ["test", "sample"]}
            )
        ]

    def test_widget_initialization(self, qt_app):
        """Test SearchWidget initializes correctly"""
        widget = SearchWidget()
        
        # Test basic widget properties
        assert widget is not None
        assert widget.archive is None
        assert widget.search_service is None
        
        # Test UI components exist
        assert hasattr(widget, 'search_input')
        assert hasattr(widget, 'search_button')
        assert hasattr(widget, 'results_table')
        assert hasattr(widget, 'mime_filter')
        assert hasattr(widget, 'size_min')
        assert hasattr(widget, 'size_max')
        assert hasattr(widget, 'limit_spin')
        
        # Test initial states
        assert not widget.search_input.isEnabled()
        assert not widget.search_button.isEnabled()
        assert widget.results_table.rowCount() == 0
        
        widget.close()
        qt_app.processEvents()
        widget.deleteLater()
        qt_app.processEvents()

    def test_archive_setting(self, search_widget):
        """Test setting archive enables/disables widget correctly"""
        widget, mock_service = search_widget
        
        # Should be enabled since we set archive in fixture
        assert widget.archive is not None
        assert widget.search_service is not None
        assert widget.search_input.isEnabled()
        assert widget.search_button.isEnabled()
        assert widget.mime_filter.isEnabled()
        
        # Test clearing archive
        widget.set_archive(None)
        assert widget.archive is None
        assert widget.search_service is None
        assert not widget.search_input.isEnabled()
        assert not widget.search_button.isEnabled()

    def test_filter_population(self, search_widget):
        """Test MIME type filter population from statistics"""
        widget, mock_service = search_widget
        
        # Check that filters were populated
        assert widget.mime_filter.count() > 1  # Should have "All Types" + actual types
        
        # Find specific MIME types
        mime_items = []
        for i in range(widget.mime_filter.count()):
            mime_items.append(widget.mime_filter.itemText(i))
        
        assert "All Types" in mime_items
        # Should have processed the mock statistics
        assert any("Text" in item for item in mime_items)  # text/plain -> Text
        assert any("Image" in item for item in mime_items)  # image/jpeg -> Image

    def test_search_input_interaction(self, search_widget, sample_search_results):
        """Test typing in search input and triggering search"""
        widget, mock_service = search_widget
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        # Type in search input
        search_text = "test document"
        QTest.keyClicks(widget.search_input, search_text)
        
        # Verify text was entered
        assert widget.search_input.text() == search_text
        
        # Trigger search by pressing Enter
        QTest.keyPress(widget.search_input, Qt.Key.Key_Return)
        QApplication.processEvents()
        
        # Verify search was called
        mock_service.search.assert_called()
        call_args = mock_service.search.call_args
        assert search_text in str(call_args)

    def test_search_button_click(self, search_widget, sample_search_results):
        """Test clicking search button"""
        widget, mock_service = search_widget
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        # Set search text
        search_text = "test query"
        widget.search_input.setText(search_text)
        
        # Click search button
        QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Verify search was called
        mock_service.search.assert_called()

    def test_results_table_population(self, search_widget, sample_search_results):
        """Test search results populate the table correctly"""
        widget, mock_service = search_widget
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        # Perform search
        widget.search_input.setText("test")
        QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Verify table was populated
        assert widget.results_table.rowCount() == len(sample_search_results)
        
        # Check first row content
        assert widget.results_table.item(0, 0).text() == "document1.txt"  # Name
        assert "1.0 KB" in widget.results_table.item(0, 1).text()  # Size (formatted)
        assert "text/plain" in widget.results_table.item(0, 2).text()  # Type
        
        # Check second row
        assert widget.results_table.item(1, 0).text() == "image1.jpg"
        assert "2.0 KB" in widget.results_table.item(1, 1).text()  # Size (formatted)

    def test_mime_type_filter_interaction(self, search_widget, sample_search_results):
        """Test MIME type filter selection"""
        widget, mock_service = search_widget
        mock_service.search.return_value = ([], 0)  # Empty results for filter test
        
        # Select a specific MIME type (find Text option)
        text_index = -1
        for i in range(widget.mime_filter.count()):
            if "Text" in widget.mime_filter.itemText(i):
                text_index = i
                break
        
        if text_index >= 0:
            widget.mime_filter.setCurrentIndex(text_index)
            
            # Perform search
            widget.search_input.setText("filtered search")
            QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            
            # Verify search was called with filters
            mock_service.search.assert_called()
            call_args = mock_service.search.call_args
            # Should have filters applied
            assert 'filters' in call_args.kwargs or len(call_args.args) > 1

    def test_size_filter_interaction(self, search_widget):
        """Test size filter controls"""
        widget, mock_service = search_widget
        mock_service.search.return_value = ([], 0)
        
        # Set size filters
        widget.size_min.setValue(1000)
        widget.size_max.setValue(5000)
        
        # Perform search
        widget.search_input.setText("size filtered")
        QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Verify search was called
        mock_service.search.assert_called()

    def test_results_limit_control(self, search_widget):
        """Test results limit spinner"""
        widget, mock_service = search_widget
        mock_service.search.return_value = ([], 0)
        
        # Change limit
        original_limit = widget.limit_spin.value()
        new_limit = 50
        widget.limit_spin.setValue(new_limit)
        
        assert widget.limit_spin.value() == new_limit
        assert widget.limit_spin.value() != original_limit

    def test_clear_results(self, search_widget, sample_search_results):
        """Test clearing search results"""
        widget, mock_service = search_widget
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        # Perform search to populate results
        widget.search_input.setText("test")
        QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Verify results exist
        assert widget.results_table.rowCount() > 0
        
        # Clear results
        widget.clear_results()
        
        # Verify results were cleared
        assert widget.results_table.rowCount() == 0

    def test_empty_search_handling(self, search_widget):
        """Test handling of empty search queries"""
        widget, mock_service = search_widget
        mock_service.search.return_value = ([], 0)
        
        # Try to search with empty query
        widget.search_input.setText("")
        QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Should still call search (empty query is valid)
        mock_service.search.assert_called()

    def test_search_error_handling(self, search_widget):
        """Test handling of search service errors"""
        widget, mock_service = search_widget
        
        # Make search service raise an exception
        mock_service.search.side_effect = Exception("Search failed")
        
        # Perform search
        widget.search_input.setText("error test")
        QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Should not crash, table should remain empty
        assert widget.results_table.rowCount() == 0

    def test_results_table_selection(self, search_widget, sample_search_results):
        """Test selecting rows in results table"""
        widget, mock_service = search_widget
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        # Populate results
        widget.search_input.setText("test")
        QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Select first row
        widget.results_table.selectRow(0)
        QApplication.processEvents()
        
        # Verify selection
        selected_rows = widget.results_table.selectionModel().selectedRows()
        assert len(selected_rows) == 1
        assert selected_rows[0].row() == 0

    def test_results_info_display(self, search_widget, sample_search_results):
        """Test results information display"""
        widget, mock_service = search_widget
        mock_service.search.return_value = (sample_search_results, len(sample_search_results))
        
        # Initial state
        assert "No search performed" in widget.results_info.text()
        
        # Perform search
        widget.search_input.setText("info test")
        QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Should show results count
        info_text = widget.results_info.text()
        assert str(len(sample_search_results)) in info_text
        assert "result" in info_text.lower()

    def test_search_signal_emission(self, search_widget):
        """Test that search_performed signal is emitted"""
        widget, mock_service = search_widget
        mock_service.search.return_value = ([], 0)
        
        # Connect signal to a mock
        signal_mock = Mock()
        widget.search_performed.connect(signal_mock)
        
        # Perform search
        search_query = "signal test"
        widget.search_input.setText(search_query)
        QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # Verify signal was emitted
        signal_mock.assert_called_once_with(search_query)

    def test_widget_cleanup(self, qt_app, mock_archive):
        """Test proper widget cleanup"""
        widget = SearchWidget()
        
        # Set archive to initialize
        with patch('src.ui.search_widget.SearchService'):
            widget.set_archive(mock_archive)
        
        # Close widget
        widget.close()
        qt_app.processEvents()
        
        # Should not crash
        assert True

    def test_multiple_searches(self, search_widget, sample_search_results):
        """Test performing multiple searches in sequence"""
        widget, mock_service = search_widget
        
        # First search
        mock_service.search.return_value = (sample_search_results[:2], 2)
        widget.search_input.setText("first search")
        QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        assert widget.results_table.rowCount() == 2
        
        # Second search with different results
        mock_service.search.return_value = (sample_search_results[2:], 1)
        widget.search_input.clear()
        QTest.keyClicks(widget.search_input, "second search")
        QTest.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        assert widget.results_table.rowCount() == 1
        assert mock_service.search.call_count == 2