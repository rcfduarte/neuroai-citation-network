"""Tripwire: no machine-specific paths in tracked code.

Every tracked text file under src/, scripts/ and tests/ must be free of '/home/', '/media/' and
'Desktop' (the author's home directory and notes folder). Paths come from
neuroai_cn.config, which is overridable with the NEUROAI_DATA environment variable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("/home/", "/media/", "Desktop")
# This test names the forbidden strings, so it excludes itself.
EXCLUDED = {"tests/test_no_local_paths.py"}


def _tracked_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "src", "scripts", "tests"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [f for f in out.splitlines() if f and f not in EXCLUDED]


def test_no_local_paths_in_tracked_files():
    offenders = []
    for rel in _tracked_files():
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue  # binary or deleted in the working tree
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(token in line for token in FORBIDDEN):
                offenders.append(f"{rel}:{lineno}: {line.strip()[:100]}")
    assert not offenders, "machine-specific paths in tracked files:\n" + "\n".join(offenders)
