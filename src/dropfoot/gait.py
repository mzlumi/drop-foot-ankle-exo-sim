"""Stride segmentation from foot contact force, and time normalization.

Conventions (docs/conventions.md): heel strike is the instant the vertical
ground reaction force of a foot rises through ``threshold`` body weights
(default 5%), toe-off the instant it falls through it. A stride runs from one
heel strike to the next heel strike of the same foot, 0 to 100%.

The cycle structure (which contacts count, how short bumps are merged) comes
from ``scone_gait.cycles.extract_gait_cycles`` in the companion repository,
which follows SCONE Studio. That function places events on the first sample
past the threshold; here every event is moved to the linearly interpolated
crossing between that sample and the one before it, so event times are not
quantized to the 5 ms output step. This matters when the timing error of the
IMU event detector is measured against these events.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scone_gait.cycles import LEGS, GaitCycle, extract_gait_cycles
from scone_gait.storage import Storage

HS_THRESHOLD = 0.05  # body weights


def crossing_time(time: np.ndarray, signal: np.ndarray, idx: int, level: float) -> float:
    """Interpolated time at which ``signal`` crosses ``level`` between samples idx-1 and idx."""
    if idx <= 0:
        return float(time[0])
    y0, y1 = signal[idx - 1], signal[idx]
    if y1 == y0:
        return float(time[idx])
    frac = float(np.clip((level - y0) / (y1 - y0), 0.0, 1.0))
    return float(time[idx - 1] + frac * (time[idx] - time[idx - 1]))


@dataclass(frozen=True)
class Stride:
    """One stride of one leg with interpolated event times (s)."""

    side: str
    heel_strike: float
    toe_off: float
    next_heel_strike: float
    length: float  # m, between centres of pressure at the two heel strikes

    @property
    def duration(self) -> float:
        return self.next_heel_strike - self.heel_strike

    @property
    def stance_time(self) -> float:
        return self.toe_off - self.heel_strike

    @property
    def swing_time(self) -> float:
        return self.next_heel_strike - self.toe_off

    @property
    def stance_fraction(self) -> float:
        return self.stance_time / self.duration

    def percent(self, t: np.ndarray | float) -> np.ndarray:
        """Gait cycle percentage of time(s) t."""
        return 100.0 * (np.asarray(t) - self.heel_strike) / self.duration


def _refine(sto: Storage, cycle: GaitCycle, threshold: float) -> Stride:
    force = sto[f"{LEGS[cycle.side]}.grf_norm_y"]
    t = sto.time

    def at(event_time: float) -> float:
        idx = int(np.searchsorted(t, event_time - 1e-9))
        return crossing_time(t, force, idx, threshold)

    return Stride(cycle.side, at(cycle.begin), at(cycle.swing), at(cycle.end), cycle.length)


def find_strides(
    sto: Storage,
    side: str | None = None,
    threshold: float = HS_THRESHOLD,
    min_stance: float = 0.1,
    skip_first: int = 0,
    skip_last: int = 0,
) -> list[Stride]:
    """Strides of one side (``'l'`` or ``'r'``) or both, sorted by heel strike time.

    ``skip_first`` and ``skip_last`` drop strides per side at the start (initial
    transient of the simulation) and at the end.
    """
    cycles = extract_gait_cycles(sto, force_threshold=threshold, min_stance_duration=min_stance)
    out: list[Stride] = []
    for s in ("l", "r") if side is None else (side,):
        mine = [_refine(sto, c, threshold) for c in cycles if c.side == s]
        out += mine[skip_first : len(mine) - skip_last if skip_last else None]
    return sorted(out, key=lambda st: st.heel_strike)


def contact_events(
    time: np.ndarray, force: np.ndarray, threshold: float = HS_THRESHOLD
) -> tuple[np.ndarray, np.ndarray]:
    """All interpolated rising (heel strike) and falling (toe-off) crossings of one force trace.

    No debouncing: use :func:`find_strides` for gait cycles. This is the raw
    ground truth used to score the event detector.
    """
    above = force > threshold
    rise = np.nonzero(~above[:-1] & above[1:])[0] + 1
    fall = np.nonzero(above[:-1] & ~above[1:])[0] + 1
    hs = np.array([crossing_time(time, force, i, threshold) for i in rise])
    to = np.array([crossing_time(time, force, i, threshold) for i in fall])
    return hs, to


PERCENT = np.linspace(0.0, 100.0, 101)


def normalize(time: np.ndarray, signal: np.ndarray, stride: Stride, percent: np.ndarray = PERCENT) -> np.ndarray:
    """Resample ``signal`` over one stride at the given gait cycle percentages."""
    t = stride.heel_strike + percent / 100.0 * stride.duration
    return np.interp(t, time, signal)


def normalize_strides(
    sto: Storage, label: str, strides: list[Stride], percent: np.ndarray = PERCENT, scale: float = 1.0
) -> np.ndarray:
    """One row per stride of channel ``label`` resampled at ``percent`` (times ``scale``)."""
    if not strides:
        return np.empty((0, len(percent)))
    return np.vstack([scale * normalize(sto.time, sto[label], s, percent) for s in strides])


def side_label(template: str, side: str) -> str:
    """Fill a channel template: ``side_label('ankle_angle_{s}', 'r') == 'ankle_angle_r'``.

    ``{leg}`` expands to SCONE's leg name (``leg1_r`` or ``leg0_l``).
    """
    return template.format(s=side, leg=LEGS[side])
