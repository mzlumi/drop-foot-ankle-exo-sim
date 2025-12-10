"""Series elastic actuator (SEA) model for the ankle exoskeleton (Part C).

Chain: brushless DC motor, gear reduction N, series spring k, ankle joint.

Signs follow docs/conventions.md: the joint torque ``tau`` acting on the
foot is positive when it dorsiflexes, and the joint angle ``theta_j`` is
positive in dorsiflexion. All angles are in rad, torques in N m.

Equations, for a prescribed joint torque tau(t) and joint angle theta_j(t)
over one stride:

* spring: tau = k (theta_out - theta_j), so theta_out = theta_j + tau / k
  (rigid actuator: k = inf, theta_out = theta_j);
* gear (ideal, efficiency ``eta``): theta_m = N theta_out; the load seen by
  the motor is tau / (N eta) when the motor drives the load and
  tau eta / N when the load drives the motor;
* motor: tau_m = J_m alpha_m + b_m omega_m + load, i = tau_m / K_t,
  V = R i + K_e omega_m (K_e = K_t in SI units).

Electrical power is P = V i = R i^2 + tau_m omega_m, so the copper loss
R i^2 is already inside V i. Energy per stride is reported two ways:

* ``energy_no_regen`` = integral of max(V i, 0): the drive does not recover
  energy; when the motor generates (V i < 0) the energy goes to a brake
  resistor. This is the design number (most small exoskeleton drives do not
  regenerate into a battery usefully).
* ``energy_regen`` = integral of V i: an ideal regenerating drive, a lower
  bound.

The trajectories are periodic over one stride, so derivatives use periodic
central differences.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Motor:
    name: str
    kt: float  # N m/A, torque constant (= back-EMF constant in V s/rad)
    resistance: float  # ohm, terminal (phase to phase)
    inertia: float  # kg m^2, rotor
    rated_current: float  # A, continuous
    max_speed: float  # rad/s, permissible
    supply_voltage: float  # V, nominal
    peak_current: float | None = None  # A, short-term limit if given
    damping: float = 0.0  # N m s/rad, viscous at the rotor

    @property
    def ke(self) -> float:
        return self.kt


MOTOR_FILE = "actuator/motor_ec45flat_411812.toml"


def load_motor(path: str | Path | None = None) -> tuple[Motor, dict]:
    """The chosen motor from its parameter file, and the remaining entries
    (inductance, gear efficiency) as a dict."""
    import tomllib

    from dropfoot import ROOT

    raw = tomllib.loads(Path(path or ROOT / MOTOR_FILE).read_text())
    fields = {f.name for f in dataclasses.fields(Motor)}
    return Motor(**{k: v for k, v in raw.items() if k in fields}), {k: v for k, v in raw.items() if k not in fields}


def periodic_resample(percent: np.ndarray, y: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Periodic cubic spline through a gait-cycle curve on ``percent`` (0 to 100), evaluated at ``x`` (wrapped).

    Linear interpolation would make the second derivative a train of impulses
    at the 1% knots, which the inertial terms (and a feedforward on joint
    acceleration) would then see as real. The end point is replaced by the
    first so that the curve closes.
    """
    from scipy.interpolate import CubicSpline

    yc = np.asarray(y, float).copy()
    yc[-1] = yc[0]
    return CubicSpline(percent, yc, bc_type="periodic")(np.mod(x, 100.0))


def periodic_derivative(y: np.ndarray, dt: float) -> np.ndarray:
    """Central difference of a periodic signal sampled without the repeated end point."""
    return (np.roll(y, -1) - np.roll(y, 1)) / (2 * dt)


@dataclass(frozen=True)
class Operation:
    """Motor operating trajectory over one stride and its summary numbers."""

    t: np.ndarray
    theta_out: np.ndarray
    omega_m: np.ndarray
    tau_m: np.ndarray
    current: np.ndarray
    voltage: np.ndarray

    @property
    def power(self) -> np.ndarray:
        return self.voltage * self.current

    @property
    def dt(self) -> float:
        return float(self.t[1] - self.t[0])

    @property
    def energy_no_regen(self) -> float:
        return float(np.sum(np.maximum(self.power, 0.0)) * self.dt)

    @property
    def energy_regen(self) -> float:
        return float(np.sum(self.power) * self.dt)

    @property
    def peak_speed(self) -> float:
        return float(np.max(np.abs(self.omega_m)))

    @property
    def peak_current(self) -> float:
        return float(np.max(np.abs(self.current)))

    @property
    def rms_current(self) -> float:
        return float(np.sqrt(np.mean(self.current**2)))

    @property
    def peak_voltage(self) -> float:
        return float(np.max(np.abs(self.voltage)))

    @property
    def peak_power(self) -> float:
        return float(np.max(self.power))


def operate(
    motor: Motor, ratio: float, stiffness: float, t: np.ndarray, tau: np.ndarray, theta_j: np.ndarray, eta: float = 1.0
) -> Operation:
    """Motor trajectory needed to produce joint torque ``tau`` while the joint follows ``theta_j``.

    ``t`` is a uniform grid over one stride without the repeated end point.
    ``stiffness = np.inf`` gives the rigid actuator.
    """
    t, tau, theta_j = (np.asarray(x, float) for x in (t, tau, theta_j))
    dt = float(t[1] - t[0])
    theta_out = theta_j + (tau / stiffness if np.isfinite(stiffness) else 0.0)
    omega_out = periodic_derivative(theta_out, dt)
    omega_m = ratio * omega_out
    alpha_m = periodic_derivative(omega_m, dt)
    load = tau / ratio
    if eta != 1.0:
        driving = tau * omega_out >= 0  # the motor delivers power to the joint side
        load = np.where(driving, load / eta, load * eta)
    tau_m = motor.inertia * alpha_m + motor.damping * omega_m + load
    current = tau_m / motor.kt
    voltage = motor.resistance * current + motor.ke * omega_m
    return Operation(t, theta_out, omega_m, tau_m, current, voltage)


@dataclass(frozen=True)
class Limits:
    speed: bool
    current: bool
    voltage: bool

    @property
    def ok(self) -> bool:
        return self.speed and self.current and self.voltage


def check_limits(op: Operation, motor: Motor) -> Limits:
    """Peak speed below the permissible speed, RMS current below the rated
    (thermal) current and peak current below the short-term limit if one is
    given, and peak voltage below the supply."""
    current_ok = op.rms_current <= motor.rated_current
    if motor.peak_current is not None:
        current_ok = current_ok and op.peak_current <= motor.peak_current
    return Limits(op.peak_speed <= motor.max_speed, current_ok, op.peak_voltage <= motor.supply_voltage)


def torque_requirement(ta_healthy: np.ndarray, ta_weak: np.ndarray, margin: float = 0.2) -> np.ndarray:
    """Assistive torque profile: the TA moment that the weakness removed, plus a margin.

    Only the dorsiflexing part is kept: the device replaces the missing
    tibialis anterior, which can only pull the foot up (in swing) or brake
    plantarflexion (in early stance), both positive moments.
    """
    return (1.0 + margin) * np.maximum(np.asarray(ta_healthy) - np.asarray(ta_weak), 0.0)


def speed_torque_envelope(motor: Motor, n: int = 50) -> tuple[np.ndarray, np.ndarray]:
    """Motor torque-speed boundary at the supply voltage (first quadrant):
    speed = (V - R tau / K_t) / K_e, capped at the permissible speed."""
    stall = motor.kt * motor.supply_voltage / motor.resistance
    torque = np.linspace(0.0, stall, n)
    speed = np.minimum((motor.supply_voltage - motor.resistance * torque / motor.kt) / motor.ke, motor.max_speed)
    return torque, speed
