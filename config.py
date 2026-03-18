# ── Kalshi credentials ────────────────────────────────────────────────────────
KALSHI_API_KEY          = "badfebbf-0b3b-4e1f-aabe-ee19fbe46c46"   # ⚠ rotate this
KALSHI_PRIVATE_KEY_PATH = "/home/jackson/kalshi_bot/kalshi-key.txt"

# ── The Odds API ───────────────────────────────────────────────────────────────
ODDS_API_KEY = "YOUR_ODDS_API_KEY_HERE"     # https://the-odds-api.com (free tier)

# ── NewsAPI ────────────────────────────────────────────────────────────────────
NEWS_API_KEY = "YOUR_NEWS_API_KEY_HERE"     # https://newsapi.org (free tier)

# ── Bot behaviour ──────────────────────────────────────────────────────────────
TRADING_ENABLED     = True      # set False for dry-run / log-only mode

SCAN_INTERVAL       = 10        # seconds between scan loops

# Arb strategy (order-book gap/overhang)
EDGE_THRESHOLD      = 1.5       # min cents of YES+NO mispricing
LIQUIDITY_THRESHOLD = 50        # min combined contract depth

# Odds strategy (Kalshi vs sportsbook fair value)
ODDS_EDGE_THRESHOLD = 4         # min cents of edge vs external odds
ODDS_SCAN_INTERVAL  = 60        # seconds between odds API refreshes

# Dip strategy (buy dip, sell before event)
DIP_THRESHOLD_CENTS = 5.0       # min cents below fair value to trigger buy
DIP_SCAN_INTERVAL   = 60        # seconds between dip scans

# Position sizing
ORDER_SIZE          = 1
MAX_POSITION_PCT    = 0.02      # max 2% of balance per trade
MIN_ORDER_DOLLARS   = 0.05
MAX_ORDER_DOLLARS   = 2.00
