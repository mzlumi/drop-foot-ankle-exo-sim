"""SCONE ``.par`` files and the symmetric to asymmetric controller conversion.

A ``.par`` file has one parameter per line: name, value, and optionally the
mean and standard deviation of the CMA-ES search distribution when it was
written. SCONE warm-starts an optimization from it (``init_file``), using the
values as the initial mean and, by default, the stored standard deviations as
the initial step sizes.

The drop-foot model needs the asymmetric reflex controller
(``ControllerGH2010asym.scone``): the right leg must be free to adapt
differently from the left. Its parameters are the symmetric ones written once
per side, so a healthy symmetric result is a valid asymmetric starting point
with both sides equal. The names follow these rules, checked against the
parameter list SCONE 2.4.5 writes for ``ControllerGH2010asym``
(tests/data/asym_parameter_names.txt):

* initial state offsets (``*.offset``) are shared and keep their names;
* ``stance_load_threshold`` becomes ``leg0_l.stance_load_threshold`` and
  ``leg1_r.stance_load_threshold``;
* in reflex parameters ``S<states>.<target>[-<source>].<gain>`` the target
  muscle gets the side suffix, and so does the source if it is a muscle or
  ``pelvis_tilt``; ``knee_angle`` stays unsuffixed;
* within each state group, all left parameters come before all right ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MUSCLES = ("hamstrings", "glut_max", "iliopsoas", "vasti", "gastroc", "soleus", "tib_ant")
SIDED_SOURCES = MUSCLES + ("pelvis_tilt",)
LEGS = (("l", "leg0_l"), ("r", "leg1_r"))


@dataclass
class Param:
    name: str
    value: float
    mean: float | None = None
    std: float | None = None


def read_par(path: str | Path) -> list[Param]:
    out = []
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        nums = [float(x) for x in parts[1:4]]
        out.append(Param(parts[0], nums[0], *(nums[1:] + [None, None])[:2]))
    return out


def write_par(params: list[Param], path: str | Path) -> None:
    width = max(len(p.name) for p in params)
    lines = []
    for p in params:
        cols = [p.value] + [x for x in (p.mean, p.std) if x is not None]
        lines.append(f"{p.name:<{width}}\t" + "\t".join(f"{x:.10g}" for x in cols) + "\t")
    Path(path).write_text("\n".join(lines) + "\n")


def sided(name: str, side: str) -> str:
    """Asymmetric name of a symmetric reflex parameter ``S<states>.<target>[-<source>].<gain>``."""
    states, body, gain = name.split(".")
    target, _, source = body.partition("-")
    body = f"{target}_{side}"
    if source:
        body += f"-{source}_{side}" if source in SIDED_SOURCES else f"-{source}"
    return f"{states}.{body}.{gain}"


def sym_to_asym(params: list[Param]) -> list[Param]:
    """Asymmetric parameters equal on both sides, in SCONE's order."""
    out: list[Param] = []
    groups: dict[str, list[Param]] = {}
    for p in params:
        if p.name.endswith(".offset"):
            out.append(p)
        elif p.name == "stance_load_threshold":
            out += [Param(f"{leg}.{p.name}", p.value, p.mean, p.std) for _, leg in LEGS]
        elif p.name.startswith("S"):
            groups.setdefault(p.name.split(".")[0], []).append(p)
        else:
            raise ValueError(f"unknown parameter {p.name!r}")
    for members in groups.values():
        for side, _ in LEGS:
            out += [Param(sided(p.name, side), p.value, p.mean, p.std) for p in members]
    return out


def set_values(params: list[Param], values: dict[str, float]) -> list[Param]:
    """Copy of ``params`` with some values replaced (the search mean too)."""
    missing = set(values) - {p.name for p in params}
    if missing:
        raise KeyError(f"not in the parameter set: {sorted(missing)}")
    return [
        Param(p.name, values[p.name], values[p.name] if p.mean is not None else None, p.std)
        if p.name in values
        else p
        for p in params
    ]
