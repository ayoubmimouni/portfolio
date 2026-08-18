# -*- coding: utf-8 -*-
"""Dashboard — the operating cockpit: account KPIs, performance, allocation."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from services import analytics, catalog, store
from services.context import get as get_context
from ui import charts, components as c, layout
from ui.format import (compact_money, long_date_fr, money, percent, ratio,
                       signed_money, signed_percent, time_ago)
from ui.icons import st_icon
from views import _shared as shared

ctx = get_context()
valuation = ctx.valuation
holdings = valuation.get("holdings", [])

# ---------------------------------------------------------------------------
#  Header
# ---------------------------------------------------------------------------

c.page_header(
    "Vue d'ensemble",
    eyebrow=long_date_fr(datetime.now()),
    icon="dashboard",
    subtitle="Valorisation du compte, performance et exposition, actualisées "
             "sur les cours de clôture les plus récents.",
    aside=c.chip_html(f"{len(catalog.TICKERS)} ETF suivis", tone="flat", icon="database")
    + c.chip_html("Yahoo Finance", tone="info", icon="live"),
)

if not ctx.has_quotes:
    layout.data_unavailable_notice()
    st.stop()

shared.strip_block(ctx.quotes)

# ---------------------------------------------------------------------------
#  KPI grid
# ---------------------------------------------------------------------------

weights = {h["ticker"]: (h["weight"] or 0.0) for h in holdings}
equity_series = analytics.equity_curve(holdings, valuation["cash"], "6mo")

concentration = analytics.herfindahl(list(weights.values()))
risk: dict[str, float] = {}
if not equity_series.empty:
    risk = analytics.risk_profile(equity_series, None, store.prefs()["risk_free_rate"])

score = analytics.risk_score(
    risk.get("volatility", float("nan")),
    risk.get("max_drawdown", float("nan")),
    concentration,
)
score_label, score_tone = analytics.risk_label(score)
diversification = analytics.diversification_score(list(weights.values()))

day_pnl = valuation.get("day_pnl", 0.0)
profit_today = max(day_pnl, 0.0)
loss_today = min(day_pnl, 0.0)

c.kpi_row([
    c.kpi_html(
        "Valeur du portefeuille", money(valuation["equity"]),
        delta=valuation.get("day_pnl_pct"),
        hint="vs clôture précédente", icon="value", tone="accent",
        spark=equity_series.tail(30).tolist() if not equity_series.empty else None,
    ),
    c.kpi_html(
        "Gain du jour", money(profit_today), icon="profit", tone="up",
        footer=c.chip_html("Positions en hausse", tone="up")
        if profit_today > 0 else c.chip_html("Aucun gain", tone="flat"),
    ),
    c.kpi_html(
        "Perte du jour", money(abs(loss_today)), icon="loss", tone="down",
        footer=c.chip_html("Positions en baisse", tone="down")
        if loss_today < 0 else c.chip_html("Aucune perte", tone="flat"),
    ),
    c.kpi_html(
        "Liquidités disponibles", money(valuation["cash"]), icon="cash", tone="info",
        hint=f"{100 - valuation['invested_pct']:.0f}% du compte",
    ),
    c.kpi_html(
        "Actifs en portefeuille", str(valuation["positions_count"]), icon="assets",
        tone="violet",
        hint=f"{money(valuation['market_value'])} investis",
    ),
    c.kpi_html(
        "Performance totale", signed_percent(valuation["total_return_pct"]),
        delta=None, icon="return", tone="up" if valuation["total_return"] >= 0 else "down",
        footer=c.chip_html(signed_money(valuation["total_return"]),
                           tone="up" if valuation["total_return"] >= 0 else "down"),
        hint=f"depuis la dotation de {compact_money(store.INITIAL_CASH)}",
    ),
], min_width="14rem")

st.write("")

metric_columns = st.columns(3)
with metric_columns[0]:
    with c.card(key="risk"):
        c.section("Score de risque", icon="risk",
                  subtitle="Volatilité, drawdown et concentration")
        c.render(
            f'<div class="opt-row opt-row--between" style="margin:0.5rem 0 0.375rem">'
            f'<span class="opt-kpi__value opt-kpi__value--sm">{c.esc(ratio(score, 0))}'
            '<span class="opt-faint" style="font-size:var(--opt-fs-sm)">/100</span></span>'
            f'{c.chip_html(score_label, tone=score_tone)}</div>'
            + c.gauge_html(score if not np.isnan(score) else 0)
        )
        c.caption("0 = très prudent · 100 = très agressif")

with metric_columns[1]:
    with c.card(key="diversification"):
        c.section("Diversification", icon="diversification",
                  subtitle="1 − indice de Herfindahl")
        effective = analytics.effective_holdings(list(weights.values()))
        c.render(
            f'<div class="opt-kpi__value opt-kpi__value--sm" style="margin:0.5rem 0 0.5rem">'
            f'{c.esc(ratio(diversification) if not np.isnan(diversification) else "—")}</div>'
            + c.bar_html((diversification or 0) * 100 if not np.isnan(diversification) else 0,
                         color="var(--opt-violet)")
        )
        c.caption(
            f"≈ {ratio(effective, 1)} positions effectives"
            if not np.isnan(effective) else "Aucune position ouverte"
        )

with metric_columns[2]:
    with c.card(key="perfmetrics"):
        c.section("Indicateurs de performance", icon="performance",
                  subtitle="Sur les 6 derniers mois")
        c.kv_list([
            ("Rendement annualisé", percent(risk.get("annual_return", float("nan")), 1)),
            ("Volatilité annualisée", percent(risk.get("volatility", float("nan")), 1)),
            ("Ratio de Sharpe", ratio(risk.get("sharpe", float("nan")))),
            ("Drawdown maximum", percent(risk.get("max_drawdown", float("nan")), 1)),
        ])

st.write("")

# ---------------------------------------------------------------------------
#  Performance vs benchmark
# ---------------------------------------------------------------------------

main_columns = st.columns([2.05, 1])

with main_columns[0]:
    with c.card(key="perf"):
        c.section(
            "Performance du portefeuille",
            subtitle="Base 100 · portefeuille à pondérations actuelles vs "
                     f"{catalog.BENCHMARK_LABEL}",
            icon="performance",
            aside=c.chip_html("Valorisation à quantités constantes", tone="flat",
                              icon="info"),
        )
        yf_period = shared.period_selector("dash_period")

        if not weights:
            c.empty_state(
                "Aucune position ouverte",
                "Lancez une optimisation puis exécutez le plan de rééquilibrage "
                "pour suivre la performance du portefeuille.",
                icon="portfolio", variant="info",
            )
            if st.button("Ouvrir l'optimiseur", type="primary",
                         icon=st_icon("forecast"), key="dash_cta"):
                layout.goto("trading")
        else:
            from services import market as market_service

            prices = market_service.closes(
                [*weights, catalog.BENCHMARK], yf_period
            )
            if prices.empty:
                c.error_state("Historique indisponible",
                              "Les séries de prix n'ont pas pu être récupérées.")
            else:
                portfolio_index = analytics.weighted_index(prices, weights)
                frame = pd.DataFrame({"Date": portfolio_index.index,
                                      "Portefeuille": portfolio_index.values})
                if catalog.BENCHMARK in prices.columns:
                    reference = analytics.normalized(
                        prices[[catalog.BENCHMARK]]
                    )[catalog.BENCHMARK]
                    frame[catalog.BENCHMARK] = reference.reindex(
                        portfolio_index.index
                    ).values

                series = [col for col in ("Portefeuille", catalog.BENCHMARK)
                          if col in frame.columns]
                st.plotly_chart(
                    charts.multi_line(frame, x="Date", series=series, height=320,
                                      baseline=100),
                    width="stretch", theme=None, config=charts.CONFIG,
                )

                if len(series) > 1:
                    delta = frame["Portefeuille"].iloc[-1] - frame[catalog.BENCHMARK].iloc[-1]
                    c.render(
                        '<div class="opt-row opt-row--wrap">'
                        + c.chip_html(
                            f"Écart vs indice : {delta:+.2f} pts",
                            tone="up" if delta >= 0 else "down",
                            icon="benchmark")
                        + c.chip_html(
                            f"Portefeuille {frame['Portefeuille'].iloc[-1] - 100:+.2f}%",
                            tone="up" if frame['Portefeuille'].iloc[-1] >= 100 else "down")
                        + "</div>"
                    )

with main_columns[1]:
    with c.card(key="alloc"):
        c.section("Allocation", subtitle="Répartition des positions", icon="allocation")
        if not weights:
            c.empty_state("Portefeuille vide", "100% en liquidités.", icon="allocation")
        else:
            labels = list(weights)
            values = [weights[t] for t in labels]
            colors = [c.mark_color(t) for t in labels]
            st.plotly_chart(
                charts.donut(labels, values, height=250,
                             center_value=f"{len(labels)}",
                             center_title="positions", colors=colors),
                width="stretch", theme=None, config=charts.CONFIG,
            )
            c.render(c.legend_html(list(zip(labels, colors))))

    with c.card(key="regions"):
        c.section("Exposition géographique", icon="globe")
        if not weights:
            c.empty_state("Aucune exposition", icon="globe")
        else:
            grouped = analytics.group_allocation(
                weights, {t: catalog.region_of(t) for t in weights}
            )
            from ui.tokens import REGION_COLOR
            st.plotly_chart(
                charts.hbar(
                    grouped["group"].tolist(), grouped["weight"].tolist(),
                    height=150,
                    colors=[REGION_COLOR.get(g, "#64748B") for g in grouped["group"]],
                ),
                width="stretch", theme=None, config=charts.CONFIG,
            )

st.write("")

# ---------------------------------------------------------------------------
#  Movers, watchlist and activity
# ---------------------------------------------------------------------------

bottom = st.columns([1.25, 1])

with bottom[0]:
    with c.card(key="board"):
        c.section(
            "Liste de suivi", subtitle="Cotations et signaux techniques",
            icon="watchlist",
            aside=c.chip_html(f"{len(store.watchlist())} instruments", tone="flat"),
        )
        watched = ctx.rows(store.watchlist())
        if watched.empty:
            c.empty_state("Watchlist vide",
                          "Ajoutez des ETF depuis la page Markets.", icon="watchlist")
        else:
            shared.market_table(watched, key="dash_watch", filters=False, page_size=6)

with bottom[1]:
    with c.card(key="movers"):
        c.section("Variations du jour", icon="markets",
                  subtitle="Univers Optiport complet")
        shared.movers_block(ctx.quotes[ctx.quotes["ticker"] != catalog.BENCHMARK])

    with c.card(key="activity"):
        c.section("Activité récente", icon="transactions")
        ledger = store.transactions()[:6]
        if not ledger:
            c.empty_state("Aucun mouvement", "Les exécutions apparaîtront ici.",
                          icon="transactions")
        else:
            c.feed([
                {
                    "title": (
                        f"{entry['type']} {entry['quantity']:,.2f} {entry['ticker']}"
                        if entry["ticker"] else entry["note"]
                    ),
                    "summary": entry["note"] if entry["ticker"] else "",
                    "icon": {"BUY": "buy", "SELL": "sell"}.get(entry["type"], "cash"),
                    "tone": {"BUY": "up", "SELL": "warn"}.get(entry["type"], "info"),
                    "meta": c.chip_html(time_ago(entry["timestamp"]), tone="flat")
                    + c.chip_html(signed_money(entry["amount"]),
                                  tone="up" if entry["amount"] >= 0 else "down"),
                }
                for entry in ledger
            ])

shared.account_note()
