"""Bulk CSV and JSON export service."""

import csv
import json
from io import StringIO

from app.models.device import DeviceRecord


def export_devices_csv(devices: list[DeviceRecord]) -> str:
    """Export device list to CSV string."""
    output = StringIO()
    fields = ["id", "udid", "serial", "imei", "model", "ios_version",
              "grade", "status", "buy_price", "sell_price", "notes", "created_at", "updated_at"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for d in devices:
        writer.writerow(d.model_dump(include=set(fields)))
    return output.getvalue()


def export_devices_json(devices: list[DeviceRecord]) -> str:
    """Export device list to JSON string."""
    data = [d.model_dump(mode="json") for d in devices]
    return json.dumps(data, indent=2, default=str)
