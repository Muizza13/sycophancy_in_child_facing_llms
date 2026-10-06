"""Build a blinded, stratified human-rating sheet from the transcripts.

Oversamples the cases where the two judges disagreed on turn-3 stance (the
hold/deflect boundary) plus the turn-3 non-holds, then fills with agreed holds
so raters see the full range and aren't primed to find problems everywhere.
Strips model/condition, shuffles, and writes:
  runs/rating_sheet.csv  (give a copy to each rater; rating columns blank)
  runs/rating_key.csv    (unblinding map; raters must NOT see this)
"""
import argparse
import csv
import json
import os
import random
from collections import defaultdict


def load_transcripts(path):
    d = {}
    with open(path) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                d[(r["case_id"], r["model"], r["condition"])] = r
    return d


def load_turn_stance(path, turn):
    d = {}
    if not os.path.exists(path):
        return d
    with open(path) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                for pt in r["scores"].get("per_turn", []):
                    if pt["turn"] == turn:
                        d[(r["case_id"], r["model"], r["condition"])] = pt["stance"]
    return d


def load_questions(path):
    d = {}
    try:
        for c in json.load(open(path)).get("cases", []):
            d[c["id"]] = c.get("question", "")
    except Exception:
        pass
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcripts", default="runs/transcripts.jsonl")
    ap.add_argument("--cases", default="test_cases.json")
    ap.add_argument("--judge-a", default="runs/scored.jsonl")
    ap.add_argument("--judge-b", default="runs/scored_groq.jsonl")
    ap.add_argument("--out", default="runs/rating_sheet.csv")
    ap.add_argument("--key", default="runs/rating_key.csv")
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    random.seed(args.seed)
    T = load_transcripts(args.transcripts)
    Q = load_questions(args.cases)
    A = load_turn_stance(args.judge_a, 3)
    B = load_turn_stance(args.judge_b, 3)

    tier1, tier2, tier3 = [], [], []
    for key in T:
        a, b = A.get(key), B.get(key)
        disagree = (a is not None and b is not None and a != b)
        nonhold = a in ("deflects", "caves") or b in ("deflects", "caves")
        (tier1 if disagree else tier2 if nonhold else tier3).append(key)

    chosen = list(tier1) + list(tier2)
    need = max(0, args.n - len(chosen))
    cells = defaultdict(list)
    for k in tier3:
        cells[(k[1], k[2])].append(k)
    for v in cells.values():
        random.shuffle(v)
    fill, ck = [], list(cells.keys())
    i = 0
    while len(fill) < need and any(cells.values()):
        c = ck[i % len(ck)] if ck else None
        if c and cells[c]:
            fill.append(cells[c].pop())
        i += 1
        if i > 100000:
            break
    chosen += fill
    random.shuffle(chosen)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="") as f, open(args.key, "w", newline="") as kf:
        w, kw = csv.writer(f), csv.writer(kf)
        w.writerow(["rating_id", "subject", "question", "correct_answer", "child_says_answer_is",
                    "T1_child", "T1_tutor", "T2_child", "T2_tutor", "T3_child", "T3_tutor",
                    "t2_stance", "t3_stance", "warmth_1to5", "growth_1to5", "fake_praise_0or1", "notes"])
        kw.writerow(["rating_id", "case_id", "model", "condition", "judge_a_t3", "judge_b_t3"])
        for idx, key in enumerate(chosen, 1):
            rid = "R%03d" % idx
            rec = T[key]
            turns = {t["turn"]: t for t in rec["turns"]}

            def cell(turn, who):
                return turns.get(turn, {}).get(who, "")

            w.writerow([rid, rec.get("subject", ""), Q.get(key[0], ""),
                        rec.get("correct_answer", ""), rec.get("child_wrong_answer", ""),
                        cell(1, "child"), cell(1, "model"), cell(2, "child"), cell(2, "model"),
                        cell(3, "child"), cell(3, "model"), "", "", "", "", "", ""])
            kw.writerow([rid, key[0], key[1], key[2], A.get(key, ""), B.get(key, "")])

    print("Wrote %d items to %s" % (len(chosen), args.out))
    print("  composition: judge-disagreement=%d, extra turn3 non-holds=%d, filled agreed-holds=%d"
          % (len(tier1), len(tier2), len(fill)))
    print("Unblinding key (keep away from raters): %s" % args.key)


if __name__ == "__main__":
    main()
