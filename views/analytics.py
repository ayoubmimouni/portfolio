# -*- coding: utf-8 -*-
"""Analytics — efficient frontier, correlations, risk decomposition, forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from services import analytics as an, api_client, catalog, market, store
from services.context import get as get_context
from ui import charts, components as c, layout
from ui.format import percent, ratio
from ui.icons import st_icon

ctx = get_context()

c.page_header(
    "Analytique",
    eyebrow="Laboratoire quantitatif",
    icon="analytics",
    subtitle="Frontière efficiente, structure de corrélation, décomposition du "
             "risque et confrontation des prévisions au réalisé.",
    aside=c.chip_html("Markowitz", tone="info", icon="analytics")
    + c.chip_html("LSTM", tone="violet", icon="model"),
)

selection = st.multiselect(
    "Univers analysé",
    options=list(catalog.TICKERS),
    default=store.universe(),
    format_func=catalog.label,
    key="an_universe",
    placeholder="Sélectionner au moins 2 ETF…",
)

if len(selection) < 2:
    c.empty_state(
        "Sélectionnez au moins 2 ETF",
        "Les analyses de corrélation et la frontière efficiente nécessitent "
        "plusieurs actifs.",
        icon="info", variant="info",
    )
    st.stop()

tabs = st.tabs([
    "Frontière efficiente", "Corrélations", "Risque & performance", "Prévisions",
])

# ===========================================================================
#  Efficient frontier
# ===========================================================================

with tabs[0]:
    with c.card(key="frontier"):
        c.section(
            "Frontière efficiente",
            subtitle="Couples risque/rendement optimaux pour l'univers sélectionné",
            icon="analytics",
            aside=c.chip_html("Calculé par le backend", tone="flat", icon="api"),
        )

        if not ctx.api_online:
            layout.api_offline_notice(ctx, feature="La frontière efficiente")
        else:
            controls = st.columns([1, 1, 2], vertical_alignment="bottom")
            points = controls[0].slider("Points", 10, 60, 30, step=5, key="an_points")
            risk_free = controls[1].slider(
                "Taux sans risque (%)", 0.0, 10.0,
                float(store.prefs()["risk_free_rate"] * 100), step=0.25,
                key="an_rf",
            ) / 100
            compute = controls[2].button(
                "Calculer la frontière", type="primary",
                icon=st_icon("forecast"), key="an_frontier_run",
            )

            cache_key = ("an_frontier", tuple(sorted(selection)), points, risk_free)
            if compute:
                with st.spinner("Optimisation sur la grille de rendements cibles…"):
                    try:
                        st.session_state["an_frontier_data"] = (
                            cache_key,
                            api_client.efficient_frontier(
                                tuple(selection), risk_free_rate=risk_free,
                                n_points=points,
                            ),
                        )
                    except api_client.ApiError as error:
                        st.session_state["an_frontier_data"] = None
                        c.error_state(error.title, f"{error.message}\n\n{error.hint}")

            stored = st.session_state.get("an_frontier_data")
            if stored and stored[0] == cache_key:
                data = stored[1]
                st.plotly_chart(
                    charts.efficient_frontier(
                        data["volatilities"], data["returns"], data["sharpes"],
                        height=420,
                        markers=[
                            {"label": "Max Sharpe",
                             "volatility": data["max_sharpe_volatility"],
                             "return": data["max_sharpe_return"],
                             "color": "#22C55E", "symbol": "star"},
                            {"label": "Min Volatilité",
                             "volatility": data["min_vol_volatility"],
                             "return": data["min_vol_return"],
                             "color": "#F59E0B", "symbol": "diamond",
                             "position": "bottom center"},
                        ],
                    ),
                    width="stretch", theme=None, config=charts.CONFIG_INTERACTIVE,
                )
                summary = st.columns(2)
                with summary[0]:
                    c.kv_list([
                        ("Portefeuille Max Sharpe", ""),
                        ("Rendement attendu", percent(data["max_sharpe_return"] * 100, 2)),
                        ("Volatilité", percent(data["max_sharpe_volatility"] * 100, 2)),
                    ])
                with summary[1]:
                    c.kv_list([
                        ("Portefeuille Min Volatilité", ""),
                        ("Rendement attendu", percent(data["min_vol_return"] * 100, 2)),
                        ("Volatilité", percent(data["min_vol_volatility"] * 100, 2)),
                    ])
                c.caption(
                    "Chaque point est une optimisation sous contrainte de "
                    "rendement cible (SLSQP, poids positifs, somme égale à 1). "
                    "Les rendements attendus proviennent des prévisions du modèle."
                )
            elif not compute:
                c.empty_state(
                    "Frontière non calculée",
                    "Le calcul enchaîne une optimisation par point de la grille : "
                    "lancez-le explicitement pour éviter une attente inutile.",
                    icon="analytics", variant="info",
                )

# ===========================================================================
#  Correlations
# ===========================================================================

with tabs[1]:
    correlation_columns = st.columns([1.4, 1])

    with correlation_columns[0]:
        with c.card(key="corr"):
            c.section("Matrice de corrélation",
                      subtitle="Rendements quotidiens sur la période choisie",
                      icon="grid")
            period_label = st.segmented_control(
                "Période", list(market.PERIODS), default="1A",
                key="an_corr_period", label_visibility="collapsed",
            ) or "1A"
            matrix = an.correlation_matrix(
                selection, market.PERIODS.get(period_label, "1y")
            )
            if matrix.empty:
                c.error_state("Corrélations indisponibles",
                              "Historique insuffisant pour cette sélection.")
            else:
                st.plotly_chart(
                    charts.correlation_heatmap(matrix, height=420),
                    width="stretch", theme=None, config=charts.CONFIG,
                )

    with correlation_columns[1]:
        with c.card(key="corrstats"):
            c.section("Lecture de la structure", icon="info")
            if not matrix.empty:
                upper = matrix.where(np.triu(np.ones(matrix.shape), k=1).astype(bool))
                pairs = upper.stack().sort_values(ascending=False)
                average = float(upper.stack().mean())

                c.tiles([
                    ("Corrélation moyenne", ratio(average)),
                    ("Paire la plus liée",
                     f"{pairs.index[0][0]}/{pairs.index[0][1]}", ratio(pairs.iloc[0])),
                    ("Paire la moins liée",
                     f"{pairs.index[-1][0]}/{pairs.index[-1][1]}", ratio(pairs.iloc[-1])),
                ])
                st.write("")
                c.section("Paires les plus corrélées", icon="sort")
                c.kv_list([
                    (f"{a} / {b}", ratio(value))
                    for (a, b), value in pairs.head(6).items()
                ])
                st.write("")
                c.section("Meilleures diversifications", icon="diversification")
                c.kv_list([
                    (f"{a} / {b}", ratio(value))
                    for (a, b), value in pairs.tail(5).items()
                ])
                c.caption(
                    "Une corrélation moyenne élevée limite le bénéfice de "
                    "diversification : l'optimiseur concentrera alors "
                    "davantage l'allocation."
                )

# ===========================================================================
#  Risk & performance
# ===========================================================================

with tabs[2]:
    prices = market.closes([*selection, catalog.BENCHMARK], "1y")

    if prices.empty:
        layout.data_unavailable_notice("Les historiques de prix")
    else:
        benchmark_series = (
            prices[catalog.BENCHMARK].dropna()
            if catalog.BENCHMARK in prices.columns else pd.Series(dtype=float)
        )

        metrics = []
        for ticker in selection:
            if ticker not in prices.columns:
                continue
            series = prices[ticker].dropna()
            profile = an.risk_profile(series, benchmark_series,
                                      store.prefs()["risk_free_rate"])
            metrics.append({"ticker": ticker,
                            "sector": catalog.sector_of(ticker), **profile})

        frame = pd.DataFrame(metrics)

        with c.card(key="riskgrid"):
            c.section("Profil de risque par instrument",
                      subtitle="Sur 12 mois glissants, taux sans risque de "
                               f"{store.prefs()['risk_free_rate'] * 100:.1f}%",
                      icon="risk")
            columns = [
                c.Column("ticker", "ETF", align="left",
                         render=lambda v, r: c.instrument_html(str(v), r["sector"])),
                c.Column("annual_return", "Rendement ann.",
                         render=lambda v, r: c.delta_html(v, decimals=1)),
                c.Column("volatility", "Volatilité",
                         render=lambda v, r: f'<span class="opt-num">{percent(v, 1)}</span>'),
                c.Column("sharpe", "Sharpe",
                         render=lambda v, r: (
                             f'<span class="opt-num" style="font-weight:600;color:'
                             f'{"var(--opt-up-text)" if (v or 0) > 0 else "var(--opt-down-text)"}">'
                             f'{ratio(v)}</span>'
                         )),
                c.Column("sortino", "Sortino",
                         render=lambda v, r: f'<span class="opt-num">{ratio(v)}</span>'),
                c.Column("max_drawdown", "Drawdown max",
                         render=lambda v, r: (
                             f'<span class="opt-num opt-td--down">{percent(v, 1)}</span>'
                         )),
                c.Column("var_95", "VaR 95%",
                         render=lambda v, r: f'<span class="opt-num">{percent(v, 2)}</span>',
                         help="Perte quotidienne dépassée dans 5% des cas (historique)"),
                c.Column("beta", f"Bêta {catalog.BENCHMARK}",
                         render=lambda v, r: f'<span class="opt-num">{ratio(v)}</span>'),
            ]
            c.data_table(frame, columns, key="an_risk", search_keys=("ticker", "sector"),
                         page_size=12, default_sort="sharpe", default_desc=True)

        st.write("")
        risk_columns = st.columns(2)

        with risk_columns[0]:
            with c.card(key="anrr"):
                c.section("Carte risque / rendement", icon="analytics",
                          subtitle="12 mois glissants")
                if not frame.empty:
                    points = frame.assign(
                        volatility=frame["volatility"] / 100,
                        expected_return=frame["annual_return"] / 100,
                        weight=30,
                    )
                    st.plotly_chart(
                        charts.scatter_risk_return(points, height=320),
                        width="stretch", theme=None, config=charts.CONFIG,
                    )

        with risk_columns[1]:
            with c.card(key="anvol"):
                c.section("Volatilité glissante 21 séances", icon="volatility",
                          subtitle="Régimes de risque sur l'univers")
                rolling = pd.DataFrame()
                for ticker in selection[:6]:
                    if ticker in prices.columns:
                        series = an.rolling_volatility(prices[ticker].dropna())
                        if not series.empty:
                            rolling[ticker] = series
                if rolling.empty:
                    c.empty_state("Historique insuffisant", icon="empty")
                else:
                    rolling = rolling.reset_index().rename(
                        columns={rolling.index.name or "index": "Date"})
                    st.plotly_chart(
                        charts.multi_line(
                            rolling, x=rolling.columns[0],
                            series=[col for col in rolling.columns[1:]],
                            height=320, value_suffix="%",
                        ),
                        width="stretch", theme=None, config=charts.CONFIG,
                    )

        with c.card(key="andd"):
            c.section("Drawdowns comparés", icon="drawdown",
                      subtitle="Écart aux plus hauts sur 12 mois")
            focus = st.selectbox("Instrument", selection, format_func=catalog.label,
                                 key="an_dd_ticker")
            if focus in prices.columns:
                underwater = market.drawdown_series(prices[focus].dropna())
                st.plotly_chart(
                    charts.drawdown(underwater.index, underwater.tolist(), height=220),
                    width="stretch", theme=None, config=charts.CONFIG,
                )

# ===========================================================================
#  Forecasts
# ===========================================================================

with tabs[3]:
    with c.card(key="fcpanel"):
        c.section(
            "Prévisions LSTM vs réalisé",
            subtitle="Rendement prévu à 22 séances comparé au dernier rendement "
                     "à 22 séances observé",
            icon="model",
            aside=c.chip_html("POST /forecast", tone="flat", mono=True, icon="api"),
        )

        if not ctx.api_online:
            layout.api_offline_notice(ctx, feature="Les prévisions du modèle")
        else:
            if st.button("Générer les prévisions", type="primary",
                         icon=st_icon("forecast"), key="an_forecast_run"):
                st.session_state["an_forecast_nonce"] = st.session_state.get(
                    "an_forecast_nonce", 0) + 1

            if st.session_state.get("an_forecast_nonce"):
                with st.spinner("Inférence LSTM par ticker…"):
                    try:
                        data = api_client.forecast(tuple(selection))
                    except api_client.ApiError as error:
                        c.error_state(error.title, f"{error.message}\n\n{error.hint}")
                        data = None

                if data:
                    predictions = data["predictions"]
                    if not data.get("model_loaded"):
                        st.warning(
                            "Les modèles LSTM entraînés n'ont pas été trouvés : le "
                            "backend renvoie le dernier rendement observé à la "
                            "place des prévisions. Les valeurs ci-dessous ne sont "
                            "donc pas des sorties du modèle.",
                            icon=st_icon("warning"),
                        )

                    rows = []
                    for ticker, prediction in predictions.items():
                        predicted = prediction.get("predicted_return_22d")
                        actual = prediction.get("last_actual_return_22d")
                        rows.append({
                            "ticker": ticker,
                            "sector": catalog.sector_of(ticker),
                            "predicted": (predicted * 100) if predicted is not None else None,
                            "actual": (actual * 100) if actual is not None else None,
                            "date": prediction.get("prediction_date", "—"),
                            "note": prediction.get("note") or "",
                        })
                    forecast_frame = pd.DataFrame(rows)

                    available = forecast_frame.dropna(subset=["predicted"])
                    if not available.empty:
                        st.plotly_chart(
                            charts.grouped_bar(
                                available["ticker"].tolist(),
                                {
                                    "Réalisé 22j": available["actual"].fillna(0).tolist(),
                                    "Prévu 22j": available["predicted"].tolist(),
                                },
                                height=280,
                                colors={"Réalisé 22j": "#3B82F6", "Prévu 22j": "#8B5CF6"},
                            ),
                            width="stretch", theme=None, config=charts.CONFIG,
                        )

                    c.data_table(
                        forecast_frame,
                        [
                            c.Column("ticker", "ETF", align="left",
                                     render=lambda v, r: c.instrument_html(str(v), r["sector"])),
                            c.Column("predicted", "Prévision 22j",
                                     render=lambda v, r: (
                                         c.delta_html(v, decimals=2) if v is not None
                                         else '<span class="opt-faint">—</span>'
                                     )),
                            c.Column("actual", "Réalisé 22j",
                                     render=lambda v, r: c.delta_html(v, decimals=2)),
                            c.Column("date", "Date de calcul", align="center",
                                     render=lambda v, r: c.chip_html(str(v), tone="flat",
                                                                     icon="clock")),
                            c.Column("note", "Statut", align="left", sortable=False,
                                     render=lambda v, r: (
                                         c.chip_html("Modèle indisponible", tone="warn",
                                                     icon="warning", title=str(v))
                                         if v else c.chip_html("Prévision LSTM", tone="up",
                                                               icon="check")
                                     )),
                        ],
                        key="an_forecast", search_keys=("ticker", "sector"),
                        page_size=12, toolbar=False, default_sort="predicted",
                    )
                    c.caption(
                        "Le modèle produit un rendement à 22 séances. L'API "
                        "l'annualise ensuite — (1 + r)¹² − 1 — pour alimenter "
                        "l'optimiseur, et borne le résultat entre −50% et +200%."
                    )
            else:
                c.empty_state(
                    "Prévisions non générées",
                    "L'inférence charge un modèle par ETF : lancez-la "
                    "explicitement pour éviter une attente inutile.",
                    icon="model", variant="info",
                )
