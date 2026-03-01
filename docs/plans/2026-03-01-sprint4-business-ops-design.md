# Sprint 4: Business Operations & Reports

## Date: 2026-03-01
## Status: Approved

---

## Scope

6 features building on Sprint 1's inventory/diagnostics foundation:

1. **Photo station** — file upload, stored on disk, referenced in DB
2. **PDF health report** — WeasyPrint HTML->PDF with full device summary
3. **Listing template generator** — eBay + Facebook Marketplace formats
4. **Sales tracking** — buy/sell/profit/fees/days-in-inventory
5. **QR code labels** — link to local device diagnostic page
6. **Bulk CSV/JSON export** — inventory data as downloadable files

## New Files

| File | Purpose |
|------|---------|
| `app/models/sales.py` | SalesRecord, PhotoRecord, ListingTemplate models |
| `app/services/report_generator.py` | WeasyPrint PDF generation |
| `app/services/photo_manager.py` | Photo save/list/delete (files on disk) |
| `app/services/listing_generator.py` | eBay + Marketplace template generation |
| `app/services/qr_generator.py` | QR code generation (qrcode lib) |
| `app/services/export_service.py` | CSV/JSON bulk export |
| `app/api/reports.py` | PDF + QR + export endpoints |
| `app/api/photos.py` | Photo upload/list/delete endpoints |
| `app/api/sales.py` | Sales CRUD + listing generation |

## DB Schema Additions

```sql
CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    sell_price REAL,
    platform TEXT,
    fees REAL DEFAULT 0,
    sold_at TIMESTAMP,
    days_in_inventory INTEGER,
    profit REAL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    label TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Design Decisions

- **Photos**: `data/photos/{udid}/{timestamp}_{label}.jpg`, paths in DB
- **PDF**: WeasyPrint renders HTML template -> PDF (diagnostics, grade, verification, photos)
- **QR**: `qrcode` library generates PNG, encodes `http://127.0.0.1:18765/device/{udid}`
- **Listings**: Jinja2 templates produce copy-paste text for eBay + Marketplace
- **Export**: CSV via stdlib `csv`, JSON via `json` — streamed as file downloads
- **Sales profit**: auto-computed `sell_price - buy_price - fees`
- **Marketplaces**: eBay + Facebook Marketplace only

## New Dependencies

| Package | Purpose |
|---------|---------|
| WeasyPrint | PDF generation |
| qrcode[pil] | QR code generation |
