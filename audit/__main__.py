"""Offline audit commands.

  python -m audit validate
  python -m audit reproduce
  python -m audit manifest
"""

import argparse
import sys
from pathlib import Path

from audit.constants import ORIGINAL_COMMIT
from audit.manifest import initialize_manifest
from audit.protect import repo_root
from audit.reproduce import run
from audit.validate import format_issues, validate_repository


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline audit of the frozen pilot")
    parser.add_argument("command", choices=("validate", "reproduce", "manifest"))
    parser.add_argument("--root", default=None)
    parser.add_argument("--outdir", default=None)
    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else repo_root()
    if args.command == "validate":
        issues = validate_repository(root)
        print(format_issues(issues))
        return 1 if issues else 0
    if args.command == "manifest":
        path = root / "evidence_manifest.json"
        initialize_manifest(root, path)
        print("initialized %s from commit %s" % (path, ORIGINAL_COMMIT))
        return 0
    outdir = Path(args.outdir) if args.outdir else root / "audit_out"
    figure_dir = root / "figures" / "validated_v2"
    code = run(
        root,
        outdir,
        manifest_path=root / "evidence_manifest.json",
        figure_dir=figure_dir,
    )
    if code != 0:
        print("reproduce failed with exit %d" % code)
        return code
    print("wrote %s" % outdir)
    print("validated figures: %s" % figure_dir)
    print("validation issues are listed in %s" % (outdir / "validation.txt"))
    print("trusted manifest was left unchanged")
    print("historical Gemini headline check exit %d" % code)
    return code


if __name__ == "__main__":
    sys.exit(main())
