"""The license scope stays path-specific and does not clear the open items."""

from pathlib import Path

import pytest

from audit.protect import assert_writable, repo_root

ROOT = repo_root()


def test_license_scope_names_the_grants_and_the_exclusions():
    text = (ROOT / "LICENSING.md").read_text(encoding="utf-8")
    mit = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT" in mit
    assert "Copyright (c) 2026 Muizza Muayqeeb Akram" in mit
    assert "CC BY 4.0" in text or "Attribution 4.0" in text
    for path in (
        "runs/transcripts.jsonl",
        "runs/scored.jsonl",
        "runs/scored_groq.jsonl",
        "rating_key.csv",
        "rater_Muizza.csv",
        "rater_Mohtasham.csv",
        "adjudication_filled.csv",
        "consensus_labels.csv",
    ):
        assert path in text
    cc_by = text.split("## Author-owned research materials, CC BY 4.0", 1)[1].split("## Model outputs", 1)[0]
    consent = text.split("## Individual ratings, adjudication, and consensus labels", 1)[1].split("## Unresolved", 1)[0]
    assert "consensus_labels.csv" not in cc_by
    assert "consensus_labels.csv" in consent
    assert "future license grant" in consent
    assert "not reviewed" in text
    assert "consent" in text
    assert "scenarios.py" in text


def test_validated_figure_dir_is_writable_and_historical_figures_are_not():
    with pytest.raises(SystemExit):
        assert_writable(ROOT / "figures" / "fig1_abandonment_by_turn.png", ROOT)
    allowed = assert_writable(ROOT / "figures" / "validated_v2" / "fig1_abandonment_by_turn.png", ROOT)
    assert Path(allowed).name == "fig1_abandonment_by_turn.png"
