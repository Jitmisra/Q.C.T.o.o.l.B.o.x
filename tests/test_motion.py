"""Tests for motion module (FWD and DVARS)."""

import numpy as np

from osipy_qc.modules.motion import MotionCheck, compute_dvars, compute_fwd
from osipy_qc.verdict import Verdict


def test_fwd_stationary():
    """Perfectly still subject should have zero FWD."""
    # 60 volumes, no motion
    params = np.zeros((60, 6))
    fwd = compute_fwd(params)
    assert np.allclose(fwd, 0.0), "Stationary subject should have FWD=0"


def test_fwd_pure_translation():
    """1mm step in X at frame 30 should produce FWD=1mm."""
    params = np.zeros((60, 6))
    params[30:, 3] = 1.0  # 1mm step in trans_x
    fwd = compute_fwd(params)
    assert fwd[29] == 1.0, "1mm step should give FWD=1mm"
    assert fwd[0] == 0.0, "No motion at first frame"


def test_fwd_rotation():
    """1-degree rotation should produce ~0.87mm FWD at 50mm radius."""
    params = np.zeros((60, 6))
    params[30:, 0] = np.radians(1.0)  # 1 degree around X
    fwd = compute_fwd(params, radius_mm=50.0)

    expected = np.radians(1.0) * 50.0  # ~0.873 mm
    assert abs(fwd[29] - expected) < 0.01, f"Expected ~{expected:.3f}mm, got {fwd[29]:.3f}"


def test_dvars_constant_signal():
    """Constant signal should produce zero DVARS."""
    asl = np.ones((10, 10, 10, 60))
    mask = np.ones((10, 10, 10), dtype=bool)
    dvars = compute_dvars(asl, mask)
    assert np.allclose(dvars, 0.0)


def test_dvars_spike():
    """Signal spike should produce high DVARS at that timepoint."""
    np.random.default_rng(42)
    asl = np.ones((10, 10, 10, 60)) * 1000
    asl[..., 30] += 500  # 50% signal spike at frame 30
    mask = np.ones((10, 10, 10), dtype=bool)

    dvars = compute_dvars(asl, mask)
    assert dvars[29] > 400, "Spike should produce high DVARS"
    assert dvars[0] < 1, "No change at first frame"


def test_motion_check_low_motion():
    """Low motion should produce PASS verdict."""
    rng = np.random.default_rng(42)
    params = rng.normal(0, 0.001, (60, 6))  # tiny jitter

    data = {"motion_params": params}
    config = {"fwd_fail_above": 1.5, "fwd_warn_above": 0.5}

    check = MotionCheck()
    result = check.run(data, config)

    assert result.verdict == Verdict.PASS
    assert result.metrics["mean_fwd_mm"] < 0.5


def test_motion_check_high_motion():
    """High motion should produce FAIL verdict."""
    params = np.zeros((60, 6))
    # Progressive drift: 0.5mm per frame
    params[:, 3] = np.linspace(0, 100, 60)

    data = {"motion_params": params}
    config = {"fwd_fail_above": 1.5, "fwd_warn_above": 0.5}

    check = MotionCheck()
    result = check.run(data, config)

    assert result.verdict == Verdict.FAIL
