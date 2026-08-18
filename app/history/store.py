from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from app.ranking.engine import _normalize_team


def kickoff_date(kickoff: str | None) -> str | None:
    """YYYY-MM-DD from a kickoff timestamp, in whichever of the two formats
    our collectors produce (ISO with 'T', or FreeSuperTips' 'YYYY-MM-DD
    HH:MM:SS'). None if missing/unparseable ("TBD" included)."""
    if not kickoff or kickoff == "TBD":
        return None
    try:
        iso = kickoff if "T" in kickoff else kickoff.replace(" ", "T", 1)
        return datetime.fromisoformat(iso).date().isoformat()
    except ValueError:
        return None


def history_key(home_team: str, away_team: str, market: str, pick: str, kickoff: str | None) -> str:
    """Stable id for one (fixture, market, pick, day) combo, used to upsert
    across repeated pipeline runs before kickoff without duplicating, and to
    avoid collisions if the same two teams meet again on a different date."""
    fixture = f"{_normalize_team(home_team)}|{_normalize_team(away_team)}"
    date_part = kickoff_date(kickoff) or "unknown-date"
    return f"{fixture}|{market}|{pick}|{date_part}"


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_history(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
