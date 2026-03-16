import config
from kalshi_client import KalshiClient

client = KalshiClient()

markets = []
liquid_markets = []


def discover_markets():
    global markets
    markets = []

    data = client.get_markets()

    print("MARKETS RECEIVED:", len(data))

    for m in data:
        ticker = m.get("ticker")
        status = m.get("status")

        if not ticker:
            continue

        if status != "active":
            continue

        markets.append(ticker)

    print("ACTIVE MARKETS:", len(markets))
    return markets


def find_liquid_markets():
    global liquid_markets
    liquid_markets = []

    print("\nScanning markets for liquidity...\n")

    for ticker in markets:

        try:
            book = client.get_orderbook(ticker)
        except Exception:
            continue

        if not book:
            continue

        orderbook = book.get("orderbook")

        if not orderbook:
            continue

        yes = orderbook.get("yes", [])
        no = orderbook.get("no", [])

        if yes or no:
            liquid_markets.append(ticker)

    print("LIQUID MARKETS FOUND:", len(liquid_markets))
    return liquid_markets


def get_snapshot(ticker):

    try:
        book = client.get_orderbook(ticker)
    except Exception:
        return None

    if not book:
        return None

    orderbook = book.get("orderbook")

    if not orderbook:
        return None

    yes = orderbook.get("yes")
    no = orderbook.get("no")

    if not yes or not no:
        return None

    try:
        yes_price = yes[0][0]
        yes_size = yes[0][1]

        no_price = no[0][0]
        no_size = no[0][1]
    except Exception:
        return None

    liquidity = yes_size + no_size

    if liquidity < config.LIQUIDITY_THRESHOLD:
        return None

    return {
        "ticker": ticker,
        "price": yes_price,
        "liquidity": liquidity
    }