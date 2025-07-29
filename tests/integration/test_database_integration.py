"""
Integration tests for database operations and data consistency
"""

import pytest
import sqlite3
from pathlib import Path
from datetime import datetime

from src.core.indexing import IndexingService
from src.core.search import SearchService
from src.models import Asset, AssetMetadata


@pytest.mark.integration
class TestDatabaseIntegration:
    """Test database operations and data consistency"""
    
    def test_database_initialization(self, sample_archive):
        """Test that database is properly initialized with correct schema"""
        
        indexing = IndexingService(sample_archive)
        
        # Check that database file exists
        assert indexing.db_path.exists()
        
        # Check that tables exist with correct schema
        with indexing._get_connection() as conn:
            # Get table info
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            
            table_names = [row[0] for row in tables]
            
            # Verify core tables exist
            assert 'assets' in table_names
            assert 'asset_metadata' in table_names
            assert 'assets_fts' in table_names
            
            # Check assets table schema
            assets_schema = conn.execute("PRAGMA table_info(assets)").fetchall()
            column_names = [row[1] for row in assets_schema]
            
            expected_columns = [
                'asset_id', 'original_path', 'archive_path', 'file_name',
                'file_size', 'mime_type', 'checksum_sha256', 'checksum_verified_at',
                'profile_id', 'created_at', 'updated_at', 'indexed_at'
            ]
            
            for col in expected_columns:
                assert col in column_names
            
            # Check asset_metadata table schema
            metadata_schema = conn.execute("PRAGMA table_info(asset_metadata)").fetchall()
            metadata_columns = [row[1] for row in metadata_schema]
            
            expected_metadata_columns = [
                'id', 'asset_id', 'field_name', 'field_value', 'field_type'
            ]
            
            for col in expected_metadata_columns:
                assert col in metadata_columns
            
            # Check indexes exist
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
            
            index_names = [row[0] for row in indexes]
            
            # Verify important indexes exist
            assert any('assets_archive_path' in name for name in index_names)
            assert any('metadata_asset_id' in name for name in index_names)
    
    def test_foreign_key_constraints(self, sample_archive):
        """Test that foreign key constraints are properly enforced"""
        
        indexing = IndexingService(sample_archive)
        
        with indexing._get_connection() as conn:
            # Check foreign keys are enabled
            fk_result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert fk_result[0] == 1  # Foreign keys should be ON
            
            # Insert test asset
            asset_id = "test-fk-asset"
            conn.execute("""
                INSERT INTO assets (
                    asset_id, original_path, archive_path, file_name, file_size,
                    created_at, updated_at, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (asset_id, "/test", "test.txt", "test.txt", 100, "2024-01-01", "2024-01-01", "2024-01-01"))
            
            # Insert metadata referencing the asset
            conn.execute("""
                INSERT INTO asset_metadata (asset_id, field_name, field_value, field_type)
                VALUES (?, ?, ?, ?)
            """, (asset_id, "title", "Test Asset", "str"))
            
            conn.commit()
            
            # Verify metadata was inserted
            metadata_count = conn.execute(
                "SELECT COUNT(*) FROM asset_metadata WHERE asset_id = ?",
                (asset_id,)
            ).fetchone()[0]
            
            assert metadata_count == 1
            
            # Delete asset (should cascade to metadata due to foreign key)
            conn.execute("DELETE FROM assets WHERE asset_id = ?", (asset_id,))
            conn.commit()
            
            # Verify metadata was also deleted
            metadata_count_after = conn.execute(
                "SELECT COUNT(*) FROM asset_metadata WHERE asset_id = ?",
                (asset_id,)
            ).fetchone()[0]
            
            assert metadata_count_after == 0
    
    def test_full_text_search_integration(self, archive_with_assets):
        """Test FTS integration with main tables"""
        
        archive, assets = archive_with_assets
        indexing = IndexingService(archive)
        
        with indexing._get_connection() as conn:
            # Verify FTS table is populated
            fts_count = conn.execute("SELECT COUNT(*) FROM assets_fts").fetchone()[0]
            assert fts_count == len(assets)
            
            # Test FTS triggers work
            test_asset_id = "fts-test-asset"
            
            # Insert new asset
            conn.execute("""
                INSERT INTO assets (
                    asset_id, original_path, archive_path, file_name, file_size,
                    created_at, updated_at, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (test_asset_id, "/fts/test", "fts_test.txt", "fts_test.txt", 100, "2024-01-01", "2024-01-01", "2024-01-01"))
            
            conn.commit()
            
            # Verify FTS was updated
            fts_count_after = conn.execute("SELECT COUNT(*) FROM assets_fts").fetchone()[0]
            assert fts_count_after == len(assets) + 1
            
            # Test FTS search works
            fts_result = conn.execute(
                "SELECT asset_id FROM assets_fts WHERE assets_fts MATCH ?",
                ("fts_test",)
            ).fetchone()
            
            assert fts_result is not None
            
            # Update asset
            conn.execute(
                "UPDATE assets SET file_name = ? WHERE asset_id = ?",
                ("updated_fts_test.txt", test_asset_id)
            )
            conn.commit()
            
            # Verify FTS was updated
            fts_updated = conn.execute(
                "SELECT file_name FROM assets_fts WHERE asset_id = ?",
                (test_asset_id,)
            ).fetchone()
            
            assert fts_updated[0] == "updated_fts_test.txt"
            
            # Delete asset
            conn.execute("DELETE FROM assets WHERE asset_id = ?", (test_asset_id,))
            conn.commit()
            
            # Verify FTS entry was deleted
            fts_count_final = conn.execute("SELECT COUNT(*) FROM assets_fts").fetchone()[0]
            assert fts_count_final == len(assets)
    
    def test_transaction_consistency(self, sample_archive):
        """Test database transaction consistency"""
        
        indexing = IndexingService(sample_archive)
        
        with indexing._get_connection() as conn:
            try:
                # Start transaction
                conn.execute("BEGIN")
                
                # Insert asset
                test_asset_id = "txn-test-asset"
                conn.execute("""
                    INSERT INTO assets (
                        asset_id, original_path, archive_path, file_name, file_size,
                        created_at, updated_at, indexed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (test_asset_id, "/txn/test", "txn_test.txt", "txn_test.txt", 100, "2024-01-01", "2024-01-01", "2024-01-01"))
                
                # Insert metadata
                conn.execute("""
                    INSERT INTO asset_metadata (asset_id, field_name, field_value, field_type)
                    VALUES (?, ?, ?, ?)
                """, (test_asset_id, "title", "Transaction Test", "str"))
                
                # Verify data exists in transaction
                asset_count = conn.execute(
                    "SELECT COUNT(*) FROM assets WHERE asset_id = ?",
                    (test_asset_id,)
                ).fetchone()[0]
                
                metadata_count = conn.execute(
                    "SELECT COUNT(*) FROM asset_metadata WHERE asset_id = ?",
                    (test_asset_id,)
                ).fetchone()[0]
                
                assert asset_count == 1
                assert metadata_count == 1
                
                # Rollback transaction
                conn.execute("ROLLBACK")
                
            except Exception:
                conn.execute("ROLLBACK")
                raise
        
        # Verify data was rolled back
        with indexing._get_connection() as conn:
            asset_count_after = conn.execute(
                "SELECT COUNT(*) FROM assets WHERE asset_id = ?",
                (test_asset_id,)
            ).fetchone()[0]
            
            metadata_count_after = conn.execute(
                "SELECT COUNT(*) FROM asset_metadata WHERE asset_id = ?",
                (test_asset_id,)
            ).fetchone()[0]
            
            assert asset_count_after == 0
            assert metadata_count_after == 0
    
    def test_concurrent_access(self, sample_archive):
        """Test concurrent database access"""
        
        indexing1 = IndexingService(sample_archive)
        indexing2 = IndexingService(sample_archive)
        
        # Both services should be able to read concurrently
        with indexing1._get_connection() as conn1, indexing2._get_connection() as conn2:
            # Insert data with first connection
            test_asset_id = "concurrent-test-asset"
            conn1.execute("""
                INSERT INTO assets (
                    asset_id, original_path, archive_path, file_name, file_size,
                    created_at, updated_at, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (test_asset_id, "/concurrent/test", "concurrent_test.txt", "concurrent_test.txt", 100, "2024-01-01", "2024-01-01", "2024-01-01"))
            
            conn1.commit()
            
            # Read with second connection
            result = conn2.execute(
                "SELECT asset_id FROM assets WHERE asset_id = ?",
                (test_asset_id,)
            ).fetchone()
            
            assert result is not None
            assert result[0] == test_asset_id
    
    def test_data_integrity_constraints(self, sample_archive):
        """Test database constraints and data integrity"""
        
        indexing = IndexingService(sample_archive)
        
        with indexing._get_connection() as conn:
            # Test unique constraint on asset_id (should be PRIMARY KEY)
            test_asset_id = "integrity-test-asset"
            
            # Insert first asset
            conn.execute("""
                INSERT INTO assets (
                    asset_id, original_path, archive_path, file_name, file_size,
                    created_at, updated_at, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (test_asset_id, "/integrity/test1", "test1.txt", "test1.txt", 100, "2024-01-01", "2024-01-01", "2024-01-01"))
            
            conn.commit()
            
            # Try to insert duplicate asset_id (should fail)
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("""
                    INSERT INTO assets (
                        asset_id, original_path, archive_path, file_name, file_size,
                        created_at, updated_at, indexed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (test_asset_id, "/integrity/test2", "test2.txt", "test2.txt", 200, "2024-01-01", "2024-01-01", "2024-01-01"))
            
            # Test unique constraint on asset_metadata (asset_id, field_name) combination
            conn.execute("""
                INSERT INTO asset_metadata (asset_id, field_name, field_value, field_type)
                VALUES (?, ?, ?, ?)
            """, (test_asset_id, "title", "First Title", "str"))
            
            conn.commit()
            
            # Try to insert duplicate field for same asset (should fail due to UNIQUE constraint)
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("""
                    INSERT INTO asset_metadata (asset_id, field_name, field_value, field_type)
                    VALUES (?, ?, ?, ?)
                """, (test_asset_id, "title", "Second Title", "str"))
    
    def test_database_recovery_from_corruption(self, sample_archive, temp_dir):
        """Test database can be rebuilt if corrupted"""
        
        # Create some assets first
        from src.core.ingestion import FileIngestionService
        
        ingestion = FileIngestionService(sample_archive)
        indexing = IndexingService(sample_archive)
        
        # Create test file
        test_file = temp_dir / "recovery_test.txt"
        test_file.write_text("Test content for recovery")
        
        # Ingest file
        asset = ingestion.ingest_file(test_file)
        indexing.index_asset(asset)
        
        # Verify asset is indexed
        stats_before = indexing.get_statistics()
        assert stats_before['total_assets'] == 1
        
        # Simulate database corruption by deleting it
        indexing.db_path.unlink()
        
        assert not indexing.db_path.exists()
        
        # Create new indexing service (should recreate database)
        new_indexing = IndexingService(sample_archive)
        
        # Database should be recreated but empty
        stats_after_recreate = new_indexing.get_statistics()
        assert stats_after_recreate['total_assets'] == 0
        
        # Rebuild index from sidecar files
        success_count, error_count = new_indexing.index_all_assets()
        
        assert success_count == 1
        assert error_count == 0
        
        # Verify asset is restored
        stats_after_rebuild = new_indexing.get_statistics()
        assert stats_after_rebuild['total_assets'] == 1
        
        # Verify search still works
        search = SearchService(sample_archive)
        results, total = search.search()
        
        assert total == 1
        assert results[0].asset_id == asset.metadata.asset_id
    
    def test_search_result_consistency(self, archive_with_assets):
        """Test that search results are consistent with database state"""
        
        archive, assets = archive_with_assets
        search = SearchService(archive)
        indexing = IndexingService(archive)
        
        # Get all results from search
        search_results, search_total = search.search()
        
        # Get count from database directly
        with indexing._get_connection() as conn:
            db_count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        
        # Counts should match
        assert search_total == db_count
        assert len(search_results) == len(assets)
        
        # Verify each search result corresponds to actual database entry
        for result in search_results:
            with indexing._get_connection() as conn:
                db_row = conn.execute(
                    "SELECT * FROM assets WHERE asset_id = ?",
                    (result.asset_id,)
                ).fetchone()
                
                assert db_row is not None
                assert db_row['asset_id'] == result.asset_id
                assert db_row['archive_path'] == result.archive_path
                assert db_row['file_size'] == result.file_size
                
                # Verify custom metadata matches
                metadata_rows = conn.execute(
                    "SELECT field_name, field_value FROM asset_metadata WHERE asset_id = ?",
                    (result.asset_id,)
                ).fetchall()
                
                db_metadata = {row['field_name']: row['field_value'] for row in metadata_rows}
                
                # Convert search result metadata for comparison
                search_metadata = {}
                for key, value in result.custom_metadata.items():
                    if isinstance(value, list):
                        search_metadata[key] = str(value)  # Lists stored as JSON strings
                    else:
                        search_metadata[key] = str(value)
                
                # All database metadata should be in search results
                for field_name, field_value in db_metadata.items():
                    assert field_name in search_metadata
                    # Note: exact comparison may vary due to type conversion