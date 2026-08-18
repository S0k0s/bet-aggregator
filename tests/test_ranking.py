import pytest
from app.models.schemas import SourcePick
from app.ranking.engine import build_ranked_matches, _normalize_team, _match_key


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
    ranked = await build_ranked_matches(picks)
    assert len(ranked) == 1
    match = ranked[0]
    assert match.home_team.lower().startswith("arsenal")
    assert match.away_team.lower() == "chelsea"
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
    ranked = await build_ranked_matches(high_agreement + low_agreement)
    assert len(ranked) == 2
    assert ranked[0].home_team == "Arsenal"
    assert ranked[0].source_count == 3
    assert ranked[1].home_team == "Liverpool"
    assert ranked[1].source_count == 1
    assert ranked[0].final_score > ranked[1].final_score


@pytest.mark.asyncio
async def test_consensus_reflects_disagreeing_sources_not_just_count():
    picks = [
        _pick("PredictZ", "Arsenal", "Chelsea", pick="1"),
        _pick("FreeSuperTips", "Arsenal", "Chelsea", pick="1"),
        _pick("StatsBet", "Arsenal", "Chelsea", pick="1"),
        _pick("PredictZ", "Arsenal", "Chelsea", pick="X"),
    ]
    ranked = await build_ranked_matches(picks)
    # Both the majority "1" pick and PredictZ's lone "X" pick surface (no
    # hard source-count cutoff), but "1" ranks first and its consensus is
    # "3 of 3 distinct sources for this fixture agree on 1" -> 1.0, not
    # len(picks)/20 as the old buggy implementation computed.
    assert ranked[0].recommended_pick == "1"
    assert ranked[0].consensus_score == 1.0
    assert ranked[0].source_count == 3
