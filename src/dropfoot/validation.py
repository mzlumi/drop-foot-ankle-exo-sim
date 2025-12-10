"""Scoring the gait-event detector against force-plate events (Part D3).

Ground truth is the right foot's vertical force crossing 5% of body weight
(:func:`dropfoot.gait.contact_events`, debounced with
:func:`dropfoot.gait.merge_contacts`): heel strike (HS) on the rise, toe-off
(TO) on the fall. The detector sees only the measured gyroscope samples, each
at the time it became available (sample time plus the sensor delay).

Scores, per event type, over true events inside an analysis window
``[t0, t1]`` that skips the start-up of the simulation:

* **timing error**: estimated event time minus true time (s). It includes the
  sensor delay and the offset of the gyroscope feature from the force event;
* **latency**: time at which the event was confirmed minus true time, the
  delay a controller acting on the event would see;
* **missed**: true events without a detection within (-0.15, +0.25) s;
* **false**: detections inside the window that pair with no true event.

The gait phase estimate is scored against the true phase, the time since the
last true HS divided by that stride's duration, as a circular difference in
percent of the cycle.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dropfoot.detector import HEEL_STRIKE, TOE_OFF, Detector, DetectorConfig
from dropfoot.gait import contact_events, merge_contacts
from dropfoot.io import Storage

WINDOW = (-0.15, 0.25)


def true_events(sto: Storage, channel: str = "leg1_r.grf_norm_y") -> tuple[np.ndarray, np.ndarray]:
    """Debounced HS and TO times; a contact still open at the end keeps its HS."""
    raw_hs, raw_to = contact_events(sto.time, sto[channel])
    hs, to = merge_contacts(raw_hs, raw_to)
    if sto[channel][-1] > 0.05 and len(raw_hs):
        last = raw_hs[-1]
        if (not len(to) or last > to[-1] + 0.05) and (not len(hs) or last > hs[-1]):
            hs = np.append(hs, last)
    return hs, to


def gyro_samples(sto: Storage, rate_hz: float, delay_s: float) -> tuple[np.ndarray, np.ndarray]:
    """(availability time, value) of each measured sample, read from the held output channels."""
    k = sto["imu.output_k"].astype(int)
    first = np.flatnonzero(np.r_[True, np.diff(k) != 0] & (k >= 0))
    return k[first] / rate_hz + delay_s, sto["imu.measured"][first]


@dataclass(frozen=True)
class Score:
    errors: np.ndarray
    latency: np.ndarray
    n_true: int
    missed: int
    false: int

    def summary(self, prefix: str) -> dict[str, float]:
        e, lat = 1000 * self.errors, 1000 * self.latency
        has = len(e) > 0
        return {
            f"{prefix}_n_true": self.n_true,
            f"{prefix}_missed": self.missed,
            f"{prefix}_false": self.false,
            f"{prefix}_error_mean_ms": float(e.mean()) if has else np.nan,
            f"{prefix}_error_sd_ms": float(e.std(ddof=1)) if len(e) > 1 else np.nan,
            f"{prefix}_error_mae_ms": float(np.abs(e).mean()) if has else np.nan,
            f"{prefix}_error_max_abs_ms": float(np.abs(e).max()) if has else np.nan,
            f"{prefix}_latency_mean_ms": float(lat.mean()) if has else np.nan,
            f"{prefix}_latency_max_ms": float(lat.max()) if has else np.nan,
        }


def score(
    true: np.ndarray, estimate: np.ndarray, detected: np.ndarray, t0: float, t1: float, window=WINDOW
) -> Score:
    """Pair detections with true events, nearest first, then score true events in [t0, t1].

    Pairing uses every true event, so a detection just inside the window that
    belongs to a true event just outside it is neither scored nor false.
    """
    true = np.asarray(true, float)
    estimate, detected = np.asarray(estimate, float), np.asarray(detected, float)
    used = np.zeros(len(estimate), bool)
    errors, latency, missed, n_true = [], [], 0, 0
    for te in true:
        d = estimate - te
        ok = (~used) & (d >= window[0]) & (d <= window[1])
        j = int(np.flatnonzero(ok)[np.argmin(np.abs(d[ok]))]) if ok.any() else -1
        if j >= 0:
            used[j] = True
        if not t0 <= te <= t1:
            continue
        n_true += 1
        if j < 0:
            missed += 1
        else:
            errors.append(d[j])
            latency.append(detected[j] - te)
    inside = (estimate >= t0) & (estimate <= t1)
    return Score(np.array(errors), np.array(latency), n_true, missed, int((inside & ~used).sum()))


@dataclass
class Run:
    """Detector events and phase at every sample of one stream."""

    t: np.ndarray
    phase: np.ndarray
    hs_time: np.ndarray
    hs_detect: np.ndarray
    to_time: np.ndarray
    to_detect: np.ndarray


def run_detector(t: np.ndarray, y: np.ndarray, cfg: DetectorConfig = DetectorConfig()) -> Run:
    d = Detector(cfg)
    phase = np.empty(len(t))
    hs, hsd, to, tod = [], [], [], []
    for i, (ti, yi) in enumerate(zip(t, y)):
        e = d.update(float(ti), float(yi))
        if e == HEEL_STRIKE:
            hs.append(d.hs_time)
            hsd.append(d.hs_detect)
        elif e == TOE_OFF:
            to.append(d.to_time)
            tod.append(d.to_detect)
        phase[i] = d.phase(float(ti))
    return Run(np.asarray(t, float), phase, *(np.array(v) for v in (hs, hsd, to, tod)))


def true_phase(t: np.ndarray, hs: np.ndarray) -> np.ndarray:
    """Fraction of the stride since the last true HS; NaN outside [first HS, last HS)."""
    t = np.asarray(t, float)
    out = np.full(len(t), np.nan)
    i = np.searchsorted(hs, t, side="right") - 1
    ok = (i >= 0) & (i < len(hs) - 1)
    out[ok] = (t[ok] - hs[i[ok]]) / (hs[i[ok] + 1] - hs[i[ok]])
    return out


def phase_error(run: Run, hs_true: np.ndarray, t0: float, t1: float) -> np.ndarray:
    """Estimated minus true phase (fraction of a cycle, wrapped to [-0.5, 0.5)) at samples in [t0, t1]."""
    truth = true_phase(run.t, hs_true)
    m = (run.t >= t0) & (run.t <= t1) & np.isfinite(truth) & (run.phase >= 0)
    return (run.phase[m] - truth[m] + 0.5) % 1.0 - 0.5
