from __future__ import annotations
import json
from app.collectors.base import BaseCollector
from app.models.schemas import SourcePick

# FreeSuperTips is a Next.js app that embeds its data as structured JSON in a
# <script id="__NEXT_DATA__"> tag, so we read that directly instead of
# guessing at CSS selectors against rendered markup.
_MARKET_MAP = {
    "full time result": "1X2",
}


class FreeSuperTipsCollector(BaseCollector):
    name = "FreeSuperTips"
    base_url = "https://www.freesupertips.com/predictions/"

    async def fetch_picks(self) -> tuple[list[SourcePick], str | None]:
        picks: list[SourcePick] = []
        try:
            soup = await self.get_html(self.base_url)
            script = soup.find("script", id="__NEXT_DATA__")
            if script is None or not script.string:
                return [], "Could not find __NEXT_DATA__ script on page"
            data = json.loads(script.string)
            day_groups = data["props"]["pageProps"]["responses"].get("predictions") or []
            for day in day_groups:
                for competition in day.get("competitions", []):
                    comp_name = competition.get("name") or "European"
                    for match in competition.get("predictions", []):
                        home, away = self._teams(match)
                        if not home or not away:
                            continue
                        kickoff = match.get("startString") or "TBD"
                        source_url = self._absolute_url(match.get("url"))
                        for tip in match.get("tips", []):
                            market, pick = self._parse_tip(tip, home, away)
                            if not pick:
                                continue
                            picks.append(SourcePick(
                                source_name=self.name,
                                source_url=source_url,
                                home_team=home,
                                away_team=away,
                                market=market,
                                pick=pick,
                                quoted_odds=tip.get("odds"),
                                confidence_text=tip.get("confidence"),
                                competition=comp_name,
                                kickoff=kickoff,
                                reason_summary=f"FreeSuperTips {tip.get('title', 'tip')} for {home} vs {away} ({comp_name}, {kickoff}).",
                            ))
        except Exception as exc:
            return [], str(exc)
        return picks, None

    def _teams(self, match: dict) -> tuple[str, str]:
        home = away = ""
        for team in match.get("teams", []):
            if team.get("homeAway") == "home":
                home = team.get("name", "")
            elif team.get("homeAway") == "away":
                away = team.get("name", "")
        return home, away

    def _parse_tip(self, tip: dict, home: str, away: str) -> tuple[str, str]:
        title = (tip.get("title") or "").strip()
        text_one = (tip.get("textOne") or "").strip()
        market = _MARKET_MAP.get(title.lower(), title or "unknown")
        if market == "1X2":
            lowered = text_one.lower()
            if lowered == f"{home.lower()} to win":
                return market, "1"
            if lowered == f"{away.lower()} to win":
                return market, "2"
            if "draw" in lowered:
                return market, "X"
        # Other markets (Correct Score, Total Goals, Draw No Bet, Goal
        # Scorer, ...) are passed through as free text — normalizing every
        # market phrasing into a shared code is future work, not attempted
        # here to avoid guessing wrong.
        return market, text_one

    def _absolute_url(self, path: str | None) -> str:
        if not path:
            return self.base_url
        if path.startswith("http"):
            return path
        return f"https://www.freesupertips.com{path}"
