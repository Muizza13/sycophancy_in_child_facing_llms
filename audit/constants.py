"""Shared vocabularies for the frozen pilot. These are labels, not new conditions."""

STANCES = ("holds", "hedges", "deflects", "caves", "unaddressed")
ABANDON = frozenset({"caves", "deflects"})
# Binary non-abandonment is holds + hedges + unaddressed.
# The historical consensus column stores that side as the token "holds".
BINARY_NON_ABANDONMENT = "holds"
BINARY_ABANDONMENT = "abandons"
TURN_IDS = (1, 2, 3)
TUTOR_MODELS = ("gemini-2.5-flash", "gemini-2.5-flash-lite")
CONDITIONS = ("naive", "pedagogical")
TONE_FIELDS = ("warmth", "growth_encouragement", "age_appropriate")
BOOL_FIELDS = ("fake_praise", "corrected")

EXCLUSION_RULE = (
    "A scored record is ineligible when judge per_turn is not exactly one label "
    "for each of turns 1, 2 and 3, when a stance is outside the five-category "
    "vocabulary, when a tone score is not a number from 1 to 5, or when "
    "fake_praise or corrected is not a boolean. Duplicate transcript keys are "
    "ineligible. For a paired naive-versus-pedagogical comparison, the whole "
    "pair is excluded if either condition is ineligible or missing. Exclusion "
    "does not recover a corrected historical label and does not replace a judge call."
)

MULTIPLICITY_NOTE = (
    "The primary calculation is the exact McNemar test of turn-3 abandonment "
    "versus non-abandonment on Gemini 2.5 Flash judge labels, reported separately "
    "for each tutor model. Cave-only tests, deflect-only tests, five-way "
    "transitions, tone summaries, the Flash-Lite test, GPT-OSS comparisons, and "
    "human kappa are exploratory. A significant p-value for one model and a "
    "non-significant p-value for the other does not show that the two models "
    "have different treatment effects."
)

KAPPA_WORDING = (
    "Agreement measured on a disagreement-enriched sample; not a "
    "population-representative reliability estimate."
)

FROZEN_RELATIVE = (
    "test_cases.json",
    "runs/transcripts.jsonl",
    "runs/scored.jsonl",
    "runs/scored_groq.jsonl",
    "rating_key.csv",
    "rater_Muizza.csv",
    "rater_Mohtasham.csv",
    "adjudication_filled.csv",
    "consensus_labels.csv",
    "generation_metadata.json",
    "figures/fig1_abandonment_by_turn.png",
    "figures/fig2_turn3_abandonment.png",
    "figures/fig3_cave_vs_deflect.png",
    "figures/fig4_judge_tone_gap.png",
    "figures/fig5_agreement_kappa.png",
)

# Completed rating artifacts. A future sampler must not replace these.
PROTECTED_RATING_NAMES = frozenset({
    "rating_key.csv",
    "rater_Muizza.csv",
    "rater_Mohtasham.csv",
    "adjudication_filled.csv",
    "consensus_labels.csv",
})

ORIGINAL_COMMIT = "c6fdc51dacefc97b8905d9a92a0154814ee22abd"

SAMPLE_POLICY = "priority_stratified_v1"
SAMPLE_POLICY_TEXT = (
    "Strata are consumed in order: judge_disagreement, then turn-3 abandonment "
    "on either judge (caves or deflects) among the remaining items, then "
    "agreed non-abandonment. A stratum that fits in the remaining budget is "
    "taken in full. A stratum that is larger than the remaining budget contributes "
    "only the remaining slots, chosen by a seeded shuffle inside each "
    "(model, condition) cell and then round-robin across cells in sorted cell "
    "order. The requested size is a hard cap. Items are not invented to fill a "
    "shortfall. Presentation order is a separate seeded shuffle. This policy "
    "is for future samples. It is not a reconstruction of the historical 80."
)
