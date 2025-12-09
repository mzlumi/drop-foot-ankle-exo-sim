"""Causal gait-event detector on the measured shank gyroscope (Part D2).

Python twin of scenarios/lua/detector.lua: the same states, thresholds and
arithmetic, so both give the same events on the same samples. Units are deg/s
and s; the gyroscope is positive when the shank rotates forward.

The detector runs once per new gyroscope sample, at the time ``t`` the sample
became available, and uses only that sample and earlier ones. In one stride
the shank signal shows (docs/conventions.md):

* **swing**: a large positive peak; the detector arms when the signal rises
  above ``swing_dps``;
* **terminal swing**: after the peak the signal crosses zero going down;
* **heel strike (HS)**: with ``hs_feature="min"`` the first negative minimum
  after that zero crossing, confirmed once the signal has risen
  ``hs_rise_dps`` above it and the minimum is deeper than ``hs_depth_dps``;
  with ``hs_feature="zero"`` the zero crossing itself (linearly interpolated
  between the two samples around it);
* **toe-off (TO)**: once ``lockout_frac`` mean stride times have passed since
  HS, the next negative minimum deeper than ``to_depth_dps``, confirmed once
  the signal has risen ``to_rise_dps`` above it.

Each event has a time estimate (the time of the sample at the extremum, or
the interpolated zero crossing) and a detection time (when it was
confirmed). Both include the sensor's transport delay; the detector does not
know it. Gait phase is (t - last HS estimate) divided by the mean of the last
three accepted stride times (0.6 to 2 s, starting from ``stride0``), capped at
1, and -1 before the first HS.

If the terminal-swing minimum is not confirmed within ``terminal_timeout``
s, or no TO follows within 2 s of HS, the detector returns to searching for
the next swing; strides lost this way are counted as missed events.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SEARCH, SWING, TERMINAL, STANCE, PRESWING = 0, 1, 2, 3, 4
NONE, HEEL_STRIKE, TOE_OFF = 0, 1, 2


@dataclass(frozen=True)
class DetectorConfig:
    swing_dps: float = 100.0
    hs_feature: str = "min"
    hs_depth_dps: float = 50.0
    hs_rise_dps: float = 20.0
    to_depth_dps: float = 100.0
    to_rise_dps: float = 20.0
    lockout_frac: float = 0.35
    terminal_timeout: float = 0.3
    stride0: float = 1.1

    def lua_properties(self) -> dict[str, str]:
        """The same settings as ScriptController properties."""
        return {k: str(v) for k, v in self.__dict__.items()}


class Detector:
    def __init__(self, cfg: DetectorConfig = DetectorConfig()):
        self.cfg = cfg
        self.state = SEARCH
        self.t_prev: float | None = None
        self.y_prev: float | None = None
        self.t_enter = 0.0
        self.ext_y = 0.0
        self.ext_t = 0.0
        self.hs_time = -1.0
        self.hs_detect = -1.0
        self.to_time = -1.0
        self.to_detect = -1.0
        self.n_hs = 0
        self.n_to = 0
        self.strides = [cfg.stride0, cfg.stride0, cfg.stride0]

    def mean_stride(self) -> float:
        return (self.strides[0] + self.strides[1] + self.strides[2]) / 3.0

    def _heel_strike(self, t_event: float, t: float) -> None:
        if self.n_hs > 0:
            T = t_event - self.hs_time
            if 0.6 <= T <= 2.0:
                self.strides = [self.strides[1], self.strides[2], T]
        self.hs_time = t_event
        self.hs_detect = t
        self.n_hs += 1
        self.state = STANCE
        self.t_enter = t

    def update(self, t: float, y: float) -> int:
        """Feed one sample ``y`` available at ``t``; returns NONE, HEEL_STRIKE or TOE_OFF."""
        c = self.cfg
        event = NONE
        s = self.state
        if s == SEARCH:
            if y > c.swing_dps:
                self.state = SWING
                self.t_enter = t
        elif s == SWING:
            if y < 0.0:
                tz = t
                if self.y_prev is not None and self.y_prev > y:
                    tz = self.t_prev + (t - self.t_prev) * self.y_prev / (self.y_prev - y)
                if c.hs_feature == "zero":
                    self._heel_strike(tz, t)
                    event = HEEL_STRIKE
                else:
                    self.state = TERMINAL
                    self.t_enter = t
                    self.ext_y = y
                    self.ext_t = t
        elif s == TERMINAL:
            if y < self.ext_y:
                self.ext_y = y
                self.ext_t = t
            if self.ext_y < -c.hs_depth_dps and y > self.ext_y + c.hs_rise_dps:
                self._heel_strike(self.ext_t, t)
                event = HEEL_STRIKE
            elif t - self.t_enter > c.terminal_timeout:
                self.state = SEARCH
                self.t_enter = t
        elif s == STANCE:
            if t - self.hs_time > c.lockout_frac * self.mean_stride():
                self.state = PRESWING
                self.t_enter = t
                self.ext_y = y
                self.ext_t = t
        elif s == PRESWING:
            if y < self.ext_y:
                self.ext_y = y
                self.ext_t = t
            if self.ext_y < -c.to_depth_dps and y > self.ext_y + c.to_rise_dps:
                self.to_time = self.ext_t
                self.to_detect = t
                self.n_to += 1
                self.state = SEARCH
                self.t_enter = t
                event = TOE_OFF
            elif t - self.hs_time > 2.0:
                self.state = SEARCH
                self.t_enter = t
        self.t_prev = t
        self.y_prev = y
        return event

    def phase(self, t: float) -> float:
        if self.n_hs == 0:
            return -1.0
        return min((t - self.hs_time) / self.mean_stride(), 1.0)


@dataclass
class Events:
    hs_time: list[float] = field(default_factory=list)
    hs_detect: list[float] = field(default_factory=list)
    to_time: list[float] = field(default_factory=list)
    to_detect: list[float] = field(default_factory=list)

    def as_arrays(self) -> dict[str, np.ndarray]:
        return {k: np.asarray(v, float) for k, v in self.__dict__.items()}


def detect(t: np.ndarray, y: np.ndarray, cfg: DetectorConfig = DetectorConfig()) -> Events:
    """Run the detector over a sample stream (availability times and values)."""
    d = Detector(cfg)
    ev = Events()
    for ti, yi in zip(t, y):
        e = d.update(float(ti), float(yi))
        if e == HEEL_STRIKE:
            ev.hs_time.append(d.hs_time)
            ev.hs_detect.append(d.hs_detect)
        elif e == TOE_OFF:
            ev.to_time.append(d.to_time)
            ev.to_detect.append(d.to_detect)
    return ev


@dataclass(frozen=True)
class Match:
    errors: np.ndarray  # detected minus true (s), one per matched true event
    latency: np.ndarray  # detection time minus true (s)
    missed: int
    false: int
    n_true: int

    @property
    def missed_rate(self) -> float:
        return self.missed / self.n_true if self.n_true else float("nan")

    @property
    def false_rate(self) -> float:
        return self.false / self.n_true if self.n_true else float("nan")


def match_events(
    true: np.ndarray, estimate: np.ndarray, detected: np.ndarray, window: tuple[float, float] = (-0.15, 0.25)
) -> Match:
    """Pair each true event with at most one detection whose estimate lies in
    ``window`` (s) around it, nearest first. Unpaired true events are missed;
    unpaired detections are false."""
    true = np.asarray(true, float)
    estimate = np.asarray(estimate, float)
    detected = np.asarray(detected, float)
    used = np.zeros(len(estimate), bool)
    errors, latency = [], []
    missed = 0
    for te in true:
        d = estimate - te
        ok = (~used) & (d >= window[0]) & (d <= window[1])
        if not ok.any():
            missed += 1
            continue
        j = int(np.flatnonzero(ok)[np.argmin(np.abs(d[ok]))])
        used[j] = True
        errors.append(d[j])
        latency.append(detected[j] - te)
    return Match(np.array(errors), np.array(latency), missed, int((~used).sum()), len(true))
