# Sprint 4: Business Operations & Reports — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add photo management, PDF reports, sales tracking, QR labels, listing templates, and bulk export to iDiag.

**Architecture:** New models in `app/models/sales.py`, 2 new DB tables in existing `inventory_db.py`, 5 new services, 3 new API routers. All follow existing patterns (thread-locked DB, Pydantic models, APIRouter with prefix).

**Tech Stack:** WeasyPrint (PDF), qrcode[pil] (QR), Jinja2 (listing templates), stdlib csv/json (export)

---

## Task 1: Foundation — Models, DB Schema, Config

**Files:**
- Create: `app/models/sales.py`
- Modify: `app/services/inventory_db.py` (add 2 tables + CRUD methods)
- Modify: `app/config.py` (add `photos_dir`)
- Test: `tests/test_sales_db.py`

**Step 1: Create models**

Create `app/models/sales.py`:

```python
"""Sales, photo, and listing models."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

Platform = Literal["ebay", "marketplace", "local", "other"]
PhotoLabel = Literal["front", "back", "screen", "side", "other"]


class PhotoRecord(BaseModel):
    id: Optional[int] = None
    device_id: int
    filename: str = ""
    filepath: str = ""
    label: PhotoLabel = "other"
    created_at: Optional[datetime] = None


class SalesRecord(BaseModel):
    id: Optional[int] = None
    device_id: int
    sell_price: Optional[float] = None
    platform: Platform = "local"
    fees: float = 0.0
    sold_at: Optional[datetime] = None
    days_in_inventory: Optional[int] = None
    profit: Optional[float] = None
    notes: str = ""
    created_at: Optional[datetime] = None


class ListingTemplate(BaseModel):
    platform: Platform
    title: str = ""
    description: str = ""
    price: Optional[float] = None
    condition: str = ""
```

**Step 2: Add DB tables to `inventory_db.py` SCHEMA string**

Append to the existing `SCHEMA` string (after verifications table):

```sql
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    label TEXT DEFAULT 'other',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    sell_price REAL,
    platform TEXT DEFAULT 'local',
    fees REAL DEFAULT 0,
    sold_at TIMESTAMP,
    days_in_inventory INTEGER,
    profit REAL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Step 3: Add import + CRUD methods to `InventoryDB`**

Add to top of `inventory_db.py`:
```python
from app.models.sales import PhotoRecord, SalesRecord
```

Add methods to `InventoryDB` class:

```python
# -- Photos --

def save_photo(self, record: PhotoRecord) -> int:
    with self._lock:
        cur = self.conn.execute(
            """INSERT INTO photos (device_id, filename, filepath, label)
               VALUES (?, ?, ?, ?)""",
            (record.device_id, record.filename, record.filepath, record.label),
        )
        self.conn.commit()
        return cur.lastrowid

def list_photos(self, device_id: int) -> list[PhotoRecord]:
    with self._lock:
        rows = self.conn.execute(
            "SELECT * FROM photos WHERE device_id=? ORDER BY created_at", (device_id,)
        ).fetchall()
        return [PhotoRecord(
            id=r["id"], device_id=r["device_id"], filename=r["filename"],
            filepath=r["filepath"], label=r["label"], created_at=r["created_at"],
        ) for r in rows]

def delete_photo(self, photo_id: int) -> bool:
    with self._lock:
        cur = self.conn.execute("DELETE FROM photos WHERE id=?", (photo_id,))
        self.conn.commit()
        return cur.rowcount > 0

# -- Sales --

def save_sale(self, record: SalesRecord) -> int:
    with self._lock:
        # Auto-compute profit if sell_price is set
        profit = None
        if record.sell_price is not None:
            device = self._get_device_by_id_unlocked(record.device_id)
            buy_price = device.buy_price if device and device.buy_price else 0.0
            profit = record.sell_price - buy_price - record.fees

        # Auto-compute days_in_inventory
        days = record.days_in_inventory
        if days is None:
            device = self._get_device_by_id_unlocked(record.device_id)
            if device and device.created_at:
                from datetime import datetime as dt
                created = device.created_at if isinstance(device.created_at, datetime) else datetime.fromisoformat(str(device.created_at))
                days = (datetime.now() - created).days

        now = datetime.now().isoformat()
        cur = self.conn.execute(
            """INSERT INTO sales (device_id, sell_price, platform, fees,
               sold_at, days_in_inventory, profit, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (record.device_id, record.sell_price, record.platform,
             record.fees, record.sold_at or now, days, profit, record.notes),
        )
        self.conn.commit()
        return cur.lastrowid

def get_sale(self, sale_id: int) -> Optional[SalesRecord]:
    with self._lock:
        row = self.conn.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
        return self._row_to_sale(row) if row else None

def list_sales(self, device_id: Optional[int] = None) -> list[SalesRecord]:
    with self._lock:
        if device_id is not None:
            rows = self.conn.execute(
                "SELECT * FROM sales WHERE device_id=? ORDER BY created_at DESC", (device_id,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM sales ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_sale(r) for r in rows]

def _get_device_by_id_unlocked(self, device_id: int) -> Optional[DeviceRecord]:
    row = self.conn.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
    return self._row_to_device(row) if row else None

@staticmethod
def _row_to_sale(row: sqlite3.Row) -> SalesRecord:
    return SalesRecord(
        id=row["id"], device_id=row["device_id"],
        sell_price=row["sell_price"], platform=row["platform"] or "local",
        fees=row["fees"] or 0.0, sold_at=row["sold_at"],
        days_in_inventory=row["days_in_inventory"],
        profit=row["profit"], notes=row["notes"] or "",
        created_at=row["created_at"],
    )
```

Also update `delete_device()` to cascade delete photos and sales:

```python
def delete_device(self, device_id: int) -> bool:
    with self._lock:
        self.conn.execute("DELETE FROM photos WHERE device_id=?", (device_id,))
        self.conn.execute("DELETE FROM sales WHERE device_id=?", (device_id,))
        self.conn.execute("DELETE FROM crash_reports WHERE device_id=?", (device_id,))
        self.conn.execute("DELETE FROM diagnostics WHERE device_id=?", (device_id,))
        self.conn.execute("DELETE FROM verifications WHERE device_id=?", (device_id,))
        cur = self.conn.execute("DELETE FROM devices WHERE id=?", (device_id,))
        self.conn.commit()
        return cur.rowcount > 0
```

**Step 4: Add `photos_dir` to config**

In `app/config.py`, add field and init:

```python
photos_dir: Path = Path("")

# In model_post_init:
self.photos_dir = self.data_dir / "photos"
```

**Step 5: Write tests**

Create `tests/test_sales_db.py`:

```python
"""Tests for sales + photos database operations."""

import tempfile
from pathlib import Path

import pytest

from app.models.device import DeviceRecord
from app.models.sales import PhotoRecord, SalesRecord
from app.services.inventory_db import InventoryDB


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = InventoryDB(db_path=Path(tmpdir) / "test.db")
        db.init_db()
        yield db
        db.close()


@pytest.fixture
def device_id(db):
    return db.upsert_device(DeviceRecord(udid="test-001", buy_price=200.0))


class TestPhotoCRUD:
    def test_save_and_list(self, db, device_id):
        record = PhotoRecord(device_id=device_id, filename="front.jpg",
                             filepath="test-001/front.jpg", label="front")
        photo_id = db.save_photo(record)
        assert photo_id is not None

        photos = db.list_photos(device_id)
        assert len(photos) == 1
        assert photos[0].filename == "front.jpg"

    def test_delete_photo(self, db, device_id):
        photo_id = db.save_photo(PhotoRecord(
            device_id=device_id, filename="back.jpg",
            filepath="test-001/back.jpg", label="back"))
        assert db.delete_photo(photo_id)
        assert len(db.list_photos(device_id)) == 0

    def test_cascade_delete(self, db, device_id):
        db.save_photo(PhotoRecord(device_id=device_id, filename="x.jpg",
                                  filepath="test-001/x.jpg"))
        db.delete_device(device_id)
        assert len(db.list_photos(device_id)) == 0


class TestSalesCRUD:
    def test_save_and_get(self, db, device_id):
        record = SalesRecord(device_id=device_id, sell_price=350.0,
                             platform="ebay", fees=35.0)
        sale_id = db.save_sale(record)
        assert sale_id is not None

        sale = db.get_sale(sale_id)
        assert sale is not None
        assert sale.sell_price == 350.0
        assert sale.profit == 115.0  # 350 - 200 - 35

    def test_list_sales(self, db, device_id):
        db.save_sale(SalesRecord(device_id=device_id, sell_price=300.0))
        db.save_sale(SalesRecord(device_id=device_id, sell_price=350.0))
        assert len(db.list_sales(device_id)) == 2
        assert len(db.list_sales()) == 2

    def test_auto_days_in_inventory(self, db, device_id):
        sale_id = db.save_sale(SalesRecord(device_id=device_id, sell_price=300.0))
        sale = db.get_sale(sale_id)
        assert sale.days_in_inventory is not None
        assert sale.days_in_inventory >= 0
```

**Step 6: Run tests**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_sales_db.py']))"`

Expected: All pass

**Step 7: Commit**

```bash
git add app/models/sales.py app/services/inventory_db.py app/config.py tests/test_sales_db.py
git commit -m "feat(sprint4): add sales/photo models, DB schema, and CRUD"
```

---

## Task 2: Photo Manager + Photo API

**Files:**
- Create: `app/services/photo_manager.py`
- Create: `app/api/photos.py`
- Test: `tests/test_photo_manager.py`

**Step 1: Create photo manager service**

Create `app/services/photo_manager.py`:

```python
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
```

**Step 2: Write tests**

Create `tests/test_photo_manager.py`:

```python
"""Tests for photo file management."""

import tempfile
from pathlib import Path

import pytest

from app.services.photo_manager import PhotoManager


@pytest.fixture
def pm():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield PhotoManager(base_dir=Path(tmpdir))


class TestPhotoManager:
    def test_save_and_get(self, pm):
        filename, relpath = pm.save("udid-001", b"\xff\xd8\xff", label="front")
        assert "front" in filename
        assert pm.get_path(relpath) is not None
        assert pm.get_path(relpath).read_bytes() == b"\xff\xd8\xff"

    def test_list_files(self, pm):
        pm.save("udid-001", b"a", label="front")
        pm.save("udid-001", b"b", label="back")
        files = pm.list_files("udid-001")
        assert len(files) == 2

    def test_delete(self, pm):
        _, relpath = pm.save("udid-001", b"x", label="screen")
        assert pm.delete(relpath)
        assert pm.get_path(relpath) is None

    def test_delete_all(self, pm):
        pm.save("udid-001", b"a")
        pm.save("udid-001", b"b")
        count = pm.delete_all("udid-001")
        assert count == 2
        assert pm.list_files("udid-001") == []

    def test_list_empty(self, pm):
        assert pm.list_files("nonexistent") == []
```

**Step 3: Run tests**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_photo_manager.py']))"`

Expected: All pass

**Step 4: Create photo API**

Create `app/api/photos.py`:

```python
"""Photo upload/list/delete API routes."""

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.inventory import get_db
from app.models.sales import PhotoLabel, PhotoRecord
from app.services.photo_manager import PhotoManager

router = APIRouter(prefix="/api/photos", tags=["photos"])
_pm = PhotoManager()


@router.post("/upload/{device_id}")
async def upload_photo(device_id: int, file: UploadFile, label: PhotoLabel = "other") -> dict:
    device = get_db().get_device_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    data = await file.read()
    ext = "." + (file.filename or "photo.jpg").rsplit(".", 1)[-1]
    filename, relpath = _pm.save(device.udid, data, label=label, extension=ext)

    photo_id = get_db().save_photo(PhotoRecord(
        device_id=device_id, filename=filename, filepath=relpath, label=label,
    ))
    return {"id": photo_id, "filename": filename, "filepath": relpath}


@router.get("/device/{device_id}")
def list_photos(device_id: int) -> list[PhotoRecord]:
    return get_db().list_photos(device_id)


@router.get("/file/{photo_id}")
def get_photo_file(photo_id: int):
    photos = get_db().list_photos(0)  # We need to find by photo_id
    # Query directly since we need photo by ID
    db = get_db()
    with db._lock:
        row = db.conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    path = _pm.get_path(row["filepath"])
    if not path:
        raise HTTPException(status_code=404, detail="Photo file missing")
    return FileResponse(path)


@router.delete("/{photo_id}")
def delete_photo(photo_id: int) -> dict:
    db = get_db()
    with db._lock:
        row = db.conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    _pm.delete(row["filepath"])
    db.delete_photo(photo_id)
    return {"deleted": True}
```

**Step 5: Commit**

```bash
git add app/services/photo_manager.py app/api/photos.py tests/test_photo_manager.py
git commit -m "feat(sprint4): add photo manager service and API"
```

---

## Task 3: Sales API

**Files:**
- Create: `app/api/sales.py`

**Step 1: Create sales routes**

Create `app/api/sales.py`:

```python
"""Sales tracking API routes."""

from fastapi import APIRouter, HTTPException

from app.api.inventory import get_db
from app.models.sales import SalesRecord

router = APIRouter(prefix="/api/sales", tags=["sales"])


@router.post("/")
def record_sale(record: SalesRecord) -> dict:
    device = get_db().get_device_by_id(record.device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    sale_id = get_db().save_sale(record)

    # Update device status to sold
    device.status = "sold"
    get_db().upsert_device(device)

    return {"id": sale_id}


@router.get("/{sale_id}")
def get_sale(sale_id: int) -> SalesRecord:
    sale = get_db().get_sale(sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale


@router.get("/device/{device_id}")
def list_device_sales(device_id: int) -> list[SalesRecord]:
    return get_db().list_sales(device_id)


@router.get("/")
def list_all_sales() -> list[SalesRecord]:
    return get_db().list_sales()
```

**Step 2: Commit**

```bash
git add app/api/sales.py
git commit -m "feat(sprint4): add sales tracking API"
```

---

## Task 4: PDF Report Generator

**Files:**
- Create: `app/services/report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Create report generator service**

Create `app/services/report_generator.py`:

```python
"""PDF health report generator using WeasyPrint."""

import logging
from datetime import datetime
from io import BytesIO
from typing import Any, Optional

logger = logging.getLogger(__name__)

REPORT_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<style>
    body { font-family: Arial, sans-serif; margin: 40px; color: #333; }
    h1 { color: #1a1a2e; border-bottom: 2px solid #16213e; padding-bottom: 10px; }
    h2 { color: #16213e; margin-top: 30px; }
    .header { display: flex; justify-content: space-between; align-items: center; }
    .grade { font-size: 48px; font-weight: bold; padding: 20px; border-radius: 10px;
             text-align: center; width: 100px; }
    .grade-a { background: #d4edda; color: #155724; }
    .grade-b { background: #fff3cd; color: #856404; }
    .grade-c { background: #ffeaa7; color: #856404; }
    .grade-d { background: #f8d7da; color: #721c24; }
    table { width: 100%; border-collapse: collapse; margin: 15px 0; }
    th, td { padding: 8px 12px; border: 1px solid #ddd; text-align: left; }
    th { background: #f8f9fa; }
    .status-clean { color: #155724; font-weight: bold; }
    .status-warning { color: #856404; font-weight: bold; }
    .status-danger { color: #721c24; font-weight: bold; }
    .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd;
              font-size: 12px; color: #666; }
</style>
</head>
<body>
    <div class="header">
        <div>
            <h1>iDiag Health Report</h1>
            <p><strong>{{ device.model or 'Unknown Model' }}</strong> &mdash;
               iOS {{ device.ios_version or 'N/A' }}</p>
            <p>Serial: {{ device.serial or 'N/A' }} &bull;
               IMEI: {{ device.imei or 'N/A' }}</p>
        </div>
        <div class="grade grade-{{ grade_class }}">{{ grade or 'N/A' }}</div>
    </div>

    <h2>Battery</h2>
    <table>
        <tr><th>Health</th><td>{{ battery_health }}%</td></tr>
        <tr><th>Cycle Count</th><td>{{ battery_cycles }}</td></tr>
    </table>

    <h2>Parts Originality</h2>
    <table>
        <tr><th>All Original</th><td>{{ 'Yes' if parts_original else 'No' }}</td></tr>
        {% if replaced_parts %}
        <tr><th>Replaced</th><td>{{ replaced_parts }}</td></tr>
        {% endif %}
    </table>

    <h2>Storage</h2>
    <table>
        <tr><th>Total</th><td>{{ storage_total }} GB</td></tr>
        <tr><th>Used</th><td>{{ storage_used }} GB</td></tr>
        <tr><th>Available</th><td>{{ storage_available }} GB</td></tr>
    </table>

    <h2>Verification</h2>
    <table>
        <tr><th>Blacklist</th>
            <td class="status-{{ 'clean' if blacklist == 'clean' else 'danger' }}">
                {{ blacklist }}</td></tr>
        <tr><th>Find My iPhone</th>
            <td class="status-{{ 'clean' if fmi == 'off' else 'danger' }}">
                {{ fmi }}</td></tr>
        <tr><th>Carrier</th><td>{{ carrier }}</td></tr>
        <tr><th>Carrier Lock</th>
            <td class="status-{{ 'warning' if carrier_locked else 'clean' }}">
                {{ 'Locked' if carrier_locked else 'Unlocked' }}</td></tr>
    </table>

    <div class="footer">
        <p>Generated by iDiag on {{ report_date }} &bull; UDID: {{ device.udid }}</p>
    </div>
</body>
</html>
"""


def generate_report_html(device: Any, diagnostics: Optional[Any] = None,
                         verification: Optional[Any] = None,
                         grade: str = "") -> str:
    """Render the HTML report template with device data."""
    from jinja2 import Template

    diag = diagnostics
    verif = verification
    grade_letter = grade[:1].upper() if grade else "N"
    grade_class = grade_letter.lower() if grade_letter in "ABCD" else "c"

    template = Template(REPORT_HTML_TEMPLATE)
    return template.render(
        device=device,
        grade=grade,
        grade_class=grade_class,
        battery_health=diag.battery.health_percent if diag else 0,
        battery_cycles=diag.battery.cycle_count if diag else 0,
        parts_original=diag.parts.all_original if diag else True,
        replaced_parts=", ".join(diag.parts.replaced_parts) if diag else "",
        storage_total=round(diag.storage.total_gb, 1) if diag else 0,
        storage_used=round(diag.storage.used_gb, 1) if diag else 0,
        storage_available=round(diag.storage.available_gb, 1) if diag else 0,
        blacklist=verif.blacklist_status if verif else "unknown",
        fmi=verif.fmi_status if verif else "unknown",
        carrier=verif.carrier if verif else "",
        carrier_locked=verif.carrier_locked if verif else False,
        report_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def generate_pdf(device: Any, diagnostics: Optional[Any] = None,
                 verification: Optional[Any] = None,
                 grade: str = "") -> bytes:
    """Generate PDF report bytes. Requires WeasyPrint."""
    html = generate_report_html(device, diagnostics, verification, grade)
    try:
        from weasyprint import HTML
        pdf_buffer = BytesIO()
        HTML(string=html).write_pdf(pdf_buffer)
        return pdf_buffer.getvalue()
    except ImportError:
        logger.error("WeasyPrint not installed — returning HTML as fallback")
        return html.encode("utf-8")
```

**Step 2: Write tests**

Create `tests/test_report_generator.py`:

```python
"""Tests for PDF report generator."""

from app.models.device import DeviceRecord
from app.models.diagnostic import BatteryInfo, DiagnosticResult, PartsOriginality, StorageInfo
from app.models.verification import VerificationResult
from app.services.report_generator import generate_report_html


class TestReportGenerator:
    def test_html_renders_device_info(self):
        device = DeviceRecord(udid="test-001", serial="C8QH6T96DPNG",
                              model="iPhone 13 Pro", ios_version="17.4")
        html = generate_report_html(device)
        assert "iPhone 13 Pro" in html
        assert "C8QH6T96DPNG" in html
        assert "17.4" in html

    def test_html_renders_diagnostics(self):
        device = DeviceRecord(udid="test-001", model="iPhone 12")
        diag = DiagnosticResult(
            battery=BatteryInfo(health_percent=87.5, cycle_count=423),
            parts=PartsOriginality(all_original=True),
            storage=StorageInfo(total_gb=256.0, used_gb=128.0, available_gb=128.0),
        )
        html = generate_report_html(device, diagnostics=diag)
        assert "87.5%" in html
        assert "423" in html
        assert "256.0 GB" in html

    def test_html_renders_verification(self):
        device = DeviceRecord(udid="test-001")
        verif = VerificationResult(blacklist_status="clean", fmi_status="off",
                                   carrier="T-Mobile", carrier_locked=False)
        html = generate_report_html(device, verification=verif)
        assert "clean" in html
        assert "T-Mobile" in html
        assert "Unlocked" in html

    def test_html_renders_grade(self):
        device = DeviceRecord(udid="test-001")
        html = generate_report_html(device, grade="B+")
        assert "B+" in html
        assert "grade-b" in html

    def test_html_handles_no_data(self):
        device = DeviceRecord(udid="test-001")
        html = generate_report_html(device)
        assert "iDiag Health Report" in html
        assert "N/A" in html
```

**Step 3: Run tests**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_report_generator.py']))"`

Expected: All pass

**Step 4: Commit**

```bash
git add app/services/report_generator.py tests/test_report_generator.py
git commit -m "feat(sprint4): add PDF health report generator"
```

---

## Task 5: QR Generator + Listing Generator + Export Service

**Files:**
- Create: `app/services/qr_generator.py`
- Create: `app/services/listing_generator.py`
- Create: `app/services/export_service.py`
- Test: `tests/test_generators.py`

**Step 1: Create QR generator**

Create `app/services/qr_generator.py`:

```python
"""QR code label generator."""

import logging
from io import BytesIO
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def generate_qr_png(udid: str, base_url: Optional[str] = None) -> bytes:
    """Generate QR code PNG bytes linking to the device page."""
    url = base_url or f"http://{settings.host}:{settings.port}"
    device_url = f"{url}/device/{udid}"

    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(device_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        logger.error("qrcode package not installed")
        return b""
```

**Step 2: Create listing generator**

Create `app/services/listing_generator.py`:

```python
"""Marketplace listing template generator."""

from app.models.device import DeviceRecord
from app.models.sales import ListingTemplate

EBAY_TEMPLATE = """
{model} - {storage} - {color} - Grade {grade}

**Condition:** {condition}

**Specifications:**
- Model: {model}
- iOS Version: {ios_version}
- Storage: {storage}
- Battery Health: {battery_health}%
- Grade: {grade}

**Verification:**
- Blacklist: {blacklist}
- Find My iPhone: {fmi}
- Carrier: {carrier} ({lock_status})

**What's Included:**
- {model}
- (add accessories here)

**Tested with iDiag diagnostic tool. Full health report available.**
""".strip()

MARKETPLACE_TEMPLATE = """
{model} - {storage} - Grade {grade}

{condition_desc}

Battery Health: {battery_health}%
Storage: {storage}
Carrier: {carrier} ({lock_status})
iOS: {ios_version}

Blacklist clean ✓ | FMI off ✓ | Fully tested ✓

Price: ${price}

No trades. Cash or electronic payment only.
""".strip()


def generate_listing(device: DeviceRecord, platform: str,
                     diagnostics=None, verification=None,
                     price: float = 0, condition: str = "Good") -> ListingTemplate:
    """Generate a marketplace listing template."""
    diag = diagnostics
    verif = verification

    data = {
        "model": device.model or "iPhone",
        "ios_version": device.ios_version or "N/A",
        "storage": f"{round(diag.storage.total_gb)}GB" if diag else "N/A",
        "color": "",
        "grade": device.grade or "N/A",
        "battery_health": diag.battery.health_percent if diag else "N/A",
        "blacklist": verif.blacklist_status if verif else "N/A",
        "fmi": verif.fmi_status if verif else "N/A",
        "carrier": verif.carrier if verif else "N/A",
        "lock_status": "Locked" if (verif and verif.carrier_locked) else "Unlocked",
        "condition": condition,
        "condition_desc": f"Condition: {condition}",
        "price": price,
    }

    if platform == "ebay":
        title = f"{data['model']} {data['storage']} {data['grade']}"
        desc = EBAY_TEMPLATE.format(**data)
    else:  # marketplace
        title = f"{data['model']} {data['storage']} - ${price}"
        desc = MARKETPLACE_TEMPLATE.format(**data)

    return ListingTemplate(
        platform=platform,
        title=title[:80],
        description=desc,
        price=price,
        condition=condition,
    )
```

**Step 3: Create export service**

Create `app/services/export_service.py`:

```python
"""Bulk CSV and JSON export service."""

import csv
import json
from io import StringIO
from typing import Optional

from app.models.device import DeviceRecord


def export_devices_csv(devices: list[DeviceRecord]) -> str:
    """Export device list to CSV string."""
    output = StringIO()
    fields = ["id", "udid", "serial", "imei", "model", "ios_version",
              "grade", "status", "buy_price", "notes", "created_at", "updated_at"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for d in devices:
        writer.writerow(d.model_dump(include=set(fields)))
    return output.getvalue()


def export_devices_json(devices: list[DeviceRecord]) -> str:
    """Export device list to JSON string."""
    data = [d.model_dump(mode="json") for d in devices]
    return json.dumps(data, indent=2, default=str)
```

**Step 4: Write tests**

Create `tests/test_generators.py`:

```python
"""Tests for QR, listing, and export generators."""

import json

from app.models.device import DeviceRecord
from app.models.diagnostic import BatteryInfo, DiagnosticResult, StorageInfo
from app.models.verification import VerificationResult
from app.services.export_service import export_devices_csv, export_devices_json
from app.services.listing_generator import generate_listing


class TestListingGenerator:
    def test_ebay_listing(self):
        device = DeviceRecord(udid="u1", model="iPhone 13 Pro", grade="B+",
                              ios_version="17.4")
        diag = DiagnosticResult(
            battery=BatteryInfo(health_percent=89.0),
            storage=StorageInfo(total_gb=256.0),
        )
        verif = VerificationResult(blacklist_status="clean", fmi_status="off",
                                   carrier="T-Mobile", carrier_locked=False)
        listing = generate_listing(device, "ebay", diag, verif, price=520)
        assert "iPhone 13 Pro" in listing.title
        assert "89" in listing.description
        assert "clean" in listing.description

    def test_marketplace_listing(self):
        device = DeviceRecord(udid="u1", model="iPhone 12", grade="A")
        listing = generate_listing(device, "marketplace", price=400)
        assert "$400" in listing.description
        assert listing.platform == "marketplace"


class TestExportService:
    def test_csv_export(self):
        devices = [
            DeviceRecord(udid="u1", model="iPhone 13", serial="SN1"),
            DeviceRecord(udid="u2", model="iPhone 14", serial="SN2"),
        ]
        csv_str = export_devices_csv(devices)
        assert "udid" in csv_str  # header
        assert "iPhone 13" in csv_str
        assert "iPhone 14" in csv_str
        lines = csv_str.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    def test_json_export(self):
        devices = [DeviceRecord(udid="u1", model="iPhone 13")]
        json_str = export_devices_json(devices)
        data = json.loads(json_str)
        assert len(data) == 1
        assert data[0]["model"] == "iPhone 13"

    def test_empty_export(self):
        assert "udid" in export_devices_csv([])
        assert json.loads(export_devices_json([])) == []
```

**Step 5: Run tests**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/test_generators.py']))"`

Expected: All pass

**Step 6: Commit**

```bash
git add app/services/qr_generator.py app/services/listing_generator.py app/services/export_service.py tests/test_generators.py
git commit -m "feat(sprint4): add QR, listing, and export generators"
```

---

## Task 6: Reports API + Wire Up + Dependencies

**Files:**
- Create: `app/api/reports.py`
- Modify: `app/main.py` (register 3 new routers)
- Modify: `requirements.txt` (add WeasyPrint + qrcode)

**Step 1: Create reports API**

Create `app/api/reports.py`:

```python
"""Reports API — PDF, QR codes, listings, bulk export."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.api.inventory import get_db
from app.services.export_service import export_devices_csv, export_devices_json
from app.services.listing_generator import generate_listing
from app.services.qr_generator import generate_qr_png
from app.services.report_generator import generate_pdf, generate_report_html

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/pdf/{device_id}")
def get_pdf_report(device_id: int):
    device = get_db().get_device_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Fetch latest diagnostics + verification from DB
    db = get_db()
    with db._lock:
        diag_row = db.conn.execute(
            "SELECT * FROM diagnostics WHERE device_id=? ORDER BY timestamp DESC LIMIT 1",
            (device_id,),
        ).fetchone()
        verif_row = db.conn.execute(
            "SELECT * FROM verifications WHERE device_id=? ORDER BY timestamp DESC LIMIT 1",
            (device_id,),
        ).fetchone()

    # Build lightweight objects for the template
    from app.models.diagnostic import BatteryInfo, DiagnosticResult, StorageInfo, PartsOriginality
    from app.models.verification import VerificationResult

    diagnostics = None
    if diag_row:
        diagnostics = DiagnosticResult(
            battery=BatteryInfo(health_percent=diag_row["battery_health"] or 0,
                                cycle_count=diag_row["battery_cycles"] or 0),
            parts=PartsOriginality(all_original=bool(diag_row["parts_original"])),
            storage=StorageInfo(total_gb=diag_row["storage_total"] or 0,
                                used_gb=diag_row["storage_used"] or 0),
        )

    verification = None
    if verif_row:
        verification = VerificationResult(
            blacklist_status=verif_row["blacklist_status"] or "unknown",
            fmi_status=verif_row["fmi_status"] or "unknown",
            carrier=verif_row["carrier"] or "",
            carrier_locked=bool(verif_row["carrier_locked"]),
        )

    pdf_bytes = generate_pdf(device, diagnostics, verification, device.grade)
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=idiag-{device.serial or device.udid}.pdf"})


@router.get("/html/{device_id}")
def get_html_report(device_id: int):
    """Same as PDF but returns HTML (useful for preview)."""
    device = get_db().get_device_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    html = generate_report_html(device, grade=device.grade)
    return Response(content=html, media_type="text/html")


@router.get("/qr/{device_id}")
def get_qr_code(device_id: int):
    device = get_db().get_device_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    png_bytes = generate_qr_png(device.udid)
    if not png_bytes:
        raise HTTPException(status_code=500, detail="QR generation failed — qrcode not installed")
    return Response(content=png_bytes, media_type="image/png",
                    headers={"Content-Disposition": f"inline; filename=qr-{device.serial or device.udid}.png"})


@router.get("/listing/{device_id}")
def get_listing(device_id: int, platform: str = "ebay", price: float = 0,
                condition: str = "Good"):
    device = get_db().get_device_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return generate_listing(device, platform, price=price, condition=condition)


@router.get("/export/csv")
def export_csv():
    devices = get_db().list_devices()
    csv_str = export_devices_csv(devices)
    return Response(content=csv_str, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=idiag-inventory.csv"})


@router.get("/export/json")
def export_json():
    devices = get_db().list_devices()
    json_str = export_devices_json(devices)
    return Response(content=json_str, media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=idiag-inventory.json"})
```

**Step 2: Register routers in `main.py`**

Add to imports (line 24):
```python
from app.api import devices, diagnostics, inventory, serial, verification, websocket
from app.api import photos, reports, sales  # Sprint 4
```

Add after existing `include_router` calls (after line 54):
```python
app.include_router(photos.router)
app.include_router(sales.router)
app.include_router(reports.router)
```

**Step 3: Update `requirements.txt`**

Add:
```
weasyprint>=62.0
qrcode[pil]>=8.0
```

**Step 4: Run ALL tests**

Run: `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/']))"`

Expected: All existing + new tests pass

**Step 5: Commit**

```bash
git add app/api/reports.py app/main.py requirements.txt
git commit -m "feat(sprint4): add reports API, wire up routers, update deps"
```

---

## Summary

| Task | What | New Files | Tests |
|------|------|-----------|-------|
| 1 | Models + DB + Config | `models/sales.py` | `test_sales_db.py` (7 tests) |
| 2 | Photo manager + API | `services/photo_manager.py`, `api/photos.py` | `test_photo_manager.py` (5 tests) |
| 3 | Sales API | `api/sales.py` | (covered by task 1 DB tests) |
| 4 | PDF report generator | `services/report_generator.py` | `test_report_generator.py` (5 tests) |
| 5 | QR + Listing + Export | `services/qr_generator.py`, `listing_generator.py`, `export_service.py` | `test_generators.py` (5 tests) |
| 6 | Reports API + wiring | `api/reports.py`, modify `main.py` | full suite run |

**Total: 9 new files, 3 modified files, ~22 new tests, 6 commits**
