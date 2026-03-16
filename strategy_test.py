from strategy import should_buy_yes


# Example market
kalshi_price = 52   # 52 cents
vegas_probability = 0.61


buy, edge = should_buy_yes(
    vegas_probability,
    kalshi_price
)

print("Edge:", edge)

if buy:
    print("TRADE: BUY YES")
else:
    print("No trade")