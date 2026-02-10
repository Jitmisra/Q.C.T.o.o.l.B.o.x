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

from osipy_qc.registry import register_qc_check, get_qc_check, list_qc_checks
from osipy_qc.pipeline import run_qc
from osipy_qc.verdict import Verdict

__all__ = [
    "register_qc_check",
    "get_qc_check",
    "list_qc_checks",
    "run_qc",
    "Verdict",
]

__version__ = "0.1.0"
