"""Deterministic manifest of the frozen pilot files."""

import json
from pathlib import Path

from audit.constants import CONDITIONS, FROZEN_RELATIVE, ORIGINAL_COMMIT, TUTOR_MODELS
from audit.io import file_size, load_cases, load_csv, load_jsonl, sha256_file


def build_manifest(root):
    root = Path(root)
    files = []
    for relative in FROZEN_RELATIVE:
        path = root / relative
        files.append({
            "path": relative,
            "sha256": sha256_file(path),
            "bytes": file_size(path),
        })
    cases = load_cases(root / "test_cases.json")
    transcripts = load_jsonl(root / "runs" / "transcripts.jsonl")
    gemini = load_jsonl(root / "runs" / "scored.jsonl")
    groq = load_jsonl(root / "runs" / "scored_groq.jsonl")
    with open(root / "generation_metadata.json", encoding="utf-8") as handle:
        historical_metadata = json.load(handle)
    case_ids = [case["id"] for case in cases]
    return {
        "original_commit": ORIGINAL_COMMIT,
        "frozen_files": files,
        "record_counts": {
            "cases": len(cases),
            "transcripts": len(transcripts),
            "gemini_judge_records": len(gemini),
            "gptoss_judge_records": len(groq),
            "rating_key_rows": len(load_csv(root / "rating_key.csv")),
            "rater_muizza_rows": len(load_csv(root / "rater_Muizza.csv")),
            "rater_mohtasham_rows": len(load_csv(root / "rater_Mohtasham.csv")),
            "adjudication_rows": len(load_csv(root / "adjudication_filled.csv")),
            "consensus_rows": len(load_csv(root / "consensus_labels.csv")),
        },
        "identifier_scheme": {
            "case_id": "prefix_NNN from test_cases.json. Observed prefixes: %s" % sorted({case_id.split("_")[0] for case_id in case_ids}),
            "case_ids": case_ids,
            "transcript_key": ["case_id", "model", "condition"],
            "models": list(TUTOR_MODELS),
            "conditions": list(CONDITIONS),
            "turns": [1, 2, 3],
            "rating_id": "R001-R080 in the frozen rating_key.csv. Future samples use a different id prefix and a new directory.",
        },
        "historical_generation_metadata": historical_metadata,
        "known_malformed_judge_records": [
            {
                "file": "runs/scored_groq.jsonl",
                "record_id": "spell_002 / gemini-2.5-flash / naive",
                "scored_turn_ids": [1, 2, 3, 4],
                "handling": "left unchanged; turn alignment flagged uncertain",
            },
            {
                "file": "runs/scored_groq.jsonl",
                "record_id": "math_004 / gemini-2.5-flash-lite / pedagogical",
                "scored_turn_ids": [1, 2, 3, 4],
                "handling": "left unchanged; turn alignment flagged uncertain",
            },
            {
                "file": "runs/scored_groq.jsonl",
                "record_id": "math_016 / gemini-2.5-flash-lite / naive",
                "scored_turn_ids": [1, 2, 3, 4, 5, 6],
                "handling": "left unchanged; turn alignment flagged uncertain",
            },
        ],
        "known_missing_or_unverified_settings": [
            "Tutor calls in the historical models.py sent no generationConfig. Temperature, max tokens, and the returned model version were not logged.",
            "The Gemini judge request in the historical judge.py sent no temperature field. The provider default at call time was not recorded. Do not read the old metadata temperature 0 as a verified Gemini judge setting.",
            "The Groq judge builder sets temperature 0, max_tokens 512, and reasoning_effort low for gpt-oss. No stored HTTP request or response confirms the historical call used that body.",
            "Raw judge completions were not retained. Temperature 0 would not by itself recover them, and the Gemini call did not set temperature.",
            "Transcript files have no timestamps, request ids, or system-prompt hashes.",
            "The seed, stratum membership, and exact inclusion rule for the historical 80 rating ids were not saved. Rerunning the committed sampler does not reproduce rating_key.csv.",
            "Returned model versions and finish reasons were not saved.",
        ],
    }


def write_manifest(root, path):
    payload = build_manifest(root)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    Path(path).write_text(text, encoding="utf-8")
    return payload


def hashes_match(root, manifest):
    root = Path(root)
    mismatches = []
    for entry in manifest["frozen_files"]:
        current = sha256_file(root / entry["path"])
        if current != entry["sha256"]:
            mismatches.append({"path": entry["path"], "manifest": entry["sha256"], "current": current})
    return mismatches
