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
