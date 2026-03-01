"""API route tests — exercises all HTTP endpoints via TestClient."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.device import DeviceCapability, DeviceInfo, DeviceRecord
from app.models.diagnostic import BatteryInfo, DiagnosticResult, PartsOriginality, StorageInfo
from app.models.crash import CrashAnalysis
from app.models.firmware import FirmwareVersion, WipeRecord
from app.models.grading import DeviceGrade
from app.models.verification import VerificationResult
from app.services.inventory_db import InventoryDB

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures — temp DB for inventory-backed endpoints
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path):
    db = InventoryDB(db_path=tmp_path / "test.db")
    db.init_db()
    yield db
    db.close()


@pytest.fixture()
def _patch_db(tmp_db):
    """Patch get_db in every API module that imports it."""
    targets = [
        "app.api.inventory.get_db",
        "app.api.firmware.get_db",
        "app.api.photos.get_db",
        "app.api.sales.get_db",
        "app.api.reports.get_db",
        "app.api.diagnostics.get_db",
    ]
    patchers = [patch(t, return_value=tmp_db) for t in targets]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture()
def seed_device(tmp_db) -> DeviceRecord:
    """Insert a test device and return the record with its id."""
    rec = DeviceRecord(udid="test-udid-001", serial="DNPXXXXXXXX", imei="353462111234567",
                       model="iPhone 13 Pro", ios_version="17.2", grade="A", buy_price=400)
    device_id = tmp_db.upsert_device(rec)
    rec.id = device_id
    return rec


# ===========================================================================
# Devices API
# ===========================================================================

class TestDevicesAPI:
    @patch("app.api.devices.device_service.list_connected_devices", return_value=["udid-1", "udid-2"])
    def test_list_connected(self, _mock):
        resp = client.get("/api/devices/connected")
        assert resp.status_code == 200
        assert resp.json() == ["udid-1", "udid-2"]

    @patch("app.api.devices.device_service.get_device_info")
    def test_get_info(self, mock_info):
        mock_info.return_value = DeviceInfo(udid="u1", serial="SER123", product_type="iPhone14,2")
        resp = client.get("/api/devices/info/u1")
        assert resp.status_code == 200
        assert resp.json()["serial"] == "SER123"

    @patch("app.api.devices.device_service.get_device_info", return_value=None)
    def test_get_info_404(self, _mock):
        resp = client.get("/api/devices/info/nonexistent")
        assert resp.status_code == 404

    @patch("app.api.devices.device_service.get_capability")
    def test_get_capabilities(self, mock_cap):
        mock_cap.return_value = DeviceCapability(name="iPhone 13 Pro", chip="A15", checkm8=False)
        resp = client.get("/api/devices/capabilities/iPhone14,2")
        assert resp.status_code == 200
        assert resp.json()["chip"] == "A15"

    @patch("app.api.devices.device_service.get_capability", return_value=None)
    def test_get_capabilities_404(self, _mock):
        resp = client.get("/api/devices/capabilities/UnknownDevice")
        assert resp.status_code == 404


# ===========================================================================
# Diagnostics API
# ===========================================================================

class TestDiagnosticsAPI:
    @patch("app.api.diagnostics.diagnostic_engine.run_diagnostics")
    def test_run_diagnostics(self, mock_diag):
        mock_diag.return_value = DiagnosticResult(battery=BatteryInfo(health_percent=92.0, cycle_count=150))
        resp = client.get("/api/diagnostics/run/test-udid")
        assert resp.status_code == 200
        assert resp.json()["battery"]["health_percent"] == 92.0

    @patch("app.api.diagnostics.log_analyzer.analyze_device")
    def test_analyze_crashes(self, mock_crashes):
        mock_crashes.return_value = CrashAnalysis(total_reports=10, matched_reports=3)
        resp = client.get("/api/diagnostics/crashes/test-udid")
        assert resp.status_code == 200
        assert resp.json()["total_reports"] == 10

    def test_grade_post(self):
        body = {
            "diagnostics": {"battery": {"health_percent": 95}, "parts": {}, "storage": {}},
            "crashes": {},
            "verification": {},
        }
        resp = client.post("/api/diagnostics/grade", json=body)
        assert resp.status_code == 200
        assert "overall_grade" in resp.json()

    @patch("app.api.diagnostics.diagnostic_engine.run_diagnostics")
    @patch("app.api.diagnostics.log_analyzer.analyze_device")
    @patch("app.api.diagnostics.verification_service.run_verification", new_callable=AsyncMock)
    def test_grade_live(self, mock_verif, mock_crashes, mock_diag):
        mock_diag.return_value = DiagnosticResult(battery=BatteryInfo(health_percent=95))
        mock_crashes.return_value = CrashAnalysis()
        mock_verif.return_value = VerificationResult(blacklist_status="clean")
        resp = client.get("/api/diagnostics/grade/test-udid?imei=353462111234567")
        assert resp.status_code == 200
        assert resp.json()["overall_grade"] in ("A", "B", "C", "D", "F")


# ===========================================================================
# Verification API
# ===========================================================================

class TestVerificationAPI:
    @patch("app.api.verification.verification_service.run_verification", new_callable=AsyncMock)
    def test_check_imei(self, mock_verif):
        mock_verif.return_value = VerificationResult(blacklist_status="clean", carrier="T-Mobile")
        resp = client.get("/api/verification/check/353462111234567")
        assert resp.status_code == 200
        assert resp.json()["blacklist_status"] == "clean"
        assert resp.json()["carrier"] == "T-Mobile"


# ===========================================================================
# Serial API (pure functions — no mocks needed)
# ===========================================================================

class TestSerialAPI:
    def test_decode_serial(self):
        resp = client.get("/api/serial/decode/DNPXXXXXXXX")
        assert resp.status_code == 200
        assert "raw" in resp.json()

    def test_validate_imei_valid(self):
        resp = client.get("/api/serial/validate-imei/353462111234567")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_valid" in data
        assert "luhn_valid" in data

    def test_validate_imei_invalid(self):
        resp = client.get("/api/serial/validate-imei/123456789012345")
        assert resp.status_code == 200
        assert resp.json()["luhn_valid"] is False

    def test_fraud_check(self):
        resp = client.get("/api/serial/fraud-check?serial=DNPXXXXXXXX&model_number=A2483&product_type=iPhone14,2&imei=353462111234567")
        assert resp.status_code == 200
        data = resp.json()
        assert "fraud_score" in data
        assert "is_suspicious" in data


# ===========================================================================
# Inventory API (DB-backed)
# ===========================================================================

@pytest.mark.usefixtures("_patch_db")
class TestInventoryAPI:
    def test_list_devices_empty(self):
        resp = client.get("/api/inventory/devices")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_upsert_and_get(self, seed_device):
        resp = client.get(f"/api/inventory/devices/{seed_device.id}")
        assert resp.status_code == 200
        assert resp.json()["serial"] == "DNPXXXXXXXX"

    def test_get_device_404(self):
        resp = client.get("/api/inventory/devices/9999")
        assert resp.status_code == 404

    def test_upsert_via_post(self):
        body = {"udid": "new-device-udid", "serial": "ABC123", "model": "iPhone 15"}
        resp = client.post("/api/inventory/devices", json=body)
        assert resp.status_code == 200
        device_id = resp.json()["id"]
        assert device_id > 0

        resp2 = client.get(f"/api/inventory/devices/{device_id}")
        assert resp2.json()["serial"] == "ABC123"

    def test_delete_device(self, seed_device):
        resp = client.delete(f"/api/inventory/devices/{seed_device.id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        resp2 = client.get(f"/api/inventory/devices/{seed_device.id}")
        assert resp2.status_code == 404

    def test_delete_device_404(self):
        resp = client.delete("/api/inventory/devices/9999")
        assert resp.status_code == 404

    def test_list_with_status_filter(self, seed_device):
        resp = client.get("/api/inventory/devices?status=intake")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        resp2 = client.get("/api/inventory/devices?status=sold")
        assert resp2.status_code == 200
        assert len(resp2.json()) == 0

    def test_device_diagnostics_history(self, seed_device, tmp_db):
        from app.models.diagnostic import DiagnosticResult, BatteryInfo
        tmp_db.save_diagnostic(seed_device.id, DiagnosticResult(
            battery=BatteryInfo(health_percent=90, cycle_count=100)))
        resp = client.get(f"/api/inventory/devices/{seed_device.id}/diagnostics")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_device_verifications_history(self, seed_device, tmp_db):
        tmp_db.save_verification(seed_device.id, VerificationResult(blacklist_status="clean"))
        resp = client.get(f"/api/inventory/devices/{seed_device.id}/verifications")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_device_crashes_history(self, seed_device, tmp_db):
        tmp_db.save_crash_summary(seed_device.id, "mediaserverd", "Camera", 5, 3)
        resp = client.get(f"/api/inventory/devices/{seed_device.id}/crashes")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_history_404_for_unknown_device(self):
        resp = client.get("/api/inventory/devices/9999/diagnostics")
        assert resp.status_code == 404


# ===========================================================================
# Firmware API
# ===========================================================================

class TestFirmwareAPI:
    @patch("app.api.firmware.firmware_manager.get_signed_versions")
    def test_signed_versions(self, mock_sv):
        mock_sv.return_value = [
            FirmwareVersion(version="18.2", build_id="22C150", model="iPhone14,2",
                            url="https://example.com/fw.ipsw", signed=True),
        ]
        resp = client.get("/api/firmware/signed/iPhone14,2")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["version"] == "18.2"

    @patch("app.api.firmware.firmware_manager.list_cached_ipsw", return_value=[])
    def test_list_cache_empty(self, _mock):
        resp = client.get("/api/firmware/cache")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("app.api.firmware.firmware_manager.get_device_mode", return_value="normal")
    def test_get_device_mode(self, _mock):
        resp = client.get("/api/firmware/mode/test-udid")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "normal"

    @patch("app.api.firmware.firmware_manager.enter_recovery_mode", return_value=True)
    def test_enter_recovery(self, _mock):
        resp = client.post("/api/firmware/recovery/test-udid")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @patch("app.api.firmware.firmware_manager.enter_recovery_mode", return_value=False)
    def test_enter_recovery_failure(self, _mock):
        resp = client.post("/api/firmware/recovery/test-udid")
        assert resp.status_code == 500

    @patch("app.api.firmware.firmware_manager.exit_recovery_mode", return_value=True)
    def test_exit_recovery(self, _mock):
        resp = client.delete("/api/firmware/recovery/test-udid")
        assert resp.status_code == 200

    @patch("app.api.firmware.firmware_manager.enter_dfu_mode", return_value=True)
    def test_enter_dfu(self, _mock):
        resp = client.post("/api/firmware/dfu/test-udid")
        assert resp.status_code == 200
        assert "recovery_entered" in resp.json()["status"]

    @patch("app.api.firmware.firmware_manager.enter_dfu_mode", return_value=False)
    def test_enter_dfu_failure(self, _mock):
        resp = client.post("/api/firmware/dfu/test-udid")
        assert resp.status_code == 500

    @pytest.mark.usefixtures("_patch_db")
    @patch("app.api.firmware.firmware_manager.get_signed_versions")
    @patch("app.api.firmware.firmware_manager.download_ipsw")
    def test_download_ipsw(self, mock_dl, mock_sv):
        mock_sv.return_value = [
            FirmwareVersion(version="18.2", model="iPhone14,2",
                            url="https://example.com/fw.ipsw"),
        ]
        mock_dl.return_value = Path("/tmp/fw.ipsw")
        resp = client.post("/api/firmware/download",
                           json={"model": "iPhone14,2", "version": "18.2"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "downloaded"

    @pytest.mark.usefixtures("_patch_db")
    @patch("app.api.firmware.firmware_manager.restore_device", return_value=True)
    @patch("app.api.websocket.broadcast", new_callable=AsyncMock)
    def test_restore_device(self, _mock_bc, _mock_restore):
        resp = client.post("/api/firmware/restore/test-udid",
                           json={"model": "iPhone14,2", "version": "18.2"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "restored"

    @pytest.mark.usefixtures("_patch_db")
    @patch("app.api.firmware.wipe_service.erase_device", return_value=True)
    @patch("app.api.firmware.wipe_service.generate_certificate", return_value=None)
    @patch("app.api.websocket.broadcast", new_callable=AsyncMock)
    def test_wipe_device(self, _mock_bc, _mock_cert, _mock_erase):
        resp = client.post("/api/firmware/wipe/test-udid",
                           json={"serial": "SER123", "model": "iPhone 13 Pro"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "erased"


# ===========================================================================
# Sales API (DB-backed)
# ===========================================================================

@pytest.mark.usefixtures("_patch_db")
class TestSalesAPI:
    def test_list_all_sales_empty(self):
        resp = client.get("/api/sales/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_record_and_get_sale(self, seed_device):
        body = {"device_id": seed_device.id, "sell_price": 600, "platform": "ebay", "fees": 50}
        resp = client.post("/api/sales/", json=body)
        assert resp.status_code == 200
        sale_id = resp.json()["id"]

        resp2 = client.get(f"/api/sales/{sale_id}")
        assert resp2.status_code == 200
        assert resp2.json()["sell_price"] == 600
        assert resp2.json()["platform"] == "ebay"

    def test_record_sale_device_404(self):
        body = {"device_id": 9999, "sell_price": 500}
        resp = client.post("/api/sales/", json=body)
        assert resp.status_code == 404

    def test_get_sale_404(self):
        resp = client.get("/api/sales/9999")
        assert resp.status_code == 404

    def test_list_device_sales(self, seed_device):
        client.post("/api/sales/", json={"device_id": seed_device.id, "sell_price": 500})
        resp = client.get(f"/api/sales/device/{seed_device.id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_sale_sets_device_to_sold(self, seed_device):
        client.post("/api/sales/", json={"device_id": seed_device.id, "sell_price": 500})
        resp = client.get(f"/api/inventory/devices/{seed_device.id}")
        assert resp.json()["status"] == "sold"


# ===========================================================================
# Photos API (DB-backed + PhotoManager mock)
# ===========================================================================

@pytest.mark.usefixtures("_patch_db")
class TestPhotosAPI:
    def test_list_photos_empty(self, seed_device):
        resp = client.get(f"/api/photos/device/{seed_device.id}")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("app.api.photos._pm")
    def test_upload_photo(self, mock_pm, seed_device):
        mock_pm.save.return_value = ("photo_001.jpg", "test-udid-001/photo_001.jpg")
        resp = client.post(
            f"/api/photos/upload/{seed_device.id}",
            files={"file": ("test.jpg", b"fake-image-data", "image/jpeg")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "photo_001.jpg"

    def test_upload_photo_device_404(self):
        resp = client.post(
            "/api/photos/upload/9999",
            files={"file": ("test.jpg", b"data", "image/jpeg")},
        )
        assert resp.status_code == 404

    def test_get_photo_file_404(self):
        resp = client.get("/api/photos/file/9999")
        assert resp.status_code == 404

    def test_delete_photo_404(self):
        resp = client.delete("/api/photos/9999")
        assert resp.status_code == 404


# ===========================================================================
# Reports API (DB-backed + generator mocks)
# ===========================================================================

@pytest.mark.usefixtures("_patch_db")
class TestReportsAPI:
    def test_html_report(self, seed_device):
        resp = client.get(f"/api/reports/html/{seed_device.id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/html; charset=utf-8"
        assert "iDiag" in resp.text

    def test_html_report_404(self):
        resp = client.get("/api/reports/html/9999")
        assert resp.status_code == 404

    @patch("app.api.reports.generate_qr_png", return_value=b"\x89PNG\r\nfake")
    def test_qr_code(self, _mock, seed_device):
        resp = client.get(f"/api/reports/qr/{seed_device.id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    def test_qr_code_404(self):
        resp = client.get("/api/reports/qr/9999")
        assert resp.status_code == 404

    def test_listing_ebay(self, seed_device):
        resp = client.get(f"/api/reports/listing/{seed_device.id}?platform=ebay&price=500")
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform"] == "ebay"
        assert "title" in data
        assert "description" in data

    def test_listing_marketplace(self, seed_device):
        resp = client.get(f"/api/reports/listing/{seed_device.id}?platform=marketplace&price=450")
        assert resp.status_code == 200
        assert resp.json()["platform"] == "marketplace"

    def test_listing_includes_diagnostics(self, seed_device, tmp_db):
        """Listing should include battery health when diagnostics exist in DB."""
        tmp_db.save_diagnostic(seed_device.id, DiagnosticResult(
            battery=BatteryInfo(health_percent=92, cycle_count=150),
            storage=StorageInfo(total_gb=128, used_gb=64),
        ))
        tmp_db.save_verification(seed_device.id, VerificationResult(
            blacklist_status="clean", fmi_status="off", carrier="T-Mobile",
        ))
        resp = client.get(f"/api/reports/listing/{seed_device.id}?platform=ebay&price=500")
        assert resp.status_code == 200
        desc = resp.json()["description"]
        assert "92" in desc  # battery health
        assert "clean" in desc  # blacklist
        assert "128" in desc  # storage

    def test_listing_404(self):
        resp = client.get("/api/reports/listing/9999")
        assert resp.status_code == 404

    def test_export_csv(self, seed_device):
        resp = client.get("/api/reports/export/csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "sell_price" in resp.text  # verify the fix from item 5
        assert "DNPXXXXXXXX" in resp.text

    def test_export_json(self, seed_device):
        resp = client.get("/api/reports/export/json")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["serial"] == "DNPXXXXXXXX"

    def test_export_csv_empty(self):
        resp = client.get("/api/reports/export/csv")
        assert resp.status_code == 200
        # Just header row
        lines = resp.text.strip().split("\n")
        assert len(lines) == 1

    @patch("app.api.reports.generate_pdf", return_value=b"%PDF-1.4 fake")
    def test_pdf_report(self, _mock, seed_device):
        resp = client.get(f"/api/reports/pdf/{seed_device.id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    def test_pdf_report_404(self):
        resp = client.get("/api/reports/pdf/9999")
        assert resp.status_code == 404


# ===========================================================================
# Health endpoint
# ===========================================================================

class TestHealthAPI:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
