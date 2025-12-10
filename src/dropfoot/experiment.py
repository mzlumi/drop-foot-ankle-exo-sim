"""Device conditions of the experiment (Part F) and the metrics that need the device channels.

Scenarios for scenarios/generated/ are written from
:func:`dropfoot.scenarios.device_scenario` with the device properties built
here, so that every condition differs only in those properties:

* ``none``: the device is worn but applies no torque; the gyroscope and the
  detector still run, so the drop-foot runs without a device can be scored
  by the detector too;
* ``passive``: a rotational spring ``tau = -k (theta - theta0)``, no actuator;
* ``active``: the phase-based controller of :mod:`dropfoot.fsm`, through the
  fitted actuator response (Part E) and clipped to the torque limit of Part C.

Device metrics per stride, from the logged ``dev.power`` (device torque times
ankle velocity, W, positive when the device does work on the ankle):

* ``device_positive_work_j``: integral of max(P, 0) over the stride, the
  mechanical energy the device delivers per stride;
* ``device_negative_work_j``: integral of min(P, 0), the energy it absorbs;
* ``device_peak_power_w``: maximum of P over the stride;
* ``device_peak_torque_nm``: maximum of the applied torque;
* ``peak_pushoff_power_w``: peak of ``ankle_angle_r.power + dev.power`` in
  stance, the push-off power of the hypothesis (muscles plus device).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from dropfoot.fsm import FSMConfig
from dropfoot.gait import Stride
from dropfoot.io import Storage
from dropfoot.scenarios import device_scenario, strength_tag, write_generated
from dropfoot.sensor import GyroConfig


@dataclass(frozen=True)
class ActuatorFit:
    delay_s: float
    time_constant_s: float
    limit_nm: float

    def props(self) -> dict[str, float]:
        return {"act_delay_s": self.delay_s, "act_time_constant_s": self.time_constant_s, "limit_nm": self.limit_nm}


def imu_props(gyro: GyroConfig = GyroConfig()) -> dict[str, float]:
    """Gyroscope settings under the names device.lua reads."""
    return {"rate_hz": gyro.rate_hz, "noise_dps": gyro.noise_dps, "bias_dps": gyro.bias_dps, "imu_delay_s": gyro.delay_s, "seed": gyro.seed}


def none_props(gyro: GyroConfig = GyroConfig()) -> dict:
    return {"mode": "none", **imu_props(gyro)}


def passive_props(k: float, theta0: float = 0.0, gyro: GyroConfig = GyroConfig()) -> dict:
    return {"mode": "passive", "k_nm_per_rad": k, "theta0_rad": theta0, **imu_props(gyro)}


def active_props(fsm: FSMConfig, actuator: ActuatorFit, gyro: GyroConfig = GyroConfig()) -> dict:
    return {"mode": "active", **fsm.lua_properties(), **actuator.props(), **imu_props(gyro)}


def write_condition(
    name: str, title: str, props: dict, factor: float, init_par: str, measure: str = "MeasureGait12", extra: str = ""
) -> Path:
    """Write scenarios/generated/<name>.scone; ``init_par`` is relative to the repository root."""
    return write_generated(
        name,
        device_scenario(
            title,
            name,
            props,
            factor=factor,
            init_file=f"../../{init_par}",
            measure=measure,
            extra=extra,
        ),
    )


def condition_name(device: str, factor: float, setting: str = "", suffix: str = "") -> str:
    parts = [device, strength_tag(factor)] + ([setting] if setting else []) + ([suffix] if suffix else [])
    return "_".join(parts)


def _integral(t: np.ndarray, y: np.ndarray) -> float:
    return float(np.sum(0.5 * (y[1:] + y[:-1]) * np.diff(t)))


def device_stride_metrics(sto: Storage, stride: Stride) -> dict[str, float]:
    m = (sto.time >= stride.heel_strike) & (sto.time <= stride.next_heel_strike)
    t = sto.time[m]
    ankle_power = sto["ankle_angle_r.power"]
    out: dict[str, float] = {}
    if sto.has("dev.power"):
        p = sto["dev.power"][m]
        out["device_positive_work_j"] = _integral(t, np.maximum(p, 0.0))
        out["device_negative_work_j"] = _integral(t, np.minimum(p, 0.0))
        out["device_peak_power_w"] = float(p.max())
        out["device_peak_torque_nm"] = float(sto["dev.torque"][m].max())
        total = ankle_power + sto["dev.power"]
    else:
        out.update({k: 0.0 for k in ("device_positive_work_j", "device_negative_work_j", "device_peak_power_w", "device_peak_torque_nm")})
        total = ankle_power
    s = (sto.time >= stride.heel_strike) & (sto.time <= stride.toe_off)
    out["peak_pushoff_power_w"] = float(total[s].max())
    return out


def device_metrics(sto: Storage, strides: list[Stride]) -> dict[str, float]:
    """Mean over strides of :func:`device_stride_metrics`."""
    rows = [device_stride_metrics(sto, st) for st in strides]
    if not rows:
        return {}
    return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}


def judge(value: float, threshold: float, sd: float, above: bool) -> str:
    """``value >= threshold`` (``above``) or ``value < threshold``; a miss smaller than ``sd`` is inconclusive."""
    holds = value >= threshold if above else value < threshold
    if holds:
        return "holds"
    return "inconclusive" if abs(value - threshold) < sd else "fails"


def select_setting(df: pd.DataFrame, device: str, healthy_toe: float, metric: str = "min_toe_clearance_mm") -> dict:
    """Tuning rule of the hypothesis on frozen runs (columns device, setting, value, seed, walks, ``metric``).

    Among the settings with the most seeds walking (all of them, normally),
    the one whose mean ``metric`` over walking seeds is closest to
    ``healthy_toe``, the lower ``value`` on a tie.
    """
    d = df[df.device == device]
    g = d.groupby("value").agg(walking=("walks", "sum"), runs=("walks", "size")).reset_index()
    g["toe"] = g.value.map(d[d.walks].groupby("value")[metric].mean())
    g["distance_mm"] = (g.toe - healthy_toe).abs()
    top = g.walking.max()
    pool = g[g.walking == top].sort_values(["distance_mm", "value"])
    best = pool.iloc[0]
    return {
        "device": device,
        "value": float(best.value),
        "setting": d[d.value == best.value].setting.iloc[0],
        "all_seeds_walk": bool(top == g.runs.max()),
        "seeds_walking": int(top),
        "toe_clearance_mm": float(best.toe),
        "distance_from_healthy_mm": float(best.distance_mm),
        "candidates": g.to_dict(orient="records"),
    }
