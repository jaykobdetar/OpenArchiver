"""
Enhanced unit tests for Ingestion Service - Simplified to match actual implementation
"""

import pytest
import tempfile
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.core.ingestion import FileIngestionService
from src.models import Archive, Asset, AssetMetadata


@pytest.fixture
def mock_archive(tmp_path):
    """Create mock archive for testing with real directory structure"""
    archive = Mock(spec=Archive)
    
    # Create real directory structure
    archive_root = tmp_path / "test_archive"
    archive_root.mkdir()
    assets_dir = archive_root / "assets"
    assets_dir.mkdir()
    
    archive.root_path = archive_root
    archive.assets_path = assets_dir
    archive.config = Mock()
    archive.config.name = "Test Archive"
    archive.config.organization_schema = {"structure": "year/month/type", "preserve_original_names": True}
    return archive


@pytest.fixture
def ingestion_service(mock_archive):
    """Create FileIngestionService instance for testing"""
    return FileIngestionService(mock_archive)


@pytest.fixture
def sample_files(tmp_path):
    """Create sample files for ingestion testing"""
    files = {}
    
    # Text file
    text_file = tmp_path / "document.txt"
    text_file.write_text("This is a test document.")
    files['text'] = text_file
    
    # Image file (fake JPEG header)
    image_file = tmp_path / "photo.jpg"
    image_file.write_bytes(b'\\xff\\xd8\\xff\\xe0\\x00\\x10JFIF')
    files['image'] = image_file
    
    # Binary file
    binary_file = tmp_path / "data.bin"
    binary_file.write_bytes(b'\\x00\\x01\\x02\\x03\\x04\\x05')
    files['binary'] = binary_file
    
    # Empty file
    empty_file = tmp_path / "empty.txt"
    empty_file.touch()
    files['empty'] = empty_file
    
    return files


@pytest.mark.unit
class TestFileIngestionService:
    """Test FileIngestionService functionality"""
    
    def test_ingestion_service_initialization(self, ingestion_service, mock_archive):
        """Test FileIngestionService initializes correctly"""
        assert ingestion_service.archive == mock_archive
        assert ingestion_service.progress_callback is None
    
    def test_set_progress_callback(self, ingestion_service):
        """Test setting progress callback"""
        callback = Mock()
        ingestion_service.set_progress_callback(callback)
        assert ingestion_service.progress_callback == callback
    
    def test_report_progress_with_callback(self, ingestion_service):
        """Test progress reporting with callback set"""
        callback = Mock()
        ingestion_service.set_progress_callback(callback)
        
        ingestion_service._report_progress(5, 10, "Ingesting file")
        callback.assert_called_once_with(5, 10, "Ingesting file")
    
    def test_report_progress_without_callback(self, ingestion_service):
        """Test progress reporting without callback (should not crash)"""
        # Should not raise exception
        ingestion_service._report_progress(5, 10, "Ingesting file")
    
    def test_ingest_single_file_basic(self, ingestion_service, sample_files):
        """Test basic single file ingestion"""
        text_file = sample_files['text']
        
        # Mock the organization method to return a simple path
        with patch.object(ingestion_service, '_organize_by_schema') as mock_organize:
            mock_organize.return_value = ingestion_service.archive.assets_path / "test_dir"
            
            asset = ingestion_service.ingest_file(text_file)
            
            # Verify asset was created and has expected properties
            assert asset is not None
            assert asset.metadata is not None
            assert asset.metadata.checksum_sha256 is not None
            assert asset.metadata.original_path == str(text_file)
    
    def test_ingest_single_file_with_profile(self, ingestion_service, sample_files):
        """Test single file ingestion with profile"""
        text_file = sample_files['text']
        mock_profile = Mock()
        mock_profile.id = "test_profile"
        
        # Mock the organization method to return a simple path
        with patch.object(ingestion_service, '_organize_by_schema') as mock_organize:
            mock_organize.return_value = ingestion_service.archive.assets_path / "test_dir"
            
            asset = ingestion_service.ingest_file(text_file, profile=mock_profile)
            
            # Should create asset with profile
            assert asset is not None
            assert asset.metadata.profile_id == mock_profile.id
    
    def test_ingest_single_file_with_custom_metadata(self, ingestion_service, sample_files):
        """Test single file ingestion with custom metadata"""
        text_file = sample_files['text']
        custom_metadata = {"title": "Test Document", "tags": ["important", "test"]}
        
        # Mock the organization method to return a simple path
        with patch.object(ingestion_service, '_organize_by_schema') as mock_organize:
            mock_organize.return_value = ingestion_service.archive.assets_path / "test_dir"
            
            asset = ingestion_service.ingest_file(text_file, custom_metadata=custom_metadata)
            
            # Should create asset with custom metadata
            assert asset is not None
            assert asset.metadata.custom_metadata == custom_metadata
    
    def test_ingest_missing_file(self, ingestion_service):
        """Test ingesting non-existent file"""
        missing_file = Path("/nonexistent/file.txt")
        
        with pytest.raises(FileNotFoundError):
            ingestion_service.ingest_file(missing_file)
    
    def test_ingest_directory_basic(self, ingestion_service, tmp_path):
        """Test basic directory ingestion"""
        # Create test directory with files
        test_dir = tmp_path / "test_directory" 
        test_dir.mkdir()
        
        (test_dir / "file1.txt").write_text("Content 1")
        (test_dir / "file2.txt").write_text("Content 2")
        
        with patch.object(ingestion_service, 'ingest_file') as mock_ingest:
            mock_ingest.return_value = Mock(spec=Asset)
            
            assets = ingestion_service.ingest_directory(test_dir)
            
            # Should ingest all files
            assert len(assets) >= 2
            assert mock_ingest.call_count >= 2
    
    def test_ingest_directory_empty(self, ingestion_service, tmp_path):
        """Test ingesting empty directory"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        assets = ingestion_service.ingest_directory(empty_dir)
        assert len(assets) == 0
    
    def test_ingest_directory_nonexistent(self, ingestion_service):
        """Test ingesting non-existent directory"""
        missing_dir = Path("/nonexistent/directory")
        
        with pytest.raises((FileNotFoundError, OSError)):
            ingestion_service.ingest_directory(missing_dir)
    
    def test_organize_by_schema_method_exists(self, ingestion_service, sample_files):
        """Test that _organize_by_schema method exists and works"""
        text_file = sample_files['text']
        
        # Method should exist and return a path
        org_path = ingestion_service._organize_by_schema(text_file)
        assert isinstance(org_path, Path)
        # Should create a path under assets directory
        assert str(org_path).startswith(str(ingestion_service.archive.assets_path))
    
    def test_handle_duplicate_method_exists(self, ingestion_service, tmp_path):
        """Test that _handle_duplicate method exists and works"""
        test_path = tmp_path / "test.txt"
        test_path.touch()
        
        # Method should exist and return a path
        result_path = ingestion_service._handle_duplicate(test_path)
        assert isinstance(result_path, Path)
        # Should be different from original if original exists
        assert result_path != test_path