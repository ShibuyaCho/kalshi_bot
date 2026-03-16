from kalshi_client import KalshiClient
import config

client = KalshiClient()

print("Fetching markets...")

markets = client.get_markets()

if "markets" not in markets:
    print("API error:", markets)
    exit()

ticker = markets["markets"][0]["ticker"]

print("Testing order on market:", ticker)

price = 50  # midpoint price

result = client.place_order(
    ticker,
    price,
    config.TEST_ORDER_SIZE
)

print("Order response:")
print(result)