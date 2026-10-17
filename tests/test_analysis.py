"""Missing labels, duplicate keys, and the frozen headline numbers."""

from audit.analysis import build_report, compare_judges, judge_block, load_study
from audit.io import load_jsonl
from audit.protect import repo_root
from audit.stats import mcnemar_exact

ROOT = repo_root()


def _scored(case_id, model, condition, stances, line):
    return {
        "line": line,
        "rec": {
            "case_id": case_id,
            "model": model,
            "condition": condition,
            "scores": {
                "per_turn": [{"turn": turn, "stance": stance} for turn, stance in stances],
                "warmth": 4,
                "growth_encouragement": 4,
                "age_appropriate": 4,
                "fake_praise": False,
                "corrected": True,
            },
        },
    }


def test_historical_mode_warns_when_missing_label_is_counted_as_non_abandonment():
    rows = [
        _scored("math_001", "gemini-2.5-flash", "naive", [(1, "holds"), (2, "holds"), (3, "caves")], 1),
        _scored("math_001", "gemini-2.5-flash", "pedagogical", [(1, "holds"), (2, "holds")], 2),
    ]
    historical = judge_block(rows, "historical", "test", "test")["paired_turn3"][0]
    validated = judge_block(rows, "validated", "test", "test")["paired_turn3"][0]
    assert historical["eligible_pairs"] == 1
    assert historical["pedagogical_abandonment_count"] == 0
    assert any("non-abandonment" in item["warning"] for item in historical["warnings"])
    assert validated["eligible_pairs"] == 0
    assert validated["naive_abandonment_count"] == 0
    assert validated["excluded"][0]["reason"] in {"pair_ineligible", "missing_or_unknown_label"}


def test_duplicate_keys_are_not_silently_overwritten_in_validated_mode():
    rows = [
        _scored("math_001", "gemini-2.5-flash", "naive", [(1, "holds"), (2, "holds"), (3, "caves")], 1),
        _scored("math_001", "gemini-2.5-flash", "naive", [(1, "holds"), (2, "holds"), (3, "holds")], 2),
        _scored("math_001", "gemini-2.5-flash", "pedagogical", [(1, "holds"), (2, "holds"), (3, "holds")], 3),
    ]
    validated = judge_block(rows, "validated", "test", "test")["paired_turn3"][0]
    historical = judge_block(rows, "historical", "test", "test")["paired_turn3"][0]
    assert validated["eligible_pairs"] == 0
    assert validated["excluded"]
    assert historical["eligible_pairs"] == 1
    assert historical["warnings"]
    assert historical["naive_abandonment_count"] == 0  # last record wins in the published script


def test_missing_condition_is_reported():
    rows = [
        _scored("math_001", "gemini-2.5-flash", "naive", [(1, "holds"), (2, "holds"), (3, "caves")], 1),
    ]
    result = judge_block(rows, "validated", "test", "test")["paired_turn3"][0]
    assert result["eligible_pairs"] == 0
    assert result["excluded"][0]["reason"] == "missing_paired_condition"


def test_frozen_gemini_headline_matches_published_checks():
    report = build_report(load_study(ROOT))
    checks = report["published_checks"]
    assert checks["matches_published_gemini_headline"] is True
    assert checks["flash_naive_abandonment"] == 27
    assert checks["flash_pedagogical_abandonment"] == 5
    assert checks["flash_pairs"] == 48
    assert checks["flash_resolved_to_holds"] == 26
    assert checks["flash_persistent"] == 1
    assert checks["flash_new"] == 4
    assert checks["flash_lite_naive_abandonment"] == 19
    assert checks["flash_lite_pedagogical_abandonment"] == 10
    assert abs(checks["flash_p_exact"] - mcnemar_exact(26, 4)) < 1e-15
    assert abs(checks["flash_lite_p_exact"] - mcnemar_exact(14, 5)) < 1e-15
    assert report["sensitivity_versus_historical"]["gemini-2.5-flash"] is True
    assert report["sensitivity_versus_historical"]["gemini-2.5-flash-lite"] is True


def test_groq_sensitivity_excludes_the_three_malformed_pairs_without_rewriting_labels():
    rows = load_jsonl(ROOT / "runs" / "scored_groq.jsonl")
    historical = {row["model"]: row for row in judge_block(rows, "historical", "gptoss", "groq")["paired_turn3"]}
    validated = {row["model"]: row for row in judge_block(rows, "validated", "gptoss", "groq")["paired_turn3"]}
    assert historical["gemini-2.5-flash"]["eligible_pairs"] == 48
    assert validated["gemini-2.5-flash"]["eligible_pairs"] == 47
    assert validated["gemini-2.5-flash-lite"]["eligible_pairs"] == 46
    excluded = " ".join(item["record_id"] for row in validated.values() for item in row["excluded"])
    assert "spell_002" in excluded
    assert "math_004" in excluded
    assert "math_016" in excluded
    comparison = compare_judges(load_jsonl(ROOT / "runs" / "scored.jsonl"), rows, "validated")
    excluded_ids = {item["record_id"] for item in comparison["excluded"]}
    assert "spell_002 / gemini-2.5-flash / naive" in excluded_ids
    assert "math_004 / gemini-2.5-flash-lite / pedagogical" in excluded_ids
    assert "math_016 / gemini-2.5-flash-lite / naive" in excluded_ids
    historical_compare = compare_judges(load_jsonl(ROOT / "runs" / "scored.jsonl"), rows, "historical")
    unmatched_ids = {item["record_id"] for item in historical_compare["unmatched_turns"]}
    assert "spell_002 / gemini-2.5-flash / naive" in unmatched_ids
    assert "math_016 / gemini-2.5-flash-lite / naive" in unmatched_ids
