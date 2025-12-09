from pathlib import Path

import pytest

from dropfoot import params
from dropfoot.params import Param

DATA = Path(__file__).parent / "data"

# the parameter names of ResultGait10.par (symmetric ControllerGH2010), in file order
SYM_NAMES = """pelvis_tilt.offset hip_flexion_r.offset knee_angle_r.offset ankle_angle_r.offset
hip_flexion_l.offset knee_angle_l.offset ankle_angle_l.offset stance_load_threshold
S11111.tib_ant.KL S11111.tib_ant.L0 S11111.tib_ant-soleus.KF S00111.soleus.KF S00111.gastroc.KF
S00011.vasti.KF S00011.vasti.C0 S00011.vasti-knee_angle.pos_max
S00011.hamstrings-pelvis_tilt.KP S00011.hamstrings-pelvis_tilt.KV S00011.hamstrings-pelvis_tilt.C0
S00011.glut_max-pelvis_tilt.KP S00011.glut_max-pelvis_tilt.KV S00011.glut_max-pelvis_tilt.C0
S00011.iliopsoas-pelvis_tilt.KP S00011.iliopsoas-pelvis_tilt.KV S00011.iliopsoas-pelvis_tilt.C0
S00100.iliopsoas.C0 S00100.glut_max.C0 S11000.iliopsoas.KL S11000.iliopsoas.L0
S11000.iliopsoas-pelvis_tilt.P0 S11000.iliopsoas-pelvis_tilt.KP S11000.iliopsoas-pelvis_tilt.KV
S11000.iliopsoas-hamstrings.KL S11000.iliopsoas-hamstrings.L0 S11000.hamstrings.KF S11000.glut_max.KF""".split()


def sym_params():
    return [Param(n, float(i), float(i) + 0.5, 0.01 * (i + 1)) for i, n in enumerate(SYM_NAMES)]


def test_sym_to_asym_matches_scone_names_and_order():
    expected = (DATA / "asym_parameter_names.txt").read_text().split()
    asym = params.sym_to_asym(sym_params())
    assert [p.name for p in asym] == expected


def test_sym_to_asym_copies_values_to_both_sides():
    sym = {p.name: p for p in sym_params()}
    asym = {p.name: p for p in params.sym_to_asym(sym_params())}
    for side in "lr":
        a = asym[f"S00011.hamstrings_{side}-pelvis_tilt_{side}.KP"]
        s = sym["S00011.hamstrings-pelvis_tilt.KP"]
        assert (a.value, a.mean, a.std) == (s.value, s.mean, s.std)
    assert asym["S00011.vasti_r-knee_angle.pos_max"].value == sym["S00011.vasti-knee_angle.pos_max"].value
    assert asym["leg1_r.stance_load_threshold"].value == sym["stance_load_threshold"].value
    assert asym["hip_flexion_r.offset"].value == sym["hip_flexion_r.offset"].value


def test_par_round_trip(tmp_path):
    ps = sym_params()[:3] + [Param("x.y", -1.25e-5)]
    params.write_par(ps, tmp_path / "a.par")
    back = params.read_par(tmp_path / "a.par")
    assert [(p.name, p.value, p.mean, p.std) for p in back] == [(p.name, p.value, p.mean, p.std) for p in ps]


def test_set_values():
    ps = params.set_values(sym_params(), {"S00111.soleus.KF": 9.0})
    p = next(p for p in ps if p.name == "S00111.soleus.KF")
    assert p.value == p.mean == 9.0
    with pytest.raises(KeyError):
        params.set_values(sym_params(), {"nope": 1.0})


def test_unknown_parameter_rejected():
    with pytest.raises(ValueError):
        params.sym_to_asym([Param("mystery", 1.0)])
