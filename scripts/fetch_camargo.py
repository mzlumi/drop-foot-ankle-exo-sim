#!/usr/bin/env python3
"""Download only the needed parts of the Camargo et al. (2021) dataset from Mendeley Data.

The dataset is three zip files of 4.7 to 10 GB on Mendeley Data (CC BY 4.0).
The files are served from S3, which answers HTTP range requests, so this
script reads each zip's central directory remotely and extracts single
members without downloading the archives.

    python scripts/fetch_camargo.py conditions          # SubjectInfo.mat and every treadmill conditions file
    python scripts/fetch_camargo.py trials --speed 1.2  # per subject, the treadmill trial with that speed

The second stage reads the conditions tables (needs the project installed)
and downloads ik, id, imu, fp, gcRight and gcLeft of the chosen trial only.
Files land in data/raw/camargo/<subject>/<date>/treadmill/<sensor>/ as in the
archives. data/raw/camargo/selected_trials.csv records what was chosen.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "camargo"
UA = {"User-Agent": "Mozilla/5.0 (drop-foot-ankle-exo-sim fetch_camargo.py)"}

# Mendeley Data version 2 file URLs (see data/README.md)
PARTS = {
    "Part1_AB06-AB14": "https://data.mendeley.com/public-files/datasets/fcgm3chfff/files/9c30f2e4-2d39-4d95-b691-1163c927455e/file_downloaded",
    "Part2_AB15-AB24": "https://data.mendeley.com/public-files/datasets/k9kvm5tn3f/files/2b976163-2870-458c-816d-30e07f17ad90/file_downloaded",
    "Part3_AB25-AB30": "https://data.mendeley.com/public-files/datasets/jj3r5f9pnf/files/2800004c-be9c-40fa-b9bd-50ad3ec1b085/file_downloaded",
}
SUBJECT_INFO = "https://data.mendeley.com/public-files/datasets/fcgm3chfff/files/d0f204d7-903c-4064-aff6-7080b2b5acb8/file_downloaded"
TRIAL_SENSORS = ["ik", "id", "imu", "fp", "gcRight", "gcLeft"]


class HttpRangeFile(io.RawIOBase):
    """A seekable, read-only file over HTTP range requests."""

    def __init__(self, url: str):
        with urllib.request.urlopen(urllib.request.Request(url, headers={**UA, "Range": "bytes=0-0"})) as r:
            self.url = r.url  # after redirects
            self.size = int(r.headers["Content-Range"].split("/")[-1])
        self.pos = 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def readinto(self, buf) -> int:
        if self.pos >= self.size or len(buf) == 0:
            return 0
        end = min(self.pos + len(buf), self.size) - 1
        req = urllib.request.Request(self.url, headers={**UA, "Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        buf[: len(data)] = data
        self.pos += len(data)
        return len(data)


def open_part(url: str) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BufferedReader(HttpRangeFile(url), buffer_size=1 << 22))


def extract(z: zipfile.ZipFile, names: list[str]) -> None:
    for name in names:
        dest = OUT / name
        if dest.exists() and dest.stat().st_size == z.getinfo(name).file_size:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part")
        with z.open(name) as src, open(tmp, "wb") as dst:
            while chunk := src.read(1 << 22):
                dst.write(chunk)
        tmp.replace(dest)
        print(f"  {name} ({dest.stat().st_size / 1e6:.1f} MB)")


def stage_conditions() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    info = OUT / "SubjectInfo.mat"
    if not info.exists():
        info.write_bytes(urllib.request.urlopen(urllib.request.Request(SUBJECT_INFO, headers=UA)).read())
    for part, url in PARTS.items():
        print(part)
        z = open_part(url)
        names = [n for n in z.namelist() if "/treadmill/conditions/" in n and n.endswith(".mat")]
        extract(z, names)


def stage_trials(speed: float) -> None:
    from dropfoot.camargo import find_trials, load_table, speed_windows

    chosen: dict[str, tuple[str, str]] = {}  # subject -> (archive folder, trial)
    for subject_dir in sorted(p for p in OUT.iterdir() if p.is_dir()):
        best = None
        for trial in find_trials(OUT, subject_dir.name):
            windows = speed_windows(load_table(trial.path("conditions"), "speed"), speed)
            length = sum(b - a for a, b in windows)
            if length > 0 and (best is None or length > best[0]):
                best = (length, trial)
        if best is None:
            print(f"{subject_dir.name}: no treadmill trial at {speed} m/s")
            continue
        trial = best[1]
        chosen[subject_dir.name] = (trial.folder.relative_to(OUT).as_posix(), trial.trial)
        print(f"{subject_dir.name}: {trial.trial} ({best[0]:.0f} s at {speed} m/s)")

    for part, url in PARTS.items():
        z = open_part(url)
        names = set(z.namelist())
        wanted = [
            f"{folder}/{sensor}/{trial}.mat"
            for folder, trial in chosen.values()
            for sensor in TRIAL_SENSORS
            if f"{folder}/{sensor}/{trial}.mat" in names
        ]
        if wanted:
            print(part)
            extract(z, wanted)

    with open(OUT / f"selected_trials_{speed:.2f}.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["subject", "folder", "trial", "speed_mps"])
        for subject, (folder, trial) in sorted(chosen.items()):
            w.writerow([subject, folder, trial, f"{speed:.2f}"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("stage", choices=["conditions", "trials"])
    p.add_argument("--speed", type=float, default=1.2)
    args = p.parse_args(argv)
    if args.stage == "conditions":
        stage_conditions()
    else:
        stage_trials(args.speed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
