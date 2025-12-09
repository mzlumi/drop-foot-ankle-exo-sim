"""Python twin of the exoskeleton script (scenarios/lua/device.lua, actuator.lua).

Sign convention: the device torque is positive when it dorsiflexes the foot.
In SCONE it is applied as a pair of external moments about z, +tau on
``talus_r`` and -tau on ``tibia_r``, so it acts only across the ankle and adds
no net moment to the body. External moments persist between steps (OpenSim 3
adds each call to the body's applied moment), so the script keeps the moment
it has applied and adds only the change; :class:`MomentBook` is that
bookkeeping.

The actuator's closed-loop torque response (fitted in Part E) is a pure delay
followed by a first-order lag, after clipping the command to the torque limit
of Part C; :class:`ActuatorLag` reproduces actuator.lua step by step.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

EPS = 1e-9


class ActuatorLag:
    def __init__(self, delay_s: float = 0.0, time_constant_s: float = 0.0, limit_nm: float = 1e9):
        self.delay = delay_s
        self.time_constant = time_constant_s
        self.limit = limit_nm
        self.queue: deque[tuple[float, float]] = deque()
        self.delayed = 0.0
        self.torque = 0.0
        self.t_prev: float | None = None

    def clip(self, u: float) -> float:
        return max(-self.limit, min(self.limit, u))

    def update(self, t: float, u: float) -> float:
        """Advance to ``t`` with command ``u``. The lag integrates over the step
        that just ended with the delayed command held during it (exact for a
        zero-order hold); then the command due at ``t`` is taken from the delay line."""
        if self.time_constant > 0 and self.t_prev is not None:
            dt = t - self.t_prev
            self.torque = self.torque + (self.delayed - self.torque) * (1.0 - math.exp(-dt / self.time_constant))
        self.queue.append((t + self.delay, self.clip(u)))
        while self.queue and self.queue[0][0] <= t + EPS:
            self.delayed = self.queue.popleft()[1]
        if self.time_constant <= 0:
            self.torque = self.delayed
        self.t_prev = t
        return self.torque


@dataclass
class MomentBook:
    """Moments applied so far to talus_r and tibia_r, changed only by increments."""

    talus: float = 0.0
    tibia: float = 0.0
    applied: float = 0.0

    def apply(self, tau: float) -> tuple[float, float]:
        """Increments to add to (talus_r, tibia_r) so that the pair becomes (+tau, -tau)."""
        change = tau - self.applied
        if change == 0.0:
            return 0.0, 0.0
        self.talus += change
        self.tibia -= change
        self.applied = tau
        return change, -change
