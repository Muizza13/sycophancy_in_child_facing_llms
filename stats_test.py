"""Paired significance test for the naive-vs-pedagogical effect.

The two conditions run on the SAME scenarios, so the outcomes are paired.
The correct test for a paired binary outcome (abandoned vs held at a turn) is
McNemar's test, not a two-proportion z-test. We report the exact (binomial)
McNemar p-value, appropriate for the modest discordant counts here.
"""
import argparse
import json
import math

FAIL_SETS = {
    "abandon": {"caves", "deflects"},   # primary: any abandonment of the stance
    "cave": {"caves"},                  # secondary: hard capitulation only
    "deflect": {"deflects"},            # secondary: face-saving reframe only
}


def load(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def turn_stance(rec, turn):
    for p in rec["scores"]["per_turn"]:
        if p["turn"] == turn:
            return p["stance"]
    return None


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value (binomial, p=0.5 on discordant pairs)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) * (0.5 ** n)
    return min(1.0, 2 * tail)


def mcnemar_chi2_cc(b, c):
    """McNemar chi-square with continuity correction (df=1; 3.841 ~ p=.05)."""
    if b + c == 0:
        return 0.0
    return (abs(b - c) - 1) ** 2 / (b + c)


def test_one(records, turn, fail_set, model):
    idx = {(r["case_id"], r["condition"]): r for r in records if r["model"] == model}
    cases = sorted({cid for (cid, _) in idx})
    b = c = both_fail = both_hold = naive_fail = ped_fail = n = 0
    for cid in cases:
        rn, rp = idx.get((cid, "naive")), idx.get((cid, "pedagogical"))
        if not rn or not rp:
            continue
        on = 1 if turn_stance(rn, turn) in fail_set else 0
        op = 1 if turn_stance(rp, turn) in fail_set else 0
        n += 1
        naive_fail += on
        ped_fail += op
        b += (on == 1 and op == 0)   # prompt FIXED this case
        c += (on == 0 and op == 1)   # prompt WORSENED this case
        both_fail += (on == 1 and op == 1)
        both_hold += (on == 0 and op == 0)
    return {
        "model": model, "n": n,
        "naive_rate": naive_fail / n if n else 0,
        "ped_rate": ped_fail / n if n else 0,
        "fixed_by_prompt": b, "worsened_by_prompt": c,
        "both_failed": both_fail, "both_held": both_hold,
        "p_exact": mcnemar_exact(b, c), "chi2_cc": mcnemar_chi2_cc(b, c),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="runs/scored.jsonl")
    ap.add_argument("--turn", type=int, default=3)
    args = ap.parse_args()

    records = load(args.inp)
    models = sorted({r["model"] for r in records})

    print("McNemar paired test: naive vs pedagogical, turn %d\n" % args.turn)
    for label, fail_set in FAIL_SETS.items():
        print("--- failure = %s (%s) ---" % (label, ", ".join(sorted(fail_set))))
        for m in models:
            r = test_one(records, args.turn, fail_set, m)
            sig = "significant" if r["p_exact"] < 0.05 else "not significant"
            print("  %s  (n=%d pairs)" % (r["model"], r["n"]))
            print("    naive %.0f%%  ->  pedagogical %.0f%%"
                  % (100 * r["naive_rate"], 100 * r["ped_rate"]))
            print("    discordant pairs: prompt fixed %d, prompt worsened %d"
                  % (r["fixed_by_prompt"], r["worsened_by_prompt"]))
            print("    McNemar exact p = %.5f (%s);  chi2_cc = %.2f"
                  % (r["p_exact"], sig, r["chi2_cc"]))
        print()


if __name__ == "__main__":
    main()
