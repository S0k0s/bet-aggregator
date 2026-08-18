from __future__ import annotations
from app.collectors.base import BaseCollector
from app.collectors.common import TIP_CODE_MAP
from app.models.schemas import SourcePick


class MyBetsTodayCollector(BaseCollector):
    """mybets.today: schema.org-annotated markup (SportsEvent microdata),
    grouped per league under div.listgames -> div.event-fixtures."""

    name = "MyBetsToday"
    base_url = "https://www.mybets.today/predictions"

    async def fetch_picks(self) -> tuple[list[SourcePick], str | None]:
        picks: list[SourcePick] = []
        try:
            soup = await self.get_html(self.base_url)
            container = soup.select_one("div.listgames")
            if container is None:
                return [], "Could not find div.listgames container"
            competition = None
            for child in container.find_all("div", recursive=False):
                classes = child.get("class") or []
                if "titlegames" in classes:
                    league_el = child.select_one(".leaguename")
                    if league_el:
                        competition = league_el.get_text(strip=True)
                    continue
                if "event-fixtures" not in classes:
                    continue
                fixture = child
                home_el = fixture.select_one(".homeTeam")
                away_el = fixture.select_one(".awayTeam")
                home = home_el.get_text(strip=True) if home_el else ""
                away = away_el.get_text(strip=True) if away_el else ""
                if not home or not away:
                    continue
                tip_el = fixture.select_one(".tipdiv")
                tip_text = (tip_el.get_text(strip=True) if tip_el else "").upper()
                market, pick = TIP_CODE_MAP.get(tip_text, ("unknown", ""))
                if not pick:
                    continue
                time_el = fixture.select_one("time[datetime]")
                kickoff = time_el.get("datetime") if time_el else None
                link = fixture.select_one("a.linkgames")
                source_url = link.get("href") if link and link.get("href") else self.base_url
                picks.append(SourcePick(
                    source_name=self.name,
                    source_url=source_url,
                    home_team=home,
                    away_team=away,
                    market=market,
                    pick=pick,
                    competition=competition,
                    kickoff=kickoff,
                    reason_summary=f"MyBets Today tip for {home} vs {away}: {market} {pick}.",
                ))
        except Exception as exc:
            return [], str(exc)
        return picks, None
