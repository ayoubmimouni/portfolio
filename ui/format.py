# -*- coding: utf-8 -*-
"""Number, currency and date formatting helpers.

Financial UIs live or die on consistent number rendering, so every figure
displayed in the app goes through one of these functions instead of ad-hoc
f-strings.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

_UNITS = ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K"))

PLACEHOLDER = "—"


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return True
    return False


def money(value: Any, decimals: int = 0, symbol: str = "$") -> str:
    """Format a currency amount: `money(12345.6)` -> `$12,346`."""
    if _is_missing(value):
        return PLACEHOLDER
    sign = "-" if value < 0 else ""
    return f"{sign}{symbol}{abs(float(value)):,.{decimals}f}"


def _trim(text: str) -> str:
    """Drop trailing zeros so `250.00K` reads `250K`."""
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def compact_money(value: Any, symbol: str = "$") -> str:
    """Abbreviate large amounts: `compact_money(2_450_000)` -> `$2.45M`."""
    if _is_missing(value):
        return PLACEHOLDER
    value = float(value)
    sign = "-" if value < 0 else ""
    abs_value = abs(value)
    for threshold, suffix in _UNITS:
        if abs_value >= threshold:
            return f"{sign}{symbol}{_trim(f'{abs_value / threshold:,.2f}')}{suffix}"
    return f"{sign}{symbol}{_trim(f'{abs_value:,.2f}')}"


def compact_number(value: Any) -> str:
    """Abbreviate a plain number: `compact_number(812817)` -> `812.8K`."""
    if _is_missing(value):
        return PLACEHOLDER
    value = float(value)
    sign = "-" if value < 0 else ""
    abs_value = abs(value)
    for threshold, suffix in _UNITS:
        if abs_value >= threshold:
            return f"{sign}{abs_value / threshold:,.1f}{suffix}"
    return f"{sign}{abs_value:,.0f}"


def percent(value: Any, decimals: int = 2) -> str:
    """Format a percentage already expressed in percent points."""
    if _is_missing(value):
        return PLACEHOLDER
    return f"{float(value):,.{decimals}f}%"


def signed_percent(value: Any, decimals: int = 2) -> str:
    """Format a percentage with an explicit sign, for variations."""
    if _is_missing(value):
        return PLACEHOLDER
    return f"{float(value):+,.{decimals}f}%"


def signed_money(value: Any, decimals: int = 0, symbol: str = "$") -> str:
    """Format a currency delta with an explicit sign."""
    if _is_missing(value):
        return PLACEHOLDER
    value = float(value)
    sign = "+" if value >= 0 else "-"
    return f"{sign}{symbol}{abs(value):,.{decimals}f}"


def ratio(value: Any, decimals: int = 2) -> str:
    """Format a unitless ratio such as a Sharpe ratio."""
    if _is_missing(value):
        return PLACEHOLDER
    return f"{float(value):,.{decimals}f}"


def price(value: Any) -> str:
    """Format an instrument price."""
    if _is_missing(value):
        return PLACEHOLDER
    return f"{float(value):,.2f}"


def tone_of(value: Any, neutral_band: float = 0.0) -> str:
    """Map a numeric variation to a semantic tone name (`up`/`down`/`flat`)."""
    if _is_missing(value):
        return "flat"
    value = float(value)
    if value > neutral_band:
        return "up"
    if value < -neutral_band:
        return "down"
    return "flat"


def arrow_of(value: Any) -> str:
    """Return a directional glyph matching a variation."""
    tone = tone_of(value)
    return {"up": "▲", "down": "▼", "flat": "•"}[tone]


# The interface is French but the server locale is not guaranteed, so date
# names are mapped explicitly instead of relying on `locale.setlocale`.
_FR_DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_FR_MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre")


def long_date_fr(value: date | datetime) -> str:
    """`"mercredi 29 juillet 2026"` — locale-independent."""
    return (
        f"{_FR_DAYS[value.weekday()]} {value.day} "
        f"{_FR_MONTHS[value.month - 1]} {value.year}"
    )


def short_date_fr(value: date | datetime) -> str:
    """`"29 juil. 2026"`."""
    month = _FR_MONTHS[value.month - 1]
    short = month[:4] + "." if len(month) > 5 else month
    return f"{value.day} {short} {value.year}"


def day(value: Any, fmt: str = "%d %b %Y") -> str:
    """Format a date-like value defensively."""
    if _is_missing(value):
        return PLACEHOLDER
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if isinstance(value, (datetime, date)):
        return value.strftime(fmt)
    return str(value)


def time_ago(value: Any) -> str:
    """Human-readable relative time, e.g. `3h ago`."""
    if _is_missing(value):
        return PLACEHOLDER
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if not isinstance(value, datetime):
        return str(value)

    now = datetime.now(tz=value.tzinfo) if value.tzinfo else datetime.now()
    seconds = max(0.0, (now - value).total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    if seconds < 604800:
        return f"{int(seconds // 86400)}d ago"
    return value.strftime("%d %b")
