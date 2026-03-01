"""Local Apple serial number / IMEI decoder and fraud detection.

No external API dependency. Decodes old-format (pre-2021) serial numbers,
validates IMEIs via Luhn, and cross-references device fields.
"""

from app.models.inventory import FraudCheck, IMEIValidation, SerialDecoded

# -- Factory codes (characters 1-3 of old serial) --

FACTORY_CODES: dict[str, str] = {
    "FC": "Fountain, Colorado, USA",
    "F": "Fremont, California, USA",
    "XA": "USA", "XB": "USA", "QP": "USA", "G8": "USA",
    "RN": "Flextronics, Mexico",
    "CK": "Cork, Ireland",
    "VM": "Foxconn, Czech Republic",
    "SG": "Singapore", "E": "Singapore",
    "MB": "Malaysia",
    "PT": "Korea", "CY": "Korea",
    "EE": "Taiwan", "QT": "Taiwan", "UV": "Taiwan",
    "FK": "Foxconn, Zhengzhou, China",
    "F1": "Foxconn, Zhengzhou, China",
    "F2": "Foxconn, Zhengzhou, China",
    "C8Q": "Foxconn, Zhengzhou, China",
    "W8": "Shanghai, China",
    "DL": "Foxconn, China", "DM": "Foxconn, China",
    "DN": "Foxconn, Chengdu, China",
    "YM": "Hon Hai/Foxconn, China", "7J": "Hon Hai/Foxconn, China",
    "1C": "China", "4H": "China", "WQ": "China", "F7": "China",
    "C0": "Quanta, China",
    "C3": "Foxconn, Shenzhen, China",
    "C7": "Pentragon, Shanghai, China",
    "Y5": "India",
    "RM": "Refurbished",
}

# Character 4 -> (year_digit, half)
YEAR_CODES: dict[str, tuple[int, str]] = {
    "C": (0, "first"), "D": (0, "second"),
    "F": (1, "first"), "G": (1, "second"),
    "H": (2, "first"), "J": (2, "second"),
    "K": (3, "first"), "L": (3, "second"),
    "M": (4, "first"), "N": (4, "second"),
    "P": (5, "first"), "Q": (5, "second"),
    "R": (6, "first"), "S": (6, "second"),
    "T": (7, "first"), "V": (7, "second"),
    "W": (8, "first"), "X": (8, "second"),
    "Y": (9, "first"), "Z": (9, "second"),
}

# Character 5 -> week number within half (1-27)
WEEK_CHARS = "123456789CDFGHJKLMNPQRTVWXY"
WEEK_MAP: dict[str, int] = {ch: i + 1 for i, ch in enumerate(WEEK_CHARS)}


def _resolve_factory(serial: str) -> str:
    for length in (3, 2, 1):
        code = serial[:length].upper()
        if code in FACTORY_CODES:
            return FACTORY_CODES[code]
    return f"Unknown ({serial[:3]})"


def decode_serial(serial: str) -> SerialDecoded:
    """Decode a 12-character Apple serial number."""
    serial = serial.strip().upper()
    result = SerialDecoded(raw=serial)

    if len(serial) != 12:
        result.is_randomized = True
        return result

    year_char = serial[3]
    if year_char not in YEAR_CODES:
        result.is_randomized = True
        return result

    result.factory = _resolve_factory(serial)

    year_digit, half = YEAR_CODES[year_char]
    result.half = half
    result.year_candidates = [2010 + year_digit, 2020 + year_digit]

    week_char = serial[4]
    if week_char in WEEK_MAP:
        result.week_in_half = WEEK_MAP[week_char]
        result.week_of_year = (
            result.week_in_half if half == "first" else result.week_in_half + 27
        )

    result.model_code = serial[8:12]
    return result


# -- IMEI validation --


def _luhn_checksum(number: str) -> int:
    digits = [int(d) for d in number if d.isdigit()]
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10


def _luhn_check_digit(partial: str) -> str:
    remainder = _luhn_checksum(partial + "0")
    return str((10 - remainder) % 10)


def validate_imei(imei: str) -> IMEIValidation:
    """Validate a 15-digit IMEI using the Luhn algorithm."""
    clean = imei.replace("-", "").replace(" ", "")
    result = IMEIValidation(raw=imei)

    if not clean.isdigit():
        result.notes.append("Contains non-digit characters.")
        return result

    if len(clean) != 15:
        result.notes.append(f"Must be 15 digits, got {len(clean)}.")
        return result

    result.tac = clean[:8]
    expected = _luhn_check_digit(clean[:14])
    result.luhn_valid = expected == clean[14]
    result.is_valid = result.luhn_valid

    if not result.luhn_valid:
        result.notes.append(f"Luhn check failed: got '{clean[14]}', expected '{expected}'.")

    return result


# -- Product type to device name --

PRODUCT_TYPE_MAP: dict[str, str] = {
    "iPhone8,1": "iPhone 6s", "iPhone8,2": "iPhone 6s Plus",
    "iPhone8,4": "iPhone SE (1st gen)",
    "iPhone9,1": "iPhone 7", "iPhone9,3": "iPhone 7",
    "iPhone9,2": "iPhone 7 Plus", "iPhone9,4": "iPhone 7 Plus",
    "iPhone10,1": "iPhone 8", "iPhone10,4": "iPhone 8",
    "iPhone10,2": "iPhone 8 Plus", "iPhone10,5": "iPhone 8 Plus",
    "iPhone10,3": "iPhone X", "iPhone10,6": "iPhone X",
    "iPhone11,2": "iPhone XS",
    "iPhone11,4": "iPhone XS Max", "iPhone11,6": "iPhone XS Max",
    "iPhone11,8": "iPhone XR",
    "iPhone12,1": "iPhone 11", "iPhone12,3": "iPhone 11 Pro",
    "iPhone12,5": "iPhone 11 Pro Max", "iPhone12,8": "iPhone SE (2nd gen)",
    "iPhone13,1": "iPhone 12 mini", "iPhone13,2": "iPhone 12",
    "iPhone13,3": "iPhone 12 Pro", "iPhone13,4": "iPhone 12 Pro Max",
    "iPhone14,2": "iPhone 13 Pro", "iPhone14,3": "iPhone 13 Pro Max",
    "iPhone14,4": "iPhone 13 mini", "iPhone14,5": "iPhone 13",
    "iPhone14,6": "iPhone SE (3rd gen)",
    "iPhone14,7": "iPhone 14", "iPhone14,8": "iPhone 14 Plus",
    "iPhone15,2": "iPhone 14 Pro", "iPhone15,3": "iPhone 14 Pro Max",
    "iPhone15,4": "iPhone 15", "iPhone15,5": "iPhone 15 Plus",
    "iPhone16,1": "iPhone 15 Pro", "iPhone16,2": "iPhone 15 Pro Max",
    "iPhone17,1": "iPhone 16 Pro", "iPhone17,2": "iPhone 16 Pro Max",
    "iPhone17,3": "iPhone 16", "iPhone17,4": "iPhone 16 Plus",
}

# A-number to (device_name, region)
ANUMBER_MAP: dict[str, tuple[str, str]] = {
    "A2111": ("iPhone 11", "US"), "A2221": ("iPhone 11", "Global"),
    "A2160": ("iPhone 11 Pro", "US"), "A2215": ("iPhone 11 Pro", "Global"),
    "A2161": ("iPhone 11 Pro Max", "US"), "A2218": ("iPhone 11 Pro Max", "Global"),
    "A2275": ("iPhone SE (2nd gen)", "US"), "A2296": ("iPhone SE (2nd gen)", "Global"),
    "A2172": ("iPhone 12", "US"), "A2403": ("iPhone 12", "Global"),
    "A2176": ("iPhone 12 mini", "US"), "A2399": ("iPhone 12 mini", "Global"),
    "A2341": ("iPhone 12 Pro", "US"), "A2407": ("iPhone 12 Pro", "Global"),
    "A2342": ("iPhone 12 Pro Max", "US"), "A2411": ("iPhone 12 Pro Max", "Global"),
    "A2482": ("iPhone 13", "US"), "A2633": ("iPhone 13", "Global"),
    "A2481": ("iPhone 13 mini", "US"), "A2628": ("iPhone 13 mini", "Global"),
    "A2483": ("iPhone 13 Pro", "US"), "A2638": ("iPhone 13 Pro", "Global"),
    "A2484": ("iPhone 13 Pro Max", "US"), "A2643": ("iPhone 13 Pro Max", "Global"),
    "A2595": ("iPhone SE (3rd gen)", "US"), "A2783": ("iPhone SE (3rd gen)", "Global"),
    "A2649": ("iPhone 14", "US"), "A2882": ("iPhone 14", "Global"),
    "A2632": ("iPhone 14 Plus", "US"), "A2886": ("iPhone 14 Plus", "Global"),
    "A2650": ("iPhone 14 Pro", "US"), "A2890": ("iPhone 14 Pro", "Global"),
    "A2651": ("iPhone 14 Pro Max", "US"), "A2894": ("iPhone 14 Pro Max", "Global"),
    "A2846": ("iPhone 15", "US"), "A3090": ("iPhone 15", "Global"),
    "A2847": ("iPhone 15 Plus", "US"), "A3094": ("iPhone 15 Plus", "Global"),
    "A2848": ("iPhone 15 Pro", "US"), "A3102": ("iPhone 15 Pro", "Global"),
    "A2849": ("iPhone 15 Pro Max", "US"), "A3106": ("iPhone 15 Pro Max", "Global"),
    "A3081": ("iPhone 16", "US"), "A3287": ("iPhone 16", "Global"),
    "A3082": ("iPhone 16 Plus", "US"), "A3290": ("iPhone 16 Plus", "Global"),
    "A3083": ("iPhone 16 Pro", "US"), "A3293": ("iPhone 16 Pro", "Global"),
    "A3084": ("iPhone 16 Pro Max", "US"), "A3296": ("iPhone 16 Pro Max", "Global"),
}


TAC_MAP: dict[str, str] = {
    "35346211": "iPhone 13 Pro",
    "35407115": "iPhone 13 Pro Max",
    "35256211": "iPhone 13",
    "35256311": "iPhone 13 mini",
    "35467211": "iPhone 14",
    "35467311": "iPhone 14 Plus",
    "35523411": "iPhone 14 Pro",
    "35523511": "iPhone 14 Pro Max",
    "35691412": "iPhone 15",
    "35691512": "iPhone 15 Plus",
    "35691612": "iPhone 15 Pro",
    "35691712": "iPhone 15 Pro Max",
    "35474212": "iPhone SE (3rd gen)",
    "35205610": "iPhone 12",
    "35205510": "iPhone 12 mini",
    "35205710": "iPhone 12 Pro",
    "35205810": "iPhone 12 Pro Max",
    "35391509": "iPhone 11",
    "35395909": "iPhone 11 Pro",
    "35395809": "iPhone 11 Pro Max",
    "35325110": "iPhone SE (2nd gen)",
    "35884810": "iPhone 16",
    "35884910": "iPhone 16 Plus",
    "35885010": "iPhone 16 Pro",
    "35885110": "iPhone 16 Pro Max",
}


def cross_reference_check(
    serial: str,
    model_number: str,
    product_type: str,
    imei: str = "",
) -> FraudCheck:
    """Cross-reference device identifiers to detect board swaps or tampering."""
    result = FraudCheck()
    score = 0

    # Check if serial is randomized
    decoded = decode_serial(serial)
    if decoded.is_randomized:
        result.randomized_note = (
            "This device has a randomized serial number (manufactured after 2021). "
            "Serial-based factory/date decoding unavailable."
        )

    # Resolve device names from both model number and product type
    a_num = model_number.strip().upper()
    if not a_num.startswith("A"):
        a_num = "A" + a_num
    model_entry = ANUMBER_MAP.get(a_num)
    pt_name = PRODUCT_TYPE_MAP.get(product_type)

    if model_entry and pt_name:
        model_name = model_entry[0]
        if model_name != pt_name:
            result.is_suspicious = True
            result.flags.append(
                f"ModelNumber '{model_number}' -> '{model_name}' but "
                f"ProductType '{product_type}' -> '{pt_name}'. Possible board swap."
            )
            score += 30

    # IMEI validation
    if imei:
        imei_result = validate_imei(imei)
        if not imei_result.is_valid:
            result.is_suspicious = True
            result.flags.append(f"Invalid IMEI: {'; '.join(imei_result.notes)}")
            score += 40

        # TAC-based model cross-reference
        if imei_result.tac:
            tac_model = TAC_MAP.get(imei_result.tac)
            if tac_model and pt_name and tac_model != pt_name:
                result.is_suspicious = True
                result.flags.append(
                    f"IMEI TAC indicates '{tac_model}' but ProductType "
                    f"'{product_type}' -> '{pt_name}'. Possible IMEI tampering."
                )
                score += 20

    if not result.flags:
        if model_entry or pt_name:
            result.flags.append("No anomalies detected.")
        else:
            result.flags.append("Insufficient data for cross-reference (unknown model identifiers).")
            score += 10

    result.fraud_score = min(score, 100)
    return result
