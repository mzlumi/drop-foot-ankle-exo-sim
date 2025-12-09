"""Python twin of the simulated shank gyroscope in scenarios/lua/gyro.lua (Part D1).

Units are deg/s and s. The sign is that of ``tibia_r.ang_vel_z``: positive
when the shank rotates forward.

Model of the measured signal, for the true sagittal angular velocity w(t):

* sampling at ``rate_hz``: sample k is taken at t_k = k / rate_hz, at the
  first control step with t >= t_k, so the true value is the one at that step;
* y_k = w(t_k) + bias + noise * n_k, with n_k a standard normal deviate;
* transport delay: y_k becomes available at t_k + delay and is held until
  y_(k+1) becomes available (zero-order hold).

The deviates come from the Park-Miller minimal standard generator
(x <- 16807 x mod (2^31 - 1)), whose products stay below 2^53 and are exact
in double precision in both languages, followed by the Box-Muller transform
(one deviate from each pair of uniforms). The same seed therefore gives the
same noise in Lua and in Python, up to the last bit of the C library's
``log`` and ``cos``.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import numpy as np

MODULUS = 2147483647
MULTIPLIER = 16807
EPS = 1e-9


@dataclass(frozen=True)
class GyroConfig:
    rate_hz: float = 100.0
    noise_dps: float = 0.5
    bias_dps: float = 2.0
    delay_s: float = 0.015
    seed: int = 1


class ParkMiller:
    def __init__(self, seed: int):
        self.state = int(seed) % MODULUS or 1

    def uniform(self) -> float:
        self.state = (MULTIPLIER * self.state) % MODULUS
        return self.state / MODULUS

    def normal(self) -> float:
        u1 = self.uniform()
        u2 = self.uniform()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


class Gyro:
    """Step-by-step gyroscope, same state machine as gyro.lua."""

    def __init__(self, cfg: GyroConfig = GyroConfig()):
        self.cfg = cfg
        self.period = 1.0 / cfg.rate_hz
        self.rng = ParkMiller(cfg.seed)
        self.k = -1
        self.queue: deque[tuple[float, float, int]] = deque()
        self.output = 0.0
        self.output_k = -1
        self.sample_true = 0.0

    def update(self, t: float, w: float) -> bool:
        """Advance to time ``t`` with true value ``w``; True when a new sample became available."""
        while (self.k + 1) * self.period <= t + EPS:
            self.k += 1
            self.sample_true = w
            y = w + self.cfg.bias_dps + self.cfg.noise_dps * self.rng.normal()
            self.queue.append((self.k * self.period + self.cfg.delay_s, y, self.k))
        fresh = False
        while self.queue and self.queue[0][0] <= t + EPS:
            _, self.output, self.output_k = self.queue.popleft()
            fresh = True
        return fresh


@dataclass(frozen=True)
class GyroTrace:
    t: np.ndarray
    measured: np.ndarray  # held output at every step
    output_k: np.ndarray
    sample_t: np.ndarray  # sample instants t_k
    sample_available: np.ndarray  # t_k + delay
    sample_value: np.ndarray  # y_k


def simulate(t: np.ndarray, w: np.ndarray, cfg: GyroConfig = GyroConfig()) -> GyroTrace:
    """Run the gyroscope over a true signal sampled at the control steps ``t``."""
    g = Gyro(cfg)
    out = np.empty(len(t))
    ks = np.empty(len(t), dtype=int)
    samples: dict[int, float] = {}
    for i, (ti, wi) in enumerate(zip(t, w)):
        if g.update(float(ti), float(wi)):
            samples[g.output_k] = g.output
        out[i] = g.output
        ks[i] = g.output_k
    k = np.array(sorted(samples), dtype=int)
    return GyroTrace(
        t=np.asarray(t, float),
        measured=out,
        output_k=ks,
        sample_t=k * g.period,
        sample_available=k * g.period + cfg.delay_s,
        sample_value=np.array([samples[i] for i in k]),
    )


def noise_sequence(seed: int, n: int) -> np.ndarray:
    rng = ParkMiller(seed)
    return np.array([rng.normal() for _ in range(n)])
