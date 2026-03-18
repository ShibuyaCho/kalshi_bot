"""
market_parser.py
Extracts team names from Kalshi market tickers/titles so they can be matched
against external sportsbook odds.

Kalshi sports tickers look like:
  KXNBA-25MAR18-LAKLAC   (Lakers vs Clippers, Mar 18 2025)
  KXNBA-25MAR18-BOSCLE
  KXNFL-26FEB02-KCKCHI
  KXMLB-26APR01-NYYBOS

We parse the suffix and map abbreviations → canonical team names.
"""

NBA_ABBREVS = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BRK": "Brooklyn Nets",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "GS":  "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAK": "Los Angeles Lakers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "PHO": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}

NFL_ABBREVS = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB":  "Green Bay Packers",
    "GBP": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC":  "Kansas City Chiefs",
    "KCK": "Kansas City Chiefs",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "LVR": "Las Vegas Raiders",
    "LV":  "Las Vegas Raiders",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE":  "New England Patriots",
    "NEP": "New England Patriots",
    "NO":  "New Orleans Saints",
    "NOS": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SF":  "San Francisco 49ers",
    "SFO": "San Francisco 49ers",
    "SEA": "Seattle Seahawks",
    "TB":  "Tampa Bay Buccaneers",
    "TBB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}

MLB_ABBREVS = {
    "ARI": "Arizona Diamondbacks",
    "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",
    "CHC": "Chicago Cubs",
    "CWS": "Chicago White Sox",
    "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",
    "DET": "Detroit Tigers",
    "HOU": "Houston Astros",
    "KC":  "Kansas City Royals",
    "KCR": "Kansas City Royals",
    "LAA": "Los Angeles Angels",
    "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",
    "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",
    "NYM": "New York Mets",
    "NYY": "New York Yankees",
    "OAK": "Oakland Athletics",
    "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",
    "SD":  "San Diego Padres",
    "SDP": "San Diego Padres",
    "SF":  "San Francisco Giants",
    "SFG": "San Francisco Giants",
    "SEA": "Seattle Mariners",
    "STL": "St. Louis Cardinals",
    "TB":  "Tampa Bay Rays",
    "TBR": "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
    "WAS": "Washington Nationals",
    "WSN": "Washington Nationals",
}

NHL_ABBREVS = {
    "ANA": "Anaheim Ducks",
    "ARI": "Arizona Coyotes",
    "BOS": "Boston Bruins",
    "BUF": "Buffalo Sabres",
    "CGY": "Calgary Flames",
    "CAR": "Carolina Hurricanes",
    "CHI": "Chicago Blackhawks",
    "COL": "Colorado Avalanche",
    "CBJ": "Columbus Blue Jackets",
    "DAL": "Dallas Stars",
    "DET": "Detroit Red Wings",
    "EDM": "Edmonton Oilers",
    "FLA": "Florida Panthers",
    "LAK": "Los Angeles Kings",
    "MIN": "Minnesota Wild",
    "MTL": "Montreal Canadiens",
    "NSH": "Nashville Predators",
    "NJD": "New Jersey Devils",
    "NYI": "New York Islanders",
    "NYR": "New York Rangers",
    "OTT": "Ottawa Senators",
    "PHI": "Philadelphia Flyers",
    "PIT": "Pittsburgh Penguins",
    "SEA": "Seattle Kraken",
    "SJS": "San Jose Sharks",
    "STL": "St. Louis Blues",
    "TBL": "Tampa Bay Lightning",
    "TOR": "Toronto Maple Leafs",
    "VAN": "Vancouver Canucks",
    "VGK": "Vegas Golden Knights",
    "WSH": "Washington Capitals",
    "WPG": "Winnipeg Jets",
}

SPORT_MAP = {
    "NBA": NBA_ABBREVS,
    "NFL": NFL_ABBREVS,
    "MLB": MLB_ABBREVS,
    "NHL": NHL_ABBREVS,
}


def parse_ticker(ticker: str):
    """
    Given a Kalshi ticker like 'KXNBA-25MAR18-LAKLAC', return a dict:
    {
      "sport": "NBA",
      "team1": "Los Angeles Lakers",
      "team2": "Los Angeles Clippers",
      "team1_abbrev": "LAK",
      "team2_abbrev": "LAC",
    }
    or None if it can't be parsed.
    """
    parts = ticker.upper().split("-")
    if len(parts) < 3:
        return None

    prefix = parts[0]  # e.g. KXNBA
    suffix = parts[2]  # e.g. LAKLAC

    sport = None
    abbrev_map = None
    for sport_key, mapping in SPORT_MAP.items():
        if sport_key in prefix:
            sport = sport_key
            abbrev_map = mapping
            break

    if not abbrev_map:
        return None

    # Try splitting suffix into two abbreviations (3+3, 2+3, 3+2, 2+2)
    for split in [3, 2]:
        t1_abbrev = suffix[:split]
        t2_abbrev = suffix[split:]
        t1 = abbrev_map.get(t1_abbrev)
        t2 = abbrev_map.get(t2_abbrev)
        if t1 and t2:
            return {
                "sport": sport,
                "team1": t1,
                "team2": t2,
                "team1_abbrev": t1_abbrev,
                "team2_abbrev": t2_abbrev,
            }

    return None
