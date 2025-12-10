#!/usr/bin/env python3
"""Part B, immediate effect: the healthy controller with a weak right tibialis anterior.

    python analysis/part_b_immediate.py

For each seed, that seed's healthy result (results/healthy/seed<i>/healthy_asym.par,
both sides equal) is evaluated without re-optimization at tib_ant_r strengths
of 10 to 100% in steps of 10%. Walking is not assumed to get monotonically
harder as the muscle weakens, so the grid comes first. The bisection then
looks for the weakest strength that still walks the full 10 s, starting from
the weakest walking grid level and the strongest falling level below it, and
stops when the bracket is narrower than 1% of the maximum isometric force.

Writes results/dropfoot/immediate.csv (one row per evaluation) and
results/dropfoot/immediate_threshold.csv (the bracket per seed). Bisection
scenarios are written to scenarios/generated/.
"""

from __future__ import annotations

import pandas as pd

from dropfoot import ROOT
from dropfoot.evaluation import evaluate_cached, is_walking, summarize
from dropfoot.scenarios import GENERATED, SCENARIOS, strength_tag, write_dropfoot

SEEDS = (1, 2, 3)
GRID = [round(0.1 * i, 2) for i in range(1, 11)]
TOLERANCE = 0.01
OUT = ROOT / "results" / "dropfoot"


def scenario_for(factor: float):
    committed = SCENARIOS / f"dropfoot_{strength_tag(factor)}.scone"
    return committed if committed.exists() else write_dropfoot(factor, GENERATED)


def run(seed: int, factor: float, stage: str) -> dict:
    par = ROOT / f"results/healthy/seed{seed}/healthy_asym.par"
    sto, report = evaluate_cached(scenario_for(factor), par, f"immediate_{strength_tag(factor)}_s{seed}")
    row = summarize(sto, report)
    return {"seed": seed, "factor": factor, "stage": stage, "walks": is_walking(row), **row}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, brackets = [], []
    for seed in SEEDS:
        grid = [run(seed, f, "grid") for f in GRID]
        rows += grid
        walking = [r["factor"] for r in grid if r["walks"]]
        if not walking:
            brackets.append({"seed": seed, "falls_at": None, "walks_at": None, "note": "no grid level walks"})
            continue
        hi = min(walking)
        below = [r["factor"] for r in grid if not r["walks"] and r["factor"] < hi]
        lo = max(below) if below else 0.0
        non_monotonic = any(not r["walks"] and r["factor"] > hi for r in grid)
        while hi - lo > TOLERANCE + 1e-9 and lo > 0:
            mid = round(0.5 * (lo + hi), 4)
            r = run(seed, mid, "bisection")
            rows.append(r)
            if r["walks"]:
                hi = mid
            else:
                lo = mid
        brackets.append(
            {
                "seed": seed,
                "falls_at": lo,
                "walks_at": hi,
                "note": "falls at a stronger grid level too" if non_monotonic else "",
            }
        )
        print(f"seed {seed}: falls at {lo:.4g}, walks at {hi:.4g}")
    cols = ["seed", "factor", "stage", "walks", "cost", "duration_s", "n_strides"]
    df = pd.DataFrame(rows)
    df = df[cols + [c for c in df.columns if c not in cols]]
    df.to_csv(OUT / "immediate.csv", index=False, float_format="%.6g")
    pd.DataFrame(brackets).to_csv(OUT / "immediate_threshold.csv", index=False)
    print(df[cols].to_string(index=False))


if __name__ == "__main__":
    main()
