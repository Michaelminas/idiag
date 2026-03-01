"""Device connection & auto-discovery via pymobiledevice3.

Provides connect(udid) -> DeviceHandle with all services accessible.
Handles iOS 17+ tunnel negotiation automatically.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.device import DeviceCapability, DeviceInfo

logger = logging.getLogger(__name__)


def _load_capabilities() -> dict[str, DeviceCapability]:
    path = settings.device_capabilities_path
    if not path.exists():
        return {}
    with open(path) as f:
        raw = json.load(f)
    return {k: DeviceCapability(**v) for k, v in raw.items()}


try:
    CAPABILITIES = _load_capabilities()
except Exception:
    logger.error("Failed to load device capabilities, using empty map")
    CAPABILITIES = {}


def get_capability(product_type: str) -> Optional[DeviceCapability]:
    """Look up device capabilities by ProductType (e.g. 'iPhone14,2')."""
    return CAPABILITIES.get(product_type)


def list_connected_devices() -> list[str]:
    """Return UDIDs of all USB-connected iOS devices."""
    try:
        from pymobiledevice3.usbmux import list_devices
        return [dev.serial for dev in list_devices() if dev.is_usb]
    except Exception as e:
        logger.error("Failed to list devices: %s", e)
        return []


def get_device_info(udid: Optional[str] = None) -> Optional[DeviceInfo]:
    """Connect to a device and retrieve all identification info."""
    try:
        from pymobiledevice3.lockdown import create_using_usbmux

        with create_using_usbmux(serial=udid) as lockdown:
            info = DeviceInfo(
                udid=lockdown.udid,
                serial=lockdown.get_value(key="SerialNumber") or "",
                imei=lockdown.get_value(key="InternationalMobileEquipmentIdentity") or "",
                imei2=lockdown.get_value(key="InternationalMobileEquipmentIdentity2") or "",
                model_number=lockdown.get_value(key="ModelNumber") or "",
                product_type=lockdown.product_type or "",
                hardware_model=lockdown.hardware_model or "",
                device_name=lockdown.get_value(key="DeviceName") or "",
                device_color=lockdown.get_value(key="DeviceColor") or "",
                ios_version=lockdown.product_version or "",
                build_version=lockdown.product_build_version or "",
                wifi_mac=lockdown.wifi_mac_address or "",
                ecid=lockdown.ecid or 0,
            )
            return info
    except ImportError:
        logger.error("pymobiledevice3 not installed")
        return None
    except Exception as e:
        logger.error("Failed to get device info: %s", e)
        return None


def get_lockdown_client(udid: Optional[str] = None):
    """Get a raw lockdown client for use by other services.

    Returns a context manager. Caller must use `with` statement.
    Raises ImportError if pymobiledevice3 is not installed.
    """
    try:
        from pymobiledevice3.lockdown import create_using_usbmux
    except ImportError:
        raise ImportError("pymobiledevice3 is required. Install with: pip install pymobiledevice3")
    return create_using_usbmux(serial=udid)
