"""Diagnostic phase integration for the documented sub-MHz continuous regime.

This is a source model, not a measurement of synthesizer hardware. Frequency
command delivery times come from the interpreter trace (reset: manual 23.7 us).
Changing MHz banks is deliberately outside this helper's supported regime.
"""
from __future__ import annotations


def accumulated_phase_deg(it, start_us, end_us, reference_hz, *, mhz=None):
    """Integrate (played carrier - reference) between two absolute event times.

    Neither resync nor reset_frequency is treated as a phase reset. The caller
    chooses a common phase origin; a constant phase before excitation is not
    evidence of an echo-dependent CPMG error.
    """
    if end_us < start_us:
        return -accumulated_phase_deg(it, end_us, start_us, reference_hz, mhz=mhz)
    rows = sorted((r for r in it.frequency_events if r["kind"] == "send"),
                  key=lambda r: r["t_us"])
    frequency = reference_hz
    active_mhz = mhz
    cursor = start_us
    phase = 0.0
    for row in rows:
        t = row["t_us"]
        if t <= start_us:
            frequency = row["frequency_hz"]
            active_mhz = row.get("mhz")
        elif t < end_us:
            if mhz is None or active_mhz == mhz:
                phase += (frequency - reference_hz) * (t - cursor) * 0.00036
            cursor = t
            frequency = row["frequency_hz"]
            active_mhz = row.get("mhz")
        else:
            break
    if mhz is None or active_mhz == mhz:
        phase += (frequency - reference_hz) * (end_us - cursor) * 0.00036
    return phase


def rf_centre_phase_deg(it, pulse, origin_us, reference_hz, *, mhz=None):
    """Programmed phase plus accrued carrier phase at the sampled RF centre."""
    return (pulse["phase_deg"] + accumulated_phase_deg(
        it, origin_us, pulse["t_center"], reference_hz, mhz=mhz)) % 360.0


def circular_difference_deg(a, b):
    return (a - b + 180.0) % 360.0 - 180.0
