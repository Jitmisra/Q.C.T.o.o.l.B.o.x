#!/usr/bin/env python3
"""
demo.py — Quick demonstration of the osipy-qc pipeline.

Shows:
1. Module discovery via registry
2. Core modules running on minimal inputs (CBF + tissue maps)
3. Extension modules gracefully degrading to UNKNOWN
4. Full pipeline with all inputs provided
5. Population-specific config switching
"""

import json
import numpy as np
from osipy_qc import run_qc, list_qc_checks, Verdict
from osipy_qc.config import QCConfig


def make_synthetic_brain(quality="good", shape=(20, 20, 20)):
    """Generate synthetic brain data with controllable quality."""
    rng = np.random.default_rng(42)

    # Tissue probability maps
    gm = np.zeros(shape)
    gm[4:16, 4:16, 4:16] = 0.9
    gm[7:13, 7:13, 7:13] = 0.0

    wm = np.zeros(shape)
    wm[7:13, 7:13, 7:13] = 0.85

    csf = np.zeros(shape)
    csf[9:11, 9:11, 9:11] = 0.7

    # CBF map with controllable quality
    if quality == "good":
        cbf = 50.0 * gm + 20.0 * wm + rng.normal(0, 3, shape)
    elif quality == "noisy":
        cbf = 50.0 * gm + 20.0 * wm + rng.normal(0, 25, shape)
    elif quality == "terrible":
        cbf = rng.normal(0, 50, shape)  # pure noise
    else:
        cbf = 50.0 * gm + 20.0 * wm

    return cbf, gm, wm, csf


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(result):
    overall = result["overall_verdict"]
    color = {"PASS": "\033[92m", "WARN": "\033[93m", "FAIL": "\033[91m", "UNKNOWN": "\033[90m"}
    reset = "\033[0m"

    print(f"\n  Overall Verdict: {color.get(overall, '')}{overall}{reset}")
    print(f"  Config Profile:  {result['config_profile']}")
    print()

    for name, mod in result["modules"].items():
        v = mod["verdict"]
        icon = {"PASS": "+", "WARN": "~", "FAIL": "!", "UNKNOWN": "?"}
        c = color.get(v, "")
        print(f"  [{icon.get(v, ' ')}] {name:20s}  {c}{v:7s}{reset}", end="")
        if mod.get("reason"):
            print(f"  ({mod['reason']})", end="")
        print()

        # Print key metrics
        for k, val in mod.get("metrics", {}).items():
            if isinstance(val, float):
                print(f"      {k}: {val}")

    if result["modules_skipped"]:
        print(f"\n  Skipped (missing inputs): {', '.join(result['modules_skipped'])}")


# ============================================================
# Demo 1: Module Discovery
# ============================================================
print_header("1. Registered QC Modules")
modules = list_qc_checks()
print(f"\n  {len(modules)} modules registered via @register_qc_check:")
for m in modules:
    print(f"    - {m}")

# ============================================================
# Demo 2: Core-only (minimal inputs = graceful degradation)
# ============================================================
print_header("2. Core Layer Only (CBF + tissue maps)")
print("  Extension modules will gracefully degrade to UNKNOWN")

cbf, gm, wm, csf = make_synthetic_brain("good")
result = run_qc({"cbf_map": cbf, "gm_prob": gm, "wm_prob": wm, "csf_prob": csf})
print_result(result)

# ============================================================
# Demo 3: Full pipeline (all inputs)
# ============================================================
print_header("3. Full Pipeline (all inputs provided)")

rng = np.random.default_rng(42)
full_data = {
    "cbf_map": cbf,
    "gm_prob": gm,
    "wm_prob": wm,
    "csf_prob": csf,
    "motion_params": rng.normal(0, 0.01, (60, 6)),
    "asl_context": ["control", "label"] * 30,
    "asl_json": {
        "ArterialSpinLabelingType": "PCASL",
        "PostLabelingDelay": 1.8,
        "LabelingDuration": 1.8,
    },
    "n_volumes": 60,
    "m0_data": rng.normal(1000, 50, gm.shape),
    "m0_json": {"RepetitionTime": 6.0},
}

result = run_qc(full_data)
print_result(result)

# ============================================================
# Demo 4: Bad scan detection
# ============================================================
print_header("4. Bad Scan Detection (noisy CBF)")

bad_cbf, gm, wm, csf = make_synthetic_brain("terrible")
result = run_qc({"cbf_map": bad_cbf, "gm_prob": gm, "wm_prob": wm, "csf_prob": csf})
print_result(result)

# ============================================================
# Demo 5: Population-specific configs
# ============================================================
print_header("5. Population-Specific Configs")

adult_config = QCConfig.from_yaml("configs/adult_3T.yaml")
neonatal_config = QCConfig.from_yaml("configs/neonatal_chd.yaml")

data = {"cbf_map": cbf, "gm_prob": gm, "wm_prob": wm, "csf_prob": csf}

print("\n  Same scan, two profiles:\n")
r1 = run_qc(data, config=adult_config)
r2 = run_qc(data, config=neonatal_config)

qei1 = r1["modules"]["qei"]["metrics"]["qei"]
qei2 = r2["modules"]["qei"]["metrics"]["qei"]

print(f"  Adult 3T:       QEI={qei1:.3f}  ->  {r1['overall_verdict']}")
print(f"  Neonatal CHD:   QEI={qei2:.3f}  ->  {r2['overall_verdict']}")

# ============================================================
# Demo 6: JSON report output
# ============================================================
print_header("6. JSON Report Output")
print(f"\n{json.dumps(result, indent=2)}")

print(f"\n{'='*60}")
print("  Done. 5 modules, 33 tests, pure numpy, zero scipy.")
print(f"{'='*60}\n")
