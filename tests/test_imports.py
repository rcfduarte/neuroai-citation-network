"""Every module under src/neuroai_cn imports cleanly and without side effects.

Importing must not open DuckDB and must not create files or directories inside the repository
or the data root (work happens in main()/build(), never at import time). Modules that need a
heavy optional third-party package are skipped, with the package named in the reason.
"""

from __future__ import annotations

import builtins
import importlib
import os
import subprocess
from pathlib import Path

import pytest

from neuroai_cn import config

SRC = Path(config.REPO_ROOT) / "src"
OPTIONAL_PACKAGES = {"igraph", "leidenalg", "sklearn", "ruptures", "scipy"}


def _module_files() -> list[str]:
    """Tracked .py files under src/ (the filesystem if this is not a git checkout)."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "src"],
            cwd=config.REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split()
        files = [f for f in out if f.endswith(".py")]
    except (OSError, subprocess.CalledProcessError):
        files = []
    if not files:
        files = [str(p.relative_to(config.REPO_ROOT)) for p in SRC.rglob("*.py")]
    return sorted(files)


def _module_name(rel: str) -> str:
    parts = list(Path(rel).relative_to("src").with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


MODULES = sorted({_module_name(f) for f in _module_files()})


def _ours(path) -> bool:
    try:
        p = Path(os.fspath(path)).resolve()
    except (TypeError, ValueError):
        return False
    return any(p.is_relative_to(root) for root in (config.REPO_ROOT, config.DATA_ROOT))


def test_module_list_is_not_empty():
    assert len(MODULES) > 30
    assert "neuroai_cn.config" in MODULES


@pytest.mark.parametrize("module", MODULES)
def test_import_has_no_side_effects(module, monkeypatch):
    # Pre-import the heavy libraries so their own cache files are not counted against the module.
    for name in ("matplotlib.pyplot", "numpy", "pandas", "duckdb"):
        importlib.import_module(name)
    import duckdb

    events: list[str] = []

    def no_duckdb(*args, **kwargs):
        raise AssertionError(f"{module} opened DuckDB at import time")

    real_mkdir = Path.mkdir
    real_makedirs = os.makedirs
    real_open = builtins.open

    def mkdir(self, *args, **kwargs):
        if _ours(self) and not self.exists():
            events.append(f"mkdir {self}")
        return real_mkdir(self, *args, **kwargs)

    def makedirs(name, *args, **kwargs):
        if _ours(name) and not os.path.exists(name):
            events.append(f"makedirs {name}")
        return real_makedirs(name, *args, **kwargs)

    def guarded_open(file, mode="r", *args, **kwargs):
        writing = any(c in mode for c in "wax+")
        if writing and isinstance(file, (str, bytes, os.PathLike)) and _ours(file):
            events.append(f"open({mode}) {file}")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", no_duckdb)
    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(os, "makedirs", makedirs)
    monkeypatch.setattr(builtins, "open", guarded_open)

    try:
        importlib.import_module(module)
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.split(".")[0] in OPTIONAL_PACKAGES:
            pytest.skip(f"needs optional dependency {exc.name}")
        raise
    assert not events, f"{module} touched the filesystem at import time: {events}"
