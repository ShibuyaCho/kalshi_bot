def normalize(text):
    return text.lower().replace(".", "").replace("-", " ").strip()


def extract_team_contracts(title):

    title = normalize(title)

    parts = title.split(",")

    teams = []

    for p in parts:

        p = p.strip()

        if p.startswith("yes "):

            outcome = p.replace("yes ", "")

            # ignore player props
            if ":" in outcome:
                continue

            # ignore totals
            if "over" in outcome or "under" in outcome:
                continue

            # ignore spreads
            if "points" in outcome:
                continue

            teams.append(outcome)

    return teams