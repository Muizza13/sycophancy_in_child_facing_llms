"""Analyse filled human-rating sheets.

With two raters: inter-rater agreement (Cohen's kappa) on stance, the hold/deflect
subset, and tone, plus the list of disagreements to adjudicate. With one or two:
judge-vs-human agreement at turn 3 for each judge.

Usage:
  python rater_agreement.py --raters runs/rater_A.csv runs/rater_B.csv --key runs/rating_key.csv
  python rater_agreement.py --raters runs/rater_A.csv --key runs/rating_key.csv
"""
import argparse
import csv
from collections import Counter


def read_csv(path):
    with open(path, newline="") as f:
        return {r["rating_id"]: r for r in csv.DictReader(f)}


def norm(s):
    return (s or "").strip().lower()


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def kappa(pairs):
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan")
    labels = sorted(set([a for a, _ in pairs] + [b for _, b in pairs]))
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    k = (po - pe) / (1 - pe) if pe != 1 else float("nan")
    return po, k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raters", nargs="+", required=True, help="1 or 2 filled sheet copies")
    ap.add_argument("--key", default="runs/rating_key.csv")
    args = ap.parse_args()

    key = read_csv(args.key)
    raters = [read_csv(p) for p in args.raters]
    common = set(key)
    for r in raters:
        common &= set(r)
    ids = sorted(common)
    print("Items with key + every rater filled in: %d" % len(ids))

    def st(rd, i, col):
        return norm(rd[i].get(col, ""))

    if len(raters) == 2:
        rA, rB = raters
        print("\n=== INTER-RATER AGREEMENT (rater 1 vs rater 2) ===")
        for col in ("t3_stance", "t2_stance"):
            pairs = [(st(rA, i, col), st(rB, i, col)) for i in ids
                     if st(rA, i, col) and st(rB, i, col)]
            if pairs:
                po, k = kappa(pairs)
                print("%-11s n=%d  raw %.3f  kappa %.3f" % (col, len(pairs), po, k))
        hd = [(st(rA, i, "t3_stance"), st(rB, i, "t3_stance")) for i in ids
              if st(rA, i, "t3_stance") in ("holds", "deflects")
              and st(rB, i, "t3_stance") in ("holds", "deflects")]
        if hd:
            po, k = kappa(hd)
            print("hold/deflect (t3)  n=%d  raw %.3f  kappa %.3f" % (len(hd), po, k))
        for col in ("warmth_1to5", "growth_1to5"):
            diffs = [abs(fnum(rA[i][col]) - fnum(rB[i][col])) for i in ids
                     if fnum(rA[i].get(col)) is not None and fnum(rB[i].get(col)) is not None]
            if diffs:
                within1 = sum(1 for d in diffs if d <= 1) / len(diffs)
                print("%-12s n=%d  mean|diff| %.2f  within 1pt %.0f%%"
                      % (col, len(diffs), sum(diffs) / len(diffs), 100 * within1))
        dis = [i for i in ids if st(rA, i, "t3_stance") and st(rB, i, "t3_stance")
               and st(rA, i, "t3_stance") != st(rB, i, "t3_stance")]
        print("\nt3 disagreements to adjudicate (%d): %s" % (len(dis), ", ".join(dis)))

    def human_label(i):
        vals = [st(r, i, "t3_stance") for r in raters if st(r, i, "t3_stance")]
        if not vals:
            return None
        if len(set(vals)) == 1:
            return vals[0]
        return None

    print("\n=== JUDGE vs HUMAN (turn 3 stance, agreed-human items only) ===")
    for jcol, lab in (("judge_a_t3", "judge A (gemini)"), ("judge_b_t3", "judge B (groq)")):
        pairs = [(human_label(i), norm(key[i].get(jcol, ""))) for i in ids
                 if human_label(i) and norm(key[i].get(jcol, ""))]
        if pairs:
            po, k = kappa(pairs)
            print("%-18s n=%d  raw %.3f  kappa %.3f" % (lab, len(pairs), po, k))
            hd = [(h, j) for h, j in pairs if h in ("holds", "deflects") and j in ("holds", "deflects")]
            if hd:
                po2, k2 = kappa(hd)
                print("   hold/deflect only  n=%d  raw %.3f  kappa %.3f" % (len(hd), po2, k2))


if __name__ == "__main__":
    main()
