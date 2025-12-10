"""Phase-based finite-state controller of the active AFO (Part F2).

Python twin of scenarios/lua/fsm.lua; see that file for the states. The
controller sees only what the device would: the shank-gyroscope detector's
events and phase estimate (:mod:`dropfoot.detector`) and its own ankle angle
and velocity. Torque is positive when it dorsiflexes and never negative.

Default gains, from a design calculation rather than tuning:

* braking ``b = 1 N m s/rad``: about 10 N m at a foot-slap velocity of
  600 deg/s, the size of the healthy model's eccentric tibialis anterior
  moment in early stance (about 12 N m at 10% of the cycle);
* swing PD ``kp = 30 N m/rad``, ``kd = 0.6 N m s/rad``: about 5 N m for a
  10 deg error, the healthy swing tibialis anterior moment (7 to 13 N m) is
  the scale, and with a foot inertia about the ankle of roughly 0.015 kg m^2
  the loop is close to critically damped (natural frequency about 45 rad/s),
  slow enough to stay stable with the actuator's delay;
* ``early_frac = 0.15`` of the cycle, as specified;
* the swing target (default 5 deg of dorsiflexion) is the one setting chosen
  by the rule in the README (0, 5 or 10 deg).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

OFF, EARLY, TRANSPARENT, SWING = 0, 1, 2, 3


@dataclass(frozen=True)
class FSMConfig:
    early_frac: float = 0.15
    brake_nms_per_rad: float = 1.0
    kp_nm_per_rad: float = 30.0
    kd_nms_per_rad: float = 0.6
    target_rad: float = math.radians(5.0)
    swing_timeout_s: float = 0.8

    def lua_properties(self) -> dict[str, str]:
        return {k: repr(v) for k, v in self.__dict__.items()}


class PhaseController:
    def __init__(self, cfg: FSMConfig = FSMConfig()):
        self.cfg = cfg
        self.state = OFF
        self.t_enter = 0.0

    def update(self, t: float, event: int, phase: float, theta: float, theta_dot: float) -> float:
        c = self.cfg
        if event == 1:
            self.state, self.t_enter = EARLY, t
        elif event == 2:
            self.state, self.t_enter = SWING, t
        if self.state == EARLY and phase >= c.early_frac:
            self.state, self.t_enter = TRANSPARENT, t
        elif self.state == SWING and t - self.t_enter > c.swing_timeout_s:
            self.state, self.t_enter = TRANSPARENT, t
        tau = 0.0
        if self.state == EARLY:
            tau = -c.brake_nms_per_rad * theta_dot
        elif self.state == SWING:
            tau = c.kp_nm_per_rad * (c.target_rad - theta) - c.kd_nms_per_rad * theta_dot
        return max(tau, 0.0)
