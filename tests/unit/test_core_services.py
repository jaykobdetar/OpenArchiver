"""
Unit tests for Archive Tool core services
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.core.ingestion import FileIngestionService
from src.core.indexing import IndexingService
from src.core.search import SearchService
from src.core.integrity import IntegrityService, IntegrityReport
from src.core.export import ExportService
from src.models import Asset, AssetMetadata


@pytest.mark.unit
class TestFileIngestionService:
    """Test FileIngestionService class"""
    
    def test_init(self, sample_archive):
        service = FileIngestionService(sample_archive)
        assert service.archive == sample_archive
        assert service.progress_callback is None
    
    def test_set_progress_callback(self, sample_archive):
        service = FileIngestionService(sample_archive)
        callback = Mock()
        
        service.set_progress_callback(callback)
        assert service.progress_callback == callback
    
    def test_ingest_single_file(self, sample_archive, sample_files, sample_profile):
        service = FileIngestionService(sample_archive)
        test_file = sample_files[0]  # First text file
        
        custom_metadata = {"title": "Test Document", "category": "Document"}
        
        asset = service.ingest_file(
            test_file,
            profile=sample_profile,
            custom_metadata=custom_metadata
        )
        
        assert asset is not None
        assert asset.metadata is not None
        assert asset.metadata.original_path == str(test_file)
        assert asset.metadata.profile_id == sample_profile.id
        assert asset.metadata.custom_metadata["title"] == "Test Document"
        assert asset.metadata.checksum_sha256 is not None
        assert len(asset.metadata.checksum_sha256) == 64  # SHA-256
        
        # Verify file was copied to archive
        archive_file = sample_archive.root_path / asset.metadata.archive_path
        assert archive_file.exists()
        
        # Verify sidecar metadata file exists
        assert asset.sidecar_path.exists()
    
    def test_ingest_nonexistent_file_raises_error(self, sample_archive):
        service = FileIngestionService(sample_archive)
        nonexistent_file = Path("/nonexistent/file.txt")
        
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            service.ingest_file(nonexistent_file)
    
    def test_ingest_directory_non_recursive(self, sample_archive, sample_files, sample_profile):
        service = FileIngestionService(sample_archive)
        source_dir = sample_files[0].parent  # Directory containing sample files
        
        custom_metadata = {"category": "Document"}
        
        assets = service.ingest_directory(
            source_dir,
            profile=sample_profile,
            custom_metadata=custom_metadata,
            recursive=False
        )
        
        assert len(assets) == len(sample_files)
        
        for asset in assets:
            assert asset.metadata.profile_id == sample_profile.id
            assert asset.metadata.custom_metadata["category"] == "Document"
            assert asset.metadata.checksum_sha256 is not None
    
    def test_ingest_directory_with_progress(self, sample_archive, sample_files, sample_profile):
        service = FileIngestionService(sample_archive)
        progress_calls = []
        
        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))
        
        service.set_progress_callback(progress_callback)
        source_dir = sample_files[0].parent
        
        assets = service.ingest_directory(source_dir, profile=sample_profile)
        
        assert len(progress_calls) == len(sample_files)
        assert progress_calls[0][1] == len(sample_files)  # Total should be consistent
        assert progress_calls[-1][0] == len(sample_files)  # Last current should equal total
    
    def test_organize_by_schema_date_type(self, sample_archive, sample_files):
        service = FileIngestionService(sample_archive)
        test_file = sample_files[0]  # Text file
        
        # Mock datetime to get predictable results
        with patch('src.core.ingestion.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.year = 2024
            mock_now.month = 1
            mock_now.day = 15
            mock_datetime.now.return_value = mock_now
            
            organized_path = service._organize_by_schema(test_file)
            
            expected_path = sample_archive.assets_path / "2024" / "01" / "text"
            assert organized_path == expected_path
    
    def test_handle_duplicate_filename(self, sample_archive, sample_files):
        service = FileIngestionService(sample_archive)
        
        # Create a file in the assets directory
        target_dir = sample_archive.assets_path / "test"
        target_dir.mkdir(parents=True)
        existing_file = target_dir / "document.txt"
        existing_file.write_text("existing content")
        
        # Test duplicate handling
        duplicate_path = service._handle_duplicate(existing_file)
        
        assert duplicate_path.name == "document_1.txt"
        assert duplicate_path.parent == existing_file.parent


@pytest.mark.unit
class TestIndexingService:
    """Test IndexingService class"""
    
    def test_init(self, sample_archive):
        service = IndexingService(sample_archive)
        assert service.archive == sample_archive
        assert service.db_path == sample_archive.index_path / "index.db"
        
        # Verify database tables were created
        with service._get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [row[0] for row in tables]
            
            assert "assets" in table_names
            assert "asset_metadata" in table_names
            assert "assets_fts" in table_names
    
    def test_index_asset(self, sample_archive, sample_files, sample_profile):
        # First ingest a file
        ingestion = FileIngestionService(sample_archive)
        test_file = sample_files[0]
        custom_metadata = {"title": "Test File", "category": "Document"}
        
        asset = ingestion.ingest_file(test_file, profile=sample_profile, custom_metadata=custom_metadata)
        
        # Now test indexing
        indexing = IndexingService(sample_archive)
        result = indexing.index_asset(asset)
        
        assert result is True
        
        # Verify asset was indexed
        with indexing._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM assets WHERE asset_id = ?", 
                (asset.metadata.asset_id,)
            ).fetchone()
            
            assert row is not None
            assert row['asset_id'] == asset.metadata.asset_id
            assert row['file_name'] == Path(asset.metadata.archive_path).name
            
            # Verify custom metadata was indexed
            metadata_rows = conn.execute(
                "SELECT * FROM asset_metadata WHERE asset_id = ?",
                (asset.metadata.asset_id,)
            ).fetchall()
            
            assert len(metadata_rows) == 2  # title and category
            field_names = [row['field_name'] for row in metadata_rows]
            assert "title" in field_names
            assert "category" in field_names
    
    def test_remove_asset(self, sample_archive):
        indexing = IndexingService(sample_archive)
        test_asset_id = "test-asset-123"
        
        # Insert test asset
        with indexing._get_connection() as conn:
            conn.execute("""
                INSERT INTO assets (asset_id, original_path, archive_path, file_name, file_size, created_at, updated_at, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (test_asset_id, "/test/path", "test/path", "test.txt", 100, "2024-01-01", "2024-01-01", "2024-01-01"))
            conn.commit()
        
        # Remove asset
        result = indexing.remove_asset(test_asset_id)
        assert result is True
        
        # Verify asset was removed
        with indexing._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM assets WHERE asset_id = ?",
                (test_asset_id,)
            ).fetchone()
            
            assert row is None
    
    def test_get_statistics(self, sample_archive):
        indexing = IndexingService(sample_archive)
        
        # Insert test data
        with indexing._get_connection() as conn:
            conn.execute("""
                INSERT INTO assets (asset_id, original_path, archive_path, file_name, file_size, mime_type, profile_id, created_at, updated_at, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("asset1", "/test/1", "test/1", "test1.txt", 100, "text/plain", "profile1", "2024-01-01", "2024-01-01", "2024-01-01"))
            
            conn.execute("""
                INSERT INTO assets (asset_id, original_path, archive_path, file_name, file_size, mime_type, profile_id, created_at, updated_at, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("asset2", "/test/2", "test/2", "test2.jpg", 200, "image/jpeg", "profile1", "2024-01-01", "2024-01-01", "2024-01-01"))
            
            conn.commit()
        
        stats = indexing.get_statistics()
        
        assert stats['total_assets'] == 2
        assert stats['total_size'] == 300
        assert 'text/plain' in stats['by_type']
        assert 'image/jpeg' in stats['by_type']
        assert stats['by_type']['text/plain']['count'] == 1
        assert stats['by_profile']['profile1'] == 2


@pytest.mark.unit
class TestSearchService:
    """Test SearchService class"""
    
    def test_init(self, sample_archive):
        service = SearchService(sample_archive)
        assert service.archive == sample_archive
        assert service.db_path == sample_archive.index_path / "index.db"
    
    def test_search_all_assets(self, archive_with_assets):
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        results, total = search.search()
        
        assert total == len(assets)
        assert len(results) == len(assets)
        
        # Verify result structure
        result = results[0]
        assert hasattr(result, 'asset_id')
        assert hasattr(result, 'archive_path')
        assert hasattr(result, 'file_name')
        assert hasattr(result, 'custom_metadata')
    
    def test_search_with_limit(self, archive_with_assets):
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        results, total = search.search(limit=2)
        
        assert total == len(assets)  # Total count should be unchanged
        assert len(results) == 2     # But only 2 results returned
    
    def test_search_with_filters(self, archive_with_assets):
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Search by MIME type
        results, total = search.search(filters={'mime_type': 'text/plain'})
        
        # Should find the text files (3 documents + 1 json = 4, but json might have different mime type)
        assert total >= 3  # At least the 3 text documents
        
        for result in results:
            assert result.mime_type == 'text/plain'
    
    def test_search_by_custom_metadata(self, archive_with_assets):
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Search by category
        results, total = search.search(filters={'category': 'Document'})
        
        assert total > 0
        for result in results:
            assert result.custom_metadata.get('category') == 'Document'
    
    def test_search_by_checksum(self, archive_with_assets):
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Get checksum of first asset
        first_asset = assets[0]
        checksum = first_asset.metadata.checksum_sha256
        
        result = search.search_by_checksum(checksum)
        
        assert result is not None
        assert result.checksum_sha256 == checksum
        assert result.asset_id == first_asset.metadata.asset_id
    
    def test_search_nonexistent_checksum(self, archive_with_assets):
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        result = search.search_by_checksum("nonexistent_checksum")
        assert result is None
    
    def test_get_metadata_fields(self, archive_with_assets):
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        fields = search.get_metadata_fields()
        
        assert len(fields) > 0
        
        # Should find our test fields
        field_names = [field['name'] for field in fields]
        assert 'title' in field_names
        assert 'category' in field_names


@pytest.mark.unit
class TestIntegrityService:
    """Test IntegrityService class"""
    
    def test_init(self, sample_archive):
        service = IntegrityService(sample_archive)
        assert service.archive == sample_archive
        assert service.progress_callback is None
    
    def test_set_progress_callback(self, sample_archive):
        service = IntegrityService(sample_archive)
        callback = Mock()
        
        service.set_progress_callback(callback)
        assert service.progress_callback == callback
    
    def test_verify_single_asset_success(self, archive_with_assets):
        archive, assets = archive_with_assets
        service = IntegrityService(archive)
        
        first_asset = assets[0]
        result = service.verify_single(first_asset.metadata.asset_id)
        
        assert result['asset_id'] == first_asset.metadata.asset_id
        assert result['status'] == 'verified'
        assert 'verified_at' in result
    
    def test_verify_single_nonexistent_asset(self, sample_archive):
        service = IntegrityService(sample_archive)
        
        result = service.verify_single("nonexistent-asset-id")
        
        assert result['asset_id'] == "nonexistent-asset-id"
        assert result['status'] == 'not_found'
        assert 'message' in result
    
    def test_verify_single_missing_file(self, archive_with_assets):
        """Test verification of an asset whose file has been deleted"""
        archive, assets = archive_with_assets
        service = IntegrityService(archive)
        
        # Delete the actual asset file but leave it in the index
        first_asset = assets[0]
        asset_path = archive.root_path / first_asset.metadata.archive_path
        asset_path.unlink()  # Delete the file
        
        result = service.verify_single(first_asset.metadata.asset_id)
        
        assert result['asset_id'] == first_asset.metadata.asset_id
        assert result['status'] == 'missing'
        assert 'verified_at' in result
    
    def test_verify_single_corrupted_file(self, archive_with_assets):
        """Test verification of a corrupted asset file"""
        archive, assets = archive_with_assets
        service = IntegrityService(archive)
        
        # Corrupt the asset file by changing its content
        first_asset = assets[0]
        asset_path = archive.root_path / first_asset.metadata.archive_path
        asset_path.write_text("CORRUPTED CONTENT - This should cause checksum mismatch")
        
        result = service.verify_single(first_asset.metadata.asset_id)
        
        assert result['asset_id'] == first_asset.metadata.asset_id
        assert result['status'] == 'corrupted'
        assert 'verified_at' in result
    
    def test_verify_single_missing_metadata(self, archive_with_assets):
        """Test verification of an asset with missing metadata"""
        archive, assets = archive_with_assets
        service = IntegrityService(archive)
        
        # Delete the metadata file but leave the asset file
        first_asset = assets[0]
        metadata_path = first_asset.sidecar_path
        metadata_path.unlink()  # Delete the metadata file
        
        result = service.verify_single(first_asset.metadata.asset_id)
        
        assert result['asset_id'] == first_asset.metadata.asset_id
        assert result['status'] == 'no_metadata'
        assert 'verified_at' in result
    
    def test_verify_all_assets(self, archive_with_assets):
        archive, assets = archive_with_assets
        service = IntegrityService(archive)
        
        report = service.verify_all(max_workers=1)  # Single thread for testing
        
        assert isinstance(report, IntegrityReport)
        assert report.total_assets == len(assets)
        assert report.verified_assets > 0
        assert report.success_rate > 0
        assert report.duration >= 0
    
    def test_verify_all_with_corrupted_assets(self, archive_with_assets):
        """Test verify_all with mixed asset states (verified, corrupted, missing)"""
        archive, assets = archive_with_assets
        service = IntegrityService(archive)
        
        # Corrupt one asset
        corrupted_asset = assets[0]
        corrupted_path = archive.root_path / corrupted_asset.metadata.archive_path
        corrupted_path.write_text("CORRUPTED")
        
        # Delete another asset file
        missing_asset = assets[1] if len(assets) > 1 else None
        if missing_asset:
            missing_path = archive.root_path / missing_asset.metadata.archive_path
            missing_path.unlink()
        
        # Delete metadata for another asset
        no_metadata_asset = assets[2] if len(assets) > 2 else None
        if no_metadata_asset:
            no_metadata_asset.sidecar_path.unlink()
        
        report = service.verify_all(max_workers=1)
        
        assert isinstance(report, IntegrityReport)
        assert report.total_assets == len(assets)
        assert len(report.corrupted_assets) >= 1
        if missing_asset:
            assert len(report.missing_assets) >= 1
        if no_metadata_asset:
            assert len(report.missing_metadata) >= 1
        assert report.success_rate < 100.0  # Should be less than 100% due to issues
    
    def test_verify_all_parallel_processing(self, archive_with_assets):
        """Test parallel verification with multiple workers"""
        archive, assets = archive_with_assets
        service = IntegrityService(archive)
        
        # Test with parallel processing (if we have enough assets)
        max_workers = 2 if len(assets) >= 10 else 1
        report = service.verify_all(max_workers=max_workers)
        
        assert isinstance(report, IntegrityReport)
        assert report.total_assets == len(assets)
        assert report.verified_assets > 0
        assert report.duration >= 0
    
    def test_verify_all_with_progress_callback(self, archive_with_assets):
        """Test that progress callbacks are called during verification"""
        archive, assets = archive_with_assets
        service = IntegrityService(archive)
        
        progress_calls = []
        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))
        
        service.set_progress_callback(progress_callback)
        report = service.verify_all(max_workers=1)
        
        assert len(progress_calls) > 0
        assert progress_calls[-1][0] == report.total_assets  # Last call should be complete
        assert all(call[1] == report.total_assets for call in progress_calls)  # Total should be consistent
    
    def test_cancel_verification_during_process(self, archive_with_assets):
        """Test cancellation during verification process"""
        archive, assets = archive_with_assets
        service = IntegrityService(archive)
        
        # Mock to simulate cancellation during process
        original_verify = service._verify_asset
        call_count = 0
        
        def mock_verify(asset_id, archive_path):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Cancel after second asset
                service.cancel_verification()
            return original_verify(asset_id, archive_path)
        
        service._verify_asset = mock_verify
        report = service.verify_all(max_workers=1)
        
        # Should have been cancelled early
        assert service._cancel_verification.is_set()
        assert report.verified_assets < report.total_assets
    
    def test_find_orphaned_files(self, sample_archive, sample_files):
        service = IntegrityService(sample_archive)
        
        # Copy a file to assets directory without indexing it
        orphan_file = sample_archive.assets_path / "orphan.txt"
        orphan_file.parent.mkdir(parents=True, exist_ok=True)
        orphan_file.write_text("Orphaned file content")
        
        orphaned = service.find_orphaned_files()
        
        assert len(orphaned) == 1
        assert orphaned[0].name == "orphan.txt"
    
    def test_find_orphaned_files_ignores_metadata(self, sample_archive):
        """Test that orphaned file detection ignores .metadata.json files"""
        service = IntegrityService(sample_archive)
        
        # Create orphaned metadata file (should be ignored)
        orphan_metadata = sample_archive.assets_path / "test.txt.metadata.json"
        orphan_metadata.parent.mkdir(parents=True, exist_ok=True)
        orphan_metadata.write_text('{"asset_id": "test"}')
        
        # Create actual orphaned file
        orphan_file = sample_archive.assets_path / "actual_orphan.txt"
        orphan_file.write_text("Real orphaned content")
        
        orphaned = service.find_orphaned_files()
        
        # Should only find the actual file, not the metadata
        assert len(orphaned) == 1
        assert orphaned[0].name == "actual_orphan.txt"
    
    def test_repair_index_removes_missing_assets(self, archive_with_assets):
        """Test that repair_index removes missing assets from the index"""
        archive, assets = archive_with_assets
        service = IntegrityService(archive)
        
        # Delete one asset file but leave it in index
        deleted_asset = assets[0]
        deleted_path = archive.root_path / deleted_asset.metadata.archive_path
        deleted_path.unlink()
        
        stats = service.repair_index()
        
        assert stats["removed_missing"] >= 1
        assert stats["errors"] >= 0
        
        # Verify the asset was removed from index
        result = service.verify_single(deleted_asset.metadata.asset_id)
        assert result["status"] == "not_found"
    
    def test_repair_index_reindexes_orphaned_with_metadata(self, sample_archive):
        """Test that repair_index reindexes orphaned files that have metadata"""
        service = IntegrityService(sample_archive)
        
        # Create orphaned file with metadata
        orphan_file = sample_archive.assets_path / "orphan_with_metadata.txt"
        orphan_file.parent.mkdir(parents=True, exist_ok=True)
        orphan_file.write_text("Orphaned file with metadata")
        
        # Create metadata for the orphaned file
        asset = Asset(orphan_file, sample_archive.root_path)
        asset.metadata = AssetMetadata(
            asset_id="orphan-123",
            original_path=str(orphan_file),
            archive_path=str(orphan_file.relative_to(sample_archive.root_path)),
            file_size=orphan_file.stat().st_size,
            mime_type="text/plain",
            checksum_sha256=asset.calculate_checksum(),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        asset.save_metadata()
        
        stats = service.repair_index()
        
        assert stats["reindexed"] >= 1
        
        # Verify the asset is now in the index
        result = service.verify_single("orphan-123")
        assert result["status"] == "verified"
    
    def test_repair_index_creates_metadata_for_new_orphans(self, sample_archive):
        """Test that repair_index creates metadata for orphaned files without metadata"""
        service = IntegrityService(sample_archive)
        
        # Create orphaned file without metadata
        orphan_file = sample_archive.assets_path / "new_orphan.txt"
        orphan_file.parent.mkdir(parents=True, exist_ok=True)
        orphan_file.write_text("New orphaned file without metadata")
        
        stats = service.repair_index()
        
        assert stats["newly_indexed"] >= 1
        
        # Verify metadata was created
        asset = Asset(orphan_file, sample_archive.root_path)
        assert asset.load_metadata()
        assert asset.metadata.asset_id is not None
        assert asset.metadata.checksum_sha256 is not None
    
    def test_repair_index_handles_errors_gracefully(self, sample_archive):
        """Test that repair_index handles errors gracefully"""
        service = IntegrityService(sample_archive)
        
        # Create a file in a directory that will cause permission errors
        protected_dir = sample_archive.assets_path / "protected"
        protected_dir.mkdir(parents=True, exist_ok=True)
        protected_file = protected_dir / "protected_file.txt"
        protected_file.write_text("Protected content")
        
        # Mock to simulate permission error during metadata creation
        with patch('src.core.integrity.AssetMetadata') as mock_metadata:
            mock_metadata.side_effect = PermissionError("Permission denied")
            
            stats = service.repair_index()
            
            # Should handle errors gracefully
            assert "errors" in stats
            assert isinstance(stats["errors"], int)
    
    def test_progress_reporting(self, sample_archive):
        """Test that progress is reported correctly"""
        service = IntegrityService(sample_archive)
        
        progress_calls = []
        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))
        
        service.set_progress_callback(progress_callback)
        service._report_progress(5, 10, "Test message")
        
        assert len(progress_calls) == 1
        assert progress_calls[0] == (5, 10, "Test message")
    
    def test_cancel_verification(self, sample_archive):
        service = IntegrityService(sample_archive)
        
        # Test that cancel flag can be set
        service.cancel_verification()
        assert service._cancel_verification.is_set()
    
    def test_verify_asset_internal_method(self, archive_with_assets):
        """Test the internal _verify_asset method directly"""
        archive, assets = archive_with_assets
        service = IntegrityService(archive)
        
        first_asset = assets[0]
        
        # Test successful verification
        status = service._verify_asset(first_asset.metadata.asset_id, first_asset.metadata.archive_path)
        assert status == "verified"
        
        # Test missing file
        status = service._verify_asset(first_asset.metadata.asset_id, "nonexistent/path.txt")
        assert status == "missing"


@pytest.mark.unit 
class TestExportService:
    """Test ExportService class"""
    
    def test_init(self, sample_archive):
        service = ExportService(sample_archive)
        assert service.archive == sample_archive
        assert service.progress_callback is None
    
    def test_set_progress_callback(self, sample_archive):
        service = ExportService(sample_archive)
        callback = Mock()
        
        service.set_progress_callback(callback)
        assert service.progress_callback == callback
    
    @patch('src.core.export.bagit')
    def test_export_to_bagit(self, mock_bagit, archive_with_assets, temp_dir):
        archive, assets = archive_with_assets
        service = ExportService(archive)
        
        # Mock bagit operations
        mock_bag = Mock()
        mock_bagit.make_bag.return_value = mock_bag
        mock_bag.validate.return_value = None
        
        output_path = temp_dir / "test_export.bag"
        metadata = {'Source-Organization': 'Test Org'}
        
        with patch('shutil.move') as mock_move:
            result_path = service.export_to_bagit(output_path, metadata=metadata)
            mock_move.assert_called_once()
        
        # Verify bagit.make_bag was called
        mock_bagit.make_bag.assert_called_once()
        mock_bag.validate.assert_called_once()
    
    def test_generate_manifest_json(self, archive_with_assets, temp_dir):
        archive, assets = archive_with_assets
        service = ExportService(archive)
        
        manifest_path = temp_dir / "manifest.json"
        
        result_path = service.generate_manifest(manifest_path, format="json")
        
        assert result_path == manifest_path
        assert manifest_path.exists()
        
        # Verify manifest content
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        assert 'archive' in manifest
        assert 'assets' in manifest
        assert manifest['archive']['name'] == archive.config.name
        assert len(manifest['assets']) == len(assets)
    
    def test_generate_manifest_csv(self, archive_with_assets, temp_dir):
        archive, assets = archive_with_assets
        service = ExportService(archive)
        
        manifest_path = temp_dir / "manifest.csv"
        
        result_path = service.generate_manifest(manifest_path, format="csv")
        
        assert result_path == manifest_path
        assert manifest_path.exists()
        
        # Verify CSV has content
        content = manifest_path.read_text()
        lines = content.strip().split('\n')
        assert len(lines) > 1  # Header + data rows
        assert 'asset_id' in lines[0]  # Header row


@pytest.mark.unit
class TestIntegrityReport:
    """Test IntegrityReport class"""
    
    def test_create_report(self):
        report = IntegrityReport()
        
        assert report.total_assets == 0
        assert report.verified_assets == 0
        assert report.corrupted_assets == []
        assert report.missing_assets == []
        assert report.missing_metadata == []
        assert report.start_time is None
        assert report.end_time is None
    
    def test_duration_calculation(self):
        report = IntegrityReport()
        
        # No times set
        assert report.duration == 0
        
        # Set times
        start_time = datetime.now()
        report.start_time = start_time
        report.end_time = datetime.now()
        
        assert report.duration >= 0
    
    def test_success_rate_calculation(self):
        report = IntegrityReport()
        
        # No assets
        assert report.success_rate == 0
        
        # Some assets
        report.total_assets = 10
        report.verified_assets = 8
        
        assert report.success_rate == 80.0
    
    def test_to_dict(self):
        report = IntegrityReport()
        report.total_assets = 5
        report.verified_assets = 4
        report.corrupted_assets = ["file1.txt"]
        report.missing_assets = ["file2.txt"]
        
        report_dict = report.to_dict()
        
        assert report_dict['total_assets'] == 5
        assert report_dict['verified_assets'] == 4
        assert report_dict['corrupted_assets'] == 1
        assert report_dict['missing_assets'] == 1
        assert report_dict['success_rate'] == 80.0
        assert 'corrupted_files' in report_dict
        assert 'missing_files' in report_dict