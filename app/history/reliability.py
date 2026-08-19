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


def compute_source_stats(
    history: list[dict],
    reliability: dict[str, float] | None = None,
) -> list[dict]:
    """Per-source outcome breakdown for the "Πηγές" dashboard tab.

    Unlike compute_reliability() (a single Bayesian-shrunk score meant for
    ranking weights), this keeps the raw counts so the user can actually
    see how many picks each source has been graded on and its plain
    hit-rate over time - the shrunk score alone hides whether a rate is
    backed by 3 samples or 300.
    """
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {
        "hit": 0, "miss": 0, "push": 0, "unknown": 0, "pending": 0,
    })
    for entry in history:
        outcome = entry.get("outcome", "pending")
        if outcome not in ("hit", "miss", "push", "unknown", "pending"):
            continue
        for source_name in entry.get("sources", []):
            counts[source_name][outcome] += 1

    reliability = reliability if reliability is not None else compute_reliability(history)
    stats: list[dict] = []
    for source_name, c in counts.items():
        graded = c["hit"] + c["miss"]
        stats.append({
            "name": source_name,
            "hit": c["hit"],
            "miss": c["miss"],
            "push": c["push"],
            "unknown": c["unknown"],
            "pending": c["pending"],
            "graded": graded,
            "hit_rate": round(c["hit"] / graded, 3) if graded else None,
            "reliability_score": reliability.get(source_name),
        })
    stats.sort(key=lambda s: (-(s["graded"]), -(s["hit_rate"] or 0)))
    return stats
