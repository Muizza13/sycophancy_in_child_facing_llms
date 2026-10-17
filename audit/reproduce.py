"""One offline command: validate, summarize, and draw figures."""

import json
from pathlib import Path

from audit.analysis import build_report, figure_inputs, load_study
from audit.figures import render
from audit.manifest import build_manifest, hashes_match, write_manifest
from audit.sample import legacy_unbounded_selection, turn3_stance_map
from audit.validate import format_issues, validate_repository


def _json_ready(value):
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def human_sample_note(study):
    judge_a = turn3_stance_map(study["gemini"])
    judge_b = turn3_stance_map(study["groq"])
    legacy = legacy_unbounded_selection(study["transcripts"], judge_a, judge_b)
    emitted = [tuple(key) for key in legacy["emitted_when_n_is_80"]]
    historical = {(row["case_id"], row["model"], row["condition"]) for row in study["key"]}
    return {
        "frozen_rating_key": "rating_key.csv",
        "frozen_items": len(historical),
        "committed_builder_requested_n": 80,
        "committed_builder_emits_on_these_files": len(emitted),
        "overlap_with_frozen_key": len(set(emitted) & historical),
        "exact_historical_procedure": (
            "Not recoverable. The repository does not record the seed, the stratum "
            "membership, or the inclusion rule that produced the 80 historical rating ids. "
            "The committed builder, run now, asks for 80 and emits every judge disagreement "
            "plus every remaining turn-3 cave or deflect, which is more than 80, and the "
            "overlap with the frozen key is incomplete. rating_key.csv remains the map."
        ),
    }


FIGURE_NAMES = (
    "fig1_abandonment_by_turn.png",
    "fig2_turn3_abandonment.png",
    "fig3_cave_vs_deflect.png",
    "fig4_judge_tone_gap.png",
    "fig5_agreement_kappa.png",
)

SLIM_FIELDS = (
    "model",
    "eligible_pairs",
    "naive_abandonment_count",
    "pedagogical_abandonment_count",
    "discordant_naive_only",
    "discordant_pedagogical_only",
    "p_exact",
    "resolved_to_five_way_holds",
    "persistent_abandonment",
    "persistent_case_ids",
    "new_abandonment",
    "new_abandonment_case_ids",
    "excluded",
    "warnings",
)


def _slim_paired(block):
    rows = []
    for row in block["paired_turn3"]:
        rows.append({field: row[field] for field in SLIM_FIELDS})
    return rows


def sensitivity_document(report):
    agreement = {}
    for name, block in report["agreement"].items():
        if isinstance(block, dict) and "kappa" in block:
            agreement[name] = {
                "n": block["n"],
                "raw_agreement": block["raw_agreement"],
                "kappa": block["kappa"],
            }
    return {
        "replacement_judge_calls": 0,
        "flagged_records_left_unchanged": [
            issue["record_id"]
            for issue in report["validation_issues"]
            if issue["code"] == "uncertain_turn_alignment"
        ],
        "exclusion_rule": report["exclusion_rule"],
        "historical_gemini": _slim_paired(report["historical"]["gemini"]),
        "sensitivity_gemini": _slim_paired(report["sensitivity"]["gemini"]),
        "historical_gptoss": _slim_paired(report["historical"]["gptoss"]),
        "sensitivity_gptoss": _slim_paired(report["sensitivity"]["gptoss"]),
        "sensitivity_versus_historical": report["sensitivity_versus_historical"],
        "agreement": agreement,
        "gptoss_rating_ids_with_uncertain_source_alignment": report["agreement"][
            "gptoss_rating_ids_with_uncertain_source_alignment"
        ],
    }


def write_provenance(figure_dir, report):
    figure_dir = Path(figure_dir)
    flagged = [
        issue["record_id"]
        for issue in report["validation_issues"]
        if issue["code"] == "uncertain_turn_alignment"
    ]
    lines = [
        "# Validated figures, v2",
        "",
        "These PNGs are the validated sensitivity figures. `python -m audit reproduce` drew them from the offline summary. No replacement judge call was made.",
        "",
        "The historical figures shipped with commit c6fdc51 are unchanged. Each validated file has a counterpart there.",
        "",
        "## Historical figures",
        "",
    ]
    for name in FIGURE_NAMES:
        lines.append("- [%s](../%s)" % (name, name))
    lines.extend(["", "## Validated figures", ""])
    for name in FIGURE_NAMES:
        lines.append("- [%s](%s)" % (name, name))
    lines.extend([
        "",
        "## Provenance",
        "",
        "Judge for the abandonment charts: Gemini 2.5 Flash labels in runs/scored.jsonl.",
        "Outcome: abandonment, caves plus deflects, versus non-abandonment, holds plus hedges plus unaddressed.",
        "Exclusion on that Gemini file: none. Both paths use 48 pairs per tutor.",
        "GPT-OSS sensitivity drops a whole naive/pedagogical pair when either side has uncertain turn alignment. The source rows stay in runs/scored_groq.jsonl.",
        "Flagged records: %s." % "; ".join(flagged),
        "Captions are in CAPTIONS.md. The counts are in sensitivity.json.",
        "Machine-readable detail for a local rerun is also written under audit_out/summary.json, which is a generated directory and is not the historical evidence.",
        "",
    ])
    (figure_dir / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")


def write_figure_bundle(report, figure_dir, root):
    figure_dir = Path(figure_dir)
    render(report["figure_inputs"], figure_dir, root=root)
    write_provenance(figure_dir, report)
    payload = _json_ready(sensitivity_document(report))
    (figure_dir / "sensitivity.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(root, outdir, manifest_path=None, figure_dir=None):
    root = Path(root)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(root)
    target = Path(manifest_path) if manifest_path else root / "evidence_manifest.json"
    write_manifest(root, target)
    mismatches = hashes_match(root, manifest)
    issues = validate_repository(root)
    study = load_study(root)
    report = build_report(study)
    report["human_sample"] = human_sample_note(study)
    report["validation_issue_count"] = len(issues)
    report["validation_issues"] = [issue.as_dict() for issue in issues]
    report["frozen_hash_mismatches"] = mismatches
    report["figure_inputs"] = figure_inputs(report)
    summary_path = outdir / "summary.json"
    summary_path.write_text(
        json.dumps(_json_ready(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (outdir / "validation.txt").write_text(format_issues(issues) + "\n", encoding="utf-8")
    bundle = Path(figure_dir) if figure_dir else outdir / "figures"
    write_figure_bundle(report, bundle, root)
    if mismatches:
        return 2
    if not report["published_checks"]["matches_published_gemini_headline"]:
        return 2
    return 0
