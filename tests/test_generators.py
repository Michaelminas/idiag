"""Tests for QR, listing, and export generators."""

import json

from app.models.device import DeviceRecord
from app.models.diagnostic import BatteryInfo, DiagnosticResult, StorageInfo
from app.models.verification import VerificationResult
from app.services.export_service import export_devices_csv, export_devices_json
from app.services.listing_generator import generate_listing


class TestListingGenerator:
    def test_ebay_listing(self):
        device = DeviceRecord(udid="u1", model="iPhone 13 Pro", grade="B+",
                              ios_version="17.4")
        diag = DiagnosticResult(
            battery=BatteryInfo(health_percent=89.0),
            storage=StorageInfo(total_gb=256.0),
        )
        verif = VerificationResult(blacklist_status="clean", fmi_status="off",
                                   carrier="T-Mobile", carrier_locked=False)
        listing = generate_listing(device, "ebay", diag, verif, price=520)
        assert "iPhone 13 Pro" in listing.title
        assert "89" in listing.description
        assert "clean" in listing.description

    def test_marketplace_listing(self):
        device = DeviceRecord(udid="u1", model="iPhone 12", grade="A")
        listing = generate_listing(device, "marketplace", price=400)
        assert "$400" in listing.description
        assert listing.platform == "marketplace"


class TestExportService:
    def test_csv_export(self):
        devices = [
            DeviceRecord(udid="u1", model="iPhone 13", serial="SN1"),
            DeviceRecord(udid="u2", model="iPhone 14", serial="SN2"),
        ]
        csv_str = export_devices_csv(devices)
        assert "udid" in csv_str  # header
        assert "iPhone 13" in csv_str
        assert "iPhone 14" in csv_str
        lines = csv_str.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    def test_json_export(self):
        devices = [DeviceRecord(udid="u1", model="iPhone 13")]
        json_str = export_devices_json(devices)
        data = json.loads(json_str)
        assert len(data) == 1
        assert data[0]["model"] == "iPhone 13"

    def test_empty_export(self):
        assert "udid" in export_devices_csv([])
        assert json.loads(export_devices_json([])) == []
