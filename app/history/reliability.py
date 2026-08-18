from __future__ import annotations
from collections import defaultdict

PRIOR_WEIGHT = 4
PRIOR_VALUE = 0.5


def compute_reliability(
    history: list[dict],
    prior_weight: float = PRIOR_WEIGHT,
    prior_value: float = PRIOR_VALUE,
) -> dict[str, float]:
    """Bayesian-shrunk hit rate per source, from graded history entries.

    Only "hit"/"miss" outcomes count (push/unknown/pending are excluded,
    same as the overall hit-rate in check_results.py). A source with zero
    graded samples is simply absent from the result — callers fall back
    to their own default for those. The prior shrinks small samples
    toward 0.5 so one early miss doesn't tank a new source to 0%.
    """
    hits: dict[str, int] = defaultdict(int)
    misses: dict[str, int] = defaultdict(int)

    for entry in history:
        outcome = entry.get("outcome")
        if outcome not in ("hit", "miss"):
            continue
        for source_name in entry.get("sources", []):
            if outcome == "hit":
                hits[source_name] += 1
            else:
                misses[source_name] += 1

    reliability: dict[str, float] = {}
    for source_name in set(hits) | set(misses):
        h, m = hits[source_name], misses[source_name]
        reliability[source_name] = round(
            (h + prior_weight * prior_value) / (h + m + prior_weight), 3
        )
    return reliability
