import sqlite3
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from ..models import Archive


@dataclass
class SearchResult:
    asset_id: str
    archive_path: str
    file_name: str
    file_size: int
    mime_type: Optional[str]
    checksum_sha256: Optional[str]
    profile_id: Optional[str]
    created_at: str
    custom_metadata: Dict[str, Any]
    relevance_score: Optional[float] = None
    
    @property
    def file_path(self) -> Path:
        return Path(self.archive_path)


class SearchService:
    def __init__(self, archive: Archive):
        self.archive = archive
        self.db_path = archive.index_path / "index.db"
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Ensure database is initialized before any operations"""
        if not self.db_path.exists():
            from .indexing import IndexingService
            # Initialize database through IndexingService
            IndexingService(self.archive)
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
        conn.execute("PRAGMA synchronous = NORMAL")  # Better performance
        return conn
    
    def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[SearchResult], int]:
        
        conn = self._get_connection()
        try:
            # Start with a simple base query
            where_conditions = []
            params = []
            
            # Handle full-text search
            if query:
                # First get asset IDs from FTS
                fts_query = "SELECT rowid FROM assets_fts WHERE assets_fts MATCH ?"
                fts_results = conn.execute(fts_query, (query,)).fetchall()
                if fts_results:
                    fts_rowids = [str(row[0]) for row in fts_results]
                    where_conditions.append(f"a.rowid IN ({','.join(fts_rowids)})")
                else:
                    # No FTS results, return empty
                    return [], 0
            
            # Handle filters
            if filters:
                for field, value in filters.items():
                    if field in ["asset_id", "mime_type", "profile_id", "checksum_sha256"]:
                        if value is None:
                            where_conditions.append(f"a.{field} IS NULL")
                        else:
                            where_conditions.append(f"a.{field} = ?")
                            params.append(value)
                    elif field == "file_size_min":
                        where_conditions.append("a.file_size >= ?")
                        params.append(value)
                    elif field == "file_size_max":
                        where_conditions.append("a.file_size <= ?")
                        params.append(value)
                    elif field == "created_after":
                        where_conditions.append("a.created_at >= ?")
                        params.append(value)
                    elif field == "created_before":
                        where_conditions.append("a.created_at <= ?")
                        params.append(value)
                    else:
                        # Custom metadata field - use EXISTS subquery
                        # For tags and arrays, use LIKE to check if value is contained
                        if field == "tags" or isinstance(value, list):
                            where_conditions.append(
                                "EXISTS (SELECT 1 FROM asset_metadata am WHERE am.asset_id = a.asset_id AND am.field_name = ? AND am.field_value LIKE ?)"
                            )
                            params.extend([field, f'%"{str(value)}"%'])
                        else:
                            where_conditions.append(
                                "EXISTS (SELECT 1 FROM asset_metadata am WHERE am.asset_id = a.asset_id AND am.field_name = ? AND am.field_value = ?)"
                            )
                            params.extend([field, str(value)])
            
            # Build WHERE clause
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # Count total results
            count_query = f"""
                SELECT COUNT(*)
                FROM assets a
                {where_clause}
            """
            total_count = conn.execute(count_query, params).fetchone()[0]
            
            # Build main query with sorting
            if sort_by in ["file_name", "file_size", "created_at", "mime_type", "asset_id", "archive_path"]:
                order_clause = f"ORDER BY a.{sort_by} {sort_order}"
            else:
                # Sort by custom metadata field using subquery
                order_clause = f"""
                    ORDER BY (
                        SELECT am.field_value 
                        FROM asset_metadata am 
                        WHERE am.asset_id = a.asset_id AND am.field_name = ?
                    ) {sort_order}
                """
                params.append(sort_by)
            
            main_query = f"""
                SELECT 
                    a.asset_id,
                    a.archive_path,
                    a.file_name,
                    a.file_size,
                    a.mime_type,
                    a.checksum_sha256,
                    a.profile_id,
                    a.created_at
                FROM assets a
                {where_clause}
                {order_clause}
                LIMIT ? OFFSET ?
            """
            
            # Add limit and offset to params
            params.extend([limit, offset])
            
            # Execute main query
            results = []
            for row in conn.execute(main_query, params):
                # Load custom metadata for each result
                metadata_query = """
                    SELECT field_name, field_value, field_type 
                    FROM asset_metadata 
                    WHERE asset_id = ?
                """
                metadata_rows = conn.execute(metadata_query, (row['asset_id'],))
                
                custom_metadata = {}
                for meta_row in metadata_rows:
                    field_value = meta_row['field_value']
                    field_type = meta_row['field_type']
                    
                    # Convert back to original type
                    if field_type == 'json':
                        import json
                        field_value = json.loads(field_value)
                    elif field_type == 'boolean':
                        field_value = field_value == '1'
                    elif field_type == 'int':
                        field_value = int(field_value)
                    elif field_type == 'float':
                        field_value = float(field_value)
                    
                    custom_metadata[meta_row['field_name']] = field_value
                
                result = SearchResult(
                    asset_id=row['asset_id'],
                    archive_path=row['archive_path'],
                    file_name=row['file_name'],
                    file_size=row['file_size'],
                    mime_type=row['mime_type'],
                    checksum_sha256=row['checksum_sha256'],
                    profile_id=row['profile_id'],
                    created_at=row['created_at'],
                    custom_metadata=custom_metadata
                )
                results.append(result)
            
            return results, total_count
            
        finally:
            conn.close()
    
    def search_by_checksum(self, checksum: str) -> Optional[SearchResult]:
        results, _ = self.search(filters={'checksum_sha256': checksum}, limit=1)
        return results[0] if results else None
    
    def search_duplicates(self) -> List[Tuple[str, List[SearchResult]]]:
        conn = self._get_connection()
        try:
            # Find checksums with multiple assets
            duplicate_checksums = conn.execute("""
                SELECT checksum_sha256, COUNT(*) as count
                FROM assets
                WHERE checksum_sha256 IS NOT NULL
                GROUP BY checksum_sha256
                HAVING count > 1
            """).fetchall()
            
            duplicates = []
            for row in duplicate_checksums:
                checksum = row['checksum_sha256']
                results, _ = self.search(filters={'checksum_sha256': checksum})
                duplicates.append((checksum, results))
            
            return duplicates
            
        finally:
            conn.close()
    
    def get_metadata_fields(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            fields = conn.execute("""
                SELECT DISTINCT field_name, field_type, COUNT(*) as usage_count
                FROM asset_metadata
                GROUP BY field_name, field_type
                ORDER BY usage_count DESC
            """).fetchall()
            
            return [
                {
                    'name': row['field_name'],
                    'type': row['field_type'],
                    'usage_count': row['usage_count']
                }
                for row in fields
            ]
            
        finally:
            conn.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the archive - delegate to IndexingService"""
        from .indexing import IndexingService
        indexing_service = IndexingService(self.archive)
        return indexing_service.get_statistics()