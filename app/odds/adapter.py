import httpx
import os

# Keyword -> The Odds API sport key, checked against the lowercased
# competition string. Our collectors produce wildly different competition
# naming ("UEFA Champions League" vs "INTERNATIONAL - CHAMPIONS LEAGUE
# PLAYOFF ROUND" vs a bare country name), so this matches on keywords
# rather than exact strings. Anything that doesn't match one of these stays
# unmapped -> no live-odds call, quoted-odds fallback only.
#
# Generic league-type names ("Premier League", "Serie A", ...) are reused by
# many countries' domestic top flights (confirmed live: Kyrgyzstan and
# Bhutan both call theirs "Premier League", Ecuador's is "Serie A"), so
# these require the specific country keyword too - a bare "premier league"
# with no recognizable country is left unmapped rather than guessed as
# England's.
_CONTINENT_WIDE_KEYWORDS = [
    ("champions league", "soccer_uefa_champs_league"),
    ("europa conference", "soccer_uefa_europa_conference_league"),
    ("conference league", "soccer_uefa_europa_conference_league"),
    ("europa league", "soccer_uefa_europa_league"),
]

# (league keyword, required country keywords, sport key)
_COUNTRY_LEAGUE_KEYS = [
    ("premier league", ("england", "english"), "soccer_epl"),
    ("la liga", ("spain", "spanish"), "soccer_spain_la_liga"),
    ("serie a", ("italy", "italian"), "soccer_italy_serie_a"),
    ("bundesliga", ("germany", "german"), "soccer_germany_bundesliga"),
    ("ligue 1", ("france", "french"), "soccer_france_ligue_one"),
    ("super league", ("greece", "greek"), "soccer_greece_super_league"),
]

# Unique enough globally that no country check is needed.
_UNAMBIGUOUS_KEYWORDS = [
    ("eredivisie", "soccer_netherlands_eredivisie"),
    ("primeira liga", "soccer_portugal_primeira_liga"),
]


def _sport_key_for(competition: str | None) -> str | None:
    if not competition:
        return None
    lowered = competition.lower()
    for keyword, sport_key in _CONTINENT_WIDE_KEYWORDS:
        if keyword in lowered:
            return sport_key
    for league_keyword, country_keywords, sport_key in _COUNTRY_LEAGUE_KEYS:
        if league_keyword in lowered and any(c in lowered for c in country_keywords):
            return sport_key
    for keyword, sport_key in _UNAMBIGUOUS_KEYWORDS:
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
                    print(f"[OddsAdapter] {sport_key} -> HTTP {resp.status_code}: {resp.text[:200]}")
                    return None
                events = resp.json()
                for event in events:
                    if self._teams_match(event, home, away):
                        price = self._extract_best_price(event, market)
                        print(f"[OddsAdapter] {sport_key} {home} vs {away}: matched, price={price}")
                        return price
                print(f"[OddsAdapter] {sport_key} {home} vs {away}: no event match ({len(events)} events)")
        except Exception as exc:
            print(f"[OddsAdapter] {sport_key} {home} vs {away}: exception {exc!r}")
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
