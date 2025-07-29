import re
import os
from pathlib import Path
from typing import Dict, Any
import mimetypes


def safe_filename(filename: str, max_length: int = 255) -> str:
    # Remove or replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    safe = safe.strip('. ')
    
    # Ensure filename is not empty
    if not safe:
        safe = "unnamed"
    
    # Truncate if too long (preserve extension if possible)
    if len(safe) > max_length:
        name, ext = os.path.splitext(safe)
        max_name_length = max_length - len(ext)
        safe = name[:max_name_length] + ext
    
    return safe


def create_directory_structure(base_path: Path, structure: str) -> Path:
    parts = structure.split('/')
    path = base_path
    
    for part in parts:
        path = path / part
        path.mkdir(parents=True, exist_ok=True)
    
    return path


def get_file_info(file_path: Path) -> Dict[str, Any]:
    stat = file_path.stat()
    mime_type, encoding = mimetypes.guess_type(str(file_path))
    
    return {
        "name": file_path.name,
        "size": stat.st_size,
        "created": stat.st_ctime,
        "modified": stat.st_mtime,
        "mime_type": mime_type,
        "encoding": encoding,
        "extension": file_path.suffix
    }