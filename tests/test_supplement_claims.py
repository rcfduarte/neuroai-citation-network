"""Every headline number quoted in the supplements is checked against the committed results.

The files `docs/supplements/claims/S*.yaml` list claims. Each claim names the supplement file, a `context`
string that must occur verbatim in it, the `shown` string (the number exactly as printed, which
must occur inside the context) and `expr`, a python expression that recomputes the number from
the committed results. The test fails if the sentence was edited away, if the printed number is
not the one in the context, or if the recomputed value rounds to something else.

Expressions may use `np`, `pd`, `json`, `Path`, `RESULTS` (the results directory) and `mod(name)`
which imports `neuroai_cn.<name>`.
"""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CLAIMS_DIR = ROOT / "docs" / "supplements" / "claims"


def _load() -> list[dict]:
    claims: list[dict] = []
    for path in sorted(CLAIMS_DIR.glob("S*.yaml")):
        claims.extend(yaml.safe_load(path.read_text(encoding="utf-8")) or [])
    return claims


def _decimals(shown: str) -> int:
    m = re.search(r"\.(\d+)", shown)
    return len(m.group(1)) if m else 0


def _number(shown: str) -> float:
    return float(shown.replace(",", "").replace("−", "-").replace("%", ""))


def _eval(expr: str):
    env = {
        "np": np,
        "pd": pd,
        "json": json,
        "Path": Path,
        "RESULTS": ROOT / "results",
        "mod": lambda name: importlib.import_module(f"neuroai_cn.{name}"),
    }
    return eval(expr, {"__builtins__": __builtins__}, env)


CLAIM_LIST = _load()


@pytest.mark.parametrize("claim", CLAIM_LIST, ids=[c["id"] for c in CLAIM_LIST])
def test_claim(claim):
    text = (ROOT / claim["file"]).read_text(encoding="utf-8")
    assert claim["context"] in text, f"{claim['id']}: context sentence no longer in {claim['file']}"
    assert claim["shown"] in claim["context"], f"{claim['id']}: shown not inside context"
    value = float(_eval(claim["expr"]))
    d = _decimals(claim["shown"])
    assert round(value, d) == pytest.approx(_number(claim["shown"]), abs=0.5 * 10**-d * 1e-6), (
        f"{claim['id']}: text says {claim['shown']}, data give {value}"
    )


def test_claims_file_present_and_nonempty():
    assert CLAIMS_DIR.is_dir(), "docs/supplements/claims/ is missing"
    assert len(CLAIM_LIST) >= 1
