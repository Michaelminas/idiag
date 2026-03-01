"""Tests for inventory database CRUD."""

import tempfile
from pathlib import Path

import pytest

from app.models.device import DeviceRecord
from app.models.diagnostic import BatteryInfo, DiagnosticResult, PartsOriginality, StorageInfo
from app.models.verification import VerificationResult
from app.services.inventory_db import InventoryDB


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = InventoryDB(db_path=Path(tmpdir) / "test.db")
        db.init_db()
        yield db
        db.close()


class TestDeviceCRUD:
    def test_upsert_and_get(self, db: InventoryDB):
        record = DeviceRecord(udid="test-udid-001", serial="C8QH6T96DPNG", model="iPhone 13 Pro")
        device_id = db.upsert_device(record)
        assert device_id is not None

        fetched = db.get_device_by_udid("test-udid-001")
        assert fetched is not None
        assert fetched.serial == "C8QH6T96DPNG"
        assert fetched.model == "iPhone 13 Pro"

    def test_upsert_updates_existing(self, db: InventoryDB):
        record = DeviceRecord(udid="test-udid-001", serial="SN1", model="iPhone 12")
        db.upsert_device(record)

        record.model = "iPhone 12 Pro"
        db.upsert_device(record)

        fetched = db.get_device_by_udid("test-udid-001")
        assert fetched.model == "iPhone 12 Pro"

    def test_list_devices(self, db: InventoryDB):
        db.upsert_device(DeviceRecord(udid="u1", status="intake"))
        db.upsert_device(DeviceRecord(udid="u2", status="listed"))
        db.upsert_device(DeviceRecord(udid="u3", status="intake"))

        all_devices = db.list_devices()
        assert len(all_devices) == 3

        intake_only = db.list_devices(status="intake")
        assert len(intake_only) == 2

    def test_delete_device(self, db: InventoryDB):
        device_id = db.upsert_device(DeviceRecord(udid="to-delete"))
        assert db.delete_device(device_id)
        assert db.get_device_by_udid("to-delete") is None


class TestDiagnosticStorage:
    def test_save_diagnostic(self, db: InventoryDB):
        device_id = db.upsert_device(DeviceRecord(udid="diag-test"))
        result = DiagnosticResult(
            battery=BatteryInfo(health_percent=87.5, cycle_count=423),
            parts=PartsOriginality(all_original=True),
            storage=StorageInfo(total_gb=256.0, used_gb=128.0),
        )
        diag_id = db.save_diagnostic(device_id, result)
        assert diag_id is not None


class TestVerificationStorage:
    def test_save_verification(self, db: InventoryDB):
        device_id = db.upsert_device(DeviceRecord(udid="verify-test"))
        result = VerificationResult(
            blacklist_status="clean", fmi_status="off",
            carrier="T-Mobile", carrier_locked=False,
        )
        ver_id = db.save_verification(device_id, result)
        assert ver_id is not None
