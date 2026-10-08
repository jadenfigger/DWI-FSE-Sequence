"""Turn interpreter recordings into exact piecewise-constant waveforms.

Gradient output for logical axis X during a channel sample (prim, sec) is
``prim/32767*M[id].X + sec/32767*M[id+256].X`` with ``id`` the active matrix at
that instant (matrix changes split samples).  Units are DAC; multiply by
``H/32767`` (Hz/mm at full scale, PPR ``grad_var[0]``) for physical units.
"""
from __future__ import annotations

from dataclasses import dataclass
import bisect

import numpy as np

AXIS_INDEX = {"S": 2, "P": 3, "R": 4}   # position in matrix tuple (t_call, t_ready, s, p, r)


@dataclass
class PWC:
    """Piecewise-constant waveform: breakpoints t[0..n], values v[0..n-1]."""
    t: np.ndarray
    v: np.ndarray

    def integral(self, ta, tb):
        t, v = self.t, self.v
        if tb <= ta or len(v) == 0:
            return 0.0
        lo = np.clip(t[:-1], ta, tb)
        hi = np.clip(t[1:], ta, tb)
        return float(np.sum(v * (hi - lo)))

    def value_at(self, x):
        i = bisect.bisect_right(self.t, x) - 1
        if i < 0 or i >= len(self.v):
            return 0.0
        return float(self.v[i])

    def sample(self, times):
        idx = np.searchsorted(self.t, times, side="right") - 1
        out = np.zeros(len(times))
        ok = (idx >= 0) & (idx < len(self.v))
        out[ok] = self.v[idx[ok]]
        return out


def gradient_pwc(it, axis, flag_unready=True):
    g = it.grad
    ch = g.ch[axis]
    k = AXIS_INDEX[axis]
    sel_t = [s[0] for s in g.sel_hist]
    sel_id = [s[1] for s in g.sel_hist]
    tt, vv = [], []
    issues = []
    for (t0, t1, prim, sec) in ch.segments:
        if t1 <= t0:
            continue
        # split by matrix selection changes and definition changes
        cuts = {t0, t1}
        i0 = bisect.bisect_right(sel_t, t0)
        i1 = bisect.bisect_left(sel_t, t1)
        cuts.update(sel_t[i0:i1])
        mids = set()
        for x in sel_id[max(0, i0 - 1):i1 + 1]:
            mids.update((x, x + 256))
        for mid in mids:
            for d in g.mats.get(mid, []):
                if t0 < d[0] < t1:
                    cuts.add(d[0])
        cuts = sorted(cuts)
        for a, b in zip(cuts[:-1], cuts[1:]):
            mid = g.selected_at(a + 1e-9)
            val = 0.0
            for m, s in ((mid, prim), (mid + 256, sec)):
                if s == 0:
                    continue
                d = g.matrix_at(m, a + 1e-9)
                if d is None:
                    issues.append((a, f"matrix {m} undefined while sample {s} plays on {axis}"))
                    continue
                if flag_unready and a < d[1] - 1e-9:
                    issues.append((a, f"matrix {m} used {d[1]-a:.1f} us before DSP ready on {axis}"))
                val += s / 32767.0 * d[k]
            tt.append(a)
            vv.append(val)
            tt.append(b)
    if not vv:
        return PWC(np.array([0.0, 0.0]), np.array([0.0])), issues
    # build contiguous representation (gaps are zero output)
    T = [tt[0]]
    V = []
    for i, val in enumerate(vv):
        a, b = tt[2 * i], tt[2 * i + 1]
        if a > T[-1] + 1e-9:
            V.append(0.0)
            T.append(a)
        V.append(val)
        T.append(b)
    return PWC(np.array(T), np.array(V)), issues


def rf_pulses(it):
    """Gated RF sample lists for every frame playback.

    Returns dicts with sample start times, DAC*multiplier amplitude (real), phase
    and frame metadata.  Samples after rfon(0) are zeroed and the gated span is
    reported (frame playback continues on the board but is not transmitted).
    """
    hist = it.rf.level_hist
    ht = [h[0] for h in hist]
    out = []
    for ev in it.rf.events:
        if not str(ev["frame"]).startswith("setup:") and ev.get("library"):
            fid = it.rf_registry[(ev["library"], ev["frame"])]
            samples = it.rf_frames[fid][2]
            dt = ev["waits"] * 0.1
            t = ev["t_go"] + dt * np.arange(len(samples))
            lev = np.array([hist[max(0, bisect.bisect_right(ht, x + dt / 2) - 1)][1] for x in t])
            amp = samples * ev["mul"] / 2047.0 * (lev > 0)
            on = np.nonzero(lev > 0)[0]
            out.append({**ev, "t": t, "dt": dt, "amp": amp, "samples": samples,
                        "gated_samples": int(len(on)),
                        "t_center": float(ev["t_go"] + dt * len(samples) / 2.0)})
    return out


def phys_moment_cycles_per_m(dac_us, H_hz_per_mm):
    """DAC*us integral -> cycles/m."""
    return dac_us / 32767.0 * H_hz_per_mm * 1e3 * 1e-6
