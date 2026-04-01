"""
pipeline.py — QC pipeline orchestrator.

Discovers registered modules, checks input availability, runs each
module, and combines verdicts.  Modules with missing inputs return
UNKNOWN instead of crashing (graceful degradation).
"""

from __future__ import annotations

from typing import Any

# Import modules to trigger registration
from osipy_qc.config import QCConfig
from osipy_qc.registry import ModuleResult, get_qc_check, list_qc_checks
from osipy_qc.verdict import Verdict, combine_verdicts

# Import modules to trigger registration
import osipy_qc.modules.control_label  # noqa: F401
import osipy_qc.modules.m0_check  # noqa: F401
import osipy_qc.modules.motion  # noqa: F401
import osipy_qc.modules.qei  # noqa: F401
import osipy_qc.modules.renal_cortex_medulla  # noqa: F401
import osipy_qc.modules.snr_cov  # noqa: F401


def run_qc(
    data: dict[str, Any],
    config: QCConfig | None = None,
    modules: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run the full QC pipeline on one subject's data.

    Parameters
    ----------
    data : dict
        Available data keyed by name. Common keys:
        - "cbf_map": np.ndarray (X, Y, Z) — CBF in mL/100g/min
        - "gm_prob": np.ndarray (X, Y, Z) — GM probability [0, 1]
        - "wm_prob": np.ndarray (X, Y, Z) — WM probability [0, 1]
        - "csf_prob": np.ndarray (X, Y, Z) — CSF probability [0, 1]
        - "asl_4d": np.ndarray (X, Y, Z, T) — raw ASL time series
        - "motion_params": np.ndarray (T, 6) — rigid-body params
        - "asl_context": list[str] — volume types from _aslcontext.tsv
        - "asl_json": dict — BIDS JSON sidecar
        - "m0_data": np.ndarray — M0 calibration image
        - "m0_json": dict — M0 JSON sidecar
    config : QCConfig, optional
        Population-specific thresholds. Defaults to adult 3T PCASL.
    modules : list[str], optional
        Subset of modules to run. Defaults to all registered.

    Returns
    -------
    dict with keys:
        "overall_verdict": str
        "modules": dict[str, module_result_dict]
        "modules_skipped": list[str]  (returned UNKNOWN)
        "config_profile": str
    """
    if config is None:
        config = QCConfig.default()

    module_names = modules or list_qc_checks()
    results: list[ModuleResult] = []
    skipped: list[str] = []

    for name in module_names:
        mod_config = config.get_module_config(name)

        if not mod_config.enabled:
            skipped.append(name)
            continue

        check = get_qc_check(name)

        # Graceful degradation: if required inputs are missing,
        # return UNKNOWN instead of crashing
        if not check.can_run(data):
            missing = [k for k in check.required_inputs
                       if k not in data or data[k] is None]
            result = ModuleResult(
                name=name,
                verdict=Verdict.UNKNOWN,
                reason=f"Missing inputs: {', '.join(missing)}",
            )
            results.append(result)
            skipped.append(name)
            continue

        result = check.run(data, mod_config.thresholds)
        results.append(result)

    overall = combine_verdicts([r.verdict for r in results])

    return {
        "overall_verdict": overall.value,
        "modules": {r.name: r.to_dict() for r in results},
        "modules_skipped": skipped,
        "config_profile": config.profile_name,
    }
