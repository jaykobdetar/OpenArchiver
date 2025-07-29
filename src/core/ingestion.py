import shutil
import uuid
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import logging

from ..models import Archive, Asset, AssetMetadata, Profile
from ..utils.file_utils import safe_filename, create_directory_structure


logger = logging.getLogger(__name__)


class FileIngestionService:
    def __init__(self, archive: Archive):
        self.archive = archive
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None
        
    def set_progress_callback(self, callback: Callable[[int, int, str], None]):
        self.progress_callback = callback
    
    def _report_progress(self, current: int, total: int, message: str):
        if self.progress_callback:
            self.progress_callback(current, total, message)
    
    def ingest_file(
        self,
        source_path: Path,
        profile: Optional[Profile] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        target_subfolder: Optional[str] = None
    ) -> Asset:
        source_path = Path(source_path).resolve()
        
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        if not source_path.is_file():
            raise ValueError(f"Source path is not a file: {source_path}")
        
        # Generate unique asset ID
        asset_id = str(uuid.uuid4())
        
        # Determine target path within archive
        if target_subfolder:
            target_dir = self.archive.assets_path / target_subfolder
        else:
            # Use organization schema from archive config
            target_dir = self._organize_by_schema(source_path)
        
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Preserve original filename or normalize it
        if self.archive.config.organization_schema.get("preserve_original_names", True):
            target_filename = source_path.name
        else:
            target_filename = safe_filename(source_path.name)
        
        target_path = target_dir / target_filename
        
        # Handle filename conflicts
        if target_path.exists():
            target_path = self._handle_duplicate(target_path)
        
        # Copy file to archive
        logger.info(f"Copying {source_path} to {target_path}")
        shutil.copy2(source_path, target_path)
        
        # Create Asset instance
        asset = Asset(target_path, self.archive.root_path)
        
        # Calculate checksum
        logger.info(f"Calculating checksum for {target_path}")
        checksum = asset.calculate_checksum()
        
        # Get file metadata
        file_stat = target_path.stat()
        mime_type, _ = mimetypes.guess_type(str(target_path))
        
        # Create metadata
        now = datetime.now().isoformat()
        asset.metadata = AssetMetadata(
            asset_id=asset_id,
            original_path=str(source_path),
            archive_path=str(target_path.relative_to(self.archive.root_path)),
            file_size=file_stat.st_size,
            mime_type=mime_type,
            checksum_sha256=checksum,
            checksum_verified_at=now,
            profile_id=profile.id if profile else None,
            custom_metadata=custom_metadata or {},
            created_at=now,
            updated_at=now
        )
        
        # Save metadata sidecar
        asset.save_metadata()
        
        logger.info(f"Successfully ingested {source_path} as {asset_id}")
        return asset
    
    def ingest_directory(
        self,
        source_dir: Path,
        profile: Optional[Profile] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        recursive: bool = True
    ) -> List[Asset]:
        source_dir = Path(source_dir).resolve()
        
        if not source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")
        
        if not source_dir.is_dir():
            raise ValueError(f"Source path is not a directory: {source_dir}")
        
        # Collect all files to ingest
        if recursive:
            files = [f for f in source_dir.rglob("*") if f.is_file()]
        else:
            files = [f for f in source_dir.iterdir() if f.is_file()]
        
        assets = []
        total_files = len(files)
        
        for idx, file_path in enumerate(files):
            try:
                self._report_progress(idx + 1, total_files, f"Ingesting {file_path.name}")
                
                # Preserve relative structure from source directory
                rel_path = file_path.relative_to(source_dir)
                target_subfolder = str(rel_path.parent) if rel_path.parent != Path(".") else None
                
                asset = self.ingest_file(
                    file_path,
                    profile=profile,
                    custom_metadata=custom_metadata,
                    target_subfolder=target_subfolder
                )
                assets.append(asset)
                
            except Exception as e:
                logger.error(f"Failed to ingest {file_path}: {e}")
                continue
        
        return assets
    
    def _organize_by_schema(self, source_path: Path) -> Path:
        schema = self.archive.config.organization_schema.get("structure", "year/month/type")
        
        now = datetime.now()
        mime_type, _ = mimetypes.guess_type(str(source_path))
        
        # Build path components based on schema
        components = []
        for part in schema.split("/"):
            if part == "year":
                components.append(str(now.year))
            elif part == "month":
                components.append(f"{now.month:02d}")
            elif part == "day":
                components.append(f"{now.day:02d}")
            elif part == "type":
                if mime_type:
                    main_type = mime_type.split("/")[0]
                    components.append(main_type)
                else:
                    components.append("other")
            elif part == "extension":
                components.append(source_path.suffix[1:] if source_path.suffix else "no-ext")
            else:
                components.append(part)
        
        return self.archive.assets_path / Path(*components)
    
    def _handle_duplicate(self, target_path: Path) -> Path:
        counter = 1
        stem = target_path.stem
        suffix = target_path.suffix
        
        while target_path.exists():
            target_path = target_path.parent / f"{stem}_{counter}{suffix}"
            counter += 1
        
        return target_path