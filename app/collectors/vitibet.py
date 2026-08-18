from __future__ import annotations
from app.collectors.base import BaseCollector
from app.models.schemas import SourcePick

_TIP_MAP = {
    "1": ("1X2", "1"),
    "X": ("1X2", "X"),
    "2": ("1X2", "2"),
    "1X": ("Double Chance", "1X"),
    "X2": ("Double Chance", "X2"),
    "12": ("Double Chance", "12"),
}


class VitibetCollector(BaseCollector):
    name = "Vitibet"
    base_url = "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en"

    async def fetch_picks(self) -> tuple[list[SourcePick], str | None]:
        picks: list[SourcePick] = []
        try:
            soup = await self.get_html(self.base_url)
            for league in soup.select("div.livescore-league"):
                title_el = league.select_one(".league-title")
                competition = title_el.get_text(strip=True) if title_el else None
                for row in league.select("a.livescore-match-row"):
                    teams = row.select(".livescore-team-name")
                    if len(teams) < 2:
                        continue
                    home = teams[0].get_text(strip=True)
                    away = teams[1].get_text(strip=True)
                    if not home or not away:
                        continue
                    tip_el = row.select_one(".tip-indicator-circle")
                    if not tip_el:
                        continue
                    market, pick = _TIP_MAP.get(
                        tip_el.get_text(strip=True).upper(), ("unknown", "")
                    )
                    if not pick:
                        continue
                    time_el = row.select_one(".local-time")
                    kickoff = time_el.get("data-time") if time_el else None
                    score_el = row.select_one(".livescore-score-combined")
                    predicted_score = score_el.get_text(strip=True) if score_el else "?"
                    href = row.get("href", "")
                    source_url = f"https://www.vitibet.com{href}" if href.startswith("/") else (href or self.base_url)
                    picks.append(SourcePick(
                        source_name=self.name,
                        source_url=source_url,
                        home_team=home,
                        away_team=away,
                        market=market,
                        pick=pick,
                        competition=competition,
                        kickoff=kickoff,
                        reason_summary=f"Vitibet statistical model for {home} vs {away}: predicted score {predicted_score}, tip {pick}.",
                    ))
        except Exception as exc:
            return [], str(exc)
        return picks, None
