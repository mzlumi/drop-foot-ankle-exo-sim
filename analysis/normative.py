"""Normative curves from the Camargo et al. (2021) treadmill trials.

For each subject in data/raw/camargo/selected_trials_<speed>.csv (written by
scripts/fetch_camargo.py), the right-leg strides on the constant-speed plateau
are normalized to 0 to 100% of the gait cycle and averaged; the committed file
holds the mean and SD of those subject means. Per-subject curves are not
written. The shank gyroscope calibration (sign, time offset, correlation with
inverse kinematics) is written per subject, because it is a property of the
recording setup that the sim-to-real test needs.

    python analysis/normative.py --speed 1.2
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from dropfoot import ROOT
from dropfoot.camargo import VARIABLES, TrialFiles, aggregate, subject_curves, subject_info, write_normative

RAW = ROOT / "data" / "raw" / "camargo"
OUT = ROOT / "results" / "normative"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--speed", type=float, default=1.2)
    args = p.parse_args(argv)

    info = subject_info(RAW / "SubjectInfo.mat")
    per_subject, counts, alignments = {}, {}, {}
    with open(RAW / f"selected_trials_{args.speed:.2f}.csv") as fh:
        for row in csv.DictReader(fh):
            trial = TrialFiles(row["subject"], row["trial"], RAW / row["folder"])
            curves, alignments[row["subject"]] = subject_curves(
                trial, float(info.loc[row["subject"], "Weight"]), args.speed
            )
            counts[row["subject"]] = len(curves["stance_pct"])
            if counts[row["subject"]] < 5:
                print(f"{row['subject']}: only {counts[row['subject']]} strides, excluded")
                continue
            per_subject[row["subject"]] = curves

    df = aggregate(per_subject)
    n_strides = sum(len(c["stance_pct"]) for c in per_subject.values())
    stem = f"camargo_treadmill_{args.speed:.2f}mps"
    write_normative(df, OUT / f"{stem}.csv", args.speed, sorted(per_subject), n_strides)

    with open(OUT / f"{stem}_imu_alignment.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["subject", "sign", "lag_ms", "r", "gain", "used"])
        for subject, a in sorted(alignments.items()):
            w.writerow([subject, a.sign, f"{1000 * a.lag:.1f}", f"{a.r:.3f}", f"{a.gain:.3f}", int(a.ok)])

    stance = [c["stance_pct"].mean() for c in per_subject.values()]
    summary = {
        "speed_mps": args.speed,
        "subjects": len(per_subject),
        "subjects_per_variable": df.attrs["n_subjects"],
        "strides_total": n_strides,
        "strides_per_subject_min": min(counts.values()),
        "strides_per_subject_max": max(counts.values()),
        "stance_pct_mean": round(float(np.mean(stance)), 2),
        "stance_pct_sd": round(float(np.std(stance, ddof=1)), 2),
        "imu_rejected": sorted(s for s, a in alignments.items() if not a.ok),
        "source": "Camargo et al. (2021), doi:10.1016/j.jbiomech.2021.110320, CC BY 4.0",
    }
    (OUT / f"{stem}.json").write_text(json.dumps(summary, indent=2) + "\n")

    fig, axes = plt.subplots(2, 3, figsize=(11, 6), sharex=True)
    for ax, (name, (_, _, _, unit)) in zip(axes.flat, VARIABLES.items()):
        m, s = df[f"{name}_mean"], df[f"{name}_sd"]
        ax.fill_between(df["percent"], m - s, m + s, color="0.8")
        ax.plot(df["percent"], m, color="k")
        ax.axvline(summary["stance_pct_mean"], color="0.5", ls="--", lw=0.8)
        ax.set_title(f"{name.replace('_', ' ')} (n = {df.attrs['n_subjects'][name]})")
        ax.set_ylabel(unit)
    for ax in axes[-1]:
        ax.set_xlabel("% gait cycle")
    fig.suptitle(f"Camargo et al. (2021), treadmill {args.speed:.2f} m/s, right leg: mean and SD of subject means")
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / f"normative_{stem}.png", dpi=150)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
