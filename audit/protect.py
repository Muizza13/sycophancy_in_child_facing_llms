"""Refuse writes that would replace frozen pilot artifacts."""

from pathlib import Path

from audit.constants import FROZEN_RELATIVE, PROTECTED_RATING_NAMES


def repo_root():
    return Path(__file__).resolve().parents[1]


def resolved(path):
    return Path(path).expanduser().resolve()


def frozen_paths(root=None):
    root = resolved(root or repo_root())
    return {root / rel for rel in FROZEN_RELATIVE}


def is_frozen(path, root=None):
    return resolved(path) in frozen_paths(root)


def assert_writable(path, root=None):
    """Raise SystemExit before any truncate, append, or delete."""
    path = resolved(path)
    root = resolved(root or repo_root())
    if path in frozen_paths(root):
        raise SystemExit(
            "refusing to write frozen historical file: %s" % path
        )
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = None
    if relative is not None and relative.as_posix() in set(FROZEN_RELATIVE):
        raise SystemExit(
            "refusing to write frozen historical file: %s" % path
        )
    if path.name in PROTECTED_RATING_NAMES and relative is not None and len(relative.parts) == 1:
        raise SystemExit(
            "refusing to replace completed rating artifact at repo root: %s" % path.name
        )
    return path
