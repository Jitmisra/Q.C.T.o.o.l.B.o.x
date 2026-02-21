"""Tests for the QC module registry pattern."""

from osipy_qc.registry import (
    register_qc_check,
    get_qc_check,
    list_qc_checks,
    BaseQCCheck,
    ModuleResult,
)
from osipy_qc.verdict import Verdict


def test_list_qc_checks():
    """All 5 modules should be registered."""
    checks = list_qc_checks()
    assert "qei" in checks
    assert "motion" in checks
    assert "control_label" in checks
    assert "m0_check" in checks
    assert "snr_cov" in checks
    assert len(checks) >= 5


def test_get_qc_check():
    """Retrieving a registered module returns a BaseQCCheck instance."""
    check = get_qc_check("qei")
    assert isinstance(check, BaseQCCheck)
    assert hasattr(check, "run")
    assert hasattr(check, "can_run")
    assert hasattr(check, "required_inputs")


def test_get_unknown_check():
    """Requesting unknown module raises KeyError."""
    import pytest
    with pytest.raises(KeyError, match="Unknown QC check"):
        get_qc_check("nonexistent_module")


def test_can_run_with_complete_data():
    """can_run() returns True when all required inputs present."""
    check = get_qc_check("qei")
    import numpy as np
    data = {
        "cbf_map": np.zeros((5, 5, 5)),
        "gm_prob": np.zeros((5, 5, 5)),
        "wm_prob": np.zeros((5, 5, 5)),
    }
    assert check.can_run(data) is True


def test_can_run_with_missing_data():
    """can_run() returns False when required inputs are missing."""
    check = get_qc_check("qei")
    data = {"cbf_map": None}
    assert check.can_run(data) is False


def test_can_run_motion_without_params():
    """Motion module correctly reports missing inputs."""
    check = get_qc_check("motion")
    assert check.can_run({}) is False
    assert check.can_run({"cbf_map": None}) is False
