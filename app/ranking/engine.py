from __future__ import annotations
from collections import defaultdict
from app.models.schemas import SourcePick, RankedMatch
from app.odds.adapter import OddsAdapter
import hashlib

MIN_SOURCES = 3
TARGET_COUNT = 20

WEIGHTS = {
    "source_quality": 0.30,
    "consensus": 0.25,
    "price_edge": 0.25,
    "ev_score": 0.20,
}

SOURCE_RELIABILITY = {
    "PredictZ": 0.65,
    "FreeSuperTips": 0.70,
    "StatsBet": 0.72,
}


def _match_key(pick: SourcePick) -> str:
    return f"{pick.source_url}|{pick.market}|{pick.pick}"


def _consensus(picks: list[SourcePick]) -> float:
    if not picks:
        return 0.0
    return min(len(picks) / TARGET_COUNT, 1.0)


def _source_quality(picks: list[SourcePick]) -> float:
    scores = [SOURCE_RELIABILITY.get(p.source_name, 0.5) for p in picks]
    return sum(scores) / len(scores) if scores else 0.0


def _price_edge(best_odds: float | None, market_avg: float = 1.90) -> float:
    if best_odds is None or best_odds <= 1.0:
        return 0.0
    edge = (best_odds - market_avg) / market_avg
    return max(0.0, min(edge, 1.0))


def _ev_score(best_odds: float | None, consensus: float) -> float:
    if best_odds is None or best_odds <= 1.0:
        return 0.0
    implied_prob = 1 / best_odds
    ev = (consensus - implied_prob) / implied_prob
    return max(0.0, min(ev, 1.0))


async def build_ranked_matches(all_picks: list[SourcePick]) -> list[RankedMatch]:
    grouped: dict[str, list[SourcePick]] = defaultdict(list)
    for pick in all_picks:
        grouped[_match_key(pick)].append(pick)

    odds_adapter = OddsAdapter()
    candidates: list[RankedMatch] = []

    for key, picks in grouped.items():
        if len(picks) < MIN_SOURCES:
            continue

        p0 = picks[0]
        parts = key.split("|")
        market = parts[1] if len(parts) > 1 else "1X2"
        rec_pick = parts[2] if len(parts) > 2 else p0.pick

        best_odds_from_picks = max(
            (p.quoted_odds for p in picks if p.quoted_odds and p.quoted_odds > 1.0),
            default=None
        )
        best_odds_live = await odds_adapter.get_best_odds(
            p0.source_name, p0.source_url, market
        )
        best_odds = best_odds_live or best_odds_from_picks or 1.90

        sq = _source_quality(picks)
        con = _consensus(picks)
        pe = _price_edge(best_odds)
        ev = _ev_score(best_odds, con)

        final_score = (
            WEIGHTS["source_quality"] * sq +
            WEIGHTS["consensus"] * con +
            WEIGHTS["price_edge"] * pe +
            WEIGHTS["ev_score"] * ev
        )

        reasons = [p.reason_summary for p in picks if p.reason_summary]
        explanation = " | ".join(reasons[:3]) if reasons else "No explanation available."

        match_id = hashlib.md5(key.encode()).hexdigest()[:8]
        candidates.append(RankedMatch(
            match_id=match_id,
            home_team=p0.source_name,
            away_team=p0.source_url,
            competition="European",
            kickoff="TBD",
            market=market,
            recommended_pick=rec_pick,
            best_odds=best_odds,
            consensus_score=round(con, 3),
            price_edge_score=round(pe, 3),
            source_count=len(picks),
            final_score=round(final_score, 3),
            sources=picks,
            explanation=explanation,
        ))

    candidates.sort(key=lambda m: m.final_score, reverse=True)
    return candidates[:TARGET_COUNT]
