# iDiag Deployment Guide — Windows to Bootable USB

How to go from your Windows desktop + blank USB drive to a working iDiag laptop.

---

## What You're Building

A bootable Ubuntu 24.04 USB drive that you plug into any laptop, boot from it, plug in an iPhone, and get instant diagnostics. Nothing installs on the laptop — everything runs from the USB.

## What You Need

| Item | Notes |
|------|-------|
| Windows 10/11 PC | Your build machine |
| USB drive | 32GB minimum (64GB if you'll cache IPSW firmware files) |
| Target laptop | Any x86_64 laptop with USB ports (the machine you'll boot from USB) |
| Internet connection | For downloading Ubuntu ISO and packages during setup |
| ~1 hour | For the full process, first time |

---

## Step 1: Download Ubuntu 24.04 Desktop ISO

Download the official ISO from Ubuntu's website:

```
https://ubuntu.com/download/desktop
```

Get the **Ubuntu 24.04.x LTS** desktop image (~6GB). Save it somewhere you'll find it, e.g. `D:\Downloads\ubuntu-24.04.2-desktop-amd64.iso`.

---

## Step 2: Flash Ubuntu to USB with Rufus

### 2a. Download Rufus

Download Rufus (free, portable — no install needed):

```
https://rufus.ie/
```

Get the latest portable version (e.g. `rufus-4.x.exe`).

### 2b. Plug in your USB drive

Plug your blank USB into your Windows PC. **Back up anything on it — it will be completely erased.**

### 2c. Flash the ISO

1. Run `rufus-4.x.exe`
2. **Device** — select your USB drive (double-check the drive letter and size)
3. **Boot selection** — click SELECT, browse to the Ubuntu ISO you downloaded
4. **Partition scheme** — GPT (for UEFI boot, which is what modern laptops use)
5. **Target system** — UEFI (non CSM)
6. **Persistent partition size** — drag the slider to allocate space for persistence:
   - **16GB minimum** — enough for iDiag + dependencies
   - **Use all remaining space** if you have a 64GB+ drive (leaves room for IPSW firmware cache)
7. Leave everything else default
8. Click **START**
9. If prompted for write mode, select **Write in ISO Image mode (Recommended)**
10. Confirm the warning about erasing the USB
11. Wait for it to finish (~5-10 minutes)

**Why persistence matters:** Without it, the live USB resets to a blank slate every reboot. With persistence, your installed packages, iDiag app, database, and config survive reboots.

---

## Step 3: Copy iDiag Source to USB

While still on Windows, the USB drive should now show up as a drive in File Explorer (the EFI/boot partition). However, the persistent casper partition isn't directly accessible from Windows.

Instead, we'll copy the project files onto the USB's accessible FAT32 partition as a transfer mechanism:

1. Open File Explorer, find the USB drive
2. Create a folder on it called `idiag-source`
3. Copy the entire iDiag project folder into it — specifically these folders/files:
   ```
   idiag-source/
   ├── app/           (entire folder)
   ├── data/          (entire folder)
   ├── scripts/       (entire folder)
   ├── requirements.txt
   └── pyproject.toml
   ```
4. Skip copying: `.git/`, `__pycache__/`, `tests/`, `build/`, `.venv/`, any `.pyc` files

Alternatively, if your project is on GitHub, you can skip this step and `git clone` it directly from the live USB once you have internet.

---

## Step 4: Boot the USB on Your Target Laptop

1. Plug the USB into the target laptop
2. Power on (or restart) the laptop
3. **Enter the boot menu:**
   - Rapidly tap the boot key during startup. Common keys by manufacturer:

   | Brand | Boot Menu Key |
   |-------|--------------|
   | Dell | F12 |
   | HP | F9 or Esc |
   | Lenovo | F12 or Fn+F12 |
   | ASUS | F8 or Esc |
   | Acer | F12 |
   | Toshiba | F12 |
   | Microsoft Surface | Volume Down (hold while pressing Power) |

4. Select the USB drive from the boot menu (it may show as "UEFI: [USB brand name]")
5. When the GRUB menu appears, select **Try Ubuntu** (or **Ubuntu**, not "Install Ubuntu")
6. Ubuntu desktop loads — you're now running Linux from USB

**If you don't see the USB in boot menu:** Enter BIOS setup (usually F2 or Del), go to Boot settings, and:
- Disable Secure Boot
- Enable USB boot
- Set USB as first boot priority
- Save and restart

---

## Step 5: Set Up iDiag on the Live USB

Open a Terminal (Ctrl+Alt+T or search for "Terminal" in the app menu).

### 5a. Copy or clone the project

**If you copied files to USB in Step 3:**

```bash
# Find where Ubuntu mounted the USB's FAT32 partition
ls /media/ubuntu/    # or /media/$USER/

# You should see a partition with your idiag-source folder
# Copy it to home directory
cp -r /media/ubuntu/*/idiag-source ~/idiag
```

**If you're cloning from git instead:**

```bash
cd ~
git clone <your-repo-url> idiag
```

### 5b. Install system dependencies

```bash
sudo apt update

sudo apt install -y \
    python3-pip \
    python3-venv \
    usbmuxd \
    libimobiledevice-utils \
    libimobiledevice6 \
    libusbmuxd-tools \
    ideviceinstaller \
    sqlite3 \
    libpango-1.0-0 \
    libharfbuzz0b \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev
```

This installs the iPhone USB communication stack (usbmuxd + libimobiledevice) and system libraries needed by WeasyPrint (for PDF certificate generation).

### 5c. Install Python dependencies

```bash
cd ~/idiag

# Create a virtual environment (keeps things clean)
python3 -m venv .venv
source .venv/bin/activate

# Install all Python packages
pip install -r requirements.txt
```

This installs FastAPI, pymobiledevice3, pywebview, and everything else iDiag needs. Takes 2-5 minutes.

### 5d. Create data directories

```bash
mkdir -p db data/ipsw_cache data/shsh_blobs data/certificates data/photos
```

### 5e. Test that it starts

```bash
cd ~/idiag
source .venv/bin/activate
python3 -m app.main
```

iDiag should start and open a native window (via pywebview). If pywebview can't open a window, it falls back to browser-only mode — open `http://127.0.0.1:18765` in Firefox.

**Verify it's working:**

```bash
# In a second terminal (Ctrl+Alt+T):
curl http://127.0.0.1:18765/health
# Expected: {"status":"ok","version":"0.1.0"}
```

Press Ctrl+C to stop the server for now.

---

## Step 6: Configure Auto-Start (Optional)

So iDiag launches automatically when you boot the USB:

```bash
mkdir -p ~/.config/autostart

cat > ~/.config/autostart/idiag.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=iDiag
Comment=iPhone Diagnostic Tool
Exec=bash -c "cd ~/idiag && source .venv/bin/activate && python3 -m app.main"
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
EOF
```

Now every time you boot this USB and log in, iDiag starts automatically.

---

## Step 7: Set Up iPhone USB Access

Make sure usbmuxd (the iPhone USB multiplexer daemon) is running:

```bash
# Start usbmuxd
sudo systemctl start usbmuxd
sudo systemctl enable usbmuxd

# Allow non-root USB access for iPhones
sudo tee /etc/udev/rules.d/39-libimobiledevice.rules << 'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="05ac", MODE="0666"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

Now plug in an iPhone via USB cable. When the phone asks "Trust This Computer?" — tap **Trust** and enter the passcode.

**Test device detection:**

```bash
# Should show your iPhone
idevice_id -l

# Or via the iDiag API (if server is running):
curl http://127.0.0.1:18765/api/devices/connected
```

---

## Step 8: Configure SICKW API (Optional)

iDiag uses SICKW.COM for IMEI/carrier/FMI/blacklist checks ($0.13 per lookup).

```bash
# Get an API key at https://sickw.com/ then:
echo 'export SICKW_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

Without this, IMEI verification returns "not configured" — everything else works fine.

---

## Step 9: Add Bypass Tool Binaries (Optional — Sprint 5)

These are third-party binaries for advanced recovery. They aren't required for normal diagnostics.

### checkra1n (jailbreak for A5-A11 devices)

```bash
# Download from https://checkra.in/ — get the Linux CLI version
sudo wget -O /usr/local/bin/checkra1n "https://assets.checkra.in/downloads/linux/cli/x86_64/dac9968939ea6e6bfbdedeb41d7e2579c4711dc2c5083f91dced66571f233f1a/checkra1n"
sudo chmod +x /usr/local/bin/checkra1n
```

### futurerestore (custom firmware restore)

```bash
# Download latest from https://github.com/futurerestore/futurerestore/releases
# Get the linux-x86_64 build
sudo wget -O /usr/local/bin/futurerestore "<release-url>"
sudo chmod +x /usr/local/bin/futurerestore
```

### tsschecker (SHSH blob saving)

```bash
# Download from https://github.com/1Conan/tsschecker/releases
sudo wget -O /usr/local/bin/tsschecker "<release-url>"
sudo chmod +x /usr/local/bin/tsschecker
```

### Verify tool detection

```bash
curl http://127.0.0.1:18765/api/tools/availability
# {"checkra1n": true, "broque": false, "ssh_ramdisk": false, "futurerestore": true}
```

---

## Done — Daily Usage

### Starting up

1. Plug USB into laptop, boot from it (F12 at startup, select USB)
2. Ubuntu boots, iDiag auto-starts (or run manually: `cd ~/idiag && source .venv/bin/activate && python3 -m app.main`)
3. Plug in iPhone, tap "Trust This Computer" if first time
4. Dashboard shows device diagnostics automatically

### Pre-purchase check (under 60 seconds)

1. Connect iPhone
2. Dashboard auto-loads: battery health, parts originality, crash analysis, verification status
3. Check the grade (A/B/C/D) and market price estimate
4. Click "Save to Inventory" and enter buy price

### Post-purchase processing

1. Firmware tab — restore/wipe as needed, get PDF erasure certificate
2. Photos tab — capture device photos
3. Reports tab — generate listing template
4. Sales tab — track the sale

### Syslog debugging

Open the Syslog tab while a device is connected for real-time iOS log streaming with process/level/keyword filters.

---

## Backing Up Your Data

Your inventory database and all data live on the USB's persistent partition. To back up:

```bash
# Copy database to an external drive or network share
cp ~/idiag/db/idiag.db /media/ubuntu/BACKUP/idiag-$(date +%Y%m%d).db

# Or export via API
curl http://127.0.0.1:18765/api/inventory/export?format=csv -o inventory.csv
curl http://127.0.0.1:18765/api/inventory/export?format=json -o inventory.json
```

---

## Troubleshooting

### USB won't boot

| Problem | Fix |
|---------|-----|
| USB not in boot menu | Enter BIOS (F2/Del), disable Secure Boot, enable USB boot |
| Boots to Windows instead | Tap F12 faster, or set USB as first boot device in BIOS |
| GRUB error | Re-flash with Rufus, make sure you selected GPT + UEFI |
| Black screen after selecting Ubuntu | Try a different USB port (use USB 2.0 if USB 3.0 fails) |

### Persistence not working (changes lost on reboot)

- Rufus must have **persistent partition** enabled during flashing (Step 2c, item 6)
- If you skipped this, you need to re-flash the USB with persistence enabled
- Verify: after rebooting, check if `~/idiag` still exists

### iPhone not detected

```bash
# Is usbmuxd running?
sudo systemctl restart usbmuxd

# Does Linux see the USB device?
lsusb | grep Apple
# Should show: Apple, Inc. iPhone

# Try unplugging and re-plugging. Tap "Trust" on the phone.

# Check iDiag
curl http://127.0.0.1:18765/api/devices/connected
```

### "Trust This Computer" doesn't appear

1. Unplug and re-plug the cable
2. `sudo systemctl restart usbmuxd`
3. Try a different USB port
4. Try a different cable (some charge-only cables don't support data)

### iDiag won't start

```bash
cd ~/idiag
source .venv/bin/activate

# Check for import errors
python3 -c "from app.main import app; print('OK')"

# Run with visible errors
python3 -m app.main
# Read the traceback — usually a missing dependency

# Reinstall deps if needed
pip install -r requirements.txt
```

### pywebview window doesn't open

```bash
# Install GTK backend for pywebview
sudo apt install -y gir1.2-webkit2-4.1 libgirepository1.0-dev

# If still fails, iDiag falls back to browser mode automatically.
# Just open http://127.0.0.1:18765 in Firefox.
```

---

## Advanced: Building a Custom ISO (Automated)

If you want to create a pre-built ISO with everything baked in (no manual setup on first boot), you can use the included build script. This requires a Linux environment.

### From Windows via WSL2

```powershell
# In Windows PowerShell (admin):
wsl --install -d Ubuntu-24.04

# After WSL restarts and you set up your username/password:
```

```bash
# Inside WSL2:
cd /mnt/d/Project\ -\ idiag

# Run the build script (requires sudo)
sudo bash scripts/build_usb.sh

# Output: build/idiag-live.iso
```

Then flash `build/idiag-live.iso` to USB using Rufus (same as Step 2, but select this ISO instead of the Ubuntu one). This ISO has all dependencies pre-installed, auto-starts iDiag on login, and uses the `idiag:idiag` user account.

**Note:** WSL2 builds may have issues with `live-build`'s chroot operations. If the build fails, use a full Ubuntu VM (VirtualBox or Hyper-V) instead.

### From a VirtualBox VM

1. Install VirtualBox on Windows: https://www.virtualbox.org/
2. Create an Ubuntu 24.04 VM (2+ CPU cores, 4GB+ RAM, 40GB+ disk)
3. Share the iDiag project folder with the VM (Shared Folders in VM settings)
4. Inside the VM: `sudo bash /media/sf_idiag/scripts/build_usb.sh`
5. Copy the resulting ISO back to Windows
6. Flash with Rufus

---

## Quick Reference

| What | Where |
|------|-------|
| iDiag app | `~/idiag/` (manual) or `/opt/idiag/` (custom ISO) |
| Database | `~/idiag/db/idiag.db` |
| IPSW cache | `~/idiag/data/ipsw_cache/` |
| Crash patterns | `~/idiag/data/crash_patterns.json` |
| Config | `~/idiag/app/config.py` |
| Logs | Terminal output (stdout) |
| Web UI | `http://127.0.0.1:18765` |
| Health check | `http://127.0.0.1:18765/health` |
| API docs | `http://127.0.0.1:18765/docs` (FastAPI auto-generated) |
