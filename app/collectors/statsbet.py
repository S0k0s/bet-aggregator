from app.collectors.base import BaseCollector
from app.models.schemas import SourcePick


class StatsBetCollector(BaseCollector):
    name = "StatsBet"
    base_url = "https://statsbet.org/predictions/"

    async def fetch_picks(self) -> tuple[list[SourcePick], str | None]:
        picks: list[SourcePick] = []
        try:
            soup = await self.get_html(self.base_url)
            rows = soup.select("tr.prediction-row, div.prediction-card")
            for row in rows:
                home_el = row.select_one(".home, .home-team")
                away_el = row.select_one(".away, .away-team")
                market_el = row.select_one(".market, .market-name")
                pick_el = row.select_one(".prediction, .pick, .tip")
                odds_el = row.select_one(".odds, .best-odds")
                home = home_el.get_text(strip=True) if home_el else ""
                away = away_el.get_text(strip=True) if away_el else ""
                market = market_el.get_text(strip=True) if market_el else "1X2"
                pick_text = pick_el.get_text(strip=True) if pick_el else ""
                if not pick_text or not home or not away:
                    continue
                try:
                    odds = float(odds_el.get_text(strip=True)) if odds_el else None
                except ValueError:
                    odds = None
                picks.append(SourcePick(
                    source_name=self.name,
                    source_url=self.base_url,
                    home_team=home,
                    away_team=away,
                    market=market,
                    pick=pick_text,
                    quoted_odds=odds,
                    reason_summary=f"StatsBet prediction: {home} vs {away} — {market} → {pick_text}"
                ))
        except Exception as exc:
            return [], str(exc)
        return picks, None
