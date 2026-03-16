import config

positions = {}


def execute(signal):

    if not signal:
        return

    side, ticker, price = signal

    if config.PAPER_TRADING:

        print("SIM TRADE:", side, ticker, price)

        if side == "BUY":
            positions[ticker] = price

        if side == "SELL":
            positions.pop(ticker, None)