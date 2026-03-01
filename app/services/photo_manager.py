"""Photo file management — save/list/delete device photos on disk."""

import logging
import shutil
import time
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class PhotoManager:
    """Manages photo files in data/photos/{udid}/."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.photos_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, udid: str, data: bytes, label: str = "other",
             extension: str = ".jpg") -> tuple[str, str]:
        """Save photo bytes to disk. Returns (filename, relative_filepath)."""
        device_dir = self.base_dir / udid
        device_dir.mkdir(parents=True, exist_ok=True)

        timestamp = int(time.time() * 1000)
        filename = f"{timestamp}_{label}{extension}"
        filepath = device_dir / filename

        filepath.write_bytes(data)
        logger.info("Saved photo: %s", filepath)

        relative = f"{udid}/{filename}"
        return filename, relative

    def delete(self, relative_path: str) -> bool:
        """Delete a photo file by its relative path."""
        full_path = self.base_dir / relative_path
        if full_path.exists():
            full_path.unlink()
            logger.info("Deleted photo: %s", full_path)
            return True
        return False

    def get_path(self, relative_path: str) -> Optional[Path]:
        """Get absolute path to a photo, or None if missing."""
        full_path = self.base_dir / relative_path
        return full_path if full_path.exists() else None

    def list_files(self, udid: str) -> list[str]:
        """List photo filenames for a device."""
        device_dir = self.base_dir / udid
        if not device_dir.exists():
            return []
        return sorted(f.name for f in device_dir.iterdir() if f.is_file())

    def delete_all(self, udid: str) -> int:
        """Delete all photos for a device. Returns count deleted."""
        device_dir = self.base_dir / udid
        if not device_dir.exists():
            return 0
        count = sum(1 for f in device_dir.iterdir() if f.is_file())
        shutil.rmtree(device_dir)
        return count
