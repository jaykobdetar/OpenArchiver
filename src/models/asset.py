from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from pathlib import Path
import json
import hashlib
from datetime import datetime


@dataclass
class AssetMetadata:
    asset_id: str
    original_path: str
    archive_path: str  # Relative path within archive
    file_size: int
    mime_type: Optional[str] = None
    checksum_sha256: Optional[str] = None
    checksum_verified_at: Optional[str] = None
    profile_id: Optional[str] = None
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "original_path": self.original_path,
            "archive_path": self.archive_path,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "checksum_sha256": self.checksum_sha256,
            "checksum_verified_at": self.checksum_verified_at,
            "profile_id": self.profile_id,
            "custom_metadata": self.custom_metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetMetadata':
        return cls(
            asset_id=data["asset_id"],
            original_path=data["original_path"],
            archive_path=data["archive_path"],
            file_size=data["file_size"],
            mime_type=data.get("mime_type"),
            checksum_sha256=data.get("checksum_sha256"),
            checksum_verified_at=data.get("checksum_verified_at"),
            profile_id=data.get("profile_id"),
            custom_metadata=data.get("custom_metadata", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", "")
        )


class Asset:
    def __init__(self, file_path: Path, archive_root: Path):
        self.file_path = file_path
        self.archive_root = archive_root
        self.metadata: Optional[AssetMetadata] = None
        self._sidecar_filename = "metadata.json"
    
    @property
    def sidecar_path(self) -> Path:
        return self.file_path.parent / f"{self.file_path.name}.{self._sidecar_filename}"
    
    def calculate_checksum(self) -> str:
        sha256_hash = hashlib.sha256()
        with open(self.file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def verify_checksum(self) -> bool:
        if not self.metadata or not self.metadata.checksum_sha256:
            return False
        
        current_checksum = self.calculate_checksum()
        is_valid = current_checksum == self.metadata.checksum_sha256
        
        if is_valid:
            self.metadata.checksum_verified_at = datetime.now().isoformat()
            self.save_metadata()
        
        return is_valid
    
    def load_metadata(self) -> bool:
        if not self.sidecar_path.exists():
            return False
        
        try:
            with open(self.sidecar_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.metadata = AssetMetadata.from_dict(data)
            return True
        except Exception:
            return False
    
    def save_metadata(self):
        if not self.metadata:
            raise ValueError("No metadata to save")
        
        self.metadata.updated_at = datetime.now().isoformat()
        
        with open(self.sidecar_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata.to_dict(), f, indent=2)
    
    def get_relative_path(self) -> Path:
        try:
            return self.file_path.relative_to(self.archive_root)
        except ValueError:
            return self.file_path