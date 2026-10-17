"""The offline audit command preserves evidence and writes the summary."""

import json

from audit.io import sha256_file
from audit.protect import repo_root
from audit.reproduce import run

ROOT = repo_root()
FROZEN = [
    "runs/transcripts.jsonl",
    "runs/scored.jsonl",
    "runs/scored_groq.jsonl",
    "rating_key.csv",
    "rater_Muizza.csv",
    "rater_Mohtasham.csv",
    "adjudication_filled.csv",
    "consensus_labels.csv",
    "test_cases.json",
    "generation_metadata.json",
    "figures/fig1_abandonment_by_turn.png",
]


def test_reproduce_preserves_evidence_and_writes_figures(tmp_path):
    before = {path: sha256_file(ROOT / path) for path in FROZEN}
    manifest_before = (ROOT / "evidence_manifest.json").read_bytes()
    code = run(ROOT, tmp_path)
    after = {path: sha256_file(ROOT / path) for path in FROZEN}
    assert before == after
    assert (ROOT / "evidence_manifest.json").read_bytes() == manifest_before
    assert not (tmp_path / "evidence_manifest.json").exists()
    assert code == 0
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["published_checks"]["matches_published_gemini_headline"] is True
    assert summary["human_sample"]["committed_builder_emits_on_these_files"] == 86
    assert summary["human_sample"]["overlap_with_frozen_key"] == 79
    assert (tmp_path / "figures" / "fig1_abandonment_by_turn.png").exists()
    assert (tmp_path / "figures" / "CAPTIONS.md").exists()
    provenance = (tmp_path / "figures" / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "../fig1_abandonment_by_turn.png" in provenance
    assert "spell_002 / gemini-2.5-flash / naive" in provenance
    sensitivity = json.loads((tmp_path / "figures" / "sensitivity.json").read_text(encoding="utf-8"))
    assert sensitivity["replacement_judge_calls"] == 0
    assert "math_016 / gemini-2.5-flash-lite / naive" in sensitivity["flagged_records_left_unchanged"]
    validation = (tmp_path / "validation.txt").read_text(encoding="utf-8")
    assert "spell_002 / gemini-2.5-flash / naive" in validation
    manifest = json.loads(manifest_before)
    assert manifest["original_commit"] == "c6fdc51dacefc97b8905d9a92a0154814ee22abd"
    assert manifest["record_counts"]["transcripts"] == 192
