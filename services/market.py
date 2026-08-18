# -*- coding: utf-8 -*-
"""Market data access and derived indicators.

Everything is fetched from Yahoo Finance through yfinance and cached with
`st.cache_data`, so a page render costs at most one network round trip per
(tickers, period) pair. Indicator formulas mirror `backend/forecaster.py`
(RSI-14, momentum over 21/63/126 sessions, 52-week position) so a number shown
on a market page means the same thing as the feature the model was trained on.

All functions degrade gracefully: on any failure they return an empty frame or
`None`, and the views render an explicit "data unavailable" state rather than
crashing or showing a fabricated value.
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")

PERIODS: dict[str, str] = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1A": "1y",
    "2A": "2y",
    "5A": "5y",
}


# ---------------------------------------------------------------------------
#  Raw downloads
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def _download(tickers: tuple[str, ...], period: str, interval: str) -> pd.DataFrame:
    """Batched OHLCV download. Empty frame on failure."""
    if not tickers:
        return pd.DataFrame()
    try:
        data = yf.download(
            tickers=list(tickers),
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as exc:  # network, rate limit, symbol errors…
        logger.warning("yfinance download failed for %s: %s", tickers, exc)
        return pd.DataFrame()
    return data if isinstance(data, pd.DataFrame) else pd.DataFrame()


def _field(data: pd.DataFrame, field: str, tickers: Sequence[str]) -> pd.DataFrame:
    """Extract one OHLCV field as a `ticker -> series` frame."""
    if data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        if field not in data.columns.get_level_values(0):
            return pd.DataFrame()
        frame = data[field].copy()
    else:
        if field not in data.columns:
            return pd.DataFrame()
        frame = data[[field]].copy()
        frame.columns = [tickers[0]]
    frame.columns = [str(c) for c in frame.columns]
    return frame.dropna(how="all")


def closes(tickers: Sequence[str], period: str = "1y") -> pd.DataFrame:
    """Close prices, one column per ticker."""
    keys = tuple(dict.fromkeys(tickers))
    return _field(_download(keys, period, "1d"), "Close", keys)


def volumes(tickers: Sequence[str], period: str = "1y") -> pd.DataFrame:
    keys = tuple(dict.fromkeys(tickers))
    return _field(_download(keys, period, "1d"), "Volume", keys)


def ohlcv(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Full OHLCV frame for a single instrument, indexed by date."""
    data = _download((ticker,), period, interval)
    if data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        frame = pd.DataFrame({
            field: data[field][ticker]
            for field in ("Open", "High", "Low", "Close", "Volume")
            if field in data.columns.get_level_values(0)
            and ticker in data[field].columns
        })
    else:
        frame = data[[c for c in ("Open", "High", "Low", "Close", "Volume")
                      if c in data.columns]].copy()
    return frame.dropna(how="all")


# ---------------------------------------------------------------------------
#  Indicators
# ---------------------------------------------------------------------------

def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index — same formulation as backend/forecaster.py."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
    rs = gain / (loss + 1e-8)
    return 100 - (100 / (1 + rs))


def max_drawdown(series: pd.Series) -> float:
    """Worst peak-to-trough decline over the series, in percent."""
    if series.empty:
        return float("nan")
    peak = series.cummax()
    return float(((series - peak) / peak).min() * 100)


def drawdown_series(series: pd.Series) -> pd.Series:
    peak = series.cummax()
    return (series - peak) / peak * 100


def _pct_change_over(series: pd.Series, sessions: int) -> float:
    """Return over the last `sessions` trading days, in percent."""
    clean = series.dropna()
    if len(clean) <= sessions:
        return float("nan")
    first, last = clean.iloc[-sessions - 1], clean.iloc[-1]
    if not first:
        return float("nan")
    return float((last / first - 1) * 100)


def ytd_return(series: pd.Series) -> float:
    clean = series.dropna()
    if clean.empty:
        return float("nan")
    year_start = pd.Timestamp(datetime.now().year, 1, 1)
    if clean.index.tz is not None:
        year_start = year_start.tz_localize(clean.index.tz)
    window = clean[clean.index >= year_start]
    if len(window) < 2:
        return float("nan")
    return float((window.iloc[-1] / window.iloc[0] - 1) * 100)


# ---------------------------------------------------------------------------
#  Composite technical signal
# ---------------------------------------------------------------------------

# Transparent, rule-based score. It is a technical composite computed from
# public price history — not a recommendation from the LSTM model, and not an
# external rating. The UI always labels it as such.
SIGNAL_RULES = (
    "Momentum 1M/3M/6M, position dans le range 52 semaines, RSI-14 et "
    "position vs moyenne mobile 50 séances."
)


def technical_score(
    *,
    mom_1m: float,
    mom_3m: float,
    mom_6m: float,
    rsi_14: float,
    position_52w: float,
    above_ma50: bool,
) -> float:
    """Composite score in roughly [-5, +5]. Higher means stronger technicals."""
    score = 0.0
    for value, weight in ((mom_1m, 1.0), (mom_3m, 1.5), (mom_6m, 1.0)):
        if not np.isnan(value):
            score += weight if value > 0 else -weight

    if not np.isnan(rsi_14):
        if rsi_14 > 70:
            score -= 0.5           # overbought
        elif rsi_14 >= 50:
            score += 1.0
        elif rsi_14 >= 30:
            score -= 0.5
        # below 30 is oversold: neither confirmation nor penalty

    if not np.isnan(position_52w):
        if position_52w > 0.8:
            score += 1.0
        elif position_52w < 0.2:
            score -= 1.0

    score += 1.0 if above_ma50 else -1.0
    return round(score, 2)


def signal_from_score(score: float) -> str:
    if np.isnan(score):
        return "Hold"
    if score >= 3.5:
        return "Strong Buy"
    if score >= 2.0:
        return "Buy"
    if score >= 0.0:
        return "Hold"
    if score >= -2.0:
        return "Reduce"
    return "Avoid"


# ---------------------------------------------------------------------------
#  Snapshot table
# ---------------------------------------------------------------------------

SPARK_POINTS = 30


@st.cache_data(ttl=300, show_spinner=False)
def snapshot(tickers: tuple[str, ...], period: str = "2y") -> pd.DataFrame:
    """One row per ticker with quote, performance, risk and signal columns.

    This is the backbone of the Markets, Watchlist and Portfolio pages.
    """
    close = closes(tickers, period)
    if close.empty:
        return pd.DataFrame()

    volume = volumes(tickers, period)
    rows: list[dict[str, Any]] = []

    for ticker in tickers:
        if ticker not in close.columns:
            continue
        series = close[ticker].dropna()
        if len(series) < 2:
            continue

        last = float(series.iloc[-1])
        previous = float(series.iloc[-2])
        window_52w = series.tail(252)
        high_52w, low_52w = float(window_52w.max()), float(window_52w.min())
        span = (high_52w - low_52w) or 1.0
        position_52w = (last - low_52w) / span
        rsi_14 = float(rsi(series).iloc[-1]) if len(series) > 15 else float("nan")
        ma50 = float(series.tail(50).mean()) if len(series) >= 50 else float("nan")
        daily = series.pct_change().dropna()

        mom_1m = _pct_change_over(series, 21)
        mom_3m = _pct_change_over(series, 63)
        mom_6m = _pct_change_over(series, 126)

        score = technical_score(
            mom_1m=mom_1m, mom_3m=mom_3m, mom_6m=mom_6m,
            rsi_14=rsi_14, position_52w=position_52w,
            above_ma50=bool(not np.isnan(ma50) and last > ma50),
        )

        avg_volume = float("nan")
        last_volume = float("nan")
        if not volume.empty and ticker in volume.columns:
            vol_series = volume[ticker].dropna()
            if not vol_series.empty:
                last_volume = float(vol_series.iloc[-1])
                avg_volume = float(vol_series.tail(63).mean())

        rows.append({
            "ticker": ticker,
            "price": last,
            "previous_close": previous,
            "change_pct": (last / previous - 1) * 100 if previous else float("nan"),
            "change_abs": last - previous,
            "return_5d": _pct_change_over(series, 5),
            "return_1m": mom_1m,
            "return_3m": mom_3m,
            "return_6m": mom_6m,
            "return_1y": _pct_change_over(series, 252),
            "ytd": ytd_return(series),
            "volatility": float(daily.tail(252).std() * np.sqrt(252) * 100)
                          if len(daily) > 20 else float("nan"),
            "max_drawdown": max_drawdown(window_52w),
            "rsi": rsi_14,
            "position_52w": position_52w * 100,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "volume": last_volume,
            "avg_volume": avg_volume,
            "turnover": last_volume * last if not np.isnan(last_volume) else float("nan"),
            "score": score,
            "signal": signal_from_score(score),
            "spark": series.tail(SPARK_POINTS).tolist(),
        })

    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def fund_stats(ticker: str) -> dict[str, Any]:
    """Shares outstanding and estimated net assets from Yahoo's quote endpoint.

    Yahoo does not expose `marketCap` for ETFs, so net assets are estimated as
    shares outstanding × last price. Returns an empty dict when unavailable —
    the UI then renders a placeholder instead of a guess.
    """
    try:
        info = yf.Ticker(ticker).fast_info
        shares = info.get("shares")
        price = info.get("lastPrice")
        stats: dict[str, Any] = {
            "currency": info.get("currency"),
            "exchange": info.get("exchange"),
            "quote_type": info.get("quoteType"),
            "shares": shares,
            "year_high": info.get("yearHigh"),
            "year_low": info.get("yearLow"),
            "avg_volume_3m": info.get("threeMonthAverageVolume"),
            "ma_50": info.get("fiftyDayAverage"),
            "ma_200": info.get("twoHundredDayAverage"),
        }
        if shares and price:
            stats["net_assets"] = float(shares) * float(price)
        return stats
    except Exception as exc:
        logger.info("fast_info unavailable for %s: %s", ticker, exc)
        return {}


# ---------------------------------------------------------------------------
#  News
# ---------------------------------------------------------------------------

@st.cache_data(ttl=900, show_spinner=False)
def news(tickers: tuple[str, ...], limit_per_ticker: int = 6) -> list[dict[str, Any]]:
    """Real headlines from Yahoo Finance for the given tickers.

    Returns a de-duplicated list sorted newest first. Never synthesised: an
    empty list means the feed was unavailable, and the page says so.
    """
    collected: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        try:
            items = yf.Ticker(ticker).get_news(count=limit_per_ticker) or []
        except Exception as exc:
            logger.info("news unavailable for %s: %s", ticker, exc)
            continue

        for item in items:
            content = item.get("content", item) or {}
            title = content.get("title")
            if not title:
                continue
            url = ((content.get("canonicalUrl") or {}).get("url")
                   or (content.get("clickThroughUrl") or {}).get("url"))
            published = content.get("pubDate") or content.get("displayTime")
            timestamp: datetime | None = None
            if published:
                try:
                    timestamp = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
                except ValueError:
                    timestamp = None

            key = str(item.get("id") or title)
            if key in collected:
                collected[key]["tickers"].add(ticker)
                continue
            collected[key] = {
                "title": title,
                "summary": (content.get("summary") or content.get("description") or "").strip(),
                "url": url,
                "provider": ((content.get("provider") or {}).get("displayName") or "Yahoo Finance"),
                "published": timestamp,
                "tickers": {ticker},
            }

    results = list(collected.values())
    results.sort(key=lambda item: item["published"] or datetime.min.replace(tzinfo=None),
                 reverse=True)
    for item in results:
        item["tickers"] = sorted(item["tickers"])
    return results


# ---------------------------------------------------------------------------
#  Session clock
# ---------------------------------------------------------------------------

OPEN_TIME = time(9, 30)
CLOSE_TIME = time(16, 0)


def market_status(now: datetime | None = None) -> dict[str, Any]:
    """US equity session state, based on New York time.

    Regular hours only (09:30–16:00, Mon–Fri). Exchange holidays are not
    modelled, so a holiday reads as "closed" only outside those hours — the
    label stays honest by describing the schedule, not asserting a calendar.
    """
    current = (now or datetime.now(NY)).astimezone(NY)
    weekday = current.weekday()
    local_time = current.time()

    if weekday >= 5:
        state, label = "closed", "Marché fermé · week-end"
    elif local_time < OPEN_TIME:
        state, label = "pre", "Pré-ouverture"
    elif local_time <= CLOSE_TIME:
        state, label = "open", "Marché ouvert"
    else:
        state, label = "post", "Après-clôture"

    return {
        "state": state,
        "label": label,
        "clock": current.strftime("%H:%M"),
        "zone": "NY",
        "is_open": state == "open",
    }
