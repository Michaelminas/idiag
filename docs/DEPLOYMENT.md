# iDiag Deployment Guide

Step-by-step guide to build, deploy, and run iDiag on a bootable Linux USB drive.

---

## Overview

iDiag runs from a bootable Ubuntu 24.04 USB drive. You plug the USB into any laptop, boot from it, connect an iPhone via USB cable, and get instant diagnostics. No installation needed on the host machine.

**What you'll need:**
- A Linux machine (or VM) with sudo access for building the ISO
- A USB drive (16GB+ recommended, 32GB ideal)
- The iDiag source code (this repo)

---

## Part 1: Building the USB Image

### Prerequisites

The build script requires a Debian/Ubuntu system. You can use:
- An existing Ubuntu desktop/server
- A cloud VM (e.g., DigitalOcean, AWS EC2)
- WSL2 on Windows (may work but untested)

### Build Steps

```bash
# 1. Clone the repo (or copy it to your build machine)
git clone <your-repo-url> idiag
cd idiag

# 2. Run the build script (requires root)
sudo bash scripts/build_usb.sh

# This will:
# - Install build dependencies (live-build, debootstrap, etc.)
# - Create an Ubuntu 24.04 minimal live system
# - Pre-install Python 3.11, usbmuxd, libimobiledevice
# - Install all pip dependencies (FastAPI, pymobiledevice3, etc.)
# - Copy the iDiag application to /opt/idiag
# - Set up auto-start on login
# - Output: build/idiag-live.iso
```

Build takes 10-30 minutes depending on internet speed.

### Write ISO to USB

```bash
# Find your USB device (be VERY careful to identify the correct drive)
lsblk

# Write the ISO (replace /dev/sdX with your actual USB device)
sudo dd if=build/idiag-live.iso of=/dev/sdX bs=4M status=progress oflag=sync

# Sync to ensure all data is written
sync
```

**WARNING:** `dd` will overwrite the entire target device. Triple-check that `/dev/sdX` is your USB drive and NOT your system disk.

---

## Part 2: Adding Bypass Tool Binaries

The USB image includes the iDiag Python application and all dependencies, but the bypass tool binaries (checkra1n, futurerestore, tsschecker) must be added manually because they are not distributable via package managers.

### checkra1n (Jailbreak — A5-A11 devices)

```bash
# Boot from the USB, open a terminal, then:
# Download checkra1n Linux CLI from https://checkra.in/
wget -O /usr/local/bin/checkra1n https://assets.checkra.in/downloads/linux/cli/x86_64/dac9968939ea6e6bfbdedeb41d7e2579c4711dc2c5083f91dced66571f233f1a/checkra1n
chmod +x /usr/local/bin/checkra1n
```

### futurerestore (SHSH blob restore)

```bash
# Download the latest release from https://github.com/futurerestore/futurerestore/releases
wget -O /usr/local/bin/futurerestore <release-url>
chmod +x /usr/local/bin/futurerestore
```

### tsschecker (SHSH blob saving)

```bash
# Download from https://github.com/1Conan/tsschecker/releases
wget -O /usr/local/bin/tsschecker <release-url>
chmod +x /usr/local/bin/tsschecker
```

### Broque Ramdisk (iCloud bypass — A9-A11)

```bash
# Clone the repo into the expected location
git clone https://github.com/user/Broque-Ramdisk /opt/idiag/tools/Broque-Ramdisk
```

### Verify tool installation

After adding binaries, verify they're detected:

```bash
curl http://127.0.0.1:18765/api/tools/availability
# Should return: {"checkra1n": true, "broque": true, "ssh_ramdisk": false, "futurerestore": true}
```

---

## Part 3: First Boot

### Boot from USB

1. Plug the USB into your target laptop
2. Enter BIOS/boot menu (usually F12, F2, or Del during startup)
3. Select the USB drive as boot device
4. Ubuntu will boot into a desktop environment
5. iDiag auto-starts and opens a browser window

### Manual Start (if auto-start doesn't trigger)

```bash
cd /opt/idiag
python3 -m app.main
# Opens at http://127.0.0.1:18765
```

### Verify Installation

```bash
# Check iDiag is running
curl http://127.0.0.1:18765/health
# Expected: {"status": "ok", "version": "0.1.0"}

# Check usbmuxd is running (required for iPhone communication)
systemctl status usbmuxd

# If not running:
sudo systemctl start usbmuxd
```

---

## Part 4: SICKW API Configuration

iDiag uses SICKW.COM for IMEI/carrier/FMI/blacklist verification ($0.13 per check).

```bash
# Set your API key (get one at https://sickw.com/)
export SICKW_API_KEY="your-api-key-here"

# To make it persistent across reboots:
echo 'export SICKW_API_KEY="your-api-key-here"' >> /home/idiag/.bashrc
```

Without the API key, verification features return "not configured" but all other features work.

---

## Part 5: Day-to-Day Usage

### Pre-Purchase Check (< 60 seconds)

1. Connect iPhone via USB cable
2. Device auto-detected — dashboard loads diagnostics automatically
3. Review: battery health, parts originality, crash analysis, verification
4. Check the grade (A/B/C/D) and market pricing
5. Click "Save to Inventory" with buy price

### Post-Purchase Processing

1. Run diagnostics again to confirm condition
2. Use Firmware tab for restore/wipe if needed
3. Download erasure certificate (PDF) after wipe
4. Take photos (Photos tab)
5. Generate listing template (Reports tab)
6. Track sale (Sales tab)

### Syslog Debugging

1. Open the Syslog tab while device is connected
2. Real-time log streaming with process/level/keyword filters
3. Useful for diagnosing intermittent issues or verifying crash patterns

### Advanced Recovery (Sprint 5 tools)

These require the device in DFU mode:

1. **checkra1n**: Jailbreak for diagnostic access (A5-A11, iOS 12-14)
2. **Broque Ramdisk**: iCloud bypass for activation-locked devices (A9-A11)
3. **FutureRestore**: Downgrade iOS using saved SHSH blobs
4. **SSH Ramdisk**: Extract data from passcode-locked devices

Check tool availability: `GET /api/tools/availability`

---

## Part 6: Data & Backup

### Database Location

```
/opt/idiag/db/idiag.db    # SQLite database (all inventory, diagnostics, sales)
```

### Backup

```bash
# Copy database to external storage
cp /opt/idiag/db/idiag.db /media/backup/idiag-$(date +%Y%m%d).db
```

### Export

```bash
# CSV export of inventory
curl http://127.0.0.1:18765/api/inventory/export?format=csv -o inventory.csv

# JSON export
curl http://127.0.0.1:18765/api/inventory/export?format=json -o inventory.json
```

---

## Troubleshooting

### Device not detected

```bash
# Check usbmuxd is running
sudo systemctl restart usbmuxd

# Check USB connection
lsusb | grep Apple
# Should show: Apple, Inc. iPhone

# Check iDiag device list
curl http://127.0.0.1:18765/api/devices/connected
```

### "Trust This Computer" prompt

When connecting an iPhone for the first time, you must tap "Trust" on the device. If the prompt doesn't appear:
1. Disconnect and reconnect the cable
2. Restart usbmuxd: `sudo systemctl restart usbmuxd`
3. Try a different USB port

### pymobiledevice3 errors

```bash
# Update to latest version
pip3 install --upgrade pymobiledevice3

# Some operations require root
sudo python3 -m app.main
```

### Poor cable detection

If cable check reports "Unknown" connection type, the device may not expose USB speed properties. This is informational only and doesn't affect diagnostics.

---

## Architecture Reference

```
/opt/idiag/
├── app/
│   ├── main.py              # Entry point — FastAPI + pywebview
│   ├── config.py             # Settings (host, port, paths, API keys)
│   ├── api/                  # REST endpoints (50 routes + WebSocket)
│   ├── models/               # Pydantic data models
│   ├── services/             # Business logic (diagnostics, firmware, bypass, etc.)
│   ├── templates/            # Jinja2 HTML templates
│   ├── static/               # CSS, JS (Tailwind bundled locally)
│   └── utils/                # Resilience utilities
├── data/                     # JSON reference files (crash patterns, device capabilities)
├── db/                       # SQLite database
├── scripts/                  # Build scripts
├── tests/                    # 352 tests
└── pyproject.toml            # Dependencies
```

### Key Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Dashboard UI |
| `GET /health` | Health check |
| `GET /api/devices/connected` | List connected iPhones |
| `GET /api/diagnostics/snapshot/{udid}` | Full device diagnostic snapshot |
| `POST /api/firmware/restore/{udid}` | Firmware restore |
| `POST /api/firmware/wipe/{udid}` | Factory reset + certificate |
| `GET /api/tools/availability` | Check bypass tool status |
| `WS /ws` | Device connect/disconnect events |
| `WS /ws/syslog/{udid}` | Real-time syslog streaming |
