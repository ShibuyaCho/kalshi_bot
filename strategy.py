import config

# store rolling prices for each market
price_history = {}


def signal(snapshot):

    ticker = snapshot["ticker"]
    price = snapshot["price"]

    if ticker not in price_history:
        price_history[ticker] = []

    history = price_history[ticker]

    history.append(price)

    # keep last 10 prices
    if len(history) > 10:
        history.pop(0)

    avg_price = sum(history) / len(history)

    edge = price - avg_price

    print(
        ticker,
        "PRICE:", price,
        "AVG:", round(avg_price, 2),
        "EDGE:", round(edge, 2)
    )

    # buy dip
    if edge <= -config.EDGE_THRESHOLD:
        return "BUY"

    # sell spike
    if edge >= config.EDGE_THRESHOLD:
        return "SELL"

    return None