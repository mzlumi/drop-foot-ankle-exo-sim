import pytest

from dropfoot import scenarios


@pytest.mark.parametrize("factor", [0.5, 0.25, 0.1])
def test_committed_dropfoot_scenarios_match_template(factor):
    path = scenarios.SCENARIOS / f"dropfoot_{scenarios.strength_tag(factor)}.scone"
    assert path.read_text() == scenarios.dropfoot_scenario(factor)


def test_template_sets_only_tib_ant_r():
    text = scenarios.dropfoot_scenario(0.175)
    assert "tib_ant_r { max_isometric_force.factor = 0.175 }" in text
    assert "tib_ant_l" not in text
    assert "ControllerGH2010asym.scone" in text
    assert "Apache-2.0" in text


def test_generated_scenarios_point_two_folders_up(tmp_path, monkeypatch):
    monkeypatch.setattr(scenarios, "SCENARIOS", tmp_path)
    path = scenarios.write_dropfoot(0.3, tmp_path / "generated")
    text = path.read_text()
    assert "model_file = ../../data/raw/scone-tutorials/data/Human0914.osim" in text
    assert "<< ../include/MeasureGait12.scone >>" in text
    assert "init_file = ../../results/healthy/seed1/healthy_asym.par" in text


def test_strength_tag():
    assert scenarios.strength_tag(0.25) == "ta25"
    assert scenarios.strength_tag(0.175) == "ta17.5"
    with pytest.raises(ValueError):
        scenarios.dropfoot_scenario(0.0)
