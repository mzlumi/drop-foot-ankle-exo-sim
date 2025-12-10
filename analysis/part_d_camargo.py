#!/usr/bin/env python3
"""Part D4, sim to real: the same detector on measured shank gyroscopes.

    python analysis/part_d_camargo.py

Data: Camargo et al. (2021), the treadmill trial of each subject that contains
1.2 m/s (data/raw/camargo/selected_trials_1.20.csv, from
scripts/fetch_camargo.py). For each subject whose shank gyroscope passes the
calibration of dropfoot.camargo.align_gyro (sign and clock offset against
motion capture, r >= 0.9), the calibrated ``shank_Gyro_Y`` signal (200 Hz)
is taken at every second sample (100 Hz, as in the simulation, without an
anti-aliasing filter, as the simulated sensor samples the true velocity) and
delayed by the simulation's 15 ms. Nothing else is changed: the detector
settings are the ones tuned on the simulation. The detector runs over the
whole trial, including the other speeds, as it would on a person; events are
scored only on the 1.2 m/s plateaus, against the right belt force crossing 5%
of body weight (dropfoot.camargo.force_events).

Writes results/detector/camargo.csv (per subject and feature: counts and
timing statistics, no signals), results/detector/camargo_pooled.csv and
figures/detector_sim_vs_real.png (error distributions and one real trace).
"""

from __future__ import annotations

import csv
from dataclasses import replace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dropfoot import ROOT
from dropfoot.camargo import (
    CITATION,
    TrialFiles,
    align_gyro,
    aligned_imu,
    force_events,
    load_table,
    speed_windows,
    subject_info,
)
from dropfoot.detector import DetectorConfig
from dropfoot.io import read_sto
from dropfoot.sensor import GyroConfig
from dropfoot.validation import Score, gyro_samples, run_detector, score, true_events

RAW = ROOT / "data" / "raw" / "camargo"
OUT = ROOT / "results" / "detector"
FIGURE = ROOT / "figures" / "detector_sim_vs_real.png"
SPEED = 1.2
GYRO = GyroConfig()
FEATURES = ("min", "zero")
DECIMATE = 2  # 200 Hz to 100 Hz


def subject_run(trial: TrialFiles, mass: float):
    ik = load_table(trial.path("ik"))
    imu_raw = load_table(trial.path("imu"))
    alignment = align_gyro(ik, imu_raw)
    if not alignment.ok:
        return alignment, None
    imu = aligned_imu(imu_raw, alignment)
    t = imu["Header"].to_numpy()[::DECIMATE] + GYRO.delay_s
    y = np.degrees(imu["shank_gyro"].to_numpy()[::DECIMATE])
    hs, to = force_events(load_table(trial.path("fp")), mass)
    windows = speed_windows(load_table(trial.path("conditions"), "speed"), SPEED)
    return alignment, (t, y, hs, to, windows)


def pooled_score(scores: list[Score]) -> Score:
    return Score(
        np.concatenate([s.errors for s in scores]) if scores else np.array([]),
        np.concatenate([s.latency for s in scores]) if scores else np.array([]),
        sum(s.n_true for s in scores),
        sum(s.missed for s in scores),
        sum(s.false for s in scores),
    )


def main() -> None:
    info = subject_info(RAW / "SubjectInfo.mat")
    rows, pooled, example = [], {f: {"hs": [], "to": []} for f in FEATURES}, None
    with open(RAW / f"selected_trials_{SPEED:.2f}.csv") as fh:
        trials = list(csv.DictReader(fh))
    for row in trials:
        trial = TrialFiles(row["subject"], row["trial"], RAW / row["folder"])
        alignment, data = subject_run(trial, float(info.loc[row["subject"], "Weight"]))
        if data is None:
            rows.append({"subject": row["subject"], "used": 0, "gyro_r": alignment.r})
            print(f"{row['subject']}: gyroscope rejected (r = {alignment.r:.2f})")
            continue
        t, y, hs_true, to_true, windows = data
        for feat in FEATURES:
            run = run_detector(t, y, replace(DetectorConfig(), hs_feature=feat))
            hs = pooled_score([score(hs_true, run.hs_time, run.hs_detect, a, b) for a, b in windows])
            to = pooled_score([score(to_true, run.to_time, run.to_detect, a, b) for a, b in windows])
            pooled[feat]["hs"].append(hs)
            pooled[feat]["to"].append(to)
            r = {"subject": row["subject"], "used": 1, "gyro_r": alignment.r, "feature": feat}
            r.update(hs.summary("hs"))
            r.update(to.summary("to"))
            rows.append(r)
            if example is None and feat == "min" and hs.missed == 0 and to.missed == 0:
                example = (row["subject"], t, y, hs_true, to_true, run, windows[0])
        print(row["subject"], "done")
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "camargo.csv", index=False, float_format="%.4g")

    out = []
    for feat in FEATURES:
        r = {"source": "Camargo et al. (2021)", "feature": feat, "subjects": len(pooled[feat]["hs"])}
        r.update(pooled_score(pooled[feat]["hs"]).summary("hs"))
        r.update(pooled_score(pooled[feat]["to"]).summary("to"))
        out.append(r)
    pdf = pd.DataFrame(out)
    pdf.to_csv(OUT / "camargo_pooled.csv", index=False, float_format="%.4g")
    cols = ["feature", "subjects", "hs_n_true", "hs_missed", "hs_false", "hs_error_mean_ms", "hs_error_sd_ms",
            "hs_latency_mean_ms", "to_n_true", "to_missed", "to_false", "to_error_mean_ms", "to_error_sd_ms",
            "to_latency_mean_ms"]
    print(pdf[cols].to_string(index=False))
    plot(pooled, example)


def sim_errors(feature: str) -> dict[str, np.ndarray]:
    """Healthy simulation errors, recomputed from the cached 60 s evaluations."""
    out = {"hs": [], "to": []}
    for s in (1, 2, 3):
        path = ROOT / f"results/raw/eval/healthy_imu60_s{s}.par.sto"
        if not path.exists():
            continue
        sto = read_sto(path)
        hs_true, to_true = true_events(sto)
        t, y = gyro_samples(sto, GYRO.rate_hz, GYRO.delay_s)
        run = run_detector(t, y, replace(DetectorConfig(), hs_feature=feature))
        t1 = float(sto.time[-1]) - 0.5
        out["hs"].append(score(hs_true, run.hs_time, run.hs_detect, 2.0, t1).errors)
        out["to"].append(score(to_true, run.to_time, run.to_detect, 2.0, t1).errors)
    return {k: np.concatenate(v) if v else np.array([]) for k, v in out.items()}


def plot(pooled, example) -> None:
    feature = (OUT / "chosen_feature.txt").read_text().split()[0]
    sim = sim_errors(feature)
    fig = plt.figure(figsize=(9, 6.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.2])
    for i, key in enumerate(("hs", "to")):
        ax = fig.add_subplot(gs[0, i])
        real = 1000 * pooled_score(pooled[feature][key]).errors
        bins = np.arange(-120, 121, 5)
        ax.hist(real, bins=bins, color="tab:orange", alpha=0.7, density=True, label=f"Camargo, n = {len(real)}")
        ax.hist(1000 * sim[key], bins=bins, color="tab:blue", alpha=0.7, density=True, label=f"Simulation, n = {len(sim[key])}")
        ax.axvline(0, color="k", lw=0.8)
        ax.set_title(f"{'Heel strike' if key == 'hs' else 'Toe-off'} timing error (estimate minus force event)", fontsize=9)
        ax.set_xlabel("ms")
        ax.legend(fontsize=7)
        ax.tick_params(labelsize=8)
    if example:
        subject, t, y, hs_true, to_true, run, (w0, w1) = example
        a = hs_true[hs_true > w0 + 2.0][0] - 0.2
        b = a + 3.0
        ax = fig.add_subplot(gs[1, :])
        m = (t >= a) & (t <= b)
        ax.step(t[m], y[m], where="post", color="tab:orange", lw=1, label=f"{subject} shank gyroscope, calibrated, 100 Hz, +15 ms")
        for ev, col, name in ((hs_true, "k", "HS"), (to_true, "tab:red", "TO")):
            sel = ev[(ev >= a) & (ev <= b)]
            for j, e in enumerate(sel):
                ax.axvline(e, color=col, lw=1.2, label=f"True {name} (belt force)" if j == 0 else None)
        for est, det, col, name in ((run.hs_time, run.hs_detect, "k", "HS"), (run.to_time, run.to_detect, "tab:red", "TO")):
            sel = (est >= a) & (est <= b)
            ax.plot(est[sel], np.interp(est[sel], t, y), "o", mfc="none", color=col, ms=7, label=f"{name} estimate")
            ax.plot(det[sel], np.interp(det[sel], t, y), "x", color=col, ms=7, label=f"{name} confirmed")
        ax.axhline(0, color="0.8", lw=0.5)
        ax.set_xlim(a, b)
        ax.set_xlabel("Time in trial (s)")
        ax.set_ylabel("deg/s")
        ax.legend(fontsize=6.5, ncol=3, loc="upper left")
        ax.tick_params(labelsize=8)
    fig.suptitle(f"Detector (HS feature '{feature}') in simulation and on Camargo et al. (2021) data, 1.2 m/s", fontsize=10)
    fig.text(0.01, 0.003, "Data: " + CITATION[:118] + "...", fontsize=5.5)
    fig.tight_layout(rect=(0, 0.015, 1, 1))
    fig.savefig(FIGURE, dpi=150)


if __name__ == "__main__":
    main()
