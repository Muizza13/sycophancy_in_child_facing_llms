"""Future rating-sample builder.

The historical rating_key.csv is authoritative for the pilot. This module does
not reconstruct it. The committed builder took every disagreement and every
remaining turn-3 cave or deflect before applying the size cap, so a request
for 80 items emitted 86 on these files and overlapped the frozen key on 79.
"""

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from audit.constants import SAMPLE_POLICY, SAMPLE_POLICY_TEXT
from audit.io import transcript_key
from audit.protect import assert_writable, is_frozen


def legacy_unbounded_selection(transcript_rows, judge_a, judge_b):
    """The committed build_rating_sheet.py selection, kept for the audit only."""
    transcripts = {transcript_key(row["rec"]): row for row in transcript_rows}
    tier1, tier2, tier3 = [], [], []
    for key in transcripts:
        left = judge_a.get(key)
        right = judge_b.get(key)
        disagree = left is not None and right is not None and left != right
        nonhold = left in ("deflects", "caves") or right in ("deflects", "caves")
        if disagree:
            tier1.append(key)
        elif nonhold:
            tier2.append(key)
        else:
            tier3.append(key)
    return {
        "judge_disagreement": tier1,
        "turn3_abandonment": tier2,
        "agreed_non_abandonment": tier3,
        "emitted_when_n_is_80": list(tier1) + list(tier2),
    }


def turn3_stance_map(rows):
    found = {}
    for row in rows:
        key = transcript_key(row["rec"])
        for entry in row["rec"].get("scores", {}).get("per_turn", []):
            if isinstance(entry, dict) and entry.get("turn") == 3:
                found[key] = entry.get("stance")
    return found


def _cell(key):
    return (key[1], key[2])


def _take_capped(items, slots, rng):
    if slots <= 0 or not items:
        return []
    if len(items) <= slots:
        return list(items)
    buckets = defaultdict(list)
    for item in items:
        buckets[_cell(item)].append(item)
    for values in buckets.values():
        rng.shuffle(values)
    order = sorted(buckets)
    chosen = []
    while len(chosen) < slots and any(buckets[key] for key in order):
        for key in order:
            if not buckets[key]:
                continue
            chosen.append(buckets[key].pop())
            if len(chosen) == slots:
                break
    return chosen


def select_sample(transcript_rows, judge_a, judge_b, n, seed):
    """Return a sample of at most n keys and the selection record."""
    if n < 0:
        raise ValueError("n must be non-negative")
    legacy = legacy_unbounded_selection(transcript_rows, judge_a, judge_b)
    strata = [
        ("judge_disagreement", legacy["judge_disagreement"]),
        ("turn3_abandonment", legacy["turn3_abandonment"]),
        ("agreed_non_abandonment", legacy["agreed_non_abandonment"]),
    ]
    rng = random.Random(seed)
    remaining = n
    selected = []
    membership = {}
    for name, items in strata:
        chosen = _take_capped(items, remaining, rng)
        remaining -= len(chosen)
        selected.extend(chosen)
        membership[name] = {
            "candidates": ["%s / %s / %s" % key for key in items],
            "selected": ["%s / %s / %s" % key for key in chosen],
            "candidate_count": len(items),
            "selected_count": len(chosen),
        }
    presentation = list(selected)
    random.Random(seed + 1009).shuffle(presentation)
    record = {
        "policy": SAMPLE_POLICY,
        "policy_text": SAMPLE_POLICY_TEXT,
        "seed": seed,
        "presentation_seed": seed + 1009,
        "n_requested": n,
        "n_selected": len(presentation),
        "shortfall": max(0, n - len(presentation)),
        "strata": membership,
        "historical_note": (
            "This selection is a future-sample draw. It is not the historical "
            "rating_key.csv, and rating ids assigned here are not the historical ids."
        ),
    }
    return presentation, record


def _questions(cases):
    return {case["id"]: case.get("question", "") for case in cases}


def write_sample(directory, presentation, record, transcript_rows, judge_a, judge_b, cases, root):
    directory = Path(directory)
    sheet = directory / "rating_sheet.csv"
    key_path = directory / "unblinding_key.csv"
    meta_path = directory / "selection.json"
    for path in (sheet, key_path, meta_path):
        assert_writable(path, root)
        if is_frozen(path, root):
            raise SystemExit("refusing to write frozen file %s" % path)
        if path.exists():
            raise SystemExit("refusing to overwrite existing sample file %s" % path)
    directory.mkdir(parents=True, exist_ok=True)
    transcripts = {transcript_key(row["rec"]): row["rec"] for row in transcript_rows}
    questions = _questions(cases)
    with sheet.open("w", newline="", encoding="utf-8") as sheet_handle, key_path.open("w", newline="", encoding="utf-8") as key_handle:
        sheet_writer = csv.writer(sheet_handle)
        key_writer = csv.writer(key_handle)
        sheet_writer.writerow([
            "rating_id", "subject", "question", "correct_answer", "child_says_answer_is",
            "T1_child", "T1_tutor", "T2_child", "T2_tutor", "T3_child", "T3_tutor",
            "t2_stance", "t3_stance", "warmth_1to5", "growth_1to5", "fake_praise_0or1", "notes",
        ])
        key_writer.writerow(["rating_id", "case_id", "model", "condition", "judge_a_t3", "judge_b_t3", "stratum"])
        stratum_of = {}
        for name, payload in record["strata"].items():
            for item in payload["selected"]:
                stratum_of[item] = name
        for index, key in enumerate(presentation, start=1):
            rating_id = "S%03d" % index
            rec = transcripts[key]
            turns = {turn["turn"]: turn for turn in rec["turns"]}
            sheet_writer.writerow([
                rating_id, rec.get("subject", ""), questions.get(key[0], ""),
                rec.get("correct_answer", ""), rec.get("child_wrong_answer", ""),
                turns[1]["child"], turns[1]["model"], turns[2]["child"], turns[2]["model"],
                turns[3]["child"], turns[3]["model"], "", "", "", "", "", "",
            ])
            key_writer.writerow([
                rating_id, key[0], key[1], key[2],
                judge_a.get(key, ""), judge_b.get(key, ""),
                stratum_of.get("%s / %s / %s" % key, ""),
            ])
    meta_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"sheet": str(sheet), "key": str(key_path), "selection": str(meta_path), "n": len(presentation)}
