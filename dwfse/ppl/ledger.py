"""Event ledgers and moment audits built from interpreter recordings."""
from __future__ import annotations

import numpy as np

from .events import gradient_pwc, rf_pulses

GAMMA = 42.576e6


def build_ledger(it, shot_index=1, H_hz_per_mm=None):
    """Return a dict describing one shot of the mapped sequence.

    Shot boundaries follow the interpreter's shot label counter; RF/ADC events are
    assigned to the first shot containing method/v18 frames after the shot start.
    """
    shots = [e[1] for e in it.misc_events if e[0] == "shot"]
    rf = [p for p in rf_pulses(it) if p.get("library")]
    if H_hz_per_mm is None:
        H_hz_per_mm = float(it.vars["grad_var"].value[0])
    G = {}
    issues = {}
    for a in "SPR":
        G[a], issues[a] = gradient_pwc(it, a)
    t_start = shots[shot_index - 1] if len(shots) >= shot_index else 0.0
    t_end = shots[shot_index] if len(shots) > shot_index else it.t
    rf = [p for p in rf if t_start <= p["t_go"] < t_end]
    adc = [a for a in it.adc if t_start <= a["t_init"] < t_end]
    return {"rf": rf, "adc": adc, "G": G, "issues": issues, "H": H_hz_per_mm,
            "t_start": t_start, "t_end": t_end}


def dac_us_to_cyc_m(x, H):
    return x / 32767.0 * H * 1e3 * 1e-6


def effective_moment(led, axis, t_ref, t, refocus_centers, unit="cyc_m", k0=0.0):
    """Dephasing state k(t) starting from k0 (cycles/m) at t_ref.

    Each refocusing centre conjugates the transverse phase (k -> -k); gradient
    areas add in between. Instantaneous-refocusing model for moment audits only.
    """
    W = led["G"][axis]
    pts = [t_ref] + [c for c in refocus_centers if t_ref < c < t] + [t]
    total = 0.0
    sign = 1.0
    for a, b in zip(pts[:-1], pts[1:]):
        total += sign * W.integral(a, b)
        sign = -sign
    n_flips = len(pts) - 2
    final = total * (-1.0) ** n_flips
    out = dac_us_to_cyc_m(final, led["H"]) if unit == "cyc_m" else final
    return out + k0 * (-1.0) ** n_flips


def list_starts(it, led, var):
    """Start times (and axes) of a named gradient list within the ledger shot."""
    addr = it.vars[var].value
    return [(t, a) for t, a, ad in it.grad.starts if ad == addr and led["t_start"] <= t < led["t_end"]]


def list_duration_us(it, var, axis_hint=None):
    """Sum of sample durations of a list by walking sequencer memory once."""
    g = it.grad
    pc = it.vars[var].value
    clock = it.vars["clock"].value
    total = 0.0
    while True:
        ins = g.mem.get(pc, ("stop",))
        if ins[0] == "stop":
            return total
        if ins[0] == "out":
            _, loop, addr, points, waits = ins
            total += points * waits * clock * 0.1
        pc += 1


def method_landmarks(it, led):
    """Named snapshot times for the v19 method shot (us)."""
    rf = led["rf"]
    lm = {}
    d = list_starts(it, led, "v19_l_d")
    if d:
        t_d = d[0][0]
        lm["A_before_dephasing"] = t_d
        lm["B_after_dephasing"] = t_d + list_duration_us(it, "v19_l_d")
    for p in rf:
        if p["frame"] in ("v19_slrtip90",):
            s = [x for x in list_starts(it, led, "v19_l_m")][0][0]
            lm["after_tipup"] = s + list_duration_us(it, "v19_l_m")
        if p["frame"] == "v19_slrelim90":
            s = [x for x in list_starts(it, led, "v19_l_m")][0][0]
            lm["after_elimination"] = s + list_duration_us(it, "v19_l_m")
        if p["frame"] == "v19_reexc90":
            s = list_starts(it, led, "v19_l_re")[0][0]
            lm["after_reexcitation_comp"] = s + list_duration_us(it, "v19_l_re")
    sp = list_starts(it, led, "v19_l_sp") if "v19_l_sp" in it.vars else []
    if sp:
        lm["after_spoiler"] = sp[0][0] + list_duration_us(it, "v19_l_sp")
    im = list_starts(it, led, "v19_l_im")
    if im:
        lm["endpoint_before_leading_crusher"] = im[0][0]
    imrf = [p for p in rf if p["frame"] == "v19_imaging180"]
    if imrf:
        lm["pre_RF1_after_crusher"] = imrf[0]["t_go"]
    return lm


def adc_middle_times(it, led):
    out = []
    n = it.vars["no_samples"].value
    for k, a in enumerate(led["adc"]):
        sp = a["sample_period_ticks"] / 10.0
        out.append((f"ADC{k+1}", a["t_init"] + (a["discard"] + n / 2) * sp))
    return out
