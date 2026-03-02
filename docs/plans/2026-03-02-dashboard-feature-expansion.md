# Dashboard Feature Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Firmware, Tools, Photos, and Reports tabs to the iDiag dashboard so all features are visible, with greyed-out disabled states when unavailable.

**Architecture:** Pure frontend work — all APIs already exist. Single file edit (`app/templates/index.html`). Add 4 tab panels with cards, JS fetch/render functions, and disabled-state logic driven by tool availability checks and inventory status.

**Tech Stack:** HTML, Tailwind CSS, vanilla JS (existing stack, no build step)

---

### Task 1: Add Tab Buttons + Panel Skeletons + Disabled State CSS

**Files:**
- Modify: `app/templates/index.html:86-91` (tab bar)
- Modify: `app/templates/index.html:8-26` (styles)
- Modify: `app/templates/index.html:435-444` (switchTab function)

**Step 1: Add disabled-state CSS to `<style>` block**

After line 25 (before `</style>`), add:

```css
.card-disabled .card-body { opacity: 0.5; pointer-events: none; }
.card-disabled-reason { background: #f3f4f6; color: #6b7280; font-size: 0.75rem; padding: 4px 12px; border-radius: 4px; margin-bottom: 8px; }
```

**Step 2: Add 4 new tab buttons to the tab bar**

Replace the tab bar (lines 86-91) with 8 tabs:

```html
<div class="flex border-b border-gray-200 mb-4 bg-white rounded-t-lg shadow-sm px-2 overflow-x-auto">
    <button onclick="switchTab('diagnostics')" id="tab-diagnostics" class="tab-btn tab-active whitespace-nowrap">Diagnostics</button>
    <button onclick="switchTab('firmware')" id="tab-firmware" class="tab-btn tab-inactive whitespace-nowrap">Firmware</button>
    <button onclick="switchTab('tools')" id="tab-tools" class="tab-btn tab-inactive whitespace-nowrap">Tools</button>
    <button onclick="switchTab('photos')" id="tab-photos" class="tab-btn tab-inactive whitespace-nowrap">Photos</button>
    <button onclick="switchTab('reports')" id="tab-reports" class="tab-btn tab-inactive whitespace-nowrap">Reports</button>
    <button onclick="switchTab('history')" id="tab-history" class="tab-btn tab-inactive whitespace-nowrap">History</button>
    <button onclick="switchTab('pricing')" id="tab-pricing" class="tab-btn tab-inactive whitespace-nowrap">Pricing</button>
    <button onclick="switchTab('syslog')" id="tab-syslog" class="tab-btn tab-inactive whitespace-nowrap">Syslog</button>
</div>
```

**Step 3: Update switchTab() function**

Replace the tabs array in `switchTab()` (around line 436):

```javascript
const tabs = ['diagnostics', 'firmware', 'tools', 'photos', 'reports', 'history', 'pricing', 'syslog'];
```

Add lazy-load triggers after the existing `if (tab === 'syslog')` block:

```javascript
if (tab === 'firmware') loadFirmwareTab();
if (tab === 'tools') loadToolsTab();
if (tab === 'photos') loadPhotosTab();
if (tab === 'reports') loadReportsTab();
```

**Step 4: Add 4 empty panel divs**

After the `panel-pricing` closing `</div>` (line 235) and before the closing `</div>` of `device-dashboard`, add empty panel skeletons:

```html
<!-- Tab: Firmware -->
<div id="panel-firmware" class="hidden">
    <div class="text-gray-400 text-center py-8">Loading firmware info...</div>
</div>

<!-- Tab: Tools -->
<div id="panel-tools" class="hidden">
    <div class="text-gray-400 text-center py-8">Loading tools...</div>
</div>

<!-- Tab: Photos -->
<div id="panel-photos" class="hidden">
    <div class="text-gray-400 text-center py-8">Loading photos...</div>
</div>

<!-- Tab: Reports -->
<div id="panel-reports" class="hidden">
    <div class="text-gray-400 text-center py-8">Loading reports...</div>
</div>
```

**Step 5: Add global state variables**

After `let inventoryDeviceId = null;` (line 243), add:

```javascript
let toolAvailability = {};
let deviceCapabilities = {};
let firmwareLoaded = false;
let toolsLoaded = false;
let photosLoaded = false;
let reportsLoaded = false;
```

**Step 6: Reset state on disconnect**

In `onDeviceDisconnected()`, add resets:

```javascript
toolAvailability = {};
deviceCapabilities = {};
firmwareLoaded = false;
toolsLoaded = false;
photosLoaded = false;
reportsLoaded = false;
```

**Step 7: Verify — run the app and confirm 8 tabs appear, clicking each shows placeholder text**

```bash
cd "D:/Project - idiag"
PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Step 8: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: add tab skeleton for firmware, tools, photos, reports tabs"
```

---

### Task 2: Firmware Tab — HTML + JS

**Files:**
- Modify: `app/templates/index.html` — replace `panel-firmware` placeholder + add JS functions

**Step 1: Replace firmware panel HTML**

Replace the `panel-firmware` div content with:

```html
<!-- Tab: Firmware -->
<div id="panel-firmware" class="hidden">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <!-- Signed Versions -->
        <div class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Signed Versions</h3>
            <div id="fw-signed"><span class="text-gray-400">Connect a device to check</span></div>
        </div>

        <!-- IPSW Cache -->
        <div class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">IPSW Cache</h3>
            <div id="fw-cache"><span class="text-gray-400">Loading...</span></div>
        </div>

        <!-- SHSH Blobs -->
        <div id="fw-shsh-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">SHSH Blobs</h3>
            <div id="fw-shsh"><span class="text-gray-400">Connect a device to manage blobs</span></div>
        </div>

        <!-- Device Mode -->
        <div id="fw-mode-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Device Mode</h3>
            <div id="fw-mode"><span class="text-gray-400">Connect a device</span></div>
        </div>

        <!-- Restore -->
        <div id="fw-restore-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Restore</h3>
            <div id="fw-restore"><span class="text-gray-400">Connect a device to restore</span></div>
        </div>

        <!-- Wipe & Certificate -->
        <div id="fw-wipe-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Wipe &amp; Certificate</h3>
            <div id="fw-wipe"><span class="text-gray-400">Connect a device to wipe</span></div>
        </div>
    </div>
</div>
```

**Step 2: Add loadFirmwareTab() JS function**

Add this function in the `<script>` section (before the `// Init` comment):

```javascript
// -- Firmware Tab --

async function loadFirmwareTab() {
    if (firmwareLoaded) return;
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    const model = currentDevice && currentDevice.info ? currentDevice.info.product_type : null;

    // Always load cache (doesn't need device)
    fetchFirmwareCache();

    if (!udid || !model) {
        setCardDisabled('fw-mode-card', 'No device connected');
        setCardDisabled('fw-restore-card', 'No device connected');
        setCardDisabled('fw-wipe-card', 'No device connected');
        return;
    }

    firmwareLoaded = true;

    // Fetch signed versions
    fetchSignedVersions(model);

    // Fetch device mode
    fetchDeviceMode(udid);

    // Fetch SHSH blobs
    fetchSHSHBlobs();

    // Enable restore & wipe
    renderRestoreCard(model);
    renderWipeCard(udid);
}

function fetchSignedVersions(model) {
    el('fw-signed').innerHTML = '<div class="text-gray-400 animate-pulse">Checking...</div>';
    fetch('/api/firmware/signed/' + model)
        .then(r => r.json())
        .then(versions => {
            if (!versions || versions.length === 0) {
                el('fw-signed').innerHTML = '<div class="text-gray-400">No signed versions found</div>';
                return;
            }
            let html = '<div class="space-y-1 text-sm max-h-48 overflow-y-auto">';
            versions.forEach(v => {
                html += '<div class="flex justify-between items-center border-b py-1">'
                    + '<span>' + esc(v.version) + '</span>'
                    + '<span class="text-xs text-gray-400">' + esc(v.build_id || '') + '</span>'
                    + '<button onclick="downloadIPSW(\'' + esc(v.version) + '\',\'' + esc(v.build_id || '') + '\')" '
                    + 'class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded hover:bg-blue-200">Download</button>'
                    + '</div>';
            });
            html += '</div>';
            el('fw-signed').innerHTML = html;
        })
        .catch(() => { el('fw-signed').innerHTML = '<span class="text-red-500">Failed to fetch</span>'; });
}

function fetchFirmwareCache() {
    el('fw-cache').innerHTML = '<div class="text-gray-400 animate-pulse">Loading...</div>';
    fetch('/api/firmware/cache')
        .then(r => r.json())
        .then(entries => {
            if (!entries || entries.length === 0) {
                el('fw-cache').innerHTML = '<div class="text-gray-400">No cached IPSW files</div>';
                return;
            }
            let html = '<div class="space-y-1 text-sm max-h-48 overflow-y-auto">';
            entries.forEach(e => {
                const sizeStr = e.size_bytes ? (e.size_bytes / 1073741824).toFixed(1) + ' GB' : '?';
                html += '<div class="flex justify-between items-center border-b py-1">'
                    + '<div><span class="font-medium">' + esc(e.model) + '</span> '
                    + '<span class="text-gray-400">' + esc(e.version) + '</span></div>'
                    + '<span class="text-xs text-gray-400">' + sizeStr + '</span>'
                    + '<button onclick="evictIPSW(\'' + esc(e.model) + '\',\'' + esc(e.version) + '\')" '
                    + 'class="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded hover:bg-red-200">Remove</button>'
                    + '</div>';
            });
            html += '</div>';
            el('fw-cache').innerHTML = html;
        })
        .catch(() => { el('fw-cache').innerHTML = '<span class="text-red-500">Failed to load</span>'; });
}

function fetchSHSHBlobs() {
    const info = currentDevice ? currentDevice.info : null;
    if (!info) {
        el('fw-shsh').innerHTML = '<div class="text-gray-400">Connect a device to manage blobs</div>';
        return;
    }
    el('fw-shsh').innerHTML = '<div class="text-gray-400 animate-pulse">Loading...</div>';

    // List blobs (ecid from device info if available)
    fetch('/api/firmware/shsh')
        .then(r => r.json())
        .then(blobs => {
            let html = '<button onclick="saveSHSHBlobs()" class="text-xs bg-green-100 text-green-700 px-3 py-1 rounded hover:bg-green-200 mb-2">Save SHSH Blobs</button>';
            if (!blobs || blobs.length === 0) {
                html += '<div class="text-gray-400 text-sm">No saved blobs</div>';
            } else {
                html += '<div class="space-y-1 text-sm max-h-40 overflow-y-auto">';
                blobs.forEach(b => {
                    html += '<div class="border-b py-1"><span class="font-medium">' + esc(b.version || b.ios_version || '?') + '</span>'
                        + ' <span class="text-xs text-gray-400">' + esc(b.ecid || '') + '</span></div>';
                });
                html += '</div>';
            }
            el('fw-shsh').innerHTML = html;
        })
        .catch(() => { el('fw-shsh').innerHTML = '<span class="text-red-500">Failed to load</span>'; });
}

async function saveSHSHBlobs() {
    const info = currentDevice ? currentDevice.info : null;
    if (!info || !info.ecid) { alert('No ECID available'); return; }
    try {
        const resp = await fetch('/api/firmware/shsh?ecid=' + info.ecid + '&model=' + (info.product_type || '') + '&version=' + (info.ios_version || ''), { method: 'POST' });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const result = await resp.json();
        alert('SHSH blobs saved: ' + (result.path || 'OK'));
        fetchSHSHBlobs();
    } catch (e) { alert('Failed: ' + e.message); }
}

function fetchDeviceMode(udid) {
    el('fw-mode').innerHTML = '<div class="text-gray-400 animate-pulse">Checking...</div>';
    fetch('/api/firmware/mode/' + udid)
        .then(r => r.json())
        .then(data => {
            const modeColors = { normal: 'text-green-600', recovery: 'text-yellow-600', dfu: 'text-red-600', unknown: 'text-gray-400' };
            const mode = data.mode || 'unknown';
            let html = '<div class="text-lg font-bold ' + (modeColors[mode] || 'text-gray-400') + ' mb-3">' + esc(mode.toUpperCase()) + '</div>';
            html += '<div class="flex gap-2 flex-wrap">';
            html += '<button onclick="enterRecovery()" class="text-xs bg-yellow-100 text-yellow-700 px-3 py-1 rounded hover:bg-yellow-200">Enter Recovery</button>';
            html += '<button onclick="enterDFU()" class="text-xs bg-red-100 text-red-700 px-3 py-1 rounded hover:bg-red-200">Enter DFU</button>';
            html += '<button onclick="exitRecovery()" class="text-xs bg-green-100 text-green-700 px-3 py-1 rounded hover:bg-green-200">Exit Recovery</button>';
            html += '</div>';
            el('fw-mode').innerHTML = html;
        })
        .catch(() => { el('fw-mode').innerHTML = '<span class="text-red-500">Failed to detect mode</span>'; });
}

async function enterRecovery() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    if (!udid) return;
    try {
        const r = await fetch('/api/firmware/recovery/' + udid, { method: 'POST' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        alert('Recovery mode entered');
        fetchDeviceMode(udid);
    } catch (e) { alert('Failed: ' + e.message); }
}

async function enterDFU() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    if (!udid) return;
    try {
        const r = await fetch('/api/firmware/dfu/' + udid, { method: 'POST' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const data = await r.json();
        alert(data.message || 'DFU mode: complete button combo now');
        fetchDeviceMode(udid);
    } catch (e) { alert('Failed: ' + e.message); }
}

async function exitRecovery() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    if (!udid) return;
    try {
        const r = await fetch('/api/firmware/recovery/' + udid, { method: 'DELETE' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        alert('Exited recovery mode');
        fetchDeviceMode(udid);
    } catch (e) { alert('Failed: ' + e.message); }
}

function renderRestoreCard(model) {
    let html = '<div class="space-y-2">';
    html += '<div class="text-sm text-gray-500 mb-2">Restore firmware on connected device</div>';
    html += '<div class="flex gap-2">';
    html += '<input type="text" id="restore-version" placeholder="iOS version (optional)" class="flex-1 border rounded px-2 py-1 text-sm">';
    html += '<button onclick="startRestore()" class="text-xs bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700">Restore</button>';
    html += '</div>';
    html += '<div id="restore-progress" class="hidden mt-2"><div class="bg-gray-200 rounded-full h-2"><div id="restore-bar" class="bg-blue-600 h-2 rounded-full" style="width:0%"></div></div><div id="restore-status" class="text-xs text-gray-500 mt-1"></div></div>';
    html += '</div>';
    el('fw-restore').innerHTML = html;
}

async function startRestore() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    const model = currentDevice && currentDevice.info ? currentDevice.info.product_type : null;
    if (!udid || !model) { alert('No device connected'); return; }
    if (!confirm('This will ERASE the device and restore firmware. Continue?')) return;
    const version = el('restore-version').value || null;
    el('restore-progress').classList.remove('hidden');
    el('restore-status').textContent = 'Starting restore...';
    try {
        const body = { model };
        if (version) body.version = version;
        const r = await fetch('/api/firmware/restore/' + udid, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const result = await r.json();
        el('restore-status').textContent = 'Restore ' + (result.status || 'complete');
    } catch (e) {
        el('restore-status').textContent = 'Failed: ' + e.message;
    }
}

function renderWipeCard(udid) {
    const info = currentDevice ? currentDevice.info : {};
    let html = '<div class="space-y-2">';
    html += '<div class="text-sm text-gray-500 mb-2">Factory reset device and generate erasure certificate</div>';
    html += '<div><label class="text-xs text-gray-500">Operator</label><input type="text" id="wipe-operator" placeholder="Your name" class="w-full border rounded px-2 py-1 text-sm mb-2"></div>';
    html += '<button onclick="startWipe()" class="text-xs bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700">Wipe Device</button>';
    html += '<div id="wipe-status" class="text-sm mt-2"></div>';
    html += '</div>';
    el('fw-wipe').innerHTML = html;
}

async function startWipe() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    if (!udid) { alert('No device connected'); return; }
    if (!confirm('This will ERASE ALL DATA on the device. Continue?')) return;
    const info = currentDevice.info || {};
    const operator = el('wipe-operator').value || '';
    el('wipe-status').innerHTML = '<span class="text-yellow-600 animate-pulse">Wiping...</span>';
    try {
        const r = await fetch('/api/firmware/wipe/' + udid, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ serial: info.serial || '', imei: info.imei || '', model: info.product_type || '', ios_version: info.ios_version || '', operator })
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const result = await r.json();
        let statusHtml = result.status === 'erased'
            ? '<span class="text-green-600 font-semibold">Wipe complete</span>'
            : '<span class="text-red-600 font-semibold">Wipe failed</span>';
        if (result.cert_path) {
            const deviceId = inventoryDeviceId;
            if (deviceId) statusHtml += ' <a href="/api/firmware/certificate/' + deviceId + '" target="_blank" class="text-blue-600 underline text-xs">Download Certificate</a>';
        }
        el('wipe-status').innerHTML = statusHtml;
    } catch (e) {
        el('wipe-status').innerHTML = '<span class="text-red-600">Failed: ' + esc(e.message) + '</span>';
    }
}

async function downloadIPSW(version, buildId) {
    const model = currentDevice && currentDevice.info ? currentDevice.info.product_type : null;
    if (!model) { alert('No device model known'); return; }
    if (!confirm('Download IPSW for ' + model + ' ' + version + '? This may take a while.')) return;
    try {
        const r = await fetch('/api/firmware/download', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model, version, build_id: buildId })
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        alert('Download started — check IPSW cache');
        fetchFirmwareCache();
    } catch (e) { alert('Failed: ' + e.message); }
}

async function evictIPSW(model, version) {
    if (!confirm('Remove cached IPSW for ' + model + ' ' + version + '?')) return;
    try {
        const r = await fetch('/api/firmware/cache/' + model + '/' + version, { method: 'DELETE' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        fetchFirmwareCache();
    } catch (e) { alert('Failed: ' + e.message); }
}

function setCardDisabled(cardId, reason) {
    const card = el(cardId);
    if (!card) return;
    card.classList.add('card-disabled');
    // Insert reason banner after the h3 if not already present
    if (!card.querySelector('.card-disabled-reason')) {
        const h3 = card.querySelector('h3');
        if (h3) {
            const banner = document.createElement('div');
            banner.className = 'card-disabled-reason';
            banner.textContent = reason;
            h3.insertAdjacentElement('afterend', banner);
        }
    }
    // Mark body content as disabled
    const body = card.querySelector('div:last-child');
    if (body) body.classList.add('card-body');
}

function clearCardDisabled(cardId) {
    const card = el(cardId);
    if (!card) return;
    card.classList.remove('card-disabled');
    const banner = card.querySelector('.card-disabled-reason');
    if (banner) banner.remove();
    const body = card.querySelector('.card-body');
    if (body) body.classList.remove('card-body');
}
```

**Step 2: Verify — open Firmware tab, confirm 6 cards render with data (signed versions may fail without real device, cache should load)**

**Step 3: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: add firmware tab — signed versions, IPSW cache, SHSH, mode, restore, wipe"
```

---

### Task 3: Tools Tab — HTML + JS

**Files:**
- Modify: `app/templates/index.html` — replace `panel-tools` placeholder + add JS functions

**Step 1: Replace tools panel HTML**

```html
<!-- Tab: Tools -->
<div id="panel-tools" class="hidden">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <!-- checkra1n -->
        <div id="tool-checkra1n-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">checkra1n Jailbreak</h3>
            <div id="tool-checkra1n" class="card-body">
                <div class="text-sm text-gray-500 mb-3">Jailbreak for checkm8-compatible devices (A5–A11). Enables diagnostic access on locked devices.</div>
                <button onclick="runCheckra1n()" class="text-xs bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700">Run checkra1n</button>
                <div id="checkra1n-status" class="text-sm mt-2"></div>
            </div>
        </div>

        <!-- Broque Ramdisk -->
        <div id="tool-broque-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Broque Ramdisk</h3>
            <div id="tool-broque" class="card-body">
                <div class="text-sm text-gray-500 mb-3">Bypass activation lock on passcode-locked devices for diagnostic purposes.</div>
                <button onclick="runBroque()" class="text-xs bg-yellow-600 text-white px-3 py-1 rounded hover:bg-yellow-700">Run Bypass</button>
                <div id="broque-status" class="text-sm mt-2"></div>
            </div>
        </div>

        <!-- SSH Ramdisk -->
        <div id="tool-ssh-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">SSH Ramdisk</h3>
            <div id="tool-ssh" class="card-body">
                <div class="text-sm text-gray-500 mb-3">Boot SSH ramdisk for low-level data extraction from locked devices.</div>
                <div class="flex gap-2 flex-wrap">
                    <button onclick="bootSSHRamdisk()" class="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">Boot Ramdisk</button>
                    <button onclick="extractSSHData()" class="text-xs bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700">Extract Data</button>
                </div>
                <div id="ssh-status" class="text-sm mt-2"></div>
            </div>
        </div>

        <!-- FutureRestore -->
        <div id="tool-futurerestore-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">FutureRestore</h3>
            <div id="tool-futurerestore" class="card-body">
                <div class="text-sm text-gray-500 mb-3">Restore to unsigned firmware using saved SHSH blobs.</div>
                <div class="space-y-2">
                    <input type="text" id="fr-blob-path" placeholder="SHSH blob path" class="w-full border rounded px-2 py-1 text-sm">
                    <input type="text" id="fr-ipsw-path" placeholder="IPSW file path" class="w-full border rounded px-2 py-1 text-sm">
                    <div class="flex gap-2">
                        <button onclick="checkFutureRestore()" class="text-xs bg-blue-100 text-blue-700 px-3 py-1 rounded hover:bg-blue-200">Pre-flight Check</button>
                        <button onclick="runFutureRestore()" class="text-xs bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700">Restore</button>
                    </div>
                </div>
                <div id="futurerestore-status" class="text-sm mt-2"></div>
            </div>
        </div>

        <!-- Cable Check -->
        <div id="tool-cable-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Cable Quality</h3>
            <div id="tool-cable" class="card-body">
                <div class="text-sm text-gray-500 mb-3">Test USB cable connection quality and data transfer speed.</div>
                <button onclick="checkCable()" class="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">Test Cable</button>
                <div id="cable-status" class="text-sm mt-2"></div>
            </div>
        </div>
    </div>
</div>
```

**Step 2: Add loadToolsTab() and action JS functions**

```javascript
// -- Tools Tab --

async function loadToolsTab() {
    if (toolsLoaded) return;
    toolsLoaded = true;

    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;

    // Check tool availability
    try {
        const r = await fetch('/api/tools/availability');
        if (r.ok) toolAvailability = await r.json();
    } catch (e) { console.error('Tool availability check failed:', e); }

    // Apply disabled states based on availability
    if (!toolAvailability.checkra1n) setCardDisabled('tool-checkra1n-card', 'checkra1n not installed on system');
    else if (!deviceCapabilities.checkm8) setCardDisabled('tool-checkra1n-card', 'Device not checkm8-compatible (requires A5\u2013A11)');

    if (!toolAvailability.broque) setCardDisabled('tool-broque-card', 'Broque Ramdisk not installed on system');
    if (!toolAvailability.ssh_ramdisk) setCardDisabled('tool-ssh-card', 'SSH Ramdisk tools not installed on system');
    if (!toolAvailability.futurerestore) setCardDisabled('tool-futurerestore-card', 'futurerestore not installed on system');

    if (!udid) {
        setCardDisabled('tool-cable-card', 'No device connected');
        if (toolAvailability.checkra1n && deviceCapabilities.checkm8) setCardDisabled('tool-checkra1n-card', 'No device connected');
        if (toolAvailability.broque) setCardDisabled('tool-broque-card', 'No device connected');
        if (toolAvailability.ssh_ramdisk) setCardDisabled('tool-ssh-card', 'No device connected');
        if (toolAvailability.futurerestore) setCardDisabled('tool-futurerestore-card', 'No device connected');
    }
}

async function runCheckra1n() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    if (!udid) return;
    if (!confirm('Run checkra1n jailbreak? Device must be in DFU mode.')) return;
    el('checkra1n-status').innerHTML = '<span class="text-yellow-600 animate-pulse">Running...</span>';
    try {
        const r = await fetch('/api/tools/checkra1n/' + udid, { method: 'POST' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const result = await r.json();
        el('checkra1n-status').innerHTML = result.success
            ? '<span class="text-green-600">Jailbreak successful</span>'
            : '<span class="text-red-600">Failed: ' + esc(result.error || 'Unknown error') + '</span>';
    } catch (e) { el('checkra1n-status').innerHTML = '<span class="text-red-600">Error: ' + esc(e.message) + '</span>'; }
}

async function runBroque() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    if (!udid) return;
    el('broque-status').innerHTML = '<span class="text-yellow-600 animate-pulse">Running bypass...</span>';
    try {
        const r = await fetch('/api/tools/broque/' + udid, { method: 'POST' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const result = await r.json();
        el('broque-status').innerHTML = result.success
            ? '<span class="text-green-600">Bypass successful</span>'
            : '<span class="text-red-600">Failed: ' + esc(result.error || 'Unknown error') + '</span>';
    } catch (e) { el('broque-status').innerHTML = '<span class="text-red-600">Error: ' + esc(e.message) + '</span>'; }
}

async function bootSSHRamdisk() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    if (!udid) return;
    el('ssh-status').innerHTML = '<span class="text-yellow-600 animate-pulse">Booting ramdisk...</span>';
    try {
        const r = await fetch('/api/tools/ssh-ramdisk/' + udid, { method: 'POST' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const result = await r.json();
        el('ssh-status').innerHTML = result.success
            ? '<span class="text-green-600">Ramdisk booted</span>'
            : '<span class="text-red-600">Failed: ' + esc(result.error || 'Unknown error') + '</span>';
    } catch (e) { el('ssh-status').innerHTML = '<span class="text-red-600">Error: ' + esc(e.message) + '</span>'; }
}

async function extractSSHData() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    if (!udid) return;
    el('ssh-status').innerHTML = '<span class="text-yellow-600 animate-pulse">Extracting data...</span>';
    try {
        const r = await fetch('/api/tools/ssh-ramdisk/' + udid + '/extract', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data_types: ['contacts', 'photos', 'messages'], target_dir: '/tmp/idiag-extract' })
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const result = await r.json();
        el('ssh-status').innerHTML = '<span class="text-green-600">Extraction complete</span>';
    } catch (e) { el('ssh-status').innerHTML = '<span class="text-red-600">Error: ' + esc(e.message) + '</span>'; }
}

async function checkFutureRestore() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    if (!udid) return;
    const blob = el('fr-blob-path').value;
    if (!blob) { alert('Enter SHSH blob path'); return; }
    el('futurerestore-status').innerHTML = '<span class="text-yellow-600 animate-pulse">Checking...</span>';
    try {
        const r = await fetch('/api/tools/futurerestore/' + udid + '/check?target_version=&blob_path=' + encodeURIComponent(blob));
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const result = await r.json();
        el('futurerestore-status').innerHTML = result.compatible
            ? '<span class="text-green-600">Compatible — ready to restore</span>'
            : '<span class="text-red-600">Not compatible: ' + esc(result.reason || '') + '</span>';
    } catch (e) { el('futurerestore-status').innerHTML = '<span class="text-red-600">Error: ' + esc(e.message) + '</span>'; }
}

async function runFutureRestore() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    if (!udid) return;
    const blob = el('fr-blob-path').value;
    const ipsw = el('fr-ipsw-path').value;
    if (!blob || !ipsw) { alert('Enter both SHSH blob and IPSW paths'); return; }
    if (!confirm('Run FutureRestore? This will erase the device.')) return;
    el('futurerestore-status').innerHTML = '<span class="text-yellow-600 animate-pulse">Restoring...</span>';
    try {
        const r = await fetch('/api/tools/futurerestore/' + udid, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ipsw_path: ipsw, blob_path: blob, set_nonce: true })
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const result = await r.json();
        el('futurerestore-status').innerHTML = result.success
            ? '<span class="text-green-600">Restore successful</span>'
            : '<span class="text-red-600">Failed: ' + esc(result.error || '') + '</span>';
    } catch (e) { el('futurerestore-status').innerHTML = '<span class="text-red-600">Error: ' + esc(e.message) + '</span>'; }
}

async function checkCable() {
    const udid = currentDevice && currentDevice.info ? currentDevice.info.udid : null;
    if (!udid) return;
    el('cable-status').innerHTML = '<span class="text-yellow-600 animate-pulse">Testing...</span>';
    try {
        const r = await fetch('/api/tools/cable/' + udid);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const result = await r.json();
        const color = result.quality === 'good' ? 'text-green-600' : result.quality === 'fair' ? 'text-yellow-600' : 'text-red-600';
        let html = '<div class="' + color + ' font-semibold">' + esc((result.quality || 'unknown').toUpperCase()) + '</div>';
        if (result.speed) html += '<div class="text-sm text-gray-500">Speed: ' + esc(result.speed) + '</div>';
        if (result.type) html += '<div class="text-sm text-gray-500">Type: ' + esc(result.type) + '</div>';
        el('cable-status').innerHTML = html;
    } catch (e) { el('cable-status').innerHTML = '<span class="text-red-600">Error: ' + esc(e.message) + '</span>'; }
}
```

**Step 3: Store capabilities for tool availability logic**

In `fetchCapabilities()` callback (around line 378), add after `renderCapabilityChips(cap)`:

```javascript
deviceCapabilities = cap;
```

**Step 4: Verify — open Tools tab, confirm 5 cards show with appropriate disabled states**

**Step 5: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: add tools tab — checkra1n, broque, SSH ramdisk, futurerestore, cable check"
```

---

### Task 4: Photos Tab — HTML + JS

**Files:**
- Modify: `app/templates/index.html` — replace `panel-photos` placeholder + add JS functions

**Step 1: Replace photos panel HTML**

```html
<!-- Tab: Photos -->
<div id="panel-photos" class="hidden">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Upload -->
        <div id="photos-upload-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Upload Photo</h3>
            <div id="photos-upload" class="card-body">
                <div class="space-y-3">
                    <div>
                        <label class="block text-sm text-gray-500 mb-1">Label</label>
                        <select id="photo-label" class="w-full border rounded px-2 py-1 text-sm">
                            <option value="front">Front</option>
                            <option value="back">Back</option>
                            <option value="screen">Screen</option>
                            <option value="damage">Damage</option>
                            <option value="other">Other</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm text-gray-500 mb-1">Photo</label>
                        <input type="file" id="photo-file" accept="image/*" class="w-full text-sm">
                    </div>
                    <button onclick="uploadPhoto()" class="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700">Upload</button>
                    <div id="photo-upload-status" class="text-sm"></div>
                </div>
            </div>
        </div>

        <!-- Gallery -->
        <div id="photos-gallery-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Photo Gallery</h3>
            <div id="photos-gallery" class="card-body">
                <span class="text-gray-400">No photos</span>
            </div>
        </div>
    </div>
</div>
```

**Step 2: Add loadPhotosTab() and photo JS functions**

```javascript
// -- Photos Tab --

async function loadPhotosTab() {
    if (!inventoryDeviceId) {
        setCardDisabled('photos-upload-card', 'Save device to inventory first');
        setCardDisabled('photos-gallery-card', 'Save device to inventory first');
        return;
    }
    clearCardDisabled('photos-upload-card');
    clearCardDisabled('photos-gallery-card');
    fetchPhotoGallery();
}

async function uploadPhoto() {
    if (!inventoryDeviceId) { alert('Save device to inventory first'); return; }
    const file = el('photo-file').files[0];
    if (!file) { alert('Select a photo'); return; }
    const label = el('photo-label').value;
    const form = new FormData();
    form.append('file', file);

    el('photo-upload-status').innerHTML = '<span class="text-yellow-600 animate-pulse">Uploading...</span>';
    try {
        const r = await fetch('/api/photos/upload/' + inventoryDeviceId + '?label=' + label, { method: 'POST', body: form });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        el('photo-upload-status').innerHTML = '<span class="text-green-600">Uploaded</span>';
        el('photo-file').value = '';
        fetchPhotoGallery();
    } catch (e) { el('photo-upload-status').innerHTML = '<span class="text-red-600">Failed: ' + esc(e.message) + '</span>'; }
}

function fetchPhotoGallery() {
    if (!inventoryDeviceId) return;
    el('photos-gallery').innerHTML = '<div class="text-gray-400 animate-pulse">Loading...</div>';
    fetch('/api/photos/device/' + inventoryDeviceId)
        .then(r => r.json())
        .then(photos => {
            if (!photos || photos.length === 0) {
                el('photos-gallery').innerHTML = '<div class="text-gray-400">No photos uploaded</div>';
                return;
            }
            let html = '<div class="grid grid-cols-2 gap-2">';
            photos.forEach(p => {
                html += '<div class="relative border rounded overflow-hidden">'
                    + '<img src="/api/photos/file/' + p.id + '" alt="' + esc(p.label) + '" class="w-full h-32 object-cover">'
                    + '<div class="absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 text-white text-xs px-2 py-1 flex justify-between">'
                    + '<span>' + esc(p.label) + '</span>'
                    + '<button onclick="deletePhoto(' + p.id + ')" class="text-red-300 hover:text-red-100">Delete</button>'
                    + '</div></div>';
            });
            html += '</div>';
            el('photos-gallery').innerHTML = html;
        })
        .catch(() => { el('photos-gallery').innerHTML = '<span class="text-red-500">Failed to load</span>'; });
}

async function deletePhoto(photoId) {
    if (!confirm('Delete this photo?')) return;
    try {
        const r = await fetch('/api/photos/' + photoId, { method: 'DELETE' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        fetchPhotoGallery();
    } catch (e) { alert('Failed: ' + e.message); }
}
```

**Step 3: Verify — open Photos tab, confirm disabled state when device not in inventory, then save to inventory and verify upload works**

**Step 4: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: add photos tab — upload and gallery with inventory gating"
```

---

### Task 5: Reports Tab — HTML + JS

**Files:**
- Modify: `app/templates/index.html` — replace `panel-reports` placeholder + add JS functions

**Step 1: Replace reports panel HTML**

```html
<!-- Tab: Reports -->
<div id="panel-reports" class="hidden">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <!-- Generate Report -->
        <div id="report-gen-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Device Report</h3>
            <div id="report-gen" class="card-body">
                <div class="text-sm text-gray-500 mb-3">Generate a comprehensive diagnostic report</div>
                <div class="flex gap-2">
                    <a id="report-pdf-link" href="#" target="_blank" class="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 inline-block">Download PDF</a>
                    <a id="report-html-link" href="#" target="_blank" class="text-xs bg-gray-200 text-gray-700 px-3 py-1 rounded hover:bg-gray-300 inline-block">Preview HTML</a>
                </div>
            </div>
        </div>

        <!-- QR Code -->
        <div id="report-qr-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">QR Code</h3>
            <div id="report-qr" class="card-body">
                <div class="text-sm text-gray-500 mb-3">Generate QR code linking to device report</div>
                <button onclick="generateQR()" class="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">Generate QR</button>
                <div id="qr-display" class="mt-2"></div>
            </div>
        </div>

        <!-- Listing Generator -->
        <div id="report-listing-card" class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Listing Generator</h3>
            <div id="report-listing" class="card-body">
                <div class="space-y-2">
                    <div>
                        <label class="block text-sm text-gray-500 mb-1">Platform</label>
                        <select id="listing-platform" class="w-full border rounded px-2 py-1 text-sm">
                            <option value="ebay">eBay</option>
                            <option value="swappa">Swappa</option>
                            <option value="facebook">Facebook Marketplace</option>
                            <option value="generic">Generic</option>
                        </select>
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-sm text-gray-500 mb-1">Price ($)</label>
                            <input type="number" id="listing-price" placeholder="0" class="w-full border rounded px-2 py-1 text-sm">
                        </div>
                        <div>
                            <label class="block text-sm text-gray-500 mb-1">Condition</label>
                            <select id="listing-condition" class="w-full border rounded px-2 py-1 text-sm">
                                <option value="Excellent">Excellent</option>
                                <option value="Good" selected>Good</option>
                                <option value="Fair">Fair</option>
                                <option value="Poor">Poor</option>
                            </select>
                        </div>
                    </div>
                    <button onclick="generateListing()" class="text-xs bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700">Generate Listing</button>
                </div>
                <div id="listing-output" class="mt-2"></div>
            </div>
        </div>

        <!-- Bulk Export -->
        <div class="bg-white rounded-lg shadow-md p-4">
            <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Bulk Export</h3>
            <div class="text-sm text-gray-500 mb-3">Export entire inventory database</div>
            <div class="flex gap-2">
                <a href="/api/reports/export/csv" target="_blank" class="text-xs bg-green-100 text-green-700 px-3 py-1 rounded hover:bg-green-200 inline-block">Export CSV</a>
                <a href="/api/reports/export/json" target="_blank" class="text-xs bg-blue-100 text-blue-700 px-3 py-1 rounded hover:bg-blue-200 inline-block">Export JSON</a>
            </div>
        </div>
    </div>
</div>
```

**Step 2: Add loadReportsTab() and report JS functions**

```javascript
// -- Reports Tab --

function loadReportsTab() {
    if (!inventoryDeviceId) {
        setCardDisabled('report-gen-card', 'Save device to inventory first');
        setCardDisabled('report-qr-card', 'Save device to inventory first');
        setCardDisabled('report-listing-card', 'Save device to inventory first');
        return;
    }
    clearCardDisabled('report-gen-card');
    clearCardDisabled('report-qr-card');
    clearCardDisabled('report-listing-card');

    // Set report links
    el('report-pdf-link').href = '/api/reports/pdf/' + inventoryDeviceId;
    el('report-html-link').href = '/api/reports/html/' + inventoryDeviceId;
}

function generateQR() {
    if (!inventoryDeviceId) { alert('Save device to inventory first'); return; }
    el('qr-display').innerHTML = '<div class="text-gray-400 animate-pulse">Generating...</div>';
    el('qr-display').innerHTML = '<img src="/api/reports/qr/' + inventoryDeviceId + '" alt="QR Code" class="w-32 h-32">';
}

async function generateListing() {
    if (!inventoryDeviceId) { alert('Save device to inventory first'); return; }
    const platform = el('listing-platform').value;
    const price = el('listing-price').value || 0;
    const condition = el('listing-condition').value;
    el('listing-output').innerHTML = '<div class="text-gray-400 animate-pulse">Generating...</div>';
    try {
        const params = new URLSearchParams({ platform, price, condition });
        const r = await fetch('/api/reports/listing/' + inventoryDeviceId + '?' + params);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const data = await r.json();
        let html = '<div class="mt-2 border rounded p-2 bg-gray-50">';
        if (data.title) html += '<div class="font-semibold text-sm">' + esc(data.title) + '</div>';
        if (data.description) html += '<pre class="text-xs text-gray-600 mt-1 whitespace-pre-wrap">' + esc(data.description) + '</pre>';
        html += '<button onclick="copyListing()" class="text-xs bg-gray-200 text-gray-700 px-2 py-0.5 rounded mt-1 hover:bg-gray-300">Copy to Clipboard</button>';
        html += '</div>';
        el('listing-output').innerHTML = html;
        // Store for copy
        window._lastListing = (data.title || '') + '\n\n' + (data.description || '');
    } catch (e) { el('listing-output').innerHTML = '<span class="text-red-600">Failed: ' + esc(e.message) + '</span>'; }
}

function copyListing() {
    if (window._lastListing) {
        navigator.clipboard.writeText(window._lastListing).then(() => alert('Copied!')).catch(() => alert('Copy failed'));
    }
}
```

**Step 3: Verify — open Reports tab, confirm 4 cards render, per-device cards disabled without inventory, bulk export always active**

**Step 4: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: add reports tab — PDF, QR, listings, bulk export"
```

---

### Task 6: Wire Capability + Availability Fetching into loadSnapshot

**Files:**
- Modify: `app/templates/index.html` — update `loadSnapshot()` and `fetchCapabilities()`

**Step 1: Store capabilities in fetchCapabilities callback**

In the `fetchCapabilities` function's `.then(cap => ...)` callback (around line 378), add after `renderCapabilityChips(cap)`:

```javascript
deviceCapabilities = cap;
```

**Step 2: Pre-fetch tool availability in loadSnapshot**

In `loadSnapshot()`, after the `fetchMarketPrice` call (around line 361), add:

```javascript
// Pre-fetch tool availability for Tools tab
fetch('/api/tools/availability')
    .then(r => r.ok ? r.json() : {})
    .then(a => { toolAvailability = a; })
    .catch(() => {});
```

**Step 3: Reset loaded flags on new snapshot load**

At the top of `loadSnapshot()`, after `if (!udid) return;`, add:

```javascript
firmwareLoaded = false;
toolsLoaded = false;
photosLoaded = false;
reportsLoaded = false;
```

**Step 4: Verify — connect device, switch between all 8 tabs, confirm data loads and disabled states apply correctly**

**Step 5: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: wire capability and tool availability into snapshot flow"
```

---

### Task 7: Final Verification + Cleanup

**Step 1: Run the app and test all 8 tabs end-to-end**

```bash
cd "D:/Project - idiag"
PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify checklist:
- [ ] 8 tabs visible, horizontally scrollable on small screens
- [ ] Diagnostics tab unchanged from before
- [ ] Firmware tab: 6 cards, signed versions + cache load, mode/restore/wipe require device
- [ ] Tools tab: 5 cards, unavailable tools greyed with reason, device-dependent tools greyed without device
- [ ] Photos tab: disabled without inventory, upload + gallery work after saving
- [ ] Reports tab: PDF/HTML/QR/listing disabled without inventory, bulk export always works
- [ ] History tab: unchanged
- [ ] Pricing tab: unchanged
- [ ] Syslog tab: unchanged
- [ ] Tab switching cleans up syslog WebSocket correctly

**Step 2: Run existing tests to confirm no regressions**

```bash
cd "D:/Project - idiag"
PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/']))"
```

Expected: 177+ tests passing (no backend changes, so no regressions expected)

**Step 3: Final commit if any cleanup needed**

```bash
git add app/templates/index.html
git commit -m "feat: complete dashboard expansion — all features visible across 8 tabs"
```
