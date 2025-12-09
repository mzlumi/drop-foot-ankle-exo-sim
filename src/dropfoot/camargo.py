"""Loader and normative curves for the Camargo et al. (2021) dataset.

J. Camargo, A. Ramanathan, W. Flanagan and A. Young, "A comprehensive,
open-source dataset of lower limb biomechanics in multiple conditions of
stairs, ramps, and level-ground ambulation and transitions," Journal of
Biomechanics 119, 110320, 2021. https://doi.org/10.1016/j.jbiomech.2021.110320
Data: CC BY 4.0. Raw files stay in data/raw/camargo/ and are never committed.

File layout (confirmed on the downloaded subjects, see data/README.md)::

    <subject>/<date>/treadmill/<sensor>/treadmill_<nn>_01.mat

Each file holds one MATLAB ``table`` object (read with ``mat-io``) with a
``Header`` column of time stamps in seconds. Sensors used here:

* ``conditions``: variable ``speed`` with columns ``Header, Speed`` (m/s,
  1000 Hz). One treadmill trial holds several speeds.
* ``ik``: OpenSim joint angles in degrees (200 Hz). ``knee_angle_r`` is
  negative in flexion and ``ankle_angle_r`` positive in dorsiflexion, the
  same signs as the SCONE model.
* ``id``: OpenSim inverse dynamics, ``ankle_angle_r_moment`` in N m,
  positive dorsiflexing (200 Hz).
* ``imu``: ``shank_Gyro_Y`` is the sagittal shank angular velocity in rad/s
  (200 Hz). Its sign and its time offset differ between subjects, so
  :func:`align_gyro` calibrates both against the shank angular velocity from
  ``ik`` before use (see that function).
* ``fp``: treadmill belt forces in N; ``Treadmill_R_vy`` is the vertical force
  under the right foot (1000 Hz).
* ``gcRight``: the dataset's own gait phase (``HeelStrike``, ``ToeOff``, in %),
  kept only as a cross-check.

Events here are recomputed from the belt force with the same definition as in
the simulation: the right vertical force crossing 5% of body weight.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from dropfoot.gait import HS_THRESHOLD, PERCENT, Stride, contact_events, merge_contacts

G = 9.81
CITATION = (
    "Camargo J, Ramanathan A, Flanagan W, Young A (2021). A comprehensive, open-source dataset of lower limb "
    "biomechanics in multiple conditions of stairs, ramps, and level-ground ambulation and transitions. "
    "Journal of Biomechanics 119:110320. doi:10.1016/j.jbiomech.2021.110320. Data CC BY 4.0."
)

# normative variables: name -> (sensor, column, scale, unit)
VARIABLES = {
    "hip_flexion": ("ik", "hip_flexion_r", 1.0, "deg"),
    "knee_flexion": ("ik", "knee_angle_r", -1.0, "deg"),
    "ankle_angle": ("ik", "ankle_angle_r", 1.0, "deg"),
    "ankle_moment": ("id", "ankle_angle_r_moment", 1.0, "N m/kg"),  # divided by mass below
    "vertical_grf": ("fp", "Treadmill_R_vy", 1.0, "BW"),  # divided by weight below
    "shank_gyro": ("imu", "shank_gyro", float(np.degrees(1.0)), "deg/s"),  # after align_gyro
}


def load_table(path: str | Path, variable: str | None = None) -> pd.DataFrame:
    """Read one dataset ``.mat`` file into a DataFrame (the ``data`` table unless ``variable`` is given)."""
    import matio

    contents = matio.load_from_mat(str(path))
    key = variable or ("data" if "data" in contents else next(k for k in contents if not k.startswith("_")))
    table = contents[key]
    if not isinstance(table, pd.DataFrame):
        raise TypeError(f"{path}: {key!r} is not a table")
    return table


def subject_info(path: str | Path) -> pd.DataFrame:
    """``SubjectInfo.mat`` as a DataFrame indexed by subject, with mass in kg."""
    df = load_table(path).copy()
    for col in ("Subject", "Gender"):
        df[col] = [str(np.ravel(v)[0]) if not isinstance(v, str) else v for v in df[col]]
    return df.set_index("Subject")


def speed_windows(speed: pd.DataFrame, target: float, tol: float = 0.01, settle: float = 5.0) -> list[tuple[float, float]]:
    """Time windows (s) where the treadmill runs at ``target`` m/s, dropping ``settle`` s after each change."""
    t = speed["Header"].to_numpy()
    on = np.abs(speed["Speed"].to_numpy() - target) <= tol
    windows = []
    edges = np.flatnonzero(np.diff(np.concatenate([[0], on.astype(int), [0]])))
    for a, b in zip(edges[::2], edges[1::2]):
        t0, t1 = t[a] + settle, t[b - 1]
        if t1 > t0:
            windows.append((float(t0), float(t1)))
    return windows


def median_smooth(t: np.ndarray, y: np.ndarray, width: float) -> np.ndarray:
    """Running median over ``width`` s: removes short spikes without moving step edges."""
    from scipy.ndimage import median_filter

    n = max(1, int(round(width / np.median(np.diff(t))))) | 1
    return median_filter(y, size=n, mode="nearest")


def force_events(
    fp: pd.DataFrame,
    mass: float,
    column: str = "Treadmill_R_vy",
    threshold: float = HS_THRESHOLD,
    width: float = 0.025,
):
    """Heel strikes and toe-offs (s) from a belt force crossing ``threshold`` body weights.

    In swing the belt force has spikes of 3 to 5% body weight that would cross
    the threshold for light subjects. A running median over ``width`` s removes
    them (a linear low-pass would also smear the loading edge and move heel
    strike earlier), then the crossings are debounced with
    :func:`dropfoot.gait.merge_contacts`.
    """
    t = fp["Header"].to_numpy()
    f = median_smooth(t, fp[column].to_numpy(), width) / (mass * G)
    return merge_contacts(*contact_events(t, f, threshold))


def strides_from_events(
    hs: np.ndarray,
    to: np.ndarray,
    windows: list[tuple[float, float]],
    max_dev: float = 0.25,
    max_stance_dev: float = 0.05,
) -> list[Stride]:
    """Strides fully inside one window, with exactly one toe-off.

    Two outlier filters remove missed or doubled contacts and steps that land
    across both belts: the duration must be within ``max_dev`` (fraction) of the
    median duration, and the stance fraction within ``max_stance_dev`` of the
    median stance fraction.
    """
    out = []
    for a, b in zip(hs[:-1], hs[1:]):
        if not any(w0 <= a and b <= w1 for w0, w1 in windows):
            continue
        inside = to[(to > a) & (to < b)]
        if len(inside) != 1:
            continue
        out.append(Stride("r", float(a), float(inside[0]), float(b), float("nan")))
    if not out:
        return out
    med = np.median([s.duration for s in out])
    out = [s for s in out if abs(s.duration - med) <= max_dev * med]
    if not out:
        return out
    med = np.median([s.stance_fraction for s in out])
    return [s for s in out if abs(s.stance_fraction - med) <= max_stance_dev]


def stride_curves(df: pd.DataFrame, column: str, strides: list[Stride], scale: float = 1.0) -> np.ndarray:
    """One row per stride of ``df[column]`` resampled at :data:`dropfoot.gait.PERCENT`."""
    t = df["Header"].to_numpy()
    y = scale * df[column].to_numpy()
    rows = [np.interp(s.heel_strike + PERCENT / 100 * s.duration, t, y) for s in strides]
    return np.vstack(rows) if rows else np.empty((0, len(PERCENT)))


def shank_velocity_ik(ik: pd.DataFrame) -> np.ndarray:
    """Sagittal shank angular velocity (rad/s) from inverse kinematics.

    In the planar chain the shank angle in the ground frame is
    ``pelvis_tilt + hip_flexion_r + knee_angle_r``, positive when the shank
    rotates forward, the sign of SCONE's ``tibia_r.ang_vel_z``.
    """
    angle = np.radians(ik["pelvis_tilt"] + ik["hip_flexion_r"] + ik["knee_angle_r"]).to_numpy()
    return np.gradient(angle, ik["Header"].to_numpy())


@dataclass(frozen=True)
class GyroAlignment:
    sign: int  # multiply the raw channel by this
    lag: float  # s, add to the IMU time stamps
    r: float  # correlation with the IK shank velocity after alignment
    gain: float  # SD ratio, gyro over IK

    @property
    def ok(self) -> bool:
        return self.r >= GYRO_MIN_R


GYRO_MIN_R = 0.9


def align_gyro(ik: pd.DataFrame, imu: pd.DataFrame, column: str = "shank_Gyro_Y", max_lag: float = 0.05) -> GyroAlignment:
    """Sign and time offset of the shank gyroscope relative to motion capture.

    The sensor's mounting (and so the sign of its sagittal axis) and its
    synchronization with the motion capture clock differ between subjects:
    at 1.2 m/s, ``shank_Gyro_Y`` correlates with the IK shank velocity at
    r = +0.98 in 2 subjects and about -0.95 in 18, and in two subjects (AB10,
    AB13) it does not match within half a second. This is the same
    calibration that an IMU-to-segment alignment would do in the lab.

    The lag is the shift within ``max_lag`` that maximizes the absolute
    correlation, refined to a fraction of a sample with a parabola. Subjects
    whose aligned correlation is below :data:`GYRO_MIN_R` are not used.
    """
    t = ik["Header"].to_numpy()
    w = shank_velocity_ik(ik)
    g = np.interp(t, imu["Header"].to_numpy(), imu[column].to_numpy())
    w, g = w - w.mean(), g - g.mean()
    dt = float(np.median(np.diff(t)))
    n = int(round(max_lag / dt))
    lags = np.arange(-n, n + 1)
    core = slice(n, len(t) - n)
    r = np.array([np.corrcoef(w[n + k : len(t) - n + k], g[core])[0, 1] for k in lags])
    i = int(np.argmax(np.abs(r)))
    frac = 0.0
    if 0 < i < len(r) - 1:
        a, b, c = np.abs(r[i - 1 : i + 2])
        denom = a - 2 * b + c
        frac = 0.5 * (a - c) / denom if denom != 0 else 0.0
    sign = 1 if r[i] > 0 else -1
    return GyroAlignment(sign, float((lags[i] + frac) * dt), float(abs(r[i])), float(g.std() / w.std()))


def aligned_imu(imu: pd.DataFrame, alignment: GyroAlignment, column: str = "shank_Gyro_Y") -> pd.DataFrame:
    """``Header`` corrected by the lag and ``shank_gyro`` (rad/s) in the SCONE sign convention."""
    return pd.DataFrame(
        {"Header": imu["Header"].to_numpy() + alignment.lag, "shank_gyro": alignment.sign * imu[column].to_numpy()}
    )


@dataclass(frozen=True)
class TrialFiles:
    subject: str
    trial: str  # e.g. treadmill_03_01
    folder: Path  # <subject>/<date>/treadmill

    def path(self, sensor: str) -> Path:
        return self.folder / sensor / f"{self.trial}.mat"


def find_trials(root: str | Path, subject: str) -> list[TrialFiles]:
    """Treadmill trials of one subject that have a ``conditions`` file."""
    out = []
    for cond in sorted(Path(root, subject).glob("*/treadmill/conditions/*.mat")):
        out.append(TrialFiles(subject, cond.stem, cond.parent.parent))
    return out


def subject_curves(trial: TrialFiles, mass: float, speed: float) -> tuple[dict[str, np.ndarray], GyroAlignment]:
    """Per-stride normative curves of one subject at one treadmill speed.

    The shank gyroscope curves are left empty when :func:`align_gyro` rejects
    the subject's IMU.
    """
    windows = speed_windows(load_table(trial.path("conditions"), "speed"), speed)
    fp = load_table(trial.path("fp"))
    hs, to = force_events(fp, mass)
    strides = strides_from_events(hs, to, windows)
    ik = load_table(trial.path("ik"))
    alignment = align_gyro(ik, load_table(trial.path("imu")))
    tables = {"ik": ik, "id": load_table(trial.path("id")), "fp": fp}
    tables["imu"] = aligned_imu(load_table(trial.path("imu")), alignment)
    out = {"stance_pct": np.array([100 * s.stance_fraction for s in strides])}
    for name, (sensor, column, scale, _) in VARIABLES.items():
        norm = {"ankle_moment": 1.0 / mass, "vertical_grf": 1.0 / (mass * G)}.get(name, 1.0)
        use = strides if (sensor != "imu" or alignment.ok) else []
        out[name] = stride_curves(tables[sensor], column, use, scale * norm)
    return out, alignment


def aggregate(per_subject: dict[str, dict[str, np.ndarray]]) -> pd.DataFrame:
    """Mean and SD across subjects of each subject's mean stride curve.

    Each subject counts once, however many strides it contributes, so the SD
    is the between-subject variability that a model is compared with.
    """
    cols: dict[str, np.ndarray] = {"percent": PERCENT}
    counts = {}
    for name in VARIABLES:
        means = np.vstack([d[name].mean(axis=0) for d in per_subject.values() if len(d[name])])
        cols[f"{name}_mean"] = means.mean(axis=0)
        cols[f"{name}_sd"] = means.std(axis=0, ddof=1) if len(means) > 1 else np.zeros(len(PERCENT))
        counts[name] = len(means)
    df = pd.DataFrame(cols)
    df.attrs["n_subjects"] = counts
    return df


def write_normative(df: pd.DataFrame, path: str | Path, speed: float, subjects: list[str], n_strides: int) -> None:
    """Write aggregated curves as CSV with an attribution header."""
    units = {name: unit for name, (_, _, _, unit) in VARIABLES.items()}
    counts = df.attrs.get("n_subjects", {})
    fewer = [f"{k} {v}" for k, v in counts.items() if v != len(subjects)]
    header = [
        f"# Normative treadmill walking at {speed:.2f} m/s, right leg, mean and SD across {len(subjects)} subjects",
        f"# ({n_strides} strides in total). Subjects: {' '.join(subjects)}.",
        *(
            [f"# Subjects per variable where fewer (IMU rejected by dropfoot.camargo.align_gyro): {', '.join(fewer)}."]
            if fewer
            else []
        ),
        "# Heel strike and toe-off: right belt vertical force crossing 5% of body weight.",
        "# shank_gyro: shank_Gyro_Y with its sign and time offset calibrated against IK per subject.",
        "# Units: " + ", ".join(f"{k} {v}" for k, v in units.items()) + "; percent of the gait cycle.",
        "# Signs: hip flexion +, knee flexion +, ankle dorsiflexion +, dorsiflexing ankle moment +.",
        f"# Source: {CITATION}",
        "# Aggregated by dropfoot.camargo (this repository); no per-subject data are included.",
    ]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        fh.write("\n".join(header) + "\n")
        df.to_csv(fh, index=False, float_format="%.5g")


def read_normative(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, comment="#")
