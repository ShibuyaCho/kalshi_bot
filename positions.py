"""
positions.py
Tracks open dip-buy positions and triggers sells before the event starts.

Position lifecycle:
  1. Bot detects a dip and calls open_position()
  2. Each scan cycle calls check_exits() which sells any position where:
       - The price has recovered to target (profit taking), OR
       - The event starts within SELL_BEFORE_MINUTES (time-based exit)
  3. close_position() is called to execute the sell order
"""

import time
import json
import os
from datetime import datetime, timezone

POSITIONS_FILE = os.path.join(os.path.dirname(__file__), "open_positions.json")

# Sell this many minutes before event start time
SELL_BEFORE_MINUTES = 10

# Minimum profit in cents before we take profit early
PROFIT_TARGET_CENTS = 4.0

# Cut losses if price drops this many cents below entry
STOP_LOSS_CENTS = 8.0


def _load() -> dict:
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(positions: dict):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)


def open_position(ticker: str, side: str, entry_cents: float,
                  count: int, commence_time: str | None, fair_value_cents: float):
    """
    Record a new open position.

    ticker:           Kalshi market ticker
    side:             'yes' or 'no'
    entry_cents:      price paid in cents (0-100)
    count:            number of contracts
    commence_time:    ISO8601 string of event start (from odds API), or None
    fair_value_cents: our estimated fair value at time of entry
    """
    positions = _load()
    positions[ticker] = {
        "side":             side,
        "entry_cents":      entry_cents,
        "count":            count,
        "commence_time":    commence_time,
        "fair_value_cents": fair_value_cents,
        "opened_at":        time.time(),
    }
    _save(positions)
    print(f"[positions] Opened: {ticker} {side.upper()} @ {entry_cents}c x{count} "
          f"(fair={fair_value_cents:.1f}c, event={commence_time})")


def get_open_positions() -> dict:
    return _load()


def close_position(ticker: str):
    """Remove a position from the tracker (call after sell order placed)."""
    positions = _load()
    if ticker in positions:
        del positions[ticker]
        _save(positions)
        print(f"[positions] Closed: {ticker}")


def should_exit(ticker: str, current_cents: float) -> tuple[bool, str]:
    """
    Returns (True, reason) if we should sell this position now, else (False, '').

    Checks:
      1. Profit target reached
      2. Stop loss hit
      3. Event starting within SELL_BEFORE_MINUTES
    """
    positions = _load()
    pos = positions.get(ticker)
    if not pos:
        return False, ""

    entry   = pos["entry_cents"]
    side    = pos["side"]

    # For YES positions, profit = current - entry. For NO, it's inverted.
    if side == "yes":
        pnl = current_cents - entry
    else:
        pnl = (100 - current_cents) - entry

    # 1. Profit target
    if pnl >= PROFIT_TARGET_CENTS:
        return True, f"Profit target hit: {pnl:+.1f}c on {ticker}"

    # 2. Stop loss
    if pnl <= -STOP_LOSS_CENTS:
        return True, f"Stop loss hit: {pnl:+.1f}c on {ticker}"

    # 3. Time-based exit
    commence = pos.get("commence_time")
    if commence:
        try:
            event_time = datetime.fromisoformat(commence.replace("Z", "+00:00"))
            now        = datetime.now(timezone.utc)
            mins_to_event = (event_time - now).total_seconds() / 60
            if mins_to_event <= SELL_BEFORE_MINUTES:
                return True, f"Event in {mins_to_event:.1f}m — exiting {ticker}"
        except Exception:
            pass

    return False, ""
