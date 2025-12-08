#!/usr/bin/env python3
"""Run headless SCONE in the companion repository's Docker image.

    python scripts/run_scone.py optimize scenarios/healthy.scone --seed 1 --generations 150
    python scripts/run_scone.py evaluate scenarios/healthy.scone results/healthy/s1/best.par \
        --out results/raw/eval/healthy_s1.par

Optimizations write to results/raw/runs/<scenario>.s<seed>/<run id>/ unless
--out is given. See src/dropfoot/scone.py for how paths are handled.
"""

from __future__ import annotations

import argparse
import sys

from dropfoot import scone


def _overrides(pairs: list[str]) -> dict[str, str]:
    out = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"override {pair!r} is not key=value")
        out[key] = value
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="mode", required=True)

    opt = sub.add_parser("optimize", help="optimize a scenario with one seed")
    opt.add_argument("scenario")
    opt.add_argument("--seed", type=int, required=True)
    opt.add_argument("--generations", type=int, required=True)
    opt.add_argument("--threads", type=int, default=3)
    opt.add_argument("--out", help="output root (default results/raw/runs/<scenario>.s<seed>)")
    opt.add_argument("overrides", nargs="*", help="key=value scenario overrides")

    ev = sub.add_parser("evaluate", help="evaluate a .par file with a scenario")
    ev.add_argument("scenario")
    ev.add_argument("par")
    ev.add_argument("--out", required=True, help="output path; SCONE writes <out>.sto")
    ev.add_argument("overrides", nargs="*", help="key=value scenario overrides")

    args = parser.parse_args(argv)
    if args.mode == "optimize":
        return scone.optimize(
            args.scenario, args.seed, args.generations, args.out, args.threads, _overrides(args.overrides)
        )
    sto = scone.evaluate(args.scenario, args.par, args.out, _overrides(args.overrides))
    print(sto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
