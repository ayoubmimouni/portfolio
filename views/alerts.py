# -*- coding: utf-8 -*-
"""Alerts — price thresholds evaluated against live quotes."""

from __future__ import annotations

import streamlit as st

from services import catalog, market, store
from services.context import get as get_context
from ui import components as c, layout
from ui.format import percent, price, signed_percent, time_ago
from ui.icons import st_icon

ctx = get_context()
alerts = store.alerts()
active = [a for a in alerts if a["status"] == "ACTIVE"]
triggered = [a for a in alerts if a["status"] == "TRIGGERED"]

c.page_header(
    "Alertes",
    eyebrow="Surveillance des seuils",
    icon="alerts",
    subtitle="Seuils de prix évalués à chaque chargement contre le dernier "
             "cours connu. Un déclenchement génère une notification.",
    aside=c.chip_html(f"{len(active)} actives", tone="up", icon="live")
    + c.chip_html(f"{len(triggered)} déclenchées", tone="warn", icon="bell"),
)

if not ctx.has_quotes:
    layout.data_unavailable_notice()
    st.stop()

# ---------------------------------------------------------------------------
#  Creation
# ---------------------------------------------------------------------------

body = st.columns([1, 2])

with body[0]:
    with c.card("hero", key="newalert"):
        c.section("Nouvelle alerte", subtitle="Seuil de prix sur un instrument",
                  icon="add")

        ticker = st.selectbox(
            "Instrument", list(catalog.TICKERS),
            index=list(catalog.TICKERS).index(store.selected_ticker())
            if store.selected_ticker() in catalog.TICKERS else 0,
            format_func=catalog.label, key="alert_ticker",
        )
        last = ctx.price(ticker)
        row = ctx.quote(ticker)

        c.render(
            '<div class="opt-row opt-row--between" style="margin:0.25rem 0 0.625rem">'
            '<span class="opt-caption">DERNIER COURS</span>'
            '<span class="opt-row"><span class="opt-num" style="font-weight:700">'
            f'{price(last)}</span>'
            + (c.delta_html(row["change_pct"]) if row else "")
            + "</span></div>"
        )

        direction = st.segmented_control(
            "Condition", ["above", "below"], default="above",
            format_func=lambda d: "Au-dessus du seuil" if d == "above" else "Sous le seuil",
            key="alert_direction",
        ) or "above"

        mode = st.radio("Définition du seuil", ["Prix", "Écart en %"],
                        horizontal=True, key="alert_mode")
        if mode == "Prix":
            threshold = st.number_input(
                "Seuil ($)", min_value=0.01,
                value=float(round(last * (1.05 if direction == "above" else 0.95), 2))
                if last else 100.0,
                step=0.5, key="alert_threshold",
            )
        else:
            offset = st.slider("Écart depuis le cours actuel (%)", 0.5, 25.0, 5.0,
                               step=0.5, key="alert_offset")
            multiplier = (1 + offset / 100) if direction == "above" else (1 - offset / 100)
            threshold = round((last or 100.0) * multiplier, 2)
            c.caption(f"Seuil calculé : {price(threshold)}")

        note = st.text_input("Note (optionnelle)", key="alert_note",
                             placeholder="Ex. sortie de range, prise de profit…")

        if last:
            gap = (threshold / last - 1) * 100
            c.kv_list([
                ("Distance au seuil", signed_percent(gap)),
                ("Déclenchement",
                 "Cours ≥ seuil" if direction == "above" else "Cours ≤ seuil"),
            ])

        st.write("")
        if st.button("Créer l'alerte", type="primary", width="stretch",
                     icon=st_icon("alerts"), key="alert_create"):
            store.add_alert(ticker, direction, threshold, note)
            st.toast(f"Alerte créée sur {ticker}", icon="🔔")
            st.rerun()

        c.caption(
            "Les alertes vivent le temps de la session et sont évaluées à "
            "chaque rechargement de page, pas en continu côté serveur."
        )

# ---------------------------------------------------------------------------
#  Active alerts
# ---------------------------------------------------------------------------

with body[1]:
    with c.card(key="activealerts"):
        c.section("Alertes actives", subtitle="Distance au seuil en temps réel",
                  icon="live")
        if not active:
            c.empty_state("Aucune alerte active",
                          "Créez un seuil pour être notifié d'un franchissement.",
                          icon="alerts")
        else:
            for alert in active:
                last = ctx.price(alert["ticker"])
                gap = ((alert["threshold"] / last - 1) * 100) if last else None
                progress = None
                if last and alert["threshold"]:
                    progress = min(
                        100.0,
                        (last / alert["threshold"] * 100) if alert["direction"] == "above"
                        else (alert["threshold"] / last * 100),
                    )

                columns = st.columns([3, 2, 1.6, 0.9], vertical_alignment="center")
                with columns[0]:
                    c.render(
                        '<div class="opt-row">'
                        + c.instrument_html(alert["ticker"],
                                            catalog.sector_of(alert["ticker"]))
                        + c.chip_html(
                            "≥" if alert["direction"] == "above" else "≤",
                            tone="up" if alert["direction"] == "above" else "down")
                        + '<span class="opt-num" style="font-weight:700">'
                        f'{price(alert["threshold"])}</span></div>'
                        + (f'<div class="opt-caption">{c.esc(alert["note"])}</div>'
                           if alert["note"] else "")
                    )
                with columns[1]:
                    c.render(
                        '<div class="opt-caption">COURS ACTUEL</div>'
                        f'<div class="opt-num" style="font-weight:600">{price(last)}</div>'
                        + (c.bar_html(progress) if progress is not None else "")
                    )
                with columns[2]:
                    c.render(
                        '<div class="opt-caption">DISTANCE</div>'
                        + (c.delta_html(gap) if gap is not None
                           else '<span class="opt-faint">—</span>')
                    )
                with columns[3]:
                    if st.button("", key=f"del_{alert['id']}", width="stretch",
                                 icon=st_icon("delete"), help="Supprimer l'alerte"):
                        store.remove_alert(alert["id"])
                        st.rerun()

    if triggered:
        with c.card(key="triggered"):
            c.section("Alertes déclenchées", icon="bell",
                      subtitle="Réactivez une alerte pour la surveiller à nouveau")
            for alert in triggered:
                columns = st.columns([3, 2, 1.4, 1.4], vertical_alignment="center")
                with columns[0]:
                    c.render(
                        '<div class="opt-row">'
                        + c.instrument_html(alert["ticker"],
                                            catalog.sector_of(alert["ticker"]))
                        + c.chip_html("Déclenchée", tone="warn", icon="check")
                        + "</div>"
                    )
                with columns[1]:
                    c.render(
                        '<div class="opt-caption">SEUIL / COURS DÉCLENCHEUR</div>'
                        f'<div class="opt-num">{price(alert["threshold"])} → '
                        f'{price(alert["triggered_price"])}</div>'
                    )
                with columns[2]:
                    c.render(
                        '<div class="opt-caption">QUAND</div>'
                        f'<div class="opt-caption">{time_ago(alert["triggered_at"])}</div>'
                    )
                with columns[3]:
                    if st.button("Réactiver", key=f"reset_{alert['id']}",
                                 width="stretch", icon=st_icon("refresh")):
                        store.reset_alert(alert["id"])
                        st.rerun()

st.write("")

# ---------------------------------------------------------------------------
#  Signal watch
# ---------------------------------------------------------------------------

with c.card(key="signalwatch"):
    c.section(
        "Surveillance des signaux techniques",
        subtitle="Instruments dont le signal composite justifie une attention",
        icon="bolt",
        aside=c.chip_html("Indicateur technique, non prédictif", tone="warn",
                          icon="info"),
    )
    universe = ctx.quotes[ctx.quotes["ticker"] != catalog.BENCHMARK]
    flagged = universe[universe["signal"].isin(["Strong Buy", "Avoid", "Reduce"])]

    if flagged.empty:
        c.empty_state("Aucun signal extrême",
                      "Aucun instrument ne présente de signal fort actuellement.",
                      icon="check", variant="success")
    else:
        frame = flagged.copy()
        frame["sector"] = frame["ticker"].map(catalog.sector_of)
        c.render(c.table_html(frame, [
            c.Column("ticker", "ETF", align="left",
                     render=lambda v, r: c.instrument_html(str(v), r["sector"])),
            c.Column("price", "Cours",
                     render=lambda v, r: f'<span class="opt-num">{price(v)}</span>'),
            c.Column("change_pct", "Jour", render=lambda v, r: c.delta_html(v)),
            c.Column("rsi", "RSI 14",
                     render=lambda v, r: f'<span class="opt-num">{v:,.1f}</span>'),
            c.Column("position_52w", "Range 52s",
                     render=lambda v, r: (
                         f'<div class="opt-num">{percent(v, 0)}</div>' + c.bar_html(v or 0)
                     )),
            c.Column("signal", "Signal", align="center",
                     render=lambda v, r: c.signal_html(str(v))),
            c.Column("spark", "30 séances", sortable=False,
                     render=lambda v, r: c.sparkline_html(v or [], width=110, height=30)),
        ]))
        c.caption(f"Composition du signal : {market.SIGNAL_RULES}")
