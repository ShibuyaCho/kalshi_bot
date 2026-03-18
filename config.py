# ── Kalshi credentials ────────────────────────────────────────────────────────
KALSHI_API_KEY          = "badfebbf-0b3b-4e1f-aabe-ee19fbe46c46"   # ⚠ rotate this
KALSHI_PRIVATE_KEY_PATH = "/home/jackson/kalshi_bot/kalshi-key.txt"

# ── The Odds API ───────────────────────────────────────────────────────────────
ODDS_API_KEY = "YOUR_ODDS_API_KEY_HERE"   # get free key at the-odds-api.com

# ── Bot behaviour ──────────────────────────────────────────────────────────────
TRADING_ENABLED    = True      # set False to run in dry-run / log-only mode

SCAN_INTERVAL      = 10        # seconds between scan loops

# Arbitrage strategy (gap / overhang on Kalshi order book)
EDGE_THRESHOLD     = 1.5       # minimum cents of mispricing before trading
LIQUIDITY_THRESHOLD = 50       # minimum combined contract depth required

# Odds-arbitrage strategy (Kalshi price vs external sportsbook)
ODDS_EDGE_THRESHOLD = 4        # minimum cents of edge vs external odds to trade
ODDS_SCAN_INTERVAL  = 60       # seconds between odds API refreshes (rate-limit friendly)

# Position sizing
ORDER_SIZE         = 1         # fallback contracts if dynamic sizing fails
MAX_POSITION_PCT   = 0.02      # max 2 % of balance per trade
MIN_ORDER_DOLLARS  = 0.05
MAX_ORDER_DOLLARS  = 2.00
