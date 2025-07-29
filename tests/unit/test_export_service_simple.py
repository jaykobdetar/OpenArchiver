"""
Focused unit tests for ExportService - Testing actual methods
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.models import Archive
from src.core.export import ExportService
from src.core.search import SearchResult


@pytest.fixture
def mock_archive(tmp_path):
    """Create mock archive for testing"""
    archive = Mock(spec=Archive)
    archive.name = "Test Archive"
    archive.root_path = tmp_path / "test_archive"
    archive.index_path = tmp_path / "test_archive" / ".index"
    archive.index_path.mkdir(parents=True, exist_ok=True)
    archive.config = Mock()
    archive.config.name = "Test Archive"
    archive.config.description = "Test description"
    archive.config.id = "test-archive-id"
    archive.config.created_at = "2024-01-01T00:00:00"
    return archive


@pytest.fixture
def export_service(mock_archive):
    """Create ExportService instance"""
    with patch('src.core.search.SearchService') as mock_search_class:
        mock_search_service = Mock()
        mock_search_class.return_value = mock_search_service
        service = ExportService(mock_archive)
        service.search_service = mock_search_service  # Ensure it's set
        return service


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
        )
    ]


@pytest.mark.unit
class TestExportService:
    """Test ExportService functionality"""
    
    def test_initialization(self, mock_archive):
        """Test ExportService initialization"""
        with patch('src.core.search.SearchService'):
            service = ExportService(mock_archive)
            
            assert service.archive == mock_archive
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
    
    @patch('src.core.export.bagit')
    @patch('src.core.export.shutil')
    @patch('src.core.export.tempfile.TemporaryDirectory')
    def test_export_to_bagit_basic(self, mock_tempdir, mock_shutil, mock_bagit, export_service, sample_search_results):
        """Test basic BagIt export functionality"""
        # Mock search service
        export_service.search_service.search = Mock(return_value=(sample_search_results, 1))
        
        # Mock tempfile
        mock_tempdir_context = Mock()
        mock_tempdir_context.__enter__ = Mock(return_value="/tmp/test")
        mock_tempdir_context.__exit__ = Mock(return_value=None)
        mock_tempdir.return_value = mock_tempdir_context
        
        # Mock bagit operations
        mock_bag = Mock()
        mock_bagit.make_bag.return_value = mock_bag
        mock_bag.validate.return_value = None
        
        # Mock path operations
        with patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.is_dir', return_value=False):
            
            output_path = Path("/tmp/test_export.bag")
            result = export_service.export_to_bagit(output_path)
            
            # Verify bagit was called
            mock_bagit.make_bag.assert_called_once()
            mock_bag.validate.assert_called_once()
            assert result == output_path
    
    def test_export_selection_directory(self, export_service, sample_search_results, tmp_path):
        """Test export_selection with directory format"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 1))
        
        output_path = tmp_path / "export_dir"
        asset_ids = ["asset1"]
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2') as mock_copy, \
             patch('src.models.Asset') as mock_asset_class:
            
            # Mock Asset sidecar
            mock_asset = Mock()
            mock_asset.sidecar_path.exists.return_value = False
            mock_asset_class.return_value = mock_asset
            
            result = export_service.export_selection(asset_ids, output_path, format="directory")
            
            assert result == output_path
            # Should call search for the specific asset
            export_service.search_service.search.assert_called()
    
    def test_generate_manifest_json(self, export_service, sample_search_results, tmp_path):
        """Test JSON manifest generation"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 1))
        export_service.search_service.get_statistics = Mock(return_value={"total_assets": 1})
        
        manifest_path = tmp_path / "manifest.json"
        result = export_service.generate_manifest(manifest_path, format="json")
        
        assert result == manifest_path
        assert manifest_path.exists()
        
        # Verify manifest content
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        assert 'archive' in manifest
        assert 'assets' in manifest
        assert 'statistics' in manifest
        assert len(manifest['assets']) == 1
        
        # Check asset data
        asset1 = manifest['assets'][0]
        assert asset1['asset_id'] == 'asset1'
        assert asset1['file_name'] == 'file1.txt'
        assert asset1['file_size'] == 1024
    
    def test_generate_manifest_csv(self, export_service, sample_search_results, tmp_path):
        """Test CSV manifest generation"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 1))
        export_service.search_service.get_statistics = Mock(return_value={"total_assets": 1})
        
        manifest_path = tmp_path / "manifest.csv"
        result = export_service.generate_manifest(manifest_path, format="csv")
        
        assert result == manifest_path
        assert manifest_path.exists()
        
        # Verify CSV content
        content = manifest_path.read_text()
        lines = content.strip().split('\n')
        
        assert len(lines) >= 2  # Header + at least 1 data row
        assert 'asset_id' in lines[0]
        assert 'file_name' in lines[0]
        assert 'asset1' in lines[1]
    
    def test_generate_manifest_unsupported_format(self, export_service):
        """Test manifest generation with unsupported format"""
        with pytest.raises(ValueError, match="Unsupported format"):
            export_service.generate_manifest(Path("/tmp/test.yaml"), format="yaml")
    
    def test_export_selection_unsupported_format(self, export_service):
        """Test export_selection with unsupported format"""
        with pytest.raises(ValueError, match="Unsupported export format"):
            export_service.export_selection(["asset1"], Path("/tmp/test"), format="unknown")
    
    def test_progress_reporting_during_export(self, export_service, sample_search_results):
        """Test that progress is reported during export operations"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 1))
        
        progress_callback = Mock()
        export_service.set_progress_callback(progress_callback)
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2'), \
             patch('src.models.Asset') as mock_asset_class:
            
            mock_asset = Mock()
            mock_asset.sidecar_path.exists.return_value = False
            mock_asset_class.return_value = mock_asset
            
            export_service.export_selection(["asset1"], Path("/tmp/test"), format="directory")
        
        # Should report progress
        assert progress_callback.call_count >= 1
    
    def test_export_selection_preserve_structure(self, export_service, sample_search_results, tmp_path):
        """Test export with structure preservation"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 1))
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.core.export.shutil.copy2') as mock_copy, \
             patch('src.models.Asset') as mock_asset_class:
            
            mock_asset = Mock()
            mock_asset.sidecar_path.exists.return_value = False
            mock_asset_class.return_value = mock_asset
            
            # Test with preserve_structure=True (default)
            export_service.export_selection(["asset1"], tmp_path / "export1", format="directory", preserve_structure=True)
            
            # Test with preserve_structure=False
            export_service.export_selection(["asset1"], tmp_path / "export2", format="directory", preserve_structure=False)
            
            # Both should succeed
            assert mock_copy.call_count >= 2
    
    def test_missing_asset_handling(self, export_service, tmp_path):
        """Test handling of missing assets during export"""
        # Mock search returning no results
        export_service.search_service.search = Mock(return_value=([], 0))
        
        result = export_service.export_selection(["nonexistent"], tmp_path / "export", format="directory")
        
        # Should complete without error
        assert result == tmp_path / "export"
    
    def test_bagit_metadata_defaults(self, export_service, sample_search_results):
        """Test that BagIt export includes default metadata"""
        export_service.search_service.search = Mock(return_value=(sample_search_results, 1))
        
        with patch('src.core.export.bagit') as mock_bagit, \
             patch('src.core.export.shutil'), \
             patch('src.core.export.tempfile.TemporaryDirectory'), \
             patch('pathlib.Path.exists', return_value=False):
            
            mock_bag = Mock()
            mock_bagit.make_bag.return_value = mock_bag
            mock_bag.validate.return_value = None
            
            export_service.export_to_bagit(Path("/tmp/test.bag"))
            
            # Check that metadata was passed to bagit
            mock_bagit.make_bag.assert_called_once()
            call_args = mock_bagit.make_bag.call_args
            metadata_arg = call_args[0][1]  # Second positional argument
            
            # Should have default metadata
            assert 'Source-Organization' in metadata_arg
            assert 'Bagging-Date' in metadata_arg
            assert 'Bag-Software-Agent' in metadata_arg