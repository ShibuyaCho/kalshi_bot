"""
strategy.py
Two independent signal generators:

1. arb_signal(snapshot)
   Pure Kalshi order-book arbitrage — fires when YES + NO implied prices
   deviate from 100 cents (gap or overhang). No external data needed.
   This is already well-implemented in trade_bot.py; kept here for reference.

2. odds_signal(ticker, kalshi_yes_price_cents, consensus_probs)
   Compares Kalshi's YES price against the consensus fair-value probability
   from external sportsbooks. Fires when there is a meaningful edge.
"""

import config
import market_parser


def odds_signal(ticker: str, kalshi_yes_cents: float, consensus_probs: dict):
    """
    Compare Kalshi's YES price (in cents, 0-100) against the consensus
    fair-value from sportsbooks.

    consensus_probs: output of odds_client.get_all_consensus_probs()
      keys are (home_team, away_team), values have home_prob / away_prob

    Returns a dict with action, edge, and reason — or None if no edge found.
    """
    parsed = market_parser.parse_ticker(ticker)
    if not parsed:
        return None

    team1 = parsed["team1"]
    team2 = parsed["team2"]

    # Try both orderings since we don't know which team is YES on Kalshi
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

    # Fair value of YES side in cents
    if team1_is_yes:
        fair_yes_cents = match["home_prob"] * 100
    else:
        fair_yes_cents = match["away_prob"] * 100

    edge = fair_yes_cents - kalshi_yes_cents  # positive = Kalshi underpriced YES

    if abs(edge) < config.ODDS_EDGE_THRESHOLD:
        return None

    action = "BUY_YES" if edge > 0 else "BUY_NO"
    return {
        "ticker": ticker,
        "action": action,
        "kalshi_yes_cents": round(kalshi_yes_cents, 1),
        "fair_yes_cents": round(fair_yes_cents, 1),
        "edge_cents": round(edge, 1),
        "sport": parsed["sport"],
        "matchup": f"{team1} vs {team2}",
        "reason": (
            f"Odds edge: Kalshi YES={kalshi_yes_cents:.1f}c, "
            f"fair={fair_yes_cents:.1f}c, edge={edge:+.1f}c"
        ),
    }
