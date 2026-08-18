from __future__ import annotations
import re
from app.ranking.engine import _normalize_team

_OVER_UNDER_RE = re.compile(r"\b(over|under)\b\D{0,10}?(\d+(?:\.\d+)?)", re.IGNORECASE)
_SCORE_RE = re.compile(r"(\d+)\s*-\s*(\d+)")

Outcome = str  # "hit" | "miss" | "push" | "unknown"


def _match_result_code(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "1"
    if home_goals < away_goals:
        return "2"
    return "X"


def grade_pick(
    market: str,
    pick: str,
    home_team: str,
    away_team: str,
    home_goals: int,
    away_goals: int,
) -> Outcome:
    """Grade a single pick against a final score. Never guesses: markets we
    can't evaluate from a final score alone (e.g. anytime goalscorer, which
    needs player-level data we don't have) return "unknown"."""
    market_lower = (market or "").lower().strip()
    pick_clean = (pick or "").strip()
    result_code = _match_result_code(home_goals, away_goals)

    if market_lower == "1x2":
        if pick_clean.upper() not in {"1", "X", "2"}:
            return "unknown"
        return "hit" if pick_clean.upper() == result_code else "miss"

    if market_lower == "double chance":
        pick_upper = pick_clean.upper()
        if pick_upper not in {"1X", "X2", "12"}:
            return "unknown"
        return "hit" if result_code in pick_upper else "miss"

    if "both teams to score" in market_lower or market_lower == "btts":
        both_scored = home_goals > 0 and away_goals > 0
        pick_lower = pick_clean.lower()
        if pick_lower.startswith("yes"):
            return "hit" if both_scored else "miss"
        if pick_lower.startswith("no"):
            return "hit" if not both_scored else "miss"
        return "unknown"

    if "draw no bet" in market_lower:
        named = pick_clean.lower().replace("draw no bet", "").strip()
        if not named:
            return "unknown"
        named_norm = _normalize_team(named)
        if named_norm == _normalize_team(home_team):
            team_goals, opp_goals = home_goals, away_goals
        elif named_norm == _normalize_team(away_team):
            team_goals, opp_goals = away_goals, home_goals
        else:
            return "unknown"
        if team_goals == opp_goals:
            return "push"
        return "hit" if team_goals > opp_goals else "miss"

    over_under = _OVER_UNDER_RE.search(pick_clean)
    if over_under or "total goals" in market_lower or "over/under" in market_lower:
        if not over_under:
            return "unknown"
        direction, threshold_str = over_under.group(1).lower(), over_under.group(2)
        threshold = float(threshold_str)
        total_goals = home_goals + away_goals
        if total_goals == threshold:
            return "push"
        if direction == "over":
            return "hit" if total_goals > threshold else "miss"
        return "hit" if total_goals < threshold else "miss"

    if "correct score" in market_lower:
        score_match = _SCORE_RE.search(pick_clean)
        if not score_match:
            return "unknown"
        named = pick_clean[: score_match.start()].strip().lower()
        picked_first, picked_second = int(score_match.group(1)), int(score_match.group(2))
        named_norm = _normalize_team(named)
        if named_norm == _normalize_team(home_team):
            predicted_home, predicted_away = picked_first, picked_second
        elif named_norm == _normalize_team(away_team):
            predicted_home, predicted_away = picked_second, picked_first
        else:
            return "unknown"
        return "hit" if (predicted_home, predicted_away) == (home_goals, away_goals) else "miss"

    return "unknown"
