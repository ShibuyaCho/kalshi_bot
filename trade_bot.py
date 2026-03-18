"""
trade_bot.py
- Fetches ALL markets, filters out KXMV parlays + stub prices + games >24h away
- One trade per market per day (daily_trades.json)
- Max 3 open positions
- Dip strategy: buy when Kalshi < Vegas odds by DIP_THRESHOLD_CENTS
- Exit: sell on any profit, hold losers to game resolution
"""
import time
import json
import os
import config
import feed
import dip_strategy
import odds_client
import positions
from kalshi_client import KalshiClient
from datetime import datetime, timezone, timedelta

client = KalshiClient()

liquid_markets:     list  = []
last_market_refresh:float = 0
MARKET_REFRESH_INTERVAL   = 60 * 30

consensus_probs:    dict  = {}
last_odds_refresh:  float = 0
last_dip_scan:      float = 0

DAILY_TRADES_FILE  = os.path.join(os.path.dirname(__file__), "daily_trades.json")
MAX_OPEN_POSITIONS = 3

# ── Daily trade log ────────────────────────────────────────────────────────────
def _load_daily_trades() -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        if os.path.exists(DAILY_TRADES_FILE):
            data = json.load(open(DAILY_TRADES_FILE))
            if data.get("date") == today:
                return data.get("trades", {})
    except Exception:
        pass
    return {}

def _save_daily_trades(trades: dict):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json.dump({"date": today, "trades": trades}, open(DAILY_TRADES_FILE, "w"))

def already_traded_today(ticker: str) -> bool:
    return ticker in _load_daily_trades()

def mark_traded_today(ticker: str):
    trades = _load_daily_trades()
    trades[ticker] = datetime.now(timezone.utc).isoformat()
    _save_daily_trades(trades)
    print(f"  [daily] {ticker} marked — skip for rest of day.")

# ── Sizing ─────────────────────────────────────────────────────────────────────
def get_order_size(price_dollars: float) -> int:
    balance, _ = client.get_balance()
    if balance < config.MIN_BALANCE_DOLLARS:
        print(f"  Balance ${balance:.2f} below minimum, skipping.")
        return 0
    max_dollars = min(balance * config.MAX_POSITION_PCT, config.MAX_ORDER_DOLLARS)
    if max_dollars < config.MIN_ORDER_DOLLARS:
        print(f"  Balance too low for min order.")
        return 0
    contracts = max(1, int(max_dollars / price_dollars))
    print(f"  Balance: ${balance:.2f} | {contracts} contracts @ ${price_dollars:.2f}")
    return contracts

# ── Market discovery ───────────────────────────────────────────────────────────
def discover_active_markets() -> list:
    print("Fetching active markets...")
    raw    = client.get_markets()
    now    = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=24)
    tickers = []
    for m in raw:
        ticker = m.get("ticker", "")
        if not ticker or m.get("status") != "active":
            continue
        # Skip KXMV multi-leg parlays
        if ticker.startswith("KXMV"):
            continue
        # Skip games more than 24 hours away
        open_time = m.get("open_time") or m.get("close_time")
        if open_time:
            try:
                ot = datetime.fromisoformat(open_time.replace("Z", "+00:00"))
                if ot > cutoff:
                    continue
            except Exception:
                pass
        # Skip stub/unopened markets
        yes_bid = float(m.get("yes_bid_dollars") or 0)
        no_bid  = float(m.get("no_bid_dollars")  or 0)
        if yes_bid <= 0.01 and no_bid <= 0.01:
            continue
        # Skip markets that opened more than 4 hours ago (game likely in progress or done)
        open_time_str = m.get("open_time")
        if open_time_str:
            try:
                ot = datetime.fromisoformat(open_time_str.replace("Z", "+00:00"))
                if ot < now - timedelta(hours=4):
                    continue
            except Exception:
                pass
        tickers.append(ticker)
    print(f"Active markets with real liquidity: {len(tickers)}")
    return tickers

def refresh_markets_if_needed(ws):
    global liquid_markets, last_market_refresh
    if time.time() - last_market_refresh < MARKET_REFRESH_INTERVAL:
        return
    print("Refreshing market list...")
    new_tickers = discover_active_markets()
    added   = set(new_tickers) - set(liquid_markets)
    removed = set(liquid_markets) - set(new_tickers)
    if added:
        feed.subscribe(ws, list(added))
        print(f"  +{len(added)} new markets subscribed.")
    if removed:
        print(f"  -{len(removed)} markets removed.")
    liquid_markets      = new_tickers
    last_market_refresh = time.time()

# ── Odds refresh ───────────────────────────────────────────────────────────────
def refresh_odds_if_needed():
    global consensus_probs, last_odds_refresh
    if time.time() - last_odds_refresh < config.ODDS_SCAN_INTERVAL:
        return
    if config.ODDS_API_KEY == "YOUR_ODDS_API_KEY_HERE":
        return
    print("Refreshing external odds...")
    try:
        consensus_probs = odds_client.get_all_consensus_probs()
        print(f"  {len(consensus_probs)} matchups loaded.")
    except Exception as e:
        print(f"  Odds refresh failed: {e}")
    last_odds_refresh = time.time()

# ── Snapshot ───────────────────────────────────────────────────────────────────
def get_snapshot(ticker: str):
    book = feed.get_live_book(ticker)
    if not book:
        return None
    yes = book.get("yes")
    no  = book.get("no")
    try:
        yes_price = float(yes[0][0]) if yes else None
        yes_size  = float(yes[0][1]) if yes else 0
        no_price  = float(no[0][0])  if no  else None
        no_size   = float(no[0][1])  if no  else 0
    except (IndexError, TypeError, ValueError):
        return None
    if yes_price is None and no_price is not None:
        yes_price = 1.0 - no_price
    if no_price is None and yes_price is not None:
        no_price = 1.0 - yes_price
    if yes_price is None or no_price is None:
        return None
    return {
        "ticker": ticker, "yes_price": yes_price, "no_price": no_price,
        "yes_size": yes_size, "no_size": no_size, "liquidity": yes_size + no_size,
    }

# ── Execution ──────────────────────────────────────────────────────────────────
def execute_dip(opp: dict):
    ticker = opp["ticker"]
    if already_traded_today(ticker):
        return
    open_pos = positions.get_open_positions()
    if len(open_pos) >= MAX_OPEN_POSITIONS:
        print(f"  Max positions open — skipping {ticker}")
        return
    if ticker in open_pos:
        return
    side          = opp["side"]
    price_dollars = opp["yes_price_dollars"] if side == "yes" else opp["no_price_dollars"]
    price_cents   = round(price_dollars * 100)
    count = get_order_size(price_dollars)
    if count == 0:
        return
    print(f"  {opp['action']} {ticker} @ {price_cents}c x{count} ({opp['matchup']})")
    result = client.place_order(ticker, side, price_cents, count)
    print(f"  Result: {result}")
    if result:
        positions.open_position(
            ticker=ticker, side=side, entry_cents=price_cents,
            count=count, commence_time=opp.get("commence_time"),
            fair_value_cents=opp["fair_value_cents"],
        )
        mark_traded_today(ticker)

def check_position_exits():
    open_pos = positions.get_open_positions()
    if not open_pos:
        return
    for ticker, pos in list(open_pos.items()):
        snapshot = get_snapshot(ticker)
        if not snapshot:
            continue
        side          = pos["side"]
        current_cents = (snapshot["yes_price"] if side == "yes" else snapshot["no_price"]) * 100
        exit_now, reason = positions.should_exit(ticker, current_cents)
        if not exit_now:
            continue
        print(f"EXIT [{datetime.now().strftime('%H:%M:%S')}] {reason}")
        if config.TRADING_ENABLED:
            sell_side    = "no" if side == "yes" else "yes"
            sell_dollars = snapshot["no_price"] if sell_side == "no" else snapshot["yes_price"]
            sell_cents   = round(sell_dollars * 100)
            print(f"  Selling {sell_side.upper()} @ {sell_cents}c x{pos['count']}")
            result = client.place_order(ticker, sell_side, sell_cents, pos["count"])
            print(f"  Result: {result}")
        positions.close_position(ticker)

# ── Main scan loop ─────────────────────────────────────────────────────────────
def scan_and_trade(ws):
    global last_dip_scan
    refresh_markets_if_needed(ws)
    refresh_odds_if_needed()
    check_position_exits()
    run_dip = (time.time() - last_dip_scan) >= config.DIP_SCAN_INTERVAL
    dip_hits = 0
    for ticker in liquid_markets:
        snapshot = get_snapshot(ticker)
        if not snapshot:
            continue
        if run_dip:
            opp = dip_strategy.evaluate_dip(ticker, snapshot, consensus_probs)
            if opp:
                dip_hits += 1
                print(f"OPPORTUNITY [{datetime.now().strftime('%H:%M:%S')}] {opp['reason']}")
                if config.TRADING_ENABLED:
                    execute_dip(opp)
    if run_dip:
        last_dip_scan = time.time()
    open_count = len(positions.get_open_positions())
    print(f"--- Scan: {len(liquid_markets)} markets | {dip_hits} dip opps | {open_count}/{MAX_OPEN_POSITIONS} positions ---")

# ── Entry point ────────────────────────────────────────────────────────────────
def run():
    global liquid_markets, last_market_refresh
    balance, portfolio = client.get_balance()
    print(f"Balance: ${balance:.2f} | Portfolio: ${portfolio:.2f}")
    if not config.TRADING_ENABLED:
        print("*** DRY RUN — no orders placed ***")
    if config.ODDS_API_KEY == "YOUR_ODDS_API_KEY_HERE":
        print("NOTE: Set ODDS_API_KEY in config.py to enable dip strategy.")
    while True:
        try:
            liquid_markets      = discover_active_markets()
            last_market_refresh = time.time()
            if not liquid_markets:
                print("No markets found, retrying in 60s...")
                time.sleep(60)
                continue
            print(f"Subscribing to {len(liquid_markets)} markets...")
            ws = feed.start(tickers=liquid_markets, daemon=True)
            time.sleep(5)
            for _ in range(30):
                populated = sum(1 for t in liquid_markets if feed.get_live_book(t))
                print(f"  {populated}/{len(liquid_markets)} books received...")
                if populated >= len(liquid_markets) * 0.5:
                    break
                time.sleep(2)
            print("Starting scan loop.")
            while True:
                scan_and_trade(ws)
                time.sleep(config.SCAN_INTERVAL)
        except KeyboardInterrupt:
            print("Stopped.")
            break
        except Exception as e:
            print(f"ERROR: {e} — restarting in 30s...")
            time.sleep(30)

if __name__ == "__main__":
    run()
