"""Device API routes."""

from fastapi import APIRouter, HTTPException

from app.models.device import DeviceCapability, DeviceInfo
from app.services import device_service

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("/connected")
def list_connected() -> list[str]:
    """List UDIDs of connected devices."""
    return device_service.list_connected_devices()


@router.get("/info")
@router.get("/info/{udid}")
def get_info(udid: str | None = None) -> DeviceInfo:
    """Get device identification info."""
    info = device_service.get_device_info(udid)
    if not info:
        raise HTTPException(status_code=404, detail="No device found or connection failed")
    return info


@router.get("/capabilities/{product_type}")
def get_capabilities(product_type: str) -> DeviceCapability:
    """Get device capabilities by ProductType (e.g. iPhone14,2)."""
    cap = device_service.get_capability(product_type)
    if not cap:
        raise HTTPException(status_code=404, detail=f"No capability data for {product_type}")
    return cap
