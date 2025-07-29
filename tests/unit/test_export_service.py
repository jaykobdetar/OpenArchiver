"""
Unit tests for ExportService with comprehensive coverage
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from src.models import Archive, Asset, AssetMetadata
from src.core.export import ExportService
from src.core.search import SearchResult


@pytest.fixture
def sample_archive(tmp_path):
    """Create a sample archive for testing"""
    from src.models import Archive
    
    archive_path = tmp_path / "test_archive"
    archive_path.mkdir()
    (archive_path / "assets").mkdir()
    (archive_path / "profiles").mkdir()
    (archive_path / ".index").mkdir()
    
    # Create archive.json
    archive_config = {
        "name": "Test Archive",
        "description": "Test archive for export testing",
        "version": "1.0",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
    }
    
    with open(archive_path / "archive.json", "w") as f:
        json.dump(archive_config, f)
    
    return Archive.load(archive_path)


@pytest.fixture
def export_service(sample_archive):
    """Create ExportService instance"""
    return ExportService(sample_archive)


@pytest.fixture
def sample_search_results():
    """Create sample search results for testing"""
    return [
        SearchResult(
            asset_id="asset1",
            archive_path="assets/documents/file1.txt",
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
            archive_path="assets/images/photo.jpg",
            file_name="photo.jpg",
            file_size=2048,
            mime_type="image/jpeg",
            checksum_sha256="def456",
            profile_id="photos",
            created_at="2024-01-02T00:00:00",
            custom_metadata={"title": "Photo 1", "location": "Paris"}
        )
    ]


@pytest.fixture
def created_assets(sample_archive, tmp_path):
    """Create actual asset files for testing"""
    assets_dir = sample_archive.root_path / "assets"
    
    # Create document
    doc_dir = assets_dir / "documents"
    doc_dir.mkdir(parents=True, exist_ok=True)
    doc_file = doc_dir / "file1.txt"
    doc_file.write_text("This is a test document")
    
    # Create sidecar
    sidecar_file = doc_file.parent / f"{doc_file.name}.metadata.json"
    sidecar_data = {
        "asset_id": "asset1",
        "checksum_sha256": "abc123",
        "custom_metadata": {"title": "Document 1", "tags": ["important"]}
    }
    sidecar_file.write_text(json.dumps(sidecar_data, indent=2))
    
    # Create image
    img_dir = assets_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    img_file = img_dir / "photo.jpg"
    img_file.write_bytes(b"fake jpeg data")
    
    # Create sidecar
    img_sidecar = img_file.parent / f"{img_file.name}.metadata.json"
    img_sidecar_data = {
        "asset_id": "asset2",
        "checksum_sha256": "def456",
        "custom_metadata": {"title": "Photo 1", "location": "Paris"}
    }
    img_sidecar.write_text(json.dumps(img_sidecar_data, indent=2))
    
    return [doc_file, img_file]


@pytest.mark.unit
class TestExportService:
    """Test ExportService functionality"""
    
    def test_initialization(self, sample_archive):
        """Test ExportService initialization"""
        service = ExportService(sample_archive)
        
        assert service.archive == sample_archive
        assert service.search_service is not None
        assert service.progress_callback is None
    
    def test_set_progress_callback(self, export_service):
        """Test setting progress callback"""
        callback = Mock()
        export_service.set_progress_callback(callback)
        
        assert export_service.progress_callback == callback
    
    def test_report_progress(self, export_service):
        """Test progress reporting"""
        callback = Mock()
        export_service.set_progress_callback(callback)
        
        export_service._report_progress(50, 100, "Testing progress")
        callback.assert_called_once_with(50, 100, "Testing progress")
    
    def test_report_progress_no_callback(self, export_service):
        """Test progress reporting with no callback set"""
        # Should not raise error
        export_service._report_progress(50, 100, "Testing progress")
    
    @patch('src.core.export.bagit')
    @patch('src.core.export.shutil')
    def test_export_to_bagit_basic(self, mock_shutil, mock_bagit, export_service, sample_search_results, tmp_path):
        """Test basic BagIt export functionality"""
        # Mock search service
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        # Mock bagit operations
        mock_bag = Mock()
        mock_bagit.make_bag.return_value = mock_bag
        mock_bag.validate.return_value = None
        
        # Mock file operations
        mock_shutil.copy2 = Mock()
        mock_shutil.move = Mock()
        
        output_path = tmp_path / "test_export.bag"
        
        # Mock file existence
        with patch('pathlib.Path.exists', return_value=True):
            result = export_service.export_to_bagit(output_path)
        
        # Verify search was called
        export_service.search_service.search.assert_called_once_with(limit=10000)
        
        # Verify bagit was called
        mock_bagit.make_bag.assert_called_once()
        mock_bag.validate.assert_called_once()
        
        # Verify files were copied
        assert mock_shutil.copy2.call_count >= 2  # Files + sidecars
    
    @patch('src.core.export.bagit')
    def test_export_to_bagit_with_filters(self, mock_bagit, export_service, sample_search_results):
        """Test BagIt export with search filters"""
        export_service.search_service.search = Mock(return_value=(sample_search_results[:1], 1))
        
        mock_bag = Mock()
        mock_bagit.make_bag.return_value = mock_bag
        mock_bag.validate.return_value = None
        
        filters = {"mime_type": "text/plain"}
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil'), \
             patch('src.core.export.tempfile.TemporaryDirectory'):
            
            export_service.export_to_bagit(Path("/tmp/test.bag"), search_filters=filters)
        
        # Verify search was called with filters
        export_service.search_service.search.assert_called_once_with(filters=filters, limit=10000)
    
    @patch('src.core.export.bagit')
    def test_export_to_bagit_with_custom_metadata(self, mock_bagit, export_service, sample_search_results):
        """Test BagIt export with custom metadata"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        mock_bag = Mock()
        mock_bagit.make_bag.return_value = mock_bag
        mock_bag.validate.return_value = None
        
        custom_metadata = {
            'Source-Organization': 'Custom Org',
            'Contact-Name': 'John Doe',
            'External-Description': 'Custom export'
        }
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil'), \
             patch('src.core.export.tempfile.TemporaryDirectory'):
            
            export_service.export_to_bagit(Path("/tmp/test.bag"), metadata=custom_metadata)
        
        # Verify bagit was called with custom metadata
        mock_bagit.make_bag.assert_called_once()
        call_args = mock_bagit.make_bag.call_args
        metadata_arg = call_args[1]['metadata']
        
        assert metadata_arg['Source-Organization'] == 'Custom Org'
        assert metadata_arg['Contact-Name'] == 'John Doe'
        assert metadata_arg['External-Description'] == 'Custom export'
        assert 'Bagging-Date' in metadata_arg
        assert 'Bag-Software-Agent' in metadata_arg
    
    @patch('src.core.export.bagit')
    def test_export_to_bagit_custom_checksums(self, mock_bagit, export_service, sample_search_results):
        """Test BagIt export with custom checksum algorithms"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        mock_bag = Mock()
        mock_bagit.make_bag.return_value = mock_bag
        mock_bag.validate.return_value = None
        
        checksums = ['sha256', 'md5']
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil'), \
             patch('src.core.export.tempfile.TemporaryDirectory'):
            
            export_service.export_to_bagit(Path("/tmp/test.bag"), checksums=checksums)
        
        # Verify bagit was called with custom checksums
        mock_bagit.make_bag.assert_called_once()
        call_args = mock_bagit.make_bag.call_args
        assert call_args[1]['checksums'] == checksums
    
    def test_export_to_bagit_missing_source_files(self, export_service, sample_search_results, tmp_path):
        """Test BagIt export handling missing source files"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        with patch('src.core.export.bagit') as mock_bagit, \
             patch('src.core.export.shutil') as mock_shutil, \
             patch('pathlib.Path.exists', return_value=False):  # Files don't exist
            
            mock_bag = Mock()
            mock_bagit.make_bag.return_value = mock_bag
            mock_bag.validate.return_value = None
            
            export_service.export_to_bagit(tmp_path / "test.bag")
            
            # Should still create bag but skip missing files
            mock_bagit.make_bag.assert_called_once()
            # copy2 should not be called for missing files
            mock_shutil.copy2.assert_not_called()
    
    @patch('src.core.export.bagit')
    def test_export_to_bagit_progress_reporting(self, mock_bagit, export_service, sample_search_results):
        """Test progress reporting during BagIt export"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        # Set up progress callback
        progress_callback = Mock()
        export_service.set_progress_callback(progress_callback)
        
        mock_bag = Mock()
        mock_bagit.make_bag.return_value = mock_bag
        mock_bag.validate.return_value = None
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil'), \
             patch('src.core.export.tempfile.TemporaryDirectory'):
            
            export_service.export_to_bagit(Path("/tmp/test.bag"))
        
        # Verify progress was reported
        assert progress_callback.call_count >= 2  # Once per file
        
        # Check progress calls
        calls = progress_callback.call_args_list
        assert calls[0] == call(1, 2, "Copying file1.txt")
        assert calls[1] == call(2, 2, "Copying photo.jpg")
    
    def test_export_selection_directory(self, export_service, sample_search_results, tmp_path):
        """Test directory export using export_selection method"""
        export_service.search_service.search = Mock(return_value=(sample_search_results[:1], 1))
        
        output_path = tmp_path / "export_dir"
        asset_ids = ["asset1"]
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2') as mock_copy:
            
            result = export_service.export_selection(asset_ids, output_path, format="directory")
        
        assert result == output_path
        # Should copy files and sidecars
        assert mock_copy.call_count >= 1
    
    def test_export_to_directory_with_filters(self, export_service, sample_search_results, tmp_path):
        """Test directory export with filters"""
        filtered_results = [sample_search_results[0]]
        export_service.search_service.search = Mock(return_value=(filtered_results, 1))
        
        filters = {"profile_id": "documents"}
        output_path = tmp_path / "filtered_export"
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2'):
            
            export_service.export_to_directory(output_path, search_filters=filters)
        
        export_service.search_service.search.assert_called_once_with(filters=filters, limit=10000)
    
    def test_export_to_directory_preserve_structure(self, export_service, sample_search_results, tmp_path):
        """Test directory export preserves folder structure"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        output_path = tmp_path / "structured_export"
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2') as mock_copy, \
             patch('pathlib.Path.mkdir') as mock_mkdir:
            
            export_service.export_to_directory(output_path, preserve_structure=True)
        
        # Should create directory structure
        mock_mkdir.assert_called()
        
        # Should copy to preserved paths
        mock_copy.assert_called()
    
    def test_export_to_directory_flatten_structure(self, export_service, sample_search_results, tmp_path):
        """Test directory export with flattened structure"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        output_path = tmp_path / "flat_export"
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2') as mock_copy:
            
            export_service.export_to_directory(output_path, preserve_structure=False)
        
        # Files should be copied to root of export directory
        mock_copy.assert_called()
    
    def test_export_to_directory_progress_reporting(self, export_service, sample_search_results, tmp_path):
        """Test progress reporting during directory export"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        progress_callback = Mock()
        export_service.set_progress_callback(progress_callback)
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2'):
            
            export_service.export_to_directory(tmp_path / "export_dir")
        
        # Verify progress was reported
        assert progress_callback.call_count >= 2
    
    def test_export_to_directory_error_handling(self, export_service, sample_search_results, tmp_path):
        """Test directory export error handling"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        output_path = tmp_path / "error_export"
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2', side_effect=PermissionError("Permission denied")):
            
            # Should handle errors gracefully
            with pytest.raises(Exception):
                export_service.export_to_directory(output_path)
    
    def test_generate_manifest_json(self, export_service, sample_search_results, tmp_path):
        """Test JSON manifest generation"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        manifest_path = tmp_path / "manifest.json"
        result = export_service.generate_manifest(manifest_path, format="json")
        
        assert result == manifest_path
        assert manifest_path.exists()
        
        # Verify manifest content
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        assert 'archive' in manifest
        assert 'assets' in manifest
        assert 'export_info' in manifest
        assert len(manifest['assets']) == 2
        
        # Check asset data
        asset1 = manifest['assets'][0]
        assert asset1['asset_id'] == 'asset1'
        assert asset1['file_name'] == 'file1.txt'
        assert asset1['file_size'] == 1024
    
    def test_generate_manifest_csv(self, export_service, sample_search_results, tmp_path):
        """Test CSV manifest generation"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        manifest_path = tmp_path / "manifest.csv"
        result = export_service.generate_manifest(manifest_path, format="csv")
        
        assert result == manifest_path
        assert manifest_path.exists()
        
        # Verify CSV content
        content = manifest_path.read_text()
        lines = content.strip().split('\n')
        
        assert len(lines) == 3  # Header + 2 data rows
        assert 'asset_id' in lines[0]
        assert 'file_name' in lines[0]
        assert 'asset1' in lines[1]
        assert 'asset2' in lines[2]
    
    def test_generate_manifest_xml(self, export_service, sample_search_results, tmp_path):
        """Test XML manifest generation"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        manifest_path = tmp_path / "manifest.xml"
        result = export_service.generate_manifest(manifest_path, format="xml")
        
        assert result == manifest_path
        assert manifest_path.exists()
        
        # Verify XML content
        content = manifest_path.read_text()
        assert '<?xml version="1.0"' in content
        assert '<archive>' in content
        assert '<assets>' in content
        assert '<asset>' in content
    
    def test_generate_manifest_unsupported_format(self, export_service, tmp_path):
        """Test manifest generation with unsupported format"""
        manifest_path = tmp_path / "manifest.yaml"
        
        with pytest.raises(ValueError, match="Unsupported manifest format"):
            export_service.generate_manifest(manifest_path, format="yaml")
    
    def test_generate_manifest_with_filters(self, export_service, sample_search_results, tmp_path):
        """Test manifest generation with search filters"""
        filtered_results = [sample_search_results[0]]
        export_service.search_service.search = Mock(return_value=(filtered_results, 1))
        
        filters = {"mime_type": "text/plain"}
        manifest_path = tmp_path / "filtered_manifest.json"
        
        export_service.generate_manifest(manifest_path, format="json", search_filters=filters)
        
        # Verify search was called with filters
        export_service.search_service.search.assert_called_once_with(filters=filters, limit=10000)
        
        # Verify manifest contains only filtered results
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        assert len(manifest['assets']) == 1
        assert manifest['assets'][0]['asset_id'] == 'asset1'
    
    def test_validate_export_path_valid(self, export_service, tmp_path):
        """Test export path validation with valid path"""
        valid_path = tmp_path / "valid_export"
        valid_path.mkdir()
        
        # Should not raise exception
        export_service._validate_export_path(valid_path)
    
    def test_validate_export_path_parent_not_exists(self, export_service):
        """Test export path validation with non-existent parent"""
        invalid_path = Path("/non/existent/path/export")
        
        with pytest.raises(ValueError, match="Parent directory does not exist"):
            export_service._validate_export_path(invalid_path)
    
    def test_validate_export_path_not_writable(self, export_service, tmp_path):
        """Test export path validation with non-writable parent"""
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        
        with patch('os.access', return_value=False):
            export_path = read_only_dir / "export"
            
            with pytest.raises(ValueError, match="Parent directory is not writable"):
                export_service._validate_export_path(export_path)
    
    def test_validate_export_path_file_exists(self, export_service, tmp_path):
        """Test export path validation with existing file"""
        existing_file = tmp_path / "existing_file.txt"
        existing_file.write_text("existing content")
        
        with pytest.raises(ValueError, match="Export path already exists"):
            export_service._validate_export_path(existing_file)
    
    @patch('src.core.export.bagit.BagError')
    def test_export_to_bagit_validation_error(self, mock_bag_error, export_service, sample_search_results):
        """Test BagIt export with bag validation error"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        with patch('src.core.export.bagit') as mock_bagit:
            mock_bag = Mock()
            mock_bagit.make_bag.return_value = mock_bag
            mock_bag.validate.side_effect = mock_bag_error("Bag validation failed")
            
            with patch('pathlib.Path.exists', return_value=True), \
                 patch('src.core.export.shutil'), \
                 patch('src.core.export.tempfile.TemporaryDirectory'):
                
                with pytest.raises(Exception):
                    export_service.export_to_bagit(Path("/tmp/test.bag"))
    
    def test_export_statistics_tracking(self, export_service, sample_search_results, tmp_path):
        """Test export statistics tracking"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2') as mock_copy:
            
            stats = export_service.export_to_directory(tmp_path / "stats_export", collect_stats=True)
        
        # Should return statistics
        assert 'files_exported' in stats
        assert 'total_size' in stats
        assert 'export_duration' in stats
        assert stats['files_exported'] == 2
    
    def test_export_with_large_dataset(self, export_service, tmp_path):
        """Test export performance with large dataset"""
        # Create large number of search results
        large_results = []
        for i in range(1000):
            large_results.append(SearchResult(
                asset_id=f"asset{i}",
                archive_path=f"assets/file{i}.txt",
                file_name=f"file{i}.txt",
                file_size=1024,
                mime_type="text/plain",
                checksum_sha256=f"hash{i}",
                profile_id="documents",
                created_at="2024-01-01T00:00:00",
                custom_metadata={"title": f"File {i}"}
            ))
        
        export_service.search_service.search = Mock(return_value=(large_results, 1000))
        
        progress_callback = Mock()
        export_service.set_progress_callback(progress_callback)
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2'):
            
            export_service.export_to_directory(tmp_path / "large_export")
        
        # Should handle large datasets efficiently
        assert progress_callback.call_count == 1000
    
    def test_export_error_recovery(self, export_service, sample_search_results, tmp_path):
        """Test export error recovery and cleanup"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 2))
        
        def copy_side_effect(src, dst):
            if "file1.txt" in str(src):
                raise IOError("Disk full")
            return Mock()
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2', side_effect=copy_side_effect):
            
            with pytest.raises(IOError):
                export_service.export_to_directory(tmp_path / "error_export")
        
        # Should clean up partial exports on error
        export_dir = tmp_path / "error_export"
        if export_dir.exists():
            # Should be empty or removed
            assert len(list(export_dir.iterdir())) == 0