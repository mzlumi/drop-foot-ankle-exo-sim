"""Clinical gait metrics for drop foot (assignment Part B3).

Signs follow docs/conventions.md: ankle dorsiflexion positive, hip flexion
positive, ``knee_angle`` negative in flexion (reported here as positive knee
flexion). Angles in degrees, velocities in deg/s, lengths in mm or m as named.

Every per-stride metric is computed on one stride (heel strike to next heel
strike of the same foot, events from :mod:`dropfoot.gait`) and then summarized
as mean and SD over strides. The definitions:

``min_toe_clearance_mm``
    Minimum height (y, mm) of the ``toes`` body origin, the metatarsophalangeal
    joint, during **mid-swing**, taken as the middle half of swing (25 to 75%
    of the time from toe-off to the next heel strike). The window excludes the
    instants near toe-off and heel strike where the forefoot is at or near the
    ground. The origin of ``toes`` sits above the ground even in stance (about
    20 to 30 mm), so the number is a height of that point, not a gap between
    the shoe and the floor.

``ankle_at_ic_deg``
    Ankle angle at heel strike (initial contact), interpolated at the event
    time. Negative values mean the foot lands plantarflexed (toe first).

``peak_swing_df_deg``
    Maximum ankle angle during swing (toe-off to next heel strike). With drop
    foot it is low or negative: the foot is never lifted.

``foot_slap_index_dps``
    Peak plantarflexion angular velocity, ``max(-d ankle_angle / dt)``, in the
    first 15% of the gait cycle after heel strike, in deg/s. A large value
    means the foot falls onto the ground without eccentric control by
    tibialis anterior. It is compared with the model's own healthy value.

``peak_hip_flexion_swing_deg``, ``peak_knee_flexion_swing_deg``
    Peak hip flexion and peak knee flexion (``-knee_angle``) during swing.
    *Steppage* is the increase of these over the healthy values, computed with
    :func:`change_from`.

``peak_ankle_power_w``
    Peak positive ankle muscle power (``ankle_angle.power``, W) during stance,
    the push-off power used by the hypothesis.

Whole-trial metrics:

``step_length_si_pct``, ``stance_time_si_pct``
    Symmetry indices ``SI = 100 * (X_r - X_l) / (0.5 * (X_r + X_l))``
    (Robinson et al. 1987); 0 is symmetric, positive means the right (affected)
    side is larger. Right step length is the forward distance from the left to
    the right calcaneus origin at right heel strike, and vice versa.

``cost_of_transport``
    The value of SCONE's ``EffortMeasure`` with ``measure_type = Wang2012`` and
    ``use_cost_of_transport = 1``: Wang et al. (2012) metabolic energy over the
    whole simulation divided by body mass and distance walked, J/(kg m). It is
    read from the objective breakdown printed by ``sconecmd -e``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scone_gait.results import parse_report

from dropfoot.gait import Stride, find_strides
from dropfoot.io import Storage

MID_SWING = (0.25, 0.75)
FOOT_SLAP_WINDOW = 0.15  # fraction of the gait cycle after heel strike

PER_STRIDE = [
    "min_toe_clearance_mm",
    "ankle_at_ic_deg",
    "peak_swing_df_deg",
    "foot_slap_index_dps",
    "peak_hip_flexion_swing_deg",
    "peak_knee_flexion_swing_deg",
    "peak_ankle_power_w",
    "stride_time_s",
    "stance_pct",
    "stride_length_m",
]


def _window(sto: Storage, t0: float, t1: float) -> np.ndarray:
    return (sto.time >= t0) & (sto.time <= t1)


def _interp(sto: Storage, label: str, t: float) -> float:
    return float(np.interp(t, sto.time, sto[label]))


def _max_in(sto: Storage, values: np.ndarray, t0: float, t1: float) -> float:
    """Maximum of ``values`` on [t0, t1], including the interpolated end points."""
    m = _window(sto, t0, t1)
    ends = np.interp([t0, t1], sto.time, values)
    return float(np.max(np.concatenate([values[m], ends])))


def stride_metrics(sto: Storage, stride: Stride) -> dict[str, float]:
    """All per-stride metrics of one stride (see the module docstring)."""
    s = stride.side
    hs, to, nxt = stride.heel_strike, stride.toe_off, stride.next_heel_strike
    swing = nxt - to
    ankle = np.degrees(sto[f"ankle_angle_{s}"])
    ankle_vel = np.degrees(sto[f"ankle_angle_{s}_u"])
    hip = np.degrees(sto[f"hip_flexion_{s}"])
    knee_flex = -np.degrees(sto[f"knee_angle_{s}"])
    toes_y = sto[f"toes_{s}.pos_y"]

    ms0, ms1 = to + MID_SWING[0] * swing, to + MID_SWING[1] * swing
    out = {
        "min_toe_clearance_mm": -1000.0 * _max_in(sto, -toes_y, ms0, ms1),
        "ankle_at_ic_deg": float(np.interp(hs, sto.time, ankle)),
        "peak_swing_df_deg": _max_in(sto, ankle, to, nxt),
        "foot_slap_index_dps": _max_in(sto, -ankle_vel, hs, hs + FOOT_SLAP_WINDOW * stride.duration),
        "peak_hip_flexion_swing_deg": _max_in(sto, hip, to, nxt),
        "peak_knee_flexion_swing_deg": _max_in(sto, knee_flex, to, nxt),
        "stride_time_s": stride.duration,
        "stance_pct": 100.0 * stride.stance_fraction,
        "stride_length_m": stride.length,
    }
    power = f"ankle_angle_{s}.power"
    out["peak_ankle_power_w"] = _max_in(sto, sto[power], hs, to) if sto.has(power) else float("nan")
    return out


def stride_table(sto: Storage, side: str = "r", skip_first: int = 2, skip_last: int = 0) -> pd.DataFrame:
    """One row of :func:`stride_metrics` per stride of ``side``, after the start-up strides."""
    strides = find_strides(sto, side, skip_first=skip_first, skip_last=skip_last)
    rows = [{"heel_strike_s": st.heel_strike, **stride_metrics(sto, st)} for st in strides]
    return pd.DataFrame(rows, columns=["heel_strike_s", *PER_STRIDE])


def symmetry_index(right: float, left: float) -> float:
    """``100 * (right - left) / mean(right, left)``, in percent."""
    return float(100.0 * (right - left) / (0.5 * (right + left)))


def step_lengths(sto: Storage, strides: list[Stride]) -> dict[str, float]:
    """Mean step length (m) per side: forward distance between the calcanei at that side's heel strike."""
    out = {}
    for side, other in (("r", "l"), ("l", "r")):
        steps = [
            _interp(sto, f"calcn_{side}.pos_x", st.heel_strike) - _interp(sto, f"calcn_{other}.pos_x", st.heel_strike)
            for st in strides
            if st.side == side
        ]
        out[side] = float(np.mean(steps)) if steps else float("nan")
    return out


def asymmetry(sto: Storage, skip_first: int = 2) -> dict[str, float]:
    """Step length and stance time symmetry indices (right versus left), in percent."""
    strides = find_strides(sto, skip_first=skip_first)
    steps = step_lengths(sto, strides)
    stance = {
        side: float(np.mean([st.stance_time for st in strides if st.side == side])) for side in ("r", "l")
    }
    return {
        "step_length_r_m": steps["r"],
        "step_length_l_m": steps["l"],
        "step_length_si_pct": symmetry_index(steps["r"], steps["l"]),
        "stance_time_r_s": stance["r"],
        "stance_time_l_s": stance["l"],
        "stance_time_si_pct": symmetry_index(stance["r"], stance["l"]),
    }


_WEIGHTED = re.compile(r"^\s*([-+\d.eE]+)\s*\*\s*([-+\d.eE]+)")


def cost_of_transport(report_text: str) -> float:
    """Cost of transport from the ``Effort`` entry of an ``sconecmd -e`` breakdown.

    The entry reads ``Effort = 0.548 <- 0.1 * 5.48``: the measure value before
    weighting (5.48 J/(kg m)) is the cost of transport.
    """
    effort = parse_report(report_text)["Effort"]
    m = _WEIGHTED.match(effort.detail)
    if not m:
        raise ValueError(f"cannot read the unweighted effort from {effort.detail!r}")
    return float(m.group(2))


@dataclass(frozen=True)
class GaitSummary:
    """Mean and SD over strides of every per-stride metric, plus whole-trial metrics."""

    strides: pd.DataFrame
    trial: dict[str, float]

    @property
    def n_strides(self) -> int:
        return len(self.strides)

    def mean(self) -> pd.Series:
        return self.strides[PER_STRIDE].mean()

    def sd(self) -> pd.Series:
        return self.strides[PER_STRIDE].std(ddof=1)

    def as_dict(self) -> dict[str, float]:
        out: dict[str, float] = {"n_strides": float(self.n_strides)}
        for k, v in self.mean().items():
            out[k] = float(v)
        for k, v in self.sd().items():
            out[f"{k}_sd"] = float(v)
        out.update(self.trial)
        return out


def gait_summary(sto: Storage, report_text: str | None = None, side: str = "r", skip_first: int = 2) -> GaitSummary:
    """Summarize a simulation: per-stride metrics of ``side``, asymmetry, speed and cost of transport."""
    table = stride_table(sto, side, skip_first=skip_first)
    trial = asymmetry(sto, skip_first=skip_first)
    strides = find_strides(sto, side, skip_first=skip_first)
    if strides:
        x = [_interp(sto, "pelvis_tx", st.heel_strike) for st in strides]
        t = [st.heel_strike for st in strides]
        trial["speed_mps"] = float((x[-1] - x[0]) / (t[-1] - t[0])) if len(strides) > 1 else float("nan")
    trial["cost_of_transport"] = cost_of_transport(report_text) if report_text else float("nan")
    trial["duration_s"] = float(sto.time[-1])
    return GaitSummary(table, trial)


def change_from(values: dict[str, float], reference: dict[str, float], keys: list[str]) -> dict[str, float]:
    """``values[k] - reference[k]`` for each key, named ``delta_<k>`` (steppage and similar)."""
    return {f"delta_{k}": values[k] - reference[k] for k in keys}
