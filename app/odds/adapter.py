import httpx
import os

# Keyword -> The Odds API sport key, checked in order (most specific first)
# against the lowercased competition string. Our collectors produce wildly
# different competition naming ("UEFA Champions League" vs "INTERNATIONAL -
# CHAMPIONS LEAGUE PLAYOFF ROUND" vs a bare country name), so this matches
# on keywords rather than exact strings. Anything that doesn't match one of
# these stays unmapped -> no live-odds call, quoted-odds fallback only.
_KEYWORD_SPORT_KEYS = [
    ("champions league", "soccer_uefa_champs_league"),
    ("europa conference", "soccer_uefa_europa_conference_league"),
    ("conference league", "soccer_uefa_europa_conference_league"),
    ("europa league", "soccer_uefa_europa_league"),
    ("premier league", "soccer_epl"),
    ("la liga", "soccer_spain_la_liga"),
    ("bundesliga", "soccer_germany_bundesliga"),
    ("ligue 1", "soccer_france_ligue_one"),
    ("eredivisie", "soccer_netherlands_eredivisie"),
    ("primeira liga", "soccer_portugal_primeira_liga"),
]


def _sport_key_for(competition: str | None) -> str | None:
    if not competition:
        return None
    lowered = competition.lower()
    if "greece" in lowered and "super league" in lowered:
        return "soccer_greece_super_league"
    if "serie a" in lowered and "brazil" not in lowered:
        return "soccer_italy_serie_a"
    for keyword, sport_key in _KEYWORD_SPORT_KEYS:
        if keyword in lowered:
            return sport_key
    return None


class OddsAdapter:
    """
    Wraps The Odds API (free tier: 500 requests/month).
    Set ODDS_API_KEY env variable. Falls back gracefully if missing.
    """
    BASE_URL = "https://api.the-odds-api.com/v4"

    def __init__(self) -> None:
        self.api_key = os.getenv("ODDS_API_KEY", "")

    async def get_best_odds(
        self, home: str, away: str, market: str, competition: str | None = None
    ) -> float | None:
        if not self.api_key:
            return None
        sport_key = _sport_key_for(competition)
        if sport_key is None:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                url = f"{self.BASE_URL}/sports/{sport_key}/odds/"
                params = {
                    "apiKey": self.api_key,
                    "regions": "eu",
                    "markets": self._map_market(market),
                    "oddsFormat": "decimal"
                }
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    return None
                events = resp.json()
                for event in events:
                    if self._teams_match(event, home, away):
                        return self._extract_best_price(event, market)
        except Exception:
            return None
        return None

    def _map_market(self, market: str) -> str:
        mapping = {
            "1X2": "h2h",
            "Over/Under 2.5": "totals",
            "Over/Under 1.5": "totals",
        }
        return mapping.get(market, "h2h")

    def _teams_match(self, event: dict, home: str, away: str) -> bool:
        h = event.get("home_team", "").lower()
        a = event.get("away_team", "").lower()
        return home.lower() in h or away.lower() in a

    def _extract_best_price(self, event: dict, market: str) -> float | None:
        best = 1.0
        for bm in event.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                for outcome in mkt.get("outcomes", []):
                    try:
                        p = float(outcome["price"])
                        if p > best:
                            best = p
                    except (KeyError, ValueError):
                        pass
        return best if best > 1.0 else None
