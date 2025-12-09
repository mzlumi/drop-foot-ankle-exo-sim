"""Generated SCONE scenarios.

The drop-foot scenarios differ only in the strength of the right tibialis
anterior. SCONE cannot override ``max_isometric_force.factor`` from the
command line (the dot in the property name is read as nesting), so every
strength level, including the bisection steps, is written from one template.
The committed files under scenarios/ are checked against it in the tests.
"""

from __future__ import annotations

from pathlib import Path

from dropfoot import ROOT

SCENARIOS = ROOT / "scenarios"

DROPFOOT = """\
# Unilateral drop foot: right tibialis anterior at {pct}% of its maximum isometric force (Part B).
# Derived from scone-core scenarios/Tutorials/Tutorial 4a - Gait.scone and
# Tutorial 5a - Pathological Gait - Weak Plantarflexors.scone
# (commit 8cc814822c58356e110027d80962ebf0f024e116, Apache-2.0).
# Changes: paths point at data/raw/scone-tutorials, the asymmetric reflex
# controller (each leg adapts on its own), the 1.2 m/s gait measure, and a
# Properties block that weakens tib_ant_r only. The init_file is replaced per
# seed on the command line (CmaOptimizer.init_file=...) by that seed's healthy
# result converted with dropfoot.params.sym_to_asym.
# Written by dropfoot.scenarios.dropfoot_scenario; edit the template, not this file.
CmaOptimizer {{
	signature_prefix = DATE_TIME
	init_file = ../results/healthy/seed1/healthy_asym.par

	SimulationObjective {{
		max_duration = {duration:g}
		signature_postfix = {tag}

		ModelOpenSim3 {{
			model_file = ../data/raw/scone-tutorials/data/Human0914.osim
			state_init_file = ../data/raw/scone-tutorials/data/InitStateGait10.sto
			initial_state_offset = 0~0.01<-0.5,0.5>
			initial_state_offset_exclude = "*_tx;*_ty;*_u"

			Properties {{
				tib_ant_r {{ max_isometric_force.factor = {factor:.4g} }}
			}}
		}}

		# Geyer and Herr (2010) reflex controller, asymmetric
		<< ../data/raw/scone-tutorials/data/ControllerGH2010asym.scone >>

		<< include/MeasureGait12.scone >>
	}}
}}
"""


def strength_tag(factor: float) -> str:
    """``ta25`` for 0.25; one decimal of a percent when needed (``ta17.5``)."""
    pct = round(100 * factor, 1)
    return f"ta{pct:g}"


def dropfoot_scenario(factor: float, duration: float = 10.0) -> str:
    if not 0 < factor <= 1:
        raise ValueError("factor must be in (0, 1]")
    return DROPFOOT.format(pct=f"{100 * factor:g}", factor=factor, duration=duration, tag=strength_tag(factor))


def write_dropfoot(factor: float, folder: Path = SCENARIOS, duration: float = 10.0) -> Path:
    path = Path(folder) / f"dropfoot_{strength_tag(factor)}.scone"
    path.write_text(dropfoot_scenario(factor, duration))
    return path
