# -*- coding: utf-8 -*-
"""News — real headlines from the Yahoo Finance feed.

Nothing on this page is generated: every item is a real article returned for the
tickers being followed. When the feed is unavailable the page says so instead of
showing filler content.
"""

from __future__ import annotations

import streamlit as st

from services import catalog, market, store
from services.context import get as get_context
from ui import components as c
from ui.format import time_ago
from ui.icons import st_icon

ctx = get_context()

followed = list(dict.fromkeys([*store.watchlist(), *store.positions()]))
if not followed:
    followed = list(catalog.DEFAULT_SELECTION)

c.page_header(
    "Actualités",
    eyebrow="Flux de marché",
    icon="news",
    subtitle="Dépêches publiées sur les instruments suivis et détenus, "
             "agrégées depuis Yahoo Finance.",
    aside=c.chip_html("Source : Yahoo Finance", tone="info", icon="live"),
)

controls = st.columns([2.4, 1.2, 1], vertical_alignment="bottom")
selection = controls[0].multiselect(
    "Instruments",
    options=list(catalog.TICKERS),
    default=followed,
    format_func=catalog.label,
    key="news_tickers",
    label_visibility="collapsed",
    placeholder="Filtrer par instrument…",
)
per_ticker = controls[1].selectbox(
    "Dépêches par instrument", [3, 5, 8], index=1, key="news_count",
    label_visibility="collapsed",
    format_func=lambda n: f"{n} par ETF",
)
if controls[2].button("Actualiser", width="stretch", icon=st_icon("refresh"),
                      key="news_refresh"):
    market.news.clear()
    st.rerun()

if not selection:
    c.empty_state(
        "Aucun instrument sélectionné",
        "Choisissez au moins un ETF pour afficher son flux d'actualités.",
        icon="news", variant="info",
    )
    st.stop()

# ---------------------------------------------------------------------------
#  Feed
# ---------------------------------------------------------------------------

placeholder = st.empty()
with placeholder.container():
    with c.card(key="newsload"):
        c.skeleton("text", 6)

items = market.news(tuple(selection), per_ticker)
placeholder.empty()

if not items:
    c.error_state(
        "Flux d'actualités indisponible",
        "Yahoo Finance n'a renvoyé aucune dépêche pour cette sélection. "
        "Le service peut être momentanément inaccessible ou limiter les requêtes.",
    )
    st.stop()

providers = sorted({item["provider"] for item in items})

c.kpi_row([
    c.kpi_html("Dépêches", str(len(items)), icon="news", tone="accent",
               hint=f"sur {len(selection)} instruments"),
    c.kpi_html("Sources", str(len(providers)), icon="database", tone="info",
               hint=", ".join(providers[:3]) + ("…" if len(providers) > 3 else "")),
    c.kpi_html("Plus récente",
               time_ago(items[0]["published"]) if items[0]["published"] else "—",
               icon="clock", tone="violet",
               hint=items[0]["provider"]),
], min_width="14rem")

st.write("")

body = st.columns([2.2, 1])

with body[0]:
    with c.card(key="feed"):
        c.section("Fil d'actualités", subtitle="Les plus récentes en premier",
                  icon="news")
        c.feed([
            {
                "title": item["title"],
                "summary": item["summary"][:260] if item["summary"] else "",
                "url": item["url"],
                "icon": "news",
                "tone": "info",
                "meta": (
                    c.chip_html(item["provider"], tone="flat", icon="database")
                    + (c.chip_html(time_ago(item["published"]), tone="flat", icon="clock")
                       if item["published"] else "")
                    + "".join(
                        c.chip_html(ticker, tone="info", mono=True)
                        for ticker in item["tickers"][:4]
                    )
                ),
            }
            for item in items[:40]
        ])
        c.caption(
            "Les titres renvoient vers l'article original. Optiport n'édite ni "
            "ne reformule le contenu des dépêches."
        )

with body[1]:
    with c.card(key="newsquotes"):
        c.section("Cotations liées", icon="markets",
                  subtitle="Instruments couverts par le fil")
        rows = ctx.rows(selection)
        if rows.empty:
            c.empty_state("Cotations indisponibles", icon="empty")
        else:
            entries = []
            for _, row in rows.iterrows():
                entries.append(
                    '<div class="opt-kv__row">'
                    f'<span class="opt-kv__k">'
                    f'{c.instrument_html(row["ticker"], catalog.sector_of(row["ticker"]))}'
                    "</span>"
                    f'<span class="opt-kv__v">{c.delta_html(row["change_pct"])}</span>'
                    "</div>"
                )
            c.render(f'<div class="opt-kv">{"".join(entries)}</div>')

    with c.card(key="newsvol"):
        c.section("Couverture par instrument", icon="analytics")
        counts: dict[str, int] = {}
        for item in items:
            for ticker in item["tickers"]:
                counts[ticker] = counts.get(ticker, 0) + 1
        if counts:
            ranked = sorted(counts.items(), key=lambda kv: -kv[1])
            c.kv_list([
                (ticker, f"{count} dépêche{'s' if count > 1 else ''}")
                for ticker, count in ranked
            ])
