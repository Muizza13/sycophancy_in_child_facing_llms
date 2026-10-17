"""Regenerate figures from the offline summary. Historical PNGs in figures/ are frozen."""

import argparse
import sys
from pathlib import Path

from audit.analysis import build_report, load_study
from audit.protect import repo_root
from audit.reproduce import write_figure_bundle
from audit.validate import validate_repository


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    parser.add_argument("--outdir", default=None)
    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else repo_root()
    outdir = Path(args.outdir) if args.outdir else root / "figures" / "validated_v2"
    report = build_report(load_study(root))
    report["validation_issues"] = [issue.as_dict() for issue in validate_repository(root)]
    write_figure_bundle(report, outdir, root)
    print("wrote %s" % outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
