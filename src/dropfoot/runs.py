"""Curate SCONE optimization folders: best ``.par`` per seed and a convergence check.

SCONE writes ``<generation>_<mean cost>_<best cost>.par`` (costs rounded to
three decimals) each time the best cost improves, plus ``history.txt`` with one line per generation. A run is
called *converged* here when the best cost improved by less than
``CONVERGED_REL`` (relative) over its last ``CONVERGED_WINDOW`` generations.
This is a practical criterion for comparing conditions, not a proof of a
global optimum: CMA-ES results depend on the seed, so every condition is
reported over several seeds.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

CONVERGED_WINDOW = 40  # generations
CONVERGED_REL = 0.01

_PAR = re.compile(r"^(\d+)_([-\d.eE+]+)_([-\d.eE+]+)\.par$")
_INIT = re.compile(r"^\s*init_file\s*=\s*\"?([^\"\s]+)", re.MULTILINE)


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    seed: int
    generations: int  # last generation in history.txt
    best_cost: float
    best_generation: int
    best_par: str  # file name inside the run folder
    best_cost_window_start: float  # best cost at generation (generations - window)
    rel_improvement_window: float
    converged: bool
    init_file: str = ""  # warm start; an earlier run's .par for a continuation


def init_file(run: Path) -> str:
    """The ``init_file`` of the run's optimizer, as written in its ``config.scone`` ("" if none)."""
    config = run / "config.scone"
    m = _INIT.search(config.read_text()) if config.exists() else None
    return m.group(1) if m else ""


def par_files(run: Path) -> list[tuple[int, float, Path]]:
    """(generation, best cost, path) of every numbered ``.par`` written by the run, by generation.

    SCONE copies the init file into the run folder; a continuation run starts
    from a numbered ``.par`` of an earlier run, so that copy is skipped.
    """
    skip = Path(init_file(run)).name
    out = []
    for p in run.glob("*.par"):
        m = _PAR.match(p.name)
        if m and p.name != skip:
            out.append((int(m.group(1)), float(m.group(3)), p))
    return sorted(out)


def last_generation(run: Path) -> int:
    lines = [ln for ln in (run / "history.txt").read_text().splitlines()[1:] if ln.strip()]
    return int(lines[-1].split()[0]) if lines else 0


def best_until(pars: list[tuple[int, float, Path]], generation: int) -> float:
    costs = [c for g, c, _ in pars if g <= generation]
    return min(costs) if costs else float("nan")


def summarize_run(run: Path, seed: int, window: int = CONVERGED_WINDOW, rel: float = CONVERGED_REL) -> RunSummary:
    pars = par_files(run)
    if not pars:
        raise FileNotFoundError(f"no numbered .par files in {run}")
    # files are written only when the best improves and names round the cost, so the last one is the best
    gen, cost, path = pars[-1]
    last = last_generation(run)
    start = best_until(pars, last - window)
    improvement = (start - cost) / abs(start) if np.isfinite(start) else float("nan")
    return RunSummary(
        run_id=run.name,
        seed=seed,
        generations=last,
        best_cost=cost,
        best_generation=gen,
        best_par=path.name,
        best_cost_window_start=start,
        rel_improvement_window=float(improvement),
        converged=bool(np.isfinite(improvement) and improvement < rel),
        init_file=init_file(run),
    )


def latest_run(root: Path) -> Path:
    """Most recent run folder (SCONE prefixes run ids with the start date and time)."""
    runs = sorted(p for p in root.iterdir() if p.is_dir() and (p / "history.txt").exists())
    if not runs:
        raise FileNotFoundError(f"no SCONE run in {root}")
    return runs[-1]


def curate(run: Path, seed: int, dest: Path) -> RunSummary:
    """Copy the best ``.par`` (as ``best.par``), ``history.txt`` and the run's ``config.scone`` to ``dest``."""
    summary = summarize_run(run, seed)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(run / summary.best_par, dest / "best.par")
    for name in ("history.txt", "config.scone"):
        if (run / name).exists():
            shutil.copyfile(run / name, dest / name)
    (dest / "run.json").write_text(json.dumps(asdict(summary), indent=2) + "\n")
    return summary
