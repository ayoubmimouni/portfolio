# -*- coding: utf-8 -*-
"""Design tokens — the single source of truth for the Optiport design system.

Everything visual derives from this module: the injected CSS variables
(`ui.styles`), the Plotly chart template (`ui.charts`) and the inline styles of
custom components (`ui.components`). `.streamlit/config.toml` mirrors the
default palette so native Streamlit widgets match without CSS overrides.

Changing a value here propagates through the whole application.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
#  Color palettes
# ---------------------------------------------------------------------------
# Two production-grade dark palettes. "midnight" is the reference navy palette;
# "graphite" is a neutral variant for users who prefer lower color temperature.
# Both share the same semantic keys so any component works with either.

MIDNIGHT: Final[dict[str, str]] = {
    # Surfaces, from deepest to most elevated
    "bg_root": "#070C15",
    "bg": "#0B1220",
    "bg_alt": "#111827",
    "surface": "#1E293B",
    "surface_hi": "#243449",
    "surface_low": "#16213A",
    "sidebar": "#080E1A",
    "sidebar_hi": "#141F35",
    # Borders
    "border": "#334155",
    "border_soft": "rgba(51, 65, 85, 0.55)",
    "border_strong": "#41526B",
    # Text
    "text": "#FFFFFF",
    "text_soft": "#E2E8F0",
    "text_muted": "#94A3B8",
    # Lightened from the classic slate-500 so captions clear WCAG AA (4.5:1)
    # against the #0B1220 background — measured at 4.6:1.
    "text_faint": "#7C8AA3",
    # Brand / accent
    "accent": "#3B82F6",
    "accent_hi": "#60A5FA",
    "accent_lo": "#2563EB",
    "accent_soft": "rgba(59, 130, 246, 0.12)",
    "accent_glow": "rgba(59, 130, 246, 0.35)",
    # Semantic
    "up": "#22C55E",
    "up_soft": "rgba(34, 197, 94, 0.12)",
    "up_text": "#4ADE80",
    "down": "#EF4444",
    "down_soft": "rgba(239, 68, 68, 0.12)",
    "down_text": "#F87171",
    "warn": "#F59E0B",
    "warn_soft": "rgba(245, 158, 11, 0.12)",
    "warn_text": "#FBBF24",
    "info": "#06B6D4",
    "info_soft": "rgba(6, 182, 212, 0.12)",
    "violet": "#8B5CF6",
    "violet_soft": "rgba(139, 92, 246, 0.12)",
    "neutral_soft": "rgba(148, 163, 184, 0.12)",
}

GRAPHITE: Final[dict[str, str]] = {
    **MIDNIGHT,
    "bg_root": "#0A0A0C",
    "bg": "#101114",
    "bg_alt": "#16181C",
    "surface": "#1E2126",
    "surface_hi": "#282C33",
    "surface_low": "#191C21",
    "sidebar": "#0C0D10",
    "sidebar_hi": "#181B20",
    "border": "#31363F",
    "border_soft": "rgba(49, 54, 63, 0.6)",
    "border_strong": "#414855",
    "text_soft": "#E4E6EB",
    "text_muted": "#9BA3AF",
    "text_faint": "#868E9C",
}

PALETTES: Final[dict[str, dict[str, str]]] = {
    "midnight": MIDNIGHT,
    "graphite": GRAPHITE,
}

DEFAULT_PALETTE: Final[str] = "midnight"

PALETTE_LABELS: Final[dict[str, str]] = {
    "midnight": "Midnight",
    "graphite": "Graphite",
}


def palette(name: str | None = None) -> dict[str, str]:
    """Return a palette by name, falling back to the default."""
    return PALETTES.get(name or DEFAULT_PALETTE, MIDNIGHT)


# ---------------------------------------------------------------------------
#  Spacing — 4px base scale
# ---------------------------------------------------------------------------
SPACING: Final[dict[str, str]] = {
    "0": "0",
    "1": "0.25rem",   # 4
    "2": "0.5rem",    # 8
    "3": "0.75rem",   # 12
    "4": "1rem",      # 16
    "5": "1.25rem",   # 20
    "6": "1.5rem",    # 24
    "7": "2rem",      # 32
    "8": "2.5rem",    # 40
    "9": "3rem",      # 48
    "10": "4rem",     # 64
}

# ---------------------------------------------------------------------------
#  Radius
# ---------------------------------------------------------------------------
RADIUS: Final[dict[str, str]] = {
    "xs": "0.25rem",
    "sm": "0.5rem",
    "md": "0.75rem",
    "lg": "1rem",
    "xl": "1.25rem",
    "2xl": "1.5rem",
    "pill": "999px",
}

# ---------------------------------------------------------------------------
#  Elevation
# ---------------------------------------------------------------------------
SHADOW: Final[dict[str, str]] = {
    "xs": "0 1px 2px rgba(2, 6, 23, 0.4)",
    "sm": "0 2px 6px -1px rgba(2, 6, 23, 0.45)",
    "md": "0 6px 20px -6px rgba(2, 6, 23, 0.65)",
    "lg": "0 16px 40px -12px rgba(2, 6, 23, 0.8)",
    "xl": "0 28px 64px -20px rgba(2, 6, 23, 0.9)",
    "inset": "inset 0 1px 0 rgba(255, 255, 255, 0.04)",
    "focus": "0 0 0 3px rgba(59, 130, 246, 0.35)",
}

# ---------------------------------------------------------------------------
#  Typography
# ---------------------------------------------------------------------------
FONT_SANS: Final[str] = (
    "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "'Helvetica Neue', Arial, sans-serif"
)
FONT_MONO: Final[str] = (
    "'JetBrains Mono', ui-monospace, SFMono-Regular, 'SF Mono', Consolas, "
    "'Liberation Mono', monospace"
)

FONT_SIZE: Final[dict[str, str]] = {
    "2xs": "0.6875rem",  # 11
    "xs": "0.75rem",     # 12
    "sm": "0.8125rem",   # 13
    "base": "0.875rem",  # 14
    "md": "0.9375rem",   # 15
    "lg": "1.0625rem",   # 17
    "xl": "1.25rem",     # 20
    "2xl": "1.5rem",     # 24
    "3xl": "1.875rem",   # 30
    "4xl": "2.375rem",   # 38
}

FONT_WEIGHT: Final[dict[str, int]] = {
    "regular": 400,
    "medium": 500,
    "semibold": 600,
    "bold": 700,
    "black": 800,
}

# ---------------------------------------------------------------------------
#  Motion
# ---------------------------------------------------------------------------
MOTION: Final[dict[str, str]] = {
    "fast": "120ms cubic-bezier(0.4, 0, 0.2, 1)",
    "base": "200ms cubic-bezier(0.4, 0, 0.2, 1)",
    "slow": "320ms cubic-bezier(0.16, 1, 0.3, 1)",
    "spring": "480ms cubic-bezier(0.34, 1.36, 0.64, 1)",
}

# ---------------------------------------------------------------------------
#  Layout
# ---------------------------------------------------------------------------
LAYOUT: Final[dict[str, str]] = {
    "sidebar_width": "16.5rem",
    "topbar_height": "3.5rem",
    "content_max": "1680px",
    "gutter": "1.25rem",
}

# ---------------------------------------------------------------------------
#  Chart palettes — mirrored in .streamlit/config.toml
# ---------------------------------------------------------------------------
CHART_CATEGORICAL: Final[tuple[str, ...]] = (
    "#3B82F6", "#22C55E", "#F59E0B", "#8B5CF6", "#06B6D4", "#EC4899",
    "#14B8A6", "#F97316", "#6366F1", "#84CC16", "#A855F7", "#0EA5E9",
)

CHART_SEQUENTIAL: Final[tuple[str, ...]] = (
    "#0B1F3A", "#12325C", "#1A467F", "#215BA2", "#2970C5", "#3B82F6",
    "#5B9BF8", "#8CBAFB", "#BDD7FD", "#E3EDFE",
)

# ---------------------------------------------------------------------------
#  Domain color mappings — keep signals and regions visually stable app-wide
# ---------------------------------------------------------------------------
SIGNAL_TONE: Final[dict[str, str]] = {
    "Strong Buy": "up",
    "Buy": "up",
    "Hold": "warn",
    "Light": "info",
    "Reduce": "down",
    "Avoid": "down",
}

REGION_COLOR: Final[dict[str, str]] = {
    "North America": "#3B82F6",
    "Developed Markets": "#8B5CF6",
    "Emerging Markets": "#F59E0B",
    "Other": "#64748B",
}

# Risk profile → optimizer strategy. Mirrors the mapping the original app used,
# kept here so both the UI labels and the API payload share one definition.
RISK_PROFILES: Final[dict[str, dict[str, str]]] = {
    "Conservative": {
        "strategy": "min_volatility",
        "icon": "shield",
        "caption": "Minimise la volatilité du portefeuille",
    },
    "Balanced": {
        "strategy": "risk_parity",
        "icon": "balance",
        "caption": "Contribution au risque égale entre actifs",
    },
    "Growth": {
        "strategy": "max_sharpe",
        "icon": "rocket_launch",
        "caption": "Maximise le rendement ajusté du risque",
    },
    "Equal Weight": {
        "strategy": "equal_weight",
        "icon": "grid_view",
        "caption": "Allocation uniforme, sans optimisation",
    },
}
