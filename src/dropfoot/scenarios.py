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
	init_file = {up}/results/healthy/seed1/healthy_asym.par

	SimulationObjective {{
		max_duration = {duration:g}
		signature_postfix = {tag}

		ModelOpenSim3 {{
			model_file = {up}/data/raw/scone-tutorials/data/Human0914.osim
			state_init_file = {up}/data/raw/scone-tutorials/data/InitStateGait10.sto
			initial_state_offset = 0~0.01<-0.5,0.5>
			initial_state_offset_exclude = "*_tx;*_ty;*_u"

			Properties {{
				tib_ant_r {{ max_isometric_force.factor = {factor:.4g} }}
			}}
		}}

		# Geyer and Herr (2010) reflex controller, asymmetric
		<< {up}/data/raw/scone-tutorials/data/ControllerGH2010asym.scone >>

		<< {include}/MeasureGait12.scone >>
	}}
}}
"""


def strength_tag(factor: float) -> str:
    """``ta25`` for 0.25; one decimal of a percent when needed (``ta17.5``)."""
    pct = round(100 * factor, 1)
    return f"ta{pct:g}"


def dropfoot_scenario(factor: float, duration: float = 10.0, depth: int = 0) -> str:
    """Scenario text for a file ``depth`` folders below scenarios/ (0: scenarios/ itself)."""
    if not 0 < factor <= 1:
        raise ValueError("factor must be in (0, 1]")
    up = "/".join([".."] * (depth + 1))
    include = "/".join([".."] * depth + ["include"])
    return DROPFOOT.format(
        pct=f"{100 * factor:g}", factor=factor, duration=duration, tag=strength_tag(factor), up=up, include=include
    )


def write_dropfoot(factor: float, folder: Path = SCENARIOS, duration: float = 10.0) -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    depth = len(folder.resolve().relative_to(SCENARIOS.resolve()).parts)
    path = folder / f"dropfoot_{strength_tag(factor)}.scone"
    path.write_text(dropfoot_scenario(factor, duration, depth))
    return path


GENERATED = SCENARIOS / "generated"

DEVICE = """\
# {title}
# Derived from scone-core scenarios/Tutorials/Tutorial 4a - Gait.scone,
# Tutorial 5a - Pathological Gait - Weak Plantarflexors.scone and
# Tutorial 6b - Script - Balance Device.scone
# (commit 8cc814822c58356e110027d80962ebf0f024e116, Apache-2.0).
# Changes: paths point at data/raw/scone-tutorials, external forces enabled,
# the reflex controller runs next to the exoskeleton script
# (scenarios/lua/device.lua), and the gait measure is {measure}.
# Written by dropfoot.scenarios.device_scenario; edit the template, not this file.
CmaOptimizer {{
	signature_prefix = DATE_TIME
	init_file = {init_file}

	SimulationObjective {{
		max_duration = {duration:g}
		signature_postfix = {tag}

		ModelOpenSim3 {{
			model_file = {data}/Human0914.osim
			state_init_file = {data}/{init_state}
			initial_state_offset = 0~0.01<-0.5,0.5>
			initial_state_offset_exclude = "*_tx;*_ty;*_u"
			enable_external_forces = 1
{properties}		}}

		CompositeController {{
			# Geyer and Herr (2010) reflex controller, {symmetry}
			<< {data}/{controller} >>

			ScriptController {{
				name = Exo
				script_file = "{lua}/device.lua"
{device}			}}
{extra}		}}

		<< {measure_path} >>
	}}
}}
"""


def _props(d: dict[str, object], indent: str) -> str:
    return "".join(f"{indent}{k} = {v}\n" for k, v in d.items())


def device_scenario(
    title: str,
    tag: str,
    device: dict[str, object],
    factor: float = 1.0,
    duration: float = 10.0,
    init_file: str = "../../data/raw/scone-tutorials/data/ResultGait10.par",
    measure: str = "MeasureGait12",
    init_state: str = "InitStateGait10.sto",
    extra: str = "",
) -> str:
    """Scenario text for scenarios/generated/: the healthy model (``factor`` = 1,
    symmetric controller) or the drop-foot model (``factor`` < 1, tib_ant_r
    scaled, asymmetric controller) wearing the device described by ``device``
    (ScriptController properties of device.lua). ``measure`` is
    MeasureGait12 (scenarios/include) or a tutorial measure such as MeasureGait15."""
    if not 0 < factor <= 1:
        raise ValueError("factor must be in (0, 1]")
    data = "../../data/raw/scone-tutorials/data"
    properties = ""
    if factor < 1:
        properties = (
            "\n\t\t\tProperties {\n"
            f"\t\t\t\ttib_ant_r {{ max_isometric_force.factor = {factor:.4g} }}\n"
            "\t\t\t}\n"
        )
    measure_path = f"../include/{measure}.scone" if measure == "MeasureGait12" else f"{data}/{measure}.scone"
    return DEVICE.format(
        title=title,
        tag=tag,
        init_file=init_file,
        duration=duration,
        data=data,
        init_state=init_state,
        properties=properties,
        symmetry="symmetric" if factor == 1 else "asymmetric",
        controller="ControllerGH2010.scone" if factor == 1 else "ControllerGH2010asym.scone",
        lua="../lua",
        device=_props(device, "\t\t\t\t"),
        extra=extra,
        measure=measure,
        measure_path=measure_path,
    )


def write_generated(name: str, text: str, folder: Path = GENERATED) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.scone"
    path.write_text(text)
    return path
