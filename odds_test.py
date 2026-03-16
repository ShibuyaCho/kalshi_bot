from odds_client import get_nba_odds, american_to_probability


games = get_nba_odds()

for game in games:

    home = game["home_team"]
    away = game["away_team"]

    book = game["bookmakers"][0]
    outcomes = book["markets"][0]["outcomes"]

    print("\nGame:", away, "vs", home)

    for o in outcomes:

        prob = american_to_probability(o["price"])

        print(
            o["name"],
            "odds:", o["price"],
            "probability:", round(prob, 3)
        )