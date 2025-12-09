#!/usr/bin/env python3
"""Fetch the inputs this project needs into data/raw/ (git-ignored).

Usage:
    python scripts/fetch_data.py            # everything that can be scripted, plus manual steps
    python scripts/fetch_data.py scone      # SCONE tutorial scenarios and the Human0914 model
    python scripts/fetch_data.py camargo    # print manual steps, then list what is in data/raw/camargo
    python scripts/fetch_data.py app        # print how to install the SCONE application

Only the Python standard library is used. See data/README.md for what each
resource is, its license and how it is used.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# scone-core (Apache-2.0), pinned so the starting files never change under us.
SCONE_CORE_COMMIT = "8cc814822c58356e110027d80962ebf0f024e116"
SCONE_CORE_RAW = (
    f"https://raw.githubusercontent.com/tgeijten/scone-core/{SCONE_CORE_COMMIT}/scenarios/Tutorials/"
)
SCONE_TUTORIAL_FILES = [
    "Tutorial 4a - Gait.scone",
    "Tutorial 4b - Gait at Different Speeds.scone",
    "Tutorial 4c - Perturbed Gait.scone",
    "Tutorial 5a - Pathological Gait - Weak Plantarflexors.scone",
    "Tutorial 5c - Pathological Gait - Hyper-reflexia.scone",
    "Tutorial 6b - Script - Balance Device.scone",
    "data/Human0914.osim",
    "data/ControllerGH2010.scone",
    "data/ControllerGH2010asym.scone",
    "data/MeasureGait05.scone",
    "data/MeasureGait10.scone",
    "data/MeasureGait15.scone",
    "data/InitStateGait10.sto",
    "data/InitStateGait15.sto",
    "data/ResultGait10.par",
    "data/ResultGait15.par",
    "data/ScriptControllerBalanceDevice.lua",
]

CAMARGO_PAGE = "https://www.epic.gatech.edu/opensource-biomechanics-camargo-et-al/"
CAMARGO_DROPBOX = "https://www.dropbox.com/sh/lhurwcy0znonh56/AAAPmVdrxh7M6FW-UYHyPHyza?dl=0"
CAMARGO_MENDELEY = [
    "https://doi.org/10.17632/fcgm3chfff.2",
    "https://doi.org/10.17632/k9kvm5tn3f.2",
    "https://doi.org/10.17632/jj3r5f9pnf.2",
]
SCONE_DOWNLOADS = "https://simtk.org/frs/?group_id=1180"

USER_AGENT = "Mozilla/5.0 (drop-foot-ankle-exo-sim fetch_data.py)"


def download(url: str, dest: Path, overwrite: bool = False) -> None:
    """Download one file to dest, skipping it if it already exists."""
    if dest.exists() and not overwrite:
        print(f"  exists   {dest.relative_to(ROOT)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(payload)
    tmp.replace(dest)
    digest = hashlib.sha256(payload).hexdigest()[:12]
    print(f"  fetched  {dest.relative_to(ROOT)}  ({len(payload)} bytes, sha256 {digest})")


def fetch_scone_tutorials(overwrite: bool) -> None:
    out = RAW / "scone-tutorials"
    print(f"SCONE tutorial files from scone-core @ {SCONE_CORE_COMMIT[:10]} -> {out.relative_to(ROOT)}")
    for name in SCONE_TUTORIAL_FILES:
        url = SCONE_CORE_RAW + urllib.parse.quote(name)
        download(url, out / name, overwrite=overwrite)


def print_scone_app_steps() -> None:
    print(
        "\nSCONE application (manual, browser):\n"
        f"  1. Open {SCONE_DOWNLOADS}\n"
        "  2. Download the installer for your system (Windows .exe, Linux .deb or macOS .dmg).\n"
        "  3. Install it as described at https://scone.software/doku.php?id=install\n"
        "  4. Record the SCONE version in results/ENVIRONMENT.md.\n"
        "  For headless runs, reuse the Docker runner in mzlumi/scone-pathological-gait."
    )


def camargo(list_only: bool = False) -> None:
    target = RAW / "camargo"
    if not list_only:
        print(
            "\nCamargo et al. 2021 dataset (CC BY 4.0):\n"
            f"  Project page: {CAMARGO_PAGE}\n"
            f"  Dropbox mirror: {CAMARGO_DROPBOX}\n"
            "  Mendeley Data: " + ", ".join(CAMARGO_MENDELEY) + "\n"
            "  The files this project needs are extracted from the Mendeley zips by:\n"
            "    python scripts/fetch_camargo.py conditions\n"
            "    python scripts/fetch_camargo.py trials --speed 1.2\n"
            f"  into {target.relative_to(ROOT)}/ (see data/README.md, section 3)."
        )
    if not target.exists():
        print(f"\n  {target.relative_to(ROOT)}/ does not exist yet.")
        return
    info = target / "SubjectInfo.mat"
    print(f"\n  SubjectInfo.mat: {'found' if info.exists() else 'missing'}")
    subjects = sorted(p.name for p in target.iterdir() if p.is_dir())
    print(f"  Subject folders: {', '.join(subjects) if subjects else 'none'}")
    for subject in subjects:
        files = list((target / subject).rglob("*.mat"))
        size_mb = sum(f.stat().st_size for f in files) / 1e6
        print(f"    {subject}: {len(files)} .mat files, {size_mb:.0f} MB")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", nargs="?", default="all", choices=["all", "scone", "camargo", "app"])
    parser.add_argument("--overwrite", action="store_true", help="download files again even if present")
    args = parser.parse_args(argv)

    RAW.mkdir(parents=True, exist_ok=True)
    if args.what in ("all", "scone"):
        fetch_scone_tutorials(args.overwrite)
    if args.what in ("all", "app"):
        print_scone_app_steps()
    if args.what in ("all", "camargo"):
        camargo()
    return 0


if __name__ == "__main__":
    sys.exit(main())
