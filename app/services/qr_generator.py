"""QR code label generator."""

import logging
from io import BytesIO
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def generate_qr_png(udid: str, base_url: Optional[str] = None) -> bytes:
    """Generate QR code PNG bytes linking to the device page."""
    url = base_url or f"http://{settings.host}:{settings.port}"
    device_url = f"{url}/device/{udid}"

    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(device_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        logger.error("qrcode package not installed")
        return b""
