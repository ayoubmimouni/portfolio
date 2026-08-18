# -*- coding: utf-8 -*-
"""Portfolio analytics computed from price history.

These are *display* analytics for the dashboard, portfolio and analytics pages
(equity curve, benchmark comparison, risk metrics, correlation, contribution).
The allocation logic itself — expected returns and optimal weights — stays in
`backend/optimizer.py` and `backend/forecaster.py` and is only ever obtained
through the API.

Every function is pure and tolerant of missing data: it returns an empty
Series/DataFrame or NaN rather than raising, so pages can render an explicit
"unavailable" state.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from services import market

TRADING_DAYS = 252


# ---------------------------------------------------------------------------
#  Series construction
# ---------------------------------------------------------------------------

def normalized(prices: pd.DataFrame, base: float = 100.0) -> pd.DataFrame:
    """Rebase every column to `base` at its first valid observation."""
    if prices.empty:
        return prices
    clean = prices.dropna(how="all").ffill()
    first = clean.bfill().iloc[0]
    first = first.replace(0, np.nan)
    return clean.divide(first, axis=1) * base


def weighted_index(prices: pd.DataFrame, weights: Mapping[str, float],
                   base: float = 100.0) -> pd.Series:
    """Rebased index of a weighted basket (weights need not sum to 1)."""
    usable = [t for t in weights if t in prices.columns and weights[t] > 0]
    if not usable:
        return pd.Series(dtype=float)

    total = sum(weights[t] for t in usable)
    rebased = normalized(prices[usable], base=1.0)
    contributions = [rebased[t] * (weights[t] / total) for t in usable]
    return pd.concat(contributions, axis=1).sum(axis=1).dropna() * base


def equity_curve(holdings: Sequence[Mapping[str, Any]], cash: float,
                 period: str = "6mo") -> pd.Series:
    """Value of today's holdings across history, plus cash.

    Quantities are held constant, so the curve answers "what would this exact
    book have been worth?" rather than reconstructing past trades — the pages
    that display it label it accordingly.
    """
    tickers = [h["ticker"] for h in holdings if h.get("quantity")]
    if not tickers:
        return pd.Series(dtype=float)

    prices = market.closes(tickers, period)
    if prices.empty:
        return pd.Series(dtype=float)

    values = None
    for holding in holdings:
        ticker = holding["ticker"]
        if ticker not in prices.columns:
            continue
        line = prices[ticker].ffill() * float(holding["quantity"])
        values = line if values is None else values.add(line, fill_value=0.0)

    if values is None:
        return pd.Series(dtype=float)
    return (values + float(cash)).dropna()


# ---------------------------------------------------------------------------
#  Risk & performance metrics
# ---------------------------------------------------------------------------

def returns_of(series: pd.Series) -> pd.Series:
    return series.pct_change().dropna()


def annualized_volatility(series: pd.Series) -> float:
    daily = returns_of(series)
    if len(daily) < 5:
        return float("nan")
    return float(daily.std() * np.sqrt(TRADING_DAYS) * 100)


def annualized_return(series: pd.Series) -> float:
    clean = series.dropna()
    if len(clean) < 5:
        return float("nan")
    years = len(clean) / TRADING_DAYS
    if years <= 0 or clean.iloc[0] <= 0:
        return float("nan")
    return float(((clean.iloc[-1] / clean.iloc[0]) ** (1 / years) - 1) * 100)


def sharpe(series: pd.Series, risk_free: float = 0.05) -> float:
    volatility = annualized_volatility(series)
    performance = annualized_return(series)
    if np.isnan(volatility) or np.isnan(performance) or volatility == 0:
        return float("nan")
    return float((performance - risk_free * 100) / volatility)


def sortino(series: pd.Series, risk_free: float = 0.05) -> float:
    daily = returns_of(series)
    downside = daily[daily < 0]
    if downside.empty:
        return float("nan")
    downside_vol = float(downside.std() * np.sqrt(TRADING_DAYS) * 100)
    performance = annualized_return(series)
    if np.isnan(performance) or downside_vol == 0:
        return float("nan")
    return float((performance - risk_free * 100) / downside_vol)


def value_at_risk(series: pd.Series, confidence: float = 0.95) -> float:
    """Historical one-day VaR, expressed as a positive percentage of value."""
    daily = returns_of(series)
    if len(daily) < 30:
        return float("nan")
    return float(-np.percentile(daily, (1 - confidence) * 100) * 100)


def beta(series: pd.Series, benchmark: pd.Series) -> float:
    """Beta against a benchmark series, on aligned daily returns."""
    portfolio = returns_of(series)
    reference = returns_of(benchmark)
    aligned = pd.concat([portfolio, reference], axis=1, join="inner").dropna()
    if len(aligned) < 30:
        return float("nan")
    variance = aligned.iloc[:, 1].var()
    if not variance:
        return float("nan")
    return float(aligned.iloc[:, 0].cov(aligned.iloc[:, 1]) / variance)


def tracking_error(series: pd.Series, benchmark: pd.Series) -> float:
    aligned = pd.concat([returns_of(series), returns_of(benchmark)],
                        axis=1, join="inner").dropna()
    if len(aligned) < 30:
        return float("nan")
    spread = aligned.iloc[:, 0] - aligned.iloc[:, 1]
    return float(spread.std() * np.sqrt(TRADING_DAYS) * 100)


def rolling_volatility(series: pd.Series, window: int = 21) -> pd.Series:
    daily = returns_of(series)
    if len(daily) <= window:
        return pd.Series(dtype=float)
    return (daily.rolling(window).std() * np.sqrt(TRADING_DAYS) * 100).dropna()


def risk_profile(series: pd.Series, benchmark: pd.Series | None = None,
                 risk_free: float = 0.05) -> dict[str, float]:
    """The full risk panel used by Portfolio and Analytics."""
    profile = {
        "annual_return": annualized_return(series),
        "volatility": annualized_volatility(series),
        "sharpe": sharpe(series, risk_free),
        "sortino": sortino(series, risk_free),
        "max_drawdown": market.max_drawdown(series),
        "var_95": value_at_risk(series),
        "beta": float("nan"),
        "tracking_error": float("nan"),
    }
    if benchmark is not None and not benchmark.empty:
        profile["beta"] = beta(series, benchmark)
        profile["tracking_error"] = tracking_error(series, benchmark)
    return profile


# ---------------------------------------------------------------------------
#  Concentration & attribution
# ---------------------------------------------------------------------------

def herfindahl(weights: Sequence[float]) -> float:
    """Concentration index on weights given in percent."""
    fractions = np.array([w / 100.0 for w in weights if w and w > 0])
    if fractions.size == 0:
        return float("nan")
    return float(np.sum(fractions ** 2))


def diversification_score(weights: Sequence[float]) -> float:
    """`1 - HHI`, on the same 0–1 scale the backend reports."""
    index = herfindahl(weights)
    return float("nan") if np.isnan(index) else round(1 - index, 3)


def effective_holdings(weights: Sequence[float]) -> float:
    """Effective number of positions (inverse HHI)."""
    index = herfindahl(weights)
    return float("nan") if np.isnan(index) or index == 0 else round(1 / index, 1)


def risk_score(volatility: float, max_drawdown: float, concentration: float) -> float:
    """Composite 0–100 risk score (higher = riskier).

    Blends annualised volatility (capped at 40%), the 52-week drawdown (capped
    at 50%) and portfolio concentration. Transparent by design so the UI can
    explain it in a tooltip.
    """
    components: list[tuple[float, float]] = []   # (normalised 0-1 value, weight)
    if not np.isnan(volatility):
        components.append((min(volatility / 40.0, 1.0), 45.0))
    if not np.isnan(max_drawdown):
        components.append((min(abs(max_drawdown) / 50.0, 1.0), 35.0))
    if not np.isnan(concentration):
        components.append((min(concentration, 1.0), 20.0))
    if not components:
        return float("nan")

    total_weight = sum(weight for _, weight in components)
    weighted = sum(value * weight for value, weight in components)
    return round(weighted / total_weight * 100, 1)


def risk_label(score: float) -> tuple[str, str]:
    """`(label, tone)` for a composite risk score."""
    if np.isnan(score):
        return "N/A", "flat"
    if score < 30:
        return "Prudent", "up"
    if score < 50:
        return "Modéré", "info"
    if score < 70:
        return "Dynamique", "warn"
    return "Agressif", "down"


def contributions(holdings: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Per-position contribution to the unrealised P&L, in currency and percent."""
    rows = [
        {
            "ticker": h["ticker"],
            "pnl": h["pnl"],
            "weight": h["weight"] or 0.0,
            "pnl_pct": h["pnl_pct"],
        }
        for h in holdings if h.get("pnl") is not None
    ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values("pnl", ascending=False)


def correlation_matrix(tickers: Sequence[str], period: str = "1y") -> pd.DataFrame:
    """Correlation of daily returns between instruments."""
    prices = market.closes(tickers, period)
    if prices.empty or prices.shape[1] < 2:
        return pd.DataFrame()
    return prices.pct_change().dropna().corr()


def group_allocation(weights: Mapping[str, float],
                     mapping: Mapping[str, str]) -> pd.DataFrame:
    """Aggregate weights by a grouping (region, theme), sorted descending."""
    totals: dict[str, float] = {}
    for ticker, weight in weights.items():
        group = mapping.get(ticker, "Other")
        totals[group] = totals.get(group, 0.0) + float(weight)
    frame = pd.DataFrame(
        {"group": list(totals), "weight": list(totals.values())}
    )
    return frame.sort_values("weight", ascending=False).reset_index(drop=True)
