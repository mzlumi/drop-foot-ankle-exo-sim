"""Small helpers around the companion repository's ``.sto`` reader and writer."""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path

import numpy as np
from scone_gait.storage import Storage, read_sto, write_sto

__all__ = ["Storage", "read_sto", "write_sto", "select", "export_channels"]


def select(sto: Storage, patterns: list[str]) -> list[str]:
    """Labels of ``sto`` that match any of the shell-style ``patterns``, in file order."""
    return [lab for lab in sto.labels if any(fnmatchcase(lab, p) for p in patterns)]


def export_channels(
    sto: Storage,
    patterns: list[str],
    path: str | Path,
    t0: float | None = None,
    t1: float | None = None,
    digits: int = 6,
) -> Storage:
    """Write a small ``.sto`` with only the matching channels, optionally cut to [t0, t1].

    Values are rounded to ``digits`` significant digits so committed exports stay small.
    """
    labels = select(sto, patterns)
    if not labels:
        raise KeyError(f"no channels match {patterns}")
    mask = np.ones(sto.frame_count, dtype=bool)
    if t0 is not None:
        mask &= sto.time >= t0 - 1e-9
    if t1 is not None:
        mask &= sto.time <= t1 + 1e-9
    cols = [sto.index(lab) for lab in labels]
    data = sto.data[mask][:, cols]
    data = np.array([[float(f"{v:.{digits}g}") for v in row] for row in data]).reshape(data.shape)
    out = Storage(labels=tuple(labels), time=np.round(sto.time[mask], 9), data=data, name=Path(path).stem)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_sto(out, path)
    return out
