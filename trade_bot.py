"""
trade_bot.py
Main trading loop. Runs two strategies in parallel:

  1. Arb strategy   — scans ALL liquid Kalshi markets for order-book
                      mispricing (YES + NO ≠ 100). Pure Kalshi data.

  2. Odds strategy  — scans sports markets (NBA/NFL/MLB/NHL) and compares
                      Kalshi YES prices against consensus sportsbook odds.
                      Trades when Kalshi is mispriced vs external fair value.
"""

import time
import config
import feed
import strategy
import odds_client
from kalshi_client import KalshiClient
from datetime import datetime

client = KalshiClient()

# ── State ──────────────────────────────────────────────────────────────────────
liquid_markets: list = []
last_market_refresh: float = 0
MARKET_REFRESH_INTERVAL = 60 * 30  # refresh market list every 30 min

consensus_probs: dict = {}
last_odds_refresh: float = 0

# Per-ticker cooldown: track last trade time to avoid hammering the same market
last_traded: dict = {}
TRADE_COOLDOWN = 120  # seconds before we trade the same ticker again


# ── Sizing ─────────────────────────────────────────────────────────────────────

def get_order_size(price_dollars: float) -> int:
    balance, _ = client.get_balance()
    if balance <= 0:
        print("  No balance available, skipping.")
        return 0

    max_dollars = min(
        balance * config.MAX_POSITION_PCT,
        config.MAX_ORDER_DOLLARS,
    )

    if max_dollars < config.MIN_ORDER_DOLLARS:
        print(f"  Balance too low for minimum order (${balance:.2f} available).")
        return 0

    contracts = max(1, int(max_dollars / price_dollars))
    print(f"  Balance: ${balance:.2f} | Sizing {contracts} contracts at ${price_dollars:.2f} each")
    return contracts


# ── Market discovery ───────────────────────────────────────────────────────────

def discover_active_markets() -> list:
    print("Fetching active markets...")
    raw = client.get_markets()
    tickers = []
    for m in raw:
        ticker = m.get("ticker")
        if not ticker or m.get("status") != "active":
            continue
        yes_bid  = float(m.get("yes_bid_dollars") or 0)
        no_bid   = float(m.get("no_bid_dollars") or 0)
        yes_ask  = float(m.get("yes_ask_dollars") or 0)
        no_ask   = float(m.get("no_ask_dollars") or 0)
        if (yes_bid > 0 and yes_ask > 0) or (no_bid > 0 and no_ask > 0):
            tickers.append(ticker)
    print(f"Liquid active markets: {len(tickers)}")
    return tickers


def refresh_markets_if_needed(ws):
    global liquid_markets, last_market_refresh
    now = time.time()
    if now - last_market_refresh < MARKET_REFRESH_INTERVAL:
        return

    print("Refreshing market list...")
    new_tickers = discover_active_markets()
    current_set = set(liquid_markets)
    new_set     = set(new_tickers)

    added   = new_set - current_set
    removed = current_set - new_set

    if added:
        print(f"  {len(added)} new markets, subscribing...")
        feed.subscribe(ws, list(added))
    if removed:
        print(f"  {len(removed)} markets removed.")

    liquid_markets     = new_tickers
    last_market_refresh = now


# ── Odds refresh ───────────────────────────────────────────────────────────────

def refresh_odds_if_needed():
    global consensus_probs, last_odds_refresh
    now = time.time()
    if now - last_odds_refresh < config.ODDS_SCAN_INTERVAL:
        return
    if config.ODDS_API_KEY == "YOUR_ODDS_API_KEY_HERE":
        return  # not configured, skip silently
    print("Refreshing external odds...")
    try:
        consensus_probs = odds_client.get_all_consensus_probs()
        print(f"  {len(consensus_probs)} matchups loaded from sportsbooks.")
    except Exception as e:
        print(f"  Odds refresh failed: {e}")
    last_odds_refresh = now


# ── Snapshot helpers ───────────────────────────────────────────────────────────

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
        "ticker":    ticker,
        "yes_price": yes_price,
        "no_price":  no_price,
        "yes_size":  yes_size,
        "no_size":   no_size,
        "liquidity": yes_size + no_size,
    }


# ── Arb evaluation (order-book gap / overhang) ─────────────────────────────────

def evaluate_arb(snapshot) -> dict | None:
    if not snapshot:
        return None

    yes_cents = snapshot["yes_price"] * 100
    no_cents  = snapshot["no_price"]  * 100
    implied   = yes_cents + no_cents

    if yes_cents < 2 or yes_cents > 98:
        return None
    if no_cents  < 2 or no_cents  > 98:
        return None
    if snapshot["liquidity"] < config.LIQUIDITY_THRESHOLD:
        return None

    if implied < 100 - config.EDGE_THRESHOLD:
        return {
            "ticker":           snapshot["ticker"],
            "type":             "gap",
            "yes_price":        round(yes_cents),
            "no_price":         round(no_cents),
            "yes_price_dollars": snapshot["yes_price"],
            "no_price_dollars":  snapshot["no_price"],
            "implied_sum":      round(implied, 1),
            "profit_per_contract": round(100 - implied, 1),
            "reason": f"[ARB-GAP] YES+NO={implied:.1f} < 100, profit {100-implied:.1f}c/contract",
            "source": "arb",
        }

    if implied > 100 + config.EDGE_THRESHOLD:
        return {
            "ticker":           snapshot["ticker"],
            "type":             "overhang",
            "yes_price":        round(yes_cents),
            "no_price":         round(no_cents),
            "yes_price_dollars": snapshot["yes_price"],
            "no_price_dollars":  snapshot["no_price"],
            "implied_sum":      round(implied, 1),
            "profit_per_contract": round(implied - 100, 1),
            "reason": f"[ARB-OVH] YES+NO={implied:.1f} > 100, profit {implied-100:.1f}c/contract",
            "source": "arb",
        }

    return None


# ── Odds evaluation ────────────────────────────────────────────────────────────

def evaluate_odds(snapshot) -> dict | None:
    if not snapshot or not consensus_probs:
        return None
    if snapshot["liquidity"] < config.LIQUIDITY_THRESHOLD:
        return None

    yes_cents = snapshot["yes_price"] * 100
    sig = strategy.odds_signal(snapshot["ticker"], yes_cents, consensus_probs)
    if not sig:
        return None

    # Attach pricing info needed by execute
    sig["yes_price_dollars"] = snapshot["yes_price"]
    sig["no_price_dollars"]  = snapshot["no_price"]
    sig["source"] = "odds"
    return sig


# ── Execution ──────────────────────────────────────────────────────────────────

def _cooldown_ok(ticker: str) -> bool:
    last = last_traded.get(ticker, 0)
    return (time.time() - last) >= TRADE_COOLDOWN


def execute_arb(opp: dict):
    ticker = opp["ticker"]
    if not _cooldown_ok(ticker):
        print(f"  Skipping {ticker} — in cooldown.")
        return

    if opp["type"] == "gap":
        count = get_order_size(max(opp["yes_price_dollars"], opp["no_price_dollars"]))
        if count == 0:
            return
        print(f"  Buying YES@{opp['yes_price']}c + NO@{opp['no_price']}c x{count}")
        yes_r = client.place_order(ticker, "yes", opp["yes_price"], count)
        no_r  = client.place_order(ticker, "no",  opp["no_price"],  count)
        print(f"  YES: {yes_r}")
        print(f"  NO:  {no_r}")

    elif opp["type"] == "overhang":
        count = get_order_size(max(opp["yes_price_dollars"], opp["no_price_dollars"]))
        if count == 0:
            return
        # Sell YES by buying NO at implied complement, and vice versa
        sell_yes_as_no = 100 - opp["yes_price"]
        sell_no_as_yes = 100 - opp["no_price"]
        print(f"  Selling: buy NO@{sell_yes_as_no}c + buy YES@{sell_no_as_yes}c x{count}")
        r1 = client.place_order(ticker, "no",  sell_yes_as_no, count)
        r2 = client.place_order(ticker, "yes", sell_no_as_yes, count)
        print(f"  r1: {r1}")
        print(f"  r2: {r2}")

    last_traded[ticker] = time.time()


def execute_odds(opp: dict):
    ticker = opp["ticker"]
    if not _cooldown_ok(ticker):
        print(f"  Skipping {ticker} — in cooldown.")
        return

    action = opp["action"]  # "BUY_YES" or "BUY_NO"
    side   = "yes" if action == "BUY_YES" else "no"
    price_dollars = opp["yes_price_dollars"] if side == "yes" else opp["no_price_dollars"]
    price_cents   = round(price_dollars * 100)

    count = get_order_size(price_dollars)
    if count == 0:
        return

    print(f"  {action} {ticker} @ {price_cents}c x{count}  ({opp['matchup']})")
    result = client.place_order(ticker, side, price_cents, count)
    print(f"  Result: {result}")
    last_traded[ticker] = time.time()


# ── Main scan loop ─────────────────────────────────────────────────────────────

def scan_and_trade(ws):
    refresh_markets_if_needed(ws)
    refresh_odds_if_needed()

    arb_hits = odds_hits = 0

    for ticker in liquid_markets:
        snapshot = get_snapshot(ticker)
        if not snapshot:
            continue

        # 1. Arb strategy (always runs)
        arb_opp = evaluate_arb(snapshot)
        if arb_opp:
            arb_hits += 1
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"OPPORTUNITY [{ts}] {arb_opp['reason']} on {ticker}")
            if config.TRADING_ENABLED:
                execute_arb(arb_opp)

        # 2. Odds strategy (runs when odds API is configured)
        odds_opp = evaluate_odds(snapshot)
        if odds_opp:
            odds_hits += 1
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"OPPORTUNITY [{ts}] {odds_opp['reason']} on {ticker}")
            if config.TRADING_ENABLED:
                execute_odds(odds_opp)

    print(
        f"--- Scan done: {len(liquid_markets)} markets | "
        f"{arb_hits} arb opps | {odds_hits} odds opps ---"
    )


# ── Entry point ────────────────────────────────────────────────────────────────

def run():
    global liquid_markets, last_market_refresh

    balance, portfolio = client.get_balance()
    print(f"Account balance: ${balance:.2f} | Portfolio value: ${portfolio:.2f}")

    if not config.TRADING_ENABLED:
        print("*** DRY RUN MODE — no orders will be placed ***")

    if config.ODDS_API_KEY == "YOUR_ODDS_API_KEY_HERE":
        print("NOTE: ODDS_API_KEY not set in config.py — odds strategy disabled.")

    while True:
        try:
            liquid_markets      = discover_active_markets()
            last_market_refresh = time.time()

            if not liquid_markets:
                print("No liquid markets found, retrying in 60s...")
                time.sleep(60)
                continue

            print(f"Subscribing to {len(liquid_markets)} markets via WebSocket...")
            ws = feed.start(tickers=liquid_markets, daemon=True)
            time.sleep(5)

            print("Waiting for WebSocket snapshots...")
            for _ in range(30):
                populated = sum(1 for t in liquid_markets if feed.get_live_book(t))
                print(f"  {populated}/{len(liquid_markets)} order books received...")
                if populated >= len(liquid_markets) * 0.5:
                    break
                time.sleep(2)

            print("Starting scan loop.")
            while True:
                scan_and_trade(ws)
                time.sleep(config.SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("Stopped by user.")
            break
        except Exception as e:
            print(f"ERROR: {e} — restarting in 30s...")
            time.sleep(30)


if __name__ == "__main__":
    run()
