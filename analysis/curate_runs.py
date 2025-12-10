"""Copy the best result of each seed of one condition into results/<condition>/seed<i>/.

    python analysis/curate_runs.py healthy --seeds 1 2 3 --asym
    python analysis/curate_runs.py dropfoot_ta25 --seeds 1 2 3

Reads the latest run in results/raw/runs/<condition>.s<seed>/ and writes
best.par, history.txt, config.scone and run.json (see dropfoot.runs). With
--asym it also writes healthy_asym.par, the symmetric result written once per
side, which is the warm start of the drop-foot optimizations.
"""

from __future__ import annotations

import argparse
import json

from dropfoot import ROOT
from dropfoot.params import read_par, sym_to_asym, write_par
from dropfoot.runs import curate, latest_run
from dropfoot.scone import RUNS_DIR


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("condition")
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--asym", action="store_true")
    ap.add_argument("--dest", help="default results/<condition>")
    args = ap.parse_args()
    dest_root = ROOT / (args.dest or f"results/{args.condition}")
    rows = []
    for seed in args.seeds:
        run = latest_run(RUNS_DIR / f"{args.condition}.s{seed}")
        dest = dest_root / f"seed{seed}"
        s = curate(run, seed, dest)
        if args.asym:
            write_par(sym_to_asym(read_par(dest / "best.par")), dest / "healthy_asym.par")
        rows.append(s)
        print(
            f"seed {seed}: best {s.best_cost:.5f} at generation {s.best_generation} of {s.generations}, "
            f"{100 * s.rel_improvement_window:.2f}% better over the last window, converged={s.converged}"
        )
    (dest_root / "runs.json").write_text(json.dumps([r.__dict__ for r in rows], indent=2) + "\n")


if __name__ == "__main__":
    main()
