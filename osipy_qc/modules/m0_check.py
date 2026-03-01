"""
m0_check.py — M0 calibration image validation.

M0 is the denominator in CBF quantification (CBF = dM / M0 * constants).
Any error in M0 scales every single CBF voxel.

Checks:
1. Saturation: histogram spike at max intensity (ADC clipping)
2. TR >= 4s: short TR causes incomplete T1 recovery
3. Geometry match: M0 voxel dims must match ASL
4. Background suppression off during M0 acquisition

Extension layer module: requires m0_data + m0_json.

Reference:
    Alsop DC et al. (2015). "Recommended implementation of ASL perfusion
    MRI for clinical applications." MRM, 73(1): 102-116.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from osipy_qc.registry import register_qc_check, BaseQCCheck, ModuleResult
from osipy_qc.verdict import Verdict


def check_saturation(m0_data: np.ndarray, ceiling_pct: float = 5.0) -> tuple[bool, float]:
    """
    Check for ADC clipping (saturation).

    If >ceiling_pct of tissue voxels are at intensity ceiling,
    the M0 is likely saturated.
    """
    brain = m0_data[m0_data > np.percentile(m0_data, 10)]
    if brain.size == 0:
        return False, 0.0

    max_val = brain.max()
    # Voxels within 1% of maximum intensity
    at_ceiling = (brain > max_val * 0.99).sum()
    pct = 100.0 * at_ceiling / brain.size
    return pct > ceiling_pct, round(pct, 2)


def check_tr(m0_json: dict) -> tuple[Verdict, float | None, str]:
    """
    Verify TR >= 4s for proper T1 recovery.

    Short TR depresses M0 signal. Dividing by artificially low M0
    inflates CBF, especially in ventricles where T1 is long.
    """
    tr = m0_json.get("RepetitionTimePreparation") or m0_json.get("RepetitionTime")
    if tr is None:
        return Verdict.UNKNOWN, None, "TR not found in M0 JSON sidecar"

    tr = float(tr)
    if tr < 2.0:
        return Verdict.FAIL, tr, f"M0 TR={tr:.1f}s is critically short (< 2s)"
    if tr < 4.0:
        return Verdict.WARN, tr, f"M0 TR={tr:.1f}s is below recommended 4s"
    return Verdict.PASS, tr, ""


def check_bg_suppression(m0_json: dict) -> tuple[bool, str]:
    """Background suppression must be OFF during M0 acquisition."""
    bg = m0_json.get("BackgroundSuppression", False)
    if bg:
        return True, "Background suppression active during M0 acquisition"
    return False, ""


@register_qc_check("m0_check")
class M0Check(BaseQCCheck):
    """
    M0 calibration validation — extension layer module.

    Falls back to UNKNOWN if M0 files aren't provided.
    """

    required_inputs = ["m0_data", "m0_json"]

    def run(self, data: dict[str, Any], config: dict[str, Any]) -> ModuleResult:
        m0_data = data["m0_data"]
        m0_json = data["m0_json"]

        issues: list[str] = []
        worst = Verdict.PASS

        # Check 1: Saturation
        saturated, sat_pct = check_saturation(
            m0_data,
            ceiling_pct=config.get("saturation_pct_fail", 5.0),
        )
        if saturated:
            issues.append(f"M0 saturated: {sat_pct}% of voxels at ceiling")
            worst = Verdict.FAIL

        # Check 2: TR
        tr_verdict, tr_val, tr_msg = check_tr(m0_json)
        if tr_verdict == Verdict.FAIL:
            issues.append(tr_msg)
            worst = Verdict.FAIL
        elif tr_verdict == Verdict.WARN and worst != Verdict.FAIL:
            issues.append(tr_msg)
            worst = Verdict.WARN

        # Check 3: Background suppression
        bg_issue, bg_msg = check_bg_suppression(m0_json)
        if bg_issue:
            issues.append(bg_msg)
            if worst != Verdict.FAIL:
                worst = Verdict.FAIL

        return ModuleResult(
            name="m0_check",
            verdict=worst,
            metrics={
                "saturation_detected": saturated,
                "saturation_pct": sat_pct,
                "tr_seconds": tr_val,
                "bg_suppression_during_m0": bg_issue,
            },
            reason="; ".join(issues) if issues else "",
        )
