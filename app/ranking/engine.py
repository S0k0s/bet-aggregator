from __future__ import annotations
from collections import defaultdict
from app.models.schemas import SourcePick, RankedMatch
from app.odds.adapter import OddsAdapter, _sport_key_for
import hashlib
import re
import unicodedata

MIN_SOURCES = 1
TARGET_COUNT = 20
MAX_ODDS_CALLS = 30  # protects the free-tier 500 req/month odds API quota

WEIGHTS = {
    "source_quality": 0.30,
    "consensus": 0.25,
    "price_edge": 0.25,
    "ev_score": 0.20,
}

# price_edge/ev_score both saturate at 1.0 fast for naturally high-odds
# markets (e.g. Correct Score) regardless of how few sources back the pick,
# which let a single-source long-shot outrank a genuine multi-source
# consensus pick. This floor makes consensus act as a confidence
# multiplier on the whole score, not just one more additive term: a
# consensus of 0.0 caps the final score at this fraction of its raw value,
# a consensus of 1.0 keeps 100% of it.
CONSENSUS_CONFIDENCE_FLOOR = 0.4

SOURCE_RELIABILITY = {
    "PredictZ": 0.65,
    "FreeSuperTips": 0.70,
    "StatsBet": 0.72,
    "Vitibet": 0.68,
    "Adibet": 0.60,
    "MyBetsToday": 0.60,
    "Statarea": 0.65,
}

_CLUB_SUFFIXES = re.compile(r"\b(fc|cf|afc|sc|cd|ac|fk)\b", re.IGNORECASE)

CONTINENTS = ("Europe", "Asia", "Americas", "Africa")

# Checked in order against the lowercased competition string. Confederation/
# competition keywords first (unambiguous), then country names. Israel is
# bucketed as Europe (UEFA member) despite its geography; Australia as Asia
# (AFC member) for the same footballing-organization reason.
_CONTINENT_KEYWORDS = [
    ("uefa", "Europe"), ("champions league", "Europe"), ("europa league", "Europe"),
    ("conference league", "Europe"), ("conmebol", "Americas"), ("copa libertadores", "Americas"),
    ("copa sudamericana", "Americas"), ("caf ", "Africa"), ("afc ", "Asia"),
    ("england", "Europe"), ("scotland", "Europe"), ("wales", "Europe"), ("ireland", "Europe"),
    ("greece", "Europe"), ("spain", "Europe"), ("italy", "Europe"), ("germany", "Europe"),
    ("france", "Europe"), ("portugal", "Europe"), ("netherlands", "Europe"), ("belgium", "Europe"),
    ("bulgaria", "Europe"), ("croatia", "Europe"), ("serbia", "Europe"), ("russia", "Europe"),
    ("poland", "Europe"), ("romania", "Europe"), ("turkey", "Europe"), ("ukraine", "Europe"),
    ("austria", "Europe"), ("switzerland", "Europe"), ("denmark", "Europe"), ("sweden", "Europe"),
    ("norway", "Europe"), ("finland", "Europe"), ("czech", "Europe"), ("hungary", "Europe"),
    ("israel", "Europe"), ("bosnia", "Europe"), ("albania", "Europe"), ("slovenia", "Europe"),
    ("slovakia", "Europe"), ("iceland", "Europe"), ("cyprus", "Europe"), ("kosovo", "Europe"),
    ("armenia", "Europe"), ("georgia", "Europe"), ("azerbaijan", "Europe"), ("kazakhstan", "Europe"),
    ("belarus", "Europe"), ("moldova", "Europe"), ("montenegro", "Europe"), ("macedonia", "Europe"),
    ("luxembourg", "Europe"), ("estonia", "Europe"), ("latvia", "Europe"), ("lithuania", "Europe"),
    ("malta", "Europe"), ("san marino", "Europe"), ("andorra", "Europe"), ("faroe", "Europe"),
    ("gibraltar", "Europe"), ("europe", "Europe"), ("international", "Europe"),
    ("iran", "Asia"), ("saudi arabia", "Asia"), ("china", "Asia"), ("japan", "Asia"),
    ("korea", "Asia"), ("qatar", "Asia"), ("emirates", "Asia"), ("uzbekistan", "Asia"),
    ("iraq", "Asia"), ("india", "Asia"), ("thailand", "Asia"), ("vietnam", "Asia"),
    ("indonesia", "Asia"), ("malaysia", "Asia"), ("singapore", "Asia"), ("australia", "Asia"),
    ("bahrain", "Asia"), ("kuwait", "Asia"), ("jordan", "Asia"), ("lebanon", "Asia"),
    ("syria", "Asia"), ("oman", "Asia"), ("yemen", "Asia"), ("kyrgyzstan", "Asia"),
    ("tajikistan", "Asia"), ("turkmenistan", "Asia"), ("mongolia", "Asia"), ("myanmar", "Asia"),
    ("cambodia", "Asia"), ("nepal", "Asia"), ("bangladesh", "Asia"), ("sri lanka", "Asia"),
    ("pakistan", "Asia"), ("afghanistan", "Asia"), ("bhutan", "Asia"), ("hong kong", "Asia"),
    ("taiwan", "Asia"), ("philippines", "Asia"), ("brunei", "Asia"), ("laos", "Asia"),
    ("brazil", "Americas"), ("argentina", "Americas"), ("mexico", "Americas"), ("chile", "Americas"),
    ("colombia", "Americas"), ("ecuador", "Americas"), ("paraguay", "Americas"), ("uruguay", "Americas"),
    ("peru", "Americas"), ("bolivia", "Americas"), ("venezuela", "Americas"), ("usa", "Americas"),
    ("united states", "Americas"), ("canada", "Americas"), ("costa rica", "Americas"),
    ("honduras", "Americas"), ("guatemala", "Americas"), ("panama", "Americas"),
    ("el salvador", "Americas"), ("jamaica", "Americas"), ("trinidad", "Americas"),
    ("nicaragua", "Americas"), ("dominican", "Americas"), ("haiti", "Americas"), ("cuba", "Americas"),
    ("barbados", "Americas"), ("suriname", "Americas"), ("guyana", "Americas"),
    ("tanzania", "Africa"), ("nigeria", "Africa"), ("egypt", "Africa"), ("south africa", "Africa"),
    ("ghana", "Africa"), ("kenya", "Africa"), ("morocco", "Africa"), ("algeria", "Africa"),
    ("tunisia", "Africa"), ("cameroon", "Africa"), ("senegal", "Africa"), ("zambia", "Africa"),
    ("zimbabwe", "Africa"), ("uganda", "Africa"), ("ivory coast", "Africa"), ("mali", "Africa"),
    ("burkina faso", "Africa"), ("angola", "Africa"), ("mozambique", "Africa"), ("botswana", "Africa"),
    ("namibia", "Africa"), ("rwanda", "Africa"), ("ethiopia", "Africa"), ("libya", "Africa"),
    ("sudan", "Africa"), ("congo", "Africa"), ("gabon", "Africa"), ("benin", "Africa"),
    ("togo", "Africa"), ("niger", "Africa"), ("chad", "Africa"), ("madagascar", "Africa"),
    ("malawi", "Africa"), ("mauritius", "Africa"), ("liberia", "Africa"), ("sierra leone", "Africa"),
    ("gambia", "Africa"), ("guinea", "Africa"), ("burundi", "Africa"), ("somalia", "Africa"),
    ("eritrea", "Africa"), ("djibouti", "Africa"), ("lesotho", "Africa"), ("eswatini", "Africa"),
    ("mauritania", "Africa"), ("cape verde", "Africa"),
]


def _continent_for(competition: str | None) -> str:
    if competition:
        lowered = competition.lower()
        for keyword, continent in _CONTINENT_KEYWORDS:
            if keyword in lowered:
                return continent
    return "Europe"


def _normalize_team(name: str) -> str:
    """Heuristic normalization for cross-source fixture matching.

    This is a pragmatic first pass (strip accents, lowercase, strip common
    club suffixes, collapse whitespace) — not the full TeamAliasNormalizer
    the handover calls out as its own backlog item (e.g. "Man Utd" vs
    "Manchester United" still won't merge). Good enough to merge trivial
    casing/accent/whitespace/suffix differences across sources — accent
    stripping matters in practice: one source may write "Fenerbahce" and
    another "Fenerbahçe" for the same club.
    """
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    normalized = _CLUB_SUFFIXES.sub("", ascii_name.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _fixture_key(pick: SourcePick) -> str:
    return f"{_normalize_team(pick.home_team)}|{_normalize_team(pick.away_team)}"


def _match_key(pick: SourcePick) -> str:
    return f"{_fixture_key(pick)}|{pick.market}|{pick.pick}"


def _consensus(picks: list[SourcePick], fixture_source_counts: dict[str, int]) -> float:
    if not picks:
        return 0.0
    fixture = _fixture_key(picks[0])
    agreeing_sources = len({p.source_name for p in picks})
    eligible_sources = fixture_source_counts.get(fixture, agreeing_sources)
    if eligible_sources == 0:
        return 0.0
    return min(agreeing_sources / eligible_sources, 1.0)


def _source_quality(picks: list[SourcePick], reliability: dict[str, float]) -> float:
    scores = [reliability.get(p.source_name, SOURCE_RELIABILITY.get(p.source_name, 0.5)) for p in picks]
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


async def build_ranked_matches(
    all_picks: list[SourcePick],
    reliability_overrides: dict[str, float] | None = None,
) -> dict[str, list[RankedMatch]]:
    reliability = reliability_overrides or {}
    grouped: dict[str, list[SourcePick]] = defaultdict(list)
    for pick in all_picks:
        grouped[_match_key(pick)].append(pick)

    # How many distinct sources reported *anything* for each fixture (any
    # market/pick), used as the denominator for a real consensus ratio.
    fixture_source_counts: dict[str, set[str]] = defaultdict(set)
    for pick in all_picks:
        fixture_source_counts[_fixture_key(pick)].add(pick.source_name)
    fixture_source_totals = {k: len(v) for k, v in fixture_source_counts.items()}

    odds_adapter = OddsAdapter()
    odds_calls_made = 0
    candidates: list[RankedMatch] = []

    # MIN_SOURCES=1: no hard cutoff on agreement. Results are sorted below
    # by final_score, which weights consensus + source_quality, so
    # higher-agreement picks naturally rank above single-source ones;
    # source_count/consensus_score stay on every RankedMatch so a
    # low-agreement pick is never mistaken for a confirmed one.
    for key, picks in grouped.items():
        distinct_sources = {p.source_name for p in picks}
        if len(distinct_sources) < MIN_SOURCES:
            continue

        p0 = picks[0]
        parts = key.split("|")
        market = parts[2] if len(parts) > 2 else "1X2"
        rec_pick = parts[3] if len(parts) > 3 else p0.pick
        home_team = next((p.home_team for p in picks if p.home_team), "Unknown")
        away_team = next((p.away_team for p in picks if p.away_team), "Unknown")
        competition = next((p.competition for p in picks if p.competition), "European")
        kickoff = next((p.kickoff for p in picks if p.kickoff), "TBD")

        best_odds_from_picks = max(
            (p.quoted_odds for p in picks if p.quoted_odds and p.quoted_odds > 1.0),
            default=None
        )
        best_odds_live = None
        if _sport_key_for(competition) is not None and odds_calls_made < MAX_ODDS_CALLS:
            best_odds_live = await odds_adapter.get_best_odds(home_team, away_team, market, competition)
            odds_calls_made += 1
        best_odds = best_odds_live or best_odds_from_picks  # None if no real price found — never fake a number

        sq = _source_quality(picks, reliability)
        con = _consensus(picks, fixture_source_totals)
        pe = _price_edge(best_odds)
        ev = _ev_score(best_odds, con)

        raw_score = (
            WEIGHTS["source_quality"] * sq +
            WEIGHTS["consensus"] * con +
            WEIGHTS["price_edge"] * pe +
            WEIGHTS["ev_score"] * ev
        )
        confidence_multiplier = CONSENSUS_CONFIDENCE_FLOOR + (1 - CONSENSUS_CONFIDENCE_FLOOR) * con
        final_score = raw_score * confidence_multiplier

        reasons = [p.reason_summary for p in picks if p.reason_summary]
        explanation = " | ".join(reasons[:3]) if reasons else "No explanation available."

        match_id = hashlib.md5(key.encode()).hexdigest()[:8]
        candidates.append(RankedMatch(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            competition=competition,
            kickoff=kickoff,
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

    by_continent: dict[str, list[RankedMatch]] = defaultdict(list)
    for m in candidates:
        by_continent[_continent_for(m.competition)].append(m)

    result: dict[str, list[RankedMatch]] = {}
    for continent in CONTINENTS:
        bucket = sorted(by_continent.get(continent, []), key=lambda m: m.final_score, reverse=True)
        result[continent] = bucket[:TARGET_COUNT]
    return result
