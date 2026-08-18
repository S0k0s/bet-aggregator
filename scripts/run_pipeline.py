"""Run all collectors + the ranking engine and write static JSON for GitHub Pages.

Replaces the old FastAPI /ranked-matches route: this script is meant to be
run by a manually-triggered GitHub Actions workflow, which commits the
resulting docs/data/*.json into the repo for the static dashboard to fetch.
"""
from __future__ import annotations
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.collectors.predictz import PredictZCollector
from app.collectors.freesupertips import FreeSuperTipsCollector
from app.collectors.statsbet import StatsBetCollector
from app.collectors.vitibet import VitibetCollector
from app.models.schemas import SourcePick
from app.ranking.engine import build_ranked_matches

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"


async def main() -> None:
    collectors = [PredictZCollector(), FreeSuperTipsCollector(), StatsBetCollector(), VitibetCollector()]
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

    ranked = await build_ranked_matches(all_picks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ranked_path = OUTPUT_DIR / "ranked-matches.json"
    ranked_path.write_text(
        json.dumps([m.model_dump() for m in ranked], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    meta_path = OUTPUT_DIR / "meta.json"
    meta_path.write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": source_status,
            "total_raw_picks": len(all_picks),
            "ranked_count": len(ranked),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {len(ranked)} ranked matches to {ranked_path}")


if __name__ == "__main__":
    asyncio.run(main())
