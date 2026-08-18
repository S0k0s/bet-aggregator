from app.history.reliability import compute_reliability


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
