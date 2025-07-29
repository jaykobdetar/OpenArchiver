import shutil
import tempfile
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
import bagit
from datetime import datetime

from ..models import Archive, Asset
from .search import SearchService, SearchResult

logger = logging.getLogger(__name__)


class ExportService:
    def __init__(self, archive: Archive):
        self.archive = archive
        self.search_service = SearchService(archive)
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None
    
    def set_progress_callback(self, callback: Callable[[int, int, str], None]):
        self.progress_callback = callback
    
    def _report_progress(self, current: int, total: int, message: str):
        if self.progress_callback:
            self.progress_callback(current, total, message)
    
    def export_to_bagit(
        self,
        output_path: Path,
        search_filters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, str]] = None,
        checksums: List[str] = None
    ) -> Path:
        
        output_path = Path(output_path).resolve()
        
        # Default checksums
        if checksums is None:
            checksums = ['sha256']
        
        # Default metadata
        if metadata is None:
            metadata = {}
        
        # Add standard BagIt metadata
        metadata.update({
            'Source-Organization': metadata.get('Source-Organization', 'Archive Tool'),
            'Organization-Address': metadata.get('Organization-Address', 'Unknown'),
            'Contact-Name': metadata.get('Contact-Name', 'Archive Administrator'),
            'Contact-Email': metadata.get('Contact-Email', 'admin@archive.local'),
            'External-Description': metadata.get('External-Description', f'Export from {self.archive.config.name}'),
            'Bagging-Date': datetime.now().strftime('%Y-%m-%d'),
            'Bag-Software-Agent': 'Archive Tool v1.0'
        })
        
        # Search for assets to export
        if search_filters:
            assets, total = self.search_service.search(filters=search_filters, limit=10000)
        else:
            assets, total = self.search_service.search(limit=10000)
        
        logger.info(f"Exporting {total} assets to BagIt format")
        
        # Create temporary directory for bag contents
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            bag_path = temp_path / output_path.name
            bag_path.mkdir()
            
            # Copy assets to bag
            data_path = bag_path / "data"
            data_path.mkdir()
            
            for idx, search_result in enumerate(assets):
                self._report_progress(idx + 1, total, f"Copying {search_result.file_name}")
                
                # Get source file
                source_file = self.archive.root_path / search_result.archive_path
                
                if not source_file.exists():
                    logger.warning(f"Source file not found: {source_file}")
                    continue
                
                # Preserve directory structure in bag
                relative_path = Path(search_result.archive_path)
                target_file = data_path / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy2(source_file, target_file)
                
                # Copy metadata sidecar
                asset = Asset(source_file, self.archive.root_path)
                if asset.sidecar_path.exists():
                    target_sidecar = target_file.parent / f"{target_file.name}.metadata.json"
                    shutil.copy2(asset.sidecar_path, target_sidecar)
            
            # Create bag
            logger.info("Creating BagIt structure")
            bag = bagit.make_bag(str(bag_path), metadata, checksums=checksums)
            
            # Validate bag
            logger.info("Validating bag")
            bag.validate()
            
            # Move to final location
            if output_path.exists():
                if output_path.is_dir():
                    shutil.rmtree(output_path)
                else:
                    output_path.unlink()
            
            shutil.move(str(bag_path), str(output_path))
        
        logger.info(f"Export completed: {output_path}")
        return output_path
    
    def export_selection(
        self,
        asset_ids: List[str],
        output_path: Path,
        format: str = "directory",
        preserve_structure: bool = True
    ) -> Path:
        
        output_path = Path(output_path).resolve()
        
        if format == "directory":
            return self._export_to_directory(asset_ids, output_path, preserve_structure)
        elif format == "bagit":
            # Create filter for specific asset IDs
            filters = {'asset_id': asset_ids} if len(asset_ids) == 1 else None
            return self.export_to_bagit(output_path, filters)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_to_directory(
        self,
        asset_ids: List[str],
        output_path: Path,
        preserve_structure: bool
    ) -> Path:
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        exported_count = 0
        
        for idx, asset_id in enumerate(asset_ids):
            self._report_progress(idx + 1, len(asset_ids), f"Exporting asset {asset_id}")
            
            # Find asset
            results, _ = self.search_service.search(filters={'asset_id': asset_id}, limit=1)
            
            if not results:
                logger.warning(f"Asset not found: {asset_id}")
                continue
            
            search_result = results[0]
            source_file = self.archive.root_path / search_result.archive_path
            
            if not source_file.exists():
                logger.warning(f"Source file not found: {source_file}")
                continue
            
            # Determine target path
            if preserve_structure:
                relative_path = Path(search_result.archive_path)
                target_file = output_path / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                target_file = output_path / search_result.file_name
            
            # Handle duplicates
            if target_file.exists():
                counter = 1
                stem = target_file.stem
                suffix = target_file.suffix
                while target_file.exists():
                    target_file = target_file.parent / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            # Copy file
            shutil.copy2(source_file, target_file)
            
            # Copy metadata sidecar
            asset = Asset(source_file, self.archive.root_path)
            if asset.sidecar_path.exists():
                target_sidecar = target_file.parent / f"{target_file.name}.metadata.json"
                shutil.copy2(asset.sidecar_path, target_sidecar)
            
            exported_count += 1
        
        logger.info(f"Exported {exported_count} assets to {output_path}")
        return output_path
    
    def generate_manifest(self, output_file: Path, format: str = "json") -> Path:
        # Get all assets
        all_assets, total = self.search_service.search(limit=10000)
        
        manifest = {
            "archive": {
                "id": self.archive.config.id,
                "name": self.archive.config.name,
                "description": self.archive.config.description,
                "created_at": self.archive.config.created_at,
                "generated_at": datetime.now().isoformat()
            },
            "statistics": self.search_service.get_statistics(),
            "assets": []
        }
        
        for search_result in all_assets:
            asset_info = {
                "asset_id": search_result.asset_id,
                "archive_path": search_result.archive_path,
                "file_name": search_result.file_name,
                "file_size": search_result.file_size,
                "mime_type": search_result.mime_type,
                "checksum_sha256": search_result.checksum_sha256,
                "created_at": search_result.created_at,
                "custom_metadata": search_result.custom_metadata
            }
            manifest["assets"].append(asset_info)
        
        # Write manifest
        output_file = Path(output_file).resolve()
        
        if format == "json":
            import json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)
        elif format == "csv":
            import csv
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                if manifest["assets"]:
                    # Flatten custom metadata fields
                    all_fields = set()
                    for asset in manifest["assets"]:
                        all_fields.update(asset["custom_metadata"].keys())
                    
                    fieldnames = [
                        "asset_id", "archive_path", "file_name", "file_size",
                        "mime_type", "checksum_sha256", "created_at"
                    ] + sorted(all_fields)
                    
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for asset in manifest["assets"]:
                        row = {k: v for k, v in asset.items() if k != "custom_metadata"}
                        row.update(asset["custom_metadata"])
                        writer.writerow(row)
        else:
            raise ValueError(f"Unsupported manifest format: {format}")
        
        logger.info(f"Generated manifest: {output_file}")
        return output_file