#!/usr/bin/env python3
"""Regenerate every figure (and the tables written next to them) from the committed results.

    python analysis/make_figures.py [--only part_c part_e ...]

Runs the analysis scripts in order. Simulations are evaluated from the
committed .par files and cached in results/raw/eval/, so the first run takes
a while (SCONE in Docker) and later runs are quick. The two scripts that read
the Camargo et al. (2021) recordings are skipped, with a message, when
data/raw/camargo/ is missing (see data/README.md); their committed tables
are not touched then.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

from dropfoot import ROOT

CAMARGO = ROOT / "data" / "raw" / "camargo"
STEPS = [
    ("normative", ["analysis/normative.py"], True, "figures/normative_camargo_treadmill_1.20mps.png"),
    ("sign_check", ["analysis/plot_stride.py", "results/sign_check/tutorial_stride.sto", "figures/sign_check_stride.png"], False,
     "figures/sign_check_stride.png"),
    ("part_a", ["analysis/part_a.py"], False, "figures/healthy_vs_normative.png"),
    ("device_check", ["analysis/device_check.py"], False, "results/device_check/summary.json"),
    ("part_b_immediate", ["analysis/part_b_immediate.py"], False, "results/dropfoot/immediate*.csv"),
    ("part_b_adapted", ["analysis/part_b_adapted.py"], False, "figures/dropfoot_overlay.png"),
    ("part_c", ["analysis/part_c.py"], False, "figures/actuator_{requirement,sweep,torque_speed}.png"),
    ("part_d_validation", ["analysis/part_d_validation.py", "--dropfoot", "0.25"], False, "figures/detector_trace.png"),
    ("part_d_camargo", ["analysis/part_d_camargo.py"], True, "figures/detector_sim_vs_real.png"),
    ("part_e", ["analysis/part_e.py"], False, "figures/sea_{bode,tracking}.png"),
    ("part_f_frozen", ["analysis/part_f.py", "frozen"], False, "results/device/frozen.csv, selection.json"),
    ("part_f_soft", ["analysis/part_f.py", "soft"], False, "results/device/frozen_soft_springs.csv"),
    ("part_f", ["analysis/part_f.py", "compare"], False, "figures/device_comparison.png"),
    ("part_f_converged", ["analysis/part_f.py", "converged"], False, "results/device/converged_check.md"),
    ("animation", ["analysis/animate.py"], False, "figures/dropfoot_conditions.gif"),
    ("part_f5", ["analysis/part_f5.py", "evaluate"], False, "figures/robustness.png"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="step names: " + ", ".join(s[0] for s in STEPS))
    args = ap.parse_args()
    failed = []
    for name, cmd, needs_camargo, figure in STEPS:
        if args.only and name not in args.only:
            continue
        if needs_camargo and not CAMARGO.exists():
            print(f"[skip] {name}: data/raw/camargo/ not found")
            continue
        t0 = time.time()
        proc = subprocess.run([sys.executable, *cmd], cwd=ROOT, capture_output=True, text=True)
        status = "ok" if proc.returncode == 0 else "FAILED"
        print(f"[{status}] {name} ({time.time() - t0:.0f} s): {figure}")
        if proc.returncode:
            failed.append(name)
            print(proc.stdout[-2000:], proc.stderr[-2000:], sep="\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
