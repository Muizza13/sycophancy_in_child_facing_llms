"""Naive-to-pedagogical transitions at turn 3."""

import argparse
import sys

from audit.analysis import judge_block
from audit.constants import STANCES
from audit.io import load_jsonl


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", default="runs/scored.jsonl")
    parser.add_argument("--mode", choices=("validated", "historical"), default="validated")
    args = parser.parse_args(argv)
    rows = load_jsonl(args.inp)
    block = judge_block(rows, "historical" if args.mode == "historical" else "validated", args.inp, args.inp)
    for row in block["paired_turn3"]:
        print("=== %s eligible pairs %d, excluded %d ===" % (row["model"], row["eligible_pairs"], len(row["excluded"])))
        matrix = row["transition_matrix_naive_to_pedagogical"]
        header = "".join("%-14s" % name for name in STANCES)
        print("naive \\ pedagogical  " + header)
        for left in list(STANCES) + [key for key in matrix if key not in STANCES]:
            counts = matrix.get(left, {})
            print("%-22s" % left + "".join("%-14d" % counts.get(name, 0) for name in STANCES))
        print("resolved to five-way holds: %d" % row["resolved_to_five_way_holds"])
        print("persistent abandonment: %d %s" % (row["persistent_abandonment"], ", ".join(row["persistent_case_ids"])))
        print("new abandonment: %d %s" % (row["new_abandonment"], ", ".join(row["new_abandonment_case_ids"])))
        for item in row["excluded"]:
            print("excluded %s (%s) %s" % (item["record_id"], item["reason"], item.get("detail", "")))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
