"""
osipy_qc — ASL CBF map quality control for osipy.

A standalone, pipeline-agnostic QC and triage engine for Arterial Spin
Labeling (ASL) cerebral blood flow (CBF) maps.  Mirrors osipy's
``@register_*(name)`` / ``get_*(name)`` / ``list_*()`` registry pattern
so modules integrate naturally into the OSIPI ecosystem.

Usage
-----
>>> from osipy_qc import run_qc
>>> result = run_qc("path/to/bids", subject="sub-01", config="adult_3T")
"""

from osipy_qc.pipeline import export_batch_csv, export_batch_json, run_qc
from osipy_qc.registry import get_qc_check, list_qc_checks, register_qc_check
from osipy_qc.threshold import compare_methods, plot_threshold_comparison
from osipy_qc.verdict import Verdict

__all__ = [
    # Registry
    "register_qc_check",
    "get_qc_check",
    "list_qc_checks",
    # Pipeline
    "run_qc",
    "export_batch_csv",
    "export_batch_json",
    # Threshold derivation
    "compare_methods",
    "plot_threshold_comparison",
    # Verdict
    "Verdict",
]

__version__ = "0.1.0"

