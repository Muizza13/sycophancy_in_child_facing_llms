"""Human agreement on the frozen sheets.

Binary agreement is abandonment versus non-abandonment. Five-way holds stay
a separate calculation. The 80-item sheet is a disagreement-enriched validation
subset, not a population reliability sample.
"""

import argparse
import sys

from audit.constants import KAPPA_WORDING, STANCES
from audit.io import load_csv
from audit.stats import binary_outcome, cohens_kappa


def _norm(value):
    return (value or "").strip().lower()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--raters", nargs="+", required=True)
    parser.add_argument("--key", default="rating_key.csv")
    parser.add_argument("--consensus", default="consensus_labels.csv")
    args = parser.parse_args(argv)
    key = {row["rating_id"]: row for row in load_csv(args.key)}
    consensus = {row["rating_id"]: row for row in load_csv(args.consensus)}
    raters = [{row["rating_id"]: row for row in load_csv(path)} for path in args.raters]
    ids = set(key)
    for sheet in raters:
        ids &= set(sheet)
    ids = sorted(ids)
    print("Items in the key and every rater sheet: %d" % len(ids))
    print(KAPPA_WORDING)
    if len(raters) == 2:
        left, right = raters
        five = [(_norm(left[i]["t3_stance"]), _norm(right[i]["t3_stance"])) for i in ids]
        binary = [(binary_outcome(a), binary_outcome(b)) for a, b in five]
        raw, kappa = cohens_kappa(five)
        print("t3 five-way n=%d raw %.3f kappa %s" % (len(five), raw, None if kappa is None else round(kappa, 3)))
        raw, kappa = cohens_kappa(binary)
        print("t3 abandonment versus non-abandonment n=%d raw %.3f kappa %s" % (len(binary), raw, None if kappa is None else round(kappa, 3)))
        cave = [pair for pair in five if pair[0] in ("caves", "deflects") and pair[1] in ("caves", "deflects")]
        if cave:
            raw, kappa = cohens_kappa(cave)
            print("t3 cave versus deflect (exploratory) n=%d raw %.3f kappa %s" % (len(cave), raw, None if kappa is None else round(kappa, 3)))
    print("Consensus column token 'holds' means non-abandonment, not the five-way stance holds.")
    print("Five-way vocabulary: %s" % ", ".join(STANCES))
    if consensus:
        print("Consensus rows available: %d" % len(consensus))
    return 0


if __name__ == "__main__":
    sys.exit(main())
