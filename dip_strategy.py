import config
import market_parser
import news_client

DIP_THRESHOLD_CENTS = 5.0
MIN_LIQUIDITY = 5

def _blend_fair_value(odds_prob, news_score):
    return round(odds_prob * 100 + news_score * 3.0, 2)

def evaluate_dip(ticker, snapshot, consensus_probs):
    if not snapshot or not consensus_probs:
        return None
    if snapshot["liquidity"] < MIN_LIQUIDITY:
        return None
    parsed = market_parser.parse_ticker(ticker)
    if not parsed:
        return None
    side_team = parsed["side_team"]
    other_team = parsed.get("other_team")
    match = None
    side_is_home = None
    for (home, away), data in consensus_probs.items():
        if side_team == home or side_team in home or home in side_team:
            match = data
            side_is_home = True
            break
        if side_team == away or side_team in away or away in side_team:
            match = data
            side_is_home = False
            break
    if not match:
        return None
    odds_prob = match["home_prob"] if side_is_home else match["away_prob"]
    news_score = 0.0
    try:
        news_score = news_client.get_team_sentiment(side_team)
    except Exception:
        pass
    fair_yes_cents = _blend_fair_value(odds_prob, news_score)
    kalshi_yes_cents = snapshot["yes_price"] * 100
    dip = fair_yes_cents - kalshi_yes_cents
    if dip < DIP_THRESHOLD_CENTS:
        return None
    return {
        "ticker": ticker,
        "action": "BUY_YES",
        "side": "yes",
        "kalshi_cents": round(kalshi_yes_cents, 1),
        "fair_value_cents": fair_yes_cents,
        "dip_cents": round(dip, 1),
        "yes_price_dollars": snapshot["yes_price"],
        "no_price_dollars": snapshot["no_price"],
        "commence_time": match.get("commence_time"),
        "matchup": f"{side_team} vs {other_team or '?'}",
        "reason": f"[DIP] {side_team} YES={kalshi_yes_cents:.1f}c fair={fair_yes_cents:.1f}c dip={dip:+.1f}c",
        "source": "dip",
    }
