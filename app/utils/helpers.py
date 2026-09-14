import os
import shutil
from pathlib import Path
from typing import List
import uuid

ALLOWED_PDF_TYPES = {".pdf"}
ALLOWED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

def is_allowed_pdf(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_PDF_TYPES

def is_allowed_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_IMAGE_TYPES

def save_uploaded_file(file_content: bytes, original_filename: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Secure filename
    safe_name = "".join(c for c in original_filename if c.isalnum() or c in "._- ").strip()
    if not safe_name:
        safe_name = f"file_{uuid.uuid4().hex[:8]}"
    
    # Avoid overwrite
    dest_path = dest_dir / safe_name
    counter = 1
    while dest_path.exists():
        stem = dest_path.stem
        suffix = dest_path.suffix
        dest_path = dest_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    
    with open(dest_path, "wb") as f:
        f.write(file_content)
    
    return dest_path

def get_file_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)
