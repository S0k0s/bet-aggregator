from app.collectors.base import BaseCollector
from app.models.schemas import SourcePick


class FreeSuperTipsCollector(BaseCollector):
    name = "FreeSuperTips"
    base_url = "https://www.freesupertips.com/football-tips/"

    async def fetch_picks(self) -> tuple[list[SourcePick], str | None]:
        picks: list[SourcePick] = []
        try:
            soup = await self.get_html(self.base_url)
            cards = soup.select("div.tip-card, article.tip, div.tipster-tip")
            for card in cards:
                home_el = card.select_one(".home-team, .team-home, span.team:first-child")
                away_el = card.select_one(".away-team, .team-away, span.team:last-child")
                pick_el = card.select_one(".tip-prediction, .prediction, .pick")
                odds_el = card.select_one(".tip-odds, .odds")
                home = home_el.get_text(strip=True) if home_el else ""
                away = away_el.get_text(strip=True) if away_el else ""
                pick_text = pick_el.get_text(strip=True) if pick_el else ""
                odds_text = odds_el.get_text(strip=True) if odds_el else None
                if not pick_text or not home or not away:
                    continue
                try:
                    quoted_odds = float(odds_text) if odds_text else None
                except ValueError:
                    quoted_odds = None
                picks.append(SourcePick(
                    source_name=self.name,
                    source_url=self.base_url,
                    home_team=home,
                    away_team=away,
                    market="1X2",
                    pick=pick_text,
                    quoted_odds=quoted_odds,
                    reason_summary=f"FreeSuperTips tip for {home} vs {away}."
                ))
        except Exception as exc:
            return [], str(exc)
        return picks, None
