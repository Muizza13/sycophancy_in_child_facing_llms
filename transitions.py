"""Stance transition analysis: naive -> pedagogical at a given turn.

Tests whether the pedagogical prompt converts failures into genuine 'holds'
or merely relabels them (for example, caves becoming polite deflects).
Reads runs/scored.jsonl only; no API calls.
"""
import argparse
import json
from collections import Counter, defaultdict

STANCES = ["holds", "hedges", "deflects", "caves", "unaddressed"]


def load(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def turn_stance(rec, turn):
    for p in rec["scores"]["per_turn"]:
        if p["turn"] == turn:
            return p["stance"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="runs/scored.jsonl")
    ap.add_argument("--turn", type=int, default=3)
    args = ap.parse_args()

    records = load(args.inp)
    models = sorted({r["model"] for r in records})

    for m in models:
        idx = {(r["case_id"], r["condition"]): r for r in records if r["model"] == m}
        cases = sorted({cid for (cid, _) in idx})
        pairs = []
        for cid in cases:
            rn, rp = idx.get((cid, "naive")), idx.get((cid, "pedagogical"))
            if rn and rp:
                pairs.append((cid, turn_stance(rn, args.turn), turn_stance(rp, args.turn)))

        print("=== %s  (turn %d, n=%d paired cases) ===" % (m, args.turn, len(pairs)))

        mat = defaultdict(Counter)
        for _, sn, sp in pairs:
            mat[sn][sp] += 1
        rows = [s for s in STANCES if s in mat]
        cols = [s for s in STANCES if any(s in mat[r] for r in mat)]
        print("\nnaive (row) -> pedagogical (col):")
        print("  %-12s" % "" + "".join("%-10s" % c for c in cols) + "total")
        for sn in rows:
            tot = sum(mat[sn].values())
            print("  %-12s" % sn + "".join("%-10d" % mat[sn].get(c, 0) for c in cols) + "%d" % tot)

        caved = [(cid, sp) for cid, sn, sp in pairs if sn == "caves"]
        if caved:
            dist = Counter(sp for _, sp in caved)
            print("\nOf %d cases that CAVED under naive, under pedagogical they became:" % len(caved))
            for s in STANCES:
                if dist.get(s):
                    print("    %-10s %d" % (s, dist[s]))
            print("    detail:", ", ".join("%s->%s" % (cid, sp) for cid, sp in caved))

        aband = [(cid, sn, sp) for cid, sn, sp in pairs if sn in ("caves", "deflects")]
        if aband:
            dist = Counter(sp for _, _, sp in aband)
            held = dist.get("holds", 0)
            still = dist.get("caves", 0) + dist.get("deflects", 0)
            other = len(aband) - held - still
            print("\nOf %d cases that ABANDONED (caved or deflected) under naive:" % len(aband))
            print("    became genuine holds: %d" % held)
            print("    still cave/deflect:   %d" % still)
            if other:
                print("    other (hedge/unaddressed): %d" % other)
        print()


if __name__ == "__main__":
    main()
