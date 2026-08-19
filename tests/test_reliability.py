from app.history.reliability import compute_reliability, compute_source_stats


def _entry(outcome, sources):
    return {"outcome": outcome, "sources": sources}


def test_no_graded_history_yields_empty():
    history = [_entry("pending", ["A"]), _entry("unknown", ["A"])]
    assert compute_reliability(history) == {}


def test_shrinks_small_sample_toward_prior():
    # One hit, no misses: raw rate would be 100%, but the prior shrinks it.
    history = [_entry("hit", ["NewSource"])]
    result = compute_reliability(history, prior_weight=4, prior_value=0.5)
    assert result["NewSource"] == round((1 + 4 * 0.5) / (1 + 4), 3)
    assert 0.5 < result["NewSource"] < 1.0


def test_large_sample_converges_to_observed_rate():
    history = [_entry("hit", ["Reliable"])] * 96 + [_entry("miss", ["Reliable"])] * 4
    result = compute_reliability(history, prior_weight=4, prior_value=0.5)
    # 96/100 observed, prior barely moves it with 100 real samples.
    assert 0.93 < result["Reliable"] < 0.97


def test_credits_all_contributing_sources_per_entry():
    history = [_entry("hit", ["A", "B"]), _entry("miss", ["A"])]
    result = compute_reliability(history, prior_weight=4, prior_value=0.5)
    assert result["A"] == round((1 + 2) / (2 + 4), 3)
    assert result["B"] == round((1 + 2) / (1 + 4), 3)


def test_push_and_pending_entries_are_ignored():
    history = [
        _entry("push", ["A"]),
        _entry("pending", ["A"]),
        _entry("hit", ["A"]),
    ]
    result = compute_reliability(history, prior_weight=4, prior_value=0.5)
    assert result["A"] == round((1 + 2) / (1 + 4), 3)


def test_source_stats_counts_every_outcome_and_computes_raw_hit_rate():
    history = [
        _entry("hit", ["A"]), _entry("hit", ["A"]), _entry("miss", ["A"]),
        _entry("push", ["A"]), _entry("unknown", ["A"]), _entry("pending", ["A"]),
    ]
    stats = {s["name"]: s for s in compute_source_stats(history)}
    a = stats["A"]
    assert a["hit"] == 2 and a["miss"] == 1 and a["push"] == 1
    assert a["unknown"] == 1 and a["pending"] == 1
    assert a["graded"] == 3
    assert a["hit_rate"] == round(2 / 3, 3)


def test_source_stats_hit_rate_is_none_with_no_graded_samples():
    history = [_entry("pending", ["A"]), _entry("push", ["A"])]
    stats = {s["name"]: s for s in compute_source_stats(history)}
    assert stats["A"]["hit_rate"] is None
    assert stats["A"]["graded"] == 0


def test_source_stats_sorted_by_graded_volume_then_hit_rate():
    history = (
        [_entry("hit", ["Big"])] * 8 + [_entry("miss", ["Big"])] * 2  # 10 graded, 80%
        + [_entry("hit", ["Small"])] * 2  # 2 graded, 100%
    )
    stats = compute_source_stats(history)
    assert [s["name"] for s in stats] == ["Big", "Small"]


def test_source_stats_includes_reliability_score():
    history = [_entry("hit", ["A"])]
    reliability = compute_reliability(history)
    stats = {s["name"]: s for s in compute_source_stats(history, reliability)}
    assert stats["A"]["reliability_score"] == reliability["A"]
