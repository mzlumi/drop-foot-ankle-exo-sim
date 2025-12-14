#!/usr/bin/env python3
"""Part F: the device experiment (tuning on frozen controllers, re-optimization, comparison).

    python analysis/part_f.py frozen               # F3: tuning sweeps, frozen drop-foot controllers
    python analysis/part_f.py soft                 # how soft a spring the frozen controllers tolerate
    python analysis/part_f.py reopt                # writes the re-optimization scenarios, prints the runs
    python analysis/part_f.py compare              # F4: table, figure and the hypothesis verdict

The rules come from the hypothesis in README.md, committed before any of this
was run.

``frozen``. Every device setting is worn by the adapted drop-foot model
(results/dropfoot_<level>/seed<i>/best.par) without changing its reflex
controller: no device (the device script runs but applies no torque), the
passive AFO at k = 10, 20, 40, 80 and 160 N m/rad with neutral angle 0, and
the active AFO with swing targets of 0, 5 and 10 degrees (other gains as in
dropfoot.fsm.FSMConfig, the actuator fit of Part E clipped at the Part C
torque limit). For each device the chosen setting is, among the settings
with which all seeds walk 10 s, the one whose toe clearance is closest to the
healthy mean, the lower setting on a tie. If no setting lets every seed walk,
the most seeds walking decides first (reported), and if no seed walks at all,
the longest mean time before the fall. Writes results/device/frozen.csv and
results/device/selection.json.

``soft``. A check outside the tuning: the passive AFO at 0.5 to 5 N m/rad on
the same frozen controllers, to find how small a spring already makes them
fall. Writes results/device/frozen_soft_springs.csv.

``reopt``. Writes the scenarios that the three re-optimizations use: no
device, the chosen passive and the chosen active setting, each started from
the adapted controller of the same seed. The no-device run is the control
for the extra generations: the devices are compared with a no-device gait
that was optimized just as long. Prints the scripts/remote.sh commands.

``compare``. Evaluates healthy, the frozen conditions (from ``frozen``) and
the curated re-optimized ones (results/device/<condition>/seed<i>/best.par,
from analysis/curate_runs.py), writes results/device/comparison.csv,
comparison.md and verdict.md, and figures/device_comparison.png.

Verdict, as committed: on the means over the re-optimized seeds,
(1) active toe clearance >= healthy mean - 10 mm, (2) active push-off power
>= 90% of no device, (3) passive push-off power < 85% of no device. A part
holds or fails; a part that fails by less than the device condition's seed
SD is inconclusive; a fall in any seed of a device fails parts 1 and 2 for
the active AFO. A passive AFO that falls leaves part 3 undecided (reported).
"""

from __future__ import annotations

import argparse
import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dropfoot import ROOT
from dropfoot.evaluation import evaluate_many, is_walking, summarize
from dropfoot.experiment import (
    ActuatorFit,
    active_props,
    condition_name,
    device_metrics,
    judge,
    none_props,
    passive_props,
    select_setting,
    write_condition,
)
from dropfoot.fsm import FSMConfig
from dropfoot.gait import PERCENT, find_strides, normalize_strides
from dropfoot.scenarios import strength_tag

SEEDS = (1, 2, 3)
LEVEL = 0.25
PASSIVE_K = (10.0, 20.0, 40.0, 80.0, 160.0)
ACTIVE_TARGET_DEG = (0.0, 5.0, 10.0)
SOFT_K = (0.5, 1.0, 2.5, 5.0)
REOPT_GENERATIONS = 150
OUT = ROOT / "results" / "device"
FIGURE = ROOT / "figures" / "device_comparison.png"
TOE = "min_toe_clearance_mm"
PUSHOFF = "peak_pushoff_power_w"

TABLE = [
    (TOE, "Min toe clearance, mid swing (mm)"),
    (PUSHOFF, "Peak push-off power, muscles + device (W)"),
    ("peak_ankle_power_w", "Peak ankle muscle power (W)"),
    ("ankle_at_ic_deg", "Ankle at initial contact (deg)"),
    ("foot_slap_index_dps", "Foot slap index (deg/s)"),
    ("peak_hip_flexion_swing_deg", "Peak hip flexion, swing (deg)"),
    ("peak_knee_flexion_swing_deg", "Peak knee flexion, swing (deg)"),
    ("step_length_si_pct", "Step length SI (%)"),
    ("speed_mps", "Speed (m/s)"),
    ("cost_of_transport", "Cost of transport, muscles (J/(kg m))"),
    ("device_positive_work_j", "Device positive work per stride (J)"),
    ("device_negative_work_j", "Device negative work per stride (J)"),
    ("device_peak_power_w", "Device peak power (W)"),
    ("device_peak_torque_nm", "Device peak torque (N m)"),
]
CURVES = {
    "ankle_angle": ("ankle_angle_r", np.degrees(1.0), "Ankle angle (deg), + dorsiflexion"),
    "toe_height": ("toes_r.pos_y", 1000.0, "Toe height (mm)"),
    "knee_flexion": ("knee_angle_r", -np.degrees(1.0), "Knee flexion (deg)"),
    "device_torque": ("dev.torque", 1.0, "Device torque (N m), + dorsiflexing"),
}


def actuator_fit() -> ActuatorFit:
    d = json.loads((ROOT / "results/actuator/actuator_fit.json").read_text())
    return ActuatorFit(d["delay_s"], d["time_constant_s"], d["limit_nm"])


def adapted_par(level: float, seed: int):
    return ROOT / f"results/dropfoot_{strength_tag(level)}/seed{seed}/best.par"


def settings():
    """(device, setting label, numeric value, device properties)."""
    yield "none", "", 0.0, none_props()
    for k in PASSIVE_K:
        yield "passive", f"k{k:g}", k, passive_props(k)
    fit = actuator_fit()
    for deg in ACTIVE_TARGET_DEG:
        yield "active", f"t{deg:g}", deg, active_props(FSMConfig(target_rad=math.radians(deg)), fit)


def scenario(device: str, setting: str, props: dict, level: float):
    name = condition_name(device, level, setting)
    tag = strength_tag(level)
    title = f"Drop foot ({tag}) wearing the {device} AFO {setting} (analysis/part_f.py)."
    return name, write_condition(name, title, props, level, f"results/dropfoot_{tag}/seed1/best.par")


def row_for(sto, report, **keys) -> dict:
    row = summarize(sto, report)
    row.update(keys)
    row["walks"] = is_walking(row)
    if row["walks"]:
        row.update(device_metrics(sto, find_strides(sto, "r", skip_first=2)))
    return row


def healthy_reference() -> pd.DataFrame:
    return pd.read_csv(ROOT / "results/healthy/summary.csv")


def cmd_frozen(level: float, workers: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs, keys = [], []
    for device, setting, value, props in settings():
        name, scen = scenario(device, setting, props, level)
        for s in SEEDS:
            jobs.append((scen, adapted_par(level, s), f"frozen_{name}_s{s}"))
            keys.append({"condition": name, "device": device, "setting": setting, "value": value, "seed": s})
    rows = [row_for(sto, rep, **k) for (sto, rep), k in zip(evaluate_many(jobs, workers), keys)]
    df = pd.DataFrame(rows)
    first = ["condition", "device", "setting", "value", "seed", "walks", "cost", "duration_s", TOE, PUSHOFF]
    df = df[first + [c for c in df.columns if c not in first]]
    df.to_csv(OUT / "frozen.csv", index=False, float_format="%.6g")
    healthy_toe = float(healthy_reference()[TOE].mean())
    sel = {"level": level, "healthy_toe_clearance_mm": healthy_toe,
           "passive": select_setting(df, "passive", healthy_toe), "active": select_setting(df, "active", healthy_toe)}
    (OUT / "selection.json").write_text(json.dumps(sel, indent=2) + "\n")
    print(df[first].to_string(index=False))
    print(json.dumps({k: {kk: v[kk] for kk in ("setting", "all_seeds_walk", "toe_clearance_mm")} for k, v in sel.items() if isinstance(v, dict)}, indent=1))


def cmd_soft(level: float, workers: int) -> None:
    jobs, keys = [], []
    for k in SOFT_K:
        name, scen = scenario("passive", f"k{k:g}", passive_props(k), level)
        for s in SEEDS:
            jobs.append((scen, adapted_par(level, s), f"diag_{name}_s{s}"))
            keys.append({"condition": name, "value": k, "seed": s})
    rows = [row_for(sto, rep, **k) for (sto, rep), k in zip(evaluate_many(jobs, workers), keys)]
    df = pd.DataFrame(rows)[["condition", "value", "seed", "walks", "cost", "duration_s", TOE]]
    df.to_csv(OUT / "frozen_soft_springs.csv", index=False, float_format="%.6g")
    print(df.to_string(index=False))


def reopt_conditions(level: float):
    sel = json.loads((OUT / "selection.json").read_text())
    fit = actuator_fit()
    p, a = sel["passive"], sel["active"]
    yield "none", "", none_props()
    yield "passive", p["setting"], passive_props(p["value"])
    yield "active", a["setting"], active_props(FSMConfig(target_rad=math.radians(a["value"])), fit)


def cmd_reopt(level: float) -> None:
    tag = strength_tag(level)
    for device, setting, props in reopt_conditions(level):
        name, scen = scenario(device, setting, props, level)
        for s in SEEDS:
            init = f"../../results/dropfoot_{tag}/seed{s}/best.par"
            print(
                f"scripts/remote.sh studio run optimize {scen.relative_to(ROOT)} --seed {s} "
                f"--generations {REOPT_GENERATIONS} --threads 2 CmaOptimizer.init_file={init}"
            )


def mean_sd(v: pd.Series) -> str:
    v = v.dropna()
    if not len(v):
        return "n/a"
    return f"{v.mean():.3g} +/- {v.std(ddof=1):.2g}" if len(v) > 1 else f"{v.mean():.3g}"


def verdict(df: pd.DataFrame, healthy_toe: float, active: str, passive: str, none: str) -> tuple[str, dict]:
    def stats(cond):
        d = df[(df.condition == cond) & (df.stage == "reoptimized")]
        w = d[d.walks]
        return d, w

    da, wa = stats(active)
    dp, wp = stats(passive)
    dn, wn = stats(none)
    parts = {}
    base = wn[PUSHOFF].mean()
    if not len(da) or len(wa) < len(da):
        parts[1] = parts[2] = {"result": "fails", "reason": f"active AFO fell in {len(da) - len(wa)} of {len(da)} seeds"}
    else:
        toe, sd = wa[TOE].mean(), wa[TOE].std(ddof=1)
        parts[1] = {"result": judge(toe, healthy_toe - 10.0, sd, True), "value": toe, "threshold": healthy_toe - 10.0, "sd": sd}
        po, sd = wa[PUSHOFF].mean(), wa[PUSHOFF].std(ddof=1)
        parts[2] = {"result": judge(po, 0.9 * base, sd, True), "value": po, "threshold": 0.9 * base, "sd": sd}
    if len(wp) < len(dp) or not len(wp):
        parts[3] = {"result": "undecided", "reason": f"passive AFO fell in {len(dp) - len(wp)} of {len(dp)} seeds"}
    else:
        po, sd = wp[PUSHOFF].mean(), wp[PUSHOFF].std(ddof=1)
        parts[3] = {"result": judge(po, 0.85 * base, sd, False), "value": po, "threshold": 0.85 * base, "sd": sd}
    results = [parts[i]["result"] for i in (1, 2, 3)]
    if all(r == "holds" for r in results):
        overall = "supported"
    elif any(r == "fails" for r in results):
        overall = "rejected"
    else:
        overall = "inconclusive"
    return overall, parts


def cmd_compare(level: float, workers: int) -> None:
    tag = strength_tag(level)
    sel = json.loads((OUT / "selection.json").read_text())
    jobs, keys = [], []
    for s in SEEDS:
        jobs.append((ROOT / "scenarios/healthy.scone", ROOT / f"results/healthy/seed{s}/best.par", f"healthy_s{s}"))
        keys.append({"condition": "healthy", "device": "healthy", "stage": "healthy", "seed": s})
    conds = {}
    for device, setting, props in reopt_conditions(level):
        name, scen = scenario(device, setting, props, level)
        conds[device] = name
        for s in SEEDS:
            jobs.append((scen, adapted_par(level, s), f"frozen_{name}_s{s}"))
            keys.append({"condition": name, "device": device, "stage": "frozen", "seed": s})
            par = OUT / name / f"seed{s}" / "best.par"
            if par.exists():
                jobs.append((scen, par, f"reopt_{name}_s{s}"))
                keys.append({"condition": name, "device": device, "stage": "reoptimized", "seed": s})
    results = evaluate_many(jobs, workers)
    rows, curves = [], {}
    for (sto, rep), k in zip(results, keys):
        row = row_for(sto, rep, **k)
        if k["device"] == "healthy":
            row.update({c: 0.0 for c in ("device_positive_work_j", "device_negative_work_j", "device_peak_power_w", "device_peak_torque_nm")})
            row[PUSHOFF] = row.get("peak_ankle_power_w", np.nan)
        rows.append(row)
        if row["walks"]:
            st = find_strides(sto, "r", skip_first=2)
            key = (k["device"], k["stage"])
            for c, (chan, scale, _) in CURVES.items():
                y = normalize_strides(sto, chan, st, scale=scale).mean(0) if sto.has(chan) else np.zeros(len(PERCENT))
                curves.setdefault(key, {}).setdefault(c, []).append(y)
    df = pd.DataFrame(rows)
    first = ["condition", "device", "stage", "seed", "walks", "cost", "duration_s", TOE, PUSHOFF]
    df = df[first + [c for c in df.columns if c not in first]]
    df.to_csv(OUT / "comparison.csv", index=False, float_format="%.6g")

    healthy_toe = float(healthy_reference()[TOE].mean())
    groups = [("healthy", "healthy")] + [(d, st) for d in ("none", "passive", "active") for st in ("frozen", "reoptimized")]
    names = {"healthy": "Healthy", "none": "No device", "passive": f"Passive AFO ({sel['passive']['setting']})",
             "active": f"Active AFO ({sel['active']['setting']})"}
    head = [f"{names[d]}{'' if st == 'healthy' else ', ' + st}" for d, st in groups]
    lines = [
        f"# Device comparison at {tag} (right tibialis anterior at {100 * level:g}% strength)",
        "",
        "Mean +/- SD over the seeds that walk 10 s; strides after the two start-up strides. Frozen: the adapted "
        "drop-foot controller with the device added. Re-optimized: the controller re-optimized with the device on "
        f"({REOPT_GENERATIONS} generations from the adapted controller; no device got the same). "
        "Generated by `analysis/part_f.py compare`.",
        "",
        "| metric | " + " | ".join(head) + " |",
        "|---|" + "---|" * len(groups),
    ]
    sub = {g: df[(df.device == g[0]) & (df.stage == g[1])] for g in groups}
    lines.append("| seeds walking / run | " + " | ".join(f"{int(sub[g].walks.sum())} / {len(sub[g])}" for g in groups) + " |")
    lines.append("| cost | " + " | ".join(mean_sd(sub[g][sub[g].walks].cost) for g in groups) + " |")
    for key, label in TABLE:
        cells = [mean_sd(sub[g][sub[g].walks][key]) if key in sub[g] else "n/a" for g in groups]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    (OUT / "comparison.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    if all(len(sub[(d, "reoptimized")]) for d in ("none", "passive", "active")):
        overall, parts = verdict(df, healthy_toe, conds["active"], conds["passive"], conds["none"])
        text = [f"# Hypothesis verdict: {overall}", "", f"Healthy toe clearance {healthy_toe:.1f} mm.", ""]
        names3 = {1: "active toe clearance >= healthy - 10 mm", 2: "active push-off >= 90% of no device",
                  3: "passive push-off < 85% of no device"}
        for i in (1, 2, 3):
            p = parts[i]
            detail = p.get("reason") or f"{p['value']:.1f} against {p['threshold']:.1f} (seed SD {p['sd']:.2g})"
            text.append(f"{i}. {names3[i]}: **{p['result']}**, {detail}")
        (OUT / "verdict.md").write_text("\n".join(text) + "\n")
        (OUT / "verdict.json").write_text(json.dumps({"overall": overall, "parts": parts}, indent=2, default=float) + "\n")
        print("\n".join(text))

    colors = {"healthy": "k", "none": "tab:red", "passive": "tab:blue", "active": "tab:green"}
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.5))
    for ax, (c, (_, _, title)) in zip(axes.ravel()[:4], CURVES.items()):
        for (d, st), cv in curves.items():
            stack = np.vstack(cv[c])
            ax.plot(PERCENT, stack.mean(0), color=colors[d], ls="--" if st == "frozen" else "-", lw=1.6 if st != "frozen" else 1.0,
                    label=f"{names[d]}{'' if st == 'healthy' else ', ' + st} (n = {len(stack)})")
        ax.set_title(title, fontsize=9)
        ax.set_xlim(0, 100)
        ax.set_xlabel("Right gait cycle (%)", fontsize=8)
        ax.tick_params(labelsize=8)
    axes[0, 0].legend(fontsize=6)
    for ax, key, label in ((axes[1, 1], TOE, "Min toe clearance (mm)"), (axes[1, 2], PUSHOFF, "Peak push-off power (W)")):
        for i, g in enumerate(groups):
            w = sub[g][sub[g].walks][key].dropna()
            fell = int((~sub[g].walks).sum())
            if len(w):
                ax.bar(i, w.mean(), color=colors[g[0]], alpha=0.35 if g[1] == "frozen" else 0.7)
                ax.plot(np.full(len(w), i), w, "k.", ms=4)
            if fell:
                ax.text(i, 0, f"{fell} fell", rotation=90, fontsize=7, va="bottom", ha="center")
        if key == TOE:
            ax.axhline(healthy_toe - 10.0, color="k", ls=":", lw=0.8)
        ax.set_xticks(range(len(groups)))
        ax.set_xticklabels(["H"] + [f"{d[0].upper()}{st[0]}" for d, st in groups[1:]], fontsize=8)
        ax.set_title(label + "; N/P/A = none/passive/active, f/r = frozen/re-opt.", fontsize=8)
    fig.suptitle(f"Drop foot at {100 * level:g}% tibialis anterior strength: devices, frozen (dashed) and re-optimized controllers", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("frozen", "soft", "reopt", "compare"))
    ap.add_argument("--level", type=float, default=LEVEL)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    {"frozen": lambda: cmd_frozen(args.level, args.workers), "soft": lambda: cmd_soft(args.level, args.workers),
     "reopt": lambda: cmd_reopt(args.level),
     "compare": lambda: cmd_compare(args.level, args.workers)}[args.command]()


if __name__ == "__main__":
    main()
