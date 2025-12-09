"""Pulse test of the device script in SCONE (Part F, before any controller).

Evaluates a healthy .par three times: with the device in mode ``none``, and
with a +2 N m and a -2 N m constant-torque pulse from 2.25 to 2.30 s, in mid
swing of the right leg for the tutorial parameters. Writes the scenarios to
scenarios/generated/, the ankle angles from 2.2 to 2.6 s to
tests/data/device_pulse.sto (used by tests/test_device.py) and a summary to
results/device_check/summary.json.

    python analysis/device_check.py [par]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from dropfoot import ROOT
from dropfoot.io import Storage, read_sto, write_sto
from dropfoot.scenarios import device_scenario, write_generated
from dropfoot.scone import evaluate

CASES = {"none": 0.0, "plus": 2.0, "minus": -2.0}
ON, OFF = 2.25, 2.30


def main(argv: list[str]) -> int:
    par = Path(argv[0]).resolve() if argv else ROOT / "data/raw/scone-tutorials/data/ResultGait10.par"
    runs, summary = {}, {"par": par.relative_to(ROOT).as_posix(), "pulse_nm": CASES, "on_s": ON, "off_s": OFF}
    for tag, tau in CASES.items():
        dev = {"mode": "constant" if tau else "none", "constant_nm": tau, "on_time": ON, "off_time": OFF}
        title = f"Device pulse test: healthy model, {tau:+g} N m from {ON} to {OFF} s (analysis/device_check.py)."
        scen = write_generated(f"test_pulse_{tag}", device_scenario(title, f"pulse_{tag}", dev))
        sto = evaluate(scen, par, ROOT / "results/raw/device_check" / tag)
        runs[tag] = read_sto(sto)
        report = sto.with_suffix(".txt").read_text() if sto.with_suffix(".txt").exists() else ""
        summary[tag] = {"duration_s": float(runs[tag].time[-1]), "fell": bool(runs[tag].time[-1] < 9.99)}
        for line in report.splitlines():
            if " result " in line or line.split()[1:2] == ["result"]:
                summary[tag]["cost"] = float(line.split("=")[1])
                break

    t = runs["none"].time
    keep = (t >= 2.2 - 1e-9) & (t <= 2.6 + 1e-9)
    n = keep.sum()
    col = lambda s, name: s.data[:, s.labels.index(name)]
    data = [col(runs[k], "ankle_angle_r")[keep] if len(runs[k].time) >= len(t) else
            col(runs[k], "ankle_angle_r")[: len(runs[k].time)][keep[: len(runs[k].time)]] for k in CASES]
    data = [np.pad(d, (0, n - len(d)), constant_values=np.nan) for d in data]
    torque = col(runs["plus"], "dev.torque")[keep]
    out = Storage(
        labels=("ankle_none", "ankle_plus", "ankle_minus", "torque_plus"),
        time=np.round(t[keep], 6),
        data=np.round(np.column_stack(data + [torque]), 8),
    )
    write_sto(out, ROOT / "tests/data/device_pulse.sto")

    d = out.data[:, 1] - out.data[:, 0]
    i = np.searchsorted(out.time, 2.26 - 1e-9)
    summary["ankle_change_after_10ms_deg"] = {
        "plus": float(np.degrees(d[i])),
        "minus": float(np.degrees(out.data[i, 2] - out.data[i, 0])),
    }
    path = ROOT / "results/device_check/summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
