"""Application configuration."""

import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    """Global application settings."""

    app_name: str = "iDiag"
    app_version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 18765
    debug: bool = False

    # Paths — resolved relative to project root
    project_root: Path = Path(__file__).resolve().parent.parent
    db_path: Path = Path("")
    data_dir: Path = Path("")
    crash_patterns_path: Path = Path("")
    device_capabilities_path: Path = Path("")

    # SICKW API
    sickw_api_key: str = os.environ.get("SICKW_API_KEY", "")
    sickw_base_url: str = "https://sickw.com/api.php"
    sickw_default_service: int = 61  # iPhone Carrier + FMI + Blacklist bundle

    def model_post_init(self, __context: object) -> None:
        if not self.db_path.is_absolute():
            self.db_path = self.project_root / "db" / "idiag.db"
        if not self.data_dir.is_absolute():
            self.data_dir = self.project_root / "data"
        self.crash_patterns_path = self.data_dir / "crash_patterns.json"
        self.device_capabilities_path = self.data_dir / "device_capabilities.json"


settings = Settings()
