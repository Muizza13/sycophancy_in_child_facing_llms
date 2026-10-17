# Licensing

Two grants apply, and they apply only to the paths named under each one. `LICENSE` is the MIT text for the software paths. Author-owned research materials are under Creative Commons Attribution 4.0 International, https://creativecommons.org/licenses/by/4.0/legalcode.

Attribution for the CC BY 4.0 materials: Muizza Muayqeeb Akram, Deflect, Cave, or Hold, 2026.

## Software, MIT

- `analyze.py`, `build_rating_sheet.py`, `judge.py`, `judge_agreement.py`, `make_figures.py`, `models.py`, `rater_agreement.py`, `runner.py`, `scenarios.py`, `stats_test.py`, `transitions.py`
- `audit/`
- `tests/`
- `.github/`
- `requirements.txt`, `pytest.ini`, `.gitignore`, `.env.example`
- `evidence_manifest.json`

The two system prompts and the three child-turn templates in `scenarios.py` are also author-owned study text and may be reused under CC BY 4.0. The rest of that module is MIT software.

## Author-owned research materials, CC BY 4.0

- `README.md`, `rubric.md`, `CODEBOOK.md`, `REPAIR_PLAN.md`, `LICENSING.md`
- `test_cases.json`
- `generation_metadata.json`, `generation_metadata_corrected.json`
- `figures/fig1_abandonment_by_turn.png`, `figures/fig2_turn3_abandonment.png`, `figures/fig3_cave_vs_deflect.png`, `figures/fig4_judge_tone_gap.png`, `figures/fig5_agreement_kappa.png`
- `figures/validated_v2/`

The figure files are the author's charts. They do not grant rights in the model transcripts those charts summarize.

## Model outputs, outside both grants

- `runs/transcripts.jsonl`
- `runs/scored.jsonl`
- `runs/scored_groq.jsonl`
- `rating_key.csv`

`rating_key.csv` is listed here because `judge_a_t3` and `judge_b_t3` are model outputs. The files remain in the repository so the audit can be checked. This repository does not grant any right in them beyond the applicable provider terms.

Provider terms for Google Gemini and for Groq were not reviewed in this repair. Nothing here says those terms allow redistribution, display, or modification.

## Individual ratings, adjudication, and consensus labels, outside both grants

- `rater_Muizza.csv`
- `rater_Mohtasham.csv`
- `adjudication_filled.csv`
- `consensus_labels.csv`

These stay unlicensed until the relevant ownership and consent are confirmed in writing. The raters are Muizza Muayqeeb Akram and Mohtasham Murshid. That consent is not recorded in this repository. A future license grant for these files, including `consensus_labels.csv`, requires that confirmation. This repair does not place `consensus_labels.csv` under CC BY 4.0.

## Unresolved

Rater consent is unresolved. Provider-term review for the Gemini and Groq outputs is unresolved. Those two open items do not remove the MIT grant or the CC BY 4.0 grant from the paths named above.
