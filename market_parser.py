import re

NBA_ABBREVS = {
    "ATL":"Atlanta Hawks","BOS":"Boston Celtics","BRK":"Brooklyn Nets","BKN":"Brooklyn Nets",
    "CHA":"Charlotte Hornets","CHI":"Chicago Bulls","CLE":"Cleveland Cavaliers","DAL":"Dallas Mavericks",
    "DEN":"Denver Nuggets","DET":"Detroit Pistons","GSW":"Golden State Warriors","GS":"Golden State Warriors",
    "HOU":"Houston Rockets","IND":"Indiana Pacers","LAC":"Los Angeles Clippers","LAK":"Los Angeles Lakers",
    "LAL":"Los Angeles Lakers","MEM":"Memphis Grizzlies","MIA":"Miami Heat","MIL":"Milwaukee Bucks",
    "MIN":"Minnesota Timberwolves","NOP":"New Orleans Pelicans","NYK":"New York Knicks",
    "OKC":"Oklahoma City Thunder","ORL":"Orlando Magic","PHI":"Philadelphia 76ers","PHX":"Phoenix Suns",
    "PHO":"Phoenix Suns","POR":"Portland Trail Blazers","SAC":"Sacramento Kings","SAS":"San Antonio Spurs",
    "TOR":"Toronto Raptors","UTA":"Utah Jazz","WAS":"Washington Wizards",
}

NHL_ABBREVS = {
    "ANA":"Anaheim Ducks","BOS":"Boston Bruins","BUF":"Buffalo Sabres","CGY":"Calgary Flames",
    "CAR":"Carolina Hurricanes","CHI":"Chicago Blackhawks","COL":"Colorado Avalanche",
    "CBJ":"Columbus Blue Jackets","DAL":"Dallas Stars","DET":"Detroit Red Wings","EDM":"Edmonton Oilers",
    "FLA":"Florida Panthers","LAK":"Los Angeles Kings","LA":"Los Angeles Kings","MIN":"Minnesota Wild",
    "MTL":"Montreal Canadiens","NSH":"Nashville Predators","NJD":"New Jersey Devils","NJ":"New Jersey Devils",
    "NYI":"New York Islanders","NYR":"New York Rangers","OTT":"Ottawa Senators","PHI":"Philadelphia Flyers",
    "PIT":"Pittsburgh Penguins","SEA":"Seattle Kraken","SJS":"San Jose Sharks","STL":"St. Louis Blues",
    "TBL":"Tampa Bay Lightning","TB":"Tampa Bay Lightning","TOR":"Toronto Maple Leafs",
    "VAN":"Vancouver Canucks","VGK":"Vegas Golden Knights","WSH":"Washington Capitals","WPG":"Winnipeg Jets",
    "UTA":"Utah Hockey Club",
}

MLB_ABBREVS = {
    "ARI":"Arizona Diamondbacks","ATL":"Atlanta Braves","BAL":"Baltimore Orioles","BOS":"Boston Red Sox",
    "CHC":"Chicago Cubs","CWS":"Chicago White Sox","CIN":"Cincinnati Reds","CLE":"Cleveland Guardians",
    "COL":"Colorado Rockies","DET":"Detroit Tigers","HOU":"Houston Astros","KC":"Kansas City Royals",
    "KCR":"Kansas City Royals","LAA":"Los Angeles Angels","LAD":"Los Angeles Dodgers","MIA":"Miami Marlins",
    "MIL":"Milwaukee Brewers","MIN":"Minnesota Twins","NYM":"New York Mets","NYY":"New York Yankees",
    "OAK":"Oakland Athletics","PHI":"Philadelphia Phillies","PIT":"Pittsburgh Pirates","SD":"San Diego Padres",
    "SDP":"San Diego Padres","SF":"San Francisco Giants","SFG":"San Francisco Giants","SEA":"Seattle Mariners",
    "STL":"St. Louis Cardinals","TB":"Tampa Bay Rays","TBR":"Tampa Bay Rays","TEX":"Texas Rangers",
    "TOR":"Toronto Blue Jays","WAS":"Washington Nationals","WSN":"Washington Nationals",
}

NFL_ABBREVS = {
    "ARI":"Arizona Cardinals","ATL":"Atlanta Falcons","BAL":"Baltimore Ravens","BUF":"Buffalo Bills",
    "CAR":"Carolina Panthers","CHI":"Chicago Bears","CIN":"Cincinnati Bengals","CLE":"Cleveland Browns",
    "DAL":"Dallas Cowboys","DEN":"Denver Broncos","DET":"Detroit Lions","GB":"Green Bay Packers",
    "GBP":"Green Bay Packers","HOU":"Houston Texans","IND":"Indianapolis Colts","JAX":"Jacksonville Jaguars",
    "KC":"Kansas City Chiefs","KCK":"Kansas City Chiefs","LAC":"Los Angeles Chargers","LAR":"Los Angeles Rams",
    "LVR":"Las Vegas Raiders","LV":"Las Vegas Raiders","MIA":"Miami Dolphins","MIN":"Minnesota Vikings",
    "NE":"New England Patriots","NEP":"New England Patriots","NO":"New Orleans Saints","NOS":"New Orleans Saints",
    "NYG":"New York Giants","NYJ":"New York Jets","PHI":"Philadelphia Eagles","PIT":"Pittsburgh Steelers",
    "SF":"San Francisco 49ers","SFO":"San Francisco 49ers","SEA":"Seattle Seahawks","TB":"Tampa Bay Buccaneers",
    "TBB":"Tampa Bay Buccaneers","TEN":"Tennessee Titans","WAS":"Washington Commanders",
}

SERIES_MAP = {
    "KXNBAGAME": ("NBA", NBA_ABBREVS),
    "KXNHLGAME": ("NHL", NHL_ABBREVS),
    "KXMLBGAME": ("MLB", MLB_ABBREVS),
    "KXNFLGAME": ("NFL", NFL_ABBREVS),
    "KXNCAABGAME": ("NCAAB", NBA_ABBREVS),
    "KXNCAAWBGAME": ("NCAAWB", NBA_ABBREVS),
}

def parse_ticker(ticker):
    ticker = ticker.upper()
    parts = ticker.split("-")
    if len(parts) < 3:
        return None
    series = parts[0]
    side_abbr = parts[2]
    sport_info = SERIES_MAP.get(series)
    if not sport_info:
        return None
    sport, abbrev_map = sport_info
    side_team = abbrev_map.get(side_abbr)
    if not side_team:
        return None
    middle = parts[1]
    date_match = re.match(r"^\d{2}[A-Z]{3}\d{2}", middle)
    if not date_match:
        return None
    teams_str = middle[date_match.end():]
    other_team = None
    for length in [3, 2, 4]:
        t1 = teams_str[:length]
        t2 = teams_str[length:]
        if t1 in abbrev_map and t2 in abbrev_map:
            t1_name = abbrev_map[t1]
            t2_name = abbrev_map[t2]
            other_team = t2_name if t1_name == side_team else t1_name
            break
    return {"sport": sport, "side_team": side_team, "other_team": other_team, "side_abbr": side_abbr}
