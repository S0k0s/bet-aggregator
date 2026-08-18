from __future__ import annotations
from app.collectors.base import BaseCollector
from app.collectors.common import TIP_CODE_MAP
from app.models.schemas import SourcePick
from app.ranking.engine import _normalize_team


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
                    market, pick = TIP_CODE_MAP.get(
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

    async def fetch_match_odds(self, detail_url: str) -> dict[str, float] | None:
        """Real decimal 1X2 odds from a match-detail page (the same
        `source_url` fetch_picks() already puts on every Vitibet pick).
        Returns {"home": x, "draw": x, "away": x} or None if the page
        doesn't have an odds box (e.g. "No predictions available")."""
        try:
            soup = await self.get_html(detail_url)
            heading = soup.find(string=lambda s: s and "Odds" in s and "1X2" in s)
            if not heading:
                return None
            h3 = heading.find_parent("h3")
            card = h3.find_next_sibling("div", class_="match-card") if h3 else None
            row = card.find("div") if card else None
            boxes = row.find_all("div", recursive=False) if row else []
            result: dict[str, float] = {}
            for box in boxes:
                divs = box.find_all("div", recursive=False)
                if len(divs) != 2:
                    continue
                label = divs[0].get_text(strip=True).lower()
                try:
                    result[label] = float(divs[1].get_text(strip=True))
                except ValueError:
                    continue
            return result if {"home", "draw", "away"} <= set(result) else None
        except Exception:
            return None

    async def fetch_results(self, date: str) -> dict[str, tuple[int, int]]:
        """Final scores for finished matches on `date` (YYYY-MM-DD).

        Vitibet's own livescore page — the same one fetch_picks() reads —
        accepts a date query param and shows FT scores for past dates, so
        result-checking needs no new source. Keyed by the same fixture key
        used for cross-source consensus grouping in app.ranking.engine.
        """
        results: dict[str, tuple[int, int]] = {}
        url = f"{self.base_url}&date={date}"
        soup = await self.get_html(url)
        for row in soup.select("a.livescore-match-row"):
            if row.get("data-status") != "finished":
                continue
            teams = row.select(".livescore-team-name")
            if len(teams) < 2:
                continue
            home = teams[0].get_text(strip=True)
            away = teams[1].get_text(strip=True)
            score_el = row.select_one(".livescore-match-actual-col .actual-score-row")
            if not score_el:
                continue
            score_text = score_el.get_text(strip=True)
            parts = score_text.split("-")
            if len(parts) != 2:
                continue
            try:
                home_goals, away_goals = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            key = f"{_normalize_team(home)}|{_normalize_team(away)}"
            results[key] = (home_goals, away_goals)
        return results
