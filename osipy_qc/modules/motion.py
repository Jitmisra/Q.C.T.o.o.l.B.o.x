"""
motion.py — Frame-wise displacement (Power et al., 2012, NeuroImage).

FWD = sum(|d_translations|) + sum(|d_rotations| * 50mm)

The 50mm radius projects rotations (radians) onto the cortical surface
so they become comparable to translations (mm). A 1-degree head nod
translates to ~0.87mm of cortical displacement.

Extension layer module: requires raw ASL 4D + motion parameters.

Reference:
    Power JD et al. (2012). "Spurious but systematic correlations in
    functional connectivity MRI networks arise from subject motion."
    NeuroImage, 59(3): 2142-2154.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from osipy_qc.registry import register_qc_check, BaseQCCheck, ModuleResult
from osipy_qc.verdict import Verdict, verdict_from_thresholds


def compute_fwd(motion_params: np.ndarray, radius_mm: float = 50.0) -> np.ndarray:
    """
    Compute framewise displacement from rigid-body motion parameters.

    Parameters
    ----------
    motion_params : ndarray, shape (T, 6)
        Columns: [rot_x, rot_y, rot_z, trans_x, trans_y, trans_z]
        Rotations in radians, translations in mm.
    radius_mm : float
        Radius for projecting rotations to mm (default 50mm,
        approximating brain center to cortical surface).

    Returns
    -------
    fwd : ndarray, shape (T-1,)
        Frame-wise displacement for each consecutive pair.
    """
    if motion_params.shape[0] < 2:
        return np.array([0.0])

    diff = np.diff(motion_params, axis=0)  # (T-1, 6)

    # Rotations (first 3 cols) -> mm displacement on cortical surface
    rot_disp = np.abs(diff[:, :3]) * radius_mm    # radians * mm
    trans_disp = np.abs(diff[:, 3:])                # mm

    fwd = rot_disp.sum(axis=1) + trans_disp.sum(axis=1)
    return fwd


def compute_dvars(asl_4d: np.ndarray, brain_mask: np.ndarray) -> np.ndarray:
    """
    Compute DVARS (Derivative of RMS VARiance of Signal).

    Measures RMS intensity change between consecutive volumes
    across all brain voxels. Catches signal instabilities that
    pure displacement metrics miss (RF interference, gradient heating).

    Parameters
    ----------
    asl_4d : ndarray, shape (X, Y, Z, T)
    brain_mask : ndarray bool, shape (X, Y, Z)

    Returns
    -------
    dvars : ndarray, shape (T-1,)
    """
    if asl_4d.shape[-1] < 2:
        return np.array([0.0])

    masked = asl_4d[brain_mask]  # (n_voxels, T)
    diff = np.diff(masked, axis=1)  # (n_voxels, T-1)
    dvars = np.sqrt(np.mean(diff ** 2, axis=0))
    return dvars


@register_qc_check("motion")
class MotionCheck(BaseQCCheck):
    """
    Motion tracking — extension layer module.

    Computes FWD (Power 2012) and optionally DVARS.
    Falls back to UNKNOWN if motion params aren't available.
    """

    required_inputs = ["motion_params"]

    def run(self, data: dict[str, Any], config: dict[str, Any]) -> ModuleResult:
        motion_params = data["motion_params"]

        fwd = compute_fwd(motion_params)
        mean_fwd = float(fwd.mean())
        max_fwd = float(fwd.max())
        n_flagged = int((fwd > config.get("fwd_warn_above", 0.5)).sum())

        metrics: dict[str, Any] = {
            "mean_fwd_mm": round(mean_fwd, 4),
            "max_fwd_mm": round(max_fwd, 4),
            "n_volumes_flagged": n_flagged,
            "n_volumes_total": len(fwd),
        }

        # DVARS if raw 4D is available
        asl_4d = data.get("asl_4d")
        gm_prob = data.get("gm_prob")
        if asl_4d is not None and gm_prob is not None:
            brain_mask = gm_prob > 0.1
            dvars = compute_dvars(asl_4d, brain_mask)
            metrics["mean_dvars"] = round(float(dvars.mean()), 4)

        v = verdict_from_thresholds(
            mean_fwd,
            fail_above=config.get("fwd_fail_above", 1.5),
            warn_above=config.get("fwd_warn_above", 0.5),
        )

        reason = ""
        if v == Verdict.FAIL:
            reason = f"Mean FWD {mean_fwd:.2f}mm exceeds FAIL threshold"
        elif v == Verdict.WARN:
            reason = f"Mean FWD {mean_fwd:.2f}mm exceeds WARN threshold"

        return ModuleResult(name="motion", verdict=v, metrics=metrics, reason=reason)
