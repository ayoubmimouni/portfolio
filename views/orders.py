# -*- coding: utf-8 -*-
"""Orders — order book of the simulated account."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services import catalog, store
from services.context import get as get_context
from ui import components as c, layout
from ui.format import money, percent, price, time_ago
from ui.icons import st_icon

ctx = get_context()
all_orders = store.orders()

STATUS_TONE = {"FILLED": "up", "OPEN": "warn", "CANCELLED": "flat", "REJECTED": "down"}
STATUS_LABEL = {"FILLED": "Exécuté", "OPEN": "En attente",
                "CANCELLED": "Annulé", "REJECTED": "Rejeté"}

c.page_header(
    "Carnet d'ordres",
    eyebrow="Exécution simulée",
    icon="orders",
    subtitle="Historique complet des ordres envoyés sur le compte de "
             "démonstration, avec suivi des ordres à cours limité.",
    aside=c.chip_html(store.ACCOUNT_MODE, tone="warn", icon="shield")
    + c.chip_html(f"{len(all_orders)} ordres", tone="flat", icon="orders"),
)

if not all_orders:
    c.empty_state(
        "Aucun ordre enregistré",
        "Passez un ordre depuis la page Trading, ou exécutez un plan de "
        "rééquilibrage issu de l'optimiseur.",
        icon="orders", variant="info",
    )
    if st.button("Aller au trading", type="primary", icon=st_icon("trading"),
                 key="orders_to_trading"):
        layout.goto("trading")
    st.stop()

# ---------------------------------------------------------------------------
#  Summary
# ---------------------------------------------------------------------------

filled = [o for o in all_orders if o["status"] == "FILLED"]
pending = [o for o in all_orders if o["status"] == "OPEN"]
rejected = [o for o in all_orders if o["status"] == "REJECTED"]
volume = sum((o["fill_price"] or 0) * o["quantity"] for o in filled)
fill_rate = len(filled) / len(all_orders) * 100 if all_orders else 0

c.kpi_row([
    c.kpi_html("Ordres exécutés", str(len(filled)), icon="check", tone="up",
               hint=f"{percent(fill_rate, 0)} du total"),
    c.kpi_html("En attente", str(len(pending)), icon="clock", tone="warn",
               hint="ordres à cours limité actifs"),
    c.kpi_html("Rejetés", str(len(rejected)), icon="error", tone="down",
               hint="liquidités ou position insuffisantes"),
    c.kpi_html("Volume traité", money(volume), icon="value", tone="accent",
               hint="somme des montants exécutés"),
], min_width="13rem")

st.write("")

# ---------------------------------------------------------------------------
#  Pending orders — cancellable
# ---------------------------------------------------------------------------

if pending:
    with c.card(key="pending"):
        c.section("Ordres en attente", icon="clock",
                  subtitle="Exécutés automatiquement dès que le cours franchit la limite")
        for order in pending:
            columns = st.columns([3, 2, 2, 1.2], vertical_alignment="center")
            last = ctx.price(order["ticker"])
            distance = None
            if last and order["limit_price"]:
                distance = (order["limit_price"] / last - 1) * 100

            with columns[0]:
                c.render(
                    '<div class="opt-row">'
                    + c.chip_html("Achat" if order["side"] == "BUY" else "Vente",
                                  tone="up" if order["side"] == "BUY" else "down",
                                  icon="buy" if order["side"] == "BUY" else "sell")
                    + c.instrument_html(order["ticker"], catalog.sector_of(order["ticker"]))
                    + "</div>"
                )
            with columns[1]:
                c.render(
                    '<div class="opt-caption">QUANTITÉ / LIMITE</div>'
                    f'<div class="opt-num" style="font-weight:600">'
                    f'{order["quantity"]:,.4f} @ {price(order["limit_price"])}</div>'
                )
            with columns[2]:
                c.render(
                    '<div class="opt-caption">COURS ACTUEL</div>'
                    f'<div class="opt-row"><span class="opt-num" style="font-weight:600">'
                    f'{price(last)}</span>'
                    + (c.chip_html(f"{distance:+.2f}% à parcourir",
                                   tone="flat") if distance is not None else "")
                    + "</div>"
                )
            with columns[3]:
                if st.button("Annuler", key=f"cancel_{order['id']}", width="stretch",
                             icon=st_icon("close")):
                    store.cancel_order(order["id"])
                    st.toast("Ordre annulé", icon="🚫")
                    st.rerun()
        c.caption(
            "Les ordres limites sont évalués à chaque chargement de page contre "
            "le dernier cours connu."
        )
    st.write("")

# ---------------------------------------------------------------------------
#  History
# ---------------------------------------------------------------------------

frame = pd.DataFrame([{
    "id": o["id"],
    "timestamp": o["timestamp"],
    "ticker": o["ticker"],
    "sector": catalog.sector_of(o["ticker"]),
    "side": o["side"],
    "type": o["type"],
    "quantity": o["quantity"],
    "reference": o["fill_price"] or o["limit_price"],
    "notional": (o["fill_price"] or o["limit_price"] or 0) * o["quantity"],
    "status": o["status"],
    "note": o["reject_reason"] or "",
} for o in all_orders])

with c.card(key="history"):
    c.section("Historique des ordres", icon="table",
              subtitle="Recherche, filtres et tri sur l'ensemble du carnet")

    columns = [
        c.Column("timestamp", "Horodatage", align="left",
                 render=lambda v, r: (
                     f'<div class="opt-num">{v:%d %b %H:%M:%S}</div>'
                     f'<div class="opt-caption">{time_ago(v)}</div>'
                 )),
        c.Column("ticker", "Instrument", align="left",
                 render=lambda v, r: c.instrument_html(str(v), r["sector"])),
        c.Column("side", "Sens", align="center",
                 render=lambda v, r: c.chip_html(
                     "Achat" if v == "BUY" else "Vente",
                     tone="up" if v == "BUY" else "down",
                     icon="buy" if v == "BUY" else "sell")),
        c.Column("type", "Type", align="center",
                 render=lambda v, r: c.chip_html(
                     "Marché" if v == "MARKET" else "Limite", tone="flat")),
        c.Column("quantity", "Quantité",
                 render=lambda v, r: f'<span class="opt-num">{v:,.4f}</span>'),
        c.Column("reference", "Prix",
                 render=lambda v, r: f'<span class="opt-num">{price(v)}</span>'),
        c.Column("notional", "Montant",
                 render=lambda v, r: f'<span class="opt-num opt-td--strong">{money(v, 2)}</span>'),
        c.Column("status", "Statut", align="center",
                 render=lambda v, r: c.chip_html(
                     STATUS_LABEL.get(str(v), str(v)),
                     tone=STATUS_TONE.get(str(v), "flat"),
                     title=r["note"] or None)),
    ]

    c.data_table(
        frame, columns, key="orders_history",
        search_keys=("ticker", "sector", "side", "status"),
        filters=[
            c.Filter("status", "Statut", tuple(STATUS_LABEL)),
            c.Filter("side", "Sens", ("BUY", "SELL")),
        ],
        page_size=12, default_sort="timestamp", default_desc=True,
    )

if rejected:
    with st.expander(f"Ordres rejetés ({len(rejected)})", icon=st_icon("warning")):
        c.kv_list([
            (f"{o['side']} {o['quantity']:,.2f} {o['ticker']}", o["reject_reason"] or "—")
            for o in rejected[:10]
        ])
