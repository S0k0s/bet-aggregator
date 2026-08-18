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
async def test_below_min_sources_is_dropped():
    picks = [
        _pick("PredictZ", "Arsenal", "Chelsea"),
        _pick("FreeSuperTips", "Arsenal", "Chelsea"),
    ]
    ranked = await build_ranked_matches(picks)
    assert ranked == []


@pytest.mark.asyncio
async def test_consensus_reflects_disagreeing_sources_not_just_count():
    picks = [
        _pick("PredictZ", "Arsenal", "Chelsea", pick="1"),
        _pick("FreeSuperTips", "Arsenal", "Chelsea", pick="1"),
        _pick("StatsBet", "Arsenal", "Chelsea", pick="1"),
        _pick("PredictZ", "Arsenal", "Chelsea", pick="X"),
    ]
    ranked = await build_ranked_matches(picks)
    assert len(ranked) == 1
    # 3 of 3 distinct sources agree on "1" for this fixture -> consensus 1.0,
    # not len(picks)/20 as the old buggy implementation computed.
    assert ranked[0].consensus_score == 1.0
