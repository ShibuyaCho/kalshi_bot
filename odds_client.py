import requests
import config


BASE = "https://api.the-odds-api.com/v4/sports"


def get_nba_odds():

    url = f"{BASE}/basketball_nba/odds"

    params = {
        "apiKey": config.ODDS_API_KEY,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american"
    }

    r = requests.get(url, params=params)

    return r.json()


def american_to_probability(odds):

    if odds > 0:
        return 100 / (odds + 100)

    else:
        return -odds / (-odds + 100)