"""Tests for inventory database CRUD."""

import tempfile
from pathlib import Path

import pytest

from app.models.device import DeviceRecord
from app.models.diagnostic import BatteryInfo, DiagnosticResult, PartsOriginality, StorageInfo
from app.models.firmware import SHSHBlob, WipeRecord
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


def _insert_test_device(db) -> int:
    """Helper to insert a device for FK references."""
    return db.upsert_device(DeviceRecord(
        udid="test-udid-001", serial="C39FAKE123", imei="353456789012345",
        model="iPhone14,2", ios_version="17.4",
    ))


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


# -- Sell Price / Profit Tests --


class TestSellPriceAndProfit:
    def test_sell_price_stored_and_retrieved(self, db: InventoryDB):
        record = DeviceRecord(udid="price-test", buy_price=200.0, sell_price=350.0)
        device_id = db.upsert_device(record)
        fetched = db.get_device_by_id(device_id)
        assert fetched is not None
        assert fetched.sell_price == 350.0
        assert fetched.buy_price == 200.0

    def test_profit_computed_correctly(self, db: InventoryDB):
        record = DeviceRecord(udid="profit-test", buy_price=150.0, sell_price=275.0)
        device_id = db.upsert_device(record)
        fetched = db.get_device_by_id(device_id)
        assert fetched is not None
        assert fetched.profit == 125.0

    def test_profit_none_when_sell_price_missing(self, db: InventoryDB):
        record = DeviceRecord(udid="no-sell", buy_price=200.0)
        device_id = db.upsert_device(record)
        fetched = db.get_device_by_id(device_id)
        assert fetched is not None
        assert fetched.profit is None

    def test_profit_none_when_buy_price_missing(self, db: InventoryDB):
        record = DeviceRecord(udid="no-buy", sell_price=300.0)
        device_id = db.upsert_device(record)
        fetched = db.get_device_by_id(device_id)
        assert fetched is not None
        assert fetched.profit is None

    def test_sell_price_updated_on_upsert(self, db: InventoryDB):
        record = DeviceRecord(udid="update-sell", buy_price=100.0, sell_price=200.0)
        db.upsert_device(record)
        record.sell_price = 250.0
        db.upsert_device(record)
        fetched = db.get_device_by_udid("update-sell")
        assert fetched is not None
        assert fetched.sell_price == 250.0
        assert fetched.profit == 150.0
