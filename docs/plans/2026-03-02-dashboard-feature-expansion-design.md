# Dashboard Feature Expansion Design

**Date:** 2026-03-02
**Goal:** Show all iDiag features on the dashboard, even when unavailable for the connected device.

## Current State

The dashboard has 4 tabs (Diagnostics, History, Pricing, Syslog) with 6 cards on the Diagnostics tab. ~12 features with full API backends have no UI representation.

## Design

### Tab Layout (8 tabs)

```
Diagnostics | Firmware | Tools | Photos | Reports | History | Pricing | Syslog
```

### Firmware Tab

| Card | Content | Disabled When |
|------|---------|---------------|
| Signed Versions | Table of currently signed iOS versions for this model | No device connected |
| IPSW Cache | List cached firmware files + download button | Never (always usable) |
| SHSH Blobs | Save blob button + list saved blobs for device | No device connected |
| Device Mode | Current mode indicator (Normal/Recovery/DFU) + Enter DFU / Enter Recovery / Exit Recovery buttons | No device connected |
| Restore | Select IPSW + restore button, WebSocket progress bar | No cached IPSW or no device |
| Wipe & Certificate | Factory reset button + download erasure PDF link | No device connected |

### Tools Tab

| Card | Content | Disabled When |
|------|---------|---------------|
| checkra1n | Run jailbreak button + status | Tool not installed OR device not checkm8-compatible |
| Broque Ramdisk | Run bypass button + status | Tool not installed |
| SSH Ramdisk | Boot ramdisk + extract data buttons | Tool not installed |
| FutureRestore | Select SHSH blob + IPSW, run restore | Tool not installed OR no saved blobs |
| Cable Check | Run test button + quality results | No device connected |

### Photos Tab

| Card | Content | Disabled When |
|------|---------|---------------|
| Upload | File input + label selector (front/back/screen/damage) | Device not saved to inventory |
| Gallery | Grid of uploaded photos with delete buttons | Device not saved to inventory |

### Reports Tab

| Card | Content | Disabled When |
|------|---------|---------------|
| Generate Report | PDF download + HTML preview buttons | Device not saved to inventory |
| QR Code | Generate + display QR code image | Device not saved to inventory |
| Listing Generator | Generate marketplace listing text with copy button | Device not saved to inventory |
| Export | CSV + JSON bulk export buttons | Never (always usable) |

### Disabled State Pattern

Cards that can't be used get:
- CSS: `opacity-50` on card body content, normal opacity on header
- `pointer-events-none` on interactive elements
- Grey banner below card header: reason text (e.g. "Requires checkm8-compatible device", "Tool not installed", "Save to inventory first")
- Banner style: `bg-gray-100 text-gray-500 text-xs px-3 py-1`

### Data Flow

On device connect (loadSnapshot), additionally fetch:
1. `GET /api/tools/availability` — check which tools are installed
2. `GET /api/firmware/signed/{model}` — signed iOS versions
3. `GET /api/firmware/shsh?ecid={ecid}` — saved blobs
4. `GET /api/firmware/cache` — cached IPSWs
5. `GET /api/firmware/mode/{udid}` — device mode
6. Check `inventoryDeviceId` — determines if photos/reports are available

Tool availability + device capabilities (checkm8 chip) determine greyed-out state for Tools tab cards.

### Implementation Approach

Single file change: `app/templates/index.html`. All APIs already exist. Work is purely frontend:
1. Add 4 new tab buttons to the tab bar
2. Add 4 new tab panels with card HTML
3. Add JS functions to fetch data and render each new panel
4. Add disabled-state logic based on availability checks
5. Update `switchTab()` to handle 8 tabs
6. Update `loadSnapshot()` to fetch additional data for new tabs
