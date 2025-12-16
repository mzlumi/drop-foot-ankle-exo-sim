#!/usr/bin/env python3
"""Side-by-side stick-figure animation of the drop-foot conditions (Part G media).

    python analysis/animate.py [--seed 1] [--start 5] [--duration 3]

Draws the planar model from the body origins logged in the evaluated .sto
files (joint centres: hip, knee, ankle, heel, metatarsophalangeal joint, and
the lumbar joint with the torso orientation), for the re-optimized no-device,
passive AFO and active AFO conditions at 25% tibialis anterior strength
(results/device/), next to the healthy gait. The right (affected) leg is red,
the left grey; the panel title shows the device torque. The camera follows
the pelvis. Writes figures/dropfoot_conditions.gif. The headless SCONE
container used here cannot render its own video, hence this.
"""

from __future__ import annotations

import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter

from dropfoot import ROOT
from dropfoot.evaluation import EVAL_CACHE
from dropfoot.io import read_sto

OUT = ROOT / "figures" / "dropfoot_conditions.gif"
FPS = 25
TORSO_LENGTH = 0.55
TOE_LENGTH = 0.05


def chain(sto, side: str, i: int) -> np.ndarray:
    bodies = [f"{b}_{side}" for b in ("femur", "tibia", "talus", "calcn", "toes")]
    p = np.array([[sto[f"{b}.pos_x"][i], sto[f"{b}.pos_y"][i]] for b in bodies])
    heel, mtp = p[3], p[4]
    d = (mtp - heel) / np.linalg.norm(mtp - heel)
    return np.vstack([p, mtp + TOE_LENGTH * d])


def torso(sto, i: int) -> np.ndarray:
    base = np.array([sto["torso.pos_x"][i], sto["torso.pos_y"][i]])
    a = sto["torso.ori_z"][i] if sto.has("torso.ori_z") else 0.0
    return np.vstack([base, base + TORSO_LENGTH * np.array([-np.sin(a), np.cos(a)])])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--start", type=float, default=5.0)
    ap.add_argument("--duration", type=float, default=3.0)
    args = ap.parse_args()
    sel = json.loads((ROOT / "results/device/selection.json").read_text())
    tag = "ta25"
    panels = [
        ("Healthy", EVAL_CACHE / f"healthy_s{args.seed}.par.sto"),
        ("Drop foot, no device", EVAL_CACHE / f"reopt_none_{tag}_s{args.seed}.par.sto"),
        (f"Passive AFO ({sel['passive']['setting']})", EVAL_CACHE / f"reopt_passive_{tag}_{sel['passive']['setting']}_s{args.seed}.par.sto"),
        (f"Active AFO ({sel['active']['setting']})", EVAL_CACHE / f"reopt_active_{tag}_{sel['active']['setting']}_s{args.seed}.par.sto"),
    ]
    stos = [(name, read_sto(p)) for name, p in panels if p.exists()]
    missing = [name for name, p in panels if not p.exists()]
    if missing:
        print("missing evaluations (run analysis/part_f.py compare first):", ", ".join(missing))
    fig, axes = plt.subplots(1, len(stos), figsize=(3.0 * len(stos), 3.4))
    axes = np.atleast_1d(axes)
    frames = np.arange(args.start, args.start + args.duration, 1.0 / FPS)
    artists = []
    for ax, (name, _) in zip(axes, stos):
        ax.set_aspect("equal")
        ax.set_ylim(-0.05, 1.65)
        ax.axis("off")
        ground = ax.axhline(0.0, color="k", lw=1)
        left, = ax.plot([], [], "-o", color="0.6", lw=2.5, ms=2.5)
        right, = ax.plot([], [], "-o", color="tab:red", lw=2.5, ms=2.5)
        trunk, = ax.plot([], [], "-", color="0.3", lw=4)
        hips, = ax.plot([], [], "-", color="0.3", lw=4)
        title = ax.set_title(name, fontsize=8)
        artists.append((ax, left, right, trunk, hips, title, name, ground))

    def draw(t):
        out = []
        for (ax, left, right, trunk, hips, title, name, _), (_, sto) in zip(artists, stos):
            i = min(np.searchsorted(sto.time, t), len(sto.time) - 1)
            x0 = sto["pelvis.pos_x"][i]
            ax.set_xlim(x0 - 0.8, x0 + 0.8)
            for line, side in ((left, "l"), (right, "r")):
                p = chain(sto, side, i)
                line.set_data(p[:, 0], p[:, 1])
            tr = torso(sto, i)
            trunk.set_data(tr[:, 0], tr[:, 1])
            hips.set_data([sto["femur_l.pos_x"][i], tr[0, 0], sto["femur_r.pos_x"][i]],
                          [sto["femur_l.pos_y"][i], tr[0, 1], sto["femur_r.pos_y"][i]])
            tau = sto["dev.torque"][i] if sto.has("dev.torque") else 0.0
            fell = " (fell)" if t > sto.time[-1] else ""
            title.set_text(f"{name}{fell}\nt = {t:.2f} s, device {tau:+.1f} N m")
            out += [left, right, trunk, hips, title]
        return out

    anim = FuncAnimation(fig, draw, frames=frames, blit=False)
    fig.tight_layout()
    anim.save(OUT, writer=PillowWriter(fps=FPS))
    print(f"wrote {OUT.relative_to(ROOT)} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
