"""
plot_koma.py  -  Plot the CSV files written by koma_sim.jl (or bloch_sim.py --csv).

Usage
  python plot_koma.py C:/path/to/my_seq                 # the .seq path without ".seq"
  python plot_koma.py my_seq --blocks 7 11 15           # only these block snapshots
  python plot_koma.py my_seq --snaps 1 2                # only these time snapshots (see below)
  python plot_koma.py my_seq --sim bloch                # read <name>_bloch_*.csv instead of _koma_
  python plot_koma.py my_seq --save                     # also save PNGs

Figures
  1. |signal| vs ADC time (all echoes)
  2. Echo amplitude vs echo number (k-space-center sample and peak)
  3. Block snapshots (<name>_koma_snapshots.csv): |Mxy|, phase of Mxy, Mz of every spin
     vs z at the END of selected blocks (koma_sim.jl `snap_blocks`; block numbers as
     shown by `python plot_blocks.py my_seq.seq`).
  4. Time snapshots (<name>_koma_snapshots_t.csv): the same at any chosen times,
     e.g. the centre of every ADC = the echo. Make the cut sequences first with
         python snapshot_seqs.py my_seq.seq --at adc
     then run koma_sim.jl; panel titles come from <name>_snap/index.csv.
  Crushers show up as a phase helix across z; at an echo centre the refocused part has a
  flat phase, and whatever is still wound is not contributing to that echo.
"""
import argparse
import csv
import os

import matplotlib.pyplot as plt
import numpy as np

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("stem")
ap.add_argument("--sim", default="koma", help="CSV prefix: koma (koma_sim.jl) or bloch (bloch_sim.py --csv)")
ap.add_argument("--blocks", nargs="*", type=int, help="block snapshots to plot (default: first --max-snaps)")
ap.add_argument("--snaps", nargs="*", type=int, help="time snapshots to plot (default: first --max-snaps)")
ap.add_argument("--max-snaps", type=int, default=8, help="max panels per snapshot figure")
ap.add_argument("--save", action="store_true")
args = ap.parse_args()
stem = args.stem[:-4] if args.stem.endswith(".seq") else args.stem
pre = f"{stem}_{args.sim}"


def load(name):
    f = f"{pre}_{name}.csv"
    if not os.path.isfile(f):
        print(f"(no {f})")
        return None
    return np.loadtxt(f, delimiter=",", ndmin=2)


def snapshot_figure(snap, ids, titles, figname):
    fig, axs = plt.subplots(3, len(ids), figsize=(2.6 * len(ids) + 0.8, 7),
                            sharex=True, sharey="row", squeeze=False, num=figname)
    for j, b in enumerate(ids):
        d = snap[snap[:, 0] == b]
        d = d[np.argsort(d[:, 1])]
        zmm, mxy = d[:, 1] * 1e3, d[:, 2] + 1j * d[:, 3]
        axs[0, j].plot(zmm, np.abs(mxy), ".", ms=1)
        axs[1, j].plot(zmm, np.angle(mxy), ".", ms=1)
        axs[2, j].plot(zmm, d[:, 4], ".", ms=1)
        axs[0, j].set_title(f"{titles[b]}\n|mean Mxy|={abs(mxy.mean()):.3f}", fontsize=9)
        axs[2, j].set_xlabel("z [mm]")
    axs[0, 0].set_ylabel("|Mxy|"); axs[1, 0].set_ylabel("phase Mxy [rad]"); axs[2, 0].set_ylabel("Mz")
    fig.tight_layout()


def pick(available, wanted):
    if wanted:
        missing = sorted(set(wanted) - set(available))
        if missing:
            print(f"not in the CSV: {missing}; available: {available}")
        return [w for w in wanted if w in available]
    return available[: args.max_snaps]


# 1. signal
sig = load("signal")
if sig is not None:
    plt.figure("signal", figsize=(12, 4))
    plt.plot(sig[:, 0] * 1e3, np.hypot(sig[:, 1], sig[:, 2]), ".", ms=2)
    plt.xlabel("ADC time [ms]"); plt.ylabel("|signal| / M0"); plt.title(f"Raw signal ({args.sim})")

# 2. echoes
ech = load("echoes")
if ech is not None:
    plt.figure("echoes", figsize=(6, 4))
    plt.plot(ech[:, 0], ech[:, 1], "o-", label="k-space center sample")
    plt.plot(ech[:, 0], ech[:, 2], "s--", label="peak in ADC window")
    plt.xlabel("echo #"); plt.ylabel("|signal| / M0"); plt.legend(); plt.title(f"Echo amplitudes ({args.sim})")

# 3. block snapshots
snap = load("snapshots")
if snap is not None:
    ids = pick(np.unique(snap[:, 0]).astype(int).tolist(), args.blocks)
    if ids:
        snapshot_figure(snap, ids, {b: f"end of block {b}" for b in ids}, "snapshots (blocks)")

# 4. time snapshots
snap_t = load("snapshots_t")
if snap_t is not None:
    titles = {}
    idx = os.path.join(stem + "_snap", "index.csv")
    if os.path.isfile(idx):
        for r in csv.DictReader(open(idx)):
            titles[int(r["snap"])] = f"{r['what']}\nt={float(r['time_ms']):.2f} ms (blk {r['block']})"
    ids = pick(np.unique(snap_t[:, 0]).astype(int).tolist(), args.snaps)
    if ids:
        snapshot_figure(snap_t, ids, {k: titles.get(k, f"snap {k}") for k in ids}, "snapshots (times)")

if args.save:
    for n in plt.get_fignums():
        f = plt.figure(n)
        f.savefig(f"{pre}_{f.get_label().replace(' ', '_').replace('(', '').replace(')', '')}.png", dpi=150)
if plt.get_backend().lower() != "agg":
    plt.show()
