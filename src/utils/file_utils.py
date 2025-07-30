import re
import os
from pathlib import Path
from typing import Dict, Any
import mimetypes


def safe_filename(filename: str, max_length: int = 255) -> str:
    # Handle None input
    if filename is None:
        raise AttributeError("filename cannot be None")
    
    # Handle edge case of max_length <= 0
    if max_length <= 0:
        return ""
    
    # Check if filename becomes empty after removing unsafe chars (before replacement)
    # This handles cases like "///" which should become "unnamed", not "___"
    temp_safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    temp_safe = temp_safe.strip('. ')
    will_be_empty = not temp_safe
    
    # Remove or replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
    
    # Handle edge case: only extension (keep it)
    if safe.startswith('.') and len(safe) > 1 and '.' not in safe[1:]:
        # This is just a file extension like ".txt", keep it as is
        if len(safe) <= max_length:
            return safe
    
    # Remove leading/trailing dots and spaces (but not for extension-only files)
    if not (safe.startswith('.') and len(safe) > 1 and '.' not in safe[1:]):
        safe = safe.strip('. ')
    
    # Ensure filename is not empty (use the check from before replacement)
    if not safe or will_be_empty:
        safe = "unnamed"
    
    # Truncate if too long (preserve extension if possible)
    if len(safe) > max_length:
        name, ext = os.path.splitext(safe)
        # If extension is longer than max_length, truncate the extension too
        if len(ext) >= max_length:
            safe = safe[:max_length]
        else:
            max_name_length = max_length - len(ext)
            if max_name_length <= 0:
                safe = ext[:max_length]
            else:
                safe = name[:max_name_length] + ext
    
    return safe


def create_directory_structure(base_path: Path, structure: str) -> Path:
    # Handle None inputs
    if base_path is None:
        raise AttributeError("base_path cannot be None")
    if structure is None:
        raise AttributeError("structure cannot be None")
    
    # Handle empty structure
    if not structure.strip():
        return base_path
    
    # Split structure - preserve trailing slash behavior
    parts = structure.split('/')
    # Remove empty parts except if there's a trailing slash (last part is empty)
    has_trailing_slash = structure.endswith('/')
    parts = [part for part in parts if part.strip()]
    
    path = base_path
    
    for part in parts:
        path = path / part
        path.mkdir(parents=True, exist_ok=True)
    
    # If there was a trailing slash, return a path inside the last created directory
    if has_trailing_slash and parts:
        # Return a path that represents being inside the last directory
        # Create a dummy path whose parent will be the directory we just created
        return path / ".directory_marker"
    
    return path


def get_file_info(file_path) -> Dict[str, Any]:
    # Convert string paths to Path objects
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
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