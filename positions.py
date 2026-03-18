"""
Exit logic:
  1. Sell immediately on any profit >= 1 cent
  2. Hold to game resolution if underwater
  3. Pre-game exit only if profitable
  4. Hard stop loss at -8 cents
"""
import time
import json
import os
from datetime import datetime, timezone

POSITIONS_FILE    = os.path.join(os.path.dirname(__file__), "open_positions.json")
SELL_BEFORE_MINS  = 10
STOP_LOSS_CENTS   = 8.0
MIN_PROFIT_CENTS  = 1.0

def _load() -> dict:
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save(p: dict):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(p, f, indent=2)

def open_position(ticker, side, entry_cents, count, commence_time, fair_value_cents):
    p = _load()
    p[ticker] = {
        "side": side, "entry_cents": entry_cents, "count": count,
        "commence_time": commence_time, "fair_value_cents": fair_value_cents,
        "opened_at": time.time(),
    }
    _save(p)
    print(f"[positions] Opened {ticker} {side.upper()} @ {entry_cents}c x{count}")

def get_open_positions() -> dict:
    return _load()

def close_position(ticker: str):
    p = _load()
    if ticker in p:
        del p[ticker]
        _save(p)
        print(f"[positions] Closed {ticker}")

def should_exit(ticker: str, current_cents: float):
    p   = _load()
    pos = p.get(ticker)
    if not pos:
        return False, ""
    pnl = current_cents - pos["entry_cents"]
    # 1. Take any profit
    if pnl >= MIN_PROFIT_CENTS:
        return True, f"Profit +{pnl:.1f}c on {ticker}"
    # 2. Pre-game exit only if profitable (already caught above)
    commence = pos.get("commence_time")
    if commence:
        try:
            event_time    = datetime.fromisoformat(commence.replace("Z", "+00:00"))
            now           = datetime.now(timezone.utc)
            mins_to_event = (event_time - now).total_seconds() / 60
            if mins_to_event <= SELL_BEFORE_MINS and pnl >= 0:
                return True, f"Game in {mins_to_event:.1f}m, profitable — exiting {ticker}"
        except Exception:
            pass
    # 3. Hard stop loss
    if pnl <= -STOP_LOSS_CENTS:
        return True, f"Stop loss {pnl:.1f}c on {ticker}"
    # 4. Underwater — hold to resolution
    return False, ""
