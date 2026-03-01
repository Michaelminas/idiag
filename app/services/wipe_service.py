"""Wipe service — device data erasure and PDF certificate generation."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.models.firmware import WipeRecord

logger = logging.getLogger(__name__)

# Template environment for certificate rendering
_templates_dir = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_templates_dir)), autoescape=True)


# ---------------------------------------------------------------------------
# Device Erase
# ---------------------------------------------------------------------------

def _perform_erase(udid: Optional[str] = None) -> bool:
    """Execute factory reset via pymobiledevice3. Mock boundary for tests."""
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.diagnostics import DiagnosticsService

    with create_using_usbmux(serial=udid) as lockdown:
        with DiagnosticsService(lockdown) as diag:
            diag.erase_device()
    return True


def erase_device(udid: Optional[str] = None) -> bool:
    """Factory reset a connected device."""
    try:
        return _perform_erase(udid)
    except Exception as e:
        logger.error("Device erase failed for %s: %s", udid or "auto", e)
        return False


# ---------------------------------------------------------------------------
# Certificate Generation
# ---------------------------------------------------------------------------

def render_certificate_html(record: WipeRecord) -> str:
    """Render erasure certificate as HTML string."""
    template = _jinja_env.get_template("erasure_certificate.html")
    return template.render(record=record)


def _html_to_pdf(html: str, output_path: Path) -> bool:
    """Convert HTML string to PDF via WeasyPrint. Mock boundary for tests."""
    from weasyprint import HTML
    HTML(string=html).write_pdf(str(output_path))
    return True


def generate_certificate(
    record: WipeRecord, output_dir: Optional[Path] = None
) -> Optional[Path]:
    """Generate a PDF erasure certificate for a wipe record."""
    output_dir = output_dir or settings.cert_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = record.timestamp.strftime("%Y%m%d_%H%M%S") if record.timestamp else "unknown"
    filename = f"erasure_{record.serial}_{ts}.pdf"
    output_path = output_dir / filename

    try:
        html = render_certificate_html(record)
        _html_to_pdf(html, output_path)
        logger.info("Generated erasure certificate: %s", filename)
        return output_path
    except Exception as e:
        logger.error("Certificate generation failed: %s", e)
        return None
