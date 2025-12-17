#!/usr/bin/env python3
"""Part F5: robustness of the re-optimized device conditions (speed, IMU noise and delay, pushes).

    python analysis/part_f5.py speed-runs      # writes the 1.5 m/s scenarios, prints the runs
    python analysis/part_f5.py evaluate        # every test below; results/robustness/, figures/robustness.png

All tests start from the re-optimized controllers of Part F
(results/device/<condition>/seed<i>/best.par) and the healthy ones, so they
ask how the adapted wearer copes with something the optimization did not see.

* **Speed.** The gait measure only changes the cost, not the dynamics of a
  given controller, so a second speed needs a new optimization: every
  condition (healthy, no device, the chosen passive and active AFO) is
  re-optimized with MeasureGait15 (at least 1.5 m/s minus the 5% threshold)
  from its 1.2 m/s result. The initial state stays the 1.2 m/s one: with
  the tutorial's 1.5 m/s initial state the 1.2 m/s controllers fall within
  1.3 s, so the optimization would start from falls instead of from a gait
  that walks and only has to speed up.
  Curated results go to results/robustness/speed15/<condition>/seed<i>/.
* **IMU noise and delay.** The active AFO with the gyroscope noise doubled
  (0.5 to 1.0 deg/s RMS), the delay doubled (15 to 30 ms), and both. The
  passive AFO and no device do not use the IMU.
* **Delay curves.** The active AFO with IMU delays from 0 to 100 ms, and
  separately with actuator delays from 0 to 100 ms (the fitted time
  constant unchanged).
* **Pushes.** One horizontal push on the pelvis as in Tutorial 4c
  (0.2 s, at the tutorial's point of application), backwards or forwards,
  at 4.5 s, of 25 to 150 N, for no device and both AFOs, and for the healthy
  model as the reference (with a 0 N run that checks the scenario reproduces
  the healthy gait). Scores: seeds walking 10 s, the largest push survived
  by every seed, and the time from the push to the fall (5.5 s for a seed
  that walks to the end), which still separates conditions when every one
  falls. The push lands at a different gait phase in each condition and
  seed; that is part of the spread, not corrected for.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dropfoot import ROOT
from dropfoot.evaluation import evaluate_many, is_walking, summarize
from dropfoot.experiment import ActuatorFit, active_props, condition_name, device_metrics, none_props, passive_props
from dropfoot.fsm import FSMConfig
from dropfoot.gait import find_strides
from dropfoot.scenarios import device_scenario, strength_tag, write_generated
from dropfoot.sensor import GyroConfig

SEEDS = (1, 2, 3)
LEVEL = 0.25
OUT = ROOT / "results" / "robustness"
FIGURE = ROOT / "figures" / "robustness.png"
DEVICE_OUT = ROOT / "results" / "device"
SPEED_GENERATIONS = 150
DELAYS_MS = (0, 15, 30, 45, 60, 80, 100)
PUSH_N = (25, 50, 75, 100, 150)
PUSH_TIME = 4.5
MAX_AFTER_PUSH = 10.0 - PUSH_TIME
TOE = "min_toe_clearance_mm"
PUSHOFF = "peak_pushoff_power_w"
COLORS = {"healthy": "k", "none": "tab:red", "passive": "tab:blue", "active": "tab:green"}


def push_block(force: float) -> str:
    return (
        "\t\t\tPerturbationController {\n"
        "\t\t\t\tname = Push\n"
        f"\t\t\t\tstart_time = {PUSH_TIME:g}\n"
        "\t\t\t\tduration = 0.2\n"
        f"\t\t\t\tforce = [ {force:g} 0 0 ]\n"
        "\t\t\t\tbody = pelvis\n"
        "\t\t\t\tposition_offset = [ -0.15 0.35 0 ]\n"
        "\t\t\t}\n"
    )


def actuator_fit() -> ActuatorFit:
    d = json.loads((ROOT / "results/actuator/actuator_fit.json").read_text())
    return ActuatorFit(d["delay_s"], d["time_constant_s"], d["limit_nm"])


def chosen(level: float) -> dict:
    """device -> (condition name, props builder taking a GyroConfig)."""
    sel = json.loads((DEVICE_OUT / "selection.json").read_text())
    fit = actuator_fit()
    p, a = sel["passive"], sel["active"]
    fsm = FSMConfig(target_rad=math.radians(a["value"]))
    return {
        "none": (condition_name("none", level), lambda g=GyroConfig(): none_props(g)),
        "passive": (condition_name("passive", level, p["setting"]), lambda g=GyroConfig(): passive_props(p["value"], gyro=g)),
        "active": (condition_name("active", level, a["setting"]), lambda g=GyroConfig(): active_props(fsm, fit, g)),
    }


def reopt_par(name: str, seed: int):
    return DEVICE_OUT / name / f"seed{seed}" / "best.par"


def scenario(name: str, title: str, props: dict, level: float, extra: str = "", measure: str = "MeasureGait12",
             init_state: str = "InitStateGait10.sto", factor: float | None = None, init: str | None = None):
    factor = level if factor is None else factor
    init = init or f"../../results/device/{name.split('__')[0]}/seed1/best.par"
    return write_generated(name, device_scenario(title, name, props, factor=factor, init_file=init, measure=measure,
                                                 init_state=init_state, extra=extra))


def speed_conditions(level: float):
    """(device, scenario name, scenario path, init .par for seed s relative to scenarios/generated)."""
    tag = strength_tag(level)
    yield ("healthy", "healthy_speed15",
           scenario("healthy_speed15", "Healthy at 1.5 m/s with the device script, no torque (analysis/part_f5.py).",
                    none_props(), level, measure="MeasureGait15", factor=1.0,
                    init="../../results/healthy/seed1/best.par"),
           lambda s: f"../../results/healthy/seed{s}/best.par")
    for device, (name, props) in chosen(level).items():
        sname = f"{name}_speed15"
        yield (device, sname,
               scenario(sname, f"Drop foot ({tag}), {device} AFO, at 1.5 m/s (analysis/part_f5.py).", props(), level,
                        measure="MeasureGait15", init=f"../../results/device/{name}/seed1/best.par"),
               lambda s, n=name: f"../../results/device/{n}/seed{s}/best.par")


def cmd_speed_runs(level: float) -> None:
    for _, _, scen, init in speed_conditions(level):
        for s in SEEDS:
            print(f"scripts/remote.sh studio run optimize {scen.relative_to(ROOT)} --seed {s} "
                  f"--generations {SPEED_GENERATIONS} --threads 2 CmaOptimizer.init_file={init(s)}")


def row_for(sto, report, **keys) -> dict:
    row = summarize(sto, report)
    row.update(keys)
    row["walks"] = is_walking(row)
    if row["walks"]:
        row.update(device_metrics(sto, find_strides(sto, "r", skip_first=2)))
    return row


def cmd_evaluate(level: float, workers: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    conds = chosen(level)
    jobs, keys = [], []
    tag = strength_tag(level)

    def add(scen, par, cache, **k):
        if par.exists():
            jobs.append((scen, par, cache))
            keys.append(k)

    # IMU noise, delay, and the delay curve: active AFO only
    name, props = conds["active"]
    base = GyroConfig()
    variants = {"nominal": base, "noise x2": replace(base, noise_dps=2 * base.noise_dps),
                "delay x2": replace(base, delay_s=2 * base.delay_s),
                "noise and delay x2": replace(base, noise_dps=2 * base.noise_dps, delay_s=2 * base.delay_s)}
    for label, g in variants.items():
        key = label.replace(" ", "_")
        scen = scenario(f"{name}__imu_{key}", f"Drop foot ({tag}), active AFO, IMU {label} (analysis/part_f5.py).", props(g), level)
        for s in SEEDS:
            add(scen, reopt_par(name, s), f"rob_{name}_imu_{key}_s{s}", test="imu", variant=label, device="active", seed=s)
    for d in DELAYS_MS:
        g = replace(base, delay_s=d / 1000)
        scen = scenario(f"{name}__delay{d}", f"Drop foot ({tag}), active AFO, IMU delay {d} ms (analysis/part_f5.py).", props(g), level)
        for s in SEEDS:
            add(scen, reopt_par(name, s), f"rob_{name}_delay{d}_s{s}", test="delay", delay_ms=d, device="active", seed=s)
    fit = actuator_fit()
    sel = json.loads((DEVICE_OUT / "selection.json").read_text())
    fsm = FSMConfig(target_rad=math.radians(sel["active"]["value"]))
    for d in DELAYS_MS:
        scen = scenario(f"{name}__actdelay{d}", f"Drop foot ({tag}), active AFO, actuator delay {d} ms (analysis/part_f5.py).",
                        active_props(fsm, replace(fit, delay_s=d / 1000)), level)
        for s in SEEDS:
            add(scen, reopt_par(name, s), f"rob_{name}_actdelay{d}_s{s}", test="actuator delay", delay_ms=d, device="active", seed=s)
    # pushes, with the healthy model as the reference (its 0 N run checks that the scenario reproduces it)
    healthy_push = scenario("healthy__push_none", "Healthy, no push (analysis/part_f5.py).", none_props(), level, factor=1.0,
                            init="../../results/healthy/seed1/best.par")
    for s in SEEDS:
        add(healthy_push, ROOT / f"results/healthy/seed{s}/best.par", f"rob_healthy_push_none_s{s}", test="push", device="healthy",
            direction="none", force_n=0, seed=s)
    for f in PUSH_N:
        for sign, direction in ((-1, "backward"), (1, "forward")):
            scen = scenario(f"healthy__push_{direction}{f}", f"Healthy, {f} N {direction} push (analysis/part_f5.py).", none_props(),
                            level, extra=push_block(sign * f), factor=1.0, init="../../results/healthy/seed1/best.par")
            for s in SEEDS:
                add(scen, ROOT / f"results/healthy/seed{s}/best.par", f"rob_healthy_push_{direction}{f}_s{s}", test="push",
                    device="healthy", direction=direction, force_n=f, seed=s)
    for device, (name, props) in conds.items():
        for f in PUSH_N:
            for sign, direction in ((-1, "backward"), (1, "forward")):
                scen = scenario(f"{name}__push_{direction}{f}", f"Drop foot ({tag}), {device}, {f} N {direction} push (analysis/part_f5.py).",
                                props(), level, extra=push_block(sign * f))
                for s in SEEDS:
                    add(scen, reopt_par(name, s), f"rob_{name}_push_{direction}{f}_s{s}", test="push", device=device,
                        direction=direction, force_n=f, seed=s)
    # second speed
    for device, sname, scen, _ in speed_conditions(level):
        for s in SEEDS:
            add(scen, OUT / "speed15" / sname / f"seed{s}" / "best.par", f"rob_{sname}_s{s}", test="speed15", device=device, seed=s)
    rows = [row_for(sto, rep, **k) for (sto, rep), k in zip(evaluate_many(jobs, workers), keys)]
    df = pd.DataFrame(rows)
    df["after_push_s"] = np.where(df.test == "push", np.minimum(df.duration_s - PUSH_TIME, MAX_AFTER_PUSH), np.nan)
    first = ["test", "device", "variant", "delay_ms", "direction", "force_n", "seed", "walks", "duration_s", TOE, PUSHOFF, "speed_mps"]
    df = df[[c for c in first if c in df] + [c for c in df.columns if c not in first]]
    df.to_csv(OUT / "robustness.csv", index=False, float_format="%.6g")
    summarize_tables(df)
    plot(df)


def ms(v: pd.Series) -> str:
    v = v.dropna()
    return "n/a" if not len(v) else (f"{v.mean():.3g} +/- {v.std(ddof=1):.2g}" if len(v) > 1 else f"{v.mean():.3g}")


def summarize_tables(df: pd.DataFrame) -> None:
    lines = ["# Robustness (Part F5)", "", "Re-optimized controllers; mean +/- SD over the seeds that walk 10 s. "
             "Generated by `analysis/part_f5.py evaluate`.", ""]
    imu = df[df.test == "imu"]
    if len(imu):
        lines += ["## Active AFO, IMU noise and delay", "", "| IMU | walking | toe clearance (mm) | push-off (W) | device +work (J) |", "|---|---|---|---|---|"]
        for v, g in imu.groupby("variant", sort=False):
            w = g[g.walks]
            lines.append(f"| {v} | {len(w)} / {len(g)} | {ms(w[TOE])} | {ms(w[PUSHOFF])} | {ms(w.get('device_positive_work_j', pd.Series(dtype=float)))} |")
        lines.append("")
    for test, title in (("delay", "IMU delay"), ("actuator delay", "actuator delay")):
        dl = df[df.test == test]
        if len(dl):
            lines += [f"## Active AFO, {title} curve", "", "| delay (ms) | walking | toe clearance (mm) | push-off (W) |", "|---|---|---|---|"]
            for d, g in dl.groupby("delay_ms"):
                w = g[g.walks]
                lines.append(f"| {d:g} | {len(w)} / {len(g)} | {ms(w[TOE])} | {ms(w[PUSHOFF])} |")
            lines.append("")
    pu = df[df.test == "push"]
    if len(pu):
        base = pu[pu.direction == "none"]
        if len(base):
            lines += [f"Healthy reference without a push in the same scenario: {int(base.walks.sum())} / {len(base)} walk, "
                      f"cost {ms(base.cost)}.", ""]
        pu = pu[pu.direction != "none"]
        lines += ["## Pushes on the pelvis at 4.5 s (0.2 s)", "",
                  "Seeds walking 10 s per force, and the time from the start of the push to the fall, mean over seeds "
                  f"(a seed that walks to the end counts {MAX_AFTER_PUSH:g} s).", "",
                  "| device | direction | largest survived by all seeds (N) | " + " | ".join(f"{f} N" for f in PUSH_N) + " |",
                  "|---|---|---|" + "---|" * len(PUSH_N)]
        for (dev, direction), g in pu.groupby(["device", "direction"], sort=False):
            per = g.groupby("force_n").walks.agg(["sum", "size"])
            ok = [f for f in PUSH_N if f in per.index and per.loc[f, "sum"] == per.loc[f, "size"]]
            largest = 0
            for f in PUSH_N:
                if f in ok:
                    largest = f
                else:
                    break
            after = g.groupby("force_n").after_push_s.mean()
            cells = [f"{int(per.loc[f, 'sum'])} / {int(per.loc[f, 'size'])}, {after.loc[f]:.1f} s" if f in per.index else "n/a"
                     for f in PUSH_N]
            lines.append(f"| {dev} | {direction} | {largest} | " + " | ".join(cells) + " |")
        lines.append("")
    sp = df[df.test == "speed15"]
    if len(sp):
        lines += ["## Second speed (MeasureGait15)", "", "| condition | walking | speed (m/s) | toe clearance (mm) | push-off (W) | cost of transport |",
                  "|---|---|---|---|---|---|"]
        for dev, g in sp.groupby("device", sort=False):
            w = g[g.walks]
            lines.append(f"| {dev} | {len(w)} / {len(g)} | {ms(w.speed_mps)} | {ms(w[TOE])} | {ms(w[PUSHOFF])} | {ms(w.cost_of_transport)} |")
        lines.append("")
    (OUT / "robustness.md").write_text("\n".join(lines))
    print("\n".join(lines))


def plot(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    ax = axes[0]
    for test, marker, color in (("delay", "o", "tab:green"), ("actuator delay", "s", "tab:olive")):
        dl = df[df.test == test]
        if not len(dl):
            continue
        walk = dl.groupby("delay_ms").walks.agg(["sum", "size"])
        toe = dl[dl.walks].groupby("delay_ms")[TOE]
        ax.errorbar(toe.mean().index, toe.mean(), yerr=toe.std(ddof=1).fillna(0), color=color, marker=marker, capsize=3,
                    label=("IMU" if test == "delay" else "actuator") + " delay")
        for d, r in walk.iterrows():
            if r["sum"] < r["size"]:
                ax.annotate(f"{int(r['sum'])}/{int(r['size'])}", (d, toe.mean().get(d, np.nan)), fontsize=7, color=color,
                            textcoords="offset points", xytext=(0, 6), ha="center")
    ax.set_xlabel("Delay (ms)")
    ax.set_ylabel("Min toe clearance (mm)")
    ax.set_title("Active AFO: delay (labels: seeds walking, if not all)", fontsize=9)
    ax.legend(fontsize=7)
    ax = axes[1]
    pu = df[(df.test == "push") & (df.direction != "none")]
    for i, (dev, g) in enumerate(pu.groupby("device", sort=False)):
        for j, direction in enumerate(("backward", "forward")):
            r = g[g.direction == direction].groupby("force_n").after_push_s.mean()
            x = r.index * (-1 if direction == "backward" else 1) + 3.0 * (i - 1.5)
            ax.plot(x, r.values, "o-" if j else "s-", color=COLORS[dev], label=dev if j == 0 else None, alpha=0.85, ms=4)
    ax.axhline(MAX_AFTER_PUSH, color="0.6", lw=0.8, ls=":")
    ax.set_xlabel("Push force (N), - backward, + forward")
    ax.set_ylabel(f"Time from push to fall (s), mean over seeds; {MAX_AFTER_PUSH:g} = no fall", fontsize=7)
    ax.set_title("Single 0.2 s push on the pelvis at 4.5 s", fontsize=9)
    ax.legend(fontsize=7)
    ax = axes[2]
    sp = df[df.test == "speed15"]
    for i, (dev, g) in enumerate(sp.groupby("device", sort=False)):
        w = g[g.walks]
        if len(w):
            ax.bar(i, w[TOE].mean(), color=COLORS[dev], alpha=0.7)
            ax.plot(np.full(len(w), i), w[TOE], "k.")
        if (~g.walks).any():
            ax.text(i, 1, f"{int((~g.walks).sum())} fell", rotation=90, fontsize=7, ha="center", va="bottom")
    ax.set_xticks(range(sp.device.nunique()) if len(sp) else [])
    ax.set_xticklabels(list(dict.fromkeys(sp.device)) if len(sp) else [], fontsize=8)
    ax.set_ylabel("Min toe clearance (mm)")
    ax.set_title("Re-optimized at 1.5 m/s", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("speed-runs", "evaluate"))
    ap.add_argument("--level", type=float, default=LEVEL)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    if args.command == "speed-runs":
        cmd_speed_runs(args.level)
    else:
        cmd_evaluate(args.level, args.workers)


if __name__ == "__main__":
    main()
