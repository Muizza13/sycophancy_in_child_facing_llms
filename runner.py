"""Run every (case x model x condition) through the 3-turn pressure protocol.

Resumable: re-running appends only the combinations not already in --out, so you
can add a model to DEFAULT_MODELS and fill in just its rows. Use --fresh to redo
from scratch.
"""
import argparse
import json
import os

from models import build_models
from scenarios import SYSTEM_PROMPTS, child_turns, load_cases


def run_one(model, system, case):
    messages, turns_out = [], []
    for i, child_msg in enumerate(child_turns(case), start=1):
        messages.append({"role": "user", "content": child_msg})
        meta = {"turn": i, "correct_answer": case["correct_answer"],
                "wrong_answer": case["child_wrong_answer"], "case_id": case["id"]}
        reply = model.chat(messages, system, meta=meta)
        messages.append({"role": "assistant", "content": reply})
        turns_out.append({"turn": i, "child": child_msg, "model": reply})
    return turns_out


def load_done(path):
    done = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    done.add((r["case_id"], r["model"], r["condition"]))
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="test_cases.json")
    ap.add_argument("--out", default="runs/transcripts.jsonl")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--conditions", default="naive,pedagogical")
    ap.add_argument("--fresh", action="store_true", help="overwrite instead of resume")
    args = ap.parse_args()

    cases = load_cases(args.cases)
    if args.limit:
        cases = cases[: args.limit]
    models = build_models(mock=args.mock)
    conditions = args.conditions.split(",")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    if args.fresh and os.path.exists(args.out):
        os.remove(args.out)
    done = load_done(args.out)
    if done:
        print("Resuming: %d combinations already recorded, skipping them." % len(done))

    n = failed = skipped = 0
    with open(args.out, "a") as f:
        for case in cases:
            for model in models:
                for cond in conditions:
                    if (case["id"], model.name, cond) in done:
                        skipped += 1
                        continue
                    try:
                        turns = run_one(model, SYSTEM_PROMPTS[cond], case)
                    except Exception as e:
                        failed += 1
                        print("  FAILED  %-10s %-22s %s: %s" % (case["id"], model.name, cond, e))
                        continue
                    rec = {"case_id": case["id"], "error_type": case["error_type"],
                           "subject": case["subject"], "correct_answer": case["correct_answer"],
                           "child_wrong_answer": case["child_wrong_answer"],
                           "answer_pattern": case.get("answer_pattern", ""),
                           "model": model.name, "condition": cond, "turns": turns}
                    f.write(json.dumps(rec) + "\n")
                    f.flush()
                    n += 1
                    print("  ok      %-10s %-22s %s" % (case["id"], model.name, cond))
    print("\nWrote %d new transcripts to %s (%d skipped, %d failed)" % (n, args.out, skipped, failed))


if __name__ == "__main__":
    main()
