"""Model gait curves in the units of the normative data, and curve agreement measures.

The model's right-leg strides are time-normalized (0 to 100% from heel strike
to heel strike, :mod:`dropfoot.gait`) and converted to the variables and
units of ``results/normative`` (written by :mod:`dropfoot.camargo`):

=============== ====================================== ==========
variable        model channel                           unit
=============== ====================================== ==========
hip_flexion     ``hip_flexion_r``                       deg
knee_flexion    ``-knee_angle_r``                       deg
ankle_angle     ``ankle_angle_r``                       deg
ankle_moment    ``ankle_angle_r.moment / mass``         N m/kg
vertical_grf    ``leg1_r.grf_norm_y``                   BW
shank_gyro      ``tibia_r.ang_vel_z``                   deg/s
=============== ====================================== ==========

``ankle_angle_r.moment`` is the sum of the muscle moments about the ankle,
which in a steady simulated stride balances the inverse dynamics moment of
the measured data. Agreement is the RMSE between the two mean curves, the
Pearson correlation of their shapes, and the RMSE after removing the
difference of their means (offset). The last one separates a constant offset,
for example a different neutral ankle angle between the marker-based model of
the data and the simulation model, from a difference in shape.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dropfoot.gait import PERCENT, Stride, find_strides, normalize_strides
from dropfoot.io import Storage

MODEL_MASS_KG = 75.1646  # sum of body masses in Human0914.osim

CHANNELS = {
    "hip_flexion": ("hip_flexion_r", np.degrees(1.0)),
    "knee_flexion": ("knee_angle_r", -np.degrees(1.0)),
    "ankle_angle": ("ankle_angle_r", np.degrees(1.0)),
    "ankle_moment": ("ankle_angle_r.moment", 1.0 / MODEL_MASS_KG),
    "vertical_grf": ("leg1_r.grf_norm_y", 1.0),
    "shank_gyro": ("tibia_r.ang_vel_z", np.degrees(1.0)),
}
UNITS = {
    "hip_flexion": "deg",
    "knee_flexion": "deg",
    "ankle_angle": "deg",
    "ankle_moment": "N m/kg",
    "vertical_grf": "BW",
    "shank_gyro": "deg/s",
}


def model_curves(sto: Storage, strides: list[Stride] | None = None, skip_first: int = 2) -> dict[str, np.ndarray]:
    """Per-stride right-leg curves (strides x 101) of every variable in :data:`CHANNELS`."""
    strides = strides if strides is not None else find_strides(sto, "r", skip_first=skip_first)
    return {name: normalize_strides(sto, label, strides, scale=scale) for name, (label, scale) in CHANNELS.items()}


def mean_curves(curves: dict[str, np.ndarray]) -> pd.DataFrame:
    """Mean over strides of each variable, one column per variable, indexed by percent."""
    return pd.DataFrame({k: v.mean(axis=0) for k, v in curves.items()}, index=pd.Index(PERCENT, name="percent"))


def agreement(model: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    """RMSE, Pearson r, mean offset (model minus reference) and RMSE without the offset."""
    model, reference = np.asarray(model, float), np.asarray(reference, float)
    diff = model - reference
    offset = float(diff.mean())
    return {
        "rmse": float(np.sqrt(np.mean(diff**2))),
        "r": float(np.corrcoef(model, reference)[0, 1]),
        "offset": offset,
        "rmse_no_offset": float(np.sqrt(np.mean((diff - offset) ** 2))),
    }
