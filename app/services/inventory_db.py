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
from app.models.firmware import SHSHBlob, WipeRecord
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
    sell_price REAL,
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
            # Sprint 2 migration: add sell_price column if missing
            try:
                self.conn.execute("SELECT sell_price FROM devices LIMIT 1")
            except sqlite3.OperationalError:
                self.conn.execute("ALTER TABLE devices ADD COLUMN sell_price REAL")

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
                       grade=?, status=?, buy_price=?, sell_price=?, notes=?, updated_at=?
                       WHERE udid=?""",
                    (
                        record.serial, record.imei, record.model, record.ios_version,
                        record.grade, record.status, record.buy_price, record.sell_price,
                        record.notes, now, record.udid,
                    ),
                )
                self.conn.commit()
                return existing.id  # type: ignore[return-value]
            else:
                cur = self.conn.execute(
                    """INSERT INTO devices (udid, serial, imei, model, ios_version,
                       grade, status, buy_price, sell_price, notes, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.udid, record.serial, record.imei, record.model,
                        record.ios_version, record.grade, record.status,
                        record.buy_price, record.sell_price, record.notes, now, now,
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
            self.conn.execute("DELETE FROM wipe_records WHERE device_id=?", (device_id,))
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
            return cur.lastrowid  # type: ignore[return-value]

    def list_photos(self, device_id: int) -> list[PhotoRecord]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM photos WHERE device_id=? ORDER BY created_at", (device_id,)
            ).fetchall()
            return [PhotoRecord(
                id=r["id"], device_id=r["device_id"], filename=r["filename"],
                filepath=r["filepath"], label=r["label"], created_at=r["created_at"],
            ) for r in rows]

    def get_photo_by_id(self, photo_id: int) -> Optional[PhotoRecord]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
            if not row:
                return None
            return PhotoRecord(
                id=row["id"], device_id=row["device_id"], filename=row["filename"],
                filepath=row["filepath"], label=row["label"], created_at=row["created_at"],
            )

    def delete_photo(self, photo_id: int) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM photos WHERE id=?", (photo_id,))
            self.conn.commit()
            return cur.rowcount > 0

    # -- Sales --

    def save_sale(self, record: SalesRecord) -> int:
        with self._lock:
            device = self._get_device_by_id_unlocked(record.device_id)

            # Auto-compute profit if sell_price is set
            profit = None
            if record.sell_price is not None:
                buy_price = device.buy_price if device and device.buy_price else 0.0
                profit = record.sell_price - buy_price - record.fees

            # Auto-compute days_in_inventory
            days = record.days_in_inventory
            if days is None and device and device.created_at:
                created = (device.created_at if isinstance(device.created_at, datetime)
                           else datetime.fromisoformat(str(device.created_at)))
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
            return cur.lastrowid  # type: ignore[return-value]

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

    # -- History Queries --

    def list_diagnostics(self, device_id: int) -> list[dict]:
        """Return all diagnostic records for a device, newest first."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM diagnostics WHERE device_id=? ORDER BY timestamp DESC",
                (device_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_verifications(self, device_id: int) -> list[dict]:
        """Return all verification records for a device, newest first."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM verifications WHERE device_id=? ORDER BY timestamp DESC",
                (device_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_crash_history(self, device_id: int) -> list[dict]:
        """Return all crash report summaries for a device, newest first."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM crash_reports WHERE device_id=? ORDER BY timestamp DESC",
                (device_id,),
            ).fetchall()
            return [dict(row) for row in rows]

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
            sell_price=row["sell_price"],
            notes=row["notes"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
