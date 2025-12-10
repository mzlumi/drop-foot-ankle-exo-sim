#!/usr/bin/env python3
"""Part D3: validate the gait-event detector over long simulated walks.

    python analysis/part_d_validation.py                 # healthy seeds only
    python analysis/part_d_validation.py --dropfoot 0.25 # plus the adapted drop-foot gait

Each condition is a 60 s evaluation with the simulated shank gyroscope
(100 Hz, 0.5 deg/s noise, 2 deg/s bias, 15 ms delay): the healthy results in
scenarios/healthy_imu.scone, and the adapted drop-foot results
(results/dropfoot_ta<x>/seed<i>/best.par) wearing the device in mode "none",
which logs the same gyroscope and detector without applying torque.

Both heel-strike features of the detector (``min`` and ``zero``) are run on the
same measured samples by the Python twin; the twin is checked against the
events the Lua detector logged during the simulation. Scores are those of
dropfoot.validation over 2 s to the end minus 0.5 s. The feature for the
controller is chosen on these simulated data only, by this rule fixed before
the results were seen: no missed or false events, then the lower mean
absolute HS timing error pooled over all conditions.

Writes results/detector/validation.csv (per run and feature),
results/detector/pooled.csv (per condition and feature, events of all seeds
pooled) and figures/detector_trace.png (annotated trace).
"""

from __future__ import annotations

import argparse
from dataclasses import replace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dropfoot import ROOT
from dropfoot.detector import DetectorConfig
from dropfoot.evaluation import evaluate_cached
from dropfoot.scenarios import device_scenario, strength_tag, write_generated
from dropfoot.sensor import GyroConfig
from dropfoot.validation import Score, gyro_samples, phase_error, run_detector, score, true_events

SEEDS = (1, 2, 3)
DURATION = 60.0
T0, T_END_MARGIN = 2.0, 0.5
GYRO = GyroConfig()
FEATURES = ("min", "zero")
OUT = ROOT / "results" / "detector"
FIGURE = ROOT / "figures" / "detector_trace.png"
IMU_PROPS = {  # property names read by scenarios/lua/device.lua
    "rate_hz": GYRO.rate_hz,
    "noise_dps": GYRO.noise_dps,
    "bias_dps": GYRO.bias_dps,
    "imu_delay_s": GYRO.delay_s,
    "seed": GYRO.seed,
}


def conditions(dropfoot: list[float]):
    for s in SEEDS:
        yield "healthy", s, ROOT / "scenarios/healthy_imu.scone", ROOT / f"results/healthy/seed{s}/best.par"
    for f in dropfoot:
        tag = strength_tag(f)
        scen = write_generated(
            f"dropfoot_{tag}_imu",
            device_scenario(
                f"Adapted drop foot ({tag}) with the shank gyroscope and detector, no device torque (Part D3).",
                f"{tag}_imu",
                {"mode": "none", **IMU_PROPS},
                factor=f,
                init_file=f"../../results/dropfoot_{tag}/seed1/best.par",
            ),
        )
        for s in SEEDS:
            par = ROOT / f"results/dropfoot_{tag}/seed{s}/best.par"
            if par.exists():
                yield f"dropfoot_{tag}", s, scen, par


def lua_consistency(sto, twin_hs: np.ndarray) -> float:
    logged = np.unique(sto["det.hs_time"])
    logged = logged[logged >= 0]
    n = min(len(logged), len(twin_hs))
    return float(np.max(np.abs(logged[:n] - twin_hs[:n]))) if n else np.nan if len(logged) == len(twin_hs) else np.inf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dropfoot", type=float, nargs="*", default=[])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows, pooled, traces = [], {}, {}
    for cond, seed, scen, par in conditions(args.dropfoot):
        sto, _ = evaluate_cached(scen, par, f"{cond}_imu60_s{seed}", {"CmaOptimizer.SimulationObjective.max_duration": DURATION})
        t1 = float(sto.time[-1]) - T_END_MARGIN
        hs_true, to_true = true_events(sto)
        t, y = gyro_samples(sto, GYRO.rate_hz, GYRO.delay_s)
        for feat in FEATURES:
            run = run_detector(t, y, replace(DetectorConfig(), hs_feature=feat))
            hs = score(hs_true, run.hs_time, run.hs_detect, T0, t1)
            to = score(to_true, run.to_time, run.to_detect, T0, t1)
            ph = 100 * phase_error(run, hs_true, T0, t1)
            row = {"condition": cond, "seed": seed, "feature": feat, "duration_s": float(sto.time[-1])}
            row.update(hs.summary("hs"))
            row.update(to.summary("to"))
            row.update({"phase_error_mean_pct": float(ph.mean()), "phase_error_rms_pct": float(np.sqrt(np.mean(ph**2)))})
            if feat == "min":
                row["lua_twin_max_diff_s"] = lua_consistency(sto, run.hs_time)
            rows.append(row)
            p = pooled.setdefault((cond, feat), {"hs": [], "to": [], "phase": []})
            p["hs"].append(hs)
            p["to"].append(to)
            p["phase"].append(ph)
            if cond == "healthy" and seed == 1 or cond.startswith("dropfoot") and seed == 1:
                traces[(cond, feat)] = (sto, t, y, run, hs_true, to_true)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "validation.csv", index=False, float_format="%.4g")

    prow = []
    for (cond, feat), p in pooled.items():
        r = {"condition": cond, "feature": feat, "seeds": len(p["hs"])}
        for key in ("hs", "to"):
            sc = Score(
                np.concatenate([s.errors for s in p[key]]),
                np.concatenate([s.latency for s in p[key]]),
                sum(s.n_true for s in p[key]),
                sum(s.missed for s in p[key]),
                sum(s.false for s in p[key]),
            )
            r.update(sc.summary(key))
        ph = np.concatenate(p["phase"])
        r.update({"phase_error_mean_pct": float(ph.mean()), "phase_error_rms_pct": float(np.sqrt(np.mean(ph**2)))})
        prow.append(r)
    pdf = pd.DataFrame(prow)
    pdf.to_csv(OUT / "pooled.csv", index=False, float_format="%.4g")

    clean = pdf.groupby("feature").apply(lambda g: (g.hs_missed + g.hs_false + g.to_missed + g.to_false).sum() == 0)
    mae = {}
    for feat in FEATURES:
        g = [s for (c, f), p in pooled.items() if f == feat for s in p["hs"]]
        mae[feat] = float(np.mean(np.abs(np.concatenate([s.errors for s in g])))) * 1000
    candidates = [f for f in FEATURES if clean[f]] or list(FEATURES)
    chosen = min(candidates, key=lambda f: mae[f])
    (OUT / "chosen_feature.txt").write_text(
        f"{chosen}\n# rule: no missed or false events, then lowest pooled HS MAE; "
        + ", ".join(f"{f}: clean={bool(clean[f])}, HS MAE {mae[f]:.1f} ms" for f in FEATURES)
        + "\n"
    )
    cols = ["condition", "feature", "hs_n_true", "hs_missed", "hs_false", "hs_error_mean_ms", "hs_error_sd_ms",
            "hs_latency_mean_ms", "to_n_true", "to_missed", "to_false", "to_error_mean_ms", "to_error_sd_ms",
            "to_latency_mean_ms", "phase_error_mean_pct", "phase_error_rms_pct"]
    print(pdf[cols].to_string(index=False))
    print("chosen:", chosen, mae)
    print("Lua vs twin max diff (s):", df.lua_twin_max_diff_s.dropna().max())
    plot_traces({k: v for k, v in traces.items() if k[1] == chosen}, chosen)


def plot_traces(traces: dict, feature: str, span: float = 3.0) -> None:
    n = len(traces)
    fig, axes = plt.subplots(2 * n, 1, figsize=(9, 3.6 * n), sharex=False, gridspec_kw={"height_ratios": [3, 1] * n})
    for i, ((cond, _), (sto, t, y, run, hs_true, to_true)) in enumerate(traces.items()):
        a = hs_true[hs_true > 20.0][0] - 0.2
        b = a + span
        ax, axp = axes[2 * i], axes[2 * i + 1]
        m = (sto.time >= a) & (sto.time <= b)
        ax.plot(sto.time[m], sto["imu.true"][m], color="0.6", lw=1, label="True shank angular velocity")
        ms = (t >= a) & (t <= b)
        ax.step(t[ms], y[ms], where="post", color="tab:blue", lw=1, label="Measured (100 Hz, 15 ms delay)")
        for k, (ev, col, name) in enumerate(((hs_true, "k", "HS"), (to_true, "tab:red", "TO"))):
            for e in ev[(ev >= a) & (ev <= b)]:
                ax.axvline(e, color=col, lw=1.2, label=f"True {name} (force)" if e == ev[(ev >= a)][0] else None)
        for est, det, col, name in ((run.hs_time, run.hs_detect, "k", "HS"), (run.to_time, run.to_detect, "tab:red", "TO")):
            sel = (est >= a) & (est <= b)
            ax.plot(est[sel], np.interp(est[sel], t, y), "o", mfc="none", color=col, ms=7, label=f"{name} estimate")
            ax.plot(det[sel], np.interp(det[sel], t, y), "x", color=col, ms=7, label=f"{name} confirmed")
        ax.axhline(0, color="0.8", lw=0.5)
        ax.set_ylabel("deg/s")
        ax.set_title(f"{cond}, seed 1, detector with HS feature '{feature}'", fontsize=9)
        ax.legend(fontsize=6.5, ncol=4, loc="upper left")
        tt = run.t[(run.t >= a) & (run.t <= b)]
        from dropfoot.validation import true_phase

        axp.plot(tt, 100 * true_phase(tt, hs_true), color="0.5", lw=1, label="True phase")
        axp.plot(tt, 100 * run.phase[(run.t >= a) & (run.t <= b)], color="tab:blue", lw=1, label="Estimated phase")
        axp.set_ylabel("Phase (%)")
        axp.legend(fontsize=6.5, loc="upper left")
        axp.set_xlabel("Time (s)")
        for x in (ax, axp):
            x.set_xlim(a, b)
            x.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)


if __name__ == "__main__":
    main()
