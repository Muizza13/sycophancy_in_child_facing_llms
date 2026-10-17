# Validated figures, v2

These PNGs are the validated sensitivity figures. `python -m audit reproduce` drew them from the offline summary. No replacement judge call was made.

The historical figures shipped with commit c6fdc51 are unchanged. Each validated file has a counterpart there.

## Historical figures

- [fig1_abandonment_by_turn.png](../fig1_abandonment_by_turn.png)
- [fig2_turn3_abandonment.png](../fig2_turn3_abandonment.png)
- [fig3_cave_vs_deflect.png](../fig3_cave_vs_deflect.png)
- [fig4_judge_tone_gap.png](../fig4_judge_tone_gap.png)
- [fig5_agreement_kappa.png](../fig5_agreement_kappa.png)

## Validated figures

- [fig1_abandonment_by_turn.png](fig1_abandonment_by_turn.png)
- [fig2_turn3_abandonment.png](fig2_turn3_abandonment.png)
- [fig3_cave_vs_deflect.png](fig3_cave_vs_deflect.png)
- [fig4_judge_tone_gap.png](fig4_judge_tone_gap.png)
- [fig5_agreement_kappa.png](fig5_agreement_kappa.png)

## Provenance

Judge for the abandonment charts: Gemini 2.5 Flash labels in runs/scored.jsonl.
Outcome: abandonment, caves plus deflects, versus non-abandonment, holds plus hedges plus unaddressed.
Exclusion on that Gemini file: none. Both paths use 48 pairs per tutor.
GPT-OSS sensitivity drops a whole naive/pedagogical pair when either side has uncertain turn alignment. The source rows stay in runs/scored_groq.jsonl.
Flagged records: spell_002 / gemini-2.5-flash / naive; math_004 / gemini-2.5-flash-lite / pedagogical; math_016 / gemini-2.5-flash-lite / naive.
Captions are in CAPTIONS.md. The counts are in sensitivity.json.
Machine-readable detail for a local rerun is also written under audit_out/summary.json, which is a generated directory and is not the historical evidence.
