import time
import config
import feed
from kalshi_client import KalshiClient
from datetime import datetime

client = KalshiClient()
liquid_markets = []
last_market_refresh = 0
MARKET_REFRESH_INTERVAL = 60 * 30


def get_order_size(price_dollars: float) -> int:
    balance, _ = client.get_balance()
    if balance <= 0:
        print("  No balance available, skipping.")
        return 0

    max_dollars = min(
        balance * config.MAX_POSITION_PCT,
        config.MAX_ORDER_DOLLARS
    )

    if max_dollars < config.MIN_ORDER_DOLLARS:
        print(f"  Balance too low for minimum order (${balance:.2f} available).")
        return 0

    contracts = int(max_dollars / price_dollars)
    contracts = max(1, contracts)

    print(f"  Balance: ${balance:.2f} | Sizing {contracts} contracts at ${price_dollars:.2f} each")
    return contracts


def discover_active_markets():
    print("Fetching active markets...")
    raw = client.get_markets()

    tickers = []
    for m in raw:
        ticker = m.get("ticker")
        status = m.get("status")
        if not ticker or status != "active":
            continue

        yes_bid = float(m.get("yes_bid_dollars") or 0)
        no_bid = float(m.get("no_bid_dollars") or 0)
        yes_ask = float(m.get("yes_ask_dollars") or 0)
        no_ask = float(m.get("no_ask_dollars") or 0)

        has_yes_market = yes_bid > 0 and yes_ask > 0
        has_no_market = no_bid > 0 and no_ask > 0

        if has_yes_market or has_no_market:
            tickers.append(ticker)

    print(f"LIQUID ACTIVE MARKETS: {len(tickers)}")
    return tickers


def refresh_markets_if_needed(ws):
    global liquid_markets, last_market_refresh
    now = time.time()
    if now - last_market_refresh < MARKET_REFRESH_INTERVAL:
        return
    print("Refreshing market list...")
    new_tickers = discover_active_markets()
    current_set = set(liquid_markets)
    new_set = set(new_tickers)
    added = new_set - current_set
    removed = current_set - new_set
    if added:
        print(f"  {len(added)} new markets found, subscribing...")
        feed.subscribe(ws, list(added))
    if removed:
        print(f"  {len(removed)} markets removed.")
    liquid_markets = new_tickers
    last_market_refresh = now


def get_snapshot(ticker):
    book = feed.get_live_book(ticker)
    if not book:
        return None

    yes = book.get("yes")
    no = book.get("no")

    if not yes and not no:
        return None

    try:
        yes_price = float(yes[0][0]) if yes else None
        yes_size = float(yes[0][1]) if yes else 0
        no_price = float(no[0][0]) if no else None
        no_size = float(no[0][1]) if no else 0
    except (IndexError, TypeError, ValueError):
        return None

    # Derive missing side from the other
    if yes_price is None and no_price is not None:
        yes_price = 1.0 - no_price
    if no_price is None and yes_price is not None:
        no_price = 1.0 - yes_price

    if yes_price is None or no_price is None:
        return None

    return {
        "ticker": ticker,
        "yes_price": yes_price,
        "no_price": no_price,
        "yes_size": yes_size,
        "no_size": no_size,
        "liquidity": yes_size + no_size
    }


def evaluate_opportunity(snapshot):
    if not snapshot:
        return None

    yes_cents = snapshot["yes_price"] * 100
    no_cents = snapshot["no_price"] * 100
    implied_sum = yes_cents + no_cents

    if yes_cents < 2 or yes_cents > 98:
        return None
    if no_cents < 2 or no_cents > 98:
        return None
    if snapshot["liquidity"] < config.LIQUIDITY_THRESHOLD:
        return None

    if implied_sum < 100 - config.EDGE_THRESHOLD:
        return {
            "ticker": snapshot["ticker"],
            "type": "gap",
            "yes_price": round(yes_cents),
            "no_price": round(no_cents),
            "yes_price_dollars": snapshot["yes_price"],
            "no_price_dollars": snapshot["no_price"],
            "implied_sum": round(implied_sum, 1),
            "profit_per_contract": round(100 - implied_sum, 1),
            "reason": f"Gap: {implied_sum:.1f} < 100, profit {100 - implied_sum:.1f}c/contract"
        }

    if implied_sum > 100 + config.EDGE_THRESHOLD:
        return {
            "ticker": snapshot["ticker"],
            "type": "overhang",
            "yes_price": round(yes_cents),
            "no_price": round(no_cents),
            "yes_price_dollars": snapshot["yes_price"],
            "no_price_dollars": snapshot["no_price"],
            "implied_sum": round(implied_sum, 1),
            "profit_per_contract": round(implied_sum - 100, 1),
            "reason": f"Overhang: {implied_sum:.1f} > 100, profit {implied_sum - 100:.1f}c/contract"
        }

    return None


def execute_opportunity(opp):
    ticker = opp["ticker"]

    if opp["type"] == "gap":
        count = get_order_size(max(opp["yes_price_dollars"], opp["no_price_dollars"]))
        if count == 0:
            return
        print(f"  Buying YES at {opp['yes_price']}c and NO at {opp['no_price']}c x{count}")
        yes_result = client.place_order(ticker, "yes", opp["yes_price"], count)
        no_result = client.place_order(ticker, "no", opp["no_price"], count)
        print(f"  YES order: {yes_result}")
        print(f"  NO order:  {no_result}")

    elif opp["type"] == "overhang":
        count = get_order_size(max(opp["yes_price_dollars"], opp["no_price_dollars"]))
        if count == 0:
            return
        sell_yes_as_no = 100 - opp["yes_price"]
        sell_no_as_yes = 100 - opp["no_price"]
        print(f"  Selling YES/NO: buy NO at {sell_yes_as_no}c, buy YES at {sell_no_as_yes}c x{count}")
        yes_result = client.place_order(ticker, "no", sell_yes_as_no, count)
        no_result = client.place_order(ticker, "yes", sell_no_as_yes, count)
        print(f"  Sell YES order: {yes_result}")
        print(f"  Sell NO order:  {no_result}")


def scan_and_trade(ws):
    refresh_markets_if_needed(ws)
    hits = 0
    opps = 0
    for ticker in liquid_markets:
        snapshot = get_snapshot(ticker)
        if not snapshot:
            continue
        hits += 1
        opp = evaluate_opportunity(snapshot)
        if not opp:
            continue
        opps += 1
        print(f"OPPORTUNITY at {datetime.now().strftime('%H:%M:%S')}: {opp['reason']} on {opp['ticker']}")
        if config.TRADING_ENABLED:
            execute_opportunity(opp)

    print(f"--- Scan complete: {hits} snapshots, {opps} opportunities ---")


def run():
    global liquid_markets, last_market_refresh

    balance, portfolio = client.get_balance()
    print(f"Account balance: ${balance:.2f} | Portfolio value: ${portfolio:.2f}")

    while True:
        try:
            liquid_markets = discover_active_markets()
            last_market_refresh = time.time()

            if not liquid_markets:
                print("No liquid markets found, retrying in 60s...")
                time.sleep(60)
                continue

            print(f"Subscribing to {len(liquid_markets)} markets via WebSocket...")
            ws = feed.start(tickers=liquid_markets, daemon=True)

            time.sleep(5)

            print("Waiting for WebSocket snapshots...")
            for i in range(30):
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
            print("Stopped by user.")
            break
        except Exception as e:
            print(f"ERROR: {e} — restarting in 30s...")
            time.sleep(30)


if __name__ == "__main__":
    run()