import dropfoot


def test_package_imports():
    assert dropfoot.__version__


def test_companion_package_imports():
    from scone_gait.storage import read_sto  # noqa: F401
    from scone_gait.cycles import extract_gait_cycles  # noqa: F401


def test_root_points_at_repository():
    assert (dropfoot.ROOT / "pyproject.toml").exists()
