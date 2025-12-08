"""Synthetic SCONE-like storages with known gait events, shared by the tests."""

from __future__ import annotations

import numpy as np

from dropfoot.io import Storage


def contact_force(t: np.ndarray, hs: list[float], to: list[float], peak: float = 1.0, ramp: float = 0.05) -> np.ndarray:
    """Trapezoid contact force rising linearly from 0 at each ``hs`` and falling to 0 at each ``to``.

    With ``peak = 1`` the 5% body-weight crossings are at ``hs[i] + 0.05 * ramp``
    and ``to[i] - 0.05 * ramp``.
    """
    f = np.zeros_like(t)
    for a, b in zip(hs, to):
        up = np.clip((t - a) / ramp, 0, 1)
        down = np.clip((b - t) / ramp, 0, 1)
        f = np.maximum(f, peak * np.minimum(up, down) * ((t >= a) & (t <= b)))
    return f


def gait_storage(
    duration: float = 6.0,
    stride: float = 1.1,
    stance_fraction: float = 0.6,
    offset_r: float = 0.3,
    dt: float = 0.005,
    ramp: float = 0.05,
    extra: dict[str, np.ndarray] | None = None,
) -> tuple[Storage, dict[str, list[float]]]:
    """Storage with both legs' contact forces and centres of pressure.

    Returns the storage and the true 5% body-weight event times per side.
    """
    t = np.arange(0.0, duration + 1e-9, dt)
    labels, cols, events = [], [], {}
    for side, leg, off in (("l", "leg0_l", offset_r + stride / 2), ("r", "leg1_r", offset_r)):
        hs = list(np.arange(off, duration, stride))
        to = [h + stance_fraction * stride for h in hs]
        f = contact_force(t, hs, to, ramp=ramp)
        labels += [f"{leg}.grf_norm_y", f"{leg}.cop_x", f"{leg}.cop_y", f"{leg}.cop_z"]
        # the centre of pressure moves 1.3 m per stride
        cols += [f, 1.3 * t / stride, np.zeros_like(t), np.zeros_like(t)]
        events[f"hs_{side}"] = [h + 0.05 * ramp for h in hs if h + 0.05 * ramp < t[-1]]
        events[f"to_{side}"] = [b - 0.05 * ramp for b in to if b - 0.05 * ramp < t[-1]]
    for k, v in (extra or {}).items():
        labels.append(k)
        cols.append(v)
    return Storage(labels=tuple(labels), time=t, data=np.column_stack(cols)), events
