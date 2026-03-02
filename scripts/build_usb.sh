#!/usr/bin/env bash
# build_usb.sh — Build a reproducible Ubuntu 24.04 live USB image with iDiag pre-installed.
#
# Requirements: Run on a Debian/Ubuntu host with sudo access.
# Usage: sudo bash scripts/build_usb.sh [output_dir]
#
# Output: idiag-live.iso in the output directory (default: ./build/)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${1:-$PROJECT_ROOT/build}"
WORK_DIR="$OUTPUT_DIR/work"
IMAGE_NAME="idiag-live"

echo "=== iDiag Live USB Builder ==="
echo "Project root: $PROJECT_ROOT"
echo "Output dir:   $OUTPUT_DIR"

# ── Prerequisites ──────────────────────────────────────────────────────

check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "ERROR: This script must be run as root (sudo)"
        exit 1
    fi
}

check_deps() {
    local missing=()
    for cmd in debootstrap lb mksquashfs xorriso; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Installing missing build dependencies: ${missing[*]}"
        apt-get update -qq
        apt-get install -y -qq live-build debootstrap squashfs-tools xorriso
    fi
}

check_root
check_deps

# ── Configure live-build ───────────────────────────────────────────────

mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

lb config \
    --distribution noble \
    --architectures amd64 \
    --binary-images iso-hybrid \
    --bootloaders syslinux,grub-efi \
    --debian-installer false \
    --memtest none \
    --iso-application "iDiag" \
    --iso-volume "iDiag Live" \
    2>/dev/null || true

# ── Package lists ──────────────────────────────────────────────────────

mkdir -p config/package-lists

cat > config/package-lists/idiag.list.chroot <<'PACKAGES'
python3
python3-pip
python3-venv
usbmuxd
libimobiledevice-utils
libimobiledevice6
libusbmuxd-tools
ideviceinstaller
git
wget
curl
openssh-client
sqlite3
libpango-1.0-0
libharfbuzz0b
libffi-dev
libgdk-pixbuf2.0-0
libcairo2
libgirepository1.0-dev
gir1.2-webkit2-4.1
PACKAGES

# ── Custom hooks ───────────────────────────────────────────────────────

mkdir -p config/hooks/normal

cat > config/hooks/normal/0100-install-idiag.hook.chroot <<'HOOK'
#!/bin/bash
set -e

# Create idiag user
useradd -m -s /bin/bash idiag || true
echo "idiag:idiag" | chpasswd

# Install Python packages
pip3 install --break-system-packages \
    fastapi uvicorn[standard] pymobiledevice3 pywebview httpx \
    pydantic jinja2 weasyprint "qrcode[pil]"

# udev rules for iPhone hotplug
cat > /etc/udev/rules.d/39-libimobiledevice.rules <<'UDEV'
# Apple iOS devices — allow non-root access
SUBSYSTEM=="usb", ATTR{idVendor}=="05ac", MODE="0666"
UDEV

# Auto-start iDiag on login
mkdir -p /home/idiag/.config/autostart
cat > /home/idiag/.config/autostart/idiag.desktop <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=iDiag
Exec=/opt/idiag/start.sh
Terminal=false
Hidden=false
DESKTOP
chown -R idiag:idiag /home/idiag/.config

echo "NOTE: checkra1n and futurerestore binaries must be added to /usr/local/bin/ manually"
HOOK

chmod +x config/hooks/normal/0100-install-idiag.hook.chroot

# ── Copy application files ─────────────────────────────────────────────

mkdir -p config/includes.chroot/opt/idiag

# Copy project files (excluding dev files)
rsync -a \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='.venv' \
    --exclude='build' \
    --exclude='*.pyc' \
    --exclude='node_modules' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    "$PROJECT_ROOT/" config/includes.chroot/opt/idiag/

# Create start script
cat > config/includes.chroot/opt/idiag/start.sh <<'START'
#!/bin/bash
cd /opt/idiag
exec python3 -m app.main
START
chmod +x config/includes.chroot/opt/idiag/start.sh

# ── Build ──────────────────────────────────────────────────────────────

echo ""
echo "Building live image (this may take 10-30 minutes)..."
lb build 2>&1 | tee "$OUTPUT_DIR/build.log"

# ── Output ─────────────────────────────────────────────────────────────

ISO_FILE=$(find . -maxdepth 1 -name "*.iso" -type f | head -1)
if [[ -n "$ISO_FILE" ]]; then
    mv "$ISO_FILE" "$OUTPUT_DIR/$IMAGE_NAME.iso"
    echo ""
    echo "=== Build complete ==="
    echo "ISO: $OUTPUT_DIR/$IMAGE_NAME.iso"
    echo "Size: $(du -h "$OUTPUT_DIR/$IMAGE_NAME.iso" | cut -f1)"
    echo ""
    echo "Write to USB:"
    echo "  sudo dd if=$OUTPUT_DIR/$IMAGE_NAME.iso of=/dev/sdX bs=4M status=progress oflag=sync"
else
    echo "ERROR: No ISO file found. Check $OUTPUT_DIR/build.log"
    exit 1
fi
