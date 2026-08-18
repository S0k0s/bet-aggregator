from __future__ import annotations
from datetime import datetime, timezone
from app.collectors.base import BaseCollector
from app.collectors.common import TIP_CODE_MAP
from app.models.schemas import SourcePick


class StatareaCollector(BaseCollector):
    """statarea.com: semantic markup (.competition > .header + .body >
    .cmatch). The recommended tip is the lone div under .tip .value
    (class name varies by confidence tier - type1..type4), using the same
    short codes as Vitibet (1/X/2/1X/X2/12).

    The page gives each match's kickoff as a bare "HH:MM" with no date or
    timezone, so kickoff here is today's date (collection time) + that
    time, unlabeled timezone — an approximation, not exact scheduling.
    """

    name = "Statarea"
    base_url = "https://www.statarea.com/en/predictions"

    async def fetch_picks(self) -> tuple[list[SourcePick], str | None]:
        picks: list[SourcePick] = []
        try:
            soup = await self.get_html(self.base_url)
            today = datetime.now(timezone.utc).date().isoformat()
            for competition_div in soup.select("div.competition"):
                competition = self._competition_name(competition_div)
                for cmatch in competition_div.select("div.cmatch"):
                    teams = cmatch.select_one(".teams")
                    links = teams.find_all("a") if teams else []
                    if len(links) < 2:
                        continue
                    home = links[0].get_text(strip=True)
                    away = links[1].get_text(strip=True)
                    if not home or not away:
                        continue
                    tip_el = cmatch.select_one(".tip .value div")
                    tip_text = (tip_el.get_text(strip=True) if tip_el else "").upper()
                    market, pick = TIP_CODE_MAP.get(tip_text, ("unknown", ""))
                    if not pick:
                        continue
                    time_el = cmatch.select_one(".time")
                    time_text = time_el.get_text(strip=True) if time_el else None
                    kickoff = f"{today}T{time_text}:00" if time_text and ":" in time_text else None
                    picks.append(SourcePick(
                        source_name=self.name,
                        source_url=self.base_url,
                        home_team=home,
                        away_team=away,
                        market=market,
                        pick=pick,
                        competition=competition,
                        kickoff=kickoff,
                        reason_summary=f"Statarea tip for {home} vs {away}: {market} {pick}.",
                    ))
        except Exception as exc:
            return [], str(exc)
        return picks, None

    def _competition_name(self, competition_div) -> str | None:
        header = competition_div.select_one(".header")
        if not header:
            return None
        text = header.get_text(" ", strip=True)
        marker = "your prediction"
        idx = text.lower().find(marker)
        if idx == -1:
            return text or None
        return text[idx + len(marker):].strip() or None
