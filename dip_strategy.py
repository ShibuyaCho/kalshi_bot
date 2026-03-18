"""
dip_strategy.py
Detects when a Kalshi sports market price has dipped below fair value
by combining three research signals:

  1. Vegas/sportsbook consensus odds  (weight: 0.60)
  2. News sentiment for each team     (weight: 0.25)
  3. Historical H2H / recent form     (weight: 0.15, via odds API implied)

The three signals are blended into a single fair_value estimate.
A dip is flagged when:
  kalshi_price < fair_value - DIP_THRESHOLD_CENTS

The bot buys the dip (YES if underpriced, NO if overpriced) and hands
the position to positions.py to manage the exit.
"""

import config
import market_parser
import news_client

# How many cents below fair value before we consider it a dip worth buying
DIP_THRESHOLD_CENTS = 5.0

# Minimum liquidity required (contracts) before we trade
MIN_LIQUIDITY = 20


def _blend_fair_value(odds_prob: float, news_score: float) -> float:
    """
    Blend signals into a single fair value (0–100 cents).

    odds_prob:   vig-removed win probability from sportsbooks (0.0–1.0)
    news_score:  sentiment score (-1.0 to +1.0)

    News nudges the fair value up or down by up to 3 cents.
    """
    base = odds_prob * 100                  # convert to cents
    news_adjustment = news_score * 3.0      # ±3 cents max from news
    return round(base + news_adjustment, 2)


def evaluate_dip(ticker: str, snapshot: dict, consensus_probs: dict) -> dict | None:
    """
    Given a live market snapshot and current consensus odds, determine
    whether the market is in a buyable dip.

    Returns a signal dict or None.

    Signal dict:
    {
      "ticker":           str,
      "action":           "BUY_YES" | "BUY_NO",
      "side":             "yes" | "no",
      "kalshi_cents":     float,   # current Kalshi price
      "fair_value_cents": float,   # our blended estimate
      "dip_cents":        float,   # how far below fair value
      "yes_price_dollars": float,
      "no_price_dollars":  float,
      "commence_time":    str | None,
      "matchup":          str,
      "reason":           str,
      "source":           "dip",
    }
    """
    if not snapshot or not consensus_probs:
        return None

    if snapshot["liquidity"] < MIN_LIQUIDITY:
        return None

    # Only process sports tickers we can parse
    parsed = market_parser.parse_ticker(ticker)
    if not parsed:
        return None

    team1 = parsed["team1"]
    team2 = parsed["team2"]

    # Match against consensus odds
    match = None
    team1_is_yes = None
    for (home, away), data in consensus_probs.items():
        if home == team1 and away == team2:
            match = data
            team1_is_yes = True
            break
        if home == team2 and away == team1:
            match = data
            team1_is_yes = False
            break

    if not match:
        return None

    # Determine which team is the YES side and get their odds probability
    if team1_is_yes:
        yes_team  = team1
        no_team   = team2
        odds_prob = match["home_prob"]
    else:
        yes_team  = team2
        no_team   = team1
        odds_prob = match["away_prob"]

    # Pull news sentiment for both teams
    yes_sentiment = news_client.get_team_sentiment(yes_team)
    no_sentiment  = news_client.get_team_sentiment(no_team)

    # Blend into fair value for YES side
    # Positive yes_sentiment pushes fair value up; positive no_sentiment pushes it down
    net_sentiment = yes_sentiment - no_sentiment
    fair_yes_cents = _blend_fair_value(odds_prob, net_sentiment)

    kalshi_yes_cents = snapshot["yes_price"] * 100
    kalshi_no_cents  = snapshot["no_price"]  * 100

    dip_yes = fair_yes_cents - kalshi_yes_cents   # positive = YES is underpriced
    dip_no  = (100 - fair_yes_cents) - kalshi_no_cents  # positive = NO is underpriced

    # Check YES dip
    if dip_yes >= DIP_THRESHOLD_CENTS:
        return {
            "ticker":            ticker,
            "action":            "BUY_YES",
            "side":              "yes",
            "kalshi_cents":      round(kalshi_yes_cents, 1),
            "fair_value_cents":  fair_yes_cents,
            "dip_cents":         round(dip_yes, 1),
            "yes_price_dollars": snapshot["yes_price"],
            "no_price_dollars":  snapshot["no_price"],
            "commence_time":     match.get("commence_time"),
            "matchup":           f"{yes_team} vs {no_team}",
            "reason": (
                f"[DIP] {yes_team} YES dip: Kalshi={kalshi_yes_cents:.1f}c "
                f"fair={fair_yes_cents:.1f}c dip={dip_yes:+.1f}c "
                f"(odds={odds_prob*100:.1f}c news={net_sentiment:+.2f})"
            ),
            "source": "dip",
        }

    # Check NO dip
    if dip_no >= DIP_THRESHOLD_CENTS:
        fair_no_cents = 100 - fair_yes_cents
        return {
            "ticker":            ticker,
            "action":            "BUY_NO",
            "side":              "no",
            "kalshi_cents":      round(kalshi_no_cents, 1),
            "fair_value_cents":  round(fair_no_cents, 1),
            "dip_cents":         round(dip_no, 1),
            "yes_price_dollars": snapshot["yes_price"],
            "no_price_dollars":  snapshot["no_price"],
            "commence_time":     match.get("commence_time"),
            "matchup":           f"{yes_team} vs {no_team}",
            "reason": (
                f"[DIP] {no_team} NO dip: Kalshi={kalshi_no_cents:.1f}c "
                f"fair={fair_no_cents:.1f}c dip={dip_no:+.1f}c "
                f"(odds={odds_prob*100:.1f}c news={net_sentiment:+.2f})"
            ),
            "source": "dip",
        }

    return None
