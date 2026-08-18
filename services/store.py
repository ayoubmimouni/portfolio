# -*- coding: utf-8 -*-
"""Session-scoped application state.

Holds the user preferences, the watchlist, the alert rules and a **paper
trading** account (orders, positions, cash, transaction ledger). Nothing here
is a real brokerage account: the account is explicitly simulated and every
screen that shows it says so. Fills always use live market prices from
`services.market` — no invented quotes.

State lives in `st.session_state`, so it is per-browser-session and resets when
the server restarts. That keeps the demo self-contained and avoids pretending
to be a persistent system of record.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Iterable, Literal, Sequence

import pandas as pd
import streamlit as st

from services import catalog

ACCOUNT_MODE = "Paper"
INITIAL_CASH = 250_000.0

Side = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT"]
OrderStatus = Literal["OPEN", "FILLED", "CANCELLED", "REJECTED"]

DEFAULT_PREFS: dict[str, Any] = {
    "palette": "midnight",
    "density": "comfortable",
    "api_url": "http://localhost:8000",
    "risk_free_rate": 0.05,
    "currency": "USD",
    "default_amount": 100_000,
    "chart_period": "6M",
    "show_signals": True,
}

DEFAULT_USER: dict[str, Any] = {
    "name": "Ayoub Mimouni",
    "initials": "AM",
    "role": "Portfolio Manager",
    "desk": "Multi-Asset / Thematic ETF",
    "plan": "Professional",
    "member_since": "2026",
}


# ---------------------------------------------------------------------------
#  Bootstrap
# ---------------------------------------------------------------------------

def init() -> None:
    """Create default state. Safe to call on every run."""
    state = st.session_state
    state.setdefault("prefs", dict(DEFAULT_PREFS))
    state.setdefault("user", dict(DEFAULT_USER))
    state.setdefault("signed_in", True)
    state.setdefault("watchlist", list(catalog.DEFAULT_SELECTION))
    state.setdefault("universe", list(catalog.DEFAULT_SELECTION))
    state.setdefault("positions", {})
    state.setdefault("cash", INITIAL_CASH)
    state.setdefault("orders", [])
    state.setdefault("transactions", [])
    state.setdefault("alerts", [])
    state.setdefault("notifications", [])
    state.setdefault("optimization", None)
    state.setdefault("selected_ticker", catalog.DEFAULT_SELECTION[0])

    if not state["transactions"]:
        state["transactions"].append({
            "id": _new_id(),
            "timestamp": datetime.now(),
            "type": "DEPOSIT",
            "ticker": None,
            "quantity": None,
            "price": None,
            "amount": INITIAL_CASH,
            "note": "Dotation initiale du compte simulé",
        })


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


# ---------------------------------------------------------------------------
#  Preferences & identity
# ---------------------------------------------------------------------------

def prefs() -> dict[str, Any]:
    return st.session_state["prefs"]


def set_pref(key: str, value: Any) -> None:
    st.session_state["prefs"][key] = value


def user() -> dict[str, Any]:
    return st.session_state["user"]


# ---------------------------------------------------------------------------
#  Watchlist & universe
# ---------------------------------------------------------------------------

def watchlist() -> list[str]:
    return st.session_state["watchlist"]


def is_watched(ticker: str) -> bool:
    return ticker in st.session_state["watchlist"]


def toggle_watch(ticker: str) -> bool:
    """Add/remove from the watchlist. Returns the new membership state."""
    items = st.session_state["watchlist"]
    if ticker in items:
        items.remove(ticker)
        return False
    items.append(ticker)
    return True


def universe() -> list[str]:
    """Tickers currently selected for optimisation."""
    return st.session_state["universe"]


def set_universe(tickers: Sequence[str]) -> None:
    st.session_state["universe"] = list(tickers)


def selected_ticker() -> str:
    return st.session_state["selected_ticker"]


def select_ticker(ticker: str) -> None:
    st.session_state["selected_ticker"] = ticker


# ---------------------------------------------------------------------------
#  Account
# ---------------------------------------------------------------------------

def cash() -> float:
    return float(st.session_state["cash"])


def positions() -> dict[str, dict[str, float]]:
    """`ticker -> {quantity, avg_price}` for non-zero holdings."""
    return st.session_state["positions"]


def orders() -> list[dict[str, Any]]:
    return st.session_state["orders"]


def open_orders() -> list[dict[str, Any]]:
    return [o for o in st.session_state["orders"] if o["status"] == "OPEN"]


def transactions() -> list[dict[str, Any]]:
    return st.session_state["transactions"]


def place_order(
    ticker: str,
    side: Side,
    quantity: float,
    *,
    order_type: OrderType = "MARKET",
    limit_price: float | None = None,
    market_price: float | None = None,
) -> dict[str, Any]:
    """Submit a paper order.

    Market orders fill immediately at `market_price`. Limit orders stay OPEN
    until `settle()` sees a crossing price. Returns the order, whose `status`
    and `reject_reason` describe the outcome.
    """
    order: dict[str, Any] = {
        "id": _new_id(),
        "timestamp": datetime.now(),
        "ticker": ticker,
        "side": side,
        "quantity": float(quantity),
        "type": order_type,
        "limit_price": float(limit_price) if limit_price else None,
        "status": "OPEN",
        "fill_price": None,
        "filled_at": None,
        "reject_reason": None,
    }

    if quantity <= 0:
        order.update(status="REJECTED", reject_reason="Quantité invalide")
        st.session_state["orders"].insert(0, order)
        return order

    if side == "SELL":
        held = positions().get(ticker, {}).get("quantity", 0.0)
        if quantity > held + 1e-9:
            order.update(
                status="REJECTED",
                reject_reason=f"Position insuffisante ({held:,.4f} détenus)",
            )
            st.session_state["orders"].insert(0, order)
            return order

    if order_type == "MARKET":
        if not market_price:
            order.update(status="REJECTED", reject_reason="Prix de marché indisponible")
            st.session_state["orders"].insert(0, order)
            return order
        if side == "BUY" and quantity * market_price > cash() + 1e-6:
            order.update(
                status="REJECTED",
                reject_reason=f"Liquidités insuffisantes ({cash():,.2f} disponibles)",
            )
            st.session_state["orders"].insert(0, order)
            return order
        st.session_state["orders"].insert(0, order)
        _fill(order, market_price)
        return order

    if not limit_price:
        order.update(status="REJECTED", reject_reason="Prix limite manquant")
    st.session_state["orders"].insert(0, order)
    return order


def cancel_order(order_id: str) -> bool:
    for order in st.session_state["orders"]:
        if order["id"] == order_id and order["status"] == "OPEN":
            order["status"] = "CANCELLED"
            return True
    return False


def _fill(order: dict[str, Any], price: float) -> None:
    """Apply a fill to cash, positions and the transaction ledger."""
    ticker, side, quantity = order["ticker"], order["side"], order["quantity"]
    notional = quantity * price
    book = positions()

    if side == "BUY":
        st.session_state["cash"] = cash() - notional
        current = book.get(ticker, {"quantity": 0.0, "avg_price": 0.0})
        total_quantity = current["quantity"] + quantity
        current["avg_price"] = (
            (current["avg_price"] * current["quantity"] + notional) / total_quantity
            if total_quantity else 0.0
        )
        current["quantity"] = total_quantity
        book[ticker] = current
    else:
        st.session_state["cash"] = cash() + notional
        current = book.get(ticker)
        if current:
            current["quantity"] -= quantity
            if current["quantity"] <= 1e-9:
                book.pop(ticker, None)

    order.update(status="FILLED", fill_price=price, filled_at=datetime.now())
    st.session_state["transactions"].insert(0, {
        "id": _new_id(),
        "timestamp": order["filled_at"],
        "type": side,
        "ticker": ticker,
        "quantity": quantity,
        "price": price,
        "amount": -notional if side == "BUY" else notional,
        "note": f"{order['type'].title()} · {catalog.sector_of(ticker)}",
    })
    notify(
        f"Ordre exécuté · {side} {quantity:,.2f} {ticker}",
        f"{quantity:,.2f} @ {price:,.2f} $ — {notional:,.2f} $",
        tone="up" if side == "BUY" else "warn",
        icon="check",
    )


# ---------------------------------------------------------------------------
#  Valuation
# ---------------------------------------------------------------------------

def valuation(quotes: pd.DataFrame | None) -> dict[str, Any]:
    """Mark the account to market.

    `quotes` is a `services.market.snapshot()` frame. Returns totals plus a
    per-holding breakdown; missing prices are skipped rather than guessed.
    """
    prices: dict[str, float] = {}
    previous: dict[str, float] = {}
    if quotes is not None and not quotes.empty:
        indexed = quotes.set_index("ticker")
        prices = indexed["price"].to_dict()
        previous = indexed["previous_close"].to_dict()

    holdings: list[dict[str, Any]] = []
    market_value = cost_basis = day_pnl = 0.0

    for ticker, position in positions().items():
        quantity = position["quantity"]
        price = prices.get(ticker)
        avg_price = position["avg_price"]
        cost = quantity * avg_price
        cost_basis += cost

        if price is None:
            holdings.append({
                "ticker": ticker, "quantity": quantity, "avg_price": avg_price,
                "price": None, "market_value": None, "cost": cost,
                "pnl": None, "pnl_pct": None, "day_pnl": None, "weight": None,
            })
            continue

        value = quantity * price
        market_value += value
        prev = previous.get(ticker, price)
        position_day_pnl = quantity * (price - prev)
        day_pnl += position_day_pnl
        holdings.append({
            "ticker": ticker,
            "quantity": quantity,
            "avg_price": avg_price,
            "price": price,
            "market_value": value,
            "cost": cost,
            "pnl": value - cost,
            "pnl_pct": ((value / cost - 1) * 100) if cost else None,
            "day_pnl": position_day_pnl,
            "weight": None,
        })

    equity = market_value + cash()
    for holding in holdings:
        if holding["market_value"] is not None and market_value:
            holding["weight"] = holding["market_value"] / market_value * 100

    pnl = market_value - cost_basis
    invested_yesterday = market_value - day_pnl
    return {
        "equity": equity,
        "cash": cash(),
        "market_value": market_value,
        "cost_basis": cost_basis,
        "pnl": pnl,
        "pnl_pct": (pnl / cost_basis * 100) if cost_basis else 0.0,
        "day_pnl": day_pnl,
        "day_pnl_pct": (day_pnl / invested_yesterday * 100) if invested_yesterday else 0.0,
        "total_return": equity - INITIAL_CASH,
        "total_return_pct": (equity / INITIAL_CASH - 1) * 100,
        "holdings": sorted(
            holdings, key=lambda h: h["market_value"] or 0.0, reverse=True
        ),
        "positions_count": len(holdings),
        "invested_pct": (market_value / equity * 100) if equity else 0.0,
    }


def rebalance_orders(
    allocations: Iterable[dict[str, Any]],
    budget: float,
    quotes: pd.DataFrame | None,
) -> list[dict[str, Any]]:
    """Turn optimiser target weights into a concrete order plan.

    Compares the target notional per ticker with the current holding and emits
    the BUY/SELL deltas. Returns proposals (not submitted orders) so the user
    reviews the plan before it is sent.
    """
    if quotes is None or quotes.empty:
        return []

    prices = quotes.set_index("ticker")["price"].to_dict()
    book = positions()
    plan: list[dict[str, Any]] = []

    for allocation in allocations:
        ticker = allocation["ticker"]
        weight = float(allocation.get("weight_percent", 0.0))
        price = prices.get(ticker)
        if not price:
            continue

        target_value = budget * weight / 100.0
        current_quantity = book.get(ticker, {}).get("quantity", 0.0)
        delta_quantity = target_value / price - current_quantity
        if abs(delta_quantity * price) < 1.0:      # ignore dust
            continue

        plan.append({
            "ticker": ticker,
            "side": "BUY" if delta_quantity > 0 else "SELL",
            "quantity": abs(round(delta_quantity, 4)),
            "price": price,
            "notional": abs(delta_quantity) * price,
            "target_weight": weight,
        })

    # Sell first so proceeds fund the buys.
    plan.sort(key=lambda item: (item["side"] != "SELL", -item["notional"]))
    return plan


# ---------------------------------------------------------------------------
#  Alerts
# ---------------------------------------------------------------------------

def alerts() -> list[dict[str, Any]]:
    return st.session_state["alerts"]


def add_alert(ticker: str, direction: Literal["above", "below"], threshold: float,
              note: str = "") -> dict[str, Any]:
    alert = {
        "id": _new_id(),
        "ticker": ticker,
        "direction": direction,
        "threshold": float(threshold),
        "note": note,
        "status": "ACTIVE",
        "created_at": datetime.now(),
        "triggered_at": None,
        "triggered_price": None,
    }
    st.session_state["alerts"].insert(0, alert)
    return alert


def remove_alert(alert_id: str) -> None:
    st.session_state["alerts"] = [a for a in alerts() if a["id"] != alert_id]


def reset_alert(alert_id: str) -> None:
    for alert in alerts():
        if alert["id"] == alert_id:
            alert.update(status="ACTIVE", triggered_at=None, triggered_price=None)


# ---------------------------------------------------------------------------
#  Notifications
# ---------------------------------------------------------------------------

def notifications() -> list[dict[str, Any]]:
    return st.session_state["notifications"]


def unread_count() -> int:
    return sum(1 for n in notifications() if not n["read"])


def notify(title: str, body: str = "", *, tone: str = "info", icon: str = "info") -> None:
    st.session_state["notifications"].insert(0, {
        "id": _new_id(),
        "timestamp": datetime.now(),
        "title": title,
        "body": body,
        "tone": tone,
        "icon": icon,
        "read": False,
    })
    del st.session_state["notifications"][40:]


def mark_all_read() -> None:
    for item in notifications():
        item["read"] = True


# ---------------------------------------------------------------------------
#  Settlement
# ---------------------------------------------------------------------------

def settle(quotes: pd.DataFrame | None) -> None:
    """Advance the simulation against the latest prices.

    Fills crossed limit orders and triggers price alerts. Called once per run
    from the app shell, so every page sees a consistent account state.
    """
    if quotes is None or quotes.empty:
        return

    prices = quotes.set_index("ticker")["price"].to_dict()

    for order in list(open_orders()):
        price = prices.get(order["ticker"])
        limit = order["limit_price"]
        if price is None or limit is None:
            continue
        if order["side"] == "BUY" and price <= limit:
            if order["quantity"] * price <= cash() + 1e-6:
                _fill(order, min(limit, price))
            else:
                order.update(status="REJECTED", reject_reason="Liquidités insuffisantes")
        elif order["side"] == "SELL" and price >= limit:
            held = positions().get(order["ticker"], {}).get("quantity", 0.0)
            if order["quantity"] <= held + 1e-9:
                _fill(order, max(limit, price))
            else:
                order.update(status="REJECTED", reject_reason="Position insuffisante")

    for alert in alerts():
        if alert["status"] != "ACTIVE":
            continue
        price = prices.get(alert["ticker"])
        if price is None:
            continue
        crossed = (
            price >= alert["threshold"] if alert["direction"] == "above"
            else price <= alert["threshold"]
        )
        if crossed:
            alert.update(status="TRIGGERED", triggered_at=datetime.now(),
                         triggered_price=price)
            arrow = "au-dessus de" if alert["direction"] == "above" else "sous"
            notify(
                f"Alerte {alert['ticker']} déclenchée",
                f"Cours {price:,.2f} $ {arrow} {alert['threshold']:,.2f} $",
                tone="warn",
                icon="alerts",
            )


# ---------------------------------------------------------------------------
#  Optimisation result
# ---------------------------------------------------------------------------

def set_optimization(result: dict[str, Any], meta: dict[str, Any]) -> None:
    st.session_state["optimization"] = {
        "result": result,
        "meta": {**meta, "ran_at": datetime.now()},
    }


def optimization() -> dict[str, Any] | None:
    return st.session_state.get("optimization")


def clear_optimization() -> None:
    st.session_state["optimization"] = None


# ---------------------------------------------------------------------------
#  Maintenance
# ---------------------------------------------------------------------------

def reset_account() -> None:
    """Reset the simulated account, keeping preferences and watchlist."""
    st.session_state["positions"] = {}
    st.session_state["cash"] = INITIAL_CASH
    st.session_state["orders"] = []
    st.session_state["transactions"] = []
    st.session_state["alerts"] = []
    st.session_state["notifications"] = []
    st.session_state["optimization"] = None
    init()
    notify("Compte simulé réinitialisé", f"Liquidités remises à {INITIAL_CASH:,.0f} $",
           tone="info", icon="refresh")


def sign_out() -> None:
    st.session_state["signed_in"] = False


def sign_in() -> None:
    st.session_state["signed_in"] = True
