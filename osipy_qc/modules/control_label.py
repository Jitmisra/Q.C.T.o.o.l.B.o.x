"""
control_label.py — BIDS ASL control-label ordering validation.

Validates ordering through 4 layers based on the BIDS ASL extension
(Clement et al., 2022, Scientific Data):

1. Schema:  Required BIDS fields present?
2. Dimensions: TSV row count matches NIfTI volume count?
3. Pattern: _aslcontext.tsv entries match expected alternation?
4. Intensity: Without bg suppression, mean(control) > mean(label)?

Extension layer module: requires asl_context + asl_json.

Reference:
    Clement P. et al. (2022). "ASL-BIDS, the brain imaging data
    structure extension for ASL." Scientific Data, 9, 543.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from osipy_qc.registry import register_qc_check, BaseQCCheck, ModuleResult
from osipy_qc.verdict import Verdict


# Required BIDS JSON fields for PCASL
REQUIRED_PCASL_FIELDS = [
    "ArterialSpinLabelingType",
    "PostLabelingDelay",
    "LabelingDuration",
]


def validate_schema(asl_json: dict) -> tuple[bool, str]:
    """Check that required BIDS fields are present."""
    missing = [f for f in REQUIRED_PCASL_FIELDS if f not in asl_json]
    if missing:
        return False, f"Missing BIDS fields: {', '.join(missing)}"
    return True, ""


def validate_dimensions(
    asl_context: list[str],
    n_volumes: int | None,
) -> tuple[bool, str]:
    """Check TSV row count matches NIfTI volume count."""
    if n_volumes is None:
        return True, "No volume count available for cross-check"

    if len(asl_context) != n_volumes:
        return False, (
            f"aslcontext has {len(asl_context)} rows but "
            f"NIfTI has {n_volumes} volumes"
        )
    return True, ""


def validate_pattern(asl_context: list[str]) -> tuple[bool, str]:
    """
    Validate ordering pattern.

    Three BIDS cases:
    - Case 1: control/label alternation (standard)
    - Case 2: deltam (already subtracted)
    - Case 3: cbf (already quantified)
    """
    if not asl_context:
        return False, "Empty aslcontext"

    types = set(asl_context)

    # Case 2: deltam only
    if types == {"deltam"} or types <= {"deltam", "m0scan"}:
        return True, "Case 2: deltam volumes (already subtracted)"

    # Case 3: cbf only
    if types == {"cbf"} or types <= {"cbf", "m0scan"}:
        return True, "Case 3: cbf volumes (already quantified)"

    # Case 1: control/label alternation
    non_m0 = [v for v in asl_context if v != "m0scan"]
    for i, vol_type in enumerate(non_m0):
        expected = "control" if i % 2 == 0 else "label"
        if vol_type not in ("control", "label"):
            return False, f"Unexpected volume type '{vol_type}' at position {i}"
        if vol_type != expected:
            return False, (
                f"Ordering error at position {i}: "
                f"expected '{expected}', got '{vol_type}'"
            )

    return True, "Case 1: valid control-label alternation"


def check_swap(
    asl_4d: np.ndarray,
    asl_context: list[str],
    bg_suppression: bool = False,
) -> tuple[bool, str]:
    """
    Intensity-based swap detection.

    Without background suppression, mean(control) should be > mean(label).
    Inverted relationship suggests swapped ordering -> globally negative CBF.
    """
    if bg_suppression:
        return False, "Skipped: background suppression active"

    control_idx = [i for i, v in enumerate(asl_context) if v == "control"]
    label_idx = [i for i, v in enumerate(asl_context) if v == "label"]

    if not control_idx or not label_idx:
        return False, "No control/label pairs found"

    mean_control = float(np.mean([
        asl_4d[..., i].mean() for i in control_idx
    ]))
    mean_label = float(np.mean([
        asl_4d[..., i].mean() for i in label_idx
    ]))

    if mean_label > mean_control:
        return True, (
            f"SWAP DETECTED: mean(label)={mean_label:.1f} > "
            f"mean(control)={mean_control:.1f}"
        )
    return False, ""


@register_qc_check("control_label")
class ControlLabelCheck(BaseQCCheck):
    """
    Control-label ordering validation — extension layer module.

    The most dangerous single error in ASL: swapped control-label
    ordering yields globally negative CBF.
    """

    required_inputs = ["asl_context", "asl_json"]

    def run(self, data: dict[str, Any], config: dict[str, Any]) -> ModuleResult:
        asl_context = data["asl_context"]
        asl_json = data["asl_json"]
        n_volumes = data.get("n_volumes")
        asl_4d = data.get("asl_4d")

        issues: list[str] = []

        # Layer 1: Schema validation
        ok, msg = validate_schema(asl_json)
        if not ok:
            issues.append(msg)

        # Layer 2: Dimension check
        ok, msg = validate_dimensions(asl_context, n_volumes)
        if not ok:
            issues.append(msg)

        # Layer 3: Pattern validation
        pattern_ok, pattern_msg = validate_pattern(asl_context)
        if not pattern_ok:
            issues.append(pattern_msg)

        # Layer 4: Intensity-based swap detection
        swap_detected = False
        if asl_4d is not None:
            bg_supp = asl_json.get("BackgroundSuppression", False)
            swap_detected, swap_msg = check_swap(
                asl_4d, asl_context, bg_suppression=bg_supp
            )
            if swap_detected:
                issues.append(swap_msg)

        # Verdict: swap = always FAIL, missing fields = WARN
        if swap_detected:
            verdict = Verdict.FAIL
        elif issues:
            verdict = Verdict.WARN
        else:
            verdict = Verdict.PASS

        return ModuleResult(
            name="control_label",
            verdict=verdict,
            metrics={
                "ordering_valid": pattern_ok,
                "swap_detected": swap_detected,
                "pattern_info": pattern_msg,
                "n_issues": len(issues),
            },
            reason="; ".join(issues) if issues else "",
        )
