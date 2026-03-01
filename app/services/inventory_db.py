"""SQLite inventory database — CRUD operations and schema management."""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.device import DeviceRecord
from app.models.diagnostic import DiagnosticResult
from app.models.sales import PhotoRecord, SalesRecord
from app.models.verification import VerificationResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    udid TEXT UNIQUE NOT NULL,
    serial TEXT DEFAULT '',
    imei TEXT DEFAULT '',
    model TEXT DEFAULT '',
    ios_version TEXT DEFAULT '',
    grade TEXT DEFAULT '',
    status TEXT DEFAULT 'intake',
    buy_price REAL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS diagnostics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    battery_health REAL,
    battery_cycles INTEGER,
    parts_original INTEGER,
    storage_total REAL,
    storage_used REAL,
    raw_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS crash_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    process TEXT DEFAULT '',
    exception TEXT DEFAULT '',
    subsystem TEXT DEFAULT '',
    severity INTEGER DEFAULT 0,
    count INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    blacklist_status TEXT DEFAULT 'unknown',
    fmi_status TEXT DEFAULT 'unknown',
    carrier TEXT DEFAULT '',
    carrier_locked INTEGER DEFAULT 0,
    mdm TEXT DEFAULT '',
    raw_json TEXT DEFAULT '{}'
);

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
"""


class InventoryDB:
    """Synchronous SQLite database for device inventory."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init_db(self) -> None:
        """Create tables if they don't exist."""
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # -- Devices CRUD --

    def upsert_device(self, record: DeviceRecord) -> int:
        """Insert or update a device record. Returns the device id."""
        with self._lock:
            existing = self._get_device_by_udid_unlocked(record.udid)
            now = datetime.now().isoformat()
            if existing:
                self.conn.execute(
                    """UPDATE devices SET serial=?, imei=?, model=?, ios_version=?,
                       grade=?, status=?, buy_price=?, notes=?, updated_at=?
                       WHERE udid=?""",
                    (
                        record.serial, record.imei, record.model, record.ios_version,
                        record.grade, record.status, record.buy_price, record.notes,
                        now, record.udid,
                    ),
                )
                self.conn.commit()
                return existing.id  # type: ignore[return-value]
            else:
                cur = self.conn.execute(
                    """INSERT INTO devices (udid, serial, imei, model, ios_version,
                       grade, status, buy_price, notes, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.udid, record.serial, record.imei, record.model,
                        record.ios_version, record.grade, record.status,
                        record.buy_price, record.notes, now, now,
                    ),
                )
                self.conn.commit()
                return cur.lastrowid  # type: ignore[return-value]

    def _get_device_by_udid_unlocked(self, udid: str) -> Optional[DeviceRecord]:
        """Internal lookup without lock — caller must hold self._lock."""
        row = self.conn.execute("SELECT * FROM devices WHERE udid=?", (udid,)).fetchone()
        return self._row_to_device(row) if row else None

    def get_device_by_udid(self, udid: str) -> Optional[DeviceRecord]:
        with self._lock:
            return self._get_device_by_udid_unlocked(udid)

    def get_device_by_id(self, device_id: int) -> Optional[DeviceRecord]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
            return self._row_to_device(row) if row else None

    def list_devices(self, status: Optional[str] = None) -> list[DeviceRecord]:
        with self._lock:
            if status:
                rows = self.conn.execute(
                    "SELECT * FROM devices WHERE status=? ORDER BY updated_at DESC", (status,)
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM devices ORDER BY updated_at DESC"
                ).fetchall()
            return [self._row_to_device(r) for r in rows]

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

    # -- Diagnostics --

    def save_diagnostic(self, device_id: int, result: DiagnosticResult) -> int:
        with self._lock:
            cur = self.conn.execute(
                """INSERT INTO diagnostics (device_id, battery_health, battery_cycles,
                   parts_original, storage_total, storage_used, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    device_id, result.battery.health_percent, result.battery.cycle_count,
                    1 if result.parts.all_original else 0,
                    result.storage.total_gb, result.storage.used_gb,
                    json.dumps(result.raw),
                ),
            )
            self.conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    # -- Verifications --

    def save_verification(self, device_id: int, result: VerificationResult) -> int:
        with self._lock:
            cur = self.conn.execute(
                """INSERT INTO verifications (device_id, blacklist_status, fmi_status,
                   carrier, carrier_locked, mdm, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    device_id, result.blacklist_status, result.fmi_status,
                    result.carrier, 1 if result.carrier_locked else 0,
                    result.mdm_organization, json.dumps(result.raw),
                ),
            )
            self.conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    # -- Crash Reports --

    def save_crash_summary(
        self, device_id: int, process: str, subsystem: str, severity: int, count: int
    ) -> int:
        with self._lock:
            cur = self.conn.execute(
                """INSERT INTO crash_reports (device_id, process, subsystem, severity, count)
                   VALUES (?, ?, ?, ?, ?)""",
                (device_id, process, subsystem, severity, count),
            )
            self.conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

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

    # -- Helpers --

    @staticmethod
    def _row_to_device(row: sqlite3.Row) -> DeviceRecord:
        return DeviceRecord(
            id=row["id"],
            udid=row["udid"],
            serial=row["serial"] or "",
            imei=row["imei"] or "",
            model=row["model"] or "",
            ios_version=row["ios_version"] or "",
            grade=row["grade"] or "",
            status=row["status"] or "intake",
            buy_price=row["buy_price"],
            notes=row["notes"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
