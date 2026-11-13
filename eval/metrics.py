"""Small, dependency-free metric helpers (unit-tested in tests/test_eval_metrics.py)."""

from __future__ import annotations

import math
import random


def auroc(positive: list[float], negative: list[float]) -> float | None:
    """P(random positive scores higher than random negative); ties count half."""
    if not positive or not negative:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in positive for n in negative)
    return wins / (len(positive) * len(negative))


def prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score interval for a proportion."""
    if n == 0:
        return None
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def bootstrap_ci(
    items: list, stat, n_boot: int = 2000, seed: int = 0
) -> tuple[float, float] | None:
    """Percentile bootstrap 95% CI of stat(sample); resamples that give None are skipped."""
    rng = random.Random(seed)
    values = []
    for _ in range(n_boot):
        sample = [rng.choice(items) for _ in items]
        v = stat(sample)
        if v is not None:
            values.append(v)
    if not values:
        return None
    values.sort()
    return values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]
