from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import uuid
from datetime import datetime


@dataclass
class ArchiveConfig:
    id: str
    name: str
    description: str
    root_path: str
    created_at: str
    updated_at: str
    version: str = "1.0"
    organization_schema: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.organization_schema is None:
            self.organization_schema = {
                "structure": "year/month/type",
                "preserve_original_names": True,
                "normalize_names": False
            }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "root_path": self.root_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "organization_schema": self.organization_schema
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArchiveConfig':
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            root_path=data["root_path"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            version=data.get("version", "1.0"),
            organization_schema=data.get("organization_schema")
        )


class Archive:
    CONFIG_FILENAME = "archive.json"
    PROFILES_DIR = "profiles"
    ASSETS_DIR = "assets"
    INDEX_DIR = ".index"
    
    def __init__(self, root_path: Path):
        self.root_path = Path(root_path).resolve()
        self.config: Optional[ArchiveConfig] = None
        
    @property
    def config_path(self) -> Path:
        return self.root_path / self.CONFIG_FILENAME
    
    @property
    def profiles_path(self) -> Path:
        return self.root_path / self.PROFILES_DIR
    
    @property
    def assets_path(self) -> Path:
        return self.root_path / self.ASSETS_DIR
    
    @property
    def index_path(self) -> Path:
        return self.root_path / self.INDEX_DIR
    
    def exists(self) -> bool:
        return self.root_path.exists() and self.config_path.exists()
    
    def create(self, name: str, description: str = "") -> 'Archive':
        if self.exists():
            raise ValueError(f"Archive already exists at {self.root_path}")
        
        self.root_path.mkdir(parents=True, exist_ok=True)
        self.profiles_path.mkdir(exist_ok=True)
        self.assets_path.mkdir(exist_ok=True)
        self.index_path.mkdir(exist_ok=True)
        
        now = datetime.now().isoformat()
        self.config = ArchiveConfig(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            root_path=str(self.root_path),
            created_at=now,
            updated_at=now
        )
        
        self.save_config()
        return self
    
    def load(self) -> 'Archive':
        if not self.exists():
            raise ValueError(f"No archive found at {self.root_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.config = ArchiveConfig.from_dict(data)
        
        return self
    
    def save_config(self):
        if not self.config:
            raise ValueError("No config to save")
        
        self.config.updated_at = datetime.now().isoformat()
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config.to_dict(), f, indent=2)
    
    def get_profiles(self) -> List[Path]:
        if not self.profiles_path.exists():
            return []
        return list(self.profiles_path.glob("*.json"))
    
    def get_asset_count(self) -> int:
        if not self.assets_path.exists():
            return 0
        return sum(1 for _ in self.assets_path.rglob("*") if _.is_file() and not _.name.endswith('.metadata.json'))