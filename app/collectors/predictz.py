from app.collectors.base import BaseCollector
from app.models.schemas import SourcePick


class PredictZCollector(BaseCollector):
    name = "PredictZ"
    base_url = "https://www.predictz.com/"

    async def fetch_picks(self) -> list[SourcePick]:
        picks: list[SourcePick] = []
        try:
            soup = await self.get_html(self.base_url)
            rows = soup.select("table.ptable tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 5:
                    continue
                home = cols[1].get_text(strip=True)
                away = cols[3].get_text(strip=True)
                pred_raw = cols[4].get_text(strip=True).upper()
                market, pick = self._map_prediction(pred_raw)
                if not home or not away or not pick:
                    continue
                picks.append(SourcePick(
                    source_name=self.name,
                    source_url=self.base_url,
                    market=market,
                    pick=pick,
                    reason_summary=f"PredictZ prediction for {home} vs {away}: {pred_raw}"
                ))
        except Exception as exc:
            picks.append(SourcePick(
                source_name=self.name,
                source_url=self.base_url,
                market="unknown",
                pick="error",
                reason_summary=f"Collector error: {exc}"
            ))
        return picks

    def _map_prediction(self, raw: str) -> tuple[str, str]:
        mapping = {
            "1": ("1X2", "1"),
            "X": ("1X2", "X"),
            "2": ("1X2", "2"),
            "1X": ("Double Chance", "1X"),
            "X2": ("Double Chance", "X2"),
            "12": ("Double Chance", "12"),
            "O2.5": ("Over/Under 2.5", "Over 2.5"),
            "U2.5": ("Over/Under 2.5", "Under 2.5"),
            "BTTS": ("BTTS", "Yes"),
            "BTTS YES": ("BTTS", "Yes"),
            "BTTS NO": ("BTTS", "No"),
        }
        for key, val in mapping.items():
            if key in raw:
                return val
        return ("1X2", raw)
