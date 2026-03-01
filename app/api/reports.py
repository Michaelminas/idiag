"""Reports API — PDF, QR codes, listings, bulk export."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.api.inventory import get_db
from app.services.export_service import export_devices_csv, export_devices_json
from app.services.listing_generator import generate_listing
from app.services.qr_generator import generate_qr_png
from app.services.report_generator import generate_pdf, generate_report_html

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/pdf/{device_id}")
def get_pdf_report(device_id: int):
    db = get_db()
    device = db.get_device_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Fetch latest diagnostics + verification from DB via public methods
    from app.models.diagnostic import BatteryInfo, DiagnosticResult, StorageInfo, PartsOriginality
    from app.models.verification import VerificationResult

    diagnostics = None
    diag_rows = db.list_diagnostics(device_id)
    if diag_rows:
        d = diag_rows[0]  # newest first
        diagnostics = DiagnosticResult(
            battery=BatteryInfo(health_percent=d.get("battery_health") or 0,
                                cycle_count=d.get("battery_cycles") or 0),
            parts=PartsOriginality(all_original=bool(d.get("parts_original"))),
            storage=StorageInfo(total_gb=d.get("storage_total") or 0,
                                used_gb=d.get("storage_used") or 0),
        )

    verification = None
    verif_rows = db.list_verifications(device_id)
    if verif_rows:
        v = verif_rows[0]  # newest first
        verification = VerificationResult(
            blacklist_status=v.get("blacklist_status") or "unknown",
            fmi_status=v.get("fmi_status") or "unknown",
            carrier=v.get("carrier") or "",
            carrier_locked=bool(v.get("carrier_locked")),
        )

    pdf_bytes = generate_pdf(device, diagnostics, verification, device.grade)
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=idiag-{device.serial or device.udid}.pdf"})


@router.get("/html/{device_id}")
def get_html_report(device_id: int):
    """Same as PDF but returns HTML (useful for preview)."""
    device = get_db().get_device_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    html = generate_report_html(device, grade=device.grade)
    return Response(content=html, media_type="text/html")


@router.get("/qr/{device_id}")
def get_qr_code(device_id: int):
    device = get_db().get_device_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    png_bytes = generate_qr_png(device.udid)
    if not png_bytes:
        raise HTTPException(status_code=500, detail="QR generation failed — qrcode not installed")
    return Response(content=png_bytes, media_type="image/png",
                    headers={"Content-Disposition": f"inline; filename=qr-{device.serial or device.udid}.png"})


@router.get("/listing/{device_id}")
def get_listing(device_id: int, platform: str = "ebay", price: float = 0,
                condition: str = "Good"):
    device = get_db().get_device_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return generate_listing(device, platform, price=price, condition=condition)


@router.get("/export/csv")
def export_csv():
    devices = get_db().list_devices()
    csv_str = export_devices_csv(devices)
    return Response(content=csv_str, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=idiag-inventory.csv"})


@router.get("/export/json")
def export_json():
    devices = get_db().list_devices()
    json_str = export_devices_json(devices)
    return Response(content=json_str, media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=idiag-inventory.json"})
