"""Validator regressions, including the three frozen GPT-OSS defects."""

import json

from audit.protect import repo_root
from audit.validate import (
    validate_cases,
    validate_human,
    validate_repository,
    validate_scored_records,
    validate_transcript_records,
)

ROOT = repo_root()
KNOWN = {
    "spell_002 / gemini-2.5-flash / naive",
    "math_004 / gemini-2.5-flash-lite / pedagogical",
    "math_016 / gemini-2.5-flash-lite / naive",
}


def _row(rec, line=1):
    return {"line": line, "rec": rec}


def _transcript(case_id="math_001", model="gemini-2.5-flash", condition="naive"):
    return {
        "case_id": case_id,
        "model": model,
        "condition": condition,
        "turns": [
            {"turn": 1, "child": "one", "model": "tutor one"},
            {"turn": 2, "child": "two", "model": "tutor two"},
            {"turn": 3, "child": "three", "model": "tutor three"},
        ],
    }


def _scored(transcript, stances):
    rec = json.loads(json.dumps(transcript))
    rec["scores"] = {
        "per_turn": [{"turn": index, "stance": stance} for index, stance in stances],
        "warmth": 4,
        "growth_encouragement": 4,
        "age_appropriate": 4,
        "fake_praise": False,
        "corrected": True,
    }
    return rec


def test_repository_flags_only_the_three_known_groq_defects():
    issues = validate_repository(ROOT)
    flagged = {(issue.code, issue.record_id) for issue in issues}
    assert flagged == {("uncertain_turn_alignment", record_id) for record_id in KNOWN}
    for issue in issues:
        assert "truncated" in issue.detail or "not truncated" in issue.detail


def test_missing_extra_and_duplicate_turns():
    transcript = _transcript()
    source = {("math_001", "gemini-2.5-flash", "naive"): _row(transcript)}
    missing = _scored(transcript, [(1, "holds"), (3, "holds")])
    extra = _scored(transcript, [(1, "holds"), (2, "holds"), (3, "holds"), (4, "holds")])
    duplicate = _scored(transcript, [(1, "holds"), (2, "holds"), (2, "hedges"), (3, "holds")])
    issues = validate_scored_records(
        [_row(missing), _row(extra, 2), _row(duplicate, 3)],
        source,
        "gemini",
    )
    codes = {issue.code for issue in issues}
    assert "uncertain_turn_alignment" in codes
    assert "duplicate_judge_turn" in codes
    assert any(issue.record_id == "math_001 / gemini-2.5-flash / naive" for issue in issues)


def test_invalid_stance_and_tone_type():
    transcript = _transcript()
    source = {("math_001", "gemini-2.5-flash", "naive"): _row(transcript)}
    rec = _scored(transcript, [(1, "holds"), (2, "holds"), (3, "agrees")])
    rec["scores"]["warmth"] = "4"
    rec["scores"]["fake_praise"] = 1
    issues = validate_scored_records([_row(rec)], source, "gemini")
    codes = {issue.code for issue in issues}
    assert "invalid_stance" in codes
    assert "invalid_tone" in codes
    assert "invalid_boolean" in codes


def test_duplicate_transcript_key_and_missing_pair_coverage():
    first = _transcript()
    second = _transcript()
    rows = [_row(first, 1), _row(second, 2)]
    issues = validate_transcript_records(rows, ["math_001"], ["gemini-2.5-flash"], ["naive", "pedagogical"])
    codes = {issue.code for issue in issues}
    assert "duplicate_transcript_key" in codes
    assert "missing_transcript" in codes
    missing = [issue for issue in issues if issue.code == "missing_transcript"]
    assert missing[0].record_id == "math_001 / gemini-2.5-flash / pedagogical"


def test_transcript_text_mismatch():
    source_rec = _transcript()
    judged = _scored(source_rec, [(1, "holds"), (2, "holds"), (3, "holds")])
    judged["turns"][2]["model"] = "different tutor text"
    issues = validate_scored_records(
        [_row(judged)],
        {("math_001", "gemini-2.5-flash", "naive"): _row(source_rec)},
        "gemini",
    )
    assert any(issue.code == "transcript_text_mismatch" for issue in issues)


def test_consensus_binary_mapping_mismatch():
    key = [{"rating_id": "R001", "case_id": "math_001", "model": "gemini-2.5-flash", "condition": "naive"}]
    rater = {
        "rating_id": "R001",
        "t2_stance": "holds",
        "t3_stance": "caves",
        "warmth_1to5": "4",
        "growth_1to5": "4",
        "fake_praise_0or1": "0",
        "T1_child": "one",
        "T1_tutor": "tutor one",
        "T2_child": "two",
        "T2_tutor": "tutor two",
        "T3_child": "three",
        "T3_tutor": "tutor three",
    }
    other = dict(rater)
    other["t3_stance"] = "holds"
    consensus = [{"rating_id": "R001", "consensus_t3_stance": "caves", "consensus_holds_or_abandon": "holds"}]
    adjudication = [{
        "rating_id": "R001",
        "Mohtasham_t3": "holds",
        "Muizza_t3": "caves",
        "consensus_t3_stance": "caves",
        "consensus_holds_or_abandon": "holds",
        "T1_child": "one",
        "T1_tutor": "tutor one",
        "T2_child": "two",
        "T2_tutor": "tutor two",
        "T3_child": "three",
        "T3_tutor": "tutor three",
    }]
    transcript = _transcript()
    issues = validate_human(
        key,
        {"Muizza": [rater], "Mohtasham": [other]},
        consensus,
        adjudication,
        {("math_001", "gemini-2.5-flash", "naive"): _row(transcript)},
    )
    assert any(issue.code == "consensus_binary_mismatch" and issue.record_id == "R001" for issue in issues)


def test_duplicate_case_ids():
    issues = validate_cases([{"id": "math_001"}, {"id": "math_001"}])
    assert issues[0].code == "duplicate_case_id"
    assert issues[0].record_id == "math_001"


def test_validate_command_exits_nonzero():
    from audit.__main__ import main
    assert main(["validate", "--root", str(ROOT)]) == 1
