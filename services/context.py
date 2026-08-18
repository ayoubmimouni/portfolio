# -*- coding: utf-8 -*-
"""Per-run application context.

`app.py` resolves market data and account valuation once per script run and
publishes it here; pages read it instead of re-fetching. Since `st.Page` targets
take no arguments, this is the injection point for shared state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import streamlit as st

_KEY = "_app_context"


@dataclass
class AppContext:
    """Snapshot of everything a page needs about "now"."""

    quotes: pd.DataFrame
    valuation: dict[str, Any]
    market: dict[str, Any]
    api_online: bool
    benchmark: pd.DataFrame | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def has_quotes(self) -> bool:
        return self.quotes is not None and not self.quotes.empty

    def quote(self, ticker: str) -> dict[str, Any] | None:
        """Single-ticker row as a dict, or None when unavailable."""
        if not self.has_quotes:
            return None
        rows = self.quotes[self.quotes["ticker"] == ticker]
        return None if rows.empty else rows.iloc[0].to_dict()

    def price(self, ticker: str) -> float | None:
        row = self.quote(ticker)
        return None if row is None else float(row["price"])

    def rows(self, tickers: list[str]) -> pd.DataFrame:
        """Quotes for a subset, preserving the requested order."""
        if not self.has_quotes:
            return pd.DataFrame()
        subset = self.quotes[self.quotes["ticker"].isin(tickers)].copy()
        order = {ticker: i for i, ticker in enumerate(tickers)}
        return subset.sort_values("ticker", key=lambda s: s.map(order))


def publish(context: AppContext) -> None:
    st.session_state[_KEY] = context


def get() -> AppContext:
    context = st.session_state.get(_KEY)
    if context is None:  # defensive: a page opened before the shell ran
        context = AppContext(pd.DataFrame(), {}, {}, False)
    return context
