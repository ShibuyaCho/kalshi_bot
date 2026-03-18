"""
news_client.py
Fetches recent sports news headlines via NewsAPI and scores them as
positive/negative/neutral for a given team.

Free NewsAPI key: https://newsapi.org (100 requests/day on free tier)
We cache results per team for NEWS_CACHE_MINUTES to stay within limits.
"""

import requests
import time
import config

BASE = "https://newsapi.org/v2/everything"

# Simple cache: {team_name: {"score": float, "fetched_at": timestamp}}
_cache: dict = {}
NEWS_CACHE_MINUTES = 30

# Words that suggest a team is performing well / price should be higher
POSITIVE_WORDS = {
    "win", "wins", "winning", "won", "victory", "dominant", "dominates",
    "streak", "unbeaten", "healthy", "returns", "back", "star", "mvp",
    "hot", "rolling", "surging", "leads", "clinch", "playoff",
}

# Words that suggest a team is struggling / price should be lower
NEGATIVE_WORDS = {
    "loss", "loses", "losing", "lost", "injury", "injured", "out",
    "doubtful", "questionable", "suspend", "suspended", "slump",
    "struggling", "fired", "benched", "eliminated", "worst", "skid",
}


def _sentiment_score(headlines: list[str]) -> float:
    """
    Score a list of headlines from -1.0 (very negative) to +1.0 (very positive).
    Simple word-count approach — good enough for a first signal layer.
    """
    pos = neg = 0
    for headline in headlines:
        words = headline.lower().split()
        pos += sum(1 for w in words if w in POSITIVE_WORDS)
        neg += sum(1 for w in words if w in NEGATIVE_WORDS)

    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def get_team_sentiment(team_name: str) -> float:
    """
    Returns a sentiment score for a team based on recent news headlines:
      +1.0 = very positive news
       0.0 = neutral / no news
      -1.0 = very negative news

    Results are cached for NEWS_CACHE_MINUTES.
    """
    if not config.NEWS_API_KEY or config.NEWS_API_KEY == "YOUR_NEWS_API_KEY_HERE":
        return 0.0

    cached = _cache.get(team_name)
    if cached and (time.time() - cached["fetched_at"]) < NEWS_CACHE_MINUTES * 60:
        return cached["score"]

    try:
        r = requests.get(BASE, params={
            "apiKey": config.NEWS_API_KEY,
            "q": team_name,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
        }, timeout=10)
        r.raise_for_status()
        articles = r.json().get("articles", [])
        headlines = [a.get("title", "") for a in articles if a.get("title")]
        score = _sentiment_score(headlines)
        _cache[team_name] = {"score": score, "fetched_at": time.time()}
        print(f"[news] {team_name}: {len(headlines)} headlines, sentiment={score:+.2f}")
        return score
    except Exception as e:
        print(f"[news] Error fetching news for {team_name}: {e}")
        return 0.0
