"""Trusted manifest of the frozen pilot files.

Ordinary reproduction loads the committed manifest and checks hashes.
Initialization is a separate command. It refuses to overwrite a manifest
that already exists, and it hashes blobs from the declared original commit.
"""

import json
import subprocess
import tempfile
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


def _manifest_text(payload):
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _git_bytes(root, commit, relative):
    result = subprocess.run(
        ["git", "show", "%s:%s" % (commit, relative)],
        cwd=str(root),
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise SystemExit(
            "refusing to build a manifest from working-tree files. "
            "git show %s:%s failed: %s" % (commit, relative, detail)
        )
    return result.stdout


def build_manifest_from_commit(root, commit=None):
    """Hash the frozen paths as stored at the original commit."""
    root = Path(root)
    commit = commit or ORIGINAL_COMMIT
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        for relative in FROZEN_RELATIVE:
            dest = tmp / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(_git_bytes(root, commit, relative))
        return build_manifest(tmp)


def initialize_manifest(root, path, commit=None):
    path = Path(path)
    if path.exists():
        raise SystemExit(
            "refusing to overwrite trusted manifest %s. "
            "Initialization does not replace an existing baseline." % path
        )
    payload = build_manifest_from_commit(root, commit)
    path.write_text(_manifest_text(payload), encoding="utf-8")
    return payload


def verify_trusted_manifest(root, path):
    """Return integrity problems. An empty list means the frozen files match."""
    root = Path(root)
    path = Path(path)
    if not path.exists():
        return [{"path": str(path), "reason": "missing_manifest", "detail": "trusted manifest is absent"}]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        return [{"path": str(path), "reason": "malformed_manifest", "detail": str(exc)}]
    if not isinstance(manifest, dict) or not isinstance(manifest.get("frozen_files"), list):
        return [{
            "path": str(path),
            "reason": "malformed_manifest",
            "detail": "frozen_files must be a list",
        }]
    problems = []
    listed = {}
    for entry in manifest["frozen_files"]:
        if not isinstance(entry, dict) or "path" not in entry or "sha256" not in entry:
            problems.append({
                "path": str(path),
                "reason": "malformed_manifest",
                "detail": "a frozen_files entry is missing path or sha256",
            })
            continue
        listed[entry["path"]] = entry
    if any(item["reason"] == "malformed_manifest" for item in problems):
        return problems
    expected = list(FROZEN_RELATIVE)
    for relative in expected:
        if relative not in listed:
            problems.append({
                "path": relative,
                "reason": "incomplete_inventory",
                "detail": "frozen file is not listed in the trusted manifest",
            })
    for relative, entry in listed.items():
        if relative not in expected:
            problems.append({
                "path": relative,
                "reason": "incomplete_inventory",
                "detail": "manifest lists a path outside the expected frozen inventory",
            })
            continue
        file_path = root / relative
        if not file_path.is_file():
            problems.append({"path": relative, "reason": "missing_file", "detail": "frozen file is absent"})
            continue
        current = sha256_file(file_path)
        if current != entry["sha256"]:
            problems.append({
                "path": relative,
                "reason": "hash_mismatch",
                "manifest": entry["sha256"],
                "current": current,
                "detail": "current bytes do not match the trusted manifest",
            })
    return problems


def format_integrity_problems(problems):
    lines = ["%d frozen-evidence integrity problem(s)" % len(problems)]
    for item in problems:
        if item["reason"] == "hash_mismatch":
            lines.append(
                "hash_mismatch\t%s\tmanifest %s\tcurrent %s"
                % (item["path"], item["manifest"], item["current"])
            )
        else:
            lines.append("%s\t%s\t%s" % (item["reason"], item["path"], item.get("detail", "")))
    return "\n".join(lines)
