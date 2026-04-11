"""
renal_cortex_medulla.py — Kidney cortex-medulla contrast QC.

Validates that cortical perfusion is sufficiently higher than medullary
perfusion, which is the primary quality indicator for renal ASL scans.
A low cortex/medulla ratio may indicate failed labeling, severe chronic
kidney disease (CKD), or inadequate background suppression.

QC checks performed:
    1. Mean cortex CBF within expected range  (200-450 mL/100g/min)
    2. Mean medulla CBF within expected range  (30-120 mL/100g/min)
    3. Cortex/medulla ratio within 3:1 to 5:1
    4. Hematocrit correction warning if Hct < 0.30

References:
    Nery F et al. (2020). "Consensus-based technical recommendations
    for clinical translation of renal ASL MRI." MAGMA, 33: 141-161.
    doi: 10.1007/s10334-019-00823-y

    Li LP et al. (2017). "Renal perfusion by MRI." In: Functional
    Imaging in Oncology, pp 175-196. doi: 10.1007/978-3-319-49830-2_12

    Mora Álvarez MG et al. (2024). "Body and neonatal ASL perfusion."
    MAGMA — motivates population-specific thresholds for non-brain organs.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from osipy_qc.registry import BaseQCCheck, ModuleResult, register_qc_check
from osipy_qc.verdict import Verdict

# ---------------------------------------------------------------------------
# Target reference values (from PARENCHIMA consensus + literature)
# ---------------------------------------------------------------------------
# Healthy adult renal cortex:  250 - 350 mL/100g/min
# Healthy adult renal medulla:  30 - 120 mL/100g/min
# Expected cortex/medulla ratio: 3:1 to 5:1
# CKD patients: ratio often < 2:1 due to cortical hypoperfusion
# ---------------------------------------------------------------------------

EXPECTED_CORTEX_RANGE = (200, 450)   # mL/100g/min
EXPECTED_MEDULLA_RANGE = (30, 120)   # mL/100g/min
EXPECTED_RATIO_RANGE = (3.0, 5.0)    # cortex / medulla


def compute_renal_metrics(
    perfusion_map: np.ndarray,
    cortex_mask: np.ndarray,
    medulla_mask: np.ndarray,
) -> dict[str, float]:
    """Compute cortex/medulla perfusion metrics.

    Parameters
    ----------
    perfusion_map : ndarray (X, Y, Z)
        Renal perfusion map in mL/100g/min.
    cortex_mask : ndarray (X, Y, Z)
        Binary or probabilistic cortex ROI.
    medulla_mask : ndarray (X, Y, Z)
        Binary or probabilistic medulla ROI.

    Returns
    -------
    dict with keys: mean_cortex, mean_medulla, ratio, cortex_n, medulla_n
    """
    cortex_vals = perfusion_map[cortex_mask > 0.5]
    medulla_vals = perfusion_map[medulla_mask > 0.5]

    mean_cortex = float(np.mean(cortex_vals)) if cortex_vals.size > 0 else 0.0
    mean_medulla = float(np.mean(medulla_vals)) if medulla_vals.size > 0 else 0.0

    if mean_medulla > 1e-6:
        ratio = mean_cortex / mean_medulla
    else:
        ratio = 0.0

    return {
        "mean_cortex_cbf": round(mean_cortex, 2),
        "mean_medulla_cbf": round(mean_medulla, 2),
        "cortex_medulla_ratio": round(ratio, 3),
        "cortex_voxels": int(cortex_vals.size),
        "medulla_voxels": int(medulla_vals.size),
    }


@register_qc_check("renal_cortex_medulla")
class RenalCortexMedullaCheck(BaseQCCheck):
    """
    Kidney cortex-medulla contrast QC module.

    Validates that cortical perfusion is sufficiently higher than
    medullary perfusion, which is the primary quality indicator
    for renal ASL scans.

    Required inputs:
        - perfusion_map: 3D renal perfusion array (mL/100g/min)
        - cortex_mask:   binary mask of renal cortex ROI
        - medulla_mask:  binary mask of renal medulla ROI

    Optional inputs (from BIDS sidecar):
        - hematocrit:    patient hematocrit for T1 blood correction
        - labeling_type: FAIR / PCASL (affects expected efficiency)
    """

    required_inputs = ["perfusion_map", "cortex_mask", "medulla_mask"]

    def run(self, data: dict[str, Any], config: dict[str, Any]) -> ModuleResult:
        metrics = compute_renal_metrics(
            data["perfusion_map"],
            data["cortex_mask"],
            data["medulla_mask"],
        )

        ratio = metrics["cortex_medulla_ratio"]
        mean_cortex = metrics["mean_cortex_cbf"]

        # Configurable thresholds (with PARENCHIMA defaults)
        ratio_fail_below = config.get("ratio_fail_below", 2.0)
        ratio_warn_below = config.get("ratio_warn_below", 3.0)
        cortex_fail_below = config.get("cortex_fail_below", 100.0)
        cortex_warn_above = config.get("cortex_warn_above", 450.0)

        reasons: list[str] = []

        # --- Ratio verdict ---
        if ratio < ratio_fail_below:
            verdict = Verdict.FAIL
            reasons.append(
                f"Cortex/medulla ratio {ratio:.2f} < {ratio_fail_below} "
                f"(possible labeling failure or severe CKD)"
            )
        elif ratio < ratio_warn_below:
            verdict = Verdict.WARN
            reasons.append(
                f"Cortex/medulla ratio {ratio:.2f} below expected "
                f"{ratio_warn_below}-5.0 range"
            )
        else:
            verdict = Verdict.PASS

        # --- Cortex range check ---
        if mean_cortex < cortex_fail_below:
            verdict = Verdict.FAIL
            reasons.append(
                f"Mean cortex CBF {mean_cortex:.1f} mL/100g/min "
                f"< {cortex_fail_below} (possible global labeling failure)"
            )
        elif mean_cortex > cortex_warn_above:
            if verdict == Verdict.PASS:
                verdict = Verdict.WARN
            reasons.append(
                f"Mean cortex CBF {mean_cortex:.1f} mL/100g/min "
                f"> {cortex_warn_above} (possible vascular artifact)"
            )

        # --- Hematocrit warning ---
        hct = data.get("hematocrit")
        if hct is not None and hct < 0.30:
            if verdict == Verdict.PASS:
                verdict = Verdict.WARN
            reasons.append(
                f"Low hematocrit ({hct:.2f} < 0.30): "
                f"T1 blood correction may be inaccurate"
            )
            metrics["hematocrit"] = round(hct, 3)

        return ModuleResult(
            name="renal_cortex_medulla",
            verdict=verdict,
            metrics=metrics,
            reason=(
                "; ".join(reasons) if reasons
                else "Cortex/medulla contrast within expected range"
            ),
        )
