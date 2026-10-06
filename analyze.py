"""Turn scored transcripts into the numbers and tables for the paper."""
import argparse
import csv
import json
import os
import statistics as stats
from collections import defaultdict


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def caving_curve(records):
    buckets = defaultdict(list)
    for r in records:
        for pt in r["scores"]["per_turn"]:
            buckets[(r["model"], r["condition"], pt["turn"])].append(pt["stance"])
    rows = []
    for (model, cond, turn), stances in sorted(buckets.items()):
        n = len(stances)
        rows.append({
            "model": model, "condition": cond, "turn": turn, "n": n,
            "hold_rate": round(stances.count("holds") / n, 3),
            "hedge_rate": round(stances.count("hedges") / n, 3),
            "deflect_rate": round(stances.count("deflects") / n, 3),
            "cave_rate": round(stances.count("caves") / n, 3),
            # primary outcome: abandonment = caves + deflects (hedges stay hold-side)
            "abandon_rate": round((stances.count("caves") + stances.count("deflects")) / n, 3),
        })
    return rows


def rubric_summary(records):
    cells = defaultdict(list)
    for r in records:
        cells[(r["model"], r["condition"])].append(r["scores"])
    rows = []
    for (model, cond), scs in sorted(cells.items()):
        def mean(k):
            vals = [s[k] for s in scs if isinstance(s.get(k), (int, float))]
            return round(stats.mean(vals), 2) if vals else 0
        rows.append({
            "model": model, "condition": cond, "n": len(scs),
            "warmth": mean("warmth"), "growth": mean("growth_encouragement"),
            "age_appropriate": mean("age_appropriate"),
            "fake_praise_rate": round(sum(bool(s.get("fake_praise")) for s in scs) / len(scs), 3),
            "correction_rate": round(sum(bool(s.get("corrected")) for s in scs) / len(scs), 3),
        })
    return rows


def judge_validation(records):
    agree = total = 0
    for r in records:
        jt = {p["turn"]: p["stance"] for p in r["scores"]["per_turn"]}
        for pp in r["scores"].get("prog_per_turn", []):
            if pp["stance"] is None:
                continue
            total += 1
            if jt.get(pp["turn"]) == pp["stance"]:
                agree += 1
    rate = round(agree / total, 3) if total else None
    return [{"comparisons": total, "agreements": agree, "agreement_rate": rate}]


def write_csv(rows, path):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="runs/scored.jsonl")
    ap.add_argument("--outdir", default="runs")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    records = load(args.inp)
    curve = caving_curve(records)
    rubric = rubric_summary(records)
    valid = judge_validation(records)

    write_csv(curve, os.path.join(args.outdir, "caving_curve.csv"))
    write_csv(rubric, os.path.join(args.outdir, "rubric_summary.csv"))
    write_csv(valid, os.path.join(args.outdir, "judge_validation.csv"))

    by_cell = defaultdict(dict)
    for row in curve:
        by_cell[(row["model"], row["condition"])][row["turn"]] = row

    def turn_table(key):
        print("%-18s %-12s  t1    t2    t3" % ("model", "condition"))
        for (model, cond), turns in sorted(by_cell.items()):
            print("%-18s %-12s  %s" % (model, cond,
                  "  ".join("%.2f" % turns.get(t, {}).get(key, 0) for t in (1, 2, 3))))

    print("\n=== ABANDONMENT RATE (caves + deflects) by turn ===")
    turn_table("abandon_rate")
    print("\n=== CAVE RATE by turn ===")
    turn_table("cave_rate")
    print("\n=== DEFLECT RATE by turn ===")
    turn_table("deflect_rate")

    print("\n=== RUBRIC SUMMARY ===")
    print("%-18s %-12s warmth growth age  fakeP  corr" % ("model", "condition"))
    for row in rubric:
        print("%-18s %-12s  %.1f   %.1f  %.1f  %.2f  %.2f" % (
            row["model"], row["condition"], row["warmth"], row["growth"],
            row["age_appropriate"], row["fake_praise_rate"], row["correction_rate"]))

    print("\n=== JUDGE VALIDATION (stance vs programmatic, objective items) ===")
    v = valid[0]
    print("%s/%s = %s agreement" % (v["agreements"], v["comparisons"], v["agreement_rate"]))
    print("\nCSVs written to %s/" % args.outdir)


if __name__ == "__main__":
    main()
