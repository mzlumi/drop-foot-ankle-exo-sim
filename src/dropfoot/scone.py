"""Thin wrapper around headless SCONE (``sconecmd``) in Docker.

The Docker image is the one built by the companion repository
mzlumi/scone-pathological-gait (``docker/Dockerfile``, tagged
``scone-headless:latest``). Its ``scripts/scone.sh`` only accepts scenarios
inside that repository, so this module repeats the same ``docker run`` call
with this repository mounted at ``/work`` instead:

* ``optimize``: ``sconecmd -o <scenario> -r <output root>`` with a CMA-ES seed
  (``CmaOptimizer.random_seed``), a generation limit and a thread limit. SCONE
  creates one folder per run inside the output root.
* ``evaluate``: ``sconecmd -e <name>.par -r <out>``. SCONE finds the scenario
  of a ``.par`` file as ``<name>.scone`` in the same folder, so the scenario
  and the ``.par`` are copied side by side into ``scenarios/`` under a unique
  temporary name, which keeps every relative path in the scenario valid.

SCONE settings (data output rate, which channels are written) come from
``scenarios/settings/scone-settings.zml``, mounted read-only where SCONE looks
for its settings file.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from dropfoot import ROOT

IMAGE = os.environ.get("SCONE_IMAGE", "scone-headless:latest")
CONTAINER_ROOT = "/work"
SETTINGS_DIR = ROOT / "scenarios" / "settings"
RUNS_DIR = ROOT / "results" / "raw" / "runs"
EVAL_DIR = ROOT / "results" / "raw" / "eval"


def container_path(path: str | Path, root: Path = ROOT) -> str:
    """Path of a file inside the repository as seen from the container."""
    rel = Path(path).resolve().relative_to(root.resolve())
    return f"{CONTAINER_ROOT}/{rel.as_posix()}" if str(rel) != "." else CONTAINER_ROOT


def docker_prefix(name: str | None = None, root: Path = ROOT, settings_dir: Path = SETTINGS_DIR) -> list[str]:
    """The ``docker run`` part of every command."""
    cmd = ["docker", "run", "--rm"]
    if name:
        cmd += ["--name", name]
    cmd += ["-v", f"{root.resolve()}:{CONTAINER_ROOT}"]
    cmd += ["-v", f"{settings_dir.resolve()}:/root/.config/SCONE:ro"]
    cmd += [IMAGE]
    return cmd


def optimize_command(
    scenario: str | Path,
    seed: int,
    output_root: str | Path,
    generations: int,
    threads: int = 3,
    overrides: dict[str, object] | None = None,
    name: str | None = None,
    root: Path = ROOT,
) -> list[str]:
    """Command line that optimizes a scenario with one CMA-ES seed."""
    args = [
        "-o", container_path(scenario, root),
        "-r", container_path(output_root, root),
        "-q",
        f"CmaOptimizer.random_seed={seed}",
        f"CmaOptimizer.max_generations={generations}",
        f"CmaOptimizer.max_threads={threads}",
    ]
    args += [f"{k}={v}" for k, v in (overrides or {}).items()]
    return docker_prefix(name, root) + args


@dataclass(frozen=True)
class EvalFiles:
    """Temporary files of one evaluation and where its output goes."""

    scenario: Path  # temporary copy of the scenario in scenarios/
    par: Path  # temporary copy of the .par next to it
    output: Path  # SCONE writes <output>.sto
    report: Path  # objective breakdown printed by sconecmd

    def cleanup(self) -> None:
        for p in (self.scenario, self.par):
            p.unlink(missing_ok=True)


def prepare_evaluation(
    scenario: str | Path, par: str | Path, output: str | Path, tag: str | None = None
) -> EvalFiles:
    """Copy scenario and .par side by side so SCONE resolves paths as in the scenario."""
    scenario, par, output = Path(scenario), Path(par), Path(output)
    tag = tag or uuid.uuid4().hex[:10]
    tmp_scenario = scenario.parent / f".eval_{tag}.scone"
    tmp_par = scenario.parent / f".eval_{tag}.par"
    shutil.copyfile(scenario, tmp_scenario)
    shutil.copyfile(par, tmp_par)
    output.parent.mkdir(parents=True, exist_ok=True)
    return EvalFiles(tmp_scenario, tmp_par, output, output.with_name(output.name + ".txt"))


def evaluate_command(files: EvalFiles, overrides: dict[str, object] | None = None, root: Path = ROOT) -> list[str]:
    args = ["-e", container_path(files.par, root), "-r", container_path(files.output, root)]
    args += [f"{k}={v}" for k, v in (overrides or {}).items()]
    return docker_prefix(None, root) + args


def evaluate(
    scenario: str | Path,
    par: str | Path,
    output: str | Path,
    overrides: dict[str, object] | None = None,
) -> Path:
    """Evaluate ``par`` with ``scenario``; returns the written ``.sto`` file.

    ``output`` is a path such as ``results/raw/eval/x.par``; SCONE writes
    ``x.par.sto`` and the objective breakdown is saved as ``x.par.txt``.
    """
    files = prepare_evaluation(scenario, par, output)
    try:
        proc = subprocess.run(evaluate_command(files, overrides), capture_output=True, text=True)
    finally:
        files.cleanup()
    files.report.write_text(proc.stdout + proc.stderr)
    sto = files.output.with_name(files.output.name + ".sto")
    if proc.returncode != 0 or not sto.exists():
        raise RuntimeError(f"SCONE evaluation failed, see {files.report}")
    return sto


def optimize(
    scenario: str | Path,
    seed: int,
    generations: int,
    output_root: str | Path | None = None,
    threads: int = 3,
    overrides: dict[str, object] | None = None,
    log: str | Path | None = None,
) -> int:
    """Run one optimization to the end; SCONE writes into ``output_root/<run id>/``."""
    scenario = Path(scenario)
    output_root = Path(output_root) if output_root else RUNS_DIR / f"{scenario.stem}.s{seed}"
    output_root.mkdir(parents=True, exist_ok=True)
    name = f"scone-{scenario.stem}-s{seed}-{uuid.uuid4().hex[:6]}".replace("_", "-")
    cmd = optimize_command(scenario, seed, output_root, generations, threads, overrides, name)
    log = Path(log) if log else output_root / "sconecmd.log"
    with open(log, "w") as fh:
        return subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT).returncode
