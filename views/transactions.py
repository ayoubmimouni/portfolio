# -*- coding: utf-8 -*-
"""Transactions — cash and settlement ledger."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services import catalog, store
from services.context import get as get_context
from ui import charts, components as c, layout
from ui.format import money, signed_money, time_ago
from ui.icons import st_icon

ctx = get_context()
ledger = store.transactions()

TYPE_META = {
    "BUY": ("Achat", "up", "buy"),
    "SELL": ("Vente", "down", "sell"),
    "DEPOSIT": ("Dotation", "info", "cash"),
}

c.page_header(
    "Transactions",
    eyebrow="Journal des mouvements",
    icon="transactions",
    subtitle="Toutes les opérations réglées sur le compte simulé : exécutions, "
             "flux de trésorerie et dotation initiale.",
    aside=c.chip_html(f"{len(ledger)} mouvements", tone="flat", icon="transactions"),
)

if len(ledger) <= 1:
    c.empty_state(
        "Aucune transaction",
        "Le journal ne contient que la dotation initiale. Exécutez un ordre "
        "pour voir apparaître les mouvements.",
        icon="transactions", variant="info",
    )
    if st.button("Passer un ordre", type="primary", icon=st_icon("trading"),
                 key="tx_to_trading"):
        layout.goto("trading")

frame = pd.DataFrame([{
    "timestamp": entry["timestamp"],
    "type": entry["type"],
    "ticker": entry["ticker"] or "—",
    "sector": catalog.sector_of(entry["ticker"]) if entry["ticker"] else "Trésorerie",
    "quantity": entry["quantity"],
    "price": entry["price"],
    "amount": entry["amount"],
    "note": entry["note"],
} for entry in ledger])

# ---------------------------------------------------------------------------
#  Summary
# ---------------------------------------------------------------------------

purchases = frame[frame["type"] == "BUY"]["amount"].sum()
sales = frame[frame["type"] == "SELL"]["amount"].sum()
net_flow = frame[frame["type"].isin(["BUY", "SELL"])]["amount"].sum()

c.kpi_row([
    c.kpi_html("Achats cumulés", money(abs(purchases)), icon="buy", tone="up",
               hint=f"{int((frame['type'] == 'BUY').sum())} opérations"),
    c.kpi_html("Ventes cumulées", money(abs(sales)), icon="sell", tone="down",
               hint=f"{int((frame['type'] == 'SELL').sum())} opérations"),
    c.kpi_html("Flux net", signed_money(net_flow), icon="transactions",
               tone="up" if net_flow >= 0 else "down",
               hint="ventes moins achats"),
    c.kpi_html("Liquidités actuelles", money(ctx.valuation.get("cash", 0)),
               icon="cash", tone="accent",
               hint=f"dotation de {money(store.INITIAL_CASH)}"),
], min_width="13rem")

st.write("")

body = st.columns([2.1, 1])

with body[0]:
    with c.card(key="ledger"):
        c.section("Journal", subtitle="Recherche, filtre par type et pagination",
                  icon="table")

        columns = [
            c.Column("timestamp", "Date", align="left",
                     render=lambda v, r: (
                         f'<div class="opt-num">{v:%d %b %Y · %H:%M}</div>'
                         f'<div class="opt-caption">{time_ago(v)}</div>'
                     )),
            c.Column("type", "Opération", align="left",
                     render=lambda v, r: c.chip_html(
                         TYPE_META.get(str(v), (str(v), "flat", "info"))[0],
                         tone=TYPE_META.get(str(v), (str(v), "flat", "info"))[1],
                         icon=TYPE_META.get(str(v), (str(v), "flat", "info"))[2])),
            c.Column("ticker", "Instrument", align="left",
                     render=lambda v, r: (
                         c.instrument_html(str(v), r["sector"]) if v != "—"
                         else '<span class="opt-faint">Trésorerie</span>'
                     )),
            c.Column("quantity", "Quantité",
                     render=lambda v, r: (
                         f'<span class="opt-num">{v:,.4f}</span>' if v
                         else '<span class="opt-faint">—</span>'
                     )),
            c.Column("price", "Prix",
                     render=lambda v, r: (
                         f'<span class="opt-num">{v:,.2f}</span>' if v
                         else '<span class="opt-faint">—</span>'
                     )),
            c.Column("amount", "Montant",
                     render=lambda v, r: (
                         f'<span class="opt-num" style="font-weight:600;color:'
                         f'{"var(--opt-up-text)" if v >= 0 else "var(--opt-down-text)"}">'
                         f'{signed_money(v, 2)}</span>'
                     )),
            c.Column("note", "Détail", align="left", sortable=False,
                     render=lambda v, r: f'<span class="opt-caption">{c.esc(v)}</span>'),
        ]

        visible = c.data_table(
            frame, columns, key="tx_ledger",
            search_keys=("ticker", "sector", "note", "type"),
            filters=[c.Filter("type", "Type", tuple(TYPE_META))],
            page_size=12, default_sort="timestamp", default_desc=True,
            search_placeholder="Rechercher un instrument ou un libellé…",
        )

        st.write("")
        st.download_button(
            "Exporter le journal (CSV)",
            data=frame.to_csv(index=False).encode("utf-8"),
            file_name="optiport_transactions.csv",
            mime="text/csv",
            icon=st_icon("download"),
            key="tx_export",
        )

with body[1]:
    with c.card(key="flows"):
        c.section("Flux par instrument", icon="analytics",
                  subtitle="Solde net des achats et ventes")
        trades = frame[frame["type"].isin(["BUY", "SELL"])]
        if trades.empty:
            c.empty_state("Aucun flux", "Aucune exécution enregistrée.", icon="empty")
        else:
            grouped = trades.groupby("ticker")["amount"].sum().sort_values()
            st.plotly_chart(
                charts.signed_bar(grouped.index.tolist(), grouped.tolist(),
                                  height=260, suffix=" $", horizontal=True),
                width="stretch", theme=None, config=charts.CONFIG,
            )

    with c.card(key="cashline"):
        c.section("Évolution des liquidités", icon="cash",
                  subtitle="Reconstituée depuis le journal")
        cash_frame = frame.sort_values("timestamp").copy()
        cash_frame["solde"] = cash_frame["amount"].cumsum()
        if len(cash_frame) < 2:
            c.empty_state("Historique insuffisant", icon="empty")
        else:
            st.plotly_chart(
                charts.area(cash_frame["timestamp"], cash_frame["solde"].tolist(),
                            height=200, tone="accent", value_prefix="$"),
                width="stretch", theme=None, config=charts.CONFIG,
            )
