# Repair plan

Branch: `repair/validation-reproducibility`, based on `c6fdc51dacefc97b8905d9a92a0154814ee22abd`.

The historical pilot stays as evidence. Repair adds checks, a separate analysis path, and safer future runs. It does not call paid APIs, rewrite transcripts, rejudge conversations, or edit human annotations.

1. Freeze the historical files. Write `evidence_manifest.json` with the original commit, SHA-256 hashes, record counts, identifier scheme, the packaging metadata that shipped with the pilot, and the settings that were never logged.
2. Add `python -m audit validate`. It names the offending record ids and exits nonzero when analysis inputs are invalid. The three GPT-OSS records with extra scored turns stay byte for byte, flagged as uncertain turn alignment.
3. Split statistics into historical reproduction and validated sensitivity. Historical reproduction follows the published calculations and warns where that code treated a missing label as non-abandonment. Sensitivity drops ineligible records, and drops a whole naive/pedagogical pair if either side is ineligible. Exclusion is not treated as a recovered label.
4. Keep `rating_key.csv` as the historical sample map. Document that the committed sampler cannot be shown to have produced those 80 ids. Fix the sampler so a future study stops at the requested size, records the seed and strata, and refuses to overwrite completed rating files.
5. Correct claims about temperature, raw-response recovery, file paths, kappa, abandonment, and what the human sample is. Put the corrected account in new metadata. Leave the original metadata file frozen.
6. Send mock runs and new judge runs to explicit directories. Refuse to overwrite historical files. Do not convert a failed judge call into a heuristic success. Resume only when the judge, prompt, config, and input hash match.
7. Reproduce the published Gemini-judge counts, transitions, exact McNemar p-values, and kappa against SciPy and scikit-learn. Write machine-readable summaries and figures from those summaries under `audit_out/`.
8. Add offline tests and GitHub Actions. Pin the dependency set used for that check. Do not add a license.
