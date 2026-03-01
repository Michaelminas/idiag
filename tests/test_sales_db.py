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
