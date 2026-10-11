"""Publication-style pulse-sequence diagrams for the 2026-10-10 slide deck.

Source model only: events come from the repo PPL interpreter (dwfse.ppl) run on the
acquired PPL + PPR pairs; these are NOT measured scanner waveforms.

  v1.81  DW-FSE   : scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl  + FSE-DWI_10-10-2026_v181_testA.ppr
  v1.911 ss-MGOT  : scanner/FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl + FSE-DWI_10-10-2026_v1911_testB.ppr

Shot shown: the first IMAGING shot (nav_cnt = 1, first echo-train view group) of the
volume with diff_acq_cnt = 3, i.e. acq_b[3] = 1000 s/mm^2 (read-axis diffusion,
diff_grad = 8216 DAC).  Gradients are DAC amplitudes, normalised per axis to the
largest value of that axis over both windows (so the two sequences are comparable).

    python docs/data/oct10_sequence_diagrams.py [--cache FILE]

Writes docs/figures/oct10_slides/sequence_v181.png, sequence_v1911.png, sequence_both.png
"""
from __future__ import annotations

import argparse
import bisect
import pickle
import sys
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs/figures/oct10_slides"
B_INDEX = 3            # acq_b[3] = 1000 s/mm^2
SEQS = {
    "v181": dict(title="v1.81 DW-FSE", ver="1.81",
                 ppr="experiments/FSE-DWI_10-10-2026_v181_testA/FSE-DWI_10-10-2026_v181_testA.ppr"),
    "v1911": dict(title="v1.911 ss-MGOT", ver="1.911",
                  ppr="experiments/FSE-DWI_10-10-2026_v1911_testB/FSE-DWI_10-10-2026_v1911_testB.ppr"),
}
T_END = {"v181": 88.1, "v1911": 104.3}    # ms: end of echo 3 plus its rewinder / next crusher
T_START = -3.0

# palette
C_GRAD_EDGE = "#2b2b2b"
C_GRAD_FILL = "#d9d9d9"
C_DIFF = "#f6b26b"
C_DIFF_EDGE = "#b45f06"
C_PRE = "#9fd5cf"
C_PRE_EDGE = "#2a7f76"
C_90 = "#7fa7d6"
C_90_EDGE = "#1f4e8c"
C_180 = "#e58c8c"
C_180_EDGE = "#a32a2a"
C_ADC = "#8fbf8f"
C_ADC_EDGE = "#2f6b2f"
C_TXT = "#222222"


# --------------------------------------------------------------------------- extraction
def extract(key: str) -> dict:
    from dwfse.ppl.run import map_events
    from examples import v19_validate_events as old
    from dwfse.ppl.ledger import build_ledger

    cfg = SEQS[key]
    ppl = ROOT / f"scanner/FSE_dwi_CPMG_non_CPMG_twoTE-{cfg['ver']}.ppl"
    it = map_events(ppl, ROOT / cfg["ppr"], max_shots=58, **old.NOMINAL)
    shots = [e[1] for e in it.misc_events if e[0] == "shot"]
    tgt = next(a for a in it.adc if a["vars"]["diff_acq_cnt"] == B_INDEX and a["vars"]["nav_cnt"] == 1)
    k = bisect.bisect_right(shots, tgt["t_init"])
    led = build_ledger(it, k)
    t0 = led["rf"][0]["t_center"]
    rfcal = it.vars["rfcal"].value
    vfa = [int(x) for x in it.vars["v19_flip_tenths"].value] if "v19_flip_tenths" in it.vars else None
    d = dict(
        key=key, shot=k, t0_us=t0, rfcal=rfcal, vfa_tenths=vfa,
        acq_b=int(it.vars["acq_b"].value[B_INDEX]), diff_grad=int(it.vars["diff_grad"].value),
        esp_ms=int(it.vars["esp"].value), te_ms=int(it.vars["te"].value),
        nsamp=int(it.vars["no_samples"].value),
        rf=[dict(frame=p["frame"], mul=p["mul"], t=(p["t"][0] - t0) / 1e3, amp=np.asarray(p["amp"]),
                 dur=p["dt"] * len(p["samples"]) / 1e3, tc=(p["t_center"] - t0) / 1e3) for p in led["rf"]],
        adc=[dict(t_init=(a["t_init"] - t0) / 1e3, sp_us=a["sample_period_ticks"] / 10.0,
                  disc=a["discard"]) for a in led["adc"]],
        G={ax: ((led["G"][ax].t - t0) / 1e3, np.asarray(led["G"][ax].v)) for ax in "SPR"},
    )
    return d


def load(key, cache):
    if cache:
        p = Path(cache).with_name(Path(cache).stem + f"_{key}.pkl")
        if p.exists():
            return pickle.load(open(p, "rb"))
    d = extract(key)
    if cache:
        pickle.dump(d, open(p, "wb"))
    return d


# --------------------------------------------------------------------------- drawing helpers
def step_poly(t, v, a, b):
    """Return x, y of a stepped waveform restricted to [a, b] ms (t are edges, v values)."""
    n = len(v)
    lo, hi = t[:-1], t[1:]
    m = (hi > a) & (lo < b)
    lo, hi, vv = np.clip(lo[m], a, b), np.clip(hi[m], a, b), v[m]
    x = np.column_stack([lo, hi]).ravel()
    y = np.repeat(vv, 2)
    return x, y


def draw_grad(ax, t, v, scale, t_end, regions=()):
    """Gradient waveform: grey fill, optional coloured regions [(t0, t1, fill, edge)]."""
    x, y = step_poly(t, v / scale, T_START, t_end)
    ax.fill_between(x, 0, y, color=C_GRAD_FILL, lw=0, zorder=2)
    for (a, b, fc, ec) in regions:
        m = (x >= a - 1e-9) & (x <= b + 1e-9)
        ax.fill_between(x[m], 0, y[m], color=fc, lw=0, zorder=3)
        ax.plot(x[m], y[m], color=ec, lw=0.9, zorder=4)
    ax.plot(x, y, color=C_GRAD_EDGE, lw=0.7, zorder=3)
    for (a, b, fc, ec) in regions:     # redraw coloured edges on top
        m = (x >= a - 1e-9) & (x <= b + 1e-9)
        ax.plot(x[m], y[m], color=ec, lw=1.0, zorder=5)


def draw_rf(ax, p, kind):
    fc, ec = (C_90, C_90_EDGE) if kind == "ex" else (C_180, C_180_EDGE)
    t = p["t"] + np.arange(len(p["amp"])) * (p["dur"] / len(p["amp"]))
    ax.fill_between(t, 0, p["amp"], color=fc, lw=0, zorder=3, alpha=0.9)
    ax.plot(t, p["amp"], color=ec, lw=0.7, zorder=4)


def style_axis(ax, ylabel, fs):
    ax.set_ylabel(ylabel, rotation=0, ha="right", va="center", fontsize=fs, color=C_TXT, labelpad=6)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.set_yticks([])
    ax.tick_params(axis="x", labelsize=fs)
    ax.axhline(0, color="#777777", lw=0.5, zorder=1)


# --------------------------------------------------------------------------- one sequence
def draw_sequence(axes, d, gscale, fs=8.0, small=7.0, t_end=None, show_xlabel=True):
    key = d["key"]
    t_end = t_end or T_END[key]
    axR, axS, axP, axG, axA = axes
    # --- RF pulses
    rfs = [p for p in d["rf"] if p["tc"] <= t_end]
    amax = max(np.abs(p["amp"]).max() for p in rfs)
    # classify: excitation-like (90) vs refocusing (180/VFA)
    spec = classify_rf(d, rfs)
    for p, (kind, label) in zip(rfs, spec):
        q = dict(p)
        q["amp"] = p["amp"] / amax
        draw_rf(axR, q, kind)
    axR.set_ylim(-0.8, 1.95 if key == "v1911" else 1.75)
    style_axis(axR, "RF", fs)
    d["_rf_spec"] = list(zip(rfs, spec))
    # --- gradients
    ax_by = {"S": axS, "P": axP, "R": axG}
    for ax_key, ax_ in ax_by.items():
        t, v = d["G"][ax_key]
        regions = []
        if ax_key == "R":
            regions.append((4.5, 9.3, C_DIFF, C_DIFF_EDGE))
            regions.append((44.5, 49.3, C_DIFF, C_DIFF_EDGE))
            if key == "v181":
                regions.append((49.45, 50.62, C_PRE, C_PRE_EDGE))
        draw_grad(ax_, t, v, gscale[ax_key], t_end, regions)
        ax_.set_ylim({"S": (-1.1, 0.55), "P": (-0.3, 1.2), "R": (-1.12, 0.85)}[ax_key])
    style_axis(axS, "Gslice", fs)
    style_axis(axP, "Gphase", fs)
    style_axis(axG, "Gread", fs)
    # --- ADC boxes
    adc_t = []
    for a in d["adc"]:
        t1 = a["t_init"] + a["disc"] * a["sp_us"] / 1e3
        t2 = t1 + d["nsamp"] * a["sp_us"] / 1e3
        mid = (t1 + t2) / 2
        if mid > t_end - 0.5 or len(adc_t) >= 3:
            continue
        adc_t.append((t1, t2, mid))
        axA.add_patch(plt.Rectangle((t1, 0.15), t2 - t1, 0.7, fc=C_ADC, ec=C_ADC_EDGE, lw=0.8, zorder=3))
    axA.set_ylim(0, 1.7)
    style_axis(axA, "ADC", fs)
    axA.axhline(0.15, color="#777777", lw=0.5, zorder=1)
    for ax_ in axes:
        ax_.set_xlim(T_START, d["xmax"])
    d["_adc"] = adc_t
    return d


def classify_rf(d, rfs):
    """(kind, label) per pulse: kind 'ex' for 90-type, 'ref' for 180-type."""
    out = []
    if d["key"] == "v181":
        for i, p in enumerate(rfs):
            out.append(("ex", "90°") if i == 0 else ("ref", "180°"))
    else:
        tenths = d["vfa_tenths"]
        n_img = 0
        for p in rfs:
            f = p["frame"]
            if f == "v19_slrprep90":
                out.append(("ex", "90°"))
            elif f == "v19_slrprep180":
                out.append(("ref", "180°"))
            elif f == "v19_slrtip90":
                out.append(("ex", "90°"))
            elif f == "v19_reexc90":
                out.append(("ex", "90°"))
            else:
                out.append(("ref", f"{tenths[n_img] / 10:.0f}°"))
                n_img += 1
    return out


def annotate(axes, d, fs=8.0, small=7.0):
    axR, axS, axP, axG, axA = axes
    key = d["key"]
    spec = d["_rf_spec"]
    amax = max(np.abs(p["amp"]).max() for p, _ in spec)
    # flip labels
    for p, (kind, label) in spec:
        y = p["amp"].max() / amax + 0.06
        x = p["tc"]
        if key == "v1911" and p["frame"] == "v19_slrtip90":
            label = "90°" + chr(10) + "tip-up"
        elif key == "v1911" and p["frame"] == "v19_reexc90":
            label = "90°" + chr(10) + "re-exc."
        axR.text(x, y, label, ha="center", va="bottom", fontsize=small, color=C_TXT, zorder=6,
                 linespacing=1.0)
    # VFA bracket label
    if key == "v1911":
        vf = [p for p, (k, l) in spec if p["frame"] == "v19_imaging180"]
        a, b = vf[0]["tc"] - 1.0, vf[-1]["tc"] + 1.0
        yb = 1.45
        axR.plot([a, b], [yb, yb], color="#555555", lw=0.8, zorder=5)
        axR.text((a + b) / 2, yb + 0.07, "variable flip angles", ha="center", va="bottom", fontsize=small,
                 color="#555555", style="italic", zorder=6)
    # ESP dimension arrow below the RF baseline, between the first two imaging refocusing pulses
    refs = [p for p, (k, l) in spec if p["frame"] == "v19_imaging180" or
            (key == "v181" and p is not spec[0][0] and p["tc"] > 50)]
    ctrs = [p["tc"] for p in refs][:2]
    yb = -0.38
    axR.annotate("", xy=(ctrs[1], yb), xytext=(ctrs[0], yb),
                 arrowprops=dict(arrowstyle="<->", lw=0.8, color="#444444", shrinkA=0, shrinkB=0), zorder=6)
    axR.text((ctrs[0] + ctrs[1]) / 2, yb - 0.08, f"ESP {d['esp_ms']} ms", ha="center", va="top",
             fontsize=small, color="#444444", zorder=6)
    # diffusion label (once), above the first read lobe
    axG.text(6.9, 0.12, "diffusion", ha="center", va="bottom", fontsize=small + 0.5, color=C_DIFF_EDGE, zorder=6)
    if key == "v181":
        axG.annotate("read prephaser", xy=(49.9, 0.36), xytext=(38.5, 0.50), fontsize=small - 0.3,
                     color=C_PRE_EDGE, ha="right", va="center", zorder=6,
                     arrowprops=dict(arrowstyle="-", lw=0.6, color=C_PRE_EDGE, shrinkA=1, shrinkB=0))
    else:
        axP.text(57.3, 1.05, "spoiler", ha="center", va="bottom", fontsize=small - 0.3, color="#555555",
                 style="italic", zorder=6)
        axS.text(68.0, 0.12, "fused slice lobes", ha="center", va="bottom", fontsize=small - 0.3,
                 color="#555555", style="italic", zorder=6)
    # first echo time, above ADC box 1
    t1, t2, mid = d["_adc"][0]
    axA.text(mid, 0.97, f"first echo {mid:.1f} ms".replace(".0 ms", " ms"), ha="center", va="bottom",
             fontsize=small, color="#444444", zorder=6)


def title(fig, ax_top, text, fs=11):
    bb = ax_top.get_position()
    fig.text(0.012, bb.y1 + 0.012, text, ha="left", va="bottom", fontsize=fs, fontweight="bold", color=C_TXT)


# --------------------------------------------------------------------------- figures
def make_individual(d, gscale, path, xmax):
    fig = plt.figure(figsize=(10, 4.2), dpi=200)
    gs = GridSpec(5, 1, figure=fig, height_ratios=[1.6, 0.9, 0.6, 1.5, 0.55], hspace=0.10,
                  left=0.095, right=0.985, top=0.88, bottom=0.14)
    axes = [fig.add_subplot(gs[0])] + [fig.add_subplot(gs[i], sharex=None) for i in range(1, 5)]
    d["xmax"] = xmax
    draw_sequence(axes, d, gscale)
    annotate(axes, d)
    for a in axes[:-1]:
        a.tick_params(axis="x", labelbottom=False, length=0)
    axes[-1].spines["bottom"].set_visible(True)
    axes[-1].spines["bottom"].set_position(("data", 0))
    axes[-1].set_xticks(np.arange(0, xmax, 10))
    axes[-1].tick_params(axis="x", length=3, pad=3)
    axes[-1].set_xlabel("time from excitation (ms)", fontsize=8, color=C_TXT, labelpad=3)
    title(fig, axes[0], SEQS[d["key"]]["title"])
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def make_combined(d1, d2, gscale, path, xmax):
    fig = plt.figure(figsize=(10, 5.4), dpi=200)
    ratios = [1.6, 0.9, 0.6, 1.5, 0.55]
    gs = GridSpec(11, 1, figure=fig, height_ratios=ratios + [1.1] + ratios, hspace=0.08,
                  left=0.095, right=0.985, top=0.935, bottom=0.085)
    rows1 = [fig.add_subplot(gs[i]) for i in range(5)]
    rows2 = [fig.add_subplot(gs[6 + i]) for i in range(5)]
    for rows, d in ((rows1, d1), (rows2, d2)):
        d["xmax"] = xmax
        draw_sequence(rows, d, gscale)
        annotate(rows, d, fs=7.0, small=6.3)
        for a in rows[:-1]:
            a.tick_params(axis="x", labelbottom=False, length=0)
        rows[-1].spines["bottom"].set_visible(True)
        rows[-1].set_xticks(np.arange(0, xmax, 10))
        rows[-1].tick_params(axis="x", length=3, pad=3, labelsize=7)
        for a in rows:
            for lab in a.get_yticklabels():
                pass
    rows2[-1].set_xlabel("time from excitation (ms)", fontsize=7.5, color=C_TXT, labelpad=2)
    for rows, d in ((rows1, d1), (rows2, d2)):
        for a in rows:
            a.yaxis.label.set_fontsize(7)
    title(fig, rows1[0], SEQS["v181"]["title"], fs=10)
    title(fig, rows2[0], SEQS["v1911"]["title"], fs=10)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=None, help="optional pickle stem to cache extracted events")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    data = {k: load(k, args.cache) for k in SEQS}
    # per-axis normalisation over both windows
    gscale = {}
    for ax in "SPR":
        m = 0.0
        for k, d in data.items():
            t, v = d["G"][ax]
            sel = (t[:-1] > T_START) & (t[:-1] < T_END[k])
            m = max(m, float(np.abs(v[sel]).max()))
        gscale[ax] = m
    for k, d in data.items():
        print(k, "shot", d["shot"], "b", d["acq_b"], "diff_grad", d["diff_grad"], "ESP", d["esp_ms"], "TE", d["te_ms"])
    make_individual(data["v181"], gscale, OUT / "sequence_v181.png", 91.0)
    make_individual(data["v1911"], gscale, OUT / "sequence_v1911.png", 107.0)
    make_combined(data["v181"], data["v1911"], gscale, OUT / "sequence_both.png", 107.0)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
