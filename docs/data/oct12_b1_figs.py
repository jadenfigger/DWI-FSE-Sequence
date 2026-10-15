"""Figures for oct12_b1_sensitivity.py (matplotlib, Agg).  Palette: validated reference categorical slots
(blue #2a78d6, orange #eb6834, aqua #1baf7a), ink #0b0b0b / #52514e, surface #fcfcfb."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "regular",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "legend.frameon": False, "legend.fontsize": 8.5, "lines.linewidth": 2.0,
})


def _save(fig, path):
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def _rows(R, model):
    return [r for r in R["_rows"]["k"] if r["model"] == model]


def fig_ratio(R, out):
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.6))
    a = ax[0]
    for model, col, ls, lab, lw in (("bloch", BLUE, "-", "Bloch (event model), echo 1", 2.4),
                                    ("epg166", ORANGE, "--", "EPG, v1.83 refocus 166.4 deg, echo 1", 1.6),
                                    ("epg180", ORANGE, ":", "EPG, nominal 180 deg, echo 1", 1.6)):
        rows = _rows(R, model)
        k = np.array([r["kappa"] for r in rows])
        a.plot(k, [r["s"][0] / r["c"][0] for r in rows], ls, color=col, lw=lw, label=lab)
    rows = _rows(R, "bloch")
    k = np.array([r["kappa"] for r in rows])
    a.plot(k, [r["s"].mean() / r["c"].mean() for r in rows], "-", color=AQUA, lw=1.6, label="Bloch, mean of echoes 1-8")
    a.axvspan(0.3, 1.2, color="#2a78d6", alpha=0.05, lw=0)
    a.axhline(0.5, color=INK2, lw=0.8, ls=(0, (4, 3)))
    a.axhline(0.05, color=INK2, lw=0.8, ls=(0, (4, 3)))
    a.text(1.99, 0.52, "observed at dorsal surface (~0.5)", ha="right", va="bottom", fontsize=8.5, color=INK2)
    a.text(1.99, 0.052, "observed 8-10 mm deep (~0.05)", ha="right", va="bottom", fontsize=8.5, color=INK2)
    inv = R["inverse_maps"]["bloch"]["echo1"]
    for key, tgt in (("kappa_for_ratio_0.5", 0.5), ("kappa_for_ratio_0.05", 0.05)):
        for x in inv[key][:1]:
            a.plot([x], [tgt], "o", color=BLUE, ms=7, mfc=SURF, mew=1.8, zorder=5)
            a.annotate(f"kappa = {x:.2f}", (x, tgt), xytext=(8, -16 if tgt > 0.1 else 10), textcoords="offset points",
                       fontsize=8.5, color=INK)
    a.set_yscale("log")
    a.set_ylim(0.004, 1.2)
    a.set_xlim(0.28, 2.0)
    a.set_xlabel("transmit scale kappa = B1+ / nominal (shaded: requested 0.3-1.2 sweep)")
    a.set_ylabel("ss-MGOT / v1.83 (b10 echo amplitude ratio)")
    a.set_title("(a) Ratio vs kappa  (B0 = 0, T1 1.9 s, T2 45 ms)")
    a.legend(loc="lower right")

    b = ax[1]
    b0 = R["b0"]
    for k0, col in ((1.0, BLUE), (0.7, ORANGE)):
        tab = b0[k0]["table"]
        x = np.array([0] + [e["b0_hz"] for e in tab])
        y0 = b0[k0]["ratio_e1_at_0"]
        b.plot(x, [y0] + [e["ratio_e1_plus"] for e in tab], "-", color=col, marker="o", ms=4,
               label=f"kappa = {k0:g}, +B0")
        b.plot(x, [y0] + [e["ratio_e1_minus"] for e in tab], "--", color=col, marker="s", ms=4, mfc=SURF,
               label=f"kappa = {k0:g}, -B0")
    b.axvspan(0, 100, color=AQUA, alpha=0.12, lw=0)
    b.text(50, 0.0055, "shimmed rat brain\n(+-50-100 Hz)", ha="center", va="bottom", fontsize=8, color=INK2)
    b.axhline(0.5, color=INK2, lw=0.8, ls=(0, (4, 3)))
    b.axhline(0.05, color=INK2, lw=0.8, ls=(0, (4, 3)))
    b.text(795, 0.52, "~0.5", ha="right", va="bottom", fontsize=8.5, color=INK2)
    b.text(795, 0.052, "~0.05", ha="right", va="bottom", fontsize=8.5, color=INK2)
    b.set_yscale("log")
    b.set_ylim(0.004, 1.2)
    b.set_xlim(0, 800)
    b.set_xlabel("|B0 offset| [Hz]   (Bloch, kappa fixed)")
    b.set_ylabel("ss-MGOT / v1.83 (echo 1)")
    b.set_title("(b) Ratio vs B0 offset")
    b.legend(loc="lower left", bbox_to_anchor=(0.18, 0.0))
    fig.tight_layout()
    _save(fig, out / "sim_ratio_vs_kappa_and_B0.png")


def fig_amplitudes(R, out):
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.4))
    for a, idx, title in ((ax[0], 0, "(a) Echo 1 (k-space centre)"), (ax[1], None, "(b) Mean of echoes 1-8")):
        for model, ls, lw, alpha in (("bloch", "-", 2.4, 1.0), ("epg166", "--", 1.5, 1.0), ("epg180", ":", 1.5, 1.0)):
            rows = _rows(R, model)
            k = np.array([r["kappa"] for r in rows])
            for key, col in (("c", BLUE), ("s", ORANGE)):
                if key == "s" and model == "epg166":
                    continue            # ss-MGOT EPG is identical for the two conventional variants
                y = [(r[key][idx] if idx is not None else r[key].mean()) for r in rows]
                lab = None
                if model == "bloch":
                    lab = NAMES[key]
                a.plot(k, y, ls, color=col, lw=lw, alpha=alpha, label=lab)
        a.set_xlim(0.28, 2.0)
        a.set_yscale("log")
        a.set_xlabel("transmit scale kappa")
        a.set_ylabel("|signal| [M0 x 1 mm slice]")
        a.set_title(title)
    from matplotlib.lines import Line2D
    h1, _ = ax[0].get_legend_handles_labels()
    extra = [Line2D([0], [0], color=INK2, ls="-", lw=2.4), Line2D([0], [0], color=INK2, ls="--", lw=1.5),
             Line2D([0], [0], color=INK2, ls=":", lw=1.5)]
    ax[0].legend(h1 + extra, [h.get_label() for h in h1] + ["Bloch (event model)", "EPG (v1.83 refocus 166.4 deg)", "EPG (nominal 180 deg)"],
                 loc="lower right")
    fig.tight_layout()
    _save(fig, out / "sim_echo_amplitude_vs_kappa.png")


NAMES = {"c": "conventional DW-FSE (v1.83)", "s": "ss-MGOT (v1.912)"}


def fig_fits(R, out):
    fig, ax = plt.subplots(2, 2, figsize=(11.5, 7.6), sharex=True)
    panels = (("v183_invivo", ax[0, 0], "v1.83, in vivo (surface coil)"), ("ssmgot_invivo", ax[0, 1], "ss-MGOT, in vivo (surface coil)"),
              ("v183_exvivo", ax[1, 0], "v1.83, ex vivo PBS (volume coil)"), ("ssmgot_exvivo", ax[1, 1], "ss-MGOT, ex vivo PBS (volume coil)"))
    x = np.arange(1, 9)
    for key, a, title in panels:
        f = R["fits"][key]
        a.plot(x, f["measured"], "o", color=INK, ms=7, label="measured", zorder=6)
        b = f["bloch"]
        a.plot(x, b["direct_bloch_train"], "-", color=BLUE, lw=2.2, marker="s", ms=4,
               label=f"Bloch fit: kappa {b['kappa']:.2f}" + (f", T2 {b['T2_s'] * 1e3:.0f} ms" if key.endswith("invivo") else "") + f"  (rms {b['direct_bloch_rms']:.3f})")
        e = f["epg180"]
        a.plot(x, e["model_train"], "--", color=ORANGE, lw=1.8, marker="^", ms=4,
               label=f"EPG fit (180 deg): kappa {e['kappa']:.2f}" + (f", T2 {e['T2_s'] * 1e3:.0f} ms" if key.endswith("invivo") else "") + f"  (rms {e['rms']:.3f})")
        if "epg166" in f:
            g = f["epg166"]
            a.plot(x, g["model_train"], ":", color=AQUA, lw=2.0, marker="v", ms=4,
                   label=f"EPG fit (166.4 deg): kappa {g['kappa']:.2f}" + (f", T2 {g['T2_s'] * 1e3:.0f} ms" if key.endswith("invivo") else "") + f"  (rms {g['rms']:.3f})")
        a.set_title(title)
        a.set_ylim(0, 1.08)
        a.legend(loc="upper right" if key.startswith("ssmgot") or key.endswith("exvivo") else "upper right", fontsize=8)
        if key.endswith("exvivo"):
            a.set_xlabel("echo number")
        if key.startswith("v183"):
            a.set_ylabel("echo / echo 1")
    fig.suptitle("Measured navigator echo trains (b10, whole-object projection) vs fitted models", y=1.0, fontsize=11)
    fig.tight_layout()
    _save(fig, out / "sim_echo_trains_measured_vs_fitted.png")


def fig_mapping(R, out):
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.5))
    a = ax[0]
    for model, col, ls, lab in (("bloch", BLUE, "-", "Bloch, echo 1"), ("epg166", ORANGE, "--", "EPG (166.4), echo 1")):
        t = R["lr_1.6"][model]["echo1"]
        kr = [e["kappa_right"] for e in t if e["kappa_left"]]
        a.plot(kr, [e["percent_higher"] for e in t if e["kappa_left"]], ls, color=col, marker="o", ms=5, label=lab)
    t = R["lr_1.6"]["bloch"]["mean"]
    a.plot([e["kappa_right"] for e in t if e["kappa_left"]], [e["percent_higher"] for e in t if e["kappa_left"]], "-",
           color=AQUA, marker="o", ms=4, lw=1.5, label="Bloch, mean of echoes 1-8")
    a.set_xlabel("kappa on the right side (kappa_R)")
    a.set_ylabel("kappa_L / kappa_R - 1  [%] for ratio L/R = 1.6")
    a.set_title("(a) L-R transmit difference needed for 1.6x")
    a.legend(loc="upper right")
    a.set_ylim(0, None)
    b = ax[1]
    for model, col, ls, lab in (("bloch", BLUE, "-", "Bloch, echo 1"), ("epg166", ORANGE, "--", "EPG (166.4), echo 1")):
        t = R["inverse_maps"][model]["echo1"]["deep_vs_surface_10x_drop"]
        ks = [e["kappa_surface"] for e in t if e["kappa_deep"]]
        b.plot(ks, [e["kappa_deep"] for e in t if e["kappa_deep"]], ls, color=col, marker="o", ms=5, label=lab)
    b.plot([0.8, 1.6], [0.8, 1.6], color=INK2, lw=0.8, ls=(0, (4, 3)))
    b.set_xlabel("kappa at the surface")
    b.set_ylabel("kappa at depth giving a 10x lower ratio")
    b.set_title("(b) Depth fall-off of B1+ for 0.5 -> 0.05 (any starting level)")
    b.legend(loc="upper left")
    fig.tight_layout()
    _save(fig, out / "sim_lr_and_depth_mapping.png")


def fig_b0_geometry(R, out):
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.4))
    a = ax[0]
    meta = R["meta"]["rf_events"]
    pulses = {}
    for r in meta["v1912"]:
        pulses.setdefault(r["frame"], abs(r["slice_grad_hz_per_mm"]))
    items = [("ss-MGOT prep 90/180 slab (3 mm)", pulses["v19_slrprep90"], ORANGE, "-"),
             ("ss-MGOT tip-up (1.67 mm)", pulses["v19_slrtip90"], ORANGE, "--"),
             ("ss-MGOT re-excite + imaging 180 (1283 Hz/mm)", pulses["v19_imaging180"], INK2, "-"),
             ("v1.83 90/180 (stock sinc)", abs(meta["v183"][0]["slice_grad_hz_per_mm"]), BLUE, "-")]
    x = np.linspace(0, 800, 50)
    for lab, g, col, ls in items:
        a.plot(x, x / g, ls, color=col, label=f"{lab}: {g:.0f} Hz/mm")
    a.set_xlabel("|B0 offset| [Hz]")
    a.set_ylabel("slice displacement [mm]")
    a.set_title("(a) Displacement of each selective pulse (same sign of gradient)")
    a.legend(loc="upper left", fontsize=8)
    b = ax[1]
    tab = R["b0"][1.0]["table"]
    xx = np.array([0] + [e["b0_hz"] for e in tab])
    for key, col, lab in (("v183_e1_rel", BLUE, "v1.83"), ("ssmgot_e1_rel", ORANGE, "ss-MGOT")):
        b.plot(xx, [1] + [e[key + "_plus"] for e in tab], "-", color=col, marker="o", ms=4, label=f"{lab}, +B0")
        b.plot(xx, [1] + [e[key + "_minus"] for e in tab], "--", color=col, marker="s", ms=4, mfc=SURF, label=f"{lab}, -B0")
    b.axvspan(0, 100, color=AQUA, alpha=0.12, lw=0)
    b.set_xlabel("|B0 offset| [Hz]")
    b.set_ylabel("echo-1 amplitude relative to B0 = 0")
    b.set_title("(b) Each sequence alone (Bloch, kappa = 1)")
    b.set_ylim(0, 1.25)
    b.legend(loc="lower left")
    fig.tight_layout()
    _save(fig, out / "sim_b0_geometry_and_echo1.png")


def make_all(R, out: Path):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    fig_ratio(R, out)
    fig_amplitudes(R, out)
    fig_fits(R, out)
    fig_mapping(R, out)
    fig_b0_geometry(R, out)
