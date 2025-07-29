import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

from ..models import Archive, Asset, AssetMetadata

logger = logging.getLogger(__name__)


class IndexingService:
    def __init__(self, archive: Archive):
        self.archive = archive
        self.db_path = archive.index_path / "index.db"
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraints and optimizations for concurrency
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
        conn.execute("PRAGMA synchronous = NORMAL")  # Better performance
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_database(self):
        with self._get_connection() as conn:
            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Create assets table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id TEXT PRIMARY KEY,
                    original_path TEXT NOT NULL,
                    archive_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    mime_type TEXT,
                    checksum_sha256 TEXT,
                    checksum_verified_at TEXT,
                    profile_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    indexed_at TEXT NOT NULL
                )
            """)
            
            # Create metadata table for custom fields
            conn.execute("""
                CREATE TABLE IF NOT EXISTS asset_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    field_value TEXT,
                    field_type TEXT,
                    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE,
                    UNIQUE(asset_id, field_name)
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_archive_path ON assets(archive_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_profile_id ON assets(profile_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_mime_type ON assets(mime_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_checksum ON assets(checksum_sha256)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_asset_id ON asset_metadata(asset_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_field_name ON asset_metadata(field_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_field_value ON asset_metadata(field_value)")
            
            # Create full-text search table
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(
                    asset_id UNINDEXED,
                    file_name,
                    original_path,
                    metadata_text
                )
            """)
            
            # Create triggers to keep FTS in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS assets_fts_insert AFTER INSERT ON assets BEGIN
                    INSERT INTO assets_fts(asset_id, file_name, original_path, metadata_text)
                    VALUES (new.asset_id, new.file_name, new.original_path, '');
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS assets_fts_update AFTER UPDATE ON assets BEGIN
                    UPDATE assets_fts SET 
                        file_name = new.file_name,
                        original_path = new.original_path
                    WHERE asset_id = new.asset_id;
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS assets_fts_delete AFTER DELETE ON assets BEGIN
                    DELETE FROM assets_fts WHERE asset_id = old.asset_id;
                END
            """)
            
            conn.commit()
    
    def index_asset(self, asset: Asset) -> bool:
        if not asset.metadata:
            if not asset.load_metadata():
                logger.error(f"Failed to load metadata for asset: {asset.file_path}")
                return False
        
        metadata = asset.metadata
        
        try:
            with self._get_connection() as conn:
                # Insert or update asset record
                conn.execute("""
                    INSERT OR REPLACE INTO assets (
                        asset_id, original_path, archive_path, file_name, file_size,
                        mime_type, checksum_sha256, checksum_verified_at, profile_id,
                        created_at, updated_at, indexed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metadata.asset_id,
                    metadata.original_path,
                    metadata.archive_path,
                    Path(metadata.archive_path).name,
                    metadata.file_size,
                    metadata.mime_type,
                    metadata.checksum_sha256,
                    metadata.checksum_verified_at,
                    metadata.profile_id,
                    metadata.created_at,
                    metadata.updated_at,
                    datetime.now().isoformat()
                ))
                
                # Delete existing custom metadata
                conn.execute("DELETE FROM asset_metadata WHERE asset_id = ?", (metadata.asset_id,))
                
                # Insert custom metadata fields
                for field_name, field_value in metadata.custom_metadata.items():
                    field_type = type(field_value).__name__
                    
                    # Convert complex types to JSON
                    if isinstance(field_value, (list, dict)):
                        field_value = json.dumps(field_value)
                        field_type = "json"
                    elif isinstance(field_value, bool):
                        field_value = "1" if field_value else "0"
                        field_type = "boolean"
                    else:
                        field_value = str(field_value)
                    
                    conn.execute("""
                        INSERT INTO asset_metadata (asset_id, field_name, field_value, field_type)
                        VALUES (?, ?, ?, ?)
                    """, (metadata.asset_id, field_name, field_value, field_type))
                
                # Update FTS with metadata content for full-text search
                metadata_text = " ".join([
                    str(value) for value in metadata.custom_metadata.values()
                    if value is not None
                ])
                
                # Update FTS table with metadata content (trigger handles basic fields)
                conn.execute("""
                    UPDATE assets_fts SET metadata_text = ? WHERE asset_id = ?
                """, (metadata_text, metadata.asset_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to index asset {metadata.asset_id}: {e}")
            return False
    
    def index_assets_batch(self, assets: List) -> bool:
        """Index multiple assets in a single transaction for better performance"""
        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN TRANSACTION")
                
                for asset in assets:
                    if not asset.metadata:
                        if not asset.load_metadata():
                            logger.error(f"Failed to load metadata for asset: {asset.file_path}")
                            continue
                    
                    metadata = asset.metadata
                    
                    # Insert or update asset record
                    conn.execute("""
                        INSERT OR REPLACE INTO assets (
                            asset_id, original_path, archive_path, file_name, file_size,
                            mime_type, checksum_sha256, checksum_verified_at, profile_id,
                            created_at, updated_at, indexed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        metadata.asset_id,
                        metadata.original_path,
                        metadata.archive_path,
                        Path(metadata.archive_path).name,
                        metadata.file_size,
                        metadata.mime_type,
                        metadata.checksum_sha256,
                        metadata.checksum_verified_at,
                        metadata.profile_id,
                        metadata.created_at,
                        metadata.updated_at,
                        datetime.now().isoformat()
                    ))
                    
                    # Delete existing custom metadata
                    conn.execute("DELETE FROM asset_metadata WHERE asset_id = ?", (metadata.asset_id,))
                    
                    # Insert custom metadata fields
                    for field_name, field_value in metadata.custom_metadata.items():
                        field_type = type(field_value).__name__
                        
                        # Convert complex types to JSON
                        if isinstance(field_value, (list, dict)):
                            field_value = json.dumps(field_value)
                            field_type = "json"
                        elif isinstance(field_value, bool):
                            field_value = "1" if field_value else "0"
                            field_type = "boolean"
                        else:
                            field_value = str(field_value)
                        
                        conn.execute("""
                            INSERT INTO asset_metadata (asset_id, field_name, field_value, field_type)
                            VALUES (?, ?, ?, ?)
                        """, (metadata.asset_id, field_name, field_value, field_type))
                    
                    # Update FTS with metadata content
                    metadata_text = " ".join([
                        str(value) for value in metadata.custom_metadata.values()
                        if value is not None
                    ])
                    
                    conn.execute("""
                        UPDATE assets_fts SET metadata_text = ? WHERE asset_id = ?
                    """, (metadata_text, metadata.asset_id))
                
                conn.execute("COMMIT")
                return True
                
        except Exception as e:
            logger.error(f"Failed to index asset batch: {e}")
            try:
                conn.execute("ROLLBACK")
            except:
                pass
            return False
    
    def index_all_assets(self, force_reindex: bool = False) -> tuple[int, int]:
        success_count = 0
        error_count = 0
        
        # Find all metadata files in the archive
        metadata_files = list(self.archive.assets_path.rglob("*.metadata.json"))
        
        for metadata_path in metadata_files:
            try:
                # Get the actual asset file path
                asset_filename = metadata_path.name.replace(".metadata.json", "")
                asset_path = metadata_path.parent / asset_filename
                
                if not asset_path.exists():
                    logger.warning(f"Asset file not found for metadata: {metadata_path}")
                    error_count += 1
                    continue
                
                # Create asset instance and load metadata
                asset = Asset(asset_path, self.archive.root_path)
                if asset.load_metadata():
                    if self.index_asset(asset):
                        success_count += 1
                    else:
                        error_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to process {metadata_path}: {e}")
                error_count += 1
        
        logger.info(f"Indexing complete: {success_count} successful, {error_count} errors")
        return success_count, error_count
    
    def remove_asset(self, asset_id: str) -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM assets WHERE asset_id = ?", (asset_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to remove asset {asset_id} from index: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            # Total assets
            total_assets = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            
            # Total size
            total_size = conn.execute("SELECT SUM(file_size) FROM assets").fetchone()[0] or 0
            
            # Assets by type
            type_stats = {}
            for row in conn.execute("""
                SELECT mime_type, COUNT(*) as count, SUM(file_size) as size
                FROM assets
                GROUP BY mime_type
            """):
                mime_type = row['mime_type'] or 'unknown'
                type_stats[mime_type] = {
                    'count': row['count'],
                    'size': row['size']
                }
            
            # Assets by profile
            profile_stats = {}
            for row in conn.execute("""
                SELECT profile_id, COUNT(*) as count
                FROM assets
                GROUP BY profile_id
            """):
                profile_id = row['profile_id'] or 'none'
                profile_stats[profile_id] = row['count']
            
            return {
                'total_assets': total_assets,
                'total_size': total_size,
                'by_type': type_stats,
                'by_profile': profile_stats,
                'index_updated': datetime.now().isoformat()
            }