import json
from pathlib import Path

import pytest

from eval.metrics import auroc, bootstrap_ci, prf, wilson


def test_auroc_perfect_chance_and_ties():
    assert auroc([0.9, 0.8], [0.1, 0.2]) == 1.0
    assert auroc([0.1], [0.9]) == 0.0
    assert auroc([0.5], [0.5]) == 0.5
    assert auroc([], [0.5]) is None


def test_prf():
    m = prf(tp=8, fp=2, fn=2)
    assert m["precision"] == pytest.approx(0.8)
    assert m["recall"] == pytest.approx(0.8)
    assert m["f1"] == pytest.approx(0.8)
    assert prf(0, 0, 0)["f1"] is None


def test_wilson_contains_point_estimate_and_is_bounded():
    lo, hi = wilson(7, 10)
    assert 0 <= lo < 0.7 < hi <= 1
    assert wilson(0, 0) is None


def test_bootstrap_ci_brackets_the_mean():
    data = [1.0] * 50 + [0.0] * 50
    lo, hi = bootstrap_ci(data, lambda s: sum(s) / len(s), n_boot=500)
    assert lo < 0.5 < hi


def test_dataset_is_well_formed():
    rows = [json.loads(x) for x in Path("eval/dataset.jsonl").read_text("utf-8").splitlines()]
    assert len(rows) >= 50
    assert len({r["id"] for r in rows}) == len(rows)
    assert {r["split"] for r in rows} == {"dev", "heldout"}
    kb_docs = {p.stem for p in Path("kb").glob("*.md")}
    for r in rows:
        assert set(r["expected_docs"]) <= kb_docs, r["id"]
