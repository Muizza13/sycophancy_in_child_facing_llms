"""Figures drawn only from an already computed summary."""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from audit.constants import KAPPA_WORDING
from audit.protect import assert_writable, repo_root


MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
CONDITIONS = ["naive", "pedagogical"]
C_NAIVE = "#d1495b"
C_PED = "#2e86ab"


def _cell_map(cells):
    return {(cell["model"], cell["condition"], cell["turn"]): cell for cell in cells}


def _rate(cell):
    if not cell or not cell["n"]:
        return 0.0
    return cell["abandonment_rate"]


def _save(fig, outdir, name):
    path = os.path.join(outdir, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def render(figure_inputs, outdir, root=None):
    root = root or repo_root()
    os.makedirs(outdir, exist_ok=True)
    for name in (
        "fig1_abandonment_by_turn.png",
        "fig2_turn3_abandonment.png",
        "fig3_cave_vs_deflect.png",
        "fig4_judge_tone_gap.png",
        "fig5_agreement_kappa.png",
        "CAPTIONS.md",
    ):
        assert_writable(Path(outdir) / name, root)
    cells = _cell_map(figure_inputs["cells"])
    captions = []
    judge = figure_inputs["judge"]
    outcome = figure_inputs["outcome"]
    policy = figure_inputs["exclusion_policy"]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    for axis, model in zip(axes, MODELS):
        for condition, color, style in (("naive", C_NAIVE, "-"), ("pedagogical", C_PED, "--")):
            ys = [_rate(cells.get((model, condition, turn))) for turn in (1, 2, 3)]
            ns = [cells.get((model, condition, turn), {}).get("n", 0) for turn in (1, 2, 3)]
            axis.plot([1, 2, 3], ys, marker="o", color=color, linewidth=2, linestyle=style, label="%s (n=%s)" % (condition, ns[0]))
        axis.set_title(model, fontsize=11)
        axis.set_xlabel("scripted turn")
        axis.set_xticks([1, 2, 3])
        axis.set_ylim(0, 1)
        axis.grid(alpha=0.3)
    axes[0].set_ylabel("abandonment rate")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Abandonment by turn. %s." % judge, fontsize=12)
    fig.tight_layout()
    path = _save(fig, outdir, "fig1_abandonment_by_turn.png")
    captions.append({
        "file": path,
        "caption": "%s. Outcome: %s. Exclusion: %s. Each point is that cell's abandonment count divided by its n." % (judge, outcome, policy),
    })

    fig, axis = plt.subplots(figsize=(7.2, 4.4))
    x = range(len(MODELS))
    width = 0.36
    naive = [_rate(cells.get((model, "naive", 3))) for model in MODELS]
    ped = [_rate(cells.get((model, "pedagogical", 3))) for model in MODELS]
    naive_n = [cells.get((model, "naive", 3), {}).get("n", 0) for model in MODELS]
    ped_n = [cells.get((model, "pedagogical", 3), {}).get("n", 0) for model in MODELS]
    bars_naive = axis.bar([i - width / 2 for i in x], naive, width, label="naive", color=C_NAIVE)
    bars_ped = axis.bar([i + width / 2 for i in x], ped, width, label="pedagogical", color=C_PED)
    for bars, counts, ns in ((bars_naive, [cells.get((m, "naive", 3), {}).get("abandonment_count", 0) for m in MODELS], naive_n), (bars_ped, [cells.get((m, "pedagogical", 3), {}).get("abandonment_count", 0) for m in MODELS], ped_n)):
        for bar, count, n in zip(bars, counts, ns):
            axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02, "%d/%d" % (count, n), ha="center", fontsize=8)
    axis.set_xticks(list(x))
    axis.set_xticklabels(MODELS)
    axis.set_ylabel("turn-3 abandonment rate")
    axis.set_ylim(0, 1)
    axis.set_title("Turn-3 abandonment. %s." % judge)
    axis.legend(frameon=False)
    axis.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    path = _save(fig, outdir, "fig2_turn3_abandonment.png")
    captions.append({
        "file": path,
        "caption": "Turn 3. %s. Outcome: %s. Exclusion: %s. Labels are counts over the cell n." % (judge, outcome, policy),
    })

    fig, axis = plt.subplots(figsize=(8, 4.4))
    pairs = [(model, condition) for model in MODELS for condition in CONDITIONS]
    labels = ["%s\n%s" % (model.replace("gemini-2.5-", ""), condition) for model, condition in pairs]
    cave, deflect = [], []
    for model, condition in pairs:
        cell = cells.get((model, condition, 3), {})
        n = cell.get("n") or 1
        counts = cell.get("counts") or {}
        cave.append(counts.get("caves", 0) / n)
        deflect.append(counts.get("deflects", 0) / n)
    xpos = range(len(pairs))
    axis.bar(xpos, cave, 0.6, label="caves (five-way)", color="#8a1c2b")
    axis.bar(xpos, deflect, 0.6, bottom=cave, label="deflects (five-way)", color="#e08a98")
    axis.set_xticks(list(xpos))
    axis.set_xticklabels(labels, fontsize=9)
    axis.set_ylabel("turn-3 share of the cell")
    axis.set_ylim(0, 1)
    axis.set_title("Cave versus deflect at turn 3. Exploratory. %s." % judge)
    axis.legend(frameon=False)
    axis.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    path = _save(fig, outdir, "fig3_cave_vs_deflect.png")
    captions.append({
        "file": path,
        "caption": "Exploratory five-way split of the two abandonment stances. %s. Exclusion: %s. Deflects is the category proposed in this study." % (judge, policy),
    })

    fig, axis = plt.subplots(figsize=(6.6, 4.4))
    tone = figure_inputs["tone"]
    x = range(2)
    width = 0.36
    g = [tone["gemini"]["warmth"], tone["gemini"]["growth"]]
    o = [tone["gptoss"]["warmth"], tone["gptoss"]["growth"]]
    b1 = axis.bar([i - width / 2 for i in x], g, width, label="Gemini judge n=%d" % tone["gemini"]["n"], color="#c44e52")
    b2 = axis.bar([i + width / 2 for i in x], o, width, label="GPT-OSS-20b judge n=%d" % tone["gptoss"]["n"], color="#55a868")
    for bars in (b1, b2):
        for bar in bars:
            axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05, "%.2f" % bar.get_height(), ha="center", fontsize=8)
    axis.set_xticks(list(x))
    axis.set_xticklabels(["warmth", "growth encouragement"])
    axis.set_ylabel("mean score (1 to 5)")
    axis.set_ylim(0, 5.6)
    axis.set_title("Mean tone scores by judge")
    axis.legend(frameon=False, fontsize=8)
    axis.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    path = _save(fig, outdir, "fig4_judge_tone_gap.png")
    captions.append({
        "file": path,
        "caption": "Means after the validated exclusion rule. Gemini n=%d, GPT-OSS n=%d. Scale 1 to 5. A different-family judge is not described as de-biased. These means do not estimate whether warmth predicts abandonment." % (tone["gemini"]["n"], tone["gptoss"]["n"]),
    })

    bars = figure_inputs["kappa_bars"]
    fig, axis = plt.subplots(figsize=(7.6, 4.4))
    vals = [0.0 if value is None else value for _label, value, _n in bars]
    colors = ["#2e86ab" if value >= 0 else "#d1495b" for value in vals]
    rectangles = axis.bar(range(len(vals)), vals, 0.6, color=colors)
    for rect, value, (_label, _kappa, n) in zip(rectangles, vals, bars):
        axis.text(rect.get_x() + rect.get_width() / 2, value + 0.02, "%.2f\nn=%d" % (value, n), ha="center", va="bottom", fontsize=8)
    axis.set_xticks(range(len(bars)))
    axis.set_xticklabels([label for label, _value, _n in bars], fontsize=8)
    axis.set_ylabel("Cohen's kappa, abandonment vs non-abandonment")
    axis.set_ylim(min(-0.05, min(vals) - 0.05), 0.85)
    axis.axhline(0, color="black", linewidth=0.8)
    axis.set_title("Turn-3 agreement on the binary outcome")
    axis.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    path = _save(fig, outdir, "fig5_agreement_kappa.png")
    captions.append({
        "file": path,
        "caption": "Binary outcome, not five-way holds. Human bars use the frozen 80-item validation subset. %s GPT-OSS sensitivity n drops items whose source turn alignment is uncertain." % KAPPA_WORDING,
    })

    caption_path = os.path.join(outdir, "CAPTIONS.md")
    with open(caption_path, "w", encoding="utf-8") as handle:
        handle.write("# Figure captions\n\n")
        for item in captions:
            handle.write("## %s\n\n%s\n\n" % (os.path.basename(item["file"]), item["caption"]))
    return captions
