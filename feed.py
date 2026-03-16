import websocket
import json
import threading
import datetime
from kalshi_client import KalshiClient, sign_pss

client = KalshiClient()

WS_HOST = "api.elections.kalshi.com"
WS_PATH = "/trade-api/ws/v2"
WS_URL = f"wss://{WS_HOST}{WS_PATH}"

live_books = {}
_lock = threading.Lock()


def get_live_book(ticker):
    with _lock:
        return live_books.get(ticker)


def build_headers():
    ts = str(int(datetime.datetime.now().timestamp() * 1000))
    sig = sign_pss(client.private_key, ts, "GET", WS_PATH)
    return [
        f"Host: {WS_HOST}",
        f"KALSHI-ACCESS-KEY: {client.api_key}",
        f"KALSHI-ACCESS-SIGNATURE: {sig}",
        f"KALSHI-ACCESS-TIMESTAMP: {ts}",
    ]


def subscribe(ws, tickers: list):
    if not tickers:
        print("No tickers to subscribe to.")
        return
    for i, ticker in enumerate(tickers):
        ws.send(json.dumps({
            "id": i + 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_ticker": ticker
            }
        }))
    print(f"Subscribed to {len(tickers)} tickers.")


def on_open(ws):
    print("Connected to Kalshi WebSocket")


def on_message(ws, message):
    try:
        data = json.loads(message)
    except Exception:
        return

    msg_type = data.get("type")
    msg = data.get("msg", {})

    if msg_type == "orderbook_snapshot":
        ticker = msg.get("market_ticker")
        if not ticker:
            return
        def parse_side(side):
            if not side:
                return []
            return [[float(e[0]), float(e[1])] for e in side]
        with _lock:
            live_books[ticker] = {
                "yes": parse_side(msg.get("yes_dollars_fp", [])),  # FIXED
                "no":  parse_side(msg.get("no_dollars_fp", []))    # FIXED
            }
        _print_top(ticker)

    elif msg_type == "orderbook_delta":
        ticker = msg.get("market_ticker")
        side = msg.get("side")
        price = msg.get("price_dollars")
        delta = msg.get("delta_fp")          # FIXED: was "delta"
        if None in (ticker, side, price, delta):
            return
        try:
            price = float(price)
            delta = float(delta)
        except (TypeError, ValueError):
            return
        with _lock:
            if ticker not in live_books:
                live_books[ticker] = {"yes": [], "no": []}
            book_side = live_books[ticker][side]
            for entry in book_side:
                if entry[0] == price:
                    entry[1] += delta
                    if entry[1] <= 0:
                        book_side.remove(entry)
                    break
            else:
                if delta > 0:
                    book_side.append([price, delta])
                    book_side.sort(key=lambda x: -x[0])
        _print_top(ticker)

    elif msg_type == "subscribed":
        pass

    elif msg_type == "error":
        print("WS error msg:", data)


def _print_top(ticker):
    book = live_books.get(ticker, {})
    yes = book.get("yes")
    no = book.get("no")
    print(
        ticker,
        "YES:", yes[0][0] if yes else None,
        "NO:", no[0][0] if no else None
    )


def on_error(ws, error):
    print("WS error:", error)


def on_close(ws, *args):
    print("WebSocket closed")


def find_liquid_ticker():
    print("Finding a liquid ticker...")
    raw = client.get_markets()
    for m in raw:
        yes_bid = float(m.get("yes_bid_dollars") or 0)
        no_bid = float(m.get("no_bid_dollars") or 0)
        yes_ask = float(m.get("yes_ask_dollars") or 0)
        no_ask = float(m.get("no_ask_dollars") or 0)
        volume = float(m.get("volume_fp") or 0)
        if yes_bid > 0 and yes_ask > 0 and no_bid > 0 and no_ask > 0 and volume > 100:
            ticker = m.get("ticker")
            print(f"Found: {ticker} YES {yes_bid}/{yes_ask} NO {no_bid}/{no_ask} vol {volume}")
            return ticker
    print("No liquid ticker found.")
    return None


def start(tickers=None, daemon=False):
    headers = build_headers()
    ws = websocket.WebSocketApp(
        WS_URL,
        header=headers,
        on_open=lambda w: (on_open(w), subscribe(w, tickers or [])),
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    if daemon:
        t = threading.Thread(target=ws.run_forever, daemon=True)
        t.start()
        return ws
    else:
        ws.run_forever()


if __name__ == "__main__":
    ticker = find_liquid_ticker()
    if ticker:
        start(tickers=[ticker])
    else:
        print("No liquid markets to test with.")