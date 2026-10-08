"""Independent reviewer check 1+2: axis/phase logic and coherence-pathway enumeration.

Does NOT import dwfse. Repository convention: dM/dt = 2*pi*(M x B) (B in Hz),
m = Mx + i My, RF phase phi puts B1 along (cos phi, sin phi, 0), positive area A
(cycles/m) gives m -> m*exp(-i 2 pi A z).

Part 1: hard-rotation axis checks (prep 0/270, ss-MGOT tip 180 + re-exc 0,
        Alsop elimination 270, imaging 270), recall-sign contracts, 50% cost.
Part 2: generalised EPG with *arbitrary real* k (dict keyed by k): exact
        bookkeeping of every low-order pathway for the PPR moments; slice
        coherence weight w(k)=sinc(k*W) for an ideal box slice. Coincidence scans.

Run: python docs/v19/review/physics_checks/check_axes_pathways.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent


# ------------------------------------------------------------------ rotations
def rot(flip_deg, phase_deg):
    """3x3 rotation for a hard pulse in the repository convention.

    dM/dt = 2pi M x B = -2pi B x M  -> rotation by -theta about n = B/|B|.
    """
    th = -np.deg2rad(flip_deg)
    n = np.array([np.cos(np.deg2rad(phase_deg)), np.sin(np.deg2rad(phase_deg)), 0.0])
    K = np.array([[0, -n[2], n[1]], [n[2], 0, -n[0]], [-n[1], n[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


def part1():
    ex, ey, ez = np.eye(3)
    r = {}
    r["prep90_phase0_Mz_to"] = (rot(90, 0) @ ez).round(12).tolist()          # expect +y
    r["prep180_phase270_on_x_y"] = [(rot(180, 270) @ ex).round(12).tolist(), (rot(180, 270) @ ey).round(12).tolist()]
    r["tip90_phase180_My_to"] = (rot(90, 180) @ ey).round(12).tolist()       # expect +z
    r["tip90_phase180_Mx_to"] = (rot(90, 180) @ ex).round(12).tolist()       # expect +x (stays transverse)
    r["reexc90_phase0_Mz_to"] = (rot(90, 0) @ ez).round(12).tolist()         # expect +y
    r["elim90_phase270_My_to"] = (rot(90, 270) @ ey).round(12).tolist()      # expect +y retained
    r["elim90_phase270_Mx_to"] = (rot(90, 270) @ ex).round(12).tolist()      # expect -z
    # Wrong-axis controls
    r["CONTROL_tip_with_phase0_My_to"] = (rot(90, 0) @ ey).round(12).tolist()  # -z: wrong sign storage
    r["CONTROL_elim_with_phase180_My_to"] = (rot(90, 180) @ ey).round(12).tolist()

    # Ideal recall contract with 180 refocusing about -y, pre C | RF | post C, +D, ADC, -D
    z = (np.arange(4000) + 0.5) / 4000 * 1e-3       # exactly 1 mm: integer cycles for all moments below
    D, C = 2000.0, 7000.0                           # cycles/m (2 and 7 cycles across 1 mm)
    res = {}
    for phi in (0.0, 45.0, 90.0, 137.0):
        for method in ("alsop", "ssmgot"):
            M = np.zeros((3, z.size)); M[2] = 1
            M = rot(90, phi) @ M                          # prep excitation (initial phase phi)
            M = rot(180, 270) @ M                         # prep refocus (ideal, no crushers needed here)
            m = (M[0] + 1j * M[1]) * np.exp(-2j * np.pi * D * z)   # +D added dephasing
            M = np.vstack([m.real, m.imag, M[2]])
            if method == "alsop":
                M = rot(90, 270) @ M
            else:
                M = rot(90, 180) @ M
                # no zeroing: the y-spoiler is emulated below on a 64-point y grid
            if method == "ssmgot":
                ny = 64
                y = (np.arange(ny) + 0.5) / ny
                m2 = (M[0] + 1j * M[1])[None, :] * np.exp(-2j * np.pi * 8 * y)[:, None]
                Mz2 = np.broadcast_to(M[2], m2.shape)
                M3 = np.stack([m2.real, m2.imag, Mz2])
                M3 = np.einsum("ij,jyz->iyz", rot(90, 0), M3)
            else:
                M3 = M[:, None, :]
            sig = []
            for e in range(4):
                m = (M3[0] + 1j * M3[1]) * np.exp(-2j * np.pi * C * z)
                M3 = np.stack([m.real, m.imag, M3[2]])
                M3 = np.einsum("ij,jyz->iyz", rot(180, 270), M3)
                m = (M3[0] + 1j * M3[1]) * np.exp(-2j * np.pi * (C + D) * z)
                sig.append(m.mean())
                m = m * np.exp(+2j * np.pi * D * z)       # -D restoration
                M3 = np.stack([m.real, m.imag, M3[2]])
            res[f"{method}_phi{phi:g}"] = {"abs": [round(abs(s), 12) for s in sig],
                                           "angle_deg": [round(float(np.angle(s, deg=True)), 6) for s in sig]}
    r["ideal_180_train_signal"] = res
    # Recall with the opposite sign (-D before ADC) at echo 1: should vanish
    return r


# ------------------------------------------------------------------ generalised EPG
class KEPG:
    """m(z) = sum_k a_k exp(-i2pi k z); Mz(z) = sum_k b_k exp(-i2pi k z) (b_-k = conj b_k).

    Keys are tuples (kz, ky) in cycles/m, rounded to 1e-6.
    """

    def __init__(self):
        self.a = {}
        self.b = {(0.0, 0.0): 1.0 + 0j}

    @staticmethod
    def key(k):
        return (round(k[0], 6) + 0.0, round(k[1], 6) + 0.0)

    def grad(self, gz, gy=0.0):
        self.a = {self.key((k[0] + gz, k[1] + gy)): v for k, v in self.a.items()}

    def rf(self, flip, phase, prune=1e-7):
        R = rot(flip, phase)
        A = ((R[0, 0] + 1j * R[1, 0]) - 1j * (R[0, 1] + 1j * R[1, 1])) / 2
        B = ((R[0, 0] + 1j * R[1, 0]) + 1j * (R[0, 1] + 1j * R[1, 1])) / 2
        Cc = R[0, 2] + 1j * R[1, 2]
        E = (R[2, 0] - 1j * R[2, 1]) / 2
        keys = set(self.a) | set(self.b) | {self.key((-k[0], -k[1])) for k in self.a}
        na, nb = {}, {}
        for k in keys:
            mk = self.key((-k[0], -k[1]))
            ak = self.a.get(k, 0)
            amk = np.conj(self.a.get(mk, 0))
            bk = self.b.get(k, 0)
            va = A * ak + B * amk + Cc * bk
            vb = E * ak + np.conj(E) * amk + R[2, 2] * bk
            if abs(va) > prune:
                na[k] = va
            if abs(vb) > prune:
                nb[k] = vb
        self.a, self.b = na, nb

    def relax_free(self, e1, e2):
        self.a = {k: v * e2 for k, v in self.a.items()}
        self.b = {k: v * e1 for k, v in self.b.items()}
        self.b[(0.0, 0.0)] = self.b.get((0.0, 0.0), 0) + (1 - e1)

    def signal(self, W, spoil_resid=0.0):
        s = 0
        contrib = []
        for k, v in self.a.items():
            w = np.sinc(k[0] * W) * (1.0 if k[1] == 0 else spoil_resid)
            s += v * w
            if abs(v * w) > 1e-4:
                contrib.append((k, v * w))
        return s, contrib


def run_epg(method, C, C1, D, flips, phi=45.0, prep180=180.0, elim=90.0, b1=1.0, W=1e-3,
            sel180_half=0.0, Kspoil=32000.0, spoil_resid=0.0, prep_flip=90.0, track=False):
    """Ideal hard-pulse model of the PPL moment structure (slice axis S, phase axis y).

    sel180_half: crude stand-in for storage at a selective 180's centre (the Z state
    created by the prep 180 carries C1 + half selector area).
    """
    e = KEPG()
    e.rf(prep_flip * b1, 0.0 + phi)
    e.grad(C1 + sel180_half)
    e.rf(prep180 * b1, 270.0)
    e.grad(C1 + sel180_half)
    e.grad(D)
    if method == "alsop":
        e.rf(elim * b1, 270.0)
    else:
        e.rf(elim * b1, 180.0)
        e.grad(0.0, Kspoil)
        e.rf(elim * b1, 0.0)
    out, contribs = [], []
    for n, a in enumerate(flips):
        e.grad(C)
        e.rf(a * b1, 270.0)
        e.grad(C + D)
        s, c = e.signal(W, spoil_resid)
        out.append(s)
        if track:
            contribs.append(c)
        e.grad(-D)
    return np.array(out), contribs


def part2():
    H = 25447.0                       # Hz/mm at 32767 DAC (grad_var[0])
    k = lambda dac, us: dac / 32767 * H * 1e3 * us * 1e-6    # cycles/m
    tramp, tcrush, diff_tcrush, tdp = 200, 1000, 1000, 700
    C = k(8223, tcrush + tramp)
    C1 = k(5482, diff_tcrush + tramp)
    D = k(2860, tdp + tramp * 1.0096)
    W = 1070 / (1377 / 32767 * H) * 1e-3
    sel180 = 1428 / 32767 * H * 1e3      # Hz/m, v192 prep-180 selector (TBW 3.55/3.2 ms over 1 mm)
    sel180_half = sel180 * (1660 + 98) * 1e-6
    flips = [142.2, 94.9, 69.2, 63.0, 60.2, 60, 60, 60]
    r = {"moments_cycles_per_m": {"C": C, "C1": C1, "D": D, "C_over_D": C / D, "slice_W_mm": W * 1e3,
                                  "v192_prep180_half_selector": sel180_half,
                                  "C_minus_D": C - D, "C_plus_D": C + D, "C_minus_2D": C - 2 * D,
                                  "C1_plus_D_plus_halfsel": C1 + D + sel180_half,
                                  "C1_plus_halfsel": C1 + sel180_half}}
    # (a) nominal ideal pathways: phase independence and size
    cases = {}
    for method in ("alsop", "ssmgot"):
        for phi in (0.0, 45.0, 90.0):
            for p180, el, b1 in ((180, 90, 1.0), (150, 90, 1.0), (120, 70, 1.0), (180, 90, 0.8)):
                s, _ = run_epg(method, C, C1, D, flips, phi, p180, el, b1, W)
                cases[f"{method}_phi{phi:g}_p180_{p180}_elim{el}_b1{b1}"] = np.abs(s).round(5).tolist()
    r["nominal_ideal_box_slice"] = cases
    # CPMG reference: ideal My input, same train, no D -> echo amplitude A_n; prediction 0.5*A_n
    e = KEPG(); e.rf(90, 0.0)
    ref = []
    for a in flips:
        e.grad(C); e.rf(a, 270.0); e.grad(C)
        ref.append(abs(e.signal(W)[0]))
    r["cpmg_reference_A_n"] = np.round(ref, 6).tolist()
    r["half_cpmg_reference"] = (0.5 * np.array(ref)).round(6).tolist()

    # (b) coincidence scan in C/D at fixed D (Alsop; imperfect prep 180=150, elim 80), ideal box slice
    scan = []
    for ratio in np.round(np.arange(0.8, 5.01, 0.05), 3):
        sp = []
        for phi in (0.0, 45.0, 90.0):
            s, _ = run_epg("alsop", ratio * D, C1, D, flips, phi, 150, 80, 1.0, W)
            sp.append(np.abs(s))
        sp = np.array(sp)
        scan.append({"C_over_D": float(ratio), "max_phase_spread_over_echoes": float((sp.max(0) - sp.min(0)).max()),
                     "echo1_mean": float(sp[:, 0].mean())})
    r["scan_C_over_D_alsop_p180_150_elim80"] = scan
    # (c) scan of C1 at the PPR C, D: Alsop, imperfect prep (slice-edge-like 120 deg, elim 70)
    scan = []
    for c1 in np.arange(1000, 16001, 100.0):
        sp = []
        for phi in (0.0, 45.0, 90.0):
            s, _ = run_epg("alsop", C, c1, D, flips, phi, 120, 70, 1.0, W)
            sp.append(np.abs(s))
        sp = np.array(sp)
        scan.append({"C1": float(c1), "max_phase_spread": float((sp.max(0) - sp.min(0)).max())})
    r["scan_C1_alsop_p180_120_elim70"] = scan
    # (d) pathway list at the PPR values, Alsop, edge-like imperfections, with the
    # half-selector stand-in so the Z state left by the prep 180 sits at C1+sel/2
    s, contrib = run_epg("alsop", C, C1, D, flips, 45.0, 120, 70, 1.0, W, sel180_half=sel180_half, track=True)
    r["alsop_edge_like_with_halfsel_abs"] = np.abs(s).round(5).tolist()
    r["alsop_edge_like_with_halfsel_contribs_echo1to4"] = [
        [{"k": list(kk), "abs": round(abs(v), 5)} for kk, v in sorted(c, key=lambda t: -abs(t[1]))[:6]] for c in contrib[:4]]
    sp = []
    for phi in (0.0, 45.0, 90.0):
        s, _ = run_epg("alsop", C, C1, D, flips, phi, 120, 70, 1.0, W, sel180_half=sel180_half)
        sp.append(np.abs(s))
    r["alsop_edge_like_with_halfsel_phase_spread"] = (np.max(sp, 0) - np.min(sp, 0)).round(5).tolist()
    # (e) 4-cycle setting with PPR C (PPL rejects; shows why)
    sp = []
    for phi in (0.0, 45.0, 90.0):
        s, _ = run_epg("alsop", C, C1, 2 * D, flips, phi, 150, 80, 1.0, W)
        sp.append(np.abs(s))
    r["alsop_4cycles_PPR_C_phase_spread"] = (np.max(sp, 0) - np.min(sp, 0)).round(5).tolist()
    # (f) old protocol C (test1e -2741) with 2 cycles, to confirm writer finding (a)
    C_old = k(2741, tcrush + tramp)
    sp = []
    for phi in (0.0, 45.0, 90.0):
        s, _ = run_epg("alsop", C_old, C1, D, flips, phi, 180, 90, 1.0, W)
        sp.append(np.abs(s).round(4).tolist())
    r["alsop_old_C_ideal_pulses_abs_by_phase"] = sp
    r["old_C_minus_D"] = C_old - D
    # (g) ss-MGOT spoiler residual sensitivity (8.24 cycles per voxel -> sinc 0.026)
    sp = []
    for phi in (0.0, 45.0, 90.0):
        s, _ = run_epg("ssmgot", C, C1, D, flips, phi, 150, 80, 1.0, W, spoil_resid=np.sinc(8.24))
        sp.append(np.abs(s))
    r["ssmgot_p150_tip80_spoilresid_phase_spread"] = (np.max(sp, 0) - np.min(sp, 0)).round(5).tolist()
    return r


def grid_check():
    """y-grid adequacy: coherent mean of exp(-i2pi n K y) on a 32-point midpoint grid."""
    out = {}
    for label, cyc in (("benchmark_8_cycles_exact", 8.0), ("scanner_8.24_cycles", 32 * 35 / 136)):
        y = (np.arange(32) + 0.5) / 32
        out[label] = {f"order{n}": float(abs(np.exp(-2j * np.pi * n * cyc * y).mean())) for n in (1, 2, 3, 4)}
        out[label]["continuous_order1"] = float(abs(np.sinc(cyc)))
    return out


if __name__ == "__main__":
    res = {"part1_axes": part1(), "part2_pathways": part2(), "y_grid": grid_check()}
    (OUT / "axes_pathways_results.json").write_text(json.dumps(res, indent=1, default=lambda o: str(o)) + "\n")
    p1 = res["part1_axes"]
    for k_, v in p1.items():
        if k_ != "ideal_180_train_signal":
            print(k_, v)
    for k_, v in p1["ideal_180_train_signal"].items():
        print(k_, v)
    p2 = res["part2_pathways"]
    print(json.dumps(p2["moments_cycles_per_m"], indent=1))
    print("cpmg A_n/2", p2["half_cpmg_reference"])
    for k_, v in p2["nominal_ideal_box_slice"].items():
        print(k_, v)
    for row in p2["scan_C_over_D_alsop_p180_150_elim80"]:
        if row["max_phase_spread_over_echoes"] > 0.01:
            print("C/D", row)
    print("C1 scan spreads >0.01:", [(r_["C1"], round(r_["max_phase_spread"], 3)) for r_ in p2["scan_C1_alsop_p180_120_elim70"] if r_["max_phase_spread"] > 0.01])
    for k_ in ("alsop_edge_like_with_halfsel_abs", "alsop_edge_like_with_halfsel_phase_spread",
               "alsop_4cycles_PPR_C_phase_spread", "alsop_old_C_ideal_pulses_abs_by_phase", "old_C_minus_D",
               "ssmgot_p150_tip80_spoilresid_phase_spread"):
        print(k_, p2[k_])
    print(json.dumps(p2["alsop_edge_like_with_halfsel_contribs_echo1to4"], indent=0)[:2000])
    print(res["y_grid"])
