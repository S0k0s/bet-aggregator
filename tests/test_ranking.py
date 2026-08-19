import pytest
from app.models.schemas import SourcePick
from app.ranking.engine import build_ranked_matches, _normalize_team, _match_key, _odds_for_pick


def _pick(source_name, home, away, market="1X2", pick="1", odds=1.9):
    return SourcePick(
        source_name=source_name,
        source_url=f"https://example.com/{source_name}",
        home_team=home,
        away_team=away,
        market=market,
        pick=pick,
        quoted_odds=odds,
    )


def test_odds_for_pick_1x2_and_double_chance_combined():
    odds_map = {"home": 1.66, "draw": 3.95, "away": 4.65}
    assert _odds_for_pick("1X2", "1", odds_map) == 1.66
    assert _odds_for_pick("1X2", "X", odds_map) == 3.95
    assert _odds_for_pick("1X2", "2", odds_map) == 4.65
    # Double Chance combined odds via implied-probability sum (no vig
    # adjustment): 1 / (1/1.66 + 1/3.95) ~= 1.17
    assert _odds_for_pick("Double Chance", "1X", odds_map) == round(1 / (1 / 1.66 + 1 / 3.95), 2)
    assert _odds_for_pick("Correct Score", "Team 2-0", odds_map) is None
    assert _odds_for_pick("1X2", "1", {}) is None


@pytest.mark.asyncio
async def test_league_breakdown_buckets_premier_league_and_afc_champions_league():
    def _pick_with_competition(source, home, away, competition):
        p = _pick(source, home, away)
        return p.model_copy(update={"competition": competition})

    picks = [
        _pick_with_competition("Vitibet", "Arsenal", "Chelsea", "England: Premier League"),
        _pick_with_competition("Vitibet", "Al Hilal", "Urawa Reds", "AFC Champions League"),
    ]
    result = await build_ranked_matches(picks)
    # Regression: "AFC Champions League" contains "champions league" but
    # must NOT be bucketed into Europe just for that substring.
    europe_leagues = result["Europe"]["leagues"]
    asia_leagues = result["Asia"]["leagues"]
    assert any(m.home_team == "Arsenal" for m in europe_leagues.get("Premier League", []))
    assert any(m.home_team == "Al Hilal" for m in asia_leagues.get("AFC Champions League", []))
    assert all(m.home_team != "Al Hilal" for ms in europe_leagues.values() for m in ms)


def test_normalize_team_strips_suffix_case_and_whitespace():
    assert _normalize_team("Arsenal FC") == "arsenal"
    assert _normalize_team("  arsenal   fc ") == "arsenal"
    assert _normalize_team("Arsenal") == "arsenal"


def test_normalize_team_strips_accents_and_fk_suffix():
    # Real gap found by running the live pipeline: FreeSuperTips wrote
    # "Fenerbahce"/"Viking FK", Vitibet wrote "Fenerbahçe"/"Viking" for the
    # same two fixtures — both must normalize to the same key.
    assert _normalize_team("Fenerbahçe") == _normalize_team("Fenerbahce")
    assert _normalize_team("Viking FK") == _normalize_team("Viking")


def test_same_fixture_from_different_sources_shares_match_key():
    a = _pick("PredictZ", "Arsenal FC", "Chelsea")
    b = _pick("FreeSuperTips", "arsenal", " Chelsea ")
    assert _match_key(a) == _match_key(b)


@pytest.mark.asyncio
async def test_three_sources_agreeing_produce_one_ranked_match_with_real_teams():
    picks = [
        _pick("PredictZ", "Arsenal FC", "Chelsea"),
        _pick("FreeSuperTips", "Arsenal", "Chelsea"),
        _pick("StatsBet", "arsenal", "chelsea"),
    ]
    ranked = (await build_ranked_matches(picks))["Europe"]["all"]
    assert len(ranked) == 1
    card = ranked[0]
    match = card.picks[0]
    assert card.home_team.lower().startswith("arsenal")
    assert card.away_team.lower() == "chelsea"
    assert match.source_count == 3
    assert match.consensus_score == 1.0


@pytest.mark.asyncio
async def test_higher_agreement_ranks_above_lower_agreement():
    # No hard minimum-sources cutoff: a single-source pick still appears,
    # but sorts below a multi-source one because final_score weights
    # consensus + source_quality.
    high_agreement = [
        _pick("PredictZ", "Arsenal", "Chelsea", pick="1"),
        _pick("FreeSuperTips", "Arsenal", "Chelsea", pick="1"),
        _pick("StatsBet", "Arsenal", "Chelsea", pick="1"),
    ]
    low_agreement = [_pick("Vitibet", "Liverpool", "Everton", pick="1")]
    ranked = (await build_ranked_matches(high_agreement + low_agreement))["Europe"]["all"]
    assert len(ranked) == 2
    assert ranked[0].home_team == "Arsenal"
    assert ranked[0].picks[0].source_count == 3
    assert ranked[1].home_team == "Liverpool"
    assert ranked[1].picks[0].source_count == 1
    assert ranked[0].picks[0].final_score > ranked[1].picks[0].final_score


@pytest.mark.asyncio
async def test_consensus_reflects_disagreeing_sources_not_just_count():
    picks = [
        _pick("PredictZ", "Arsenal", "Chelsea", pick="1"),
        _pick("FreeSuperTips", "Arsenal", "Chelsea", pick="1"),
        _pick("StatsBet", "Arsenal", "Chelsea", pick="1"),
        _pick("PredictZ", "Arsenal", "Chelsea", pick="X"),
    ]
    ranked = (await build_ranked_matches(picks))["Europe"]["all"]
    # Same fixture, two markets/picks -> grouped into a single MatchCard.
    # Both the majority "1" pick and PredictZ's lone "X" pick surface (no
    # hard source-count cutoff), but "1" ranks first within the card and its
    # consensus is "3 of 3 distinct sources for this fixture agree on 1" ->
    # 1.0, not len(picks)/20 as the old buggy implementation computed.
    assert len(ranked) == 1
    top_pick = ranked[0].picks[0]
    assert top_pick.recommended_pick == "1"
    assert top_pick.consensus_score == 1.0
    assert top_pick.source_count == 3


@pytest.mark.asyncio
async def test_domestic_cup_or_group_matches_alternate_sponsor_names():
    def _pick_with_competition(source, home, away, competition):
        p = _pick(source, home, away)
        return p.model_copy(update={"competition": competition})

    # Sponsor-renamed cups need to match under any known name (Belgium's
    # cup has been "Croky Cup" and "Belgian Cup" across seasons/sources).
    picks = [
        _pick_with_competition("Vitibet", "Anderlecht", "Club Brugge", "Belgium: Croky Cup"),
        _pick_with_competition("Vitibet", "Genk", "Gent", "Belgium Cup"),
    ]
    result = await build_ranked_matches(picks)
    cup_matches = result["Europe"]["leagues"].get("Belgian Cup", [])
    assert {m.home_team for m in cup_matches} == {"Anderlecht", "Genk"}


@pytest.mark.asyncio
async def test_low_consensus_longshot_no_longer_beats_high_consensus_safe_pick():
    # Regression test for a real ranking anomaly found live: a
    # single-agreeing-source, high-odds "long shot" (Correct Score) was
    # outranking a genuine 3-source consensus pick on a safer market,
    # purely because price_edge/ev_score saturate fast on high odds
    # regardless of how many sources actually back the pick.
    longshot_fixture = [
        _pick("PredictZ", "LongshotFC", "Rival", market="Correct Score", pick="LongshotFC 2-1", odds=8.50),
        _pick("FreeSuperTips", "LongshotFC", "Rival", market="1X2", pick="X", odds=3.2),
        _pick("StatsBet", "LongshotFC", "Rival", market="1X2", pick="2", odds=2.5),
    ]
    safe_fixture = [
        _pick("PredictZ", "Favourite", "Underdog", market="Double Chance", pick="1X", odds=1.3),
        _pick("FreeSuperTips", "Favourite", "Underdog", market="Double Chance", pick="1X", odds=1.3),
        _pick("StatsBet", "Favourite", "Underdog", market="Double Chance", pick="1X", odds=1.3),
    ]
    ranked = (await build_ranked_matches(longshot_fixture + safe_fixture))["Europe"]["all"]
    longshot = next(m for m in ranked if m.home_team == "LongshotFC").picks[0]
    safe = next(m for m in ranked if m.home_team == "Favourite").picks[0]
    assert longshot.consensus_score < 0.5
    assert safe.consensus_score == 1.0
    assert safe.final_score > longshot.final_score
