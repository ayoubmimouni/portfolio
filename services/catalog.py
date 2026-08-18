# -*- coding: utf-8 -*-
"""ETF universe metadata.

Ticker, sector label and region are the same values the backend uses
(`api.ETF_METADATA` / `backend.forecaster.REGION_MAPPING`); this module only
adds presentation-level grouping (theme bucket) used by the UI for filters and
colour coding. Nothing here is a market data point — live figures always come
from `services.market`.
"""

from __future__ import annotations

from typing import Final, NamedTuple


class Etf(NamedTuple):
    ticker: str
    sector: str
    region: str
    theme: str


# Order matters: it is the default display order of the universe.
UNIVERSE: Final[tuple[Etf, ...]] = (
    Etf("IYW", "US Technology", "North America", "Technology"),
    Etf("PSI", "Semiconductors", "North America", "Technology"),
    Etf("PTLC", "Large Cap", "North America", "Broad Market"),
    Etf("UTES", "Utilities", "North America", "Utilities"),
    Etf("FXU", "Utilities Alpha", "North America", "Utilities"),
    Etf("NLR", "Nuclear Energy", "Developed Markets", "Energy"),
    Etf("NANR", "Natural Resources", "North America", "Resources"),
    Etf("GUNR", "Global Resources", "Developed Markets", "Resources"),
    Etf("PICK", "Metals & Mining", "Developed Markets", "Materials"),
    Etf("RING", "Gold Miners", "Developed Markets", "Materials"),
    Etf("LIT", "Lithium & Battery", "Developed Markets", "Materials"),
    Etf("XCEM", "Emerging Markets", "Emerging Markets", "Broad Market"),
)

BY_TICKER: Final[dict[str, Etf]] = {etf.ticker: etf for etf in UNIVERSE}

TICKERS: Final[tuple[str, ...]] = tuple(etf.ticker for etf in UNIVERSE)

REGIONS: Final[tuple[str, ...]] = ("North America", "Developed Markets", "Emerging Markets")

THEMES: Final[tuple[str, ...]] = (
    "Technology", "Broad Market", "Utilities", "Energy", "Resources", "Materials",
)

# The selection the original application opened with — kept as the default
# portfolio universe so returning users see the same starting point.
DEFAULT_SELECTION: Final[tuple[str, ...]] = ("IYW", "PSI", "NLR", "UTES", "PTLC", "FXU")

# Reference index used as the portfolio benchmark on the analytics pages.
BENCHMARK: Final[str] = "SPY"
BENCHMARK_LABEL: Final[str] = "S&P 500 (SPY)"


def sector_of(ticker: str) -> str:
    etf = BY_TICKER.get(ticker)
    return etf.sector if etf else ticker


def region_of(ticker: str) -> str:
    etf = BY_TICKER.get(ticker)
    return etf.region if etf else "Other"


def theme_of(ticker: str) -> str:
    etf = BY_TICKER.get(ticker)
    return etf.theme if etf else "Other"


def label(ticker: str) -> str:
    """`"IYW — US Technology"`, used in select widgets."""
    etf = BY_TICKER.get(ticker)
    return f"{ticker} — {etf.sector}" if etf else ticker
