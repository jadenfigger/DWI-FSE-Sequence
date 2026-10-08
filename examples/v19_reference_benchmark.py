"""Gibbons reference benchmark (separate from the scanner adaptation).

Published geometry (Gibbons et al. MRM 2018, Methods p3036-3037, Fig 3/4, SI S2):
Published grid: 3000 isochromats over 30 mm, 6-mm imaging slice, 18-mm ss-MGOT preparation
slab, 10-mm tip-up, 2 (and 4) added dephasing cycles across the slice,
initial excitation phase 45 deg (Fig 3/S2) and 0/45/90 deg (Fig 4), muscle
T1=1300 ms / T2=32 ms for Fig 4, ESP 4.2 ms, 76 nominal echoes.

Numerical refinement: 9000 z points for two cycles, 18000 for four cycles,
checked against 18000/27000. The 32 y points have four distinct phases after
the eight-cycle spoiler; each occurs eight times. They are represented by
four equally weighted states, with the original middle-column state retained.
This is exact phase grouping, not manual removal of transverse magnetization.

Departures that are UNAVOIDABLE with the supplied inputs (all disclosed):
* RF: the six real research pulses of scanner/rf/v19_research_rf.seq at their
  reference gradients (SLR prep/tip/elimination, Hamming-sinc re-excitation
  and imaging). Gibbons' spectral-spatial tip-up and windowed sincs are not
  reproduced (docs/v19/reference_rf.md).
* Gradient timing: idealised short (100 us) moment blocks; crushers C=1500
  cycles/m (>=3D for 2 cycles; 4 cycles uses C=3000). Gibbons' crusher areas,
  preparation TE (30 ms here) and readout gradients are not published.
* Alsop elimination: 1.2-ms Hamming-sinc 90 (6 mm) because a 3.2-ms pulse
  cannot sit ESP/2 before the first refocusing RF at ESP 4.2 ms. Its broader
  transition biases the comparison against Alsop. The assumed preparation
  TE mainly rescales the desired transverse signal through T2 decay.
* Trains: Alsop - original Alsop 1997 first five angles then 60 deg;
  ss-MGOT - Busse-style prescribed-signal schedule designed here by EPG
  (4-echo catalysation ramp 160/110/80/65 deg, then constant prescribed
  signal with minimum 55 deg and 60 deg at assumed k-space-centre echo 16;
  later flips held). Gibbons'
  exact schedules are not published.
* S1 (ss-MGOT vs nCPMG PSF) is NOT reproduced: it needs nCPMG double phase
  encoding and image reconstruction. A signal-only illustration is labelled.

Run:  python examples/v19_reference_benchmark.py
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.events import PWC  # noqa: E402
from dwfse.ppl.bloch import EventBloch, Grid, SimConfig  # noqa: E402

OUT = ROOT / "docs/v19/reference_benchmark"
CONTRACT = ROOT / "docs/v19/reference_rf/real_rf_contract.npz"
CONTRACT_JSON = ROOT / "docs/v19/reference_rf/real_rf_contract.json"
TRANSFER = ROOT / "docs/v19/reference_rf/real_rf_transfer_results.json"
SLICE = 6e-3
Z = (np.arange(9000) + 0.5) / 9000 * 30e-3 - 15e-3
ESP = 4200.0
N_ECHO = 76
TE_PREP = 30000.0
T1, T2 = 1.300, 0.032
K_CENTRE = 16


# ------------------------------------------------------------------ EPG design
def epg_cpmg(flips_deg, esp_s, t1, t2, nstates=200):
    """CPMG echo amplitudes: 90 deg about x, refocusing about y (Weigel EPG)."""
    E1 = np.exp(-esp_s / 2 / t1)
    E2 = np.exp(-esp_s / 2 / t2)

    def rf(F, a, ph):
        c2, s2 = np.cos(a / 2) ** 2, np.sin(a / 2) ** 2
        sa, ca = np.sin(a), np.cos(a)
        e = np.exp(1j * ph)
        T = np.array([[c2, e * e * s2, -1j * e * sa],
                      [np.conj(e) ** 2 * s2, c2, 1j * np.conj(e) * sa],
                      [-0.5j * np.conj(e) * sa, 0.5j * e * sa, ca]])
        return T @ F

    def relax_shift(F):
        F = F.copy()
        F[0:2] *= E2
        F[2] *= E1
        F[2, 0] += 1 - E1
        Fp = np.zeros_like(F[0])
        Fm = np.zeros_like(F[1])
        Fp[1:] = F[0, :-1]
        Fm[:-1] = F[1, 1:]
        Fp[0] = np.conj(Fm[0])
        F[0], F[1] = Fp, Fm
        return F

    F = np.zeros((3, nstates), complex)
    F[2, 0] = 1.0
    F = rf(F, np.pi / 2, 0.0)
    out = []
    for a in flips_deg:
        F = relax_shift(F)
        F = rf(F, np.deg2rad(a), np.pi / 2)
        F = relax_shift(F)
        out.append(abs(F[0, 0]))
    return np.array(out)


def busse_style_schedule(n, k_centre, a_min=55.0, a_centre=60.0, ramp=(160.0, 110.0, 80.0, 65.0)):
    """Busse-style prescribed-signal train (approximation; exact schedule unpublished).

    Four-echo catalysation ramp, then each flip is solved by EPG (muscle T1/T2,
    ESP 4.2 ms) so the echo amplitude stays at a constant prescribed level up to
    the assumed k-space-centre echo; the level is chosen so the flip there is
    a_centre (60 deg), with every flip >= a_min (55 deg). Later flips hold the
    k-centre flip.
    """
    esp = ESP * 1e-6

    def design(target):
        flips = list(ramp)
        for k in range(len(ramp), n):
            if k >= k_centre:
                flips.append(flips[-1])
                continue
            lo, hi = a_min, 180.0
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                sig = epg_cpmg(flips + [mid], esp, T1, T2)[-1]
                if sig < target:
                    lo = mid
                else:
                    hi = mid
            flips.append(0.5 * (lo + hi))
        return flips

    lo, hi = 0.01, 0.99
    for _ in range(40):
        tgt = 0.5 * (lo + hi)
        f = design(tgt)
        if f[k_centre - 1] > a_centre:
            hi = tgt
        else:
            lo = tgt
    return [round(x, 2) for x in design(0.5 * (lo + hi))]


ALSOP = [142.2, 94.9, 69.2, 63.0, 60.2] + [60.0] * (N_ECHO - 5)


# ------------------------------------------------------------------ sequence builder
class Seq:
    def __init__(self):
        self.rf = []
        self.blocks = {"S": [], "P": []}
        self.marks = {}
        self.adc = []
        c = np.load(CONTRACT)
        self.contract = json.loads(CONTRACT_JSON.read_text())["pulses"]
        self.kappa = {n: -p["post_RF_correction_cycles_m"] / p["net_RF_gradient_cycles_m"]
                      for n, p in json.loads(TRANSFER.read_text())["pulses"].items()}
        self.samples = {n: c[n + "_dac"].astype(float) for n in self.contract}

    def add_rf(self, t_c, name, flip, phase, width):
        info = self.contract[name]
        s = self.samples[name]
        dt = info["wait_ticks"] / 10.0
        T = len(s) * dt
        integral = s.sum() / 2047.0 * dt * 1e-6
        b1 = s / 2047.0 * (flip / 360.0) / integral          # Hz
        t = t_c - T / 2 + dt * np.arange(len(s))
        self.rf.append({"t": t, "amp": b1, "dt": dt, "phase_deg": phase, "frame": name})
        g = info["bandwidth_Hz"] / width                       # Hz/m
        self.blocks["S"].append((t_c - T / 2, t_c + T / 2, g))
        return g * T * 1e-6, T                                 # RF-time area (cycles/m)

    def kick(self, axis, t0, area, dur=100.0):
        self.blocks[axis].append((t0, t0 + dur, area / (dur * 1e-6)))

    def ledger(self):
        G = {}
        for ax in ("S", "P", "R"):
            bl = sorted(self.blocks.get(ax, []))
            for (a0, a1, _), (b0, b1, _) in zip(bl[:-1], bl[1:]):
                assert b0 >= a1 - 1e-6, (ax, a0, a1, b0)
            T, V = [], []
            for a0, a1, v in bl:
                if T and a0 > T[-1] + 1e-9:
                    V.append(0.0)
                    T.append(a0)
                if not T:
                    T.append(a0)
                V.append(v)
                T.append(a1)
            G[ax] = PWC(np.array(T if T else [0.0, 0.0]), np.array(V if V else [0.0]))
        return {"G": G, "H": 32767 / 1000.0, "rf": sorted(self.rf, key=lambda p: p["t"][0])}


def build(method, cycles, flips, crusher):
    s = Seq()
    D = cycles / SLICE
    slab = 18e-3 if method == "ssmgot" else SLICE
    # preparation excitation (phase 0 + initial phase applied by SimConfig)
    a, T = s.add_rf(0.0, "v19_slrprep90", 90, 0.0, slab)
    s.kick("S", T / 2 + 10, -s.kappa["v19_slrprep90"] * a)
    # refocusing with first crushers C1
    # Avoid the measured C1 coincidence window for both reference crusher settings.
    # The two-cycle value has a small residual phase spread (see c1 scan report).
    C1 = 2550.0 if cycles == 2 else 5100.0
    s.kick("S", TE_PREP / 2 - 1600 - 100, C1)
    s.add_rf(TE_PREP / 2, "v19_slrprep180", 180, 270.0, slab)
    s.kick("S", TE_PREP / 2 + 1600, C1)
    if method == "uncorrected":
        t0 = TE_PREP
        for k in range(N_ECHO):
            tc = t0 + (k + 0.5) * ESP
            s.kick("S", tc - 600 - 220, crusher, dur=200.0)
            s.add_rf(tc, "v19_imaging180", flips[k], 270.0, SLICE)
            s.kick("S", tc + 600 + 20, crusher, dur=200.0)
            s.adc.append((f"ADC{k+1}", t0 + (k + 1) * ESP))
        return s
    # added dephasing D
    tD = TE_PREP - 1600 - 600
    s.marks["A_before_dephasing"] = tD - 1
    s.kick("S", tD, D)
    s.marks["B_after_dephasing"] = tD + 101
    if method == "alsop":
        # Elimination must sit ESP/2 = 2.1 ms before the first refocusing RF;
        # the 1.2-ms imaging-class selective 90 is used (Gibbons does not give
        # the elimination pulse; the 3.2-ms SLR cannot fit at ESP 4.2 ms).
        am, Tm = 1.2 * 1283.3333333 / SLICE * 1e-3, 1200.0
        s.kick("S", TE_PREP - Tm / 2 - 110, -s.kappa["v19_reexc90"] * am)
        s.add_rf(TE_PREP, "v19_reexc90", 90, 270.0, SLICE)
        s.kick("S", TE_PREP + Tm / 2 + 10, -s.kappa["v19_reexc90"] * am)
        s.marks["after_elimination"] = TE_PREP + Tm / 2 + 111
        t0 = TE_PREP
    else:
        am, Tm = 3.2 * 1109.375 / 10e-3 * 1e-3, 3200.0
        s.kick("S", TE_PREP - Tm / 2 - 110, -s.kappa["v19_slrtip90"] * am)
        s.add_rf(TE_PREP, "v19_slrtip90", 90, 180.0, 10e-3)
        s.marks["after_tipup"] = TE_PREP + Tm / 2 + 1
        ts = TE_PREP + Tm / 2 + 50
        s.kick("P", ts, 8.0 / 1e-3, dur=500.0)            # 8 cycles across a 1-mm y voxel
        s.marks["after_spoiler"] = ts + 501
        t0 = ts + 500 + 50 + 600
        ar, Tr = s.add_rf(t0, "v19_reexc90", 90, 0.0, SLICE)
        s.kick("S", t0 + Tr / 2 + 10, -s.kappa["v19_reexc90"] * ar)
        s.marks["after_reexcitation_comp"] = t0 + Tr / 2 + 111
    # imaging train: C | RF | C, +D after, ADC, -D after
    for k in range(N_ECHO):
        tc = t0 + (k + 0.5) * ESP
        s.kick("S", tc - 600 - 220, crusher, dur=200.0)
        if k == 0:
            s.marks["endpoint_before_leading_crusher"] = tc - 600 - 221
            s.marks["pre_RF1_after_crusher"] = tc - 600 - 1
        s.add_rf(tc, "v19_imaging180", flips[k], 270.0, SLICE)
        s.kick("S", tc + 600 + 20, crusher, dur=200.0)
        s.kick("S", tc + 600 + 240, D, dur=200.0)
        te = t0 + (k + 1) * ESP
        s.adc.append((f"ADC{k+1}", te))
        s.kick("S", te + 200, -D, dur=200.0)
    return s


def run(method, cycles, phase, flips, relax=True, b1=1.0, df=0.0, snaps=False,
        nz=None, fold_spoiler=True, n_echo=None):
    crusher = 1500.0 if cycles == 2 else 3000.0
    s = build(method, cycles, flips, crusher)
    led = s.ledger()
    ny = 32 if method == "ssmgot" else 1
    y = (np.arange(ny) + 0.5) / ny * 1e-3 if ny > 1 else np.zeros(1)
    if method == "ssmgot" and fold_spoiler:
        # P has no RF overlap and no later lobe. At the complete spoiler,
        # y_j and y_(j+4) differ by exactly one turn (8000 cycles/m * 0.125 mm).
        # Later evolution is linear and independent of y, so equal phase
        # groups stay equal. Reorder to retain original column 16 at index 2.
        p = led["G"]["P"]
        assert abs(p.integral(p.t[0], p.t[-1]) * 1e-6 - 8000.0) < 1e-6
        y = y[[18, 19, 16, 17]]
    nz = nz or (9000 if cycles == 2 else 18000)
    z = (np.arange(nz) + .5) / nz * 30e-3 - 15e-3
    cfg = SimConfig(b1_scale=b1, df_hz=df, extra_phase_deg={0: phase},
                    t1_s=T1 if relax else None, t2_s=T2 if relax else None)
    sim = EventBloch(led, Grid(z, y), 1.0, cfg)
    adc = s.adc[:n_echo] if n_echo else s.adc
    rf = [p for p in led["rf"] if p["t"][0] < adc[-1][1]]
    sn, ad = sim.run(rf, s.marks if snaps else {}, adc)
    dz = (z[1] - z[0]) / SLICE
    S = np.array([ad[n][0].mean(axis=0).sum() * dz for n, _ in adc])
    return S, sn, ad


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    busse = busse_style_schedule(N_ECHO, K_CENTRE)
    res = {"assumptions": __doc__, "flips": {"alsop": ALSOP, "ssmgot_busse_style": busse},
           "grid_points_by_cycles": {"2": 9000, "4": 18000},
           "C1_cycles_per_m_by_cycles": {"2": 2550, "4": 5100},
           "fig3_S2": {}, "fig3_echo_abs": {}, "fig4": {}, "s1_signal_only_illustration": {}}
    # Figure 3 / S2 analogue: phase 45, 2 cycles, preparation landmarks (no relaxation stated).
    # The 9000-point z grid resolves the late-echo pathway orders that alias at 3000.
    fig, axs = plt.subplots(2, 1, figsize=(11, 7))
    for ax, method in zip(axs, ("alsop", "ssmgot")):
        flips = ALSOP if method == "alsop" else busse
        S, sn, ad = run(method, 2, 45.0, flips, relax=False, snaps=True)
        res["fig3_echo_abs"][method] = np.abs(S).tolist()
        print("Fig3", method, "9000 z points", flush=True)
        rows = {}
        inside = np.abs(Z) < SLICE / 2
        arr = {}
        for n, (m, mz) in list(sn.items()) + [(k, ad[k]) for k in ("ADC1", "ADC2", f"ADC{N_ECHO}")]:
            mean = m.mean(axis=0)
            rows[n] = {"coherent_mean_mx": float(mean[inside].mean().real),
                       "coherent_mean_my": float(mean[inside].mean().imag),
                       "mean_mz": float(mz.mean(axis=0)[inside].mean()),
                       "mean_local_abs_mxy": float(np.abs(m[m.shape[0] // 2][inside]).mean())}
            arr[n + "_local"] = m[m.shape[0] // 2]
            arr[n + "_mean"] = mean
            arr[n + "_mz"] = mz.mean(axis=0)
        np.savez_compressed(OUT / f"fig3_{method}_profiles.npz", z_m=Z, **arr)
        res["fig3_S2"][method] = rows
        n = "endpoint_before_leading_crusher"
        m, mz = sn[n]
        mean = m.mean(axis=0)
        ax.plot(Z * 1e3, mean.real, label="Mx (coherent mean)")
        ax.plot(Z * 1e3, mean.imag, label="My (coherent mean)")
        ax.plot(Z * 1e3, mz.mean(axis=0), label="Mz")
        ax.axvspan(-3, 3, color="0.9", zorder=0)
        ax.set_title(f"{method}: preparation endpoint C (phase 45 deg, 2 cycles) - research RF, not Gibbons pulses")
        ax.legend(fontsize=7)
    axs[-1].set_xlabel("z (mm)")
    fig.tight_layout()
    fig.savefig(OUT / "fig3_S2_endpoint_profiles.png", dpi=120)
    plt.close(fig)
    # Figure 4 analogue: phases 0/45/90, 2/4 cycles, muscle relaxation
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for ax, cycles in zip(axs, (2, 4)):
        for method, col in (("alsop", "tab:red"), ("ssmgot", "tab:blue")):
            flips = ALSOP if method == "alsop" else busse
            for ph, ls in ((0.0, "-"), (45.0, "--"), (90.0, ":")):
                S, *_ = run(method, cycles, ph, flips)
                print("Fig4", method, cycles, ph, flush=True)
                res["fig4"][f"{method}_c{cycles}_p{int(ph)}"] = np.abs(S).tolist()
                ax.plot(np.arange(1, N_ECHO + 1), np.abs(S), ls, color=col, label=f"{method} {int(ph)} deg")
        ax.set_title(f"Fig 4 analogue, {cycles} cycles, T1/T2 1300/32 ms")
        ax.set_xlabel("echo")
    axs[0].set_ylabel("|S| / full 6-mm slice signal")
    axs[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "fig4_echo_trains.png", dpi=120)
    plt.close(fig)
    # B1/B0 robustness at the reference geometry (2 cycles, 45 deg)
    rob = {}
    for method in ("alsop", "ssmgot"):
        flips = ALSOP if method == "alsop" else busse
        for b1 in (1.0, 0.8):
            for df in (-128.0, 0.0, 128.0):
                S, *_ = run(method, 2, 45.0, flips, b1=b1, df=df, n_echo=8)
                rob[f"{method}_b1{b1}_df{int(df)}"] = np.abs(S[:8]).tolist()
                print("robustness", method, b1, df, flush=True)
    res["robustness_first8"] = rob
    # Demonstrate exact y-phase grouping; then test the late-echo z sampling
    # for the no-relaxation Fig3 and the four-cycle Fig4 comparison.
    folded, *_ = run("ssmgot", 2, 45, busse, nz=3000, n_echo=8)
    full, *_ = run("ssmgot", 2, 45, busse, nz=3000, n_echo=8, fold_spoiler=False)
    convergence = {"y32_vs_four_phase_groups_max_complex_diff": float(np.max(np.abs(folded-full)))}
    assert convergence["y32_vs_four_phase_groups_max_complex_diff"] < 1e-11
    for method in ("alsop", "ssmgot"):
        flips = ALSOP if method == "alsop" else busse
        for cycles in (2, 4):
            fine, *_ = run(method, cycles, 45, flips, relax=(cycles == 4),
                           nz=18000 if cycles == 2 else 27000)
            coarse = res["fig3_echo_abs"][method] if cycles == 2 else res["fig4"][f"{method}_c4_p45"]
            diff = np.abs(np.asarray(coarse) - np.abs(fine))
            convergence[f"{method}_c{cycles}"] = {"max_abs_diff_all76": float(diff.max()),
                                                   "max_abs_diff_first32": float(diff[:32].max())}
            print("z convergence", method, cycles, diff.max(), flush=True)
            assert diff.max() < 1e-5, (method, cycles, diff.max())
    res["convergence"] = convergence
    # S1: signal-only illustration (NOT S1 PSF): fixed 160 deg train after the
    # uncorrected (no added dephasing, no tip-up/elimination) preparation.
    for ph in (0.0, 45.0, 90.0):
        s = build("uncorrected", 2, [160.0] * N_ECHO, 1500.0)
        led = s.ledger()
        cfg = SimConfig(extra_phase_deg={0: ph}, t1_s=T1, t2_s=T2)
        sim = EventBloch(led, Grid(Z, np.zeros(1)), 1.0, cfg)
        _, ad = sim.run(led["rf"], {}, s.adc)
        dz = (Z[1] - Z[0]) / SLICE
        res["s1_signal_only_illustration"][f"uncorrected_160_p{int(ph)}"] = [abs(ad[n][0].mean(axis=0).sum() * dz) for n, _ in s.adc][:16]
    (OUT / "results.json").write_text(json.dumps(res, indent=1) + "\n")
    print("Busse-style flips (first 20):", busse[:20])
    for k, v in res["fig4"].items():
        print(k, np.round(v[:8], 3))


if __name__ == "__main__":
    main()
