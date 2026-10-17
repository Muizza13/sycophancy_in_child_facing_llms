"""Compare two judge files. Keys and turns that do not match are listed."""

import argparse
import sys

from audit.analysis import compare_judges
from audit.io import load_jsonl
from audit.stats import cohens_kappa, confusion


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", default="runs/scored.jsonl")
    parser.add_argument("--b", default="runs/scored_groq.jsonl")
    parser.add_argument("--mode", choices=("validated", "historical"), default="validated")
    args = parser.parse_args(argv)
    report = compare_judges(load_jsonl(args.a), load_jsonl(args.b), "historical" if args.mode == "historical" else "validated")
    raw, kappa = cohens_kappa(report["pairs"])
    print("mode %s" % report["mode"])
    print("compared turn labels %d" % report["compared_turn_labels"])
    print("raw agreement %s  kappa %s" % (raw, kappa))
    print("only in A: %d" % len(report["only_in_a"]))
    print("only in B: %d" % len(report["only_in_b"]))
    print("excluded records: %d" % len(report["excluded"]))
    for item in report["excluded"]:
        print("  excluded %s (%s)" % (item["record_id"], item["reason"]))
    print("unmatched turns: %d" % len(report["unmatched_turns"]))
    for item in report["unmatched_turns"]:
        print("  unmatched %s turn %s" % (item["record_id"], item["turn"]))
    matrix = confusion(report["pairs"])
    print("confusion labels: %s" % ", ".join(matrix["labels"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
