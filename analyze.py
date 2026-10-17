"""Print stance rates. Writes tables under the chosen output directory, never by rewriting source labels."""

import argparse
import csv
import sys
from pathlib import Path

from audit.analysis import judge_block
from audit.io import load_jsonl
from audit.protect import assert_writable


def _write(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", default="runs/scored.jsonl")
    parser.add_argument("--outdir", default="audit_out/tables")
    parser.add_argument("--mode", choices=("validated", "historical"), default="validated")
    args = parser.parse_args(argv)
    for name in ("distribution.csv", "tone.csv"):
        assert_writable(Path(args.outdir) / name)
    rows = load_jsonl(args.inp)
    block = judge_block(rows, "historical" if args.mode == "historical" else "validated", args.inp, args.inp)
    flat = []
    for cell in block["distribution"]["cells"]:
        flat.append({
            "model": cell["model"],
            "condition": cell["condition"],
            "turn": cell["turn"],
            "n": cell["n"],
            "holds": cell["counts"]["holds"],
            "hedges": cell["counts"]["hedges"],
            "deflects": cell["counts"]["deflects"],
            "caves": cell["counts"]["caves"],
            "unaddressed": cell["counts"]["unaddressed"],
            "abandonment": cell["abandonment_count"],
            "non_abandonment": cell["non_abandonment_count"],
        })
    _write(flat, Path(args.outdir) / "distribution.csv")
    print("mode %s" % block["mode"])
    print("uncertain records %d; excluded %d" % (
        len(block["distribution"]["uncertain_records"]),
        len(block["distribution"]["excluded"]),
    ))
    for cell in flat:
        if cell["turn"] == 3:
            print("%s %s turn 3 abandonment %d/%d; five-way holds %d" % (
                cell["model"], cell["condition"], cell["abandonment"], cell["n"], cell["holds"],
            ))
    print("tables written to %s" % args.outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
