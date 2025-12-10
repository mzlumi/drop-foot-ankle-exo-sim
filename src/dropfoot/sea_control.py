"""Low-level torque control of the series elastic actuator (Part E).

Plant, in output (joint side) coordinates, with the gearbox output angle
``theta`` (motor angle divided by N) and the prescribed joint angle
``theta_j``:

* spring torque ``tau = k (theta - theta_j)``, the controlled variable;
* motor and gear: ``J_r theta'' = eta N K_t i - b_r theta' - tau`` with the
  reflected inertia ``J_r = J_m N^2`` and damping ``b_r = b_m N^2``; the gear
  efficiency ``eta`` scales the motor torque (a constant here, so the model is
  linear; Part C treats driving and back-driving separately);
* winding: ``L di/dt = V - R i - K_e N theta'``, with a PI current loop of
  bandwidth ``current_bw_hz`` that saturates at the supply voltage, and a
  current command clipped to the drive's peak current.

Torque controller, sampled at ``period`` (1 ms, the SCONE control step), with
the command applied one sample later (computation delay) and held:

    u = u_ff + Kp e + Ki integral(e) - Kd d(tau_f)/dt,      e = tau_d - tau
    i_cmd = u / (eta N K_t)

where ``tau_f`` is the measured torque through a first-order filter of
``d_filter_hz`` (derivative on measurement, so torque steps do not kick).
The feedforward is the static term ``tau_d`` plus, optionally, the model
term ``J_r a_ff + b_r w_ff`` that moves the gearbox output with the joint and
the spring deflection: ``w_ff = theta_j' + tau_d'/k``, ``a_ff = theta_j'' +
tau_d''/k``. The integral stops when the current command is clipped
(anti-windup).

Gains come from pole placement on the locked-output plant
``J_r s^2 + (b_r + Kd k) s + k (1 + Kp)``: natural frequency
``2 pi bandwidth_hz`` and damping ``zeta``, with the integral zero a factor
``ki_ratio`` below it. The resulting closed-loop bandwidth is measured, not
assumed, from simulated small-signal sine responses (:func:`frequency_response`).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from dropfoot.actuator import Motor
from dropfoot.device import ActuatorLag


@dataclass(frozen=True)
class SEA:
    motor: Motor
    ratio: float
    stiffness: float  # N m/rad
    eta: float = 0.85
    inductance: float = 0.463e-3  # H

    @property
    def j_r(self) -> float:
        return self.motor.inertia * self.ratio**2

    @property
    def b_r(self) -> float:
        return self.motor.damping * self.ratio**2

    @property
    def torque_per_amp(self) -> float:
        return self.eta * self.ratio * self.motor.kt

    @property
    def locked_resonance_hz(self) -> float:
        return float(np.sqrt(self.stiffness / self.j_r) / (2 * np.pi))


@dataclass(frozen=True)
class Controller:
    kp: float
    ki: float  # 1/s
    kd: float  # s
    period: float = 1e-3
    d_filter_hz: float = 100.0
    current_bw_hz: float = 1000.0
    model_feedforward: bool = True
    computation_delay: bool = True


def design(sea: SEA, bandwidth_hz: float, zeta: float = 0.7, ki_ratio: float = 5.0, **kw) -> Controller:
    """PID gains by pole placement on the locked-output plant (see the module docstring)."""
    w = 2 * np.pi * bandwidth_hz
    kp = max(sea.j_r * w**2 / sea.stiffness - 1.0, 0.0)
    kd = max((2 * zeta * w * sea.j_r - sea.b_r) / sea.stiffness, 0.0)
    ki = (1.0 + kp) * w / ki_ratio
    return Controller(kp=kp, ki=ki, kd=kd, **kw)


@dataclass
class Trace:
    t: np.ndarray
    tau_d: np.ndarray
    tau: np.ndarray
    current: np.ndarray
    voltage: np.ndarray
    omega_m: np.ndarray
    current_clipped: np.ndarray = field(default_factory=lambda: np.array([]))
    voltage_clipped: np.ndarray = field(default_factory=lambda: np.array([]))

    def rms_error(self, mask: np.ndarray | None = None) -> float:
        e = self.tau - self.tau_d
        return float(np.sqrt(np.mean(e[mask] ** 2 if mask is not None else e**2)))


def _deriv(y: np.ndarray, dt: float) -> np.ndarray:
    return np.gradient(y, dt)


def simulate(
    sea: SEA,
    ctrl: Controller,
    t: np.ndarray,
    tau_d: np.ndarray,
    theta_j: np.ndarray | None = None,
    saturate: bool = True,
    substeps: int = 40,
) -> Trace:
    """Run the closed loop over the controller sample times ``t`` (uniform, ``ctrl.period``).

    ``tau_d`` and ``theta_j`` are given at those samples; ``theta_j`` = None locks
    the output (``theta_j = 0``). Returns values at the sample times.
    """
    m = sea.motor
    T = ctrl.period
    t = np.asarray(t, float)
    n = len(t)
    tau_d = np.asarray(tau_d, float)
    theta_j = np.zeros(n) if theta_j is None else np.asarray(theta_j, float)
    omega_j = _deriv(theta_j, T)
    alpha_j = _deriv(omega_j, T)
    dtau = _deriv(tau_d, T)
    ddtau = _deriv(dtau, T)
    k, jr, br, ka = sea.stiffness, sea.j_r, sea.b_r, sea.torque_per_amp
    i_peak = m.peak_current if (saturate and m.peak_current) else np.inf
    v_sup = m.supply_voltage if saturate else np.inf
    wc = 2 * np.pi * ctrl.current_bw_hz
    kp_i, ki_i = sea.inductance * wc, m.resistance * wc
    alpha_f = 1.0 - np.exp(-2 * np.pi * ctrl.d_filter_hz * T)
    h = T / substeps

    theta = theta_j[0] + tau_d[0] / k
    omega = omega_j[0] + dtau[0] / k
    cur = 0.0
    i_int = 0.0
    e_int = 0.0
    tau_f = k * (theta - theta_j[0])
    i_cmd_next = i_cmd = 0.0
    out = {name: np.empty(n) for name in ("tau", "cur", "volt", "om", "iclip", "vclip")}
    for j in range(n):
        tau = k * (theta - theta_j[j])
        # torque controller at the sample
        tau_f_prev = tau_f
        tau_f = tau_f + alpha_f * (tau - tau_f)
        e = tau_d[j] - tau
        ff = tau_d[j]
        if ctrl.model_feedforward:
            ff += jr * (alpha_j[j] + ddtau[j] / k) + br * (omega_j[j] + dtau[j] / k)
        u = ff + ctrl.kp * e + ctrl.ki * e_int - ctrl.kd * (tau_f - tau_f_prev) / T
        raw = u / ka
        cmd = float(np.clip(raw, -i_peak, i_peak))
        clipped = cmd != raw
        if not clipped:
            e_int += e * T
        if ctrl.computation_delay:
            i_cmd, i_cmd_next = i_cmd_next, cmd
        else:
            i_cmd = cmd
        # plant over one period, joint motion interpolated linearly
        th0, th1 = theta_j[j], theta_j[min(j + 1, n - 1)]
        v_max = 0.0
        vclip = False
        for s in range(substeps):
            thj = th0 + (th1 - th0) * (s + 0.5) / substeps
            ei = i_cmd - cur
            v = kp_i * ei + ki_i * i_int
            v_sat = float(np.clip(v, -v_sup, v_sup))
            if v_sat == v:
                i_int += ei * h
            else:
                vclip = True
            wm = sea.ratio * omega
            cur += h * (v_sat - m.resistance * cur - m.ke * wm) / sea.inductance
            acc = (ka * cur - br * omega - k * (theta - thj)) / jr
            omega += h * acc
            theta += h * omega
            v_max = v_sat if abs(v_sat) > abs(v_max) else v_max
        out["tau"][j] = tau
        out["cur"][j] = cur
        out["volt"][j] = v_max
        out["om"][j] = sea.ratio * omega
        out["iclip"][j] = clipped
        out["vclip"][j] = vclip
    return Trace(t, tau_d, out["tau"], out["cur"], out["volt"], out["om"], out["iclip"].astype(bool), out["vclip"].astype(bool))


def frequency_response(
    sea: SEA, ctrl: Controller, freqs_hz: np.ndarray, amplitude: float = 0.5, cycles: int = 12, settle: int = 6
) -> tuple[np.ndarray, np.ndarray]:
    """Closed-loop gain and phase (rad) from tau_d to tau with the output locked.

    Each frequency is simulated without saturation; gain and phase come from
    projecting the last ``cycles - settle`` periods on sine and cosine.
    """
    gains, phases = [], []
    for f in freqs_hz:
        dur = max(cycles / f, 0.2)
        t = np.arange(0.0, dur, ctrl.period)
        ref = amplitude * np.sin(2 * np.pi * f * t)
        tr = simulate(sea, ctrl, t, ref, saturate=False)
        keep = t >= dur * settle / cycles
        s, c = np.sin(2 * np.pi * f * t[keep]), np.cos(2 * np.pi * f * t[keep])
        a = 2 * np.mean(tr.tau[keep] * s)
        b = 2 * np.mean(tr.tau[keep] * c)
        gains.append(np.hypot(a, b) / amplitude)
        phases.append(np.arctan2(b, a))
    return np.array(gains), np.unwrap(np.array(phases))


def bandwidth(freqs_hz: np.ndarray, gains: np.ndarray, level: float = 10 ** (-3 / 20)) -> float:
    """First frequency where the gain falls below ``level`` (-3 dB), interpolated in log frequency."""
    below = np.flatnonzero(gains < level)
    if not len(below):
        return float("nan")
    i = below[0]
    if i == 0:
        return float(freqs_hz[0])
    lf = np.log(freqs_hz[i - 1 : i + 1])
    return float(np.exp(np.interp(level, gains[i - 1 : i + 1][::-1], lf[::-1])))


def first_order_delay(u: np.ndarray, dt: float, time_constant: float, delay: float) -> np.ndarray:
    """Response of the SCONE actuator model (:class:`dropfoot.device.ActuatorLag`, the twin of
    scenarios/lua/actuator.lua) to commands ``u`` given every ``dt``, so that fitted parameters
    mean exactly what the device script does."""
    lag = ActuatorLag(delay, time_constant)
    return np.array([lag.update(i * dt, float(x)) for i, x in enumerate(u)])


def fit_first_order_delay(
    u: np.ndarray, y: np.ndarray, dt: float, delays: np.ndarray | None = None, taus: np.ndarray | None = None
) -> tuple[float, float, float]:
    """Grid search for (time constant, delay) minimizing the RMS of y minus the model; returns them and the RMS."""
    delays = np.arange(0.0, 0.0205, dt) if delays is None else delays
    taus = np.concatenate([[0.0], np.geomspace(1e-3, 0.1, 40)]) if taus is None else taus
    best = (np.inf, 0.0, 0.0)
    for L in delays:
        for tc in taus:
            r = float(np.sqrt(np.mean((first_order_delay(u, dt, tc, L) - y) ** 2)))
            if r < best[0]:
                best = (r, tc, L)
    return best[1], best[2], best[0]


def with_gains(ctrl: Controller, **kw) -> Controller:
    return replace(ctrl, **kw)
