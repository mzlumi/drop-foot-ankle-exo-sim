from pathlib import Path

import numpy as np
import pytest

from dropfoot import scone
from dropfoot.io import Storage, export_channels, read_sto, write_sto


def test_container_path_maps_into_work(tmp_path):
    (tmp_path / "scenarios").mkdir()
    assert scone.container_path(tmp_path / "scenarios" / "x.scone", tmp_path) == "/work/scenarios/x.scone"
    assert scone.container_path(tmp_path, tmp_path) == "/work"


def test_container_path_rejects_outside_files(tmp_path):
    with pytest.raises(ValueError):
        scone.container_path("/etc/passwd", tmp_path)


def test_optimize_command_sets_seed_generations_and_threads(tmp_path):
    cmd = scone.optimize_command(
        tmp_path / "s.scone", seed=7, output_root=tmp_path / "out", generations=50, threads=2,
        overrides={"CmaOptimizer.lambda": 20}, name="n", root=tmp_path,
    )
    assert cmd[:3] == ["docker", "run", "--rm"]
    assert f"{tmp_path.resolve()}:/work" in cmd
    assert any(arg.endswith(":/root/.config/SCONE:ro") for arg in cmd)
    i = cmd.index(scone.IMAGE)
    assert cmd[i + 1 : i + 5] == ["-o", "/work/s.scone", "-r", "/work/out"]
    for arg in ("CmaOptimizer.random_seed=7", "CmaOptimizer.max_generations=50",
                "CmaOptimizer.max_threads=2", "CmaOptimizer.lambda=20"):
        assert arg in cmd


def test_prepare_evaluation_puts_par_next_to_scenario_copy(tmp_path):
    scen = tmp_path / "scenarios" / "a.scone"
    scen.parent.mkdir()
    scen.write_text("CmaOptimizer {}")
    par = tmp_path / "p.par"
    par.write_text("x 1 1 0.1\n")
    files = scone.prepare_evaluation(scen, par, tmp_path / "out" / "r.par", tag="t")
    assert files.scenario == scen.parent / ".eval_t.scone"
    assert files.par.with_suffix(".scone") == files.scenario
    assert files.scenario.read_text() == "CmaOptimizer {}"
    cmd = scone.evaluate_command(files, root=tmp_path)
    assert cmd[-4:] == ["-e", "/work/scenarios/.eval_t.par", "-r", "/work/out/r.par"]
    files.cleanup()
    assert not files.scenario.exists() and not files.par.exists()


def test_export_channels_selects_cuts_and_rounds(tmp_path):
    t = np.arange(0, 1.0, 0.1)
    data = np.column_stack([np.pi * t, t, -t])
    sto = Storage(labels=("a.x", "a.y", "b"), time=t, data=data)
    write_sto(sto, tmp_path / "full.sto")
    out = export_channels(read_sto(tmp_path / "full.sto"), ["a.*"], tmp_path / "small.sto", 0.2, 0.5, digits=4)
    back = read_sto(tmp_path / "small.sto")
    assert back.labels == ("a.x", "a.y")
    np.testing.assert_allclose(back.time, [0.2, 0.3, 0.4, 0.5])
    np.testing.assert_allclose(back["a.x"], np.round(np.pi * back.time, 3), atol=1e-3)
    assert out.frame_count == 4


def test_sign_check_export_is_committed():
    path = Path(__file__).resolve().parents[1] / "results" / "sign_check" / "tutorial_stride.sto"
    sto = read_sto(path)
    # dorsiflexion positive: late-stance peak above +10 deg; plantarflexor moment negative
    assert np.degrees(sto["ankle_angle_r"]).max() > 10
    assert sto["ankle_angle_r.moment"].min() < -80
    # shank gyro positive in swing
    assert np.degrees(sto["tibia_r.ang_vel_z"]).max() > 300
