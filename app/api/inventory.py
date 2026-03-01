"""Inventory API routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.models.device import DeviceRecord
from app.services.inventory_db import InventoryDB

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

_db: Optional[InventoryDB] = None


def get_db() -> InventoryDB:
    global _db
    if _db is None:
        _db = InventoryDB()
        _db.init_db()
    return _db


@router.get("/devices")
def list_devices(status: str | None = None) -> list[DeviceRecord]:
    return get_db().list_devices(status)


@router.get("/devices/{device_id}")
def get_device(device_id: int) -> DeviceRecord:
    record = get_db().get_device_by_id(device_id)
    if not record:
        raise HTTPException(status_code=404, detail="Device not found")
    return record


@router.post("/devices")
def upsert_device(record: DeviceRecord) -> dict:
    device_id = get_db().upsert_device(record)
    return {"id": device_id}


@router.delete("/devices/{device_id}")
def delete_device(device_id: int) -> dict:
    if get_db().delete_device(device_id):
        return {"deleted": True}
    raise HTTPException(status_code=404, detail="Device not found")
