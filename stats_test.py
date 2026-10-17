"""Paired naive-versus-pedagogical test.

Default mode is validated: missing and malformed labels are excluded, not
counted as non-abandonment. --mode historical reproduces the published
script, which did count a missing label as non-abandonment, and prints that
warning when it happens.
"""

import argparse
import sys

from audit.analysis import judge_block
from audit.io import load_jsonl


def _print_block(block):
    print("Mode: %s" % block["mode"])
    print("Source: %s" % block["source"])
    print("Outcome: abandonment (caves + deflects) versus non-abandonment (holds + hedges + unaddressed).")
    print("Five-way holds are reported separately from non-abandonment.")
    print("A significant result for one model and a non-significant result for the other does not show different treatment effects.\n")
    for row in block["paired_turn3"]:
        print("%s  eligible pairs=%d  excluded=%d  warnings=%d" % (
            row["model"], row["eligible_pairs"], len(row["excluded"]), len(row["warnings"]),
        ))
        if row["eligible_pairs"]:
            print("  naive %d/%d -> pedagogical %d/%d" % (
                row["naive_abandonment_count"], row["eligible_pairs"],
                row["pedagogical_abandonment_count"], row["eligible_pairs"],
            ))
        print("  discordant: naive-only %d, pedagogical-only %d" % (
            row["discordant_naive_only"], row["discordant_pedagogical_only"],
        ))
        print("  resolved to five-way holds %d; persistent abandonment %d; new abandonment %d" % (
            row["resolved_to_five_way_holds"], row["persistent_abandonment"], row["new_abandonment"],
        ))
        print("  McNemar exact p = %.10f; chi2_cc = %.3f" % (
            row["p_exact"], row["chi2_continuity_correction"],
        ))
        for item in row["excluded"]:
            print("  excluded %s (%s)" % (item["record_id"], item["reason"]))
        for item in row["warnings"]:
            print("  warning %s" % item.get("record_id", ""))
            print("    %s" % item.get("warning", item.get("historical_behavior", "")))
        print()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", default="runs/scored.jsonl")
    parser.add_argument("--mode", choices=("validated", "historical"), default="validated")
    args = parser.parse_args(argv)
    rows = load_jsonl(args.inp)
    block = judge_block(rows, "historical" if args.mode == "historical" else "validated", args.inp, args.inp)
    _print_block(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
