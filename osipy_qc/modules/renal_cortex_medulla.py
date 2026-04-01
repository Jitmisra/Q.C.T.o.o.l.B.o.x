"""
renal_cortex_medulla.py — Kidney cortex-medulla contrast QC (stub).

Checks whether the perfusion ratio between renal cortex and medulla
falls within the expected 3:1 to 5:1 range. A low ratio may indicate
failed labeling or severe chronic kidney disease (CKD).

This module demonstrates multi-organ extensibility of the QC Toolbox.
Full implementation is planned for the GSoC coding period.

Status: STUB — registers with the pipeline but raises NotImplementedError.

References:
    Nery F et al. (2020). "Consensus-based technical recommendations
    for clinical translation of renal ASL MRI." MAGMA, 33: 141-161.
    doi: 10.1007/s10334-019-00823-y

    Li LP et al. (2017). "Renal perfusion by MRI." In: Functional
    Imaging in Oncology, pp 175-196. doi: 10.1007/978-3-319-49830-2_12
"""

from __future__ import annotations

from typing import Any

import numpy as np

from osipy_qc.registry import register_qc_check, BaseQCCheck, ModuleResult
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


@register_qc_check("renal_cortex_medulla")
class RenalCortexMedullaCheck(BaseQCCheck):
    """
    Kidney cortex-medulla contrast QC module (stub).

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

    What this module will check (planned for GSoC):
        1. Mean cortex perfusion within expected range (200-450)
        2. Mean medulla perfusion within expected range (30-120)
        3. Cortex/medulla ratio within 3:1 to 5:1
        4. T1 blood correction warning if hematocrit < 0.30
        5. Verdict: PASS / WARN / FAIL based on ratio thresholds
    """

    required_inputs = ["perfusion_map", "cortex_mask", "medulla_mask"]

    def run(self, data: dict[str, Any], config: dict[str, Any]) -> ModuleResult:
        # TODO: implement during GSoC coding period
        #
        # Planned implementation:
        #   cortex_cbf = data["perfusion_map"][data["cortex_mask"] > 0.5]
        #   medulla_cbf = data["perfusion_map"][data["medulla_mask"] > 0.5]
        #   ratio = np.mean(cortex_cbf) / np.mean(medulla_cbf)
        #   hct = data.get("hematocrit")
        #   if hct is not None and hct < 0.30:
        #       warn about T1 blood correction needed
        #
        raise NotImplementedError(
            "renal_cortex_medulla module is a stub. "
            "Full implementation planned for GSoC 2026 coding period. "
            "See proposal section 6.7 for design details."
        )
