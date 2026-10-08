"""Derived analyses on PPL-mapped events: b-tensors, ADC echo sweeps, ODE checks."""
from __future__ import annotations

import numpy as np
from scipy.integrate import solve_ivp

from .bloch import EventBloch, Grid, SimConfig, dac_to_hz_per_m

AXES = ("S", "P", "R")


def k_path(led, t0, t1, flips, frozen=(), dt_us=1.0, latency_us=0.0, k0=None):
    """Dephasing wave-vector k(t) (cycles/m, logical S/P/R) along one coherence path.

    flips: refocusing centres (k -> -k). frozen: [(ta, tb)] intervals where the
    path is longitudinal (k held, gradients ignored).
    """
    kfac = dac_to_hz_per_m(led["H"])
    t = np.arange(t0, t1 + dt_us / 2, dt_us)
    k = np.zeros((len(t), 3)) if k0 is None else np.tile(np.asarray(k0, float), (len(t), 1))
    G = np.stack([led["G"][a].sample(t - latency_us + dt_us / 2) for a in AXES], axis=1) * kfac
    flips = sorted(f for f in flips if t0 < f < t1)
    fi = 0
    cur = np.zeros(3) if k0 is None else np.asarray(k0, float).copy()
    for i in range(len(t)):
        k[i] = cur
        if fi < len(flips) and t[i] + dt_us > flips[fi] >= t[i]:
            cur = -cur
            fi += 1
        if any(a <= t[i] < b for a, b in frozen):
            continue
        cur = cur + G[i] * dt_us * 1e-6
    return t, k


def b_tensor(t_us, k):
    """b = (2 pi)^2 * integral k k^T dt, in s/mm^2."""
    dt = np.diff(t_us).mean() * 1e-6
    kk = np.einsum("ti,tj->ij", k, k) * dt
    return (2 * np.pi) ** 2 * kk * 1e-6


def echo_sweep(sim_factory, rf_list, adc_window, n_points=41, t_start=None):
    """Coherent signal over the ADC window around its middle sample."""
    t_mid, sp = adc_window
    times = [(f"s{i}", t_mid + (i - n_points // 2) * sp) for i in range(n_points)]
    sim = sim_factory()
    _, ad = sim.run(rf_list, {}, times, t_start=t_start)
    return np.array([t for _, t in times]), ad


def ode_crosscheck(led, rf_list, cal, z_points, t_a, t_b, cfg: SimConfig, m0, mz0):
    """Independent continuous Bloch integration (solve_ivp) for a few spins.

    RF is the same piecewise-constant sample stream, gradients the same PWC, but
    integration is a generic ODE solver rather than exact rotations.
    """
    kfac = dac_to_hz_per_m(led["H"])
    lat = cfg.grad_latency_us
    Gs = led["G"]["S"]
    samples = []
    for p in rf_list:
        ph = np.deg2rad(p["phase_deg"] + cfg.extra_phase_deg.get(rf_list.index(p), 0.0))
        for t0, a in zip(p["t"], p["amp"]):
            if a and t0 + p["dt"] > t_a and t0 < t_b:
                samples.append((t0, t0 + p["dt"], a * cal * cfg.b1_scale, ph))
    samples.sort()
    st = np.array([s[0] for s in samples]) if samples else np.zeros(0)

    def b1_at(t):
        i = np.searchsorted(st, t, side="right") - 1
        if i >= 0 and samples[i][0] <= t < samples[i][1]:
            return samples[i][2], samples[i][3]
        return 0.0, 0.0

    out = []
    for z, m, mz in zip(z_points, m0, mz0):
        def f(t, M):
            b1, ph = b1_at(t)
            bz = Gs.value_at(t - lat) * kfac * z + cfg.df_hz
            bx, by = b1 * np.cos(ph), b1 * np.sin(ph)
            # dM/dt = 2 pi (M x b), t in us
            return 2 * np.pi * 1e-6 * np.array([M[1] * bz - M[2] * by,
                                               M[2] * bx - M[0] * bz,
                                               M[0] * by - M[1] * bx])
        # break integration at every RF sample edge and gradient breakpoint
        edges = sorted({t_a, t_b, *[s[0] for s in samples], *[s[1] for s in samples],
                        *[x + lat for x in Gs.t if t_a < x + lat < t_b]})
        edges = [e for e in edges if t_a <= e <= t_b]
        M = np.array([m.real, m.imag, mz], float)
        for a, b in zip(edges[:-1], edges[1:]):
            if b - a < 1e-9:
                continue
            sol = solve_ivp(f, (a, b), M, method="DOP853", rtol=1e-11, atol=1e-12,
                            t_eval=[b], first_step=min(1.0, (b - a) / 4))
            M = sol.y[:, -1]
        out.append(M)
    return np.array(out)
