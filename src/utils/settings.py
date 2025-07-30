import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class Settings:
    def __init__(self):
        self.settings_file = Path.home() / ".archive_tool" / "settings.json"
        self.settings_file.parent.mkdir(exist_ok=True)
        self._settings: Dict[str, Any] = {}
        self.load_settings()
    
    def load_settings(self):
        """Load settings from file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self._settings = json.load(f)
                logger.info(f"Loaded settings from {self.settings_file}")
            else:
                self._settings = self.get_default_settings()
                self.save_settings()
                logger.info("Created default settings")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            self._settings = self.get_default_settings()
    
    def save_settings(self):
        """Save settings to file."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2)
            logger.info(f"Saved settings to {self.settings_file}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    def get_default_settings(self) -> Dict[str, Any]:
        """Get default settings."""
        return {
            "default_archive_location": str(Path.home() / "Archives"),
            "recent_archives": [],
            "max_recent_archives": 10,
            "window_geometry": None,
            "window_maximized": False,
            "splitter_sizes": [300, 900]
        }
    
    def get(self, key: str, default=None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a setting value."""
        self._settings[key] = value
    
    def get_default_archive_location(self) -> Path:
        """Get the default archive location as a Path object."""
        location = self.get("default_archive_location", str(Path.home() / "Archives"))
        return Path(location)
    
    def set_default_archive_location(self, path: Path):
        """Set the default archive location."""
        self.set("default_archive_location", str(path))
        self.save_settings()
    
    def add_recent_archive(self, archive_path: Path):
        """Add an archive to the recent archives list."""
        recent = self.get("recent_archives", [])
        archive_str = str(archive_path)
        
        # Remove if already exists
        if archive_str in recent:
            recent.remove(archive_str)
        
        # Add to beginning
        recent.insert(0, archive_str)
        
        # Limit to max recent
        max_recent = self.get("max_recent_archives", 10)
        recent = recent[:max_recent]
        
        self.set("recent_archives", recent)
        self.save_settings()
    
    def get_recent_archives(self) -> list[Path]:
        """Get list of recent archive paths."""
        recent = self.get("recent_archives", [])
        return [Path(p) for p in recent if Path(p).exists()]
    
    def remove_recent_archive(self, archive_path: Path):
        """Remove an archive from recent archives."""
        recent = self.get("recent_archives", [])
        archive_str = str(archive_path)
        
        if archive_str in recent:
            recent.remove(archive_str)
            self.set("recent_archives", recent)
            self.save_settings()


# Global settings instance
settings = Settings()