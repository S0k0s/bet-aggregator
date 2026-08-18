"""Grade pending history entries against real final scores.

Meant to run once a day via GitHub Actions. Reuses the Vitibet collector's
own livescore page (date-addressable, shows FT scores for past dates) as
the results source — see app/collectors/vitibet.py:fetch_results and the
plan notes on why flashscore was rejected (ToS enforcement risk) in favor
of a source we already compliantly scrape.
"""
from __future__ import annotations
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.collectors.vitibet import VitibetCollector
from app.history.grader import grade_pick
from app.history.store import load_history, save_history, kickoff_date
from app.ranking.engine import _normalize_team

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
GRACE_HOURS = 3  # long enough for a match to finish
STALE_DAYS = 7  # give up and mark "unknown" past this


def _fixture_key(home: str, away: str) -> str:
    return f"{_normalize_team(home)}|{_normalize_team(away)}"


async def main() -> None:
    history_path = OUTPUT_DIR / "history.json"
    history = load_history(history_path)

    now = datetime.now(timezone.utc)
    pending_by_date: dict[str, list[dict]] = {}
    stale = 0

    for entry in history:
        if entry.get("outcome") != "pending":
            continue
        date = kickoff_date(entry.get("kickoff"))
        if not date:
            continue
        kickoff_dt = datetime.fromisoformat(
            entry["kickoff"] if "T" in entry["kickoff"] else entry["kickoff"].replace(" ", "T", 1)
        )
        if kickoff_dt.tzinfo is None:
            kickoff_dt = kickoff_dt.replace(tzinfo=timezone.utc)
        if now - kickoff_dt < timedelta(hours=GRACE_HOURS):
            continue
        if now - kickoff_dt > timedelta(days=STALE_DAYS):
            entry["outcome"] = "unknown"
            entry["graded_at"] = now.isoformat()
            stale += 1
            continue
        pending_by_date.setdefault(date, []).append(entry)

    collector = VitibetCollector()
    graded = 0
    for date, entries in pending_by_date.items():
        results = await collector.fetch_results(date)
        print(f"[{date}] {len(results)} finished matches, {len(entries)} pending picks to check")
        for entry in entries:
            key = _fixture_key(entry["home_team"], entry["away_team"])
            score = results.get(key)
            if score is None:
                continue
            home_goals, away_goals = score
            outcome = grade_pick(
                entry["market"], entry["recommended_pick"],
                entry["home_team"], entry["away_team"],
                home_goals, away_goals,
            )
            entry["final_score"] = f"{home_goals}-{away_goals}"
            entry["outcome"] = outcome
            entry["graded_at"] = now.isoformat()
            graded += 1

    save_history(history_path, history)
    print(f"Graded {graded} entries, {stale} marked unknown (stale), {len(history)} total in history")

    summary = _build_summary(history)
    summary_path = OUTPUT_DIR / "history-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote summary: {summary}")


def _build_summary(history: list[dict]) -> dict:
    counts = {"hit": 0, "miss": 0, "push": 0, "unknown": 0, "pending": 0}
    by_market: dict[str, dict[str, int]] = {}
    for entry in history:
        outcome = entry.get("outcome", "pending")
        counts[outcome] = counts.get(outcome, 0) + 1
        market = entry.get("market", "unknown")
        by_market.setdefault(market, {"hit": 0, "miss": 0, "push": 0, "unknown": 0, "pending": 0})
        by_market[market][outcome] = by_market[market].get(outcome, 0) + 1

    graded_for_rate = counts["hit"] + counts["miss"]
    hit_rate = round(counts["hit"] / graded_for_rate, 3) if graded_for_rate else None

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(history),
        "counts": counts,
        "hit_rate": hit_rate,
        "by_market": by_market,
    }


if __name__ == "__main__":
    asyncio.run(main())
