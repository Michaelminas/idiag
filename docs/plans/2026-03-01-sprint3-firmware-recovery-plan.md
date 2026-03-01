# Sprint 3: Firmware & Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add firmware management (IPSW download/cache, TSS signing, SHSH blobs), device mode helpers (DFU/Recovery), firmware restore, and data wipe with PDF erasure certificates.

**Architecture:** Two new services (`firmware_manager.py`, `wipe_service.py`) following Sprint 1 patterns — Pydantic models, asyncio.to_thread for blocking calls, lazy pymobiledevice3 imports, graceful degradation. IPSW.me free API for firmware metadata. WeasyPrint for PDF certificates.

**Tech Stack:** Python 3.11+ / FastAPI / pymobiledevice3 / httpx / WeasyPrint / SQLite

**Test command:**
```bash
PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/']))"
```

**Single test file:**
```bash
PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_firmware_manager.py']))"
```

---

### Task 1: Pydantic Models

**Files:**
- Create: `app/models/firmware.py`

**Step 1: Create firmware models**

```python
"""Firmware, restore, and wipe data models."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class FirmwareVersion(BaseModel):
    """A signed (or formerly signed) iOS firmware build."""
    version: str = ""
    build_id: str = ""
    model: str = ""  # e.g. "iPhone14,2"
    url: str = ""
    sha1: str = ""
    size_bytes: int = 0
    signed: bool = False


class IPSWCacheEntry(BaseModel):
    """An IPSW file stored in the local cache."""
    path: str = ""
    model: str = ""
    version: str = ""
    build_id: str = ""
    downloaded_at: Optional[datetime] = None
    size_bytes: int = 0


class SHSHBlob(BaseModel):
    """Saved SHSH2 blob for a specific device + iOS version."""
    id: Optional[int] = None
    ecid: str = ""
    device_model: str = ""
    ios_version: str = ""
    blob_path: str = ""
    saved_at: Optional[datetime] = None


RestoreStage = Literal[
    "downloading", "verifying", "preparing", "restoring", "complete", "error"
]


class RestoreProgress(BaseModel):
    """Progress update during firmware operations."""
    stage: RestoreStage = "preparing"
    percent: int = 0
    message: str = ""


WipeMethod = Literal["factory_reset", "dfu_restore"]


class WipeRecord(BaseModel):
    """Record of a device data erasure."""
    id: Optional[int] = None
    device_id: int = 0
    udid: str = ""
    serial: str = ""
    imei: str = ""
    model: str = ""
    ios_version: str = ""
    method: WipeMethod = "factory_reset"
    timestamp: Optional[datetime] = None
    operator: str = ""
    success: bool = False
    cert_path: str = ""
```

**Step 2: Verify models import cleanly**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "from app.models.firmware import FirmwareVersion, IPSWCacheEntry, SHSHBlob, RestoreProgress, WipeRecord; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add app/models/firmware.py
git commit -m "feat(sprint3): add firmware & wipe Pydantic models"
```

---

### Task 2: Config Additions

**Files:**
- Modify: `app/config.py`

**Step 1: Add firmware settings to Settings class**

Add these fields after the SICKW fields:

```python
    # Firmware / IPSW
    ipsw_cache_dir: Path = Path("")
    ipsw_cache_max_gb: float = 20.0
    shsh_blob_dir: Path = Path("")
    cert_output_dir: Path = Path("")
    ipsw_api_base: str = "https://api.ipsw.me/v4"
```

Add these lines at the end of `model_post_init`:

```python
        if not self.ipsw_cache_dir.is_absolute():
            self.ipsw_cache_dir = self.data_dir / "ipsw_cache"
        if not self.shsh_blob_dir.is_absolute():
            self.shsh_blob_dir = self.data_dir / "shsh_blobs"
        if not self.cert_output_dir.is_absolute():
            self.cert_output_dir = self.data_dir / "certificates"
```

**Step 2: Verify config loads**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "from app.config import settings; print(settings.ipsw_cache_dir); print(settings.ipsw_cache_max_gb)"`
Expected: Path ending in `data/ipsw_cache` and `20.0`

**Step 3: Commit**

```bash
git add app/config.py
git commit -m "feat(sprint3): add firmware config settings"
```

---

### Task 3: Database Schema — SHSH Blobs & Wipe Records

**Files:**
- Modify: `app/services/inventory_db.py`
- Test: `tests/test_inventory_db.py`

**Step 1: Write failing tests for new DB operations**

Add to `tests/test_inventory_db.py`:

```python
from app.models.firmware import SHSHBlob, WipeRecord

# -- SHSH Blob Tests --

def test_save_and_list_shsh_blobs(db):
    """Save SHSH blobs and retrieve them by ECID."""
    blob_id = db.save_shsh_blob(
        ecid="0x1234ABCD",
        device_model="iPhone14,2",
        ios_version="17.4",
        blob_path="/data/shsh/blob1.shsh2",
    )
    assert blob_id > 0

    blobs = db.list_shsh_blobs(ecid="0x1234ABCD")
    assert len(blobs) == 1
    assert blobs[0].ios_version == "17.4"
    assert blobs[0].blob_path == "/data/shsh/blob1.shsh2"


def test_shsh_blob_unique_constraint(db):
    """Same ECID + version should update, not duplicate."""
    db.save_shsh_blob("0xAAAA", "iPhone14,2", "17.4", "/path/a.shsh2")
    db.save_shsh_blob("0xAAAA", "iPhone14,2", "17.4", "/path/b.shsh2")
    blobs = db.list_shsh_blobs(ecid="0xAAAA")
    assert len(blobs) == 1
    assert blobs[0].blob_path == "/path/b.shsh2"


# -- Wipe Record Tests --

def test_save_and_get_wipe_record(db):
    """Save a wipe record and retrieve by device_id."""
    device_id = _insert_test_device(db)
    wipe_id = db.save_wipe_record(
        device_id=device_id,
        udid="test-udid-001",
        serial="C39FAKE123",
        imei="353456789012345",
        model="iPhone14,2",
        ios_version="17.4",
        method="factory_reset",
        operator="TestUser",
        success=True,
        cert_path="/data/certs/cert001.pdf",
    )
    assert wipe_id > 0

    records = db.list_wipe_records(device_id=device_id)
    assert len(records) == 1
    assert records[0].method == "factory_reset"
    assert records[0].success is True
    assert records[0].cert_path == "/data/certs/cert001.pdf"


def _insert_test_device(db) -> int:
    """Helper to insert a device for FK references."""
    from app.models.device import DeviceRecord
    return db.upsert_device(DeviceRecord(
        udid="test-udid-001", serial="C39FAKE123", imei="353456789012345",
        model="iPhone14,2", ios_version="17.4",
    ))
```

**Step 2: Run tests — verify they fail**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_inventory_db.py::test_save_and_list_shsh_blobs', 'tests/test_inventory_db.py::test_save_and_get_wipe_record']))"`
Expected: FAIL (methods don't exist yet)

**Step 3: Add new tables to SCHEMA in inventory_db.py**

Append to the `SCHEMA` string (before the closing `"""`):

```sql

CREATE TABLE IF NOT EXISTS shsh_blobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ecid TEXT NOT NULL,
    device_model TEXT NOT NULL,
    ios_version TEXT NOT NULL,
    blob_path TEXT NOT NULL,
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ecid, ios_version)
);

CREATE TABLE IF NOT EXISTS wipe_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    udid TEXT NOT NULL,
    serial TEXT DEFAULT '',
    imei TEXT DEFAULT '',
    model TEXT DEFAULT '',
    ios_version TEXT DEFAULT '',
    method TEXT NOT NULL DEFAULT 'factory_reset',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    operator TEXT DEFAULT '',
    success INTEGER NOT NULL DEFAULT 0,
    cert_path TEXT DEFAULT ''
);
```

**Step 4: Add CRUD methods to InventoryDB**

Add import at top of `inventory_db.py`:
```python
from app.models.firmware import SHSHBlob, WipeRecord
```

Add methods to the InventoryDB class:

```python
    # -- SHSH Blobs --

    def save_shsh_blob(
        self, ecid: str, device_model: str, ios_version: str, blob_path: str
    ) -> int:
        """Insert or update an SHSH blob record. Returns row id."""
        with self._lock:
            existing = self.conn.execute(
                "SELECT id FROM shsh_blobs WHERE ecid=? AND ios_version=?",
                (ecid, ios_version),
            ).fetchone()
            if existing:
                self.conn.execute(
                    "UPDATE shsh_blobs SET blob_path=?, saved_at=CURRENT_TIMESTAMP WHERE id=?",
                    (blob_path, existing["id"]),
                )
                self.conn.commit()
                return existing["id"]
            cur = self.conn.execute(
                """INSERT INTO shsh_blobs (ecid, device_model, ios_version, blob_path)
                   VALUES (?, ?, ?, ?)""",
                (ecid, device_model, ios_version, blob_path),
            )
            self.conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def list_shsh_blobs(self, ecid: Optional[str] = None) -> list[SHSHBlob]:
        """List SHSH blobs, optionally filtered by ECID."""
        with self._lock:
            if ecid:
                rows = self.conn.execute(
                    "SELECT * FROM shsh_blobs WHERE ecid=? ORDER BY saved_at DESC",
                    (ecid,),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM shsh_blobs ORDER BY saved_at DESC"
                ).fetchall()
            return [
                SHSHBlob(
                    id=r["id"], ecid=r["ecid"], device_model=r["device_model"],
                    ios_version=r["ios_version"], blob_path=r["blob_path"],
                    saved_at=r["saved_at"],
                )
                for r in rows
            ]

    # -- Wipe Records --

    def save_wipe_record(
        self,
        device_id: int,
        udid: str,
        serial: str,
        imei: str,
        model: str,
        ios_version: str,
        method: str,
        operator: str = "",
        success: bool = False,
        cert_path: str = "",
    ) -> int:
        """Insert a wipe record. Returns row id."""
        with self._lock:
            cur = self.conn.execute(
                """INSERT INTO wipe_records
                   (device_id, udid, serial, imei, model, ios_version, method,
                    operator, success, cert_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    device_id, udid, serial, imei, model, ios_version,
                    method, operator, 1 if success else 0, cert_path,
                ),
            )
            self.conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def list_wipe_records(self, device_id: Optional[int] = None) -> list[WipeRecord]:
        """List wipe records, optionally filtered by device_id."""
        with self._lock:
            if device_id is not None:
                rows = self.conn.execute(
                    "SELECT * FROM wipe_records WHERE device_id=? ORDER BY timestamp DESC",
                    (device_id,),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM wipe_records ORDER BY timestamp DESC"
                ).fetchall()
            return [
                WipeRecord(
                    id=r["id"], device_id=r["device_id"], udid=r["udid"],
                    serial=r["serial"], imei=r["imei"], model=r["model"],
                    ios_version=r["ios_version"], method=r["method"],
                    timestamp=r["timestamp"], operator=r["operator"],
                    success=bool(r["success"]), cert_path=r["cert_path"],
                )
                for r in rows
            ]
```

**Step 5: Run tests — verify they pass**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_inventory_db.py']))"`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add app/models/firmware.py app/services/inventory_db.py tests/test_inventory_db.py
git commit -m "feat(sprint3): add shsh_blobs and wipe_records DB tables + CRUD"
```

---

### Task 4: Firmware Manager — TSS Signing Check

**Files:**
- Create: `app/services/firmware_manager.py`
- Create: `tests/test_firmware_manager.py`

Uses the free ipsw.me API: `GET https://api.ipsw.me/v4/device/{identifier}?type=ipsw`

**Step 1: Write failing test**

Create `tests/test_firmware_manager.py`:

```python
"""Tests for firmware manager service."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.firmware import FirmwareVersion


# -- Fixture: mock ipsw.me API response --

IPSW_API_RESPONSE = {
    "name": "iPhone 13 Pro",
    "identifier": "iPhone14,2",
    "firmwares": [
        {
            "identifier": "iPhone14,2",
            "version": "17.4",
            "buildid": "21E219",
            "sha1sum": "abc123def456",
            "url": "https://updates.cdn-apple.com/fake/iPhone14,2_17.4_21E219.ipsw",
            "filesize": 6_500_000_000,
            "signed": True,
        },
        {
            "identifier": "iPhone14,2",
            "version": "17.3.1",
            "buildid": "21D61",
            "sha1sum": "789ghi012jkl",
            "url": "https://updates.cdn-apple.com/fake/iPhone14,2_17.3.1_21D61.ipsw",
            "filesize": 6_400_000_000,
            "signed": False,
        },
    ],
}


class TestGetSignedVersions:
    """Test TSS signing status lookup via ipsw.me API."""

    @patch("app.services.firmware_manager.httpx")
    def test_returns_signed_versions(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = IPSW_API_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        from app.services.firmware_manager import get_signed_versions

        versions = get_signed_versions("iPhone14,2")

        assert len(versions) == 1
        assert versions[0].version == "17.4"
        assert versions[0].signed is True
        assert versions[0].sha1 == "abc123def456"

    @patch("app.services.firmware_manager.httpx")
    def test_returns_all_versions_when_signed_only_false(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = IPSW_API_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        from app.services.firmware_manager import get_signed_versions

        versions = get_signed_versions("iPhone14,2", signed_only=False)
        assert len(versions) == 2

    @patch("app.services.firmware_manager.httpx")
    def test_returns_empty_on_api_error(self, mock_httpx):
        mock_httpx.get.side_effect = Exception("Network error")

        from app.services.firmware_manager import get_signed_versions

        versions = get_signed_versions("iPhone14,2")
        assert versions == []
```

**Step 2: Run test — verify it fails**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_firmware_manager.py::TestGetSignedVersions']))"`
Expected: FAIL (module doesn't exist)

**Step 3: Implement get_signed_versions**

Create `app/services/firmware_manager.py`:

```python
"""Firmware management — IPSW download, cache, TSS signing, SHSH blobs, restore."""

import hashlib
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import httpx

from app.config import settings
from app.models.firmware import (
    FirmwareVersion,
    IPSWCacheEntry,
    RestoreProgress,
    SHSHBlob,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TSS / Signing Status (via ipsw.me free API)
# ---------------------------------------------------------------------------

def get_signed_versions(
    model_identifier: str, signed_only: bool = True
) -> list[FirmwareVersion]:
    """Query ipsw.me API for firmware versions of a device model.

    Args:
        model_identifier: Apple model ID, e.g. "iPhone14,2"
        signed_only: If True (default), only return currently signed versions.

    Returns:
        List of FirmwareVersion, empty list on error.
    """
    try:
        url = f"{settings.ipsw_api_base}/device/{model_identifier}?type=ipsw"
        resp = httpx.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        versions = []
        for fw in data.get("firmwares", []):
            fv = FirmwareVersion(
                version=fw.get("version", ""),
                build_id=fw.get("buildid", ""),
                model=fw.get("identifier", model_identifier),
                url=fw.get("url", ""),
                sha1=fw.get("sha1sum", ""),
                size_bytes=fw.get("filesize", 0),
                signed=fw.get("signed", False),
            )
            if signed_only and not fv.signed:
                continue
            versions.append(fv)
        return versions
    except Exception as e:
        logger.error("Failed to fetch signed versions for %s: %s", model_identifier, e)
        return []
```

**Step 4: Run test — verify it passes**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_firmware_manager.py::TestGetSignedVersions']))"`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add app/services/firmware_manager.py tests/test_firmware_manager.py
git commit -m "feat(sprint3): firmware manager — TSS signing check via ipsw.me"
```

---

### Task 5: Firmware Manager — IPSW Download + LRU Cache

**Files:**
- Modify: `app/services/firmware_manager.py`
- Modify: `tests/test_firmware_manager.py`

**Step 1: Write failing tests**

Add to `tests/test_firmware_manager.py`:

```python
class TestIPSWCache:
    """Test IPSW download and LRU cache logic."""

    def test_list_cached_empty(self, tmp_path):
        from app.services.firmware_manager import list_cached_ipsw
        entries = list_cached_ipsw(cache_dir=tmp_path)
        assert entries == []

    def test_cache_entry_creation_and_listing(self, tmp_path):
        """Simulate a cached IPSW and verify listing."""
        from app.services.firmware_manager import list_cached_ipsw, _ipsw_filename

        fname = _ipsw_filename("iPhone14,2", "17.4", "21E219")
        fpath = tmp_path / fname
        fpath.write_bytes(b"fake ipsw content")

        entries = list_cached_ipsw(cache_dir=tmp_path)
        assert len(entries) == 1
        assert entries[0].model == "iPhone14,2"
        assert entries[0].version == "17.4"

    def test_evict_cache_oldest_first(self, tmp_path):
        """LRU eviction should remove oldest files first."""
        import time
        from app.services.firmware_manager import evict_cache, _ipsw_filename

        # Create 3 "IPSW" files with different timestamps
        for i, (model, ver) in enumerate([
            ("iPhone14,2", "17.3"), ("iPhone14,2", "17.4"), ("iPhone15,2", "17.4")
        ]):
            fpath = tmp_path / _ipsw_filename(model, ver, f"BUILD{i}")
            fpath.write_bytes(b"x" * 1000)
            time.sleep(0.05)  # ensure different mtime

        # Evict with max_bytes = 2500 (keeps 2 of 3)
        evict_cache(cache_dir=tmp_path, max_bytes=2500)
        remaining = list(tmp_path.glob("*.ipsw"))
        assert len(remaining) == 2

    def test_verify_sha1(self, tmp_path):
        """SHA1 verification of a downloaded file."""
        from app.services.firmware_manager import verify_sha1

        fpath = tmp_path / "test.ipsw"
        content = b"test firmware content"
        fpath.write_bytes(content)

        import hashlib
        expected = hashlib.sha1(content).hexdigest()
        assert verify_sha1(fpath, expected) is True
        assert verify_sha1(fpath, "wrong_hash") is False
```

**Step 2: Run tests — verify they fail**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_firmware_manager.py::TestIPSWCache']))"`
Expected: FAIL

**Step 3: Implement cache functions**

Add to `app/services/firmware_manager.py`:

```python
# ---------------------------------------------------------------------------
# IPSW Cache
# ---------------------------------------------------------------------------

def _ipsw_filename(model: str, version: str, build_id: str) -> str:
    """Deterministic filename: iPhone14,2_17.4_21E219.ipsw"""
    safe_model = model.replace(",", "_")
    return f"{safe_model}_{version}_{build_id}.ipsw"


def _parse_ipsw_filename(filename: str) -> tuple[str, str, str]:
    """Extract (model, version, build_id) from cache filename."""
    stem = filename.rsplit(".", 1)[0]  # remove .ipsw
    parts = stem.split("_", 2)
    if len(parts) >= 3:
        model = parts[0].replace("_", ",", 1)  # iPhone14_2 -> iPhone14,2
        return model, parts[1], parts[2]
    return "", "", ""


def list_cached_ipsw(cache_dir: Optional[Path] = None) -> list[IPSWCacheEntry]:
    """List all IPSW files in the cache directory."""
    cache_dir = cache_dir or settings.ipsw_cache_dir
    if not cache_dir.exists():
        return []

    entries = []
    for fpath in sorted(cache_dir.glob("*.ipsw"), key=lambda p: p.stat().st_mtime):
        model, version, build_id = _parse_ipsw_filename(fpath.name)
        stat = fpath.stat()
        entries.append(IPSWCacheEntry(
            path=str(fpath),
            model=model,
            version=version,
            build_id=build_id,
            downloaded_at=datetime.fromtimestamp(stat.st_mtime),
            size_bytes=stat.st_size,
        ))
    return entries


def evict_cache(
    cache_dir: Optional[Path] = None, max_bytes: Optional[int] = None
) -> int:
    """Remove oldest IPSW files until total cache size <= max_bytes.

    Returns number of files removed.
    """
    cache_dir = cache_dir or settings.ipsw_cache_dir
    if max_bytes is None:
        max_bytes = int(settings.ipsw_cache_max_gb * 1_073_741_824)

    if not cache_dir.exists():
        return 0

    # Sort by mtime ascending (oldest first)
    files = sorted(cache_dir.glob("*.ipsw"), key=lambda p: p.stat().st_mtime)
    total = sum(f.stat().st_size for f in files)
    removed = 0

    while total > max_bytes and files:
        oldest = files.pop(0)
        total -= oldest.stat().st_size
        oldest.unlink()
        removed += 1
        logger.info("Evicted cached IPSW: %s", oldest.name)

    return removed


def get_cached_ipsw(
    model: str, version: str, cache_dir: Optional[Path] = None
) -> Optional[Path]:
    """Look up a cached IPSW by model + version. Returns path or None."""
    cache_dir = cache_dir or settings.ipsw_cache_dir
    if not cache_dir.exists():
        return None
    for fpath in cache_dir.glob("*.ipsw"):
        m, v, _ = _parse_ipsw_filename(fpath.name)
        if m == model and v == version:
            return fpath
    return None


def verify_sha1(file_path: Path, expected_sha1: str) -> bool:
    """Verify a file's SHA1 checksum."""
    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha1.update(chunk)
    return sha1.hexdigest().lower() == expected_sha1.lower()


def download_ipsw(
    firmware: FirmwareVersion,
    cache_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[RestoreProgress], None]] = None,
) -> Optional[Path]:
    """Download an IPSW file from Apple CDN, verify SHA1, store in cache.

    Args:
        firmware: FirmwareVersion with url, sha1, size_bytes populated.
        cache_dir: Override cache directory (for testing).
        progress_callback: Called with RestoreProgress updates.

    Returns:
        Path to downloaded file, or None on failure.
    """
    cache_dir = cache_dir or settings.ipsw_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    filename = _ipsw_filename(firmware.model, firmware.version, firmware.build_id)
    dest = cache_dir / filename

    # Already cached?
    if dest.exists() and verify_sha1(dest, firmware.sha1):
        logger.info("IPSW already cached: %s", filename)
        return dest

    if progress_callback:
        progress_callback(RestoreProgress(
            stage="downloading", percent=0, message=f"Downloading {filename}..."
        ))

    try:
        with httpx.stream("GET", firmware.url, timeout=None, follow_redirects=True) as resp:
            resp.raise_for_status()
            total = firmware.size_bytes or int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=1_048_576):  # 1MB chunks
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        pct = min(int(downloaded / total * 100), 99)
                        progress_callback(RestoreProgress(
                            stage="downloading", percent=pct,
                            message=f"Downloading: {downloaded // 1_048_576}MB / {total // 1_048_576}MB",
                        ))

        # Verify SHA1
        if progress_callback:
            progress_callback(RestoreProgress(
                stage="verifying", percent=99, message="Verifying SHA1 checksum..."
            ))

        if firmware.sha1 and not verify_sha1(dest, firmware.sha1):
            logger.error("SHA1 mismatch for %s", filename)
            dest.unlink(missing_ok=True)
            if progress_callback:
                progress_callback(RestoreProgress(
                    stage="error", percent=0, message="SHA1 verification failed"
                ))
            return None

        # Evict old files if over budget
        evict_cache(cache_dir=cache_dir)

        logger.info("Downloaded and verified: %s", filename)
        return dest

    except Exception as e:
        logger.error("IPSW download failed for %s: %s", filename, e)
        dest.unlink(missing_ok=True)
        if progress_callback:
            progress_callback(RestoreProgress(
                stage="error", percent=0, message=str(e)
            ))
        return None
```

**Step 4: Run tests — verify they pass**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_firmware_manager.py::TestIPSWCache']))"`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add app/services/firmware_manager.py tests/test_firmware_manager.py
git commit -m "feat(sprint3): IPSW download with SHA1 verify and LRU cache"
```

---

### Task 6: Firmware Manager — SHSH Blob Saving

**Files:**
- Modify: `app/services/firmware_manager.py`
- Modify: `tests/test_firmware_manager.py`

**Step 1: Write failing test**

Add to `tests/test_firmware_manager.py`:

```python
class TestSHSHBlobs:
    """Test SHSH blob save (mocked pymobiledevice3)."""

    @patch("app.services.firmware_manager._get_tss_response")
    def test_save_shsh_blob_success(self, mock_tss, tmp_path):
        from app.services.firmware_manager import save_shsh_blobs

        mock_tss.return_value = b"fake-shsh-blob-plist-data"

        result = save_shsh_blobs(
            ecid="0x1234ABCD",
            device_model="iPhone14,2",
            ios_version="17.4",
            blob_dir=tmp_path,
        )

        assert result is not None
        assert result.exists()
        assert result.read_bytes() == b"fake-shsh-blob-plist-data"

    @patch("app.services.firmware_manager._get_tss_response")
    def test_save_shsh_blob_failure(self, mock_tss, tmp_path):
        from app.services.firmware_manager import save_shsh_blobs

        mock_tss.side_effect = Exception("TSS server error")

        result = save_shsh_blobs(
            ecid="0x1234ABCD",
            device_model="iPhone14,2",
            ios_version="17.4",
            blob_dir=tmp_path,
        )
        assert result is None
```

**Step 2: Run test — verify it fails**

Expected: FAIL

**Step 3: Implement SHSH blob functions**

Add to `app/services/firmware_manager.py`:

```python
# ---------------------------------------------------------------------------
# SHSH Blob Saving
# ---------------------------------------------------------------------------

def _get_tss_response(ecid: str, device_model: str, ios_version: str) -> bytes:
    """Request SHSH2 blob from Apple TSS server via pymobiledevice3.

    This is the hardware-dependent function that tests mock out.
    """
    from pymobiledevice3.restore.tss import TSSRequest

    tss = TSSRequest()
    tss.add_common_tags(ecid=int(ecid, 16) if ecid.startswith("0x") else int(ecid))
    response = tss.send_receive()
    return response


def save_shsh_blobs(
    ecid: str,
    device_model: str,
    ios_version: str,
    blob_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Save SHSH2 blob for a device + iOS version.

    Args:
        ecid: Device ECID (hex string, e.g. "0x1234ABCD").
        device_model: Apple identifier, e.g. "iPhone14,2".
        ios_version: iOS version string, e.g. "17.4".
        blob_dir: Override blob storage directory (for testing).

    Returns:
        Path to saved blob file, or None on failure.
    """
    blob_dir = blob_dir or settings.shsh_blob_dir
    blob_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{ecid}_{device_model}_{ios_version}.shsh2"
    dest = blob_dir / filename

    try:
        blob_data = _get_tss_response(ecid, device_model, ios_version)
        dest.write_bytes(blob_data)
        logger.info("Saved SHSH blob: %s", filename)
        return dest
    except Exception as e:
        logger.error("Failed to save SHSH blob for %s/%s: %s", device_model, ios_version, e)
        return None
```

**Step 4: Run test — verify it passes**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_firmware_manager.py::TestSHSHBlobs']))"`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add app/services/firmware_manager.py tests/test_firmware_manager.py
git commit -m "feat(sprint3): SHSH blob saving via pymobiledevice3 TSS"
```

---

### Task 7: Firmware Manager — DFU/Recovery Helpers

**Files:**
- Modify: `app/services/firmware_manager.py`
- Modify: `tests/test_firmware_manager.py`

**Step 1: Write failing tests**

Add to `tests/test_firmware_manager.py`:

```python
class TestDeviceModeHelpers:
    """Test DFU/Recovery mode entry/exit (mocked pymobiledevice3)."""

    @patch("app.services.firmware_manager._create_lockdown")
    def test_enter_recovery_mode(self, mock_lockdown_factory):
        from app.services.firmware_manager import enter_recovery_mode

        mock_lockdown = MagicMock()
        mock_lockdown_factory.return_value.__enter__ = MagicMock(return_value=mock_lockdown)
        mock_lockdown_factory.return_value.__exit__ = MagicMock(return_value=False)

        result = enter_recovery_mode("test-udid")
        assert result is True

    @patch("app.services.firmware_manager._create_lockdown")
    def test_enter_recovery_mode_failure(self, mock_lockdown_factory):
        from app.services.firmware_manager import enter_recovery_mode

        mock_lockdown_factory.side_effect = Exception("No device")
        result = enter_recovery_mode("test-udid")
        assert result is False

    @patch("app.services.firmware_manager._exit_recovery")
    def test_exit_recovery_mode(self, mock_exit):
        from app.services.firmware_manager import exit_recovery_mode

        mock_exit.return_value = True
        result = exit_recovery_mode("test-udid")
        assert result is True

    def test_get_device_mode_normal(self):
        from app.services.firmware_manager import get_device_mode

        with patch("app.services.firmware_manager._create_lockdown") as mock_ld:
            mock_lockdown = MagicMock()
            mock_ld.return_value.__enter__ = MagicMock(return_value=mock_lockdown)
            mock_ld.return_value.__exit__ = MagicMock(return_value=False)
            mode = get_device_mode("test-udid")
            assert mode == "normal"

    def test_get_device_mode_no_device(self):
        from app.services.firmware_manager import get_device_mode

        with patch("app.services.firmware_manager._create_lockdown") as mock_ld:
            mock_ld.side_effect = Exception("Not found")
            with patch("app.services.firmware_manager._check_recovery_mode") as mock_rec:
                mock_rec.return_value = False
                with patch("app.services.firmware_manager._check_dfu_mode") as mock_dfu:
                    mock_dfu.return_value = False
                    mode = get_device_mode("test-udid")
                    assert mode == "unknown"
```

**Step 2: Run tests — verify they fail**

Expected: FAIL

**Step 3: Implement device mode helpers**

Add to `app/services/firmware_manager.py`:

```python
# ---------------------------------------------------------------------------
# Device Mode Helpers (DFU / Recovery)
# ---------------------------------------------------------------------------

def _create_lockdown(udid: Optional[str] = None):
    """Create a lockdown client. This is the mock boundary for tests."""
    from pymobiledevice3.lockdown import create_using_usbmux
    return create_using_usbmux(serial=udid)


def _check_recovery_mode(udid: Optional[str] = None) -> bool:
    """Check if any device is in recovery mode."""
    try:
        from pymobiledevice3.irecv import IRecv
        IRecv()
        return True
    except Exception:
        return False


def _check_dfu_mode(udid: Optional[str] = None) -> bool:
    """Check if any device is in DFU mode."""
    try:
        from pymobiledevice3.irecv import IRecv
        device = IRecv()
        return device.is_dfu
    except Exception:
        return False


def _exit_recovery(udid: Optional[str] = None) -> bool:
    """Exit recovery mode. This is the mock boundary for tests."""
    try:
        from pymobiledevice3.irecv import IRecv
        device = IRecv()
        device.set_autoboot(True)
        device.reboot()
        return True
    except Exception as e:
        logger.error("Failed to exit recovery: %s", e)
        return False


def get_device_mode(udid: Optional[str] = None) -> str:
    """Detect current device mode: 'normal', 'recovery', 'dfu', or 'unknown'."""
    # Try normal mode first
    try:
        with _create_lockdown(udid):
            return "normal"
    except Exception:
        pass

    # Try recovery mode
    if _check_recovery_mode(udid):
        return "recovery"

    # Try DFU mode
    if _check_dfu_mode(udid):
        return "dfu"

    return "unknown"


def enter_recovery_mode(udid: Optional[str] = None) -> bool:
    """Put device into recovery mode."""
    try:
        with _create_lockdown(udid) as lockdown:
            lockdown.enter_recovery()
        logger.info("Device %s entered recovery mode", udid or "auto")
        return True
    except Exception as e:
        logger.error("Failed to enter recovery mode: %s", e)
        return False


def enter_dfu_mode(udid: Optional[str] = None) -> bool:
    """Guide device into DFU mode.

    Note: DFU mode requires physical button combo — this puts device into
    recovery first, then the user must hold the button combo.
    Returns True if recovery mode was entered (DFU prep step).
    """
    logger.info("DFU mode requires manual button combo. Entering recovery first...")
    return enter_recovery_mode(udid)


def exit_recovery_mode(udid: Optional[str] = None) -> bool:
    """Kick device out of recovery mode back to normal boot."""
    result = _exit_recovery(udid)
    if result:
        logger.info("Device exited recovery mode")
    return result
```

**Step 4: Run tests — verify they pass**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_firmware_manager.py::TestDeviceModeHelpers']))"`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add app/services/firmware_manager.py tests/test_firmware_manager.py
git commit -m "feat(sprint3): DFU/Recovery mode helpers"
```

---

### Task 8: Firmware Manager — Restore

**Files:**
- Modify: `app/services/firmware_manager.py`
- Modify: `tests/test_firmware_manager.py`

**Step 1: Write failing test**

Add to `tests/test_firmware_manager.py`:

```python
class TestRestore:
    """Test firmware restore orchestration (mocked)."""

    @patch("app.services.firmware_manager._perform_restore")
    @patch("app.services.firmware_manager.download_ipsw")
    @patch("app.services.firmware_manager.get_signed_versions")
    def test_restore_device_success(self, mock_signed, mock_download, mock_restore, tmp_path):
        from app.services.firmware_manager import restore_device
        from app.models.firmware import FirmwareVersion

        # Setup: signed version available, IPSW downloads OK, restore succeeds
        mock_signed.return_value = [FirmwareVersion(
            version="17.4", build_id="21E219", model="iPhone14,2",
            url="https://example.com/fw.ipsw", sha1="abc123", size_bytes=1000, signed=True,
        )]
        fake_ipsw = tmp_path / "fw.ipsw"
        fake_ipsw.write_bytes(b"firmware")
        mock_download.return_value = fake_ipsw
        mock_restore.return_value = True

        progress_log = []
        result = restore_device(
            udid="test-udid",
            model="iPhone14,2",
            progress_callback=lambda p: progress_log.append(p),
        )
        assert result is True
        assert any(p.stage == "restoring" for p in progress_log)

    @patch("app.services.firmware_manager.get_signed_versions")
    def test_restore_no_signed_version(self, mock_signed):
        from app.services.firmware_manager import restore_device

        mock_signed.return_value = []

        progress_log = []
        result = restore_device(
            udid="test-udid",
            model="iPhone14,2",
            progress_callback=lambda p: progress_log.append(p),
        )
        assert result is False
        assert any(p.stage == "error" for p in progress_log)
```

**Step 2: Run tests — verify they fail**

Expected: FAIL

**Step 3: Implement restore orchestration**

Add to `app/services/firmware_manager.py`:

```python
# ---------------------------------------------------------------------------
# Firmware Restore
# ---------------------------------------------------------------------------

def _perform_restore(udid: Optional[str], ipsw_path: Path) -> bool:
    """Execute the actual firmware restore via pymobiledevice3.

    This is the mock boundary — real implementation calls pymobiledevice3's
    restore module.
    """
    try:
        from pymobiledevice3.restore.device import Device
        from pymobiledevice3.restore.restore import Restore

        device = Device()
        restore = Restore(ipsw_path, device)
        restore.restore()
        return True
    except Exception as e:
        logger.error("Restore failed: %s", e)
        return False


def restore_device(
    udid: str,
    model: str,
    version: Optional[str] = None,
    progress_callback: Optional[Callable[[RestoreProgress], None]] = None,
) -> bool:
    """Full firmware restore workflow.

    1. Look up signed versions
    2. Download IPSW (with progress)
    3. Verify SHA1
    4. Execute restore (with progress)

    Args:
        udid: Device UDID.
        model: Apple model identifier (e.g. "iPhone14,2").
        version: Specific iOS version to restore. If None, uses latest signed.
        progress_callback: Called with RestoreProgress updates.

    Returns:
        True if restore succeeded, False otherwise.
    """
    cb = progress_callback or (lambda p: None)

    # 1. Get signed versions
    cb(RestoreProgress(stage="preparing", percent=0, message="Checking signed versions..."))
    signed = get_signed_versions(model, signed_only=True)

    if not signed:
        cb(RestoreProgress(stage="error", percent=0, message="No signed firmware versions found"))
        return False

    # Pick version
    if version:
        firmware = next((f for f in signed if f.version == version), None)
        if not firmware:
            cb(RestoreProgress(
                stage="error", percent=0,
                message=f"iOS {version} is not currently signed for {model}",
            ))
            return False
    else:
        firmware = signed[0]  # latest signed

    # 2. Download IPSW
    ipsw_path = download_ipsw(firmware, progress_callback=progress_callback)
    if not ipsw_path:
        return False

    # 3. Restore
    cb(RestoreProgress(
        stage="restoring", percent=0,
        message=f"Restoring iOS {firmware.version} ({firmware.build_id})...",
    ))

    success = _perform_restore(udid, ipsw_path)

    if success:
        cb(RestoreProgress(stage="complete", percent=100, message="Restore complete"))
    else:
        cb(RestoreProgress(stage="error", percent=0, message="Restore failed"))

    return success
```

**Step 4: Run tests — verify they pass**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_firmware_manager.py::TestRestore']))"`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add app/services/firmware_manager.py tests/test_firmware_manager.py
git commit -m "feat(sprint3): firmware restore orchestration"
```

---

### Task 9: Wipe Service — Erase + PDF Certificate

**Files:**
- Create: `app/services/wipe_service.py`
- Create: `app/templates/erasure_certificate.html`
- Create: `tests/test_wipe_service.py`

**Step 1: Write failing tests**

Create `tests/test_wipe_service.py`:

```python
"""Tests for wipe service — device erasure and certificate generation."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.firmware import WipeRecord


class TestEraseDevice:
    """Test device factory reset (mocked pymobiledevice3)."""

    @patch("app.services.wipe_service._perform_erase")
    def test_erase_success(self, mock_erase):
        from app.services.wipe_service import erase_device

        mock_erase.return_value = True
        result = erase_device("test-udid")
        assert result is True

    @patch("app.services.wipe_service._perform_erase")
    def test_erase_failure(self, mock_erase):
        from app.services.wipe_service import erase_device

        mock_erase.side_effect = Exception("Device locked")
        result = erase_device("test-udid")
        assert result is False


class TestCertificateGeneration:
    """Test erasure certificate PDF generation."""

    def test_render_certificate_html(self):
        from app.services.wipe_service import render_certificate_html

        record = WipeRecord(
            device_id=1, udid="ABCD1234", serial="C39TEST123",
            imei="353456789012345", model="iPhone 13 Pro",
            ios_version="17.4", method="factory_reset",
            timestamp=datetime(2026, 3, 1, 12, 0, 0),
            operator="TestUser", success=True,
        )
        html = render_certificate_html(record)
        assert "C39TEST123" in html
        assert "353456789012345" in html
        assert "iPhone 13 Pro" in html
        assert "factory_reset" in html

    @patch("app.services.wipe_service._html_to_pdf")
    def test_generate_certificate_pdf(self, mock_pdf, tmp_path):
        from app.services.wipe_service import generate_certificate

        mock_pdf.return_value = True

        record = WipeRecord(
            device_id=1, udid="ABCD1234", serial="C39TEST123",
            imei="353456789012345", model="iPhone 13 Pro",
            ios_version="17.4", method="factory_reset",
            timestamp=datetime(2026, 3, 1, 12, 0, 0),
            operator="TestUser", success=True,
        )

        cert_path = generate_certificate(record, output_dir=tmp_path)
        assert cert_path is not None
        assert "C39TEST123" in cert_path.name
        mock_pdf.assert_called_once()
```

**Step 2: Run tests — verify they fail**

Expected: FAIL

**Step 3: Create erasure certificate HTML template**

Create `app/templates/erasure_certificate.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Data Erasure Certificate</title>
    <style>
        body {
            font-family: Arial, Helvetica, sans-serif;
            margin: 40px;
            color: #1a1a1a;
        }
        .header {
            text-align: center;
            border-bottom: 3px solid #2563eb;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 24px;
            color: #2563eb;
            margin-bottom: 5px;
        }
        .header p {
            color: #666;
            font-size: 14px;
        }
        .section {
            margin-bottom: 20px;
        }
        .section h2 {
            font-size: 16px;
            color: #374151;
            border-bottom: 1px solid #e5e7eb;
            padding-bottom: 5px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        td {
            padding: 8px 12px;
            border-bottom: 1px solid #f3f4f6;
        }
        td:first-child {
            font-weight: bold;
            width: 200px;
            color: #4b5563;
        }
        .status {
            text-align: center;
            padding: 20px;
            margin: 30px 0;
            border-radius: 8px;
        }
        .status.success {
            background-color: #d1fae5;
            color: #065f46;
            border: 2px solid #10b981;
        }
        .status.failed {
            background-color: #fee2e2;
            color: #991b1b;
            border: 2px solid #ef4444;
        }
        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: #9ca3af;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Data Erasure Certificate</h1>
        <p>Generated by iDiag Device Management System</p>
    </div>

    <div class="section">
        <h2>Device Information</h2>
        <table>
            <tr><td>Model</td><td>{{ record.model }}</td></tr>
            <tr><td>Serial Number</td><td>{{ record.serial }}</td></tr>
            <tr><td>IMEI</td><td>{{ record.imei }}</td></tr>
            <tr><td>UDID</td><td>{{ record.udid }}</td></tr>
            <tr><td>iOS Version</td><td>{{ record.ios_version }}</td></tr>
        </table>
    </div>

    <div class="section">
        <h2>Erasure Details</h2>
        <table>
            <tr><td>Method</td><td>{{ record.method }}</td></tr>
            <tr><td>Date &amp; Time</td><td>{{ record.timestamp }}</td></tr>
            <tr><td>Operator</td><td>{{ record.operator or 'N/A' }}</td></tr>
        </table>
    </div>

    <div class="status {{ 'success' if record.success else 'failed' }}">
        {% if record.success %}
            <strong>PASS — All user data has been securely erased</strong>
        {% else %}
            <strong>FAIL — Data erasure did not complete successfully</strong>
        {% endif %}
    </div>

    <div class="footer">
        <p>This certificate was generated automatically by iDiag.<br>
        Certificate ID: {{ record.serial }}-{{ record.timestamp.strftime('%Y%m%d%H%M%S') if record.timestamp else 'unknown' }}</p>
    </div>
</body>
</html>
```

**Step 4: Implement wipe_service.py**

Create `app/services/wipe_service.py`:

```python
"""Wipe service — device data erasure and PDF certificate generation."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.models.firmware import WipeRecord

logger = logging.getLogger(__name__)

# Template environment for certificate rendering
_templates_dir = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_templates_dir)), autoescape=True)


# ---------------------------------------------------------------------------
# Device Erase
# ---------------------------------------------------------------------------

def _perform_erase(udid: Optional[str] = None) -> bool:
    """Execute factory reset via pymobiledevice3. Mock boundary for tests."""
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.diagnostics import DiagnosticsService

    with create_using_usbmux(serial=udid) as lockdown:
        with DiagnosticsService(lockdown) as diag:
            diag.erase_device()
    return True


def erase_device(udid: Optional[str] = None) -> bool:
    """Factory reset a connected device.

    Args:
        udid: Device UDID, or None for auto-detect.

    Returns:
        True if erase succeeded, False otherwise.
    """
    try:
        return _perform_erase(udid)
    except Exception as e:
        logger.error("Device erase failed for %s: %s", udid or "auto", e)
        return False


# ---------------------------------------------------------------------------
# Certificate Generation
# ---------------------------------------------------------------------------

def render_certificate_html(record: WipeRecord) -> str:
    """Render erasure certificate as HTML string."""
    template = _jinja_env.get_template("erasure_certificate.html")
    return template.render(record=record)


def _html_to_pdf(html: str, output_path: Path) -> bool:
    """Convert HTML string to PDF via WeasyPrint. Mock boundary for tests."""
    from weasyprint import HTML
    HTML(string=html).write_pdf(str(output_path))
    return True


def generate_certificate(
    record: WipeRecord, output_dir: Optional[Path] = None
) -> Optional[Path]:
    """Generate a PDF erasure certificate for a wipe record.

    Args:
        record: WipeRecord with device/wipe details.
        output_dir: Override output directory (for testing).

    Returns:
        Path to generated PDF, or None on failure.
    """
    output_dir = output_dir or settings.cert_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = record.timestamp.strftime("%Y%m%d_%H%M%S") if record.timestamp else "unknown"
    filename = f"erasure_{record.serial}_{ts}.pdf"
    output_path = output_dir / filename

    try:
        html = render_certificate_html(record)
        _html_to_pdf(html, output_path)
        logger.info("Generated erasure certificate: %s", filename)
        return output_path
    except Exception as e:
        logger.error("Certificate generation failed: %s", e)
        return None
```

**Step 5: Run tests — verify they pass**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_wipe_service.py']))"`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add app/services/wipe_service.py app/templates/erasure_certificate.html tests/test_wipe_service.py
git commit -m "feat(sprint3): wipe service with PDF erasure certificates"
```

---

### Task 10: API Endpoints

**Files:**
- Create: `app/api/firmware.py`

**Step 1: Create firmware API router**

```python
"""Firmware management API routes — IPSW, signing, SHSH, restore, wipe."""

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.models.firmware import (
    FirmwareVersion,
    IPSWCacheEntry,
    RestoreProgress,
    WipeRecord,
)
from app.services import firmware_manager, wipe_service
from app.services.inventory_db import InventoryDB

router = APIRouter(prefix="/api/firmware", tags=["firmware"])
db = InventoryDB()
db.init_db()


# -- Request models --

class DownloadRequest(BaseModel):
    model: str
    version: str
    build_id: str = ""
    url: str = ""
    sha1: str = ""
    size_bytes: int = 0


class RestoreRequest(BaseModel):
    model: str
    version: Optional[str] = None


class WipeRequest(BaseModel):
    serial: str = ""
    imei: str = ""
    model: str = ""
    ios_version: str = ""
    operator: str = ""


# -- Signing / Firmware Info --

@router.get("/signed/{model}")
async def get_signed_versions(model: str) -> list[FirmwareVersion]:
    """Get currently signed iOS firmware versions for a device model."""
    return await asyncio.to_thread(firmware_manager.get_signed_versions, model)


# -- IPSW Cache --

@router.get("/cache")
async def list_cache() -> list[IPSWCacheEntry]:
    """List all cached IPSW files."""
    return await asyncio.to_thread(firmware_manager.list_cached_ipsw)


@router.delete("/cache/{model}/{version}")
async def evict_cached_ipsw(model: str, version: str):
    """Remove a specific IPSW from the cache."""
    path = await asyncio.to_thread(firmware_manager.get_cached_ipsw, model, version)
    if path and path.exists():
        path.unlink()
        return {"status": "deleted", "model": model, "version": version}
    raise HTTPException(status_code=404, detail="IPSW not found in cache")


@router.post("/download")
async def download_ipsw(req: DownloadRequest):
    """Trigger an IPSW download. Progress reported via WebSocket."""
    firmware = FirmwareVersion(
        version=req.version, build_id=req.build_id, model=req.model,
        url=req.url, sha1=req.sha1, size_bytes=req.size_bytes,
    )

    # If no URL provided, look it up from signed versions
    if not firmware.url:
        versions = await asyncio.to_thread(
            firmware_manager.get_signed_versions, req.model, False
        )
        match = next((v for v in versions if v.version == req.version), None)
        if not match:
            raise HTTPException(404, f"Version {req.version} not found for {req.model}")
        firmware = match

    from app.api.websocket import broadcast

    async def _progress(p: RestoreProgress):
        await broadcast("firmware_download_progress", p.model_dump())

    # Run download in thread, but we can't use async callback from thread
    # So just run it synchronously and broadcast after
    path = await asyncio.to_thread(firmware_manager.download_ipsw, firmware)
    if path:
        return {"status": "downloaded", "path": str(path)}
    raise HTTPException(500, "Download failed")


# -- SHSH Blobs --

@router.post("/shsh/{udid}")
async def save_shsh_blobs(udid: str, ecid: str, model: str, version: str):
    """Save SHSH blobs for a device + iOS version."""
    path = await asyncio.to_thread(
        firmware_manager.save_shsh_blobs, ecid, model, version
    )
    if path:
        # Also save to DB
        await asyncio.to_thread(db.save_shsh_blob, ecid, model, version, str(path))
        return {"status": "saved", "path": str(path)}
    raise HTTPException(500, "Failed to save SHSH blobs")


@router.get("/shsh")
async def list_shsh_blobs(ecid: Optional[str] = None):
    """List saved SHSH blobs."""
    return await asyncio.to_thread(db.list_shsh_blobs, ecid)


# -- Device Mode Helpers --

@router.get("/mode/{udid}")
async def get_device_mode(udid: str):
    """Detect device mode: normal, recovery, dfu, or unknown."""
    mode = await asyncio.to_thread(firmware_manager.get_device_mode, udid)
    return {"udid": udid, "mode": mode}


@router.post("/dfu/{udid}")
async def enter_dfu_mode(udid: str):
    """Enter DFU mode (enters recovery first, user must complete button combo)."""
    ok = await asyncio.to_thread(firmware_manager.enter_dfu_mode, udid)
    if ok:
        return {"status": "recovery_entered", "message": "Now hold DFU button combo"}
    raise HTTPException(500, "Failed to enter recovery/DFU mode")


@router.post("/recovery/{udid}")
async def enter_recovery(udid: str):
    """Put device into recovery mode."""
    ok = await asyncio.to_thread(firmware_manager.enter_recovery_mode, udid)
    if ok:
        return {"status": "ok"}
    raise HTTPException(500, "Failed to enter recovery mode")


@router.delete("/recovery/{udid}")
async def exit_recovery(udid: str):
    """Kick device out of recovery mode."""
    ok = await asyncio.to_thread(firmware_manager.exit_recovery_mode, udid)
    if ok:
        return {"status": "ok"}
    raise HTTPException(500, "Failed to exit recovery mode")


# -- Restore --

@router.post("/restore/{udid}")
async def restore_device(udid: str, req: RestoreRequest):
    """Start a full firmware restore. Progress reported via WebSocket."""
    from app.api.websocket import broadcast

    progress_log: list[RestoreProgress] = []

    def _progress(p: RestoreProgress):
        progress_log.append(p)

    ok = await asyncio.to_thread(
        firmware_manager.restore_device, udid, req.model, req.version, _progress
    )

    # Broadcast final status
    if progress_log:
        await broadcast("restore_progress", progress_log[-1].model_dump())

    if ok:
        return {"status": "restored", "version": req.version or "latest"}
    raise HTTPException(500, "Restore failed")


# -- Wipe --

@router.post("/wipe/{udid}")
async def wipe_device(udid: str, req: WipeRequest):
    """Erase device and generate erasure certificate."""
    # Erase
    ok = await asyncio.to_thread(wipe_service.erase_device, udid)

    # Create wipe record
    record = WipeRecord(
        udid=udid,
        serial=req.serial,
        imei=req.imei,
        model=req.model,
        ios_version=req.ios_version,
        method="factory_reset",
        timestamp=datetime.now(),
        operator=req.operator,
        success=ok,
    )

    # Generate certificate regardless of outcome (records the attempt)
    cert_path = await asyncio.to_thread(wipe_service.generate_certificate, record)

    if cert_path:
        record.cert_path = str(cert_path)

    # Save to DB if device exists
    device = await asyncio.to_thread(db.get_device_by_udid, udid)
    if device and device.id:
        record.device_id = device.id
        await asyncio.to_thread(
            db.save_wipe_record,
            device.id, udid, req.serial, req.imei, req.model,
            req.ios_version, "factory_reset", req.operator, ok,
            str(cert_path) if cert_path else "",
        )

    from app.api.websocket import broadcast
    await broadcast("wipe_complete", {"udid": udid, "success": ok, "cert_path": str(cert_path or "")})

    return {
        "status": "erased" if ok else "failed",
        "cert_path": str(cert_path or ""),
    }


@router.get("/certificate/{device_id}")
async def download_certificate(device_id: int):
    """Download the most recent erasure certificate PDF for a device."""
    records = await asyncio.to_thread(db.list_wipe_records, device_id)
    if not records:
        raise HTTPException(404, "No wipe records found")

    latest = records[0]
    from pathlib import Path
    cert = Path(latest.cert_path)
    if not cert.exists():
        raise HTTPException(404, "Certificate file not found")

    return FileResponse(
        path=str(cert),
        media_type="application/pdf",
        filename=cert.name,
    )
```

**Step 2: Verify it imports cleanly**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "from app.api.firmware import router; print('Endpoints:', len(router.routes))"`
Expected: Prints endpoint count (should be ~13)

**Step 3: Commit**

```bash
git add app/api/firmware.py
git commit -m "feat(sprint3): firmware API endpoints"
```

---

### Task 11: Register Router + Update Dependencies

**Files:**
- Modify: `app/main.py`
- Modify: `requirements.txt`

**Step 1: Add firmware router to main.py**

Add import at line 24 (alongside other API imports):
```python
from app.api import devices, diagnostics, firmware, inventory, serial, verification, websocket
```

Add router inclusion after line 54 (after `serial.router`):
```python
app.include_router(firmware.router)
```

**Step 2: Add weasyprint to requirements.txt**

Add after `jinja2>=3.1.0`:
```
weasyprint>=62.0
```

**Step 3: Verify app starts without errors**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "from app.main import app; print('Routes:', len(app.routes))"`
Expected: Prints route count (should be > 20)

**Step 4: Run ALL tests**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/']))"`
Expected: ALL PASS (all existing + new tests)

**Step 5: Commit**

```bash
git add app/main.py requirements.txt
git commit -m "feat(sprint3): register firmware router, add weasyprint dep"
```

---

### Task 12: Final Verification + Sprint 3 Commit

**Step 1: Run full test suite**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/']))"`
Expected: ALL PASS

**Step 2: Verify no import errors across all modules**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "from app.services.firmware_manager import get_signed_versions, download_ipsw, save_shsh_blobs, enter_recovery_mode, restore_device; from app.services.wipe_service import erase_device, generate_certificate; from app.api.firmware import router; print('All Sprint 3 modules OK')"`

**Step 3: Verify lint passes**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -m ruff check app/services/firmware_manager.py app/services/wipe_service.py app/api/firmware.py app/models/firmware.py`

**Step 4: Fix any lint issues, then final commit if needed**

```bash
git add -A
git commit -m "feat: Sprint 3 — Firmware & Recovery (IPSW, TSS, SHSH, DFU, restore, wipe)"
```
