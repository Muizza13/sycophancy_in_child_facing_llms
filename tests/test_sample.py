"""Future samples stay at the requested size and do not replace the frozen key."""

import json

import pytest

from audit.io import load_csv, load_jsonl
from audit.protect import assert_writable, repo_root
from audit.sample import legacy_unbounded_selection, select_sample, turn3_stance_map, write_sample

ROOT = repo_root()


def _item(case_id, model, condition, child="c", tutor="t"):
    return {
        "line": 1,
        "rec": {
            "case_id": case_id,
            "model": model,
            "condition": condition,
            "subject": "arithmetic",
            "correct_answer": "1",
            "child_wrong_answer": "2",
            "turns": [
                {"turn": 1, "child": child, "model": tutor},
                {"turn": 2, "child": child, "model": tutor},
                {"turn": 3, "child": child, "model": tutor},
            ],
        },
    }


def test_requested_size_is_a_hard_cap_and_the_draw_is_reproducible():
    rows = []
    judge_a = {}
    judge_b = {}
    index = 0
    for model in ("gemini-2.5-flash", "gemini-2.5-flash-lite"):
        for condition in ("naive", "pedagogical"):
            for number in range(3):
                case_id = "math_%03d" % index
                index += 1
                key = (case_id, model, condition)
                rows.append(_item(case_id, model, condition))
                judge_a[key] = "holds"
                judge_b[key] = "caves"
    first, record = select_sample(rows, judge_a, judge_b, 5, seed=7)
    second, _record = select_sample(rows, judge_a, judge_b, 5, seed=7)
    assert len(first) == 5
    assert first == second
    assert record["n_selected"] == 5
    assert record["strata"]["judge_disagreement"]["selected_count"] == 5
    assert record["strata"]["turn3_abandonment"]["selected_count"] == 0
    assert record["seed"] == 7


def test_smaller_stratum_is_exhausted_before_the_next():
    rows = [
        _item("math_001", "gemini-2.5-flash", "naive"),
        _item("math_002", "gemini-2.5-flash", "pedagogical"),
        _item("math_003", "gemini-2.5-flash-lite", "naive"),
    ]
    judge_a = {
        ("math_001", "gemini-2.5-flash", "naive"): "holds",
        ("math_002", "gemini-2.5-flash", "pedagogical"): "holds",
        ("math_003", "gemini-2.5-flash-lite", "naive"): "caves",
    }
    judge_b = {
        ("math_001", "gemini-2.5-flash", "naive"): "caves",
        ("math_002", "gemini-2.5-flash", "pedagogical"): "holds",
        ("math_003", "gemini-2.5-flash-lite", "naive"): "caves",
    }
    _chosen, record = select_sample(rows, judge_a, judge_b, 2, seed=1)
    assert record["strata"]["judge_disagreement"]["selected_count"] == 1
    assert record["strata"]["turn3_abandonment"]["selected_count"] == 1
    assert record["n_selected"] == 2


def test_historical_builder_does_not_reproduce_the_frozen_key():
    transcripts = load_jsonl(ROOT / "runs" / "transcripts.jsonl")
    legacy = legacy_unbounded_selection(
        transcripts,
        turn3_stance_map(load_jsonl(ROOT / "runs" / "scored.jsonl")),
        turn3_stance_map(load_jsonl(ROOT / "runs" / "scored_groq.jsonl")),
    )
    emitted = legacy["emitted_when_n_is_80"]
    historical = {(row["case_id"], row["model"], row["condition"]) for row in load_csv(ROOT / "rating_key.csv")}
    assert len(emitted) == 86
    assert len(set(emitted) & historical) == 79
    chosen, record = select_sample(
        transcripts,
        turn3_stance_map(load_jsonl(ROOT / "runs" / "scored.jsonl")),
        turn3_stance_map(load_jsonl(ROOT / "runs" / "scored_groq.jsonl")),
        80,
        7,
    )
    assert len(chosen) == 80
    assert record["n_requested"] == 80


def test_frozen_rating_key_cannot_be_replaced(tmp_path):
    with pytest.raises(SystemExit):
        assert_writable(ROOT / "rating_key.csv", ROOT)
    rows = [_item("math_001", "gemini-2.5-flash", "naive")]
    chosen, record = select_sample(rows, {}, {}, 1, 1)
    target = tmp_path / "sample"
    write_sample(target, chosen, record, rows, {}, {}, [{"id": "math_001", "question": "q"}], ROOT)
    with pytest.raises(SystemExit):
        write_sample(target, chosen, record, rows, {}, {}, [{"id": "math_001", "question": "q"}], ROOT)
    saved = json.loads((target / "selection.json").read_text(encoding="utf-8"))
    assert saved["n_selected"] == 1
    assert (ROOT / "rating_key.csv").exists()
