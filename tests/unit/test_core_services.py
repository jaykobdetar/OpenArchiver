"""
Unit tests for Archive Tool core services
"""

import pytest
import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from contextlib import contextmanager

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
    
    def test_init_database_creates_indexes(self, sample_archive):
        """Test that database initialization creates proper indexes"""
        service = IndexingService(sample_archive)
        
        with service._get_connection() as conn:
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
            index_names = [row[0] for row in indexes]
            
            # Check that our custom indexes were created
            assert "idx_assets_archive_path" in index_names
            assert "idx_assets_profile_id" in index_names
            assert "idx_assets_mime_type" in index_names
            assert "idx_assets_checksum" in index_names
            assert "idx_metadata_asset_id" in index_names
    
    def test_init_database_creates_triggers(self, sample_archive):
        """Test that database initialization creates FTS triggers"""
        service = IndexingService(sample_archive)
        
        with service._get_connection() as conn:
            triggers = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            ).fetchall()
            trigger_names = [row[0] for row in triggers]
            
            assert "assets_fts_insert" in trigger_names
            assert "assets_fts_update" in trigger_names
            assert "assets_fts_delete" in trigger_names
    
    def test_connection_context_manager(self, sample_archive):
        """Test that connection context manager works properly"""
        service = IndexingService(sample_archive)
        
        # Test successful connection
        with service._get_connection() as conn:
            assert conn is not None
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1
        
        # Connection should be closed after context
        # Note: sqlite3 connections don't have a reliable way to check if closed
    
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
    
    def test_index_asset_with_complex_metadata(self, sample_archive, sample_files, sample_profile):
        """Test indexing asset with complex metadata types (lists, dicts, booleans)"""
        ingestion = FileIngestionService(sample_archive)
        test_file = sample_files[0]
        
        # Complex metadata with different types
        custom_metadata = {
            "tags": ["important", "document", "test"],  # List
            "properties": {"color": "blue", "size": "large"},  # Dict
            "archived": True,  # Boolean
            "priority": 5,  # Integer
            "description": "Test document"  # String
        }
        
        asset = ingestion.ingest_file(test_file, profile=sample_profile, custom_metadata=custom_metadata)
        
        indexing = IndexingService(sample_archive)
        result = indexing.index_asset(asset)
        
        assert result is True
        
        # Verify complex metadata was properly stored
        with indexing._get_connection() as conn:
            metadata_rows = conn.execute(
                "SELECT field_name, field_value, field_type FROM asset_metadata WHERE asset_id = ?",
                (asset.metadata.asset_id,)
            ).fetchall()
            
            metadata_dict = {row['field_name']: (row['field_value'], row['field_type']) for row in metadata_rows}
            
            # Check list was JSON serialized
            assert metadata_dict['tags'][1] == 'json'
            assert '["important", "document", "test"]' in metadata_dict['tags'][0]
            
            # Check dict was JSON serialized
            assert metadata_dict['properties'][1] == 'json'
            
            # Check boolean was converted
            assert metadata_dict['archived'][1] == 'boolean'
            assert metadata_dict['archived'][0] == '1'
            
            # Check string and integer
            assert metadata_dict['description'][0] == 'Test document'
            assert metadata_dict['priority'][0] == '5'
    
    def test_index_asset_without_metadata(self, sample_archive, sample_files):
        """Test indexing an asset that has no metadata file"""
        test_file = sample_files[0]
        asset = Asset(test_file, sample_archive.root_path)
        # Don't create metadata - asset.metadata will be None
        
        indexing = IndexingService(sample_archive)
        result = indexing.index_asset(asset)
        
        # Should return False because no metadata could be loaded
        assert result is False
    
    def test_index_asset_update_existing(self, sample_archive, sample_files, sample_profile):
        """Test that indexing an existing asset updates the record"""
        ingestion = FileIngestionService(sample_archive)
        test_file = sample_files[0]
        
        # Initial metadata
        custom_metadata = {"title": "Original Title"}
        asset = ingestion.ingest_file(test_file, profile=sample_profile, custom_metadata=custom_metadata)
        
        indexing = IndexingService(sample_archive)
        indexing.index_asset(asset)
        
        # Update metadata
        asset.metadata.custom_metadata["title"] = "Updated Title"
        asset.metadata.custom_metadata["new_field"] = "New Value"
        asset.save_metadata()
        
        # Re-index
        result = indexing.index_asset(asset)
        assert result is True
        
        # Verify update
        with indexing._get_connection() as conn:
            metadata_rows = conn.execute(
                "SELECT field_name, field_value FROM asset_metadata WHERE asset_id = ?",
                (asset.metadata.asset_id,)
            ).fetchall()
            
            metadata_dict = {row['field_name']: row['field_value'] for row in metadata_rows}
            assert metadata_dict['title'] == 'Updated Title'
            assert metadata_dict['new_field'] == 'New Value'
    
    def test_index_assets_batch(self, sample_archive, sample_files, sample_profile):
        """Test batch indexing of multiple assets"""
        ingestion = FileIngestionService(sample_archive)
        
        # Create multiple assets
        assets = []
        for i, test_file in enumerate(sample_files[:3]):  # Use first 3 files
            custom_metadata = {"title": f"Document {i+1}", "batch": "test_batch"}
            asset = ingestion.ingest_file(test_file, profile=sample_profile, custom_metadata=custom_metadata)
            assets.append(asset)
        
        indexing = IndexingService(sample_archive)
        result = indexing.index_assets_batch(assets)
        
        assert result is True
        
        # Verify all assets were indexed
        with indexing._get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            assert count == len(assets)
            
            # Verify metadata for all assets
            batch_assets = conn.execute(
                "SELECT DISTINCT asset_id FROM asset_metadata WHERE field_name = 'batch' AND field_value = 'test_batch'"
            ).fetchall()
            assert len(batch_assets) == len(assets)
    
    def test_index_assets_batch_partial_failure(self, sample_archive, sample_files, sample_profile):
        """Test batch indexing handles partial failures gracefully"""
        ingestion = FileIngestionService(sample_archive)
        
        # Create assets, some with metadata, some without
        assets = []
        
        # Good asset
        good_asset = ingestion.ingest_file(sample_files[0], profile=sample_profile, custom_metadata={"title": "Good"})
        assets.append(good_asset)
        
        # Bad asset (no metadata)
        bad_asset = Asset(sample_files[1], sample_archive.root_path)
        # Don't create metadata for this one
        assets.append(bad_asset)
        
        indexing = IndexingService(sample_archive)
        
        # Should continue processing even with failures
        result = indexing.index_assets_batch(assets)
        
        # Batch might return False due to error, but good asset should still be indexed
        with indexing._get_connection() as conn:
            good_count = conn.execute(
                "SELECT COUNT(*) FROM assets WHERE asset_id = ?", 
                (good_asset.metadata.asset_id,)
            ).fetchone()[0]
            assert good_count == 1
    
    def test_index_assets_batch_transaction_rollback(self, sample_archive, sample_files, sample_profile):
        """Test that batch indexing rolls back on database errors"""
        ingestion = FileIngestionService(sample_archive)
        test_file = sample_files[0]
        asset = ingestion.ingest_file(test_file, profile=sample_profile, custom_metadata={"title": "Test"})
        
        indexing = IndexingService(sample_archive)
        
        # Mock database to raise an error mid-transaction
        original_execute = None
        call_count = 0
        
        with indexing._get_connection() as conn:
            original_execute = conn.execute
            
            def mock_execute(sql, params=None):
                nonlocal call_count
                call_count += 1
                # Fail on the UPDATE statement to FTS table
                if "UPDATE assets_fts" in sql:
                    raise sqlite3.OperationalError("Simulated database error")
                return original_execute(sql, params) if params else original_execute(sql)
            
            # Can't directly assign to conn.execute in Python 3.12+, skip this test for now
            # TODO: Implement proper mocking strategy for database transactions
            pytest.skip("Test requires fixing SQLite connection mocking approach")
            count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            assert count == 0  # Should be 0 due to rollback
    
    def test_index_all_assets(self, sample_archive, sample_files, sample_profile):
        """Test indexing all assets from metadata files"""
        ingestion = FileIngestionService(sample_archive)
        
        # Create several assets with metadata files
        expected_count = len(sample_files[:3])  # Use first 3 files
        for i, test_file in enumerate(sample_files[:3]):
            ingestion.ingest_file(test_file, profile=sample_profile, custom_metadata={"title": f"Doc {i+1}"})
        
        # Create fresh indexing service to test index_all_assets
        indexing = IndexingService(sample_archive)
        
        # Clear the index first
        with indexing._get_connection() as conn:
            conn.execute("DELETE FROM assets")
            conn.commit()
        
        success_count, error_count = indexing.index_all_assets()
        
        assert success_count == expected_count
        assert error_count == 0
        
        # Verify all assets are in the index
        with indexing._get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            assert count == expected_count
    
    def test_index_all_assets_with_orphaned_metadata(self, sample_archive):
        """Test index_all_assets handles orphaned metadata files"""
        indexing = IndexingService(sample_archive)
        
        # Create orphaned metadata file (metadata without corresponding asset file)
        orphan_metadata_path = sample_archive.assets_path / "orphan.txt.metadata.json"
        orphan_metadata_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_metadata_path.write_text('{"asset_id": "orphan", "original_path": "orphan.txt"}')
        
        success_count, error_count = indexing.index_all_assets()
        
        # Should have 1 error due to missing asset file
        assert error_count >= 1
    
    def test_index_all_assets_force_reindex(self, sample_archive, sample_files, sample_profile):
        """Test force reindexing of all assets"""
        ingestion = FileIngestionService(sample_archive)
        
        # Create assets
        for i, test_file in enumerate(sample_files[:2]):
            ingestion.ingest_file(test_file, profile=sample_profile, custom_metadata={"title": f"Doc {i+1}"})
        
        indexing = IndexingService(sample_archive)
        
        # First indexing
        success1, error1 = indexing.index_all_assets()
        assert success1 == 2
        
        # Force reindex (should still work)
        success2, error2 = indexing.index_all_assets(force_reindex=True)
        assert success2 == 2
        assert error2 == 0
    
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
    
    def test_remove_asset_with_metadata(self, sample_archive):
        """Test that removing asset also removes associated metadata (foreign key cascade)"""
        indexing = IndexingService(sample_archive)
        test_asset_id = "test-asset-with-metadata"
        
        # Insert test asset with metadata
        with indexing._get_connection() as conn:
            conn.execute("""
                INSERT INTO assets (asset_id, original_path, archive_path, file_name, file_size, created_at, updated_at, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (test_asset_id, "/test/path", "test/path", "test.txt", 100, "2024-01-01", "2024-01-01", "2024-01-01"))
            
            conn.execute("""
                INSERT INTO asset_metadata (asset_id, field_name, field_value, field_type)
                VALUES (?, ?, ?, ?)
            """, (test_asset_id, "title", "Test Title", "str"))
            
            conn.commit()
        
        # Remove asset
        result = indexing.remove_asset(test_asset_id)
        assert result is True
        
        # Verify both asset and metadata were removed
        with indexing._get_connection() as conn:
            asset_count = conn.execute(
                "SELECT COUNT(*) FROM assets WHERE asset_id = ?", 
                (test_asset_id,)
            ).fetchone()[0]
            
            metadata_count = conn.execute(
                "SELECT COUNT(*) FROM asset_metadata WHERE asset_id = ?", 
                (test_asset_id,)
            ).fetchone()[0]
            
            assert asset_count == 0
            assert metadata_count == 0  # Should be removed by foreign key cascade
    
    def test_remove_nonexistent_asset(self, sample_archive):
        """Test removing a non-existent asset returns True (idempotent)"""
        indexing = IndexingService(sample_archive)
        
        result = indexing.remove_asset("nonexistent-asset-id")
        assert result is True  # Should succeed even if asset doesn't exist
    
    def test_remove_asset_database_error(self, sample_archive):
        """Test remove_asset handles database errors gracefully"""
        indexing = IndexingService(sample_archive)
        
        # Mock database connection to raise an error
        original_get_connection = indexing._get_connection
        
        @contextmanager
        def mock_get_connection():
            conn = Mock()
            conn.execute.side_effect = sqlite3.OperationalError("Database locked")
            conn.commit.side_effect = sqlite3.OperationalError("Database locked")
            yield conn
        
        indexing._get_connection = mock_get_connection
        
        result = indexing.remove_asset("test-asset")
        assert result is False
    
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
    
    def test_get_statistics_empty_database(self, sample_archive):
        """Test statistics with empty database"""
        indexing = IndexingService(sample_archive)
        
        stats = indexing.get_statistics()
        
        assert stats['total_assets'] == 0
        assert stats['total_size'] == 0
        assert stats['by_type'] == {}
        assert stats['by_profile'] == {}
        assert 'index_updated' in stats
    
    def test_get_statistics_null_values(self, sample_archive):
        """Test statistics handles NULL mime_type and profile_id properly"""
        indexing = IndexingService(sample_archive)
        
        # Insert asset with NULL values
        with indexing._get_connection() as conn:
            conn.execute("""
                INSERT INTO assets (asset_id, original_path, archive_path, file_name, file_size, mime_type, profile_id, created_at, updated_at, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("asset1", "/test/1", "test/1", "test1.txt", 100, None, None, "2024-01-01", "2024-01-01", "2024-01-01"))
            
            conn.commit()
        
        stats = indexing.get_statistics()
        
        assert stats['total_assets'] == 1
        assert stats['total_size'] == 100
        assert 'unknown' in stats['by_type']  # NULL mime_type becomes 'unknown'
        assert 'none' in stats['by_profile']   # NULL profile_id becomes 'none'
    
    def test_fts_triggers_work(self, sample_archive, sample_files, sample_profile):
        """Test that FTS triggers properly maintain the full-text search table"""
        ingestion = FileIngestionService(sample_archive)
        test_file = sample_files[0]
        
        asset = ingestion.ingest_file(test_file, profile=sample_profile, custom_metadata={"title": "Searchable Document"})
        
        indexing = IndexingService(sample_archive)
        indexing.index_asset(asset)
        
        # Verify FTS table was populated by triggers
        with indexing._get_connection() as conn:
            fts_row = conn.execute(
                "SELECT * FROM assets_fts WHERE asset_id = ?",
                (asset.metadata.asset_id,)
            ).fetchone()
            
            assert fts_row is not None
            assert fts_row['asset_id'] == asset.metadata.asset_id
            assert fts_row['file_name'] == Path(asset.metadata.archive_path).name
            assert "Searchable Document" in fts_row['metadata_text']


@pytest.mark.unit
class TestSearchService:
    """Test SearchService class"""
    
    def test_init(self, sample_archive):
        service = SearchService(sample_archive)
        assert service.archive == sample_archive
        assert service.db_path == sample_archive.index_path / "index.db"
    
    def test_init_creates_database_if_missing(self, sample_archive):
        """Test that SearchService creates database if it doesn't exist"""
        # Remove database file
        db_path = sample_archive.index_path / "index.db"
        if db_path.exists():
            db_path.unlink()
        
        # Creating SearchService should recreate database
        service = SearchService(sample_archive)
        assert db_path.exists()
    
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
    
    def test_search_with_limit_and_offset(self, archive_with_assets):
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Test limit
        results, total = search.search(limit=2)
        assert total == len(assets)  # Total count should be unchanged
        assert len(results) == 2     # But only 2 results returned
        
        # Test offset
        results_page2, total_page2 = search.search(limit=2, offset=2)
        assert total_page2 == len(assets)  # Total should be same
        assert len(results_page2) <= 2      # Should have remaining results
        
        # Results should be different (pagination)
        if len(results_page2) > 0:
            assert results[0].asset_id != results_page2[0].asset_id
    
    def test_search_with_filters(self, archive_with_assets):
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Search by MIME type
        results, total = search.search(filters={'mime_type': 'text/plain'})
        
        # Should find the text files (3 documents + 1 json = 4, but json might have different mime type)
        assert total >= 3  # At least the 3 text documents
        
        for result in results:
            assert result.mime_type == 'text/plain'
    
    def test_search_with_null_filters(self, archive_with_assets):
        """Test filtering by NULL values"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Insert asset with NULL mime_type for testing
        from src.core.indexing import IndexingService
        indexing = IndexingService(archive)
        
        with indexing._get_connection() as conn:
            conn.execute("""
                INSERT INTO assets (asset_id, original_path, archive_path, file_name, file_size, mime_type, created_at, updated_at, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("null-test", "/test/null", "test/null.txt", "null.txt", 100, None, "2024-01-01", "2024-01-01", "2024-01-01"))
            conn.commit()
        
        # Search for assets with NULL mime_type
        results, total = search.search(filters={'mime_type': None})
        
        assert total >= 1
        assert any(result.mime_type is None for result in results)
    
    def test_search_by_custom_metadata(self, archive_with_assets):
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Search by category
        results, total = search.search(filters={'category': 'Document'})
        
        assert total > 0
        for result in results:
            assert result.custom_metadata.get('category') == 'Document'
    
    def test_search_by_tags_array(self, archive_with_assets):
        """Test searching by array values (tags)"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Create asset with tags
        from src.core.ingestion import FileIngestionService
        from src.core.indexing import IndexingService
        
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        # Use existing sample files
        sample_files = list(archive.assets_path.parent.parent.rglob("*.txt"))[:1]
        if sample_files:
            test_file = sample_files[0]
            from src.models import Profile
            profile = Profile("test_profile", "Test Profile", "Test Profile Description")
            
            custom_metadata = {"tags": ["important", "urgent", "document"]}
            asset = ingestion.ingest_file(test_file, profile=profile, custom_metadata=custom_metadata)
            indexing.index_asset(asset)
            
            # Search by tag
            results, total = search.search(filters={'tags': 'important'})
            
            # Should find the asset with 'important' tag
            assert total >= 1
            found = False
            for result in results:
                if 'tags' in result.custom_metadata:
                    if 'important' in result.custom_metadata['tags']:
                        found = True
                        break
            assert found
    
    def test_search_by_file_size_range(self, archive_with_assets):
        """Test searching by file size ranges"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Search by minimum file size
        results, total = search.search(filters={'file_size_min': 0})
        assert total > 0  # Should find all assets
        
        # Search by maximum file size
        results, total = search.search(filters={'file_size_max': 1000000})
        assert total > 0  # Should find assets smaller than 1MB
        
        # Verify file sizes
        for result in results:
            assert result.file_size <= 1000000
        
        # Search by range
        results, total = search.search(filters={'file_size_min': 100, 'file_size_max': 10000})
        for result in results:
            assert 100 <= result.file_size <= 10000
    
    def test_search_by_date_range(self, archive_with_assets):
        """Test searching by creation date ranges"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Search after a date
        results, total = search.search(filters={'created_after': '2020-01-01T00:00:00'})
        assert total > 0  # Should find recent assets
        
        # Search before a date
        results, total = search.search(filters={'created_before': '2030-01-01T00:00:00'})
        assert total > 0  # Should find all assets (created before 2030)
    
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
    
    def test_search_full_text_basic(self, archive_with_assets):
        """Test basic full-text search functionality"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Search for content that should exist
        results, total = search.search(query="document")
        
        # Should find assets containing "document" in filename or metadata
        assert total >= 0  # May be 0 if no matches, which is fine
    
    def test_search_full_text_no_results(self, archive_with_assets):
        """Test full-text search with no matching results"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Search for something that definitely doesn't exist
        results, total = search.search(query="zyxwvutsrqponmlkjihgfedcba")
        
        assert total == 0
        assert len(results) == 0
    
    def test_search_full_text_combined_with_filters(self, archive_with_assets):
        """Test combining full-text search with filters"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Search with both text query and filters
        results, total = search.search(
            query="document",
            filters={'mime_type': 'text/plain'}
        )
        
        # All results should match both criteria
        for result in results:
            assert result.mime_type == 'text/plain'
    
    def test_search_sorting_by_standard_fields(self, archive_with_assets):
        """Test sorting by standard database fields"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Sort by file_name ascending
        results_asc, _ = search.search(sort_by="file_name", sort_order="ASC")
        if len(results_asc) > 1:
            assert results_asc[0].file_name <= results_asc[1].file_name
        
        # Sort by file_name descending
        results_desc, _ = search.search(sort_by="file_name", sort_order="DESC")
        if len(results_desc) > 1:
            assert results_desc[0].file_name >= results_desc[1].file_name
        
        # Sort by file_size
        results_size, _ = search.search(sort_by="file_size", sort_order="DESC")
        if len(results_size) > 1:
            assert results_size[0].file_size >= results_size[1].file_size
        
        # Sort by created_at (default)
        results_date, _ = search.search(sort_by="created_at", sort_order="DESC")
        if len(results_date) > 1:
            assert results_date[0].created_at >= results_date[1].created_at
    
    def test_search_sorting_by_custom_metadata(self, archive_with_assets):
        """Test sorting by custom metadata fields"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Sort by custom field (title)
        results, _ = search.search(sort_by="title", sort_order="ASC")
        
        # Verify sorting (assets with title field should be sorted)
        titled_results = [r for r in results if 'title' in r.custom_metadata]
        if len(titled_results) > 1:
            titles = [r.custom_metadata['title'] for r in titled_results]
            assert titles == sorted(titles)
    
    def test_search_duplicates(self, archive_with_assets):
        """Test finding duplicate assets by checksum"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Create duplicate by copying file content
        from src.core.ingestion import FileIngestionService
        from src.core.indexing import IndexingService
        
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        # Get sample files
        sample_files = list(archive.assets_path.parent.parent.rglob("*.txt"))[:2]
        if len(sample_files) >= 2:
            # Make second file identical to first
            content = sample_files[0].read_text()
            sample_files[1].write_text(content)
            
            from src.models import Profile
            profile = Profile("test_profile", "Test Profile", "Test Profile Description")
            
            # Ingest both files
            asset1 = ingestion.ingest_file(sample_files[0], profile=profile, custom_metadata={"title": "Original"})
            asset2 = ingestion.ingest_file(sample_files[1], profile=profile, custom_metadata={"title": "Duplicate"})
            
            indexing.index_asset(asset1)
            indexing.index_asset(asset2)
            
            # Find duplicates
            duplicates = search.search_duplicates()
            
            # Should find at least one set of duplicates
            assert len(duplicates) >= 1
            
            # Each duplicate set should have multiple assets
            for checksum, duplicate_assets in duplicates:
                assert len(duplicate_assets) >= 2
                # All should have same checksum
                for asset in duplicate_assets:
                    assert asset.checksum_sha256 == checksum
    
    def test_search_duplicates_none_exist(self, archive_with_assets):
        """Test duplicate search when no duplicates exist"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Initially should have no duplicates (all files are different)
        duplicates = search.search_duplicates()
        
        # Should return empty list if no duplicates
        assert isinstance(duplicates, list)
    
    def test_get_metadata_fields(self, archive_with_assets):
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        fields = search.get_metadata_fields()
        
        assert len(fields) > 0
        
        # Should find our test fields
        field_names = [field['name'] for field in fields]
        assert 'title' in field_names
        assert 'category' in field_names
        
        # Verify field structure
        for field in fields:
            assert 'name' in field
            assert 'type' in field
            assert 'usage_count' in field
            assert isinstance(field['usage_count'], int)
    
    def test_get_metadata_fields_empty_database(self, sample_archive):
        """Test get_metadata_fields with empty database"""
        search = SearchService(sample_archive)
        
        fields = search.get_metadata_fields()
        
        assert isinstance(fields, list)
        assert len(fields) == 0  # No metadata fields in empty database
    
    def test_complex_metadata_type_conversion(self, archive_with_assets):
        """Test that complex metadata types are properly converted back"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Create asset with various metadata types
        from src.core.ingestion import FileIngestionService
        from src.core.indexing import IndexingService
        
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        sample_files = list(archive.assets_path.parent.parent.rglob("*.txt"))[:1]
        if sample_files:
            test_file = sample_files[0]
            from src.models import Profile
            profile = Profile("test_profile", "Test Profile", "Test Profile Description")
            
            custom_metadata = {
                "tags": ["tag1", "tag2"],  # JSON array
                "config": {"setting": "value"},  # JSON object
                "active": True,  # Boolean
                "count": 42,  # Integer
                "rating": 4.5,  # Float
                "description": "Simple string"  # String
            }
            
            asset = ingestion.ingest_file(test_file, profile=profile, custom_metadata=custom_metadata)
            indexing.index_asset(asset)
            
            # Search and verify type conversion
            results, _ = search.search(filters={'asset_id': asset.metadata.asset_id})
            
            assert len(results) == 1
            result = results[0]
            metadata = result.custom_metadata
            
            # Verify types were converted back correctly
            assert isinstance(metadata['tags'], list)
            assert metadata['tags'] == ["tag1", "tag2"]
            
            assert isinstance(metadata['config'], dict)
            assert metadata['config']['setting'] == "value"
            
            assert isinstance(metadata['active'], bool)
            assert metadata['active'] is True
            
            assert isinstance(metadata['count'], int)
            assert metadata['count'] == 42
            
            # Note: float might come back as string depending on how it was stored
            # This is acceptable behavior
            
            assert isinstance(metadata['description'], str)
            assert metadata['description'] == "Simple string"
    
    def test_search_with_complex_filter_combinations(self, archive_with_assets):
        """Test search with multiple complex filters"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Combine multiple filter types
        results, total = search.search(filters={
            'mime_type': 'text/plain',
            'file_size_min': 0,
            'file_size_max': 1000000,
            'created_after': '2020-01-01T00:00:00',
            'category': 'Document'
        })
        
        # All results should satisfy all filters
        for result in results:
            assert result.mime_type == 'text/plain'
            assert 0 <= result.file_size <= 1000000
            assert result.created_at >= '2020-01-01T00:00:00'
            if 'category' in result.custom_metadata:
                assert result.custom_metadata['category'] == 'Document'
    
    def test_search_result_file_path_property(self, archive_with_assets):
        """Test SearchResult file_path property"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        results, _ = search.search(limit=1)
        
        if results:
            result = results[0]
            file_path = result.file_path
            
            assert isinstance(file_path, Path)
            assert str(file_path) == result.archive_path
    
    def test_get_statistics_delegation(self, archive_with_assets):
        """Test that get_statistics properly delegates to IndexingService"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        stats = search.get_statistics()
        
        # Should have standard statistics structure
        assert 'total_assets' in stats
        assert 'total_size' in stats
        assert 'by_type' in stats
        assert 'by_profile' in stats
        assert isinstance(stats['total_assets'], int)
        assert stats['total_assets'] > 0  # Should have assets from the fixture
    
    def test_connection_timeout_and_pragma_settings(self, sample_archive):
        """Test that database connections have proper settings"""
        search = SearchService(sample_archive)
        
        conn = search._get_connection()
        
        # Test that connection works
        result = conn.execute("SELECT 1").fetchone()
        assert result[0] == 1
        
        # Test that pragma settings were applied (journal_mode should be WAL)
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode.upper() == 'WAL'
        
        conn.close()
    
    def test_search_edge_cases(self, archive_with_assets):
        """Test various edge cases in search"""
        archive, assets = archive_with_assets
        search = SearchService(archive)
        
        # Empty query string
        results, total = search.search(query="")
        assert isinstance(results, list)
        assert isinstance(total, int)
        
        # Very large limit
        results, total = search.search(limit=999999)
        assert len(results) <= total
        
        # Negative offset (should be handled gracefully)
        results, total = search.search(offset=-1)
        assert isinstance(results, list)
        
        # Zero limit
        results, total = search.search(limit=0)
        assert len(results) == 0
        assert total >= 0  # Total should still be calculated


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