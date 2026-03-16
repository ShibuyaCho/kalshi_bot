import config


def approve(signal, positions):

    if not signal:
        return False

    side, ticker, price = signal

    if side == "BUY":

        if len(positions) >= config.MAX_POSITIONS:
            return False

    return True