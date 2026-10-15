"""Simple EPG models of conventional DW-FSE (v1.83) and ss-MGOT diffusion-prepared FSE (v1.912).

Helper for oct12_b1_sensitivity.py.  Ideal (rectangular-profile) instantaneous RF, uniform crushers.

Conventional DW-FSE (CPMG, ETL 8): 90(kappa) x - tau=TE/2 - 180(kappa) y - ... echo 1 at TE, then
refocusing every ESP, echo n at TE + (n-1) ESP.  Crushers: one EPG order shift before and after every
refocusing pulse; echo = F0 after the post-crusher.

ss-MGOT (main recalled branch): prep 90(kappa) x - TE/2 - 180(kappa) y - prep echo at TE; tip-up
90(kappa) stores the component along the tip axis on Mz; the 2-cycle twist (magnitude stabilisation)
splits it into two Mz harmonics of half amplitude each, one of which is recalled by the +D/-D scheme
(factor 1/2; the other harmonic is dephased and not tracked); the y-spoiler destroys all remaining
transverse magnetisation; re-excitation 90(kappa) after T_store; then the variable-flip refocusing
train with flips scaled by kappa, first echo ESP after re-excitation.  The recalled branch is tracked
as an ordinary EPG whose Z0 has no thermal regrowth (regrowth is untwisted and is not recalled).

Echo amplitudes are |F0| in units of M0 (full ideal slice = 1), same units as the Bloch model.
"""
from __future__ import annotations

import numpy as np

# Variable flip schedule of v1.912 (requested angles; docs/v19/implementation_report.md).
VFA = (142.2, 94.9, 69.2, 63.0, 60.2, 60.0, 60.0, 60.0)
# Timing of the first v1.912 events relative to the prep excitation, from the PPL event model (ms).
T_STORE_MS = 5.714            # tip-up centre -> re-excitation centre (storage on Mz)
T_REEXC_TO_RF1_MS = 5.5       # re-excitation centre -> first imaging 180 (ESP/2)


class EPG:
    def __init__(self, n_pulses=24, T1=1.9, T2=0.045, recover=True):
        self.K = n_pulses + 2
        n = 2 * self.K + 1
        self.F = np.zeros(n, complex)       # F+_k, k = -K..K  (F-_k = conj(F+_-k))
        self.Z = np.zeros(n, complex)       # Z_k, Z_-k = conj(Z_k)
        self.T1, self.T2, self.recover = T1, T2, recover

    @property
    def k0(self):
        return self.K

    def pulse(self, flip_deg, phase_deg):
        a = np.deg2rad(flip_deg)
        p = np.deg2rad(phase_deg)
        c2, s2, sa, ca = np.cos(a / 2) ** 2, np.sin(a / 2) ** 2, np.sin(a), np.cos(a)
        Fn = np.conj(self.F[::-1])
        F, Z = self.F, self.Z
        self.F = c2 * F + np.exp(2j * p) * s2 * Fn - 1j * np.exp(1j * p) * sa * Z
        self.Z = (-0.5j * np.exp(-1j * p) * sa * F + 0.5j * np.exp(1j * p) * sa * Fn + ca * Z)

    def relax(self, t_ms):
        t = t_ms * 1e-3
        e1, e2 = np.exp(-t / self.T1), np.exp(-t / self.T2)
        self.F *= e2
        z0 = self.Z[self.k0]
        self.Z *= e1
        self.Z[self.k0] = (1 + (z0 - 1) * e1) if self.recover else z0 * e1

    def shift(self, n=1):
        self.F = np.roll(self.F, n)
        if n > 0:
            self.F[:n] = 0
        elif n < 0:
            self.F[n:] = 0

    def echo(self):
        return self.F[self.k0]


def cpmg_train(flips_deg, kappa, T1, T2, first_tau_ms, esp_ms, exc_flip=90.0, exc_phase=0.0,
               ref_phase=90.0, n_echo=8, state=None, exc=True, first_echo_after_ms=None):
    """CPMG train with crushers; returns complex F0 at each echo.

    first_tau_ms     : time from the excitation (or, with exc=False, from the state origin) to refocus 1
    first_echo_after_ms : time from refocus 1 to echo 1 (default = first_tau)
    """
    e = state or EPG(n_pulses=n_echo + 4, T1=T1, T2=T2)
    if exc:
        e.pulse(exc_flip * kappa, exc_phase)
    out = []
    for n in range(n_echo):
        tau_a = first_tau_ms if n == 0 else esp_ms / 2.0
        tau_b = (first_tau_ms if first_echo_after_ms is None else first_echo_after_ms) if n == 0 \
            else esp_ms / 2.0
        e.relax(tau_a)
        e.shift(1)
        e.pulse(flips_deg[n] * kappa, ref_phase)
        e.shift(1)
        e.relax(tau_b)
        out.append(e.echo())
    return np.array(out)


def conventional_epg(kappa, T1=1.9, T2=0.045, te_ms=44.0, esp_ms=11.0, refocus_deg=180.0, n_echo=8,
                     z0_init=1.0):
    """Conventional CPMG DW-FSE.  refocus_deg 180 = nominal 180 (task), 166.4 = event model (p180_scale 185)."""
    e = EPG(n_pulses=n_echo + 4, T1=T1, T2=T2)
    e.Z[e.k0] = z0_init
    flips = [refocus_deg] * n_echo
    return np.abs(cpmg_train(flips, kappa, T1, T2, te_ms / 2.0, esp_ms, state=e,
                             first_echo_after_ms=te_ms / 2.0, n_echo=n_echo))


def ssmgot_epg(kappa, T1=1.9, T2=0.045, te_ms=44.0, esp_ms=11.0, flips=VFA, prep_refocus_deg=180.0,
               tip_deg=90.0, reexc_deg=90.0, twist_factor=0.5, t_store_ms=T_STORE_MS, n_echo=8,
               return_parts=False):
    """ss-MGOT main recalled branch (see module docstring)."""
    # ---- preparation: 90x - TE/2 - 180y - TE/2 -> prep echo
    p = EPG(n_pulses=4, T1=T1, T2=T2)
    p.Z[p.k0] = 1.0
    p.pulse(90.0 * kappa, 0.0)
    p.relax(te_ms / 2.0)
    p.shift(1)
    p.pulse(prep_refocus_deg * kappa, 90.0)
    p.shift(1)
    p.relax(te_ms / 2.0)
    m_prep = abs(p.echo())
    # ---- tip-up stores the component along the tip axis; twist halves it (two harmonics)
    stored = twist_factor * m_prep * abs(np.sin(np.deg2rad(tip_deg * kappa)))
    stored *= np.exp(-t_store_ms * 1e-3 / T1)
    # ---- re-excitation + VFA train, recalled branch only (no thermal regrowth in the branch)
    e = EPG(n_pulses=n_echo + 4, T1=T1, T2=T2, recover=False)
    e.Z[e.k0] = stored
    e.pulse(reexc_deg * kappa, 0.0)
    out = []
    for n in range(n_echo):
        e.relax(esp_ms / 2.0)
        e.shift(1)
        e.pulse(flips[n] * kappa, 90.0)
        e.shift(1)
        e.relax(esp_ms / 2.0)
        out.append(abs(e.echo()))
    out = np.array(out)
    if return_parts:
        return out, dict(prep_echo=m_prep, stored=stored)
    return out


if __name__ == "__main__":
    np.set_printoptions(precision=4, suppress=True)
    for k in (1.0, 0.7, 0.5):
        c180 = conventional_epg(k)
        c166 = conventional_epg(k, refocus_deg=166.4)
        s = ssmgot_epg(k)
        print(f"kappa {k}:")
        print("  conv 180  ", c180)
        print("  conv 166.4", c166)
        print("  ssMGOT    ", s)
        print("  ratio e1 (180/166)", s[0] / c180[0], s[0] / c166[0], " mean", s.mean() / c180.mean())
