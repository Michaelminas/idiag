"""Marketplace listing template generator."""

from app.models.device import DeviceRecord
from app.models.sales import ListingTemplate

EBAY_TEMPLATE = """
{model} - {storage} - {color} - Grade {grade}

**Condition:** {condition}

**Specifications:**
- Model: {model}
- iOS Version: {ios_version}
- Storage: {storage}
- Battery Health: {battery_health}%
- Grade: {grade}

**Verification:**
- Blacklist: {blacklist}
- Find My iPhone: {fmi}
- Carrier: {carrier} ({lock_status})

**What's Included:**
- {model}
- (add accessories here)

**Tested with iDiag diagnostic tool. Full health report available.**
""".strip()

MARKETPLACE_TEMPLATE = """
{model} - {storage} - Grade {grade}

{condition_desc}

Battery Health: {battery_health}%
Storage: {storage}
Carrier: {carrier} ({lock_status})
iOS: {ios_version}

Blacklist clean ✓ | FMI off ✓ | Fully tested ✓

Price: ${price}

No trades. Cash or electronic payment only.
""".strip()


def generate_listing(device: DeviceRecord, platform: str,
                     diagnostics=None, verification=None,
                     price: float = 0, condition: str = "Good") -> ListingTemplate:
    """Generate a marketplace listing template."""
    diag = diagnostics
    verif = verification

    data = {
        "model": device.model or "iPhone",
        "ios_version": device.ios_version or "N/A",
        "storage": f"{round(diag.storage.total_gb)}GB" if diag else "N/A",
        "color": "",
        "grade": device.grade or "N/A",
        "battery_health": diag.battery.health_percent if diag else "N/A",
        "blacklist": verif.blacklist_status if verif else "N/A",
        "fmi": verif.fmi_status if verif else "N/A",
        "carrier": verif.carrier if verif else "N/A",
        "lock_status": "Locked" if (verif and verif.carrier_locked) else "Unlocked",
        "condition": condition,
        "condition_desc": f"Condition: {condition}",
        "price": price,
    }

    if platform == "ebay":
        title = f"{data['model']} {data['storage']} {data['grade']}"
        desc = EBAY_TEMPLATE.format(**data)
    else:  # marketplace
        title = f"{data['model']} {data['storage']} - ${price}"
        desc = MARKETPLACE_TEMPLATE.format(**data)

    return ListingTemplate(
        platform=platform,
        title=title[:80],
        description=desc,
        price=price,
        condition=condition,
    )
