# -*- coding: utf-8 -*-
"""Trading — ML-driven allocation engine and order execution.

This page carries the original application's core workflow end to end: pick an
ETF universe, pick a risk profile, set an amount, call `POST /smart-invest`
(LSTM forecast + Markowitz optimisation) and read the resulting allocation.
Everything the previous single-page app displayed is preserved here, plus an
execution layer that turns target weights into paper orders.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services import api_client, catalog, store
from services.context import get as get_context
from ui import charts, components as c, layout
from ui.format import (money, percent, price, ratio, signed_money,
                       signed_percent, time_ago)
from ui.icons import st_icon
from ui.tokens import REGION_COLOR, RISK_PROFILES

ctx = get_context()

c.page_header(
    "Trading",
    eyebrow="Moteur d'allocation & exécution",
    icon="trading",
    subtitle="Prévisions de rendement par LSTM et optimisation moyenne-variance, "
             "converties en plan d'ordres exécutable.",
    aside=c.chip_html("LSTM · 22 jours", tone="violet", icon="model")
    + c.chip_html("Markowitz", tone="info", icon="analytics")
    + c.chip_html(store.ACCOUNT_MODE, tone="warn", icon="shield"),
)

layout_columns = st.columns([1, 2.6], gap="medium")

# ===========================================================================
#  Configuration panel
# ===========================================================================

with layout_columns[0]:
    with c.card("hero", key="config"):
        c.section("Paramètres", subtitle="Univers, profil et montant", icon="settings")

        tickers = st.multiselect(
            "ETF considérés",
            options=list(catalog.TICKERS),
            default=store.universe(),
            format_func=catalog.label,
            key="trade_tickers",
            placeholder="Sélectionner au moins 2 ETF…",
            help="L'optimiseur répartit le capital entre les ETF sélectionnés.",
        )
        if tickers != store.universe():
            store.set_universe(tickers)

        st.write("")
        profile_name = st.segmented_control(
            "Profil de risque",
            list(RISK_PROFILES),
            default="Balanced",
            key="trade_profile",
            help="Détermine la stratégie d'optimisation envoyée au backend.",
        ) or "Balanced"
        profile = RISK_PROFILES[profile_name]
        c.render(
            '<div class="opt-row" style="margin:-0.25rem 0 0.5rem">'
            + c.chip_html(profile["strategy"], tone="info", icon=profile["icon"], mono=True)
            + f'<span class="opt-caption">{c.esc(profile["caption"])}</span></div>'
        )

        amount = st.number_input(
            "Montant à investir ($)",
            min_value=1_000,
            max_value=10_000_000,
            value=int(store.prefs()["default_amount"]),
            step=1_000,
            format="%d",
            key="trade_amount",
            icon=st_icon("cash"),
        )

        with st.expander("Paramètres avancés", icon=st_icon("settings")):
            risk_free = st.slider(
                "Taux sans risque annuel (%)",
                min_value=0.0, max_value=10.0,
                value=float(store.prefs()["risk_free_rate"] * 100),
                step=0.25, key="trade_rf",
                help="Utilisé pour le ratio de Sharpe et l'optimisation max Sharpe.",
            ) / 100
            include_charts = st.toggle(
                "Inclure les séries de prix", value=True, key="trade_charts",
                help="Récupère les historiques 1 an et 6 mois normalisés "
                     "pour les graphiques de comparaison.",
            )
            model_path = st.text_input(
                "Répertoire des modèles",
                value=api_client.DEFAULT_MODEL_PATH,
                key="trade_model_path",
                help="Répertoire contenant les modèles LSTM par ticker "
                     "(`<TICKER>_model.keras`).",
            )

        st.write("")
        enough = len(tickers) >= 2
        run = st.button(
            "Lancer l'optimisation",
            type="primary", width="stretch",
            icon=st_icon("forecast"),
            disabled=not enough or not ctx.api_online,
            key="trade_run",
        )
        if not enough:
            c.caption("Sélectionnez au moins 2 ETF pour lancer une optimisation.")

        st.write("")
        c.kv_list([
            ("Backend", c.chip_html("En ligne", tone="up", icon="check")
             if ctx.api_online else c.chip_html("Hors ligne", tone="down", icon="error")),
            ("Univers", f"{len(tickers)} ETF"),
            ("Stratégie", profile["strategy"]),
        ])

        snapshot = store.optimization()
        if snapshot:
            c.caption(f"Dernière exécution : {time_ago(snapshot['meta']['ran_at'])}")
            if st.button("Effacer le résultat", width="stretch",
                         icon=st_icon("delete"), key="trade_clear"):
                store.clear_optimization()
                st.rerun()

# ===========================================================================
#  Run the optimisation
# ===========================================================================

if run:
    with layout_columns[1]:
        with st.status("Optimisation en cours…", expanded=True) as status:
            st.write("Téléchargement des historiques depuis Yahoo Finance")
            st.write("Prévision du rendement à 22 jours par ETF (LSTM)")
            st.write("Matrice de covariance et optimisation moyenne-variance")
            try:
                result = api_client.smart_invest(
                    tickers,
                    strategy=profile["strategy"],
                    risk_free_rate=risk_free,
                    investment_amount=float(amount),
                    include_charts=include_charts,
                    model_path=model_path,
                )
            except api_client.ApiError as error:
                status.update(label=error.title, state="error")
                c.error_state(error.title, f"{error.message}\n\n{error.hint}")
                st.stop()

            store.set_optimization(result, {
                "tickers": tickers,
                "profile": profile_name,
                "strategy": profile["strategy"],
                "amount": float(amount),
            })
            status.update(label="Optimisation terminée", state="complete", expanded=False)
    st.rerun()

# ===========================================================================
#  Results
# ===========================================================================

with layout_columns[1]:
    if not ctx.api_online:
        layout.api_offline_notice(ctx, feature="L'optimisation de portefeuille")
        st.stop()

    if len(tickers) < 2:
        c.empty_state(
            "Sélectionnez au moins 2 ETF",
            "L'optimisation moyenne-variance a besoin de plusieurs actifs pour "
            "répartir le risque. Choisissez vos ETF dans le panneau de gauche.",
            icon="info", variant="info",
        )
        st.stop()

    snapshot = store.optimization()
    if not snapshot:
        c.empty_state(
            "Aucune allocation calculée",
            "Configurez vos paramètres puis lancez l'optimisation : le moteur "
            "prévoit le rendement de chaque ETF à 22 jours, estime la matrice "
            "de covariance et calcule l'allocation optimale.",
            icon="forecast", variant="info",
        )

        with c.card(key="method"):
            c.section("Méthodologie", subtitle="Ce que fait le moteur", icon="model")
            c.kv_list([
                ("1 · Données", "Historiques quotidiens ajustés depuis 2010"),
                ("2 · Features", "Momentum 1/3/6M, volatilité, RSI-14, "
                                "position 52s, corrélation, drawdown, région"),
                ("3 · Prévision", "Un LSTM par ETF, séquences de 10 séances, "
                                 "cible = rendement à 22 séances"),
                ("4 · Risque", "Covariance annualisée sur 252 séances, "
                              "correction semi-définie positive"),
                ("5 · Allocation", "Optimisation SLSQP selon la stratégie choisie"),
            ])
        st.stop()

    result = snapshot["result"]
    meta = snapshot["meta"]
    metrics = result["portfolio_metrics"]
    allocations = result["allocations"]
    active = [a for a in allocations if a["weight_percent"] > 0]
    invested = meta["amount"]

    c.render(
        '<div class="opt-row opt-row--wrap" style="margin-bottom:0.25rem">'
        + c.chip_html(f"Profil {meta['profile']}", tone="info", icon="risk")
        + c.chip_html(result["strategy_used"], tone="violet", mono=True, icon="model")
        + c.chip_html(f"{len(active)} positions retenues", tone="flat", icon="assets")
        + c.chip_html(f"Exécuté {time_ago(meta['ran_at'])}", tone="flat", icon="clock")
        + "</div>"
    )

    tabs = st.tabs([
        "Allocation", "Prévisions & marché", "ETF vs pairs", "Exécution",
    ])

    # -----------------------------------------------------------------------
    #  Tab 1 — Allocation
    # -----------------------------------------------------------------------
    with tabs[0]:
        # Backend metrics are numeric by contract, but a degraded run (e.g. a
        # missing YTD series) can leave a field null. Coerce to a safe number
        # before any arithmetic or comparison; the format helpers already
        # render None as an em dash on their own.
        def _num(value: float | None) -> float:
            return float(value) if value is not None else 0.0

        expected_return = _num(metrics.get("expected_annual_return"))
        expected_value = invested * (1 + min(expected_return, 1.0))
        expected_gain = expected_value - invested
        ytd_return = metrics.get("portfolio_ytd_return")

        c.kpi_row([
            c.kpi_html("Rendement attendu",
                       percent(metrics["expected_annual_return_capped"], 1),
                       icon="return", tone="up",
                       footer=c.chip_html(f"Sharpe {ratio(metrics['sharpe_ratio'])}",
                                          tone="info", icon="sharpe"),
                       hint="annualisé, plafonné à 100% pour l'affichage"),
            c.kpi_html("Volatilité",
                       percent(metrics["annual_volatility_percent"], 1),
                       icon="volatility", tone="warn",
                       footer=c.chip_html(f"YTD {signed_percent(ytd_return, 1)}",
                                          tone="up" if _num(ytd_return) >= 0
                                          else "down"),
                       hint="écart-type annualisé du portefeuille"),
            c.kpi_html("Diversification",
                       ratio(metrics["diversification_score"]),
                       icon="diversification", tone="violet",
                       hint="1 − indice de Herfindahl"),
            c.kpi_html("Valeur projetée à 1 an", money(expected_value),
                       icon="target", tone="accent",
                       footer=c.chip_html(signed_money(expected_gain),
                                          tone="up" if expected_gain >= 0 else "down"),
                       hint=f"sur {money(invested)} investis"),
        ], min_width="14rem")

        st.write("")
        allocation_columns = st.columns([1, 1.35])

        with allocation_columns[0]:
            with c.card(key="allocdonut"):
                c.section("Répartition cible", icon="allocation",
                          subtitle="Poids optimisés par ETF")
                labels = [a["ticker"] for a in active]
                values = [a["weight_percent"] for a in active]
                colors = [c.mark_color(t) for t in labels]
                if labels:
                    st.plotly_chart(
                        charts.donut(labels, values, height=260,
                                     center_value=percent(sum(values), 0),
                                     center_title="alloué", colors=colors),
                        width="stretch", theme=None, config=charts.CONFIG,
                    )
                    c.render(c.legend_html(list(zip(labels, colors))))
                else:
                    c.empty_state("Allocation vide",
                                  "L'optimiseur n'a retenu aucun actif.", icon="empty")

            with c.card(key="summary"):
                c.section("Synthèse de l'investissement", icon="cash")
                c.kv_list([
                    ("Capital initial", money(invested)),
                    ("Valeur attendue (1 an)", money(expected_value)),
                    ("Gain attendu", signed_money(expected_gain)),
                    ("Rendement attendu", percent(metrics["expected_annual_return_capped"], 1)),
                ])
                c.caption(
                    "Projection déterministe : capital × (1 + rendement attendu), "
                    "plafonnée à +100%. Il ne s'agit pas d'une garantie de "
                    "performance."
                )

        with allocation_columns[1]:
            with c.card(key="alloctable"):
                c.section("Détail de l'allocation", icon="table",
                          subtitle="Poids, montants, prévisions et signaux")

                frame = pd.DataFrame(allocations)
                frame["theme"] = frame["ticker"].map(catalog.theme_of)

                columns = [
                    c.Column("ticker", "ETF", align="left",
                             render=lambda v, r: c.instrument_html(str(v), r["name"])),
                    c.Column("region", "Région", align="left",
                             render=lambda v, r: c.chip_html(str(v), tone="flat",
                                                             icon="globe")),
                    c.Column("weight_percent", "Poids",
                             render=lambda v, r: (
                                 f'<div class="opt-num" style="font-weight:600">{percent(v, 1)}</div>'
                                 + c.bar_html(v or 0, color=c.mark_color(r["ticker"]))
                             )),
                    c.Column("amount", "Montant",
                             render=lambda v, r: (
                                 f'<span class="opt-num opt-td--strong">{money(v)}</span>'
                                 if v else '<span class="opt-faint">—</span>'
                             )),
                    c.Column("ytd_return", "YTD",
                             render=lambda v, r: c.delta_html(v, decimals=1)),
                    c.Column("predicted_return_capped", "Prévision",
                             help="Rendement annualisé prévu par le LSTM, plafonné à 100%",
                             render=lambda v, r: (
                                 f'<span class="opt-num" style="font-weight:600;'
                                 f'color:var(--opt-violet)">{percent(v, 1)}</span>'
                             )),
                    c.Column("historical_volatility", "Volatilité",
                             render=lambda v, r: f'<span class="opt-num">{percent(v * 100, 1)}</span>'),
                    c.Column("recommendation", "Signal", align="center",
                             render=lambda v, r: c.signal_html(str(v))),
                ]

                c.data_table(
                    frame, columns, key="trade_alloc",
                    search_keys=("ticker", "name", "region"),
                    filters=[c.Filter("region", "Région", catalog.REGIONS)],
                    page_size=12, default_sort="weight_percent", default_desc=True,
                )

        # Kept at tab level rather than nested inside the right-hand column:
        # a scatter plot needs real width to stay readable.
        lower_columns = st.columns([1, 1.5])
        with lower_columns[0]:
            with c.card(key="toppicks"):
                c.section("Recommandations", subtitle="Sélection du moteur",
                          icon="star")
                if result.get("top_picks"):
                    c.render(
                        '<div class="opt-row opt-row--wrap">'
                        + "".join(
                            c.chip_html(t, tone="up", icon="verified", mono=True)
                            for t in result["top_picks"]
                        )
                        + "</div>"
                    )
                if active:
                    best = max(active, key=lambda a: a["predicted_return_capped"])
                    worst = min(active, key=lambda a: a["predicted_return_capped"])
                    heaviest = max(active, key=lambda a: a["weight_percent"])
                    st.write("")
                    c.kv_list([
                        ("Prévision la plus élevée",
                         f'{best["ticker"]} · {percent(best["predicted_return_capped"], 1)}'),
                        ("Prévision la plus faible",
                         f'{worst["ticker"]} · {percent(worst["predicted_return_capped"], 1)}'),
                        ("Poids le plus fort",
                         f'{heaviest["ticker"]} · {percent(heaviest["weight_percent"], 1)}'),
                    ])

        with lower_columns[1]:
            with c.card(key="riskreturn"):
                c.section("Risque / rendement des actifs retenus", icon="analytics",
                          subtitle="Volatilité historique vs rendement prévu · "
                                   "taille = poids alloué")
                if active:
                    points = pd.DataFrame([{
                        "ticker": a["ticker"],
                        "volatility": a["historical_volatility"],
                        "expected_return": min(a["predicted_return"], 1.0),
                        "weight": a["weight_percent"],
                    } for a in active])
                    st.plotly_chart(
                        charts.scatter_risk_return(points, height=300),
                        width="stretch", theme=None, config=charts.CONFIG,
                    )
                else:
                    c.empty_state("Aucun actif retenu", icon="empty")

        with c.card(key="reco"):
            c.section("Lecture du moteur", icon="model")
            st.code(result["recommendation_summary"], language=None)

    # -----------------------------------------------------------------------
    #  Tab 2 — Forecasts & market
    # -----------------------------------------------------------------------
    with tabs[1]:
        with c.card(key="normprices"):
            c.section(
                "Évolution normalisée des prix",
                subtitle="Base 100 sur 6 mois — comparaison des ETF sélectionnés",
                icon="performance",
            )
            normalized = result.get("normalized_prices")
            if normalized and normalized.get("dates"):
                frame = pd.DataFrame({"Date": pd.to_datetime(normalized["dates"])})
                for ticker, series in normalized["prices"].items():
                    frame[ticker] = series
                series_names = [col for col in frame.columns if col != "Date"]
                st.plotly_chart(
                    charts.multi_line(frame, x="Date", series=series_names,
                                      height=360, baseline=100),
                    width="stretch", theme=None, config=charts.CONFIG,
                )
            else:
                c.empty_state(
                    "Séries de prix non incluses",
                    "Activez « Inclure les séries de prix » dans les paramètres "
                    "avancés puis relancez l'optimisation.",
                    icon="empty",
                )

        chart_columns = st.columns(2)

        with chart_columns[0]:
            with c.card(key="geo"):
                c.section("Exposition géographique", icon="globe",
                          subtitle="Poids agrégés par région")
                geo = result.get("geographic_allocation") or []
                if geo:
                    st.plotly_chart(
                        charts.hbar(
                            [g["region"] for g in geo],
                            [g["allocation_percent"] for g in geo],
                            height=200,
                            colors=[REGION_COLOR.get(g["region"], "#64748B") for g in geo],
                        ),
                        width="stretch", theme=None, config=charts.CONFIG,
                    )
                else:
                    c.empty_state("Aucune exposition", icon="globe")

        with chart_columns[1]:
            with c.card(key="fc"):
                c.section("YTD vs prévision", icon="forecast",
                          subtitle="Réalisé depuis janvier et prévision LSTM annualisée")
                if active:
                    st.plotly_chart(
                        charts.grouped_bar(
                            [a["ticker"] for a in active],
                            {
                                "YTD réalisé": [a["ytd_return"] for a in active],
                                "Prévision": [a["predicted_return_capped"] for a in active],
                            },
                            height=200,
                            colors={"YTD réalisé": "#3B82F6", "Prévision": "#8B5CF6"},
                        ),
                        width="stretch", theme=None, config=charts.CONFIG,
                    )
                else:
                    c.empty_state("Aucune position retenue", icon="empty")

        with c.card(key="fcnote"):
            c.section("Qualité des prévisions", icon="model")
            notes = []
            try:
                forecast = api_client.forecast(tuple(meta["tickers"]))
                if not forecast.get("model_loaded"):
                    notes = [
                        (t, p.get("note") or "—")
                        for t, p in forecast["predictions"].items() if p.get("note")
                    ]
                if notes:
                    c.render(
                        c.chip_html("Modèles LSTM non chargés", tone="warn",
                                    icon="warning")
                    )
                    c.caption(
                        "Le backend est retombé sur le dernier rendement à 22 "
                        "séances observé pour les tickers ci-dessous. Placez les "
                        "modèles entraînés dans le répertoire configuré pour "
                        "activer les prévisions LSTM."
                    )
                    c.kv_list(notes[:6])
                else:
                    c.render(c.chip_html("Modèles LSTM chargés", tone="up",
                                         icon="check"))
                    c.kv_list([
                        (ticker,
                         signed_percent((prediction.get("predicted_return_22d") or 0) * 100))
                        for ticker, prediction in list(forecast["predictions"].items())[:8]
                    ])
                    c.caption("Rendements prévus à 22 séances, par ETF.")
            except api_client.ApiError as error:
                c.error_state(error.title, error.message)

    # -----------------------------------------------------------------------
    #  Tab 3 — Peer comparison (preserved from the original app)
    # -----------------------------------------------------------------------
    with tabs[2]:
        c.section(
            "ETF individuels vs moyenne des pairs",
            subtitle="Pour chaque ETF, la moyenne des pairs exclut l'ETF lui-même",
            icon="benchmark",
        )
        normalized = result.get("normalized_prices")
        active_tickers = [a["ticker"] for a in active]

        if not normalized or not normalized.get("dates") or len(active_tickers) < 2:
            c.empty_state(
                "Comparaison indisponible",
                "Deux ETF au minimum et les séries de prix normalisées sont "
                "nécessaires pour cette analyse.",
                icon="empty",
            )
        else:
            frame = pd.DataFrame({"Date": pd.to_datetime(normalized["dates"])})
            for ticker in active_tickers:
                if ticker in normalized["prices"]:
                    frame[ticker] = normalized["prices"][ticker]
            frame = frame.set_index("Date").dropna(axis=1, how="all")

            available = [t for t in active_tickers if t in frame.columns]
            for start in range(0, len(available), 2):
                row_columns = st.columns(2)
                for column, ticker in zip(row_columns, available[start:start + 2]):
                    peers = frame.drop(columns=[ticker], errors="ignore")
                    if peers.empty:
                        continue
                    peer_average = peers.mean(axis=1)
                    with column:
                        with c.card(key=f"peer-{ticker}"):
                            spread = frame[ticker] - peer_average
                            final = float(spread.iloc[-1])
                            c.section(
                                f"{ticker} vs pairs",
                                subtitle=catalog.sector_of(ticker),
                                icon="markets",
                                aside=c.chip_html(
                                    f"{final:+.2f} pts", tone="up" if final >= 0 else "down",
                                ),
                            )
                            st.plotly_chart(
                                charts.band_compare(
                                    frame.index, frame[ticker].tolist(),
                                    peer_average.tolist(),
                                    primary_name=ticker,
                                    reference_name="Moyenne des pairs",
                                    height=230,
                                ),
                                width="stretch", theme=None, config=charts.CONFIG,
                            )
                            st.plotly_chart(
                                charts.spread(frame.index, spread.tolist(), height=150,
                                              name=f"{ticker} − pairs"),
                                width="stretch", theme=None, config=charts.CONFIG,
                            )

    # -----------------------------------------------------------------------
    #  Tab 4 — Execution
    # -----------------------------------------------------------------------
    with tabs[3]:
        execution_columns = st.columns([1.3, 1])

        with execution_columns[0]:
            with c.card(key="plan"):
                c.section(
                    "Plan de rééquilibrage",
                    subtitle="Écart entre l'allocation cible et les positions actuelles",
                    icon="rebalance",
                    aside=c.chip_html("Ordres simulés", tone="warn", icon="shield"),
                )
                budget = st.number_input(
                    "Capital à allouer ($)",
                    min_value=1_000.0,
                    max_value=10_000_000.0,
                    value=float(min(invested, ctx.valuation.get("equity", invested))),
                    step=1_000.0,
                    key="plan_budget",
                    icon=st_icon("cash"),
                    help="Par défaut : le montant optimisé, borné par la valeur "
                         "du compte simulé.",
                )

                plan = store.rebalance_orders(allocations, budget, ctx.quotes)
                if not plan:
                    c.empty_state(
                        "Aucun ordre nécessaire",
                        "Les positions actuelles correspondent déjà à "
                        "l'allocation cible, ou les cours sont indisponibles.",
                        icon="check", variant="success",
                    )
                else:
                    plan_frame = pd.DataFrame(plan)
                    c.render(c.table_html(plan_frame, [
                        c.Column("ticker", "ETF", align="left",
                                 render=lambda v, r: c.instrument_html(
                                     str(v), catalog.sector_of(str(v)))),
                        c.Column("side", "Sens", align="center",
                                 render=lambda v, r: c.chip_html(
                                     "Achat" if v == "BUY" else "Vente",
                                     tone="up" if v == "BUY" else "down",
                                     icon="buy" if v == "BUY" else "sell")),
                        c.Column("quantity", "Quantité",
                                 render=lambda v, r: f'<span class="opt-num">{v:,.4f}</span>'),
                        c.Column("price", "Cours",
                                 render=lambda v, r: f'<span class="opt-num">{price(v)}</span>'),
                        c.Column("notional", "Montant",
                                 render=lambda v, r: f'<span class="opt-num opt-td--strong">{money(v, 2)}</span>'),
                        c.Column("target_weight", "Poids cible",
                                 render=lambda v, r: percent(v, 1)),
                    ]))

                    total_buy = sum(p["notional"] for p in plan if p["side"] == "BUY")
                    total_sell = sum(p["notional"] for p in plan if p["side"] == "SELL")
                    c.render(
                        '<div class="opt-row opt-row--wrap" style="margin-top:0.5rem">'
                        + c.chip_html(f"{len(plan)} ordres", tone="flat", icon="orders")
                        + c.chip_html(f"Achats {money(total_buy)}", tone="up", icon="buy")
                        + c.chip_html(f"Ventes {money(total_sell)}", tone="down", icon="sell")
                        + "</div>"
                    )

                    st.write("")
                    if st.button("Exécuter le plan", type="primary", width="stretch",
                                 icon=st_icon("bolt"), key="plan_execute"):
                        executed, rejected = 0, []
                        for item in plan:
                            order = store.place_order(
                                item["ticker"], item["side"], item["quantity"],
                                order_type="MARKET", market_price=item["price"],
                            )
                            if order["status"] == "FILLED":
                                executed += 1
                            else:
                                rejected.append(f"{item['ticker']}: {order['reject_reason']}")
                        if executed:
                            st.toast(f"{executed} ordres exécutés", icon="✅")
                        if rejected:
                            st.warning("Ordres rejetés :\n\n- " + "\n- ".join(rejected))
                        else:
                            st.rerun()

        with execution_columns[1]:
            with c.card(key="ticket"):
                c.section("Ordre manuel", subtitle="Saisie directe", icon="buy")
                order_ticker = st.selectbox(
                    "Instrument",
                    options=list(catalog.TICKERS),
                    index=list(catalog.TICKERS).index(store.selected_ticker())
                    if store.selected_ticker() in catalog.TICKERS else 0,
                    format_func=catalog.label,
                    key="ticket_ticker",
                )
                last_price = ctx.price(order_ticker)
                c.render(
                    '<div class="opt-row opt-row--between" style="margin:0.25rem 0 0.5rem">'
                    '<span class="opt-caption">DERNIER COURS</span>'
                    f'<span class="opt-num" style="font-weight:700">{price(last_price)}</span>'
                    "</div>"
                )

                side = st.segmented_control(
                    "Sens", ["BUY", "SELL"], default="BUY", key="ticket_side",
                    format_func=lambda s: "Achat" if s == "BUY" else "Vente",
                ) or "BUY"
                order_type = st.segmented_control(
                    "Type", ["MARKET", "LIMIT"], default="MARKET", key="ticket_type",
                    format_func=lambda t: "Marché" if t == "MARKET" else "Limite",
                ) or "MARKET"

                sizing = st.radio("Dimensionnement", ["Montant", "Quantité"],
                                  horizontal=True, key="ticket_sizing")
                if sizing == "Montant":
                    notional = st.number_input(
                        "Montant ($)", min_value=100.0, value=5_000.0, step=500.0,
                        key="ticket_notional", icon=st_icon("cash"),
                    )
                    quantity = (notional / last_price) if last_price else 0.0
                else:
                    quantity = st.number_input(
                        "Quantité", min_value=0.0001, value=10.0, step=1.0,
                        key="ticket_quantity",
                    )

                limit_price = None
                if order_type == "LIMIT":
                    limit_price = st.number_input(
                        "Prix limite ($)", min_value=0.01,
                        value=float(round(last_price, 2)) if last_price else 100.0,
                        step=0.5, key="ticket_limit",
                    )

                estimated = quantity * (limit_price or last_price or 0)
                c.kv_list([
                    ("Quantité estimée", f"{quantity:,.4f}"),
                    ("Montant estimé", money(estimated, 2)),
                    ("Liquidités après", money(
                        ctx.valuation.get("cash", 0)
                        - (estimated if side == "BUY" else -estimated), 2)),
                ])

                st.write("")
                if st.button("Envoyer l'ordre", type="primary", width="stretch",
                             icon=st_icon("bolt"), key="ticket_send",
                             disabled=not last_price):
                    order = store.place_order(
                        order_ticker, side, quantity,
                        order_type=order_type, limit_price=limit_price,
                        market_price=last_price,
                    )
                    if order["status"] == "FILLED":
                        st.toast(f"Ordre exécuté à {order['fill_price']:,.2f} $", icon="✅")
                        st.rerun()
                    elif order["status"] == "OPEN":
                        st.toast("Ordre limite enregistré", icon="⏳")
                        st.rerun()
                    else:
                        st.error(f"Ordre rejeté — {order['reject_reason']}")

                c.caption(
                    "Exécution simulée aux cours réels : les ordres au marché "
                    "sont servis au dernier cours connu, les ordres à cours "
                    "limité lorsque le cours franchit le seuil."
                )

            with c.card(key="openorders"):
                c.section("Ordres en attente", icon="orders")
                pending = store.open_orders()
                if not pending:
                    c.empty_state("Aucun ordre en attente", icon="orders")
                else:
                    for order in pending[:5]:
                        c.render(
                            '<div class="opt-kv__row">'
                            '<span class="opt-kv__k">'
                            + c.chip_html(order["side"], tone="up" if order["side"] == "BUY" else "down")
                            + f' <span class="opt-ticker">{order["ticker"]}</span>'
                            f'<span class="opt-caption"> {order["quantity"]:,.2f} @ '
                            f'{price(order["limit_price"])}</span></span>'
                            f'<span class="opt-kv__v">{c.chip_html("En attente", tone="warn")}</span>'
                            "</div>"
                        )
                    if st.button("Gérer les ordres", width="stretch",
                                 icon=st_icon("orders"), key="ticket_to_orders"):
                        layout.goto("orders")
