"""Build a future blinded rating sample.

The frozen rating_key.csv is not a product of this command. Output goes to a
new directory. Existing completed rating files are not replaced.
"""

import argparse
import sys
from pathlib import Path

from audit.io import load_cases, load_jsonl
from audit.protect import assert_writable, repo_root
from audit.sample import select_sample, turn3_stance_map, write_sample


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcripts", default="runs/transcripts.jsonl")
    parser.add_argument("--cases", default="test_cases.json")
    parser.add_argument("--judge-a", default="runs/scored.jsonl")
    parser.add_argument("--judge-b", default="runs/scored_groq.jsonl")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--sample-id", default=None)
    parser.add_argument("--n", type=int, default=80)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    root = repo_root()
    sample_id = args.sample_id or "future_n%d_seed%d" % (args.n, args.seed)
    directory = Path(args.out_dir) if args.out_dir else root / "samples" / sample_id
    assert_writable(directory / "rating_sheet.csv", root)
    assert_writable(directory / "unblinding_key.csv", root)
    transcripts = load_jsonl(args.transcripts)
    judge_a = turn3_stance_map(load_jsonl(args.judge_a))
    judge_b = turn3_stance_map(load_jsonl(args.judge_b))
    presentation, record = select_sample(transcripts, judge_a, judge_b, args.n, args.seed)
    record["sample_id"] = sample_id
    written = write_sample(
        directory, presentation, record, transcripts, judge_a, judge_b, load_cases(args.cases), root,
    )
    print("Wrote %d items to %s" % (written["n"], written["sheet"]))
    print("Selection record: %s" % written["selection"])
    print("This sample does not replace rating_key.csv.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
