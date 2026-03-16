from kalshi_client import KalshiClient


client = KalshiClient()

markets = client.get_markets()

sports_markets = []

for market in markets.get("markets", []):

    ticker = market.get("ticker", "")
    title = market.get("title", "")

    # Kalshi sports tickers often include these prefixes
    if ticker.startswith("KXMVESPORTS") or "game" in title.lower():

        sports_markets.append({
            "ticker": ticker,
            "title": title,
            "status": market.get("status"),
            "yes_bid": market.get("yes_bid"),
            "yes_ask": market.get("yes_ask"),
        })


print("\nFound Sports Markets:\n")

for m in sports_markets:

    print("Ticker:", m["ticker"])
    print("Title:", m["title"])
    print("Status:", m["status"])
    print("YES Bid:", m["yes_bid"])
    print("YES Ask:", m["yes_ask"])
    print("-" * 40)