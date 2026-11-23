"""Utilitários compartilhados de detecção e parsing de números com unidades (Core v8.0)."""

from __future__ import annotations

import re

UNITS_MULTI = (
    r"°[CFK]|kg/m³|kg/m3|g/cm³|g/cm3|g/cm²|g/cm2|kg/kW|W/kg|Wh/kg|W/m²|W/m2|N/m²|"
    r"J/\(kg[·\*\.]K\)|W/\(m[·\*\.]K\)|W/\(m²[·\*\.]K⁴\)|"
    r"ms|μs|us|ns|ps|min|Hz|kHz|MHz|GHz|THz|"
    r"kW|MW|GW|TW|Wh|kWh|MWh|GWh|kJ|MJ|GJ|eV|keV|MeV|GeV|"
    r"kg|mg|μg|km|cm|mm|nm|μm|um|"
    r"m/s²|m/s2|m/s|km/s|km/h|kg/s|kN|MN|"
    r"Pa|kPa|MPa|GPa|bar|mbar|atm|"
    r"kV|mV|mA|μA|Ah|mAh|kΩ|MΩ|Ohm|μF|nF|pF|mH|μH|"
    r"dBi|dBm|dBc|dB|ppm|ppb|"
    r"TB/day|TB/dia|GB/s|Gbps|Mbps|kbps|KiB|MiB|GiB|TiB|KB|MB|GB|TB|PB|"
    r"N[·\.]m|J/kg|m²/s|m2/s|m²|m2|m³|m3|cm²|cm2|cm³|cm3|mm²|mm2|"
    r"rad/s|rad|sr|cd|lm|lx|Bq|Gy|Sv|krad|Mrad"
)

UNITS_SINGLE = r"%|[KJWAVNΩ]|(?<![a-zA-Z])[smgthL](?![a-zA-Z])"

NUMBER_WITH_UNIT_RE = re.compile(
    r"(?<![a-zA-Z0-9_])([+-]?\d+(?:[.,]\d+)?)\s*(" + UNITS_MULTI + r"|" + UNITS_SINGLE + r")(?=$|[\s,.;:)!?\]\}])"
)


def extract_numbers_with_units(text: str) -> list[dict[str, str | float]]:
    """Extrai pares estruturados (raw, value, unit) de um trecho textual."""
    results: list[dict[str, str | float]] = []
    for match in NUMBER_WITH_UNIT_RE.finditer(text):
        raw_num = match.group(1)
        unit = match.group(2)
        try:
            val = float(raw_num.replace(",", "."))
        except ValueError:
            continue
        results.append({"raw": match.group(0), "value": val, "unit": unit})
    return results
