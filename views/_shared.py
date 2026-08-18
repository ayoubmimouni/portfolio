# -*- coding: utf-8 -*-
"""Helpers shared by several pages.

Keeps the market table definition, the period selector and the instrument
detail panel in one place so Markets, Watchlist, Portfolio and Analytics stay
visually and behaviourally identical.
"""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd
import streamlit as st

from services import catalog, market, store
from services.context import AppContext
from ui import charts, components as c
from ui.format import (compact_money, compact_number, percent, price, ratio,
                       signed_percent)
from ui.icons import st_icon

PERIOD_LABELS = list(market.PERIODS)


# ---------------------------------------------------------------------------
#  Controls
# ---------------------------------------------------------------------------

def period_selector(key: str, default: str | None = None) -> str:
    """Segmented period control. Returns a yfinance period string."""
    default = default or store.prefs().get("chart_period", "6M")
    label = st.segmented_control(
        "Période",
        PERIOD_LABELS,
        default=default if default in PERIOD_LABELS else "6M",
        key=key,
        label_visibility="collapsed",
    ) or default
    return market.PERIODS.get(label, "6mo")


def enrich(quotes: pd.DataFrame) -> pd.DataFrame:
    """Add catalog metadata columns used for display and filtering."""
    if quotes.empty:
        return quotes
    frame = quotes.copy()
    frame["sector"] = frame["ticker"].map(catalog.sector_of)
    frame["region"] = frame["ticker"].map(catalog.region_of)
    frame["theme"] = frame["ticker"].map(catalog.theme_of)
    frame["watched"] = frame["ticker"].map(store.is_watched)
    return frame


@st.cache_data(ttl=3600, show_spinner=False)
def aum_map(tickers: tuple[str, ...]) -> dict[str, float]:
    """Estimated net assets per ticker (shares outstanding × price).

    Yahoo does not publish `marketCap` for ETFs, so this is an estimate and the
    table labels it as such. Missing values are simply absent from the mapping.
    """
    result: dict[str, float] = {}
    for ticker in tickers:
        stats = market.fund_stats(ticker)
        if stats.get("net_assets"):
            result[ticker] = float(stats["net_assets"])
    return result


# ---------------------------------------------------------------------------
#  Market table
# ---------------------------------------------------------------------------

def _ticker_cell(value: Any, row: pd.Series) -> str:
    return c.instrument_html(str(value), None)


def _sector_cell(value: Any, row: pd.Series) -> str:
    return (
        f'<span class="opt-td--strong">{c.esc(value)}</span>'
        f'<div class="opt-caption">{c.esc(row.get("region", ""))}</div>'
    )


def _price_cell(value: Any, row: pd.Series) -> str:
    return f'<span class="opt-num opt-td--strong">{c.esc(price(value))}</span>'


def _change_cell(value: Any, row: pd.Series) -> str:
    return c.delta_html(value)


def _volume_cell(value: Any, row: pd.Series) -> str:
    average = row.get("avg_volume")
    relative = ""
    if average and value and average > 0:
        ratio_value = value / average
        tone = "up" if ratio_value >= 1 else "flat"
        relative = f'<div class="opt-caption">{ratio_value:.2f}× moy. 3M</div>' if tone else ""
    return f'<span class="opt-num">{c.esc(compact_number(value))}</span>{relative}'


def _aum_cell(value: Any, row: pd.Series) -> str:
    if value is None or pd.isna(value):
        return '<span class="opt-faint">—</span>'
    return f'<span class="opt-num">{c.esc(compact_money(value))}</span>'


def _signal_cell(value: Any, row: pd.Series) -> str:
    return c.signal_html(str(value))


def _ytd_cell(value: Any, row: pd.Series) -> str:
    return (
        f'<div class="opt-num" style="font-weight:600;color:'
        f'{"var(--opt-up-text)" if (value or 0) >= 0 else "var(--opt-down-text)"}">'
        f'{c.esc(signed_percent(value, 1))}</div>{c.diverging_bar_html(value, scale=30)}'
    )


def _spark_cell(value: Any, row: pd.Series) -> str:
    return c.sparkline_html(value or [], width=110, height=30)


def _actions_cell(value: Any, row: pd.Series) -> str:
    watched = bool(row.get("watched"))
    star = c.chip_html(
        "Suivi" if watched else "Libre",
        tone="warn" if watched else "flat",
        icon="star" if watched else "star_outline",
        title="Présent dans la watchlist" if watched else "Absent de la watchlist",
    )
    held = row["ticker"] in store.positions()
    position = c.chip_html("En position", tone="info", icon="portfolio") if held else ""
    return f'<div class="opt-row" style="justify-content:flex-end">{star}{position}</div>'


def market_columns(*, with_aum: bool = False) -> list[c.Column]:
    """Column set for the market board."""
    columns = [
        c.Column("ticker", "Ticker", align="left", render=_ticker_cell),
        c.Column("sector", "Secteur", align="left", render=_sector_cell),
        c.Column("price", "Prix", render=_price_cell),
        c.Column("change_pct", "Variation", render=_change_cell,
                 help="Variation depuis la clôture précédente"),
        c.Column("volume", "Volume", render=_volume_cell,
                 help="Volume de la dernière séance, comparé à la moyenne 3 mois"),
    ]
    if with_aum:
        columns.append(
            c.Column("aum", "Actifs", render=_aum_cell,
                     help="Actifs sous gestion estimés : parts en circulation × dernier cours")
        )
    columns += [
        c.Column("signal", "Signal", align="center", render=_signal_cell,
                 help=f"Signal technique composite. {market.SIGNAL_RULES}"),
        c.Column("ytd", "Performance YTD", render=_ytd_cell),
        c.Column("spark", "30 séances", render=_spark_cell, sortable=False),
        c.Column("watched", "Statut", render=_actions_cell, sortable=False),
    ]
    return columns


def market_table(quotes: pd.DataFrame, *, key: str, with_aum: bool = False,
                 filters: bool = True, page_size: int = 10) -> pd.DataFrame:
    """The premium market board with search, filters, sort and pagination."""
    frame = enrich(quotes)
    if with_aum and not frame.empty:
        assets = aum_map(tuple(frame["ticker"]))
        frame["aum"] = frame["ticker"].map(assets)

    table_filters: list[c.Filter] = []
    if filters:
        table_filters = [
            c.Filter("region", "Région", catalog.REGIONS),
            c.Filter("signal", "Signal", ("Strong Buy", "Buy", "Hold", "Reduce", "Avoid")),
        ]

    return c.data_table(
        frame,
        market_columns(with_aum=with_aum),
        key=key,
        search_keys=("ticker", "sector", "theme", "region"),
        filters=table_filters,
        page_size=page_size,
        default_sort="change_pct",
        default_desc=True,
    )


# ---------------------------------------------------------------------------
#  Instrument detail
# ---------------------------------------------------------------------------

def instrument_actions(ticker: str, ctx: AppContext, *, key_prefix: str) -> None:
    """Watch / trade / alert actions for one instrument."""
    row = ctx.quote(ticker)
    last = row["price"] if row else None
    columns = st.columns(3)

    watched = store.is_watched(ticker)
    if columns[0].button(
        "Retirer du suivi" if watched else "Ajouter au suivi",
        key=f"{key_prefix}_watch", width="stretch",
        icon=st_icon("star" if watched else "star_outline"),
    ):
        store.toggle_watch(ticker)
        st.rerun()

    if columns[1].button("Trader", key=f"{key_prefix}_trade", width="stretch",
                         icon=st_icon("trading"), type="primary"):
        store.select_ticker(ticker)
        from ui import layout
        layout.goto("trading")

    with columns[2].popover("Alerte", icon=st_icon("alerts"), width="stretch"):
        c.section("Nouvelle alerte", subtitle=f"Seuil de prix sur {ticker}", icon="alerts")
        direction = st.radio("Condition", ["above", "below"], horizontal=True,
                             format_func=lambda d: "Au-dessus de" if d == "above" else "Sous",
                             key=f"{key_prefix}_dir")
        threshold = st.number_input(
            "Seuil ($)", min_value=0.0,
            value=float(round(last, 2)) if last else 100.0,
            step=1.0, key=f"{key_prefix}_thr",
        )
        if st.button("Créer l'alerte", type="primary", width="stretch",
                     key=f"{key_prefix}_add"):
            store.add_alert(ticker, direction, threshold)
            st.toast(f"Alerte créée sur {ticker}", icon="🔔")
            st.rerun()


def instrument_stats(ticker: str, ctx: AppContext) -> None:
    """Quote statistics grid for one instrument."""
    row = ctx.quote(ticker)
    if row is None:
        c.empty_state("Cotation indisponible", f"Aucune donnée récente pour {ticker}.")
        return

    c.tiles([
        ("Dernier", price(row["price"])),
        ("Variation", signed_percent(row["change_pct"])),
        ("Volume", compact_number(row["volume"])),
        ("Volatilité 1A", percent(row["volatility"], 1)),
        ("Plus haut 52s", price(row["high_52w"])),
        ("Plus bas 52s", price(row["low_52w"])),
        ("RSI 14", ratio(row["rsi"], 1)),
        ("Drawdown 52s", percent(row["max_drawdown"], 1)),
    ])


def instrument_panel(ticker: str, ctx: AppContext, *, key_prefix: str = "detail") -> None:
    """Full detail panel: candles, statistics and actions."""
    row = ctx.quote(ticker)
    header_aside = ""
    if row is not None:
        header_aside = (
            c.delta_html(row["change_pct"])
            + c.signal_html(str(row["signal"]))
            + c.chip_html(catalog.region_of(ticker), tone="flat", icon="globe")
        )

    c.section(
        f"{ticker} · {catalog.sector_of(ticker)}",
        subtitle="Cours ajustés, moyennes mobiles 20/50 séances et volumes",
        icon="markets",
        aside=header_aside,
    )

    top = st.columns([3, 1], vertical_alignment="center")
    with top[0]:
        yf_period = period_selector(f"{key_prefix}_period_{ticker}")
    with top[1]:
        show_volume = st.toggle("Volumes", value=True, key=f"{key_prefix}_vol_{ticker}")

    with st.spinner("Chargement des cours…"):
        candles = market.ohlcv(ticker, yf_period)

    if candles.empty:
        c.error_state("Historique indisponible",
                      f"Yahoo Finance n'a pas renvoyé d'historique pour {ticker}.")
    else:
        st.plotly_chart(
            charts.candlestick(candles, show_volume=show_volume, height=380),
            width="stretch", theme=None, config=charts.CONFIG_INTERACTIVE,
        )

    instrument_stats(ticker, ctx)
    st.write("")
    instrument_actions(ticker, ctx, key_prefix=f"{key_prefix}_{ticker}")


# ---------------------------------------------------------------------------
#  Small building blocks reused across pages
# ---------------------------------------------------------------------------

def movers_block(quotes: pd.DataFrame, *, count: int = 4) -> None:
    """Top gainers and losers of the session."""
    if quotes.empty:
        c.empty_state("Aucune cotation", "Les variations apparaîtront ici.")
        return

    ranked = quotes.dropna(subset=["change_pct"]).sort_values("change_pct", ascending=False)
    columns = st.columns(2)
    for column, (title, subset, icon) in zip(
        columns,
        [("Hausses", ranked.head(count), "profit"),
         ("Baisses", ranked.tail(count).iloc[::-1], "loss")],
    ):
        with column:
            c.section(title, icon=icon)
            rows = []
            for _, row in subset.iterrows():
                rows.append(
                    '<div class="opt-kv__row">'
                    f'<span class="opt-kv__k">{c.instrument_html(row["ticker"], catalog.sector_of(row["ticker"]))}</span>'
                    f'<span class="opt-kv__v">{c.delta_html(row["change_pct"])}</span></div>'
                )
            c.render(f'<div class="opt-kv">{"".join(rows)}</div>')


def strip_block(quotes: pd.DataFrame, tickers: Sequence[str] | None = None) -> None:
    """Quote strip used at the top of Dashboard and Markets."""
    if quotes.empty:
        return
    frame = quotes if tickers is None else quotes[quotes["ticker"].isin(tickers)]
    c.market_strip([
        {
            "ticker": row["ticker"],
            "price": price(row["price"]),
            "change": row["change_pct"],
        }
        for _, row in frame.iterrows()
    ])


def account_note() -> None:
    """One-line reminder that the account is simulated."""
    c.caption(
        "Compte de démonstration : les ordres et le solde sont simulés, "
        "les cours et historiques proviennent de Yahoo Finance."
    )
