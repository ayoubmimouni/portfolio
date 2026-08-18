# -*- coding: utf-8 -*-
"""Settings — appearance, data sources, trading defaults, maintenance."""

from __future__ import annotations

import streamlit as st

from services import api_client, catalog, store
from services.context import get as get_context
from ui import components as c, styles, tokens
from ui.format import money, percent
from ui.icons import st_icon

ctx = get_context()
prefs = store.prefs()

c.page_header(
    "Paramètres",
    eyebrow="Configuration de l'espace de travail",
    icon="settings",
    subtitle="Apparence, sources de données, valeurs par défaut du moteur "
             "d'allocation et maintenance du compte simulé.",
)

tabs = st.tabs(["Apparence", "Données & API", "Trading", "Maintenance"])

# ===========================================================================
#  Appearance
# ===========================================================================

with tabs[0]:
    columns = st.columns([1.3, 1])

    with columns[0]:
        with c.card(key="appearance"):
            c.section("Thème", subtitle="Palette et densité d'affichage", icon="theme")

            palette = st.radio(
                "Palette de surfaces",
                list(tokens.PALETTES),
                index=list(tokens.PALETTES).index(prefs["palette"]),
                format_func=lambda name: tokens.PALETTE_LABELS[name],
                horizontal=True,
                key="settings_palette",
                captions=["Bleu nuit — palette de référence",
                          "Graphite — température neutre"],
            )
            density = st.select_slider(
                "Densité de l'interface",
                options=list(styles.DENSITY_LABELS),
                value=prefs["density"],
                format_func=lambda name: styles.DENSITY_LABELS[name],
                key="settings_density",
            )
            show_signals = st.toggle(
                "Afficher les signaux techniques dans les tableaux",
                value=prefs["show_signals"], key="settings_signals",
            )
            chart_period = st.segmented_control(
                "Période par défaut des graphiques",
                ["1M", "3M", "6M", "1A", "2A", "5A"],
                default=prefs["chart_period"], key="settings_period",
            ) or prefs["chart_period"]

            if st.button("Appliquer", type="primary", width="stretch",
                         icon=st_icon("check"), key="settings_apply_theme"):
                store.set_pref("palette", palette)
                store.set_pref("density", density)
                store.set_pref("show_signals", show_signals)
                store.set_pref("chart_period", chart_period)
                st.toast("Préférences enregistrées", icon="🎨")
                st.rerun()

            c.caption(
                "Optiport est conçu en mode sombre, comme les terminaux de "
                "marché : les deux palettes conservent des contrastes conformes "
                "aux recommandations d'accessibilité."
            )

    with columns[1]:
        with c.card(key="preview"):
            c.section("Aperçu", subtitle="Rendu des composants", icon="grid")
            c.kpi_row([
                c.kpi_html("Exemple KPI", "$128,450", delta=1.84, icon="value",
                           tone="accent", spark=[100, 102, 101, 106, 108, 112]),
            ], columns=1)
            st.write("")
            c.render(
                '<div class="opt-row opt-row--wrap">'
                + c.signal_html("Strong Buy") + c.signal_html("Hold")
                + c.signal_html("Avoid")
                + c.chip_html("Chip neutre", tone="flat", icon="info")
                + "</div>"
            )
            st.write("")
            c.render(c.bar_html(68, large=True))
            st.write("")
            c.tiles([("Volatilité", "18.4%"), ("Sharpe", "1.24"), ("VaR 95%", "1.9%")])

# ===========================================================================
#  Data & API
# ===========================================================================

with tabs[1]:
    columns = st.columns([1.3, 1])

    with columns[0]:
        with c.card(key="apisettings"):
            c.section("Backend d'optimisation",
                      subtitle="API FastAPI exposant le modèle et l'optimiseur",
                      icon="api")

            api_url = st.text_input(
                "URL de l'API", value=prefs["api_url"], key="settings_api_url",
                icon=st_icon("api"),
                help="Par défaut http://localhost:8000 — lancez "
                     "`uvicorn api:app --port 8000` depuis le dossier Optiport.",
            )
            model_path = st.text_input(
                "Répertoire des modèles LSTM",
                value=api_client.DEFAULT_MODEL_PATH,
                key="settings_model_path", icon=st_icon("model"),
                help="Chemin relatif au backend, contenant `<TICKER>_model.keras` "
                     "et `scalers.pkl`.",
            )

            actions = st.columns(2)
            if actions[0].button("Enregistrer", type="primary", width="stretch",
                                 icon=st_icon("check"), key="settings_save_api"):
                store.set_pref("api_url", api_url.strip() or api_client.DEFAULT_BASE_URL)
                api_client.health.clear()
                st.toast("URL enregistrée", icon="🔌")
                st.rerun()
            if actions[1].button("Tester la connexion", width="stretch",
                                 icon=st_icon("refresh"), key="settings_test_api"):
                api_client.health.clear()
                st.rerun()

            probe = api_client.health(api_client.base_url())
            if probe:
                c.success_state(
                    "Backend accessible",
                    f"Version {probe.get('version', '—')} · statut "
                    f"{probe.get('status', '—')}",
                )
            else:
                c.error_state(
                    "Backend injoignable",
                    f"Aucune réponse de {api_client.base_url()}/health.",
                )
                st.code("uvicorn api:app --reload --port 8000", language="bash")

        with c.card(key="endpoints"):
            c.section("Points d'entrée utilisés", icon="database")
            c.kv_list([
                ("POST /smart-invest", "Prévision + optimisation combinées"),
                ("POST /forecast", "Rendements prévus à 22 séances"),
                ("POST /chart-data", "Séries de prix normalisées et YTD"),
                ("POST /efficient-frontier", "Frontière efficiente"),
                ("GET /health", "Sonde de disponibilité"),
            ])
            c.caption(
                "Optiport ne duplique aucun calcul : l'optimiseur et le "
                "forecaster restent la seule source de vérité côté backend."
            )

    with columns[1]:
        with c.card(key="marketdata"):
            c.section("Données de marché", subtitle="Yahoo Finance via yfinance",
                      icon="live")
            c.kv_list([
                ("Instruments couverts", f"{len(catalog.TICKERS)} ETF"),
                ("Indice de référence", catalog.BENCHMARK_LABEL),
                ("Cache cotations", "5 minutes"),
                ("Cache actualités", "15 minutes"),
                ("Cache encours (AUM)", "60 minutes"),
                ("Statut cotations",
                 c.chip_html("Disponibles", tone="up", icon="check") if ctx.has_quotes
                 else c.chip_html("Indisponibles", tone="down", icon="error")),
            ])
            st.write("")
            if st.button("Vider le cache de données", width="stretch",
                         icon=st_icon("refresh"), key="settings_clear_cache"):
                st.cache_data.clear()
                st.toast("Cache vidé — rechargement des données", icon="🔄")
                st.rerun()
            c.caption(
                "Les cotations sont mises en cache par lot : une seule requête "
                "réseau alimente toutes les pages pendant la durée du cache."
            )

# ===========================================================================
#  Trading defaults
# ===========================================================================

with tabs[2]:
    columns = st.columns([1.3, 1])

    with columns[0]:
        with c.card(key="tradingsettings"):
            c.section("Valeurs par défaut", subtitle="Appliquées au moteur d'allocation",
                      icon="trading")

            default_amount = st.number_input(
                "Montant à investir par défaut ($)",
                min_value=1_000, max_value=10_000_000,
                value=int(prefs["default_amount"]), step=1_000, format="%d",
                key="settings_amount", icon=st_icon("cash"),
            )
            risk_free = st.slider(
                "Taux sans risque annuel (%)", 0.0, 10.0,
                float(prefs["risk_free_rate"] * 100), step=0.25,
                key="settings_rf",
                help="Utilisé pour le ratio de Sharpe, l'optimisation max Sharpe "
                     "et les mesures de risque des pages Portefeuille et Analytique.",
            )
            currency = st.selectbox(
                "Devise d'affichage", ["USD"], key="settings_currency",
                help="Les ETF couverts sont cotés en dollars américains ; "
                     "aucune conversion n'est appliquée.",
            )
            default_universe = st.multiselect(
                "Univers par défaut",
                options=list(catalog.TICKERS),
                default=store.universe(),
                format_func=catalog.label,
                key="settings_universe",
            )

            if st.button("Enregistrer", type="primary", width="stretch",
                         icon=st_icon("check"), key="settings_save_trading"):
                store.set_pref("default_amount", int(default_amount))
                store.set_pref("risk_free_rate", risk_free / 100)
                store.set_pref("currency", currency)
                if default_universe:
                    store.set_universe(default_universe)
                st.toast("Paramètres de trading enregistrés", icon="💾")
                st.rerun()

    with columns[1]:
        with c.card(key="strategies"):
            c.section("Stratégies disponibles", subtitle="Exposées par l'optimiseur",
                      icon="model")
            for name, profile in tokens.RISK_PROFILES.items():
                c.render(
                    '<div class="opt-kv__row">'
                    '<span class="opt-kv__k">'
                    + c.chip_html(name, tone="info", icon=profile["icon"])
                    + f'<span class="opt-caption">{c.esc(profile["caption"])}</span></span>'
                    f'<span class="opt-kv__v">'
                    + c.chip_html(profile["strategy"], tone="flat", mono=True)
                    + "</span></div>"
                )

        with c.card(key="accountinfo"):
            c.section("Compte simulé", icon="shield")
            c.kv_list([
                ("Mode", c.chip_html(store.ACCOUNT_MODE, tone="warn", icon="shield")),
                ("Dotation initiale", money(store.INITIAL_CASH)),
                ("Liquidités actuelles", money(ctx.valuation.get("cash", 0))),
                ("Valeur totale", money(ctx.valuation.get("equity", 0))),
                ("Taux d'investissement", percent(ctx.valuation.get("invested_pct", 0), 1)),
            ])

# ===========================================================================
#  Maintenance
# ===========================================================================

with tabs[3]:
    columns = st.columns([1.3, 1])

    with columns[0]:
        with c.card(key="maintenance"):
            c.section("Réinitialisation", subtitle="Actions irréversibles sur la session",
                      icon="warning")
            st.warning(
                "La réinitialisation efface les positions, les ordres, le journal "
                "des transactions et les alertes de cette session. Les préférences "
                "et la liste de suivi sont conservées.",
                icon=st_icon("warning"),
            )
            confirm = st.checkbox("Je confirme vouloir réinitialiser le compte simulé",
                                  key="settings_confirm_reset")
            if st.button("Réinitialiser le compte", type="primary", width="stretch",
                         icon=st_icon("refresh"), disabled=not confirm,
                         key="settings_reset"):
                store.reset_account()
                st.toast("Compte simulé réinitialisé", icon="♻️")
                st.rerun()

    with columns[1]:
        with c.card(key="about"):
            c.section("À propos", icon="info")
            c.kv_list([
                ("Application", "Optiport"),
                ("Version de l'interface", "2.1"),
                ("Moteur", "LSTM par ticker + optimisation moyenne-variance"),
                ("Données de marché", "Yahoo Finance"),
                ("Framework", f"Streamlit {st.__version__}"),
            ])
            c.caption(
                "Optiport est un outil d'analyse et de démonstration. Il ne "
                "fournit pas de conseil en investissement personnalisé et "
                "n'exécute aucun ordre réel."
            )
