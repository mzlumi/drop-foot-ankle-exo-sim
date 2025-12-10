#!/usr/bin/env python3
"""Part A: the healthy model against normative treadmill walking at 1.2 m/s.

    python analysis/part_a.py

Evaluates results/healthy/seed{1,2,3}/best.par in scenarios/healthy.scone and
writes, in results/healthy/: summary.csv (gait metrics per seed),
model_curves.csv (mean and SD across seeds of each seed's mean stride),
vs_normative.csv and vs_normative.md (RMSE, r, offset and RMSE without the
offset, per seed and for the mean across seeds), and the figure
figures/healthy_vs_normative.png. The normative curves are those of
results/normative (Camargo et al. 2021, see that file's header).
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dropfoot import ROOT
from dropfoot.camargo import CITATION, read_normative
from dropfoot.compare import UNITS, agreement, mean_curves, model_curves
from dropfoot.evaluation import evaluate_cached, summarize
from dropfoot.gait import PERCENT, find_strides

SEEDS = (1, 2, 3)
OUT = ROOT / "results" / "healthy"
NORMATIVE = ROOT / "results" / "normative" / "camargo_treadmill_1.20mps.csv"
FIGURE = ROOT / "figures" / "healthy_vs_normative.png"
TITLES = {
    "hip_flexion": "Hip flexion (deg)",
    "knee_flexion": "Knee flexion (deg)",
    "ankle_angle": "Ankle angle (deg), + dorsiflexion",
    "ankle_moment": "Ankle moment (N m/kg), + dorsiflexing",
    "vertical_grf": "Vertical GRF (BW)",
    "shank_gyro": "Shank angular velocity (deg/s)",
}


def main() -> None:
    norm = read_normative(NORMATIVE)
    norm_meta = json.loads(NORMATIVE.with_suffix(".json").read_text())
    per_seed, rows, stance = {}, [], {}
    for seed in SEEDS:
        sto, report = evaluate_cached(ROOT / "scenarios/healthy.scone", OUT / f"seed{seed}/best.par", f"healthy_s{seed}")
        row = summarize(sto, report)
        rows.append({"seed": seed, **row})
        strides = find_strides(sto, "r", skip_first=2)
        per_seed[seed] = mean_curves(model_curves(sto, strides))
        stance[seed] = 100 * np.mean([s.stance_fraction for s in strides])
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "summary.csv", index=False, float_format="%.6g")

    variables = list(TITLES)
    stack = {v: np.vstack([per_seed[s][v].to_numpy() for s in SEEDS]) for v in variables}
    curves = pd.DataFrame({"percent": PERCENT})
    for v in variables:
        curves[f"{v}_mean"] = stack[v].mean(axis=0)
        curves[f"{v}_sd"] = stack[v].std(axis=0, ddof=1)
    curves.to_csv(OUT / "model_curves.csv", index=False, float_format="%.6g")

    table = []
    for v in variables:
        ref = norm[f"{v}_mean"].to_numpy()
        seeds = [agreement(stack[v][i], ref) for i in range(len(SEEDS))]
        mean = agreement(stack[v].mean(axis=0), ref)
        row = {"variable": v, "unit": UNITS[v]}
        for k in ("rmse", "r", "offset", "rmse_no_offset"):
            row[k] = mean[k]
            row[f"{k}_seed_min"] = min(s[k] for s in seeds)
            row[f"{k}_seed_max"] = max(s[k] for s in seeds)
        row["normative_sd_mean"] = float(norm[f"{v}_sd"].mean())
        table.append(row)
    table = pd.DataFrame(table)
    table.to_csv(OUT / "vs_normative.csv", index=False, float_format="%.4g")

    lines = [
        "# Healthy model versus normative walking at 1.2 m/s",
        "",
        f"Model: mean of the mean right strides of seeds {', '.join(map(str, SEEDS))} "
        f"({int(summary.n_strides.sum())} strides). Normative: {norm_meta['subjects']} subjects, "
        f"{norm_meta['strides_total']} strides, Camargo et al. (2021). RMSE and r compare the two mean "
        "curves over 0 to 100% of the gait cycle; ranges in brackets are over seeds. The offset is the "
        "model minus normative mean; the last column is the RMSE after removing it. The normative SD is "
        "the between-subject SD averaged over the cycle, for scale.",
        "",
        "| variable | unit | RMSE | RMSE without offset | offset | r | normative SD |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in table.itertuples():
        lines.append(
            f"| {r.variable} | {r.unit} | {r.rmse:.3g} [{r.rmse_seed_min:.3g}, {r.rmse_seed_max:.3g}] "
            f"| {r.rmse_no_offset:.3g} | {r.offset:+.3g} | {r.r:.2f} [{r.r_seed_min:.2f}, {r.r_seed_max:.2f}] "
            f"| {r.normative_sd_mean:.3g} |"
        )
    st = np.array(list(stance.values()))
    lines += [
        "",
        f"Stance: model {st.mean():.1f}% (seeds {st.min():.1f} to {st.max():.1f}%), normative "
        f"{norm_meta['stance_pct_mean']:.1f} +/- {norm_meta['stance_pct_sd']:.1f}%.",
        f"Speed: {summary.speed_mps.mean():.3f} m/s (seeds {summary.speed_mps.min():.3f} to "
        f"{summary.speed_mps.max():.3f}). Cost of transport: {summary.cost_of_transport.mean():.3f} J/(kg m).",
        "",
        f"Source of the normative data: {CITATION}",
    ]
    (OUT / "vs_normative.md").write_text("\n".join(lines) + "\n")

    fig, axes = plt.subplots(3, 2, figsize=(9, 8.5), sharex=True)
    for ax, v in zip(axes.T.ravel(), variables):
        m, sd = norm[f"{v}_mean"], norm[f"{v}_sd"]
        ax.fill_between(PERCENT, m - sd, m + sd, color="0.85", lw=0, label="Normative mean +/- SD")
        ax.plot(PERCENT, m, color="0.4", lw=1.5)
        for i, s in enumerate(SEEDS):
            ax.plot(PERCENT, stack[v][i], color="tab:blue", lw=0.7, alpha=0.6, label="Model seeds" if i == 0 else None)
        ax.plot(PERCENT, stack[v].mean(axis=0), color="tab:blue", lw=2, label="Model mean")
        ax.axvline(norm_meta["stance_pct_mean"], color="0.4", ls="--", lw=0.8)
        ax.axvline(st.mean(), color="tab:blue", ls="--", lw=0.8)
        ax.axhline(0, color="0.7", lw=0.5)
        a = table.set_index("variable").loc[v]
        ax.set_title(f"{TITLES[v]}\nRMSE {a.rmse:.3g}, r {a.r:.2f}", fontsize=9)
        ax.tick_params(labelsize=8)
    for ax in axes[-1]:
        ax.set_xlabel("Gait cycle (%), right heel strike to heel strike")
        ax.set_xlim(0, 100)
    axes[0, 0].legend(fontsize=7, loc="upper right")
    fig.suptitle(
        "Healthy model (3 seeds) versus Camargo et al. (2021), 1.2 m/s; dashed lines are toe-off", fontsize=10
    )
    fig.tight_layout()
    FIGURE.parent.mkdir(exist_ok=True)
    fig.savefig(FIGURE, dpi=150)
    print((OUT / "vs_normative.md").read_text())
    print(summary.to_string())


if __name__ == "__main__":
    main()
