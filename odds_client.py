"""
odds_client.py
Fetches moneyline odds from The Odds API and converts them to consensus
implied probabilities (vig-removed) that can be compared against Kalshi prices.
"""

import requests
import config

BASE = "https://api.the-odds-api.com/v4/sports"

# Sports supported — maps sport key → human label
SUPPORTED_SPORTS = {
    "basketball_nba": "NBA",
    "americanfootball_nfl": "NFL",
    "baseball_mlb": "MLB",
    "icehockey_nhl": "NHL",
}


def _get_odds(sport_key: str) -> list:
    """Return raw odds API response for a given sport."""
    url = f"{BASE}/{sport_key}/odds"
    params = {
        "apiKey": config.ODDS_API_KEY,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[odds_client] Error fetching {sport_key}: {e}")
        return []


def american_to_prob(odds: float) -> float:
    """Convert American odds to raw implied probability (includes vig)."""
    if odds > 0:
        return 100.0 / (odds + 100.0)
    else:
        return (-odds) / (-odds + 100.0)


def remove_vig(prob_a: float, prob_b: float):
    """Normalise two raw implied probs to sum to 1.0 (remove bookmaker vig)."""
    total = prob_a + prob_b
    if total == 0:
        return 0.5, 0.5
    return prob_a / total, prob_b / total


def get_consensus_probs(sport_key: str) -> dict:
    """
    Returns a dict keyed by (home_team, away_team) with vig-removed consensus
    win probabilities averaged across all bookmakers.

    Example return value:
    {
      ("Lakers", "Celtics"): {"home_prob": 0.61, "away_prob": 0.39},
      ...
    }
    """
    games = _get_odds(sport_key)
    results = {}

    for game in games:
        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue

        home_probs = []
        away_probs = []

        for bookmaker in game.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                home_odds = outcomes.get(home)
                away_odds = outcomes.get(away)
                if home_odds is None or away_odds is None:
                    continue
                raw_home = american_to_prob(home_odds)
                raw_away = american_to_prob(away_odds)
                fair_home, fair_away = remove_vig(raw_home, raw_away)
                home_probs.append(fair_home)
                away_probs.append(fair_away)

        if not home_probs:
            continue

        results[(home, away)] = {
            "home_prob": round(sum(home_probs) / len(home_probs), 4),
            "away_prob": round(sum(away_probs) / len(away_probs), 4),
            "home_team": home,
            "away_team": away,
            "sport": SUPPORTED_SPORTS.get(sport_key, sport_key),
            "commence_time": game.get("commence_time"),
        }

    return results


def get_all_consensus_probs() -> dict:
    """Fetch and merge consensus probs across all supported sports."""
    all_probs = {}
    for sport_key in SUPPORTED_SPORTS:
        probs = get_consensus_probs(sport_key)
        all_probs.update(probs)
    return all_probs
