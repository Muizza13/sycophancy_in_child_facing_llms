"""Compare two judge passes on the same transcripts (e.g. gemini vs groq).

Answers two questions that block the cross-model claims:
  1. Do two independent judges agree on stance, especially hold vs deflect?
  2. Does the non-Gemini judge break the tone ceiling?
"""
import argparse
import json
import math
from collections import Counter

LABS = ["holds", "hedges", "deflects", "caves", "unaddressed"]


def load_stance(path):
    d = {}
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            for pt in r["scores"].get("per_turn", []):
                d[(r["case_id"], r["model"], r["condition"], pt["turn"])] = pt["stance"]
    return d


def load_tone(path):
    d = {}
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            s = r["scores"]
            d[(r["case_id"], r["model"], r["condition"])] = (
                s.get("warmth"), s.get("growth_encouragement"), s.get("age_appropriate"))
    return d


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


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def sd(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="runs/scored.jsonl", help="judge A scored file")
    ap.add_argument("--b", default="runs/scored_groq.jsonl", help="judge B scored file")
    ap.add_argument("--label-a", default="gemini")
    ap.add_argument("--label-b", default="groq")
    args = ap.parse_args()

    A, B = load_stance(args.a), load_stance(args.b)
    keys = sorted(set(A) & set(B))
    if not keys:
        raise SystemExit("No overlapping keys between the two files.")
    pairs = [(A[k], B[k]) for k in keys]

    po, k = kappa(pairs)
    print("=== STANCE AGREEMENT: %s vs %s ===" % (args.label_a, args.label_b))
    print("all turns (n=%d): raw %.3f   Cohen's kappa %.3f" % (len(pairs), po, k))
    for turn in (2, 3):
        tp = [(A[x], B[x]) for x in keys if x[3] == turn]
        if tp:
            po_t, k_t = kappa(tp)
            print("turn %d   (n=%d): raw %.3f   kappa %.3f" % (turn, len(tp), po_t, k_t))

    present = [l for l in LABS if any(a == l or b == l for a, b in pairs)]
    print("\nConfusion (rows=%s, cols=%s):" % (args.label_a, args.label_b))
    print("  %-11s" % "" + "".join("%-11s" % l for l in present))
    for ra in present:
        row = [sum(1 for a, b in pairs if a == ra and b == rb) for rb in present]
        print("  %-11s" % ra + "".join("%-11d" % c for c in row))

    hd = [(a, b) for a, b in pairs if a in ("holds", "deflects") and b in ("holds", "deflects")]
    if hd:
        po_hd, k_hd = kappa(hd)
        print("\nHold-vs-deflect subset (n=%d): raw %.3f   kappa %.3f" % (len(hd), po_hd, k_hd))
        print("  (kappa near 0 = the judges cannot agree where deflect ends and hold begins)")

    TA, TB = load_tone(args.a), load_tone(args.b)
    tkeys = sorted(set(TA) & set(TB))
    print("\n=== TONE: is the ceiling real or a self-grading artifact? ===")
    print("%-8s %-26s %-26s" % ("axis", args.label_a, args.label_b))
    for i, name in enumerate(["warmth", "growth", "age"]):
        av = [TA[x][i] for x in tkeys if TA[x][i] is not None and TB[x][i] is not None]
        bv = [TB[x][i] for x in tkeys if TA[x][i] is not None and TB[x][i] is not None]
        if av:
            print("%-8s mean %.2f  sd %.2f (range %d-%d)   mean %.2f  sd %.2f (range %d-%d)" % (
                name, mean(av), sd(av), min(av), max(av),
                mean(bv), sd(bv), min(bv), max(bv)))


if __name__ == "__main__":
    main()
