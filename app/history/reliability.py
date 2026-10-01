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


def compute_market_reliability(
    history: list[dict],
    prior_weight: float = PRIOR_WEIGHT,
    prior_value: float = PRIOR_VALUE,
) -> dict[str, float]:
    """Bayesian-shrunk hit rate per market (1X2, Double Chance, ...), same
    shrinkage as compute_reliability() but grouped by entry["market"]
    instead of source. Lets the ranking engine favor markets with a real
    track record (Double Chance/Total Goals/BTTS have run well above 1X2
    and far above Correct Score) over a flat per-source score alone.
    """
    hits: dict[str, int] = defaultdict(int)
    misses: dict[str, int] = defaultdict(int)

    for entry in history:
        outcome = entry.get("outcome")
        if outcome not in ("hit", "miss"):
            continue
        market = entry.get("market")
        if not market:
            continue
        if outcome == "hit":
            hits[market] += 1
        else:
            misses[market] += 1

    reliability: dict[str, float] = {}
    for market in set(hits) | set(misses):
        h, m = hits[market], misses[market]
        reliability[market] = round(
            (h + prior_weight * prior_value) / (h + m + prior_weight), 3
        )
    return reliability


def source_market_key(source_name: str, market: str) -> str:
    return f"{source_name}|{market}"


def compute_source_market_reliability(
    history: list[dict],
    prior_weight: float = PRIOR_WEIGHT,
    prior_value: float = PRIOR_VALUE,
    min_samples: int = 10,
) -> dict[str, float]:
    """Bayesian-shrunk hit rate per (source, market) combo, key'd as
    "Source|Market" (flat, so it loads with the same generic
    load_reliability() as every other *-reliability.json file).

    A real audit found this combo can diverge sharply from either the
    source's or the market's own average alone - e.g. Adibet's 1X2 ran
    ~82% (well above Vitibet/Statarea's ~58-60% on the same market) while
    Adibet's own Double Chance ran ~54% (below Vitibet/Statarea's ~67-71%
    on *that* market). A flat per-source or per-market score can't capture
    that; this can.

    `min_samples` guards against noise: a combo with fewer than this many
    graded picks is left out entirely, so a 2-sample fluke doesn't
    override the coarser per-source/per-market fallback the engine already
    has. 10 is a judgment call, not a measured threshold - tune it once
    more data exists.
    """
    hits: dict[str, int] = defaultdict(int)
    misses: dict[str, int] = defaultdict(int)

    for entry in history:
        outcome = entry.get("outcome")
        if outcome not in ("hit", "miss"):
            continue
        market = entry.get("market")
        if not market:
            continue
        for source_name in entry.get("sources", []):
            key = source_market_key(source_name, market)
            if outcome == "hit":
                hits[key] += 1
            else:
                misses[key] += 1

    reliability: dict[str, float] = {}
    for key in set(hits) | set(misses):
        h, m = hits[key], misses[key]
        if h + m < min_samples:
            continue
        reliability[key] = round(
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
