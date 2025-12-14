#!/usr/bin/env python3
"""Part E: torque controller for the chosen SEA, bandwidth, saturation and the fitted actuator model.

    python analysis/part_e.py

Reads the design of Part C (results/actuator/design.json, requirement.csv).

E1. Gains by pole placement (dropfoot.sea_control.design), for the lowest
closed-loop natural frequency in ``CANDIDATE_HZ`` (only those at least 10%
above the locked-output resonance, where pole placement needs a positive
proportional gain) that meets both targets of
the assignment: small-signal bandwidth of at least 10 Hz (feedback and
static feedforward only, so the number does not rely on a perfect model) and
RMS tracking error under 10% of the peak torque on the gait profile with
saturation. The model-based feedforward is on in the tracking runs.

E2. Bode plot of the closed loop with the output locked, small signal
(0.5 N m) with and without the model feedforward, and large signal (the
peak of the requirement) with current and voltage saturation. Tracking: five
strides of the Part C requirement while the joint follows the same healthy
ankle trajectory as in Part C.

E3. Fit of the device script's actuator model (pure delay plus first-order
lag, dropfoot.device.ActuatorLag) to the tracking runs, with and without the
model feedforward. With it the loop is nearly ideal on the smooth gait
profile (the fit has no delay and no lag), but that relies on the first and
second derivatives of the command, and the FSM of Part F commands torques
that jump at state changes. The SCONE device therefore uses the more
conservative fit of the loop with the static feedforward only; it goes to
results/actuator/actuator_fit.json with the torque limit of Part C (the
peak of the requirement). The ideal fit is checked against the full model on
a step.

Outputs: results/actuator/control.json, results/actuator/actuator_fit.json,
figures/sea_bode.png, figures/sea_tracking.png.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dropfoot import ROOT
from dropfoot.actuator import load_motor, periodic_resample
from dropfoot.sea_control import (
    SEA,
    bandwidth,
    design,
    first_order_delay,
    fit_first_order_delay,
    frequency_response,
    simulate,
)

OUT = ROOT / "results" / "actuator"
FIG = ROOT / "figures"
CANDIDATE_HZ = tuple(float(f) for f in np.arange(10.0, 81.0, 5.0))
FREQS = np.geomspace(0.5, 200.0, 28)
STRIDES = 5


def tracking_inputs(req: pd.DataFrame, stride: float, period: float):
    t = np.arange(0.0, STRIDES * stride, period)
    pct = 100 * ((t / stride) % 1.0)
    tau_d = periodic_resample(req.percent.to_numpy(), req.requirement_nm.to_numpy(), pct)
    theta = periodic_resample(req.percent.to_numpy(), req.ankle_normative_rad.to_numpy(), pct)
    return t, tau_d, theta


def main() -> None:
    dj = json.loads((OUT / "design.json").read_text())
    req = pd.read_csv(OUT / "requirement.csv")
    motor, extra = load_motor()
    sea = SEA(motor, dj["chosen"]["ratio"], dj["chosen"]["stiffness"], eta=extra["gear_efficiency"], inductance=extra["inductance"])
    stride = dj["stride_time_s"]
    peak = float(tracking_inputs(req, stride, 1e-3)[1].max())

    chosen, candidates = None, []
    for f in (f for f in CANDIDATE_HZ if f >= 1.1 * sea.locked_resonance_hz):
        ctrl = design(sea, f)
        g, _ = frequency_response(sea, replace(ctrl, model_feedforward=False), FREQS)
        bw = bandwidth(FREQS, g)
        t, tau_d, theta = tracking_inputs(req, stride, ctrl.period)
        tr = simulate(sea, ctrl, t, tau_d, theta)
        keep = t >= stride  # after the first stride
        rms = tr.rms_error(keep)
        # saturation bounds an unstable loop in the tracking run, so stability (and peaking under 6 dB) is judged on the small-signal response
        stable = bool(np.all(np.isfinite(g)) and np.isfinite(bw) and g.max() < 2.0 and np.all(np.isfinite(tr.tau)))
        candidates.append({"design_hz": f, "bandwidth_hz": bw, "rms_error_nm": rms, "rms_error_pct_peak": 100 * rms / peak, "small_signal_ok": stable})
        print(candidates[-1])
        if chosen is None and stable and bw >= 10.0 and rms < 0.1 * peak:
            chosen = (f, ctrl, tr)
    if chosen is None:
        best = min((c for c in candidates if c["small_signal_ok"]), key=lambda c: c["rms_error_nm"])
        f = best["design_hz"]
        ctrl = design(sea, f)
        t, tau_d, theta = tracking_inputs(req, stride, ctrl.period)
        chosen = (f, ctrl, simulate(sea, ctrl, t, tau_d, theta))
        print("no candidate meets both targets; using", f)
    f_design, ctrl, tr = chosen
    t, tau_d, theta = tracking_inputs(req, stride, ctrl.period)
    keep = t >= stride

    g_fb, ph_fb = frequency_response(sea, replace(ctrl, model_feedforward=False), FREQS)
    g_ff, ph_ff = frequency_response(sea, ctrl, FREQS)
    g_big, ph_big = frequency_response(sea, replace(ctrl, model_feedforward=False), FREQS, amplitude=peak, saturate=True)
    bw = {"feedback_static_ff": bandwidth(FREQS, g_fb), "with_model_ff": bandwidth(FREQS, g_ff), "large_signal_saturated": bandwidth(FREQS, g_big)}
    differs = np.flatnonzero(np.abs(20 * np.log10(g_big / g_fb)) > 1.0)
    saturation_onset_hz = float(FREQS[differs[0]]) if len(differs) else float("nan")
    no_ff = simulate(sea, replace(ctrl, model_feedforward=False), t, tau_d, theta)

    tc, delay, fit_rms = fit_first_order_delay(tau_d[keep], tr.tau[keep], ctrl.period)
    tc_s, delay_s, fit_rms_s = fit_first_order_delay(tau_d[keep], no_ff.tau[keep], ctrl.period)
    step_t = np.arange(0.0, 0.25, ctrl.period)
    step_u = np.where(step_t >= 0.02, 0.5 * peak, 0.0)
    step_full = simulate(sea, ctrl, step_t, step_u)
    step_fit = first_order_delay(step_u, ctrl.period, tc, delay)
    step_rms = float(np.sqrt(np.mean((step_full.tau - step_fit) ** 2)))

    control = {
        "sea": {"ratio": sea.ratio, "stiffness": sea.stiffness, "reflected_inertia": sea.j_r, "reflected_damping": sea.b_r,
                "locked_resonance_hz": sea.locked_resonance_hz, "eta": sea.eta},
        "controller": asdict(ctrl),
        "design_natural_frequency_hz": f_design,
        "candidates": candidates,
        "bandwidth_hz": bw,
        "saturation_onset_hz": saturation_onset_hz,  # NaN: saturation changes no gain by 1 dB up to the next key
        "saturation_checked_up_to_hz": float(FREQS[-1]),
        "tracking": {
            "rms_error_nm": tr.rms_error(keep),
            "rms_error_pct_peak": 100 * tr.rms_error(keep) / peak,
            "rms_error_without_model_ff_nm": no_ff.rms_error(keep),
            "peak_torque_nm": peak,
            "peak_current_a": float(np.max(np.abs(tr.current))),
            "peak_voltage_v": float(np.max(np.abs(tr.voltage))),
            "current_clipped_fraction": float(tr.current_clipped[keep].mean()),
            "voltage_clipped_fraction": float(tr.voltage_clipped[keep].mean()),
        },
        "fit": {"time_constant_s": tc, "delay_s": delay, "rms_error_nm": fit_rms, "step_rms_error_nm": step_rms},
        "fit_without_model_ff": {"time_constant_s": tc_s, "delay_s": delay_s, "rms_error_nm": fit_rms_s},
    }
    (OUT / "control.json").write_text(json.dumps(control, indent=2) + "\n")
    (OUT / "actuator_fit.json").write_text(
        json.dumps({"delay_s": round(delay_s, 4), "time_constant_s": round(tc_s, 5), "limit_nm": round(peak, 2),
                    "source": "analysis/part_e.py: fit to the closed-loop tracking of the Part C requirement, static feedforward"},
                   indent=2) + "\n"
    )
    print(json.dumps({k: control[k] for k in ("bandwidth_hz", "saturation_onset_hz", "tracking", "fit", "fit_without_model_ff")}, indent=1))

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.5, 6), sharex=True)
    for g, ph, lab, st in ((g_fb, ph_fb, "small signal, feedback + static FF", "-"), (g_ff, ph_ff, "small signal, + model FF", "--"),
                           (g_big, ph_big, f"large signal ({peak:.1f} N m), saturated", ":")):
        a1.semilogx(FREQS, 20 * np.log10(g), st, label=lab)
        a2.semilogx(FREQS, np.degrees(ph), st)
    a1.axhline(-3, color="0.6", lw=0.8)
    a1.axvline(10, color="0.6", lw=0.8)
    a1.set_ylabel("Gain (dB)")
    a1.set_ylim(-30, 10)
    a1.legend(fontsize=7)
    a1.set_title(f"SEA torque loop, N = {sea.ratio:.0f}, k = {sea.stiffness:.0f} N m/rad, output locked; "
                 f"bandwidth {bw['feedback_static_ff']:.1f} Hz", fontsize=9)
    a2.set_ylabel("Phase (deg)")
    a2.set_xlabel("Frequency (Hz)")
    a2.set_ylim(-360, 45)
    fig.tight_layout()
    fig.savefig(FIG / "sea_bode.png", dpi=150)

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7, 5.5), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    m = (t >= 2 * stride) & (t <= 4 * stride)
    a1.plot(t[m], tau_d[m], "k", lw=1.2, label="Command (Part C requirement)")
    a1.plot(t[m], tr.tau[m], color="tab:blue", lw=1, label=f"SEA, PID + model FF (RMS error {tr.rms_error(keep):.2f} N m)")
    a1.plot(t[m], no_ff.tau[m], color="tab:orange", lw=0.8, alpha=0.8, label=f"SEA, PID + static FF ({no_ff.rms_error(keep):.2f} N m)")
    a1.plot(t[m], first_order_delay(tau_d, ctrl.period, tc_s, delay_s)[m], "--", color="tab:green", lw=1,
            label=f"Fit to the static FF loop (used in SCONE): delay {1000 * delay_s:.0f} ms, lag {1000 * tc_s:.1f} ms")
    a1.set_ylabel("Ankle torque (N m)")
    a1.legend(fontsize=7)
    a2.plot(t[m], tr.current[m], color="tab:blue", lw=1)
    a2.axhline(motor.peak_current, color="k", ls=":", lw=0.8)
    a2.axhline(-motor.peak_current, color="k", ls=":", lw=0.8)
    a2.set_ylabel("Current (A)")
    a2.set_xlabel("Time (s)")
    fig.tight_layout()
    fig.savefig(FIG / "sea_tracking.png", dpi=150)


if __name__ == "__main__":
    main()
