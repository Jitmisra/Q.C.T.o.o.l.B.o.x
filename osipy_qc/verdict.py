"""
verdict.py — PASS / WARN / FAIL / UNKNOWN verdict engine.

Conservative fail-fast logic: any single FAIL condemns the scan.
Graceful degradation: modules that can't run (missing inputs)
return UNKNOWN instead of crashing the pipeline.
"""

from __future__ import annotations

from enum import Enum


class Verdict(Enum):
    """Quality verdict for a single module or overall scan."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"  # module couldn't run (missing inputs)


def combine_verdicts(verdicts: list[Verdict]) -> Verdict:
    """
    Combine per-module verdicts into an overall scan verdict.

    Rules (conservative, fail-fast):
    - Any FAIL -> overall FAIL
    - Any WARN (and no FAIL) -> overall WARN
    - All PASS (ignoring UNKNOWN) -> overall PASS
    - UNKNOWN modules are noted but don't block the verdict
    """
    evaluated = [v for v in verdicts if v != Verdict.UNKNOWN]

    if not evaluated:
        return Verdict.UNKNOWN

    if Verdict.FAIL in evaluated:
        return Verdict.FAIL

    if Verdict.WARN in evaluated:
        return Verdict.WARN

    return Verdict.PASS


def verdict_from_thresholds(
    value: float,
    *,
    fail_below: float | None = None,
    fail_above: float | None = None,
    warn_below: float | None = None,
    warn_above: float | None = None,
) -> Verdict:
    """
    Determine verdict by comparing a metric value against thresholds.

    Parameters
    ----------
    value : metric value to evaluate
    fail_below / fail_above : FAIL if value is below/above this
    warn_below / warn_above : WARN if value is below/above this

    Returns
    -------
    Verdict (FAIL, WARN, or PASS)
    """
    if fail_below is not None and value < fail_below:
        return Verdict.FAIL
    if fail_above is not None and value > fail_above:
        return Verdict.FAIL
    if warn_below is not None and value < warn_below:
        return Verdict.WARN
    if warn_above is not None and value > warn_above:
        return Verdict.WARN
    return Verdict.PASS
