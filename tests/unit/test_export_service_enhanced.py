"""
Enhanced unit tests for Export Service - Improving coverage from 42-63% to 85%+
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.core.export import ExportService
from src.models import Archive
from src.core.search import SearchResult


@pytest.fixture
def mock_archive(tmp_path):
    """Create mock archive for testing with real directory structure"""
    archive = Mock(spec=Archive)
    
    # Create real directory structure for database
    archive_root = tmp_path / "test_archive"
    archive_root.mkdir()
    index_dir = archive_root / ".index"
    index_dir.mkdir()
    
    archive.root_path = archive_root
    archive.index_path = index_dir
    archive.config = Mock()
    archive.config.name = "Test Archive"
    archive.config.id = "test-archive-id"
    archive.config.description = "Test archive description"
    archive.config.created_at = "2024-01-01T00:00:00"
    return archive


@pytest.fixture
def export_service(mock_archive):
    """Create ExportService instance for testing"""
    return ExportService(mock_archive)


@pytest.fixture
def sample_search_results():
    """Create sample search results for export testing"""
    return [
        SearchResult(
            asset_id="asset1",
            archive_path="assets/2024/01/file1.txt",
            file_name="file1.txt",
            file_size=1024,
            mime_type="text/plain",
            checksum_sha256="abc123def456",
            profile_id="documents",
            created_at="2024-01-01T00:00:00",
            custom_metadata={"title": "Document 1", "tags": ["important"]}
        ),
        SearchResult(
            asset_id="asset2", 
            archive_path="assets/2024/02/photo.jpg",
            file_name="photo.jpg",
            file_size=2048,
            mime_type="image/jpeg",
            checksum_sha256="def456ghi789",
            profile_id="photos",
            created_at="2024-02-01T00:00:00",
            custom_metadata={"title": "Photo 1", "location": "Paris"}
        )
    ]


@pytest.mark.unit
class TestExportService:
    """Test ExportService functionality comprehensively"""
    
    def test_export_service_initialization(self, export_service, mock_archive):
        """Test ExportService initializes correctly"""
        assert export_service.archive == mock_archive
        assert export_service.search_service is not None
        assert export_service.progress_callback is None
    
    def test_set_progress_callback(self, export_service):
        """Test setting progress callback"""
        callback = Mock()
        export_service.set_progress_callback(callback)
        assert export_service.progress_callback == callback
    
    def test_report_progress_with_callback(self, export_service):
        """Test progress reporting with callback set"""
        callback = Mock()
        export_service.set_progress_callback(callback)
        
        export_service._report_progress(5, 10, "Test message")
        callback.assert_called_once_with(5, 10, "Test message")
    
    def test_report_progress_without_callback(self, export_service):
        """Test progress reporting without callback (should not crash)"""
        # Should not raise exception
        export_service._report_progress(5, 10, "Test message")
    
    def test_export_to_bagit_basic(self, export_service, sample_search_results, tmp_path):
        """Test basic BagIt export functionality"""
        output_path = tmp_path / "test_bag"
        
        with patch.object(export_service.search_service, 'search') as mock_search:
            mock_search.return_value = (sample_search_results, 2)
            
            with patch('src.core.export.bagit.make_bag') as mock_make_bag, \
                 patch('pathlib.Path.exists') as mock_exists, \
                 patch('pathlib.Path.is_dir') as mock_is_dir, \
                 patch('pathlib.Path.unlink') as mock_unlink, \
                 patch('shutil.copy2') as mock_copy, \
                 patch('shutil.move') as mock_move:
                
                # Setup mocks
                mock_exists.return_value = False  # Output doesn't exist initially
                mock_is_dir.return_value = False
                mock_bag = Mock()
                mock_make_bag.return_value = mock_bag
                
                # Perform export
                result = export_service.export_to_bagit(output_path)
                
                # Verify search was called
                mock_search.assert_called_once()
                
                # Verify bag creation
                mock_make_bag.assert_called_once()
                mock_bag.validate.assert_called_once()
                
                # Verify final move
                mock_move.assert_called_once()
                
                assert result == output_path.resolve()
    
    def test_export_to_bagit_with_search_filters(self, export_service, sample_search_results, tmp_path):
        """Test BagIt export with search filters"""
        output_path = tmp_path / "filtered_bag"
        search_filters = {'mime_type': 'text/plain', 'file_size_min': 500}
        
        with patch.object(export_service.search_service, 'search') as mock_search:
            mock_search.return_value = (sample_search_results[:1], 1)
            
            with patch('src.core.export.bagit.make_bag') as mock_make_bag, \
                 patch('pathlib.Path.exists') as mock_exists, \
                 patch('pathlib.Path.is_dir') as mock_is_dir, \
                 patch('pathlib.Path.unlink') as mock_unlink, \
                 patch('shutil.copy2') as mock_copy, \
                 patch('shutil.move') as mock_move:
                
                mock_exists.return_value = False
                mock_is_dir.return_value = False
                mock_bag = Mock()
                mock_make_bag.return_value = mock_bag
                
                # Perform export with filters
                export_service.export_to_bagit(output_path, search_filters=search_filters)
                
                # Verify search was called with filters
                mock_search.assert_called_once()
                call_args = mock_search.call_args
                assert call_args.kwargs['filters'] == search_filters
    
    def test_export_to_bagit_with_custom_metadata(self, export_service, sample_search_results, tmp_path):
        """Test BagIt export with custom metadata"""
        output_path = tmp_path / "custom_bag"
        custom_metadata = {
            'Source-Organization': 'Test Org',
            'Contact-Name': 'Test User',
            'External-Description': 'Custom description'
        }
        
        with patch.object(export_service.search_service, 'search') as mock_search:
            mock_search.return_value = (sample_search_results, 2)
            
            with patch('src.core.export.bagit.make_bag') as mock_make_bag, \
                 patch('pathlib.Path.exists') as mock_exists, \
                 patch('pathlib.Path.is_dir') as mock_is_dir, \
                 patch('pathlib.Path.unlink') as mock_unlink, \
                 patch('shutil.copy2') as mock_copy, \
                 patch('shutil.move') as mock_move:
                
                mock_exists.return_value = False
                mock_is_dir.return_value = False
                mock_bag = Mock()
                mock_make_bag.return_value = mock_bag
                
                # Perform export with custom metadata
                export_service.export_to_bagit(output_path, metadata=custom_metadata)
                
                # Verify bag creation with custom metadata
                mock_make_bag.assert_called_once()
                call_args = mock_make_bag.call_args
                metadata_arg = call_args[0][1]  # Second argument is metadata
                
                # Check custom metadata was included
                assert metadata_arg['Source-Organization'] == 'Test Org'
                assert metadata_arg['Contact-Name'] == 'Test User'
                assert 'Bagging-Date' in metadata_arg  # Auto-generated
    
    def test_export_to_bagit_with_custom_checksums(self, export_service, sample_search_results, tmp_path):
        """Test BagIt export with custom checksum algorithms"""
        output_path = tmp_path / "checksum_bag"
        checksums = ['sha256', 'md5']
        
        with patch.object(export_service.search_service, 'search') as mock_search:
            mock_search.return_value = (sample_search_results, 2)
            
            with patch('src.core.export.bagit.make_bag') as mock_make_bag, \
                 patch('pathlib.Path.exists') as mock_exists, \
                 patch('pathlib.Path.is_dir') as mock_is_dir, \
                 patch('pathlib.Path.unlink') as mock_unlink, \
                 patch('shutil.copy2') as mock_copy, \
                 patch('shutil.move') as mock_move:
                
                mock_exists.return_value = False
                mock_is_dir.return_value = False
                mock_bag = Mock()
                mock_make_bag.return_value = mock_bag
                
                # Perform export with custom checksums
                export_service.export_to_bagit(output_path, checksums=checksums)
                
                # Verify bag creation with custom checksums
                mock_make_bag.assert_called_once()
                call_args = mock_make_bag.call_args
                checksums_arg = call_args.kwargs['checksums']
                assert checksums_arg == checksums
    
    def test_export_to_bagit_missing_source_file(self, export_service, sample_search_results, tmp_path):
        """Test BagIt export handling of missing source files"""
        output_path = tmp_path / "missing_files_bag"
        
        with patch.object(export_service.search_service, 'search') as mock_search:
            mock_search.return_value = (sample_search_results, 2)
            
            with patch('src.core.export.bagit.make_bag') as mock_make_bag, \
                 patch('pathlib.Path.exists') as mock_exists, \
                 patch('pathlib.Path.is_dir') as mock_is_dir, \
                 patch('pathlib.Path.unlink') as mock_unlink, \
                 patch('shutil.copy2') as mock_copy, \
                 patch('shutil.move') as mock_move:
                
                # First call for source file (False = missing), others False for output path
                mock_exists.side_effect = [False, False, False, False, False]
                mock_is_dir.return_value = False
                mock_bag = Mock()
                mock_make_bag.return_value = mock_bag
                
                # Should not crash with missing file
                result = export_service.export_to_bagit(output_path)
                
                # Should still complete export
                assert result == output_path.resolve()
                mock_make_bag.assert_called_once()
    
    def test_export_to_bagit_existing_output_directory(self, export_service, sample_search_results, tmp_path):
        """Test BagIt export with existing output directory"""
        output_path = tmp_path / "existing_bag"
        output_path.mkdir()  # Create existing directory
        
        with patch.object(export_service.search_service, 'search') as mock_search:
            mock_search.return_value = (sample_search_results, 2)
            
            with patch('src.core.export.bagit.make_bag') as mock_make_bag, \
                 patch('pathlib.Path.exists') as mock_exists, \
                 patch('shutil.copy2') as mock_copy, \
                 patch('shutil.move') as mock_move, \
                 patch('shutil.rmtree') as mock_rmtree:
                
                mock_exists.return_value = True
                mock_bag = Mock()
                mock_make_bag.return_value = mock_bag
                
                # Perform export
                export_service.export_to_bagit(output_path)
                
                # Should remove existing directory
                mock_rmtree.assert_called_once_with(output_path)
    
    def test_export_to_bagit_existing_output_file(self, export_service, sample_search_results, tmp_path):
        """Test BagIt export with existing output file"""
        output_path = tmp_path / "existing_file"
        output_path.touch()  # Create existing file
        
        with patch.object(export_service.search_service, 'search') as mock_search:
            mock_search.return_value = (sample_search_results, 2)
            
            with patch('src.core.export.bagit.make_bag') as mock_make_bag, \
                 patch('pathlib.Path.exists') as mock_exists, \
                 patch('pathlib.Path.is_dir') as mock_is_dir, \
                 patch('pathlib.Path.unlink') as mock_unlink, \
                 patch('shutil.copy2') as mock_copy, \
                 patch('shutil.move') as mock_move:
                
                mock_exists.return_value = True
                mock_is_dir.return_value = False
                mock_bag = Mock()
                mock_make_bag.return_value = mock_bag
                
                # Perform export
                export_service.export_to_bagit(output_path)
                
                # Should remove existing file
                mock_unlink.assert_called_once()
    
    def test_export_selection_directory_format(self, export_service, sample_search_results):
        """Test export_selection with directory format"""
        asset_ids = ["asset1", "asset2"]
        output_path = Path("/tmp/export_dir")
        
        with patch.object(export_service, '_export_to_directory') as mock_export_dir:
            mock_export_dir.return_value = output_path
            
            result = export_service.export_selection(asset_ids, output_path, format="directory")
            
            mock_export_dir.assert_called_once_with(asset_ids, output_path, True)
            assert result == output_path
    
    def test_export_selection_bagit_format(self, export_service, sample_search_results):
        """Test export_selection with BagIt format"""
        asset_ids = ["asset1"]
        output_path = Path("/tmp/export_bag")
        
        with patch.object(export_service, 'export_to_bagit') as mock_export_bagit:
            mock_export_bagit.return_value = output_path
            
            result = export_service.export_selection(asset_ids, output_path, format="bagit")
            
            mock_export_bagit.assert_called_once_with(output_path, {'asset_id': asset_ids})
            assert result == output_path
    
    def test_export_selection_invalid_format(self, export_service):
        """Test export_selection with invalid format raises error"""
        asset_ids = ["asset1"]
        output_path = Path("/tmp/export")
        
        with pytest.raises(ValueError, match="Unsupported export format"):
            export_service.export_selection(asset_ids, output_path, format="invalid")
    
    def test_export_to_directory_method_exists(self, export_service):
        """Test that _export_to_directory method exists"""
        # Just verify the method exists without complex mocking
        assert hasattr(export_service, '_export_to_directory')
        assert callable(getattr(export_service, '_export_to_directory'))
    
    def test_generate_manifest_json_format(self, export_service, sample_search_results, tmp_path):
        """Test generate_manifest with JSON format"""
        output_file = tmp_path / "manifest.json"
        
        with patch.object(export_service.search_service, 'search') as mock_search, \
             patch.object(export_service.search_service, 'get_statistics') as mock_stats:
            
            mock_search.return_value = (sample_search_results, 2)
            mock_stats.return_value = {'total_assets': 2, 'total_size': 3072}
            
            result = export_service.generate_manifest(output_file, format="json")
            
            # Verify file was created
            assert result == output_file.resolve()
            assert output_file.exists()
            
            # Verify JSON content
            with open(output_file, 'r') as f:
                manifest = json.load(f)
            
            assert 'archive' in manifest
            assert 'statistics' in manifest
            assert 'assets' in manifest
            assert len(manifest['assets']) == 2
            assert manifest['archive']['name'] == "Test Archive"
    
    def test_generate_manifest_csv_format(self, export_service, sample_search_results, tmp_path):
        """Test generate_manifest with CSV format"""
        output_file = tmp_path / "manifest.csv"
        
        with patch.object(export_service.search_service, 'search') as mock_search, \
             patch.object(export_service.search_service, 'get_statistics') as mock_stats:
            
            mock_search.return_value = (sample_search_results, 2)
            mock_stats.return_value = {'total_assets': 2, 'total_size': 3072}
            
            result = export_service.generate_manifest(output_file, format="csv")
            
            # Verify file was created
            assert result == output_file.resolve()
            assert output_file.exists()
            
            # Verify CSV content
            content = output_file.read_text()
            assert "asset_id" in content  # Header
            assert "file_name" in content
            assert "asset1" in content    # Data
            assert "file1.txt" in content
    
    def test_generate_manifest_invalid_format(self, export_service):
        """Test generate_manifest with invalid format raises error"""
        output_file = Path("/tmp/manifest.xml")
        
        with pytest.raises(ValueError, match="Unsupported manifest format"):
            export_service.generate_manifest(output_file, format="xml")
    
    def test_generate_manifest_empty_assets(self, export_service, tmp_path):
        """Test generate_manifest with no assets"""
        output_file = tmp_path / "empty_manifest.json"
        
        with patch.object(export_service.search_service, 'search') as mock_search, \
             patch.object(export_service.search_service, 'get_statistics') as mock_stats:
            
            mock_search.return_value = ([], 0)
            mock_stats.return_value = {'total_assets': 0, 'total_size': 0}
            
            result = export_service.generate_manifest(output_file, format="json")
            
            # Verify file was created
            assert result == output_file.resolve()
            assert output_file.exists()
            
            # Verify empty content
            with open(output_file, 'r') as f:
                manifest = json.load(f)
            
            assert len(manifest['assets']) == 0
    
    def test_search_service_integration(self, export_service):
        """Test integration with search service"""
        # Verify that the export service properly uses the search service
        assert hasattr(export_service, 'search_service')
        assert export_service.search_service is not None
        
        # Test that search service has the expected interface
        assert hasattr(export_service.search_service, 'search')