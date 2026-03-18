import requests
import config

SUPPORTED_SPORTS = {
    "basketball_nba": "NBA",
    "icehockey_nhl":  "NHL",
    "baseball_mlb":   "MLB",
    "americanfootball_nfl": "NFL",
}

ESPN_SCOREBOARD = {
    "basketball_nba": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    "icehockey_nhl":  "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
    "baseball_mlb":   "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
    "americanfootball_nfl": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
}

def american_to_prob(odds: float) -> float:
    if odds > 0:
        return 100.0 / (odds + 100.0)
    else:
        return (-odds) / (-odds + 100.0)

def remove_vig(p1: float, p2: float):
    total = p1 + p2
    if total == 0:
        return 0.5, 0.5
    return p1 / total, p2 / total

def _get_espn_scoreboard(sport_key: str) -> dict:
    results = {}
    url = ESPN_SCOREBOARD.get(sport_key)
    if not url:
        return results
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[odds_client] ESPN error for {sport_key}: {e}")
        return results

    for event in data.get("events", []):
        try:
            comp        = event.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue

            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue

            home_name = home.get("team", {}).get("displayName", "")
            away_name = away.get("team", {}).get("displayName", "")
            if not home_name or not away_name:
                continue

            commence  = event.get("date", "")
            odds_list = comp.get("odds", [])
            if not odds_list:
                continue

            home_probs = []
            away_probs = []

            for odds in odds_list:
                ml = odds.get("moneyline", {})
                home_close = ml.get("home", {}).get("close", {}).get("odds")
                away_close = ml.get("away", {}).get("close", {}).get("odds")
                if home_close is None or away_close is None:
                    continue
                try:
                    fh, fa = remove_vig(
                        american_to_prob(float(home_close)),
                        american_to_prob(float(away_close))
                    )
                    home_probs.append(fh)
                    away_probs.append(fa)
                except Exception:
                    continue

            if not home_probs:
                continue

            results[(home_name, away_name)] = {
                "home_prob":     round(sum(home_probs) / len(home_probs), 4),
                "away_prob":     round(sum(away_probs) / len(away_probs), 4),
                "home_team":     home_name,
                "away_team":     away_name,
                "sport":         SUPPORTED_SPORTS.get(sport_key, sport_key),
                "commence_time": commence,
            }

        except Exception:
            continue

    return results

def _get_odds_api(sport_key: str) -> dict:
    if not config.ODDS_API_KEY or config.ODDS_API_KEY == "YOUR_ODDS_API_KEY_HERE":
        return {}
    try:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
            params={"apiKey": config.ODDS_API_KEY, "regions": "us", "markets": "h2h", "oddsFormat": "american"},
            timeout=10
        )
        if r.status_code in (401, 422):
            return {}
        r.raise_for_status()
        games   = r.json()
        results = {}
        for game in games:
            home = game.get("home_team")
            away = game.get("away_team")
            if not home or not away:
                continue
            home_probs = []
            away_probs = []
            for bm in game.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market.get("key") != "h2h":
                        continue
                    outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                    ho = outcomes.get(home)
                    ao = outcomes.get(away)
                    if ho is None or ao is None:
                        continue
                    fh, fa = remove_vig(american_to_prob(ho), american_to_prob(ao))
                    home_probs.append(fh)
                    away_probs.append(fa)
            if not home_probs:
                continue
            results[(home, away)] = {
                "home_prob":     round(sum(home_probs) / len(home_probs), 4),
                "away_prob":     round(sum(away_probs) / len(away_probs), 4),
                "home_team":     home,
                "away_team":     away,
                "sport":         SUPPORTED_SPORTS.get(sport_key, sport_key),
                "commence_time": game.get("commence_time"),
            }
        return results
    except Exception:
        return {}

def get_consensus_probs(sport_key: str) -> dict:
    odds_api = _get_odds_api(sport_key)
    if odds_api:
        return odds_api
    return _get_espn_scoreboard(sport_key)

def get_all_consensus_probs() -> dict:
    all_probs = {}
    for sport_key, label in SUPPORTED_SPORTS.items():
        probs = get_consensus_probs(sport_key)
        all_probs.update(probs)
        print(f"[odds_client] {label}: {len(probs)} matchups")
    return all_probs
