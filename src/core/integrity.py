import logging
import uuid
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import threading

from ..models import Archive, Asset, AssetMetadata
from .search import SearchService

logger = logging.getLogger(__name__)


def _verify_asset_standalone(asset_info):
    """Standalone function for process-based parallel verification"""
    asset_id, archive_path, archive_root_path = asset_info
    
    # Construct full path
    asset_path = Path(archive_root_path) / archive_path
    
    # Check if file exists
    if not asset_path.exists():
        return asset_id, "missing"
    
    # Create asset instance
    asset = Asset(asset_path, Path(archive_root_path))
    
    # Load metadata
    if not asset.load_metadata():
        return asset_id, "no_metadata"
    
    # Verify checksum
    if asset.verify_checksum():
        return asset_id, "verified"
    else:
        return asset_id, "corrupted"


class IntegrityReport:
    def __init__(self):
        self.total_assets = 0
        self.verified_assets = 0
        self.corrupted_assets = []
        self.missing_assets = []
        self.missing_metadata = []
        self.start_time = None
        self.end_time = None
    
    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0
    
    @property
    def success_rate(self) -> float:
        if self.total_assets == 0:
            return 0
        return (self.verified_assets / self.total_assets) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_assets": self.total_assets,
            "verified_assets": self.verified_assets,
            "corrupted_assets": len(self.corrupted_assets),
            "missing_assets": len(self.missing_assets),
            "missing_metadata": len(self.missing_metadata),
            "success_rate": self.success_rate,
            "duration_seconds": self.duration,
            "corrupted_files": self.corrupted_assets,
            "missing_files": self.missing_assets,
            "missing_metadata_files": self.missing_metadata
        }


class IntegrityService:
    def __init__(self, archive: Archive):
        self.archive = archive
        self.search_service = SearchService(archive)
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None
        self._cancel_verification = threading.Event()
    
    def set_progress_callback(self, callback: Callable[[int, int, str], None]):
        self.progress_callback = callback
    
    def _report_progress(self, current: int, total: int, message: str):
        if self.progress_callback:
            self.progress_callback(current, total, message)
    
    def cancel_verification(self):
        self._cancel_verification.set()
    
    def verify_all(self, max_workers: int = 4) -> IntegrityReport:
        report = IntegrityReport()
        report.start_time = datetime.now()
        
        # Reset cancel flag
        self._cancel_verification.clear()
        
        try:
            # Get all assets from the index
            all_assets, total = self.search_service.search(limit=10000)
            report.total_assets = total
            
            # Use single-threaded for very small datasets or when explicitly requested
            if max_workers == 1 or len(all_assets) < 10:
                # Single-threaded processing
                for idx, search_result in enumerate(all_assets):
                    if self._cancel_verification.is_set():
                        break
                    
                    self._report_progress(idx + 1, report.total_assets, f"Verifying {search_result.file_name}")
                    
                    try:
                        status = self._verify_asset(search_result.asset_id, search_result.archive_path)
                        
                        if status == "verified":
                            report.verified_assets += 1
                        elif status == "corrupted":
                            report.corrupted_assets.append(search_result.archive_path)
                        elif status == "missing":
                            report.missing_assets.append(search_result.archive_path)
                        elif status == "no_metadata":
                            report.missing_metadata.append(search_result.archive_path)
                            
                    except Exception as e:
                        logger.error(f"Error verifying asset {search_result.asset_id}: {e}")
            else:
                # Multi-process processing for true parallelism (bypasses GIL)
                asset_info_list = [
                    (search_result.asset_id, search_result.archive_path, str(self.archive.root_path))
                    for search_result in all_assets
                ]
                
                with ProcessPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all tasks at once
                    futures = {
                        executor.submit(_verify_asset_standalone, asset_info): (idx, all_assets[idx])
                        for idx, asset_info in enumerate(asset_info_list)
                    }
                    
                    # Process results as they complete
                    completed = 0
                    for future in as_completed(futures):
                        if self._cancel_verification.is_set():
                            break
                        
                        idx, search_result = futures[future]
                        completed += 1
                        self._report_progress(completed, report.total_assets, f"Verifying {search_result.file_name}")
                        
                        try:
                            asset_id, status = future.result()
                            
                            if status == "verified":
                                report.verified_assets += 1
                            elif status == "corrupted":
                                report.corrupted_assets.append(search_result.archive_path)
                            elif status == "missing":
                                report.missing_assets.append(search_result.archive_path)
                            elif status == "no_metadata":
                                report.missing_metadata.append(search_result.archive_path)
                                
                        except Exception as e:
                            logger.error(f"Error verifying asset {search_result.asset_id}: {e}")
            
        finally:
            report.end_time = datetime.now()
        
        return report
    
    def _verify_asset(self, asset_id: str, archive_path: str) -> str:
        # Construct full path
        asset_path = self.archive.root_path / archive_path
        
        # Check if file exists
        if not asset_path.exists():
            return "missing"
        
        # Create asset instance
        asset = Asset(asset_path, self.archive.root_path)
        
        # Load metadata
        if not asset.load_metadata():
            return "no_metadata"
        
        # Verify checksum
        if asset.verify_checksum():
            return "verified"
        else:
            return "corrupted"
    
    def verify_single(self, asset_id: str) -> Dict[str, Any]:
        # Find asset in index
        results, _ = self.search_service.search(filters={'asset_id': asset_id}, limit=1)
        
        if not results:
            return {
                "asset_id": asset_id,
                "status": "not_found",
                "message": "Asset not found in index"
            }
        
        search_result = results[0]
        status = self._verify_asset(asset_id, search_result.archive_path)
        
        return {
            "asset_id": asset_id,
            "archive_path": search_result.archive_path,
            "status": status,
            "verified_at": datetime.now().isoformat()
        }
    
    def find_orphaned_files(self) -> List[Path]:
        orphaned = []
        
        # Get all files in assets directory
        all_files = set()
        for file_path in self.archive.assets_path.rglob("*"):
            if file_path.is_file() and not file_path.name.endswith('.metadata.json'):
                all_files.add(file_path)
        
        # Get all indexed files
        indexed_files = set()
        all_assets, _ = self.search_service.search(limit=10000)
        for search_result in all_assets:
            asset_path = self.archive.root_path / search_result.archive_path
            indexed_files.add(asset_path)
        
        # Find orphaned files (in filesystem but not in index)
        orphaned = list(all_files - indexed_files)
        
        return orphaned
    
    def repair_index(self) -> Dict[str, int]:
        from .indexing import IndexingService
        
        stats = {
            "removed_missing": 0,
            "reindexed": 0,
            "newly_indexed": 0,
            "errors": 0
        }
        
        # Find and remove missing assets from index
        all_assets, _ = self.search_service.search(limit=10000)
        indexing_service = IndexingService(self.archive)
        
        for search_result in all_assets:
            asset_path = self.archive.root_path / search_result.archive_path
            
            if not asset_path.exists():
                # Remove from index
                if indexing_service.remove_asset(search_result.asset_id):
                    stats["removed_missing"] += 1
                else:
                    stats["errors"] += 1
        
        # Find orphaned files and index them
        orphaned = self.find_orphaned_files()
        
        for file_path in orphaned:
            asset = Asset(file_path, self.archive.root_path)
            
            # Check if metadata exists
            if asset.load_metadata():
                # Reindex existing asset
                if indexing_service.index_asset(asset):
                    stats["reindexed"] += 1
                else:
                    stats["errors"] += 1
            else:
                # Create new metadata and index
                try:
                    from ..core.ingestion import FileIngestionService
                    ingestion_service = FileIngestionService(self.archive)
                    
                    # Generate metadata for orphaned file
                    asset_id = str(uuid.uuid4())
                    checksum = asset.calculate_checksum()
                    file_stat = file_path.stat()
                    mime_type, _ = mimetypes.guess_type(str(file_path))
                    
                    now = datetime.now().isoformat()
                    asset.metadata = AssetMetadata(
                        asset_id=asset_id,
                        original_path=str(file_path),
                        archive_path=str(file_path.relative_to(self.archive.root_path)),
                        file_size=file_stat.st_size,
                        mime_type=mime_type,
                        checksum_sha256=checksum,
                        checksum_verified_at=now,
                        created_at=now,
                        updated_at=now
                    )
                    
                    asset.save_metadata()
                    
                    if indexing_service.index_asset(asset):
                        stats["newly_indexed"] += 1
                    else:
                        stats["errors"] += 1
                        
                except Exception as e:
                    logger.error(f"Failed to create metadata for orphaned file {file_path}: {e}")
                    stats["errors"] += 1
        
        return stats