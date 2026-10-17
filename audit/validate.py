"""Strict checks for the frozen pilot files.

Issues name the record id. The command exits nonzero when any issue is present.
Known historical defects are reported, not repaired.
"""

from collections import Counter, defaultdict
from pathlib import Path

from audit.constants import (
    ABANDON,
    BINARY_ABANDONMENT,
    BINARY_NON_ABANDONMENT,
    BOOL_FIELDS,
    CONDITIONS,
    STANCES,
    TONE_FIELDS,
    TUTOR_MODELS,
    TURN_IDS,
)
from audit.io import format_key, load_cases, load_csv, load_jsonl, transcript_key


class Issue:
    def __init__(self, code, record_id, detail):
        self.code = code
        self.record_id = record_id
        self.detail = detail

    def as_dict(self):
        return {"code": self.code, "record_id": self.record_id, "detail": self.detail}


def _tone_ok(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return 1 <= value <= 5


def _norm(value):
    return (value or "").strip().lower()


def validate_cases(cases):
    issues = []
    counts = Counter(case["id"] for case in cases)
    for case_id, count in sorted(counts.items()):
        if count != 1:
            issues.append(Issue(
                "duplicate_case_id",
                case_id,
                "case id appears %d times" % count,
            ))
    return issues


def validate_transcript_records(rows, case_ids, models, conditions):
    issues = []
    seen = defaultdict(list)
    expected = {
        (case_id, model, condition)
        for case_id in case_ids
        for model in models
        for condition in conditions
    }
    found = set()
    for row in rows:
        rec = row["rec"]
        key = transcript_key(rec)
        found.add(key)
        seen[key].append(row["line"])
        record_id = format_key(key)
        turns = rec.get("turns")
        if not isinstance(turns, list):
            issues.append(Issue("transcript_turns", record_id, "turns is not a list"))
            continue
        ids = [turn.get("turn") if isinstance(turn, dict) else None for turn in turns]
        if ids != list(TURN_IDS):
            issues.append(Issue(
                "transcript_turns",
                record_id,
                "expected turn ids 1, 2, 3; found %s" % ids,
            ))
        for turn in turns if all(isinstance(turn, dict) for turn in turns) else []:
            child = turn.get("child")
            tutor = turn.get("model")
            if not isinstance(child, str) or not child.strip():
                issues.append(Issue(
                    "empty_child_message",
                    "%s / turn %s" % (record_id, turn.get("turn")),
                    "child message is empty",
                ))
            if not isinstance(tutor, str) or not tutor.strip():
                issues.append(Issue(
                    "empty_tutor_message",
                    "%s / turn %s" % (record_id, turn.get("turn")),
                    "tutor message is empty",
                ))
    for key, lines in sorted(seen.items()):
        if len(lines) > 1:
            issues.append(Issue(
                "duplicate_transcript_key",
                format_key(key),
                "lines %s" % lines,
            ))
    for key in sorted(expected - found):
        issues.append(Issue("missing_transcript", format_key(key), "expected combination is absent"))
    for key in sorted(found - expected):
        issues.append(Issue("unexpected_transcript", format_key(key), "not in the expected case/model/condition grid"))
    return issues


def _turn_alignment_issues(record_id, per_turn):
    issues = []
    if not isinstance(per_turn, list):
        return [Issue("uncertain_turn_alignment", record_id, "per_turn is not a list")]
    ids = []
    for entry in per_turn:
        if not isinstance(entry, dict):
            issues.append(Issue("uncertain_turn_alignment", record_id, "per_turn entry is not an object"))
            continue
        ids.append(entry.get("turn"))
        if entry.get("stance") not in STANCES:
            issues.append(Issue(
                "invalid_stance",
                record_id,
                "turn %s stance %r is outside %s" % (entry.get("turn"), entry.get("stance"), list(STANCES)),
            ))
    if len(ids) != len(set(ids)):
        issues.append(Issue(
            "duplicate_judge_turn",
            record_id,
            "duplicate turn ids %s" % ids,
        ))
    if ids != list(TURN_IDS):
        issues.append(Issue(
            "uncertain_turn_alignment",
            record_id,
            "expected exactly turn ids 1, 2 and 3; found %s. "
            "Alignment is uncertain. Labels were not truncated or remapped." % ids,
        ))
    return issues


def validate_scored_records(rows, transcripts_by_key, judge_name):
    issues = []
    seen = defaultdict(list)
    for row in rows:
        rec = row["rec"]
        key = transcript_key(rec)
        record_id = format_key(key)
        seen[key].append(row["line"])
        source = transcripts_by_key.get(key)
        if source is None:
            issues.append(Issue("judge_without_transcript", record_id, "%s record has no source transcript" % judge_name))
        else:
            left = rec.get("turns")
            right = source["rec"].get("turns")
            if left != right:
                issues.append(Issue(
                    "transcript_text_mismatch",
                    record_id,
                    "%s turns do not match the source transcript text" % judge_name,
                ))
        scores = rec.get("scores") or {}
        issues.extend(_turn_alignment_issues(record_id, scores.get("per_turn")))
        for field in TONE_FIELDS:
            if not _tone_ok(scores.get(field)):
                issues.append(Issue(
                    "invalid_tone",
                    record_id,
                    "%s = %r" % (field, scores.get(field)),
                ))
        for field in BOOL_FIELDS:
            if not isinstance(scores.get(field), bool):
                issues.append(Issue(
                    "invalid_boolean",
                    record_id,
                    "%s = %r (%s)" % (field, scores.get(field), type(scores.get(field)).__name__),
                ))
    for key, lines in sorted(seen.items()):
        if len(lines) > 1:
            issues.append(Issue(
                "duplicate_judge_record",
                format_key(key),
                "%s lines %s" % (judge_name, lines),
            ))
    expected = set(transcripts_by_key)
    found = set(seen)
    for key in sorted(expected - found):
        issues.append(Issue("missing_judge_record", format_key(key), "%s record is absent" % judge_name))
    for key in sorted(found - expected):
        issues.append(Issue("unexpected_judge_record", format_key(key), "%s record is not in the transcript file" % judge_name))
    return issues


def _binary_for_stance(stance):
    if stance in ABANDON:
        return BINARY_ABANDONMENT
    if stance in STANCES:
        return BINARY_NON_ABANDONMENT
    return None


def validate_human(key_rows, rater_rows, consensus_rows, adjudication_rows, transcripts_by_key):
    issues = []
    key_ids = [row["rating_id"] for row in key_rows]
    if len(key_ids) != len(set(key_ids)):
        dupes = sorted(i for i, count in Counter(key_ids).items() if count > 1)
        for rating_id in dupes:
            issues.append(Issue("duplicate_rating_id", rating_id, "duplicated in rating_key.csv"))
    key_by_id = {}
    for row in key_rows:
        key_by_id[row["rating_id"]] = row
        triple = (row["case_id"], row["model"], row["condition"])
        if triple not in transcripts_by_key:
            issues.append(Issue(
                "rating_key_without_transcript",
                row["rating_id"],
                "no transcript for %s" % format_key(triple),
            ))

    def check_sheet(rows, sheet_name, has_text):
        ids = [row["rating_id"] for row in rows]
        if len(ids) != len(set(ids)):
            for rating_id in sorted(i for i, count in Counter(ids).items() if count > 1):
                issues.append(Issue("duplicate_rating_id", rating_id, "duplicated in %s" % sheet_name))
        by_id = {}
        for row in rows:
            rating_id = row["rating_id"]
            by_id[rating_id] = row
            if rating_id not in key_by_id:
                issues.append(Issue("rating_id_not_in_key", rating_id, "%s id is not in rating_key.csv" % sheet_name))
                continue
            for column in ("t2_stance", "t3_stance"):
                stance = _norm(row.get(column))
                if stance not in STANCES:
                    issues.append(Issue("invalid_stance", rating_id, "%s %s = %r" % (sheet_name, column, row.get(column))))
            for column in ("warmth_1to5", "growth_1to5"):
                try:
                    value = float(row.get(column))
                except (TypeError, ValueError):
                    issues.append(Issue("invalid_tone", rating_id, "%s %s = %r" % (sheet_name, column, row.get(column))))
                    continue
                if not 1 <= value <= 5:
                    issues.append(Issue("invalid_tone", rating_id, "%s %s = %r" % (sheet_name, column, row.get(column))))
            if str(row.get("fake_praise_0or1", "")).strip() not in {"0", "1", "0.0", "1.0"}:
                issues.append(Issue(
                    "invalid_boolean",
                    rating_id,
                    "%s fake_praise_0or1 = %r" % (sheet_name, row.get("fake_praise_0or1")),
                ))
            if has_text and rating_id in key_by_id:
                mapped = key_by_id[rating_id]
                source = transcripts_by_key.get((mapped["case_id"], mapped["model"], mapped["condition"]))
                if source is not None:
                    turns = {turn["turn"]: turn for turn in source["rec"]["turns"]}
                    for turn_id in TURN_IDS:
                        child_col = "T%d_child" % turn_id
                        tutor_col = "T%d_tutor" % turn_id
                        if row.get(child_col) != turns[turn_id]["child"] or row.get(tutor_col) != turns[turn_id]["model"]:
                            issues.append(Issue(
                                "human_transcript_mismatch",
                                rating_id,
                                "%s turn %d text does not match the mapped source conversation" % (sheet_name, turn_id),
                            ))
                            break
        for rating_id in key_by_id:
            if rating_id not in by_id:
                issues.append(Issue("missing_human_rating", rating_id, "absent from %s" % sheet_name))
        return by_id

    muizza = check_sheet(rater_rows["Muizza"], "rater_Muizza.csv", True)
    mohtasham = check_sheet(rater_rows["Mohtasham"], "rater_Mohtasham.csv", False)

    consensus_by_id = {}
    consensus_ids = [row["rating_id"] for row in consensus_rows]
    if len(consensus_ids) != len(set(consensus_ids)):
        for rating_id in sorted(i for i, count in Counter(consensus_ids).items() if count > 1):
            issues.append(Issue("duplicate_rating_id", rating_id, "duplicated in consensus_labels.csv"))
    for row in consensus_rows:
        rating_id = row["rating_id"]
        consensus_by_id[rating_id] = row
        if rating_id not in key_by_id:
            issues.append(Issue("rating_id_not_in_key", rating_id, "consensus id is not in rating_key.csv"))
            continue
        stance = _norm(row.get("consensus_t3_stance"))
        binary = _norm(row.get("consensus_holds_or_abandon"))
        expected = _binary_for_stance(stance)
        if stance not in STANCES:
            issues.append(Issue("invalid_stance", rating_id, "consensus_t3_stance = %r" % row.get("consensus_t3_stance")))
        elif binary != expected:
            issues.append(Issue(
                "consensus_binary_mismatch",
                rating_id,
                "consensus_t3_stance %s maps to %s; file has %s. "
                "The stored token holds on this column means non-abandonment, not five-way holds."
                % (stance, expected, binary),
            ))
    for rating_id in key_by_id:
        if rating_id not in consensus_by_id:
            issues.append(Issue("missing_consensus", rating_id, "absent from consensus_labels.csv"))

    disagreements = []
    for rating_id, left in muizza.items():
        right = mohtasham.get(rating_id)
        if right is None:
            continue
        if _norm(left.get("t3_stance")) and _norm(right.get("t3_stance")) and _norm(left.get("t3_stance")) != _norm(right.get("t3_stance")):
            disagreements.append(rating_id)
    adjudication_ids = []
    for row in adjudication_rows:
        rating_id = row["rating_id"]
        adjudication_ids.append(rating_id)
        if rating_id not in key_by_id:
            issues.append(Issue("rating_id_not_in_key", rating_id, "adjudication id is not in rating_key.csv"))
            continue
        if _norm(row.get("Mohtasham_t3")) != _norm(mohtasham.get(rating_id, {}).get("t3_stance")):
            issues.append(Issue(
                "adjudication_rater_mismatch",
                rating_id,
                "Mohtasham_t3 %r does not match rater_Mohtasham.csv %r"
                % (row.get("Mohtasham_t3"), mohtasham.get(rating_id, {}).get("t3_stance")),
            ))
        if _norm(row.get("Muizza_t3")) != _norm(muizza.get(rating_id, {}).get("t3_stance")):
            issues.append(Issue(
                "adjudication_rater_mismatch",
                rating_id,
                "Muizza_t3 %r does not match rater_Muizza.csv %r"
                % (row.get("Muizza_t3"), muizza.get(rating_id, {}).get("t3_stance")),
            ))
        if _norm(row.get("Mohtasham_t3")) == _norm(row.get("Muizza_t3")):
            issues.append(Issue(
                "adjudication_not_a_disagreement",
                rating_id,
                "adjudication row records identical t3 labels",
            ))
        stance = _norm(row.get("consensus_t3_stance"))
        binary = _norm(row.get("consensus_holds_or_abandon"))
        expected = _binary_for_stance(stance)
        if expected is None or binary != expected:
            issues.append(Issue(
                "consensus_binary_mismatch",
                rating_id,
                "adjudication consensus %r / %r does not follow the abandonment mapping"
                % (row.get("consensus_t3_stance"), row.get("consensus_holds_or_abandon")),
            ))
        consensus = consensus_by_id.get(rating_id)
        if consensus is not None and (
            _norm(consensus.get("consensus_t3_stance")) != stance
            or _norm(consensus.get("consensus_holds_or_abandon")) != binary
        ):
            issues.append(Issue(
                "adjudication_consensus_mismatch",
                rating_id,
                "adjudication consensus does not match consensus_labels.csv",
            ))
        mapped = key_by_id[rating_id]
        source = transcripts_by_key.get((mapped["case_id"], mapped["model"], mapped["condition"]))
        if source is not None:
            turns = {turn["turn"]: turn for turn in source["rec"]["turns"]}
            for turn_id in TURN_IDS:
                if row.get("T%d_child" % turn_id) != turns[turn_id]["child"] or row.get("T%d_tutor" % turn_id) != turns[turn_id]["model"]:
                    issues.append(Issue(
                        "human_transcript_mismatch",
                        rating_id,
                        "adjudication turn %d text does not match the mapped source conversation" % turn_id,
                    ))
                    break
    if len(adjudication_ids) != len(set(adjudication_ids)):
        for rating_id in sorted(i for i, count in Counter(adjudication_ids).items() if count > 1):
            issues.append(Issue("duplicate_rating_id", rating_id, "duplicated in adjudication_filled.csv"))
    for rating_id in sorted(set(disagreements) - set(adjudication_ids)):
        issues.append(Issue("missing_adjudication", rating_id, "raters disagree on t3 and no adjudication row exists"))
    for rating_id in sorted(set(adjudication_ids) - set(disagreements)):
        issues.append(Issue("unexpected_adjudication", rating_id, "adjudication row is not a t3 disagreement between the rater sheets"))
    for rating_id in key_by_id:
        if rating_id in disagreements or rating_id not in muizza or rating_id not in mohtasham:
            continue
        agreed = _norm(muizza[rating_id].get("t3_stance"))
        consensus = consensus_by_id.get(rating_id)
        if consensus is not None and _norm(consensus.get("consensus_t3_stance")) != agreed:
            issues.append(Issue(
                "consensus_disagrees_with_unanimous_raters",
                rating_id,
                "raters both said %s; consensus file says %s" % (agreed, consensus.get("consensus_t3_stance")),
            ))
    return issues


def validate_repository(root):
    root = Path(root)
    cases = load_cases(root / "test_cases.json")
    transcripts = load_jsonl(root / "runs" / "transcripts.jsonl")
    gemini = load_jsonl(root / "runs" / "scored.jsonl")
    groq = load_jsonl(root / "runs" / "scored_groq.jsonl")
    key_rows = load_csv(root / "rating_key.csv")
    rater_rows = {
        "Muizza": load_csv(root / "rater_Muizza.csv"),
        "Mohtasham": load_csv(root / "rater_Mohtasham.csv"),
    }
    consensus_rows = load_csv(root / "consensus_labels.csv")
    adjudication_rows = load_csv(root / "adjudication_filled.csv")
    case_ids = [case["id"] for case in cases]
    issues = []
    issues.extend(validate_cases(cases))
    issues.extend(validate_transcript_records(transcripts, case_ids, TUTOR_MODELS, CONDITIONS))
    by_key = {transcript_key(row["rec"]): row for row in transcripts}
    issues.extend(validate_scored_records(gemini, by_key, "gemini"))
    issues.extend(validate_scored_records(groq, by_key, "gpt-oss"))
    issues.extend(validate_human(key_rows, rater_rows, consensus_rows, adjudication_rows, by_key))
    return issues


def format_issues(issues):
    lines = ["%d validation issue(s)" % len(issues)]
    for issue in issues:
        lines.append("%s\t%s\t%s" % (issue.code, issue.record_id, issue.detail))
    return "\n".join(lines)
