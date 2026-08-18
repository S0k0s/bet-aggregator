from __future__ import annotations
import re
from app.collectors.base import BaseCollector
from app.collectors.common import TIP_CODE_MAP
from app.models.schemas import SourcePick

_DATE_RE = re.compile(r"(\d{1,2})\s*-\s*(\d{2})\s*-\s*(\d{4})")
_MARKET_COLUMNS = ["1", "X", "2", "+1.5", "GG", "+2.5"]
_HIGHLIGHT_BGCOLOR = "#252525"


class AdibetCollector(BaseCollector):
    """adibet.com: old-style nested-table markup with no CSS classes, so
    picks are identified positionally — 6 fixed market columns per match
    row (1, X, 2, +1.5, GG, +2.5), and the recommended one(s) are the
    cell(s) with a distinct highlight bgcolor.

    The page gives a date per day-section but no per-match kickoff time,
    so kickoff is a midday-UTC placeholder on the right date — enough for
    day-bucketed result checking, not for exact scheduling.
    """

    name = "Adibet"
    base_url = "https://www.adibet.com/"

    async def fetch_picks(self) -> tuple[list[SourcePick], str | None]:
        picks: list[SourcePick] = []
        try:
            soup = await self.get_html(self.base_url)
            table = soup.find("table")
            if table is None:
                return [], "Could not find predictions table"
            current_date = None
            for row in table.find_all("tr"):
                tds = row.find_all("td", recursive=False)
                if len(tds) != 8:
                    date_match = _DATE_RE.search(row.get_text())
                    if date_match:
                        day, month, year = date_match.groups()
                        current_date = f"{year}-{month}-{day.zfill(2)}"
                    continue
                teams_text = tds[1].get_text(" ", strip=True)
                if " - " not in teams_text:
                    continue
                home, away = (t.strip() for t in teams_text.split(" - ", 1))
                if not home or not away:
                    continue
                flag = tds[0].find("img")
                competition = flag.get("alt") if flag else None
                kickoff = f"{current_date}T12:00:00+00:00" if current_date else None
                highlighted = [
                    _MARKET_COLUMNS[i] for i, td in enumerate(tds[2:8])
                    if td.get("bgcolor") == _HIGHLIGHT_BGCOLOR
                ]
                for market, pick in self._picks_from_highlights(highlighted):
                    picks.append(SourcePick(
                        source_name=self.name,
                        source_url=self.base_url,
                        home_team=home,
                        away_team=away,
                        market=market,
                        pick=pick,
                        competition=competition,
                        kickoff=kickoff,
                        reason_summary=f"Adibet tip for {home} vs {away}: {market} {pick}.",
                    ))
        except Exception as exc:
            return [], str(exc)
        return picks, None

    def _picks_from_highlights(self, highlighted: list[str]) -> list[tuple[str, str]]:
        results: list[tuple[str, str]] = []
        result_codes = [h for h in highlighted if h in ("1", "X", "2")]
        if len(result_codes) in (1, 2):
            combo = "".join(result_codes)
            if combo in TIP_CODE_MAP:
                results.append(TIP_CODE_MAP[combo])
        if "GG" in highlighted:
            results.append(("BTTS", "Yes"))
        for goal_column in ("+1.5", "+2.5"):
            if goal_column in highlighted:
                results.append(("Total Goals", f"Over {goal_column[1:]}"))
        return results
