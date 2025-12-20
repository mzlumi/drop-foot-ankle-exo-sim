"""Evaluate a result once, cache the output, and summarize it as one row of metrics.

A simulation *falls* when SCONE ends it before ``max_duration`` (10 s): the
tutorial gait scenarios stop when the centre of mass drops below the
termination height. A fallen run is reported with its fall time and is never
averaged with walking runs. Gait metrics need at least ``MIN_STRIDES``
right strides after the first two (start-up) strides.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from scone_gait.results import parse_report

from dropfoot import ROOT, scone
from dropfoot.gait import find_strides
from dropfoot.io import Storage, read_sto
from dropfoot.metrics import gait_summary

EVAL_CACHE = ROOT / "results" / "raw" / "eval"
MAX_DURATION = 10.0
MIN_STRIDES = 3


def evaluate_cached(
    scenario: str | Path, par: str | Path, name: str, overrides: dict | None = None, force: bool = False
) -> tuple[Storage, str]:
    """``.sto`` and objective breakdown of ``par`` in ``scenario``, cached under ``name``.

    The cache entry is reused only while the scenario text, the ``.par`` and
    the overrides are unchanged (their hash is stored next to it). Files the
    scenario includes are not hashed.
    """
    out = EVAL_CACHE / f"{name}.par"
    sto_path = out.with_name(out.name + ".sto")
    report = out.with_name(out.name + ".txt")
    key_path = out.with_name(out.name + ".key")
    key = cache_key(scenario, par, overrides)
    if force or not sto_path.exists() or not key_path.exists() or key_path.read_text() != key:
        scone.evaluate(scenario, par, out, overrides)
        key_path.write_text(key)
    return read_sto(sto_path), report.read_text()


def cache_key(scenario: str | Path, par: str | Path, overrides: dict | None = None) -> str:
    h = hashlib.sha256()
    for f in (scenario, par):
        h.update(Path(f).read_bytes())
        h.update(b"\0")
    h.update(repr(sorted((overrides or {}).items())).encode())
    return h.hexdigest()


def evaluate_many(jobs: list[tuple], workers: int = 6) -> list[tuple[Storage, str]]:
    """:func:`evaluate_cached` for each ``(scenario, par, name[, overrides])`` in parallel, results in order.

    Each SCONE evaluation runs in its own container on its own temporary
    scenario copy, so the threads only wait on subprocesses.
    """
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda job: evaluate_cached(*job), jobs))


def summarize(sto: Storage, report: str, skip_first: int = 2) -> dict[str, float]:
    """Cost, fall flag and time, and the gait metrics of :func:`dropfoot.metrics.gait_summary`."""
    duration = float(sto.time[-1])
    row: dict[str, float] = {
        "cost": parse_report(report).value,
        "duration_s": duration,
        "fell": float(duration < MAX_DURATION - 0.01),
    }
    n = len(find_strides(sto, "r", skip_first=skip_first))
    row["n_strides"] = float(n)
    if n >= MIN_STRIDES:
        row.update(gait_summary(sto, report, skip_first=skip_first).as_dict())
        row["n_strides"] = float(n)
    return row


def is_walking(row: dict[str, float]) -> bool:
    return not row.get("fell", 1.0) and row.get("n_strides", 0) >= MIN_STRIDES and not math.isnan(row.get("cost", math.nan))
