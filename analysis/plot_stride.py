#!/usr/bin/env python3
"""Plot one right-side stride: joint angles, shank gyroscope, ankle moment and vertical GRF.

This is the sign check behind docs/conventions.md: every new signal is plotted
before it is used.

    python analysis/plot_stride.py results/sign_check/tutorial_stride.sto figures/sign_check_stride.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scone_gait.cycles import extract_gait_cycles

from dropfoot.io import read_sto

PANELS = [
    ("hip_flexion_r", "Hip angle (deg)\n+ flexion", np.degrees),
    ("knee_angle_r", "Knee angle (deg)\n+ extension", np.degrees),
    ("ankle_angle_r", "Ankle angle (deg)\n+ dorsiflexion", np.degrees),
    ("tibia_r.ang_vel_z", "Shank gyro z (deg/s)\n+ shank rotates forward", np.degrees),
    ("ankle_angle_r.moment", "Ankle muscle moment (N m)\n+ dorsiflexing", lambda x: x),
    ("leg1_r.grf_norm_y", "Vertical GRF (BW)", lambda x: x),
]


def plot_stride(sto_path: str | Path, out: str | Path, threshold: float = 0.05) -> Path:
    sto = read_sto(sto_path)
    cycles = [c for c in extract_gait_cycles(sto, threshold) if c.side == "r"]
    if not cycles:
        raise ValueError("no complete right-side stride in the file")
    c = cycles[0]
    m = (sto.time >= c.begin) & (sto.time <= c.end)
    pct = 100.0 * (sto.time[m] - c.begin) / c.duration
    toe_off = 100.0 * c.stance_fraction

    fig, axes = plt.subplots(len(PANELS), 1, figsize=(6, 10), sharex=True)
    for ax, (label, ylabel, fn) in zip(axes, PANELS):
        ax.plot(pct, fn(sto[label][m]), color="k", lw=1.5)
        ax.axhline(0, color="0.7", lw=0.8)
        ax.axvline(toe_off, color="tab:red", lw=1, ls="--")
        ax.set_ylabel(ylabel, fontsize=8)
        ax.tick_params(labelsize=8)
    axes[0].set_title(f"Right stride {c.begin:.2f} to {c.end:.2f} s (heel strike at 0%, toe-off dashed)", fontsize=9)
    axes[-1].set_xlabel("Gait cycle (%)")
    axes[-1].set_xlim(0, 100)
    fig.tight_layout()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sto")
    p.add_argument("out")
    args = p.parse_args(argv)
    print(plot_stride(args.sto, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
