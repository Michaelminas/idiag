"""Device-related data models."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

DeviceStatus = Literal["intake", "testing", "listed", "sold", "returned", "junk"]


class DeviceInfo(BaseModel):
    """Core device identification from pymobiledevice3 lockdown."""

    udid: str
    serial: str = ""
    imei: str = ""
    imei2: str = ""
    model_number: str = ""  # A-number e.g. "A2483"
    product_type: str = ""  # e.g. "iPhone14,2"
    hardware_model: str = ""  # e.g. "D63AP"
    device_name: str = ""
    device_color: str = ""
    ios_version: str = ""
    build_version: str = ""
    wifi_mac: str = ""
    ecid: int = 0


class DeviceCapability(BaseModel):
    """What a device model supports — loaded from device_capabilities.json."""

    name: str
    chip: str
    checkm8: bool = False
    esim: bool = False
    faceid: bool = False
    touchid: bool = False
    max_ios: Optional[str] = None


class DeviceRecord(BaseModel):
    """Persisted device record in inventory database."""

    id: Optional[int] = None
    udid: str
    serial: str = ""
    imei: str = ""
    model: str = ""
    ios_version: str = ""
    grade: str = ""
    status: DeviceStatus = "intake"
    buy_price: Optional[float] = None
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
