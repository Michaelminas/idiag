# Sprint 3: Firmware & Recovery — Design Document

**Date:** 2026-03-01
**Status:** Approved

## Scope

All 6 planned features:
1. IPSW auto-download, cache (LRU), SHA1 verify
2. Apple TSS signing status checker
3. SHSH blob saver (via pymobiledevice3 TSS client)
4. DFU/Recovery mode helpers
5. Firmware restore (pymobiledevice3, WebSocket progress)
6. Data wipe + PDF erasure certificates (WeasyPrint)

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Restore tool | pymobiledevice3 | Already a dep, pure Python, no C compilation on USB |
| SHSH blob tool | pymobiledevice3 TSS client | Same rationale, keeps stack homogeneous |
| IPSW caching | Download on demand + LRU eviction | 3-7GB per file, USB space is limited |
| Erasure certificate | PDF via WeasyPrint | Professional output for buyer handoff |
| Testing | Mock device layer + unit tests | Develop on Windows, deploy on Linux USB |

## New Files

### Services
- `app/services/firmware_manager.py` — IPSW download/cache, TSS queries, SHSH blobs, DFU/recovery helpers, restore
- `app/services/wipe_service.py` — Factory reset, erasure certificate PDF generation

### Models
- `app/models/firmware.py` — FirmwareVersion, IPSWCache, SHSHBlob, RestoreProgress, WipeRecord, ErasureCertificate

### API
- `app/api/firmware.py` — All firmware & wipe endpoints

### Templates
- `app/templates/erasure_certificate.html` — WeasyPrint HTML template for PDF

### Tests
- `tests/test_firmware_manager.py` — Cache LRU, TSS parsing, SHA1 verification
- `tests/test_wipe_service.py` — Certificate generation, wipe record creation

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/firmware/signed/{model}` | Currently signed iOS versions |
| POST | `/api/firmware/download` | Trigger IPSW download (progress via WS) |
| GET | `/api/firmware/cache` | List cached IPSWs |
| DELETE | `/api/firmware/cache/{version}` | Evict specific cached IPSW |
| POST | `/api/firmware/shsh/{udid}` | Save SHSH blobs for device |
| POST | `/api/firmware/dfu/{udid}` | Enter DFU mode |
| POST | `/api/firmware/recovery/{udid}` | Enter/exit recovery mode |
| POST | `/api/firmware/restore/{udid}` | Start firmware restore (progress via WS) |
| POST | `/api/firmware/wipe/{udid}` | Erase device + generate certificate |
| GET | `/api/firmware/certificate/{device_id}` | Download erasure certificate PDF |

## Pydantic Models

```python
class FirmwareVersion(BaseModel):
    version: str
    build_id: str
    model: str
    url: str
    sha1: str
    size_bytes: int
    signed: bool

class IPSWCache(BaseModel):
    path: str
    model: str
    version: str
    downloaded_at: datetime
    size_bytes: int

class SHSHBlob(BaseModel):
    ecid: str
    device_model: str
    version: str
    blob_path: str
    saved_at: datetime

class RestoreProgress(BaseModel):
    stage: Literal["downloading", "verifying", "preparing", "restoring", "complete", "error"]
    percent: int
    message: str

class WipeRecord(BaseModel):
    device_id: int
    udid: str
    serial: str
    imei: str
    method: Literal["factory_reset", "dfu_restore"]
    timestamp: datetime
    operator: str
    success: bool

class ErasureCertificate(WipeRecord):
    cert_path: str
    model: str
    ios_version: str
```

## Database Schema (new tables)

```sql
CREATE TABLE IF NOT EXISTS shsh_blobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ecid TEXT NOT NULL,
    device_model TEXT NOT NULL,
    ios_version TEXT NOT NULL,
    blob_path TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    UNIQUE(ecid, ios_version)
);

CREATE TABLE IF NOT EXISTS wipe_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    udid TEXT NOT NULL,
    serial TEXT NOT NULL,
    imei TEXT NOT NULL,
    method TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    operator TEXT NOT NULL DEFAULT '',
    success INTEGER NOT NULL DEFAULT 0,
    cert_path TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(id)
);
```

## Data Flow

```
User clicks "Restore" on dashboard
  -> POST /api/firmware/restore/{udid}
  -> firmware_manager checks signed versions (Apple TSS)
  -> downloads IPSW if not cached (progress via WebSocket)
  -> verifies SHA1 checksum
  -> pymobiledevice3 restore (progress via WebSocket)
  -> on success: wipe_record created + erasure certificate PDF
  -> WebSocket: "restore_complete" event -> dashboard updates
```

## Configuration (app/config.py additions)

```python
ipsw_cache_dir: str = "data/ipsw_cache"
ipsw_cache_max_gb: float = 20.0
shsh_blob_dir: str = "data/shsh_blobs"
cert_output_dir: str = "data/certificates"
```

## Dependencies

- `weasyprint` — new dependency for PDF certificate generation
- `pymobiledevice3` — existing, use `restore` and `tss` modules

## WebSocket Events (extend existing)

- `firmware_download_progress` — {model, version, percent, speed_mbps}
- `restore_progress` — {udid, stage, percent, message}
- `wipe_complete` — {udid, success, cert_path}

## Testing Strategy

Mock pymobiledevice3 at the service boundary:
- `test_firmware_manager.py`: LRU cache eviction, TSS response parsing, SHA1 verification, IPSW URL construction
- `test_wipe_service.py`: Certificate PDF generation (mock WeasyPrint), wipe record DB operations
- All device interactions behind abstract methods that tests can mock
