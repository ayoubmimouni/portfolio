# -*- coding: utf-8 -*-
"""Portfolio — holdings, allocation, performance attribution and risk."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from services import analytics, catalog, market, store
from services.context import get as get_context
from ui import charts, components as c, layout
from ui.format import (money, percent, price, ratio, signed_money,
                       signed_percent)
from ui.icons import st_icon
from ui.tokens import REGION_COLOR
from views import _shared as shared

ctx = get_context()
valuation = ctx.valuation
holdings = valuation.get("holdings", [])

c.page_header(
    "Portefeuille",
    eyebrow="Positions et attribution",
    icon="portfolio",
    subtitle="Détail des positions valorisées aux derniers cours, exposition "
             "et mesures de risque du portefeuille simulé.",
    aside=c.chip_html(store.ACCOUNT_MODE, tone="warn", icon="shield")
    + c.chip_html(f"{valuation.get('positions_count', 0)} lignes", tone="flat",
                  icon="assets"),
)

if not holdings:
    c.empty_state(
        "Aucune position en portefeuille",
        "Le compte est intégralement en liquidités. Lancez une optimisation "
        "pour obtenir une allocation cible, puis exécutez le plan de "
        "rééquilibrage depuis la page Trading.",
        icon="portfolio", variant="info",
    )
    action_columns = st.columns([1, 1, 3])
    if action_columns[0].button("Optimiser", type="primary", width="stretch",
                                icon=st_icon("forecast"), key="pf_optimize"):
        layout.goto("trading")
    if action_columns[1].button("Marchés", width="stretch",
                                icon=st_icon("markets"), key="pf_markets"):
        layout.goto("markets")

    with c.card(key="cashonly"):
        c.section("Liquidités", subtitle="Dotation du compte simulé", icon="cash")
        c.tiles([
            ("Disponible", money(valuation.get("cash", 0))),
            ("Dotation initiale", money(store.INITIAL_CASH)),
            ("Investi", "0%"),
        ])
    shared.account_note()
    st.stop()

# ---------------------------------------------------------------------------
#  KPIs
# ---------------------------------------------------------------------------

weights = {h["ticker"]: (h["weight"] or 0.0) for h in holdings}
equity_series = analytics.equity_curve(holdings, valuation["cash"], "1y")
benchmark_prices = market.closes([catalog.BENCHMARK], "1y")
benchmark_series = (
    benchmark_prices[catalog.BENCHMARK].dropna()
    if not benchmark_prices.empty and catalog.BENCHMARK in benchmark_prices.columns
    else pd.Series(dtype=float)
)
risk = analytics.risk_profile(equity_series, benchmark_series,
                             store.prefs()["risk_free_rate"])
top_holding = holdings[0] if holdings else None

c.kpi_row([
    c.kpi_html("Valeur de marché", money(valuation["market_value"]),
               delta=valuation["day_pnl_pct"], hint="variation du jour",
               icon="value", tone="accent",
               spark=equity_series.tail(30).tolist() if not equity_series.empty else None),
    c.kpi_html("Prix de revient", money(valuation["cost_basis"]),
               icon="cash", tone="info",
               hint=f"{valuation['positions_count']} lignes"),
    c.kpi_html("P&L latent", signed_money(valuation["pnl"]),
               delta=valuation["pnl_pct"], icon="return",
               tone="up" if valuation["pnl"] >= 0 else "down"),
    c.kpi_html("P&L du jour", signed_money(valuation["day_pnl"]),
               delta=valuation["day_pnl_pct"], icon="performance",
               tone="up" if valuation["day_pnl"] >= 0 else "down"),
    c.kpi_html("Première position",
               top_holding["ticker"] if top_holding else "—",
               icon="allocation", tone="violet",
               footer=c.chip_html(percent(top_holding["weight"], 1), tone="info")
               if top_holding and top_holding["weight"] else "",
               hint=catalog.sector_of(top_holding["ticker"]) if top_holding else None),
    c.kpi_html("Liquidités", money(valuation["cash"]), icon="cash", tone="warn",
               hint=f"{100 - valuation['invested_pct']:.0f}% du compte"),
], min_width="14rem")

st.write("")

# ---------------------------------------------------------------------------
#  Holdings table
# ---------------------------------------------------------------------------

frame = pd.DataFrame(holdings)
frame["sector"] = frame["ticker"].map(catalog.sector_of)
frame["region"] = frame["ticker"].map(catalog.region_of)
frame["signal"] = frame["ticker"].map(
    lambda t: (ctx.quote(t) or {}).get("signal", "Hold")
)
frame["spark"] = frame["ticker"].map(lambda t: (ctx.quote(t) or {}).get("spark", []))
frame["change_pct"] = frame["ticker"].map(
    lambda t: (ctx.quote(t) or {}).get("change_pct", float("nan"))
)

with c.card(key="holdings"):
    c.section("Positions", subtitle="Valorisation ligne à ligne", icon="assets",
              aside=c.chip_html("Cours de clôture les plus récents", tone="flat",
                                icon="live"))

    columns = [
        c.Column("ticker", "Ticker", align="left",
                 render=lambda v, r: c.instrument_html(str(v), r["sector"])),
        c.Column("quantity", "Quantité",
                 render=lambda v, r: f'<span class="opt-num">{v:,.4f}</span>'),
        c.Column("avg_price", "PRU",
                 render=lambda v, r: f'<span class="opt-num">{price(v)}</span>'),
        c.Column("price", "Dernier",
                 render=lambda v, r: f'<span class="opt-num opt-td--strong">{price(v)}</span>'),
        c.Column("change_pct", "Jour", render=lambda v, r: c.delta_html(v)),
        c.Column("market_value", "Valeur",
                 render=lambda v, r: f'<span class="opt-num opt-td--strong">{money(v, 2)}</span>'),
        c.Column("weight", "Poids",
                 render=lambda v, r: (
                     f'<div class="opt-num" style="font-weight:600">{percent(v, 1)}</div>'
                     + c.bar_html(v or 0, color=c.mark_color(r["ticker"]))
                 )),
        c.Column("pnl", "P&L latent",
                 render=lambda v, r: (
                     f'<div class="opt-num" style="font-weight:600;color:'
                     f'{"var(--opt-up-text)" if (v or 0) >= 0 else "var(--opt-down-text)"}">'
                     f'{signed_money(v, 2)}</div>'
                     f'<div class="opt-caption">{signed_percent(r["pnl_pct"])}</div>'
                 )),
        c.Column("signal", "Signal", align="center",
                 render=lambda v, r: c.signal_html(str(v))),
        c.Column("spark", "30 séances", sortable=False,
                 render=lambda v, r: c.sparkline_html(v or [], width=110, height=30)),
    ]

    c.data_table(
        frame, columns, key="pf_holdings",
        search_keys=("ticker", "sector", "region"),
        filters=[c.Filter("region", "Région", catalog.REGIONS)],
        page_size=10, default_sort="market_value", default_desc=True,
    )

st.write("")

# ---------------------------------------------------------------------------
#  Allocation & performance
# ---------------------------------------------------------------------------

allocation_columns = st.columns([1, 1, 1.4])

with allocation_columns[0]:
    with c.card(key="byetf"):
        c.section("Par instrument", icon="allocation")
        labels = list(weights)
        colors = [c.mark_color(t) for t in labels]
        st.plotly_chart(
            charts.donut(labels, [weights[t] for t in labels], height=240,
                         center_value=money(valuation["market_value"], 0),
                         center_title="investi", colors=colors),
            width="stretch", theme=None, config=charts.CONFIG,
        )
        c.render(c.legend_html(list(zip(labels, colors))))

with allocation_columns[1]:
    with c.card(key="byregion"):
        c.section("Par région", icon="globe")
        regions = analytics.group_allocation(
            weights, {t: catalog.region_of(t) for t in weights})
        st.plotly_chart(
            charts.hbar(regions["group"].tolist(), regions["weight"].tolist(),
                        height=140,
                        colors=[REGION_COLOR.get(g, "#64748B") for g in regions["group"]]),
            width="stretch", theme=None, config=charts.CONFIG,
        )
        c.section("Par thème", icon="sector")
        themes = analytics.group_allocation(
            weights, {t: catalog.theme_of(t) for t in weights})
        st.plotly_chart(
            charts.hbar(themes["group"].tolist(), themes["weight"].tolist(),
                        height=170),
            width="stretch", theme=None, config=charts.CONFIG,
        )

with allocation_columns[2]:
    with c.card(key="attribution"):
        c.section("Attribution du P&L", subtitle="Contribution de chaque ligne",
                  icon="analytics")
        contribution = analytics.contributions(holdings)
        if contribution.empty:
            c.empty_state("Attribution indisponible", icon="empty")
        else:
            st.plotly_chart(
                charts.signed_bar(contribution["ticker"].tolist(),
                                  contribution["pnl"].tolist(),
                                  height=260, suffix=" $", horizontal=True),
                width="stretch", theme=None, config=charts.CONFIG,
            )
            best = contribution.iloc[0]
            worst = contribution.iloc[-1]
            c.render(
                '<div class="opt-row opt-row--wrap">'
                + c.chip_html(f"Meilleur : {best['ticker']} {signed_money(best['pnl'])}",
                              tone="up", icon="profit")
                + c.chip_html(f"Pire : {worst['ticker']} {signed_money(worst['pnl'])}",
                              tone="down", icon="loss")
                + "</div>"
            )

st.write("")

# ---------------------------------------------------------------------------
#  Performance & risk
# ---------------------------------------------------------------------------

bottom = st.columns([2, 1])

with bottom[0]:
    with c.card(key="pfperf"):
        c.section(
            "Performance vs indice de référence",
            subtitle=f"Base 100 · portefeuille à quantités constantes vs {catalog.BENCHMARK_LABEL}",
            icon="performance",
        )
        yf_period = shared.period_selector("pf_period", default="1A")
        prices = market.closes([*weights, catalog.BENCHMARK], yf_period)
        if prices.empty:
            c.error_state("Historique indisponible",
                          "Les séries de prix n'ont pas pu être récupérées.")
        else:
            index = analytics.weighted_index(prices, weights)
            chart_frame = pd.DataFrame({"Date": index.index, "Portefeuille": index.values})
            if catalog.BENCHMARK in prices.columns:
                reference = analytics.normalized(prices[[catalog.BENCHMARK]])[catalog.BENCHMARK]
                chart_frame[catalog.BENCHMARK] = reference.reindex(index.index).values
            st.plotly_chart(
                charts.multi_line(chart_frame, x="Date",
                                  series=[col for col in chart_frame.columns if col != "Date"],
                                  height=300, baseline=100),
                width="stretch", theme=None, config=charts.CONFIG,
            )

    with c.card(key="pfdd"):
        c.section("Drawdown", subtitle="Sous les plus hauts historiques de la période",
                  icon="drawdown")
        if equity_series.empty:
            c.empty_state("Drawdown indisponible", icon="empty")
        else:
            underwater = market.drawdown_series(equity_series)
            st.plotly_chart(
                charts.drawdown(underwater.index, underwater.tolist(), height=200),
                width="stretch", theme=None, config=charts.CONFIG,
            )

with bottom[1]:
    with c.card(key="pfrisk"):
        c.section("Mesures de risque", subtitle="12 derniers mois", icon="risk")
        c.kv_list([
            ("Rendement annualisé", percent(risk["annual_return"], 1)),
            ("Volatilité annualisée", percent(risk["volatility"], 1)),
            ("Ratio de Sharpe", ratio(risk["sharpe"])),
            ("Ratio de Sortino", ratio(risk["sortino"])),
            ("Drawdown maximum", percent(risk["max_drawdown"], 1)),
            ("VaR 95% (1 jour)", percent(risk["var_95"], 2)),
            (f"Bêta vs {catalog.BENCHMARK}", ratio(risk["beta"])),
            ("Tracking error", percent(risk["tracking_error"], 2)),
        ])
        c.caption(
            "Calculées sur la valorisation du portefeuille à quantités "
            "constantes, taux sans risque de "
            f"{store.prefs()['risk_free_rate'] * 100:.1f}%."
        )

    with c.card(key="pfconc"):
        c.section("Concentration", icon="diversification")
        values = list(weights.values())
        diversification = analytics.diversification_score(values)
        effective = analytics.effective_holdings(values)
        c.tiles([
            ("Diversification", ratio(diversification) if not np.isnan(diversification) else "—"),
            ("Positions effectives", ratio(effective, 1) if not np.isnan(effective) else "—"),
            ("Poids max", percent(max(values) if values else 0, 1)),
        ])
        c.render(
            c.bar_html((diversification or 0) * 100 if not np.isnan(diversification) else 0,
                       color="var(--opt-violet)", large=True)
        )
        c.caption("Indice de Herfindahl inversé : 1 = parfaitement diversifié.")

shared.account_note()
