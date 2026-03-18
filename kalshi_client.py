import requests
import json
import datetime
import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import config

def load_private_key(path: str):
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(
            f.read(), password=None, backend=default_backend()
        )

def sign_pss(private_key, timestamp: str, method: str, path: str) -> str:
    path_without_query = path.split("?")[0]
    message = f"{timestamp}{method}{path_without_query}".encode("utf-8")
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode("utf-8")

class KalshiClient:
    def __init__(self):
        self.api_key     = config.KALSHI_API_KEY
        self.private_key = load_private_key(config.KALSHI_PRIVATE_KEY_PATH)
        self.base_url    = "https://api.elections.kalshi.com"
        self.base_path   = "/trade-api/v2"

    def _headers(self, method: str, path: str) -> dict:
        full_path = self.base_path + path
        ts  = str(int(datetime.datetime.now().timestamp() * 1000))
        sig = sign_pss(self.private_key, ts, method, full_path)
        return {
            "Content-Type":              "application/json",
            "KALSHI-ACCESS-KEY":         self.api_key,
            "KALSHI-ACCESS-SIGNATURE":   sig,
            "KALSHI-ACCESS-TIMESTAMP":   ts,
        }

    def _get(self, path: str):
        url = self.base_url + self.base_path + path
        r = requests.get(url, headers=self._headers("GET", path))
        if r.status_code != 200:
            print(f"API ERROR {r.status_code}: {r.text}")
            return None
        try:
            return r.json()
        except Exception:
            return None

    def _post(self, path: str, payload: dict):
        url = self.base_url + self.base_path + path
        r = requests.post(
            url,
            headers=self._headers("POST", path),
            data=json.dumps(payload)
        )
        if r.status_code not in (200, 201):
            print(f"POST ERROR {r.status_code}: {r.text}")
            return None
        try:
            return r.json()
        except Exception:
            return None

    def get_balance(self):
        data = self._get("/portfolio/balance")
        if not data:
            return 0.0, 0.0
        return data.get("balance", 0) / 100, data.get("portfolio_value", 0) / 100

    def get_markets(self):
        all_markets = []
        cursor = None
        page   = 0
        while True:
            page += 1
            path = "/markets?limit=100"
            if cursor:
                path += f"&cursor={cursor}"
            data = self._get(path)
            if not data:
                break
            batch  = data.get("markets", [])
            all_markets.extend(batch)
            cursor = data.get("cursor")
            if not cursor or page >= 20:
                break
        print("TOTAL MARKETS FETCHED:", len(all_markets))
        return all_markets

    def get_orderbook(self, ticker: str):
        data = self._get(f"/markets/{ticker}/orderbook")
        if not data:
            return None
        ob = data.get("orderbook")
        if not ob:
            return None
        def parse_side(side):
            if not side:
                return []
            return [[float(e[0]), float(e[1])] for e in side]
        return {
            "yes": parse_side(ob.get("yes_dollars_fp", [])),
            "no":  parse_side(ob.get("no_dollars_fp",  [])),
        }

    def place_order(self, ticker: str, side: str, price_cents: int, count: int):
        payload = {
            "ticker":    ticker,
            "side":      side,
            "type":      "limit",
            "yes_price": price_cents if side == "yes" else 100 - price_cents,
            "count":     count,
            "action":    "buy",
            "time_in_force": "fill_or_kill",
        }
        return self._post("/portfolio/orders", payload)
