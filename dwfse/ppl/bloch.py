"""Bloch simulation driven by PPL-mapped events (repository convention).

Convention: dM/dt = 2*pi*(M x b) with b in Hz (gamma*B); m = Mx + i*My; free
precession m -> m*exp(-i*2*pi*(A*z + df*t)) for gradient area A in cycles/m.
RF phase 0 rotates +Mz to +My.  RF samples are piecewise constant (exact
rotations).  Gradients are the exact piecewise-constant sequencer output from
``events.gradient_pwc`` (optionally delayed by ``grad_latency_us``).

The transverse state is never zeroed: spoiling appears only through the
explicit phase-axis (y) grid and coherent averaging.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .events import PWC


def dac_to_hz_per_m(H_hz_per_mm):
    return H_hz_per_mm * 1e3 / 32767.0


def rf_calibration_hz_per_unit(stock_samples, stock_dwell_us, rfcal):
    """b1[Hz] per amplitude unit (sample*multiplier/2047, as in events.rf_pulses)
    such that multiplier=rfcal gives 90 deg on the supplied stock pulse.
    Linear DAC x multiplier model (inferred, not a measured transmit gain)."""
    integral = float(np.sum(stock_samples)) * rfcal / 2047.0 * stock_dwell_us * 1e-6
    return 0.25 / integral


@dataclass
class Grid:
    z: np.ndarray            # m
    y: np.ndarray            # m (phase-axis positions inside one voxel)

    @property
    def shape(self):
        return (len(self.y), len(self.z))


@dataclass
class SimConfig:
    b1_scale: float = 1.0
    df_hz: float = 0.0
    t1_s: float | None = None
    t2_s: float | None = None
    grad_latency_us: float = 0.0
    extra_phase_deg: dict = field(default_factory=dict)  # rf index -> added phase


def shifted(pwc: PWC, dt):
    return PWC(pwc.t + dt, pwc.v)


class EventBloch:
    def __init__(self, led, grid: Grid, cal_hz_per_unit, cfg: SimConfig):
        self.led = led
        self.grid = grid
        self.cal = cal_hz_per_unit
        self.cfg = cfg
        k = dac_to_hz_per_m(led["H"])
        lat = cfg.grad_latency_us
        self.Gs = shifted(led["G"]["S"], lat)
        self.Gp = shifted(led["G"]["P"], lat)
        self.k = k
        ny, nz = grid.shape
        self.Z = np.broadcast_to(grid.z[None, :], (ny, nz))
        self.Y = np.broadcast_to(grid.y[:, None], (ny, nz))
        self.m = np.zeros((ny, nz), complex)
        self.mz = np.ones((ny, nz))
        self.t = None

    # free precession/relaxation from self.t to t
    def precess(self, t):
        if self.t is None:
            self.t = t
            return
        dt = t - self.t
        if dt < -1e-6:
            raise ValueError(f"time reversal: snapshot at {t} inside an RF sample ending {self.t}")
        if dt <= 0:
            return
        As = self.Gs.integral(self.t, t) * 1e-6 * self.k     # cycles/m
        Ap = self.Gp.integral(self.t, t) * 1e-6 * self.k
        ph = -2 * np.pi * (As * self.Z + Ap * self.Y + self.cfg.df_hz * dt * 1e-6)
        self.m *= np.exp(1j * ph)
        if self.cfg.t2_s:
            self.m *= np.exp(-dt * 1e-6 / self.cfg.t2_s)
        if self.cfg.t1_s:
            e1 = np.exp(-dt * 1e-6 / self.cfg.t1_s)
            self.mz = self.mz * e1 + (1 - e1)
        self.t = t

    def rf_sample(self, t0, dt, b1_hz, phase_rad):
        """Exact rotation for one constant RF sample of duration dt (us)."""
        self.precess(t0)
        tm = t0 + dt / 2
        gs = self.Gs.value_at(tm) * self.k
        gp = self.Gp.value_at(tm) * self.k
        if (abs(self.Gs.value_at(t0 + 1e-6) - self.Gs.value_at(t0 + dt - 1e-6)) > 1e-9 or
                abs(self.Gp.value_at(t0 + 1e-6) - self.Gp.value_at(t0 + dt - 1e-6)) > 1e-9):
            self.gradient_change_in_rf = getattr(self, "gradient_change_in_rf", 0) + 1
        bx = b1_hz * np.cos(phase_rad)
        by = b1_hz * np.sin(phase_rad)
        bz = gs * self.Z + gp * self.Y + self.cfg.df_hz
        mx, my, mz = self.m.real, self.m.imag, self.mz
        bn = np.sqrt(bx * bx + by * by + bz * bz)
        th = -2 * np.pi * bn * dt * 1e-6
        safe = np.where(bn > 0, bn, 1.0)
        nx, ny, nz = bx / safe, by / safe, bz / safe
        c, s = np.cos(th), np.sin(th)
        dot = nx * mx + ny * my + nz * mz
        cx = ny * mz - nz * my
        cy = nz * mx - nx * mz
        cz = nx * my - ny * mx
        mx2 = mx * c + cx * s + nx * dot * (1 - c)
        my2 = my * c + cy * s + ny * dot * (1 - c)
        mz2 = mz * c + cz * s + nz * dot * (1 - c)
        self.m = mx2 + 1j * my2
        self.mz = mz2
        # relaxation over the RF sample (first-order, applied after rotation)
        if self.cfg.t2_s:
            self.m *= np.exp(-dt * 1e-6 / self.cfg.t2_s)
        if self.cfg.t1_s:
            e1 = np.exp(-dt * 1e-6 / self.cfg.t1_s)
            self.mz = self.mz * e1 + (1 - e1)
        self.t = t0 + dt

    def run(self, rf_list, snapshots, adc_times=(), rf_substeps=1, t_start=None):
        """Play RF list in time order; record states at snapshot/ADC times."""
        events = []
        for i, p in enumerate(rf_list):
            ph = np.deg2rad(p["phase_deg"] + self.cfg.extra_phase_deg.get(i, 0.0))
            for t0, a in zip(p["t"], p["amp"]):
                if a == 0:
                    continue
                for j in range(rf_substeps):
                    events.append((t0 + j * p["dt"] / rf_substeps, 3, (p["dt"] / rf_substeps, a, ph)))
        for name, t in snapshots.items():
            events.append((t, 1, name))
        for name, t in adc_times:
            events.append((t, 2, name))
        events.sort(key=lambda e: (e[0], e[1]))
        self.t = t_start if t_start is not None else (events[0][0] - 1.0)
        snaps, adc = {}, {}
        for t, kind, payload in events:
            if kind == 3:
                dt, a, ph = payload
                self.rf_sample(t, dt, a * self.cal * self.cfg.b1_scale, ph)
            else:
                self.precess(t)
                state = (self.m.copy(), self.mz.copy())
                if kind == 1:
                    snaps[payload] = state
                else:
                    adc[payload] = state
        return snaps, adc
