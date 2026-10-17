"""Loaders. They do not rewrite the files they read."""

import csv
import json
from pathlib import Path


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows.append({"line": line_no, "rec": json.loads(line)})
    return rows


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_cases(path):
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["cases"]


def transcript_key(rec):
    return (rec["case_id"], rec["model"], rec["condition"])


def format_key(key):
    return "%s / %s / %s" % key


def sha256_file(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_size(path):
    return Path(path).stat().st_size
