#!/usr/bin/env python3
"""Part C: torque requirement, (N, k) design sweep and the chosen actuator.

    python analysis/part_c.py [--level 0.25]

C1. The assistive torque is the tibialis anterior moment the weakness removed,
plus 20%: ``1.2 * max(TA_healthy - TA_weak, 0)`` over the gait cycle
(dropfoot.actuator.torque_requirement). TA_healthy is the mean right-stride
``tib_ant_r.ankle_angle_r.moment`` of the three healthy seeds, TA_weak the
same for the three adapted drop-foot seeds at ``--level`` strength. The
curves are first averaged over strides and seeds on the normalized cycle,
then mapped onto the healthy mean stride time.

The joint motion the device has to follow is that of healthy gait, the gait
it is meant to restore. Two versions are swept. With the healthy *model's*
mean ankle angle, no design is feasible for this motor: the model's ankle
plantarflexes about 20 deg in the first 3% of the cycle (Part A), peak joint
acceleration about 2500 rad/s^2, and the reflected motor inertia needed to
follow it pushes the RMS current above the rating for every (N, k). That
transient is a model artifact (the human ankle reaches about 130 rad/s^2), so
the design uses the *normative human* mean ankle angle of results/normative
(Camargo et al. 2021), on the model's stride time. Both sweeps are written.

C3. N from 20 to 150 in steps of 5, k from 50 to 2000 N m/rad on a log grid,
and the rigid case. For each design, dropfoot.actuator.operate gives the motor
trajectory and dropfoot.actuator.check_limits the speed, current (RMS against
the rated current, peak against the drive's 15 A) and voltage limits.

C4. Energy per stride is nearly flat over the stiffness for this profile, so
the chosen design is the most compliant feasible one whose electrical energy
per stride (no regeneration) is within ``ENERGY_TOL`` (2%) of the feasible
minimum, and the lower gear ratio on a tie. A compliant spring makes torque
control easier and the device more tolerant of impacts at no energy cost here. Outputs in results/actuator/ (requirement.csv,
sweep.csv, design.json) and figures/actuator_requirement.png,
figures/actuator_sweep.png, figures/actuator_torque_speed.png.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dropfoot import ROOT
from dropfoot.camargo import read_normative
from dropfoot.actuator import check_limits, load_motor, operate, periodic_resample, speed_torque_envelope, torque_requirement
from dropfoot.evaluation import evaluate_cached, is_walking, summarize
from dropfoot.gait import PERCENT, find_strides, normalize_strides
from dropfoot.scenarios import strength_tag

OUT = ROOT / "results" / "actuator"
FIG = ROOT / "figures"
SEEDS = (1, 2, 3)
RATIOS = np.arange(20, 151, 5)
STIFFNESS = np.geomspace(50, 2000, 25)
SAMPLES = 400  # per stride
ENERGY_TOL = 0.02
NORMATIVE = ROOT / "results" / "normative" / "camargo_treadmill_1.20mps.csv"


def mean_curves(cond: str, scenario, par_of, name_of):
    ta, ankle, durations = [], [], []
    for s in SEEDS:
        par = par_of(s)
        if not par.exists():
            continue
        sto, report = evaluate_cached(scenario, par, name_of(s))
        if not is_walking(summarize(sto, report)):
            print(f"{cond} seed {s} falls, not used")
            continue
        st = find_strides(sto, "r", skip_first=2)
        ta.append(normalize_strides(sto, "tib_ant_r.ankle_angle_r.moment", st).mean(0))
        ankle.append(normalize_strides(sto, "ankle_angle_r", st).mean(0))
        durations.append(np.mean([x.duration for x in st]))
    return np.vstack(ta), np.vstack(ankle), np.array(durations)


def run_sweep(motor, eta, t, tau, theta) -> pd.DataFrame:
    rows = []
    for n in RATIOS:
        for k in list(STIFFNESS) + [np.inf]:
            op = operate(motor, float(n), float(k), t, tau, theta, eta=eta)
            lim = check_limits(op, motor)
            rows.append(
                {
                    "ratio": n,
                    "stiffness": k,
                    "energy_j": op.energy_no_regen,
                    "energy_regen_j": op.energy_regen,
                    "peak_power_w": op.peak_power,
                    "peak_speed": op.peak_speed,
                    "rms_current": op.rms_current,
                    "peak_current": op.peak_current,
                    "peak_voltage": op.peak_voltage,
                    "speed_ok": lim.speed,
                    "current_ok": lim.current,
                    "voltage_ok": lim.voltage,
                    "ok": lim.ok,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=float, default=0.25)
    ap.add_argument("--weak-root", help="folder with seed<i>/best.par (default results/dropfoot_<tag>)")
    args = ap.parse_args()
    tag = strength_tag(args.level)
    OUT.mkdir(parents=True, exist_ok=True)
    motor, extra = load_motor()
    eta = extra["gear_efficiency"]

    ta_h, ankle_h, dur_h = mean_curves(
        "healthy", ROOT / "scenarios/healthy.scone", lambda s: ROOT / f"results/healthy/seed{s}/best.par", lambda s: f"healthy_s{s}"
    )
    ta_w, ankle_w, dur_w = mean_curves(
        f"dropfoot_{tag}",
        ROOT / f"scenarios/dropfoot_{tag}.scone",
        lambda s: ROOT / (args.weak_root or f"results/dropfoot_{tag}") / f"seed{s}/best.par",
        lambda s: f"adapted_{tag}_s{s}" if not args.weak_root else f"tmp_{tag}_s{s}",
    )
    req_pct = torque_requirement(ta_h.mean(0), ta_w.mean(0))
    stride = float(dur_h.mean())
    t = np.arange(SAMPLES) * stride / SAMPLES
    pct = 100 * t / stride
    tau = periodic_resample(PERCENT, req_pct, pct)
    theta = periodic_resample(PERCENT, ankle_h.mean(0), pct)
    ankle_normative = np.radians(read_normative(NORMATIVE)["ankle_angle_mean"].to_numpy())
    pd.DataFrame(
        {
            "percent": PERCENT,
            "ta_moment_healthy_nm": ta_h.mean(0),
            "ta_moment_weak_nm": ta_w.mean(0),
            "requirement_nm": req_pct,
            "ankle_model_rad": ankle_h.mean(0),
            "ankle_normative_rad": ankle_normative,
        }
    ).to_csv(OUT / "requirement.csv", index=False, float_format="%.5g")

    theta_model = theta
    theta = periodic_resample(PERCENT, ankle_normative, pct)
    sweep_model = run_sweep(motor, eta, t, tau, theta_model)
    sweep_model.to_csv(OUT / "sweep_model_trajectory.csv", index=False, float_format="%.5g")
    sweep = run_sweep(motor, eta, t, tau, theta)
    sweep.to_csv(OUT / "sweep.csv", index=False, float_format="%.5g")
    feasible = sweep[sweep.ok]
    near = feasible[feasible.energy_j <= (1 + ENERGY_TOL) * feasible.energy_j.min()]
    best = near.sort_values(["stiffness", "ratio"]).iloc[0]
    rigid_same_n = sweep[(sweep.ratio == best.ratio) & np.isinf(sweep.stiffness)].iloc[0]
    best_rigid = sweep[np.isinf(sweep.stiffness) & sweep.ok]
    best_rigid = best_rigid.loc[best_rigid.energy_j.idxmin()] if len(best_rigid) else None
    design = {
        "level": args.level,
        "stride_time_s": stride,
        "peak_requirement_nm": float(tau.max()),
        "requirement_percent_of_peak": float(PERCENT[np.argmax(req_pct)]),
        "motor": asdict(motor),
        "gear_efficiency": eta,
        "chosen": {k: (float(v) if not isinstance(v, (bool, np.bool_)) else bool(v)) for k, v in best.items()},
        "rigid_same_ratio": {k: (float(v) if not isinstance(v, (bool, np.bool_)) else bool(v)) for k, v in rigid_same_n.items()},
        "best_rigid": None if best_rigid is None else {k: (float(v) if not isinstance(v, (bool, np.bool_)) else bool(v)) for k, v in best_rigid.items()},
        "feasible_designs": int(len(feasible)),
        "feasible_designs_model_trajectory": int(sweep_model.ok.sum()),
        "min_rms_current_model_trajectory": float(sweep_model.rms_current.min()),
        "minimum_energy_j": float(feasible.energy_j.min()),
        "joint_trajectory": "normative (Camargo et al. 2021) mean ankle angle on the model stride time",
        "designs": int(len(sweep)),
        "seeds_healthy": int(len(ta_h)),
        "seeds_weak": int(len(ta_w)),
    }
    (OUT / "design.json").write_text(json.dumps(design, indent=2, default=str) + "\n")
    print(json.dumps({k: design[k] for k in ("peak_requirement_nm", "chosen", "rigid_same_ratio", "feasible_designs")}, indent=1, default=str))

    # C1 figure
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.plot(PERCENT, ta_h.mean(0), "k", label=f"TA moment, healthy (n = {len(ta_h)})")
    ax.plot(PERCENT, ta_w.mean(0), color="tab:orange", label=f"TA moment, drop foot {tag}, adapted (n = {len(ta_w)})")
    ax.fill_between(PERCENT, 0, req_pct, color="tab:blue", alpha=0.3, label="Requirement: 1.2 x deficit")
    ax.set_xlabel("Gait cycle (%)")
    ax.set_ylabel("N m, + dorsiflexing")
    ax.set_xlim(0, 100)
    ax.legend(fontsize=7)
    ax.set_title("Assistive torque requirement (Part C1)", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "actuator_requirement.png", dpi=150)

    # C3 heat map
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ks = list(STIFFNESS) + [STIFFNESS[-1] * 1.6]
    grid = np.full((len(RATIOS), len(ks)), np.nan)
    for i, n in enumerate(RATIOS):
        for j, k in enumerate(list(STIFFNESS) + [np.inf]):
            r = sweep[(sweep.ratio == n) & (sweep.stiffness == k)].iloc[0]
            grid[i, j] = r.energy_j if r.ok else np.nan
    x_edges = np.concatenate([[STIFFNESS[0] / 1.08], np.sqrt(np.array(ks[:-1]) * np.array(ks[1:])), [ks[-1] * 1.15]])
    y_edges = np.concatenate([RATIOS - 2.5, [RATIOS[-1] + 2.5]])
    pcm = ax.pcolormesh(x_edges, y_edges, grid, cmap="viridis", shading="flat")
    ax.set_facecolor("0.85")
    ax.set_xscale("log")
    ax.set_xlabel("Series stiffness k (N m/rad); rightmost column: rigid")
    ax.set_ylabel("Gear ratio N")
    fig.colorbar(pcm, label="Electrical energy per stride, no regeneration (J)")
    kb = best.stiffness if np.isfinite(best.stiffness) else ks[-1]
    ax.plot(kb, best.ratio, "r*", ms=14, label=f"Chosen: N = {best.ratio:.0f}, k = {best.stiffness:.0f}, {best.energy_j:.2f} J")
    ax.legend(fontsize=7, loc="upper left")
    ax.set_title("Design sweep (grey: speed, current or voltage limit violated)", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "actuator_sweep.png", dpi=150)

    # C4 torque-speed
    op = operate(motor, float(best.ratio), float(best.stiffness), t, tau, theta, eta=eta)
    rig = operate(motor, float(best.ratio), np.inf, t, tau, theta, eta=eta)
    tq, sp = speed_torque_envelope(motor)
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for sx, sy in ((1, 1), (-1, -1)):
        ax.plot(sx * sp, sy * tq, color="k", lw=1)
    ax.plot([-motor.max_speed, motor.max_speed], [motor.rated_current * motor.kt] * 2, "k--", lw=0.8, label="Rated (continuous) torque")
    ax.plot([-motor.max_speed, motor.max_speed], [-motor.rated_current * motor.kt] * 2, "k--", lw=0.8)
    ax.plot([-motor.max_speed, motor.max_speed], [motor.peak_current * motor.kt] * 2, "k:", lw=0.8, label="Drive peak current")
    ax.plot([-motor.max_speed, motor.max_speed], [-motor.peak_current * motor.kt] * 2, "k:", lw=0.8)
    ax.plot(rig.omega_m, rig.tau_m, color="0.6", lw=1, label=f"Rigid, N = {best.ratio:.0f}")
    ax.plot(op.omega_m, op.tau_m, color="tab:blue", lw=1.5, label=f"Chosen SEA, k = {best.stiffness:.0f} N m/rad")
    ax.set_xlabel("Motor speed (rad/s)")
    ax.set_ylabel("Motor torque (N m)")
    ax.set_xlim(-1.1 * motor.max_speed, 1.1 * motor.max_speed)
    ax.set_ylim(-1.3 * motor.peak_current * motor.kt, 1.3 * motor.peak_current * motor.kt)
    ax.axhline(0, color="0.8", lw=0.5)
    ax.axvline(0, color="0.8", lw=0.5)
    ax.legend(fontsize=7, loc="lower right")
    ax.set_title(f"{motor.name}: operating points over one stride, 24 V envelope", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "actuator_torque_speed.png", dpi=150)


if __name__ == "__main__":
    main()
