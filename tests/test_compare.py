import numpy as np
import pytest

from dropfoot.compare import agreement


def test_agreement_separates_offset_from_shape():
    x = np.linspace(0, 2 * np.pi, 101)
    ref = 10 * np.sin(x)
    a = agreement(ref + 3.0, ref)
    assert a["offset"] == pytest.approx(3.0)
    assert a["rmse"] == pytest.approx(3.0)
    assert a["rmse_no_offset"] == pytest.approx(0.0, abs=1e-12)
    assert a["r"] == pytest.approx(1.0)


def test_agreement_shape_error():
    x = np.linspace(0, 2 * np.pi, 101)
    a = agreement(np.cos(x), np.sin(x))
    assert abs(a["r"]) < 0.05
    assert a["rmse"] == pytest.approx(1.0, rel=0.02)
