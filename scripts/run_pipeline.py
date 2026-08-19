"""Run all collectors + the ranking engine and write static JSON for GitHub Pages.

Replaces the old FastAPI /ranked-matches route: this script is meant to be
run by a manually-triggered GitHub Actions workflow, which commits the
resulting docs/data/*.json into the repo for the static dashboard to fetch.
"""
from __future__ import annotations
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.collectors.predictz import PredictZCollector
from app.collectors.freesupertips import FreeSuperTipsCollector
from app.collectors.statsbet import StatsBetCollector
from app.collectors.vitibet import VitibetCollector
from app.collectors.adibet import AdibetCollector
from app.collectors.mybets_today import MyBetsTodayCollector
from app.collectors.statarea import StatareaCollector
from app.models.schemas import SourcePick
from app.ranking.engine import build_ranked_matches
from app.history.store import load_history, save_history, history_key, load_reliability

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"


async def main() -> None:
    collectors = [
        PredictZCollector(), FreeSuperTipsCollector(), StatsBetCollector(), VitibetCollector(),
        AdibetCollector(), MyBetsTodayCollector(), StatareaCollector(),
    ]
    all_picks: list[SourcePick] = []
    source_status: list[dict] = []

    for collector in collectors:
        picks, error = await collector.fetch_picks()
        all_picks.extend(picks)
        source_status.append({
            "name": collector.name,
            "pick_count": len(picks),
            "error": error,
        })
        print(f"[{collector.name}] {len(picks)} picks" + (f" — error: {error}" if error else ""))

    # Some sources (e.g. Statarea) give a bare "HH:MM" with no date, so a
    # match that already finished on a previous day can still get today's
    # date stamped on it by the collector and slip past the kickoff-based
    # stale filter. Cross-check against Vitibet's own results feed (today +
    # yesterday) to catch those regardless of which source reported them.
    finished_fixture_keys: set[str] = set()
    vitibet_results_source = VitibetCollector()
    today = datetime.now(timezone.utc).date()
    for days_back in (0, 1):
        date_str = (today - timedelta(days=days_back)).isoformat()
        try:
            results = await vitibet_results_source.fetch_results(date_str)
            finished_fixture_keys.update(results.keys())
        except Exception as exc:
            print(f"[finished-results] {date_str} lookup failed: {exc}")

    reliability = load_reliability(OUTPUT_DIR / "source-reliability.json")
    ranked_by_continent = await build_ranked_matches(
        all_picks, reliability_overrides=reliability, finished_fixture_keys=finished_fixture_keys,
    )

    # Flatten cards for counts, deduped by match_id since a card can
    # appear in both a continent's "all" list and its specific league list.
    seen_ids: set[str] = set()
    cards: list = []
    for data in ranked_by_continent.values():
        for c in data["all"]:
            if c.match_id not in seen_ids:
                seen_ids.add(c.match_id)
                cards.append(c)
        for league_cards in data["leagues"].values():
            for c in league_cards:
                if c.match_id not in seen_ids:
                    seen_ids.add(c.match_id)
                    cards.append(c)

    # Flatten every individual pick across all cards for history tracking,
    # deduped by (match_id, market, recommended_pick) since one card can
    # carry several picks for the same fixture.
    seen_pick_keys: set[tuple] = set()
    ranked: list = []
    for c in cards:
        for p in c.picks:
            pick_key = (p.match_id, p.market, p.recommended_pick)
            if pick_key not in seen_pick_keys:
                seen_pick_keys.add(pick_key)
                ranked.append(p)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ranked_path = OUTPUT_DIR / "ranked-matches.json"
    ranked_path.write_text(
        json.dumps(
            {
                continent: {
                    "all": [m.model_dump() for m in data["all"]],
                    "leagues": {name: [m.model_dump() for m in ms] for name, ms in data["leagues"].items()},
                }
                for continent, data in ranked_by_continent.items()
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    meta_path = OUTPUT_DIR / "meta.json"
    meta_path.write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": source_status,
            "total_raw_picks": len(all_picks),
            "ranked_count": len(ranked),
            "match_count": len(cards),
            "ranked_by_continent": {c: len(d["all"]) for c, d in ranked_by_continent.items()},
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {len(cards)} match cards ({len(ranked)} picks) across continents to {ranked_path}")

    history_path = OUTPUT_DIR / "history.json"
    history = load_history(history_path)
    history_by_key = {entry["history_key"]: entry for entry in history}
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0
    for m in ranked:
        key = history_key(m.home_team, m.away_team, m.market, m.recommended_pick, m.kickoff)
        source_names = sorted({s.source_name for s in m.sources})
        existing = history_by_key.get(key)
        if existing is None:
            entry = {
                "history_key": key,
                "match_id": m.match_id,
                "home_team": m.home_team,
                "away_team": m.away_team,
                "competition": m.competition,
                "market": m.market,
                "recommended_pick": m.recommended_pick,
                "predicted_at": now,
                "kickoff": m.kickoff,
                "best_odds": m.best_odds,
                "source_count": m.source_count,
                "consensus_score": m.consensus_score,
                "sources": source_names,
                "final_score": None,
                "outcome": "pending",
                "graded_at": None,
            }
            history.append(entry)
            history_by_key[key] = entry
            new_count += 1
        elif existing.get("outcome") == "pending":
            # Still pending: refresh display fields, never touch outcome.
            existing["best_odds"] = m.best_odds
            existing["source_count"] = m.source_count
            existing["consensus_score"] = m.consensus_score
            existing["kickoff"] = m.kickoff
            existing["sources"] = source_names

    save_history(history_path, history)
    print(f"History: {new_count} new, {len(history)} total")


if __name__ == "__main__":
    asyncio.run(main())
