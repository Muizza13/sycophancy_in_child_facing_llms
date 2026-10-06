"""Generate paper figures from the scored transcripts and the human labels.

Dependency-light: matplotlib + stdlib only. Every figure is guarded; if an input
file is missing, that figure is skipped with a note and the rest still run.
Outputs PNGs into --outdir (default: figures/).
"""
import argparse
import csv
import json
import os
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
CONDS = ["naive", "pedagogical"]
C_NAIVE, C_PED = "#d1495b", "#2e86ab"
ABANDON = ("caves", "deflects")


def n(s):
    return (s or "").strip().lower()


def load_scored(path):
    dist = defaultdict(Counter)
    tone = defaultdict(list)
    if not os.path.exists(path):
        return None, None
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            m, c = r["model"], r["condition"]
            for pt in r["scores"].get("per_turn", []):
                dist[(m, c, pt["turn"])][n(pt["stance"])] += 1
            sc = r["scores"]
            if sc.get("warmth") is not None:
                tone[(m, c)].append((sc.get("warmth"), sc.get("growth_encouragement")))
    return dist, tone


def rate(counter, labels):
    tot = sum(counter.values())
    return (sum(counter[l] for l in labels) / tot) if tot else 0.0


def kappa(pairs):
    N = len(pairs)
    if not N:
        return float("nan")
    L = sorted(set([a for a, _ in pairs] + [b for _, b in pairs]))
    po = sum(1 for a, b in pairs if a == b) / N
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum((ca[l] / N) * (cb[l] / N) for l in L)
    return (po - pe) / (1 - pe) if pe != 1 else float("nan")


def binr(s):
    """Primary binary outcome. Abandonment = caves or deflects ONLY.
    Hedges and unaddressed stay on the hold side, matching stats_test.py and the paper."""
    return "abandons" if n(s) in ABANDON else "holds"


def read_csv(path):
    if not os.path.exists(path):
        return None
    with open(path, newline="") as f:
        return {row["rating_id"]: row for row in csv.DictReader(f) if row.get("rating_id")}


def fig_abandon_by_turn(dist, outdir):
    if not dist:
        print("skip fig1 (abandonment by turn): no scored.jsonl"); return
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, m in zip(axes, MODELS):
        for c, col in (("naive", C_NAIVE), ("pedagogical", C_PED)):
            ys = [rate(dist[(m, c, t)], ABANDON) for t in (1, 2, 3)]
            ax.plot([1, 2, 3], ys, marker="o", color=col, linewidth=2,
                    label=c, linestyle="-" if c == "naive" else "--")
        ax.set_title(m, fontsize=11)
        ax.set_xlabel("turn"); ax.set_xticks([1, 2, 3]); ax.set_ylim(0, 1)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("abandonment rate (cave + deflect)")
    axes[0].legend(frameon=False)
    fig.suptitle("Abandonment of the correct answer under escalating pressure", fontsize=12)
    fig.tight_layout()
    p = os.path.join(outdir, "fig1_abandonment_by_turn.png")
    fig.savefig(p, dpi=150, bbox_inches="tight"); plt.close(fig); print("wrote", p)


def fig_turn3_bars(dist, outdir):
    if not dist:
        print("skip fig2 (turn-3 bars): no scored.jsonl"); return
    fig, ax = plt.subplots(figsize=(7, 4.2))
    x = range(len(MODELS)); w = 0.36
    naive = [rate(dist[(m, "naive", 3)], ABANDON) for m in MODELS]
    ped = [rate(dist[(m, "pedagogical", 3)], ABANDON) for m in MODELS]
    b1 = ax.bar([i - w / 2 for i in x], naive, w, label="naive", color=C_NAIVE)
    b2 = ax.bar([i + w / 2 for i in x], ped, w, label="pedagogical", color=C_PED)
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.02,
                    "%.0f%%" % (100 * b.get_height()), ha="center", fontsize=9)
    ax.set_xticks(list(x)); ax.set_xticklabels(MODELS)
    ax.set_ylabel("turn-3 abandonment rate"); ax.set_ylim(0, 1)
    ax.set_title("Abandonment at the decisive turn, by model and prompt")
    ax.legend(frameon=False); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    p = os.path.join(outdir, "fig2_turn3_abandonment.png")
    fig.savefig(p, dpi=150, bbox_inches="tight"); plt.close(fig); print("wrote", p)


def fig_cave_deflect_stack(dist, outdir):
    if not dist:
        print("skip fig3 (cave/deflect): no scored.jsonl"); return
    cells = [(m, c) for m in MODELS for c in CONDS]
    labels = ["%s\n%s" % (m.replace("gemini-2.5-", ""), c) for m, c in cells]
    cave = [rate(dist[(m, c, 3)], ("caves",)) for m, c in cells]
    defl = [rate(dist[(m, c, 3)], ("deflects",)) for m, c in cells]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = range(len(cells))
    ax.bar(x, cave, 0.6, label="cave", color="#8a1c2b")
    ax.bar(x, defl, 0.6, bottom=cave, label="deflect", color="#e08a98")
    ax.set_xticks(list(x)); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("turn-3 rate"); ax.set_ylim(0, 1)
    ax.set_title("Cave vs deflect split at turn 3 (exploratory)")
    ax.legend(frameon=False); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    p = os.path.join(outdir, "fig3_cave_vs_deflect.png")
    fig.savefig(p, dpi=150, bbox_inches="tight"); plt.close(fig); print("wrote", p)


def fig_tone_bias(tone_a, tone_b, outdir):
    if not tone_a or not tone_b:
        print("skip fig4 (judge tone gap): need both scored files"); return

    def means(tone):
        allw = [w for vals in tone.values() for (w, g) in vals if w is not None]
        allg = [g for vals in tone.values() for (w, g) in vals if g is not None]
        return (sum(allw) / len(allw) if allw else 0, sum(allg) / len(allg) if allg else 0)
    wa, ga = means(tone_a); wb, gb = means(tone_b)
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    x = range(2); w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], [wa, ga], w, label="Gemini judge", color="#c44e52")
    b2 = ax.bar([i + w / 2 for i in x], [wb, gb], w, label="GPT-OSS-20b judge", color="#55a868")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03,
                    "%.2f" % b.get_height(), ha="center", fontsize=9)
    ax.set_xticks(list(x)); ax.set_xticklabels(["warmth", "growth"])
    ax.set_ylabel("mean rating (1-5)"); ax.set_ylim(0, 5.4)
    ax.set_title("Judges disagree on absolute tone (measurement caution)")
    ax.legend(frameon=False, fontsize=9); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    p = os.path.join(outdir, "fig4_judge_tone_gap.png")
    fig.savefig(p, dpi=150, bbox_inches="tight"); plt.close(fig); print("wrote", p)


def read_scored_binary(path, turn):
    if not os.path.exists(path):
        return None
    out = {}
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            for pt in r["scores"].get("per_turn", []):
                if pt["turn"] == turn:
                    out[(r["case_id"], r["model"], r["condition"])] = binr(pt["stance"])
    return out


def fig_agreement(args, outdir):
    bars = []
    rmoht = read_csv(args.rater_a); rmuiz = read_csv(args.rater_b)
    con = read_csv(args.consensus); key = read_csv(args.key)
    if rmoht and rmuiz:
        ids = sorted(set(rmoht) & set(rmuiz))
        pairs = [(binr(rmoht[i]["t3_stance"]), binr(rmuiz[i]["t3_stance"])) for i in ids]
        bars.append(("human vs human", kappa(pairs)))
    if con and key:
        ids = sorted(set(con) & set(key))
        ga = [(con[i]["consensus_holds_or_abandon"], binr(key[i].get("judge_a_t3", ""))) for i in ids if n(key[i].get("judge_a_t3"))]
        gb = [(con[i]["consensus_holds_or_abandon"], binr(key[i].get("judge_b_t3", ""))) for i in ids if n(key[i].get("judge_b_t3"))]
        if ga: bars.append(("Gemini judge\nvs human", kappa(ga)))
        if gb: bars.append(("GPT-OSS judge\nvs human", kappa(gb)))
    sa = read_scored_binary(args.scored, 3); sb = read_scored_binary(args.scored_groq, 3)
    if sa and sb:
        ids = sorted(set(sa) & set(sb))
        cj = [(sa[i], sb[i]) for i in ids]
        if cj: bars.append(("Gemini vs GPT-OSS\njudge", kappa(cj)))
    if not bars:
        print("skip fig5 (agreement): no rater/consensus/key/scored inputs"); return
    labels = [b[0] for b in bars]; vals = [b[1] for b in bars]
    cols = ["#2e86ab" if v >= 0 else "#d1495b" for v in vals]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    b = ax.bar(range(len(vals)), vals, 0.6, color=cols)
    for rect, v in zip(b, vals):
        ax.text(rect.get_x() + rect.get_width() / 2,
                v + (0.02 if v >= 0 else -0.06), "%.2f" % v, ha="center", fontsize=10)
    for y, lab in ((0.2, "slight"), (0.4, "fair"), (0.6, "moderate")):
        ax.axhline(y, color="gray", linewidth=0.7, linestyle=":")
        ax.text(len(vals) - 0.4, y + 0.005, lab, fontsize=8, color="gray", ha="right")
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Cohen's kappa (holds vs abandonment, turn 3)")
    ax.set_ylim(min(-0.15, min(vals) - 0.05), 0.75)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Agreement on the holds-vs-abandonment call")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    p = os.path.join(outdir, "fig5_agreement_kappa.png")
    fig.savefig(p, dpi=150, bbox_inches="tight"); plt.close(fig); print("wrote", p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", default="runs/scored.jsonl")
    ap.add_argument("--scored-groq", default="runs/scored_groq.jsonl")
    ap.add_argument("--consensus", default="consensus_labels.csv")
    ap.add_argument("--key", default="rating_key.csv")
    ap.add_argument("--rater-a", default="rater_Mohtasham.csv")
    ap.add_argument("--rater-b", default="rater_Muizza.csv")
    ap.add_argument("--outdir", default="figures")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    dist_a, tone_a = load_scored(args.scored)
    dist_b, tone_b = load_scored(args.scored_groq)
    fig_abandon_by_turn(dist_a, args.outdir)
    fig_turn3_bars(dist_a, args.outdir)
    fig_cave_deflect_stack(dist_a, args.outdir)
    fig_tone_bias(tone_a, tone_b, args.outdir)
    fig_agreement(args, args.outdir)
    print("\nDone. Figures in %s/" % args.outdir)


if __name__ == "__main__":
    main()
