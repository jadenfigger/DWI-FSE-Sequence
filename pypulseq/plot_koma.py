"""
plot_koma.py  -  Plot the CSV files written by koma_sim.jl.

Usage
  python plot_koma.py C:/path/to/my_seq          # the .seq path without ".seq"
  python plot_koma.py C:/path/to/my_seq --save   # also save PNGs

Figures
  1. |signal| vs ADC time (all echoes)
  2. Echo amplitude vs echo number (k-space-center sample and peak)
  3. Snapshots: |Mxy|, phase of Mxy, and Mz of every spin vs z after each
     snapshot block. Crushers show up as a phase helix across z; a good
     refocusing pulse unwinds it, an imperfect one leaves part of it in Mz.
"""
import argparse
import numpy as np
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("stem")
ap.add_argument("--save", action="store_true")
ap.add_argument("--max-snaps", type=int, default=8, help="max snapshot blocks to plot")
args = ap.parse_args()
stem = args.stem[:-4] if args.stem.endswith(".seq") else args.stem

# 1. signal
sig = np.loadtxt(stem + "_koma_signal.csv", delimiter=",", ndmin=2)
plt.figure("Koma signal", figsize=(12, 4))
plt.plot(sig[:, 0] * 1e3, np.hypot(sig[:, 1], sig[:, 2]), ".", ms=2)
plt.xlabel("ADC time [ms]"); plt.ylabel("|signal| / M0"); plt.title("Raw signal")

# 2. echoes
ech = np.loadtxt(stem + "_koma_echoes.csv", delimiter=",", ndmin=2)
plt.figure("Koma echoes", figsize=(6, 4))
plt.plot(ech[:, 0], ech[:, 1], "o-", label="k-space center sample")
plt.plot(ech[:, 0], ech[:, 2], "s--", label="peak in ADC window")
plt.xlabel("echo #"); plt.ylabel("|signal| / M0"); plt.legend(); plt.title("Echo amplitudes")

# 3. snapshots
snap = np.loadtxt(stem + "_koma_snapshots.csv", delimiter=",", ndmin=2)
blocks = np.unique(snap[:, 0]).astype(int)[: args.max_snaps]
fig, axs = plt.subplots(3, len(blocks), figsize=(2.6 * len(blocks), 7),
                        sharex=True, sharey="row", squeeze=False, num="Koma snapshots")
for j, b in enumerate(blocks):
    d = snap[snap[:, 0] == b]
    d = d[np.argsort(d[:, 1])]
    zmm, mxy = d[:, 1] * 1e3, d[:, 2] + 1j * d[:, 3]
    axs[0, j].plot(zmm, np.abs(mxy), ".", ms=1)
    axs[1, j].plot(zmm, np.angle(mxy), ".", ms=1)
    axs[2, j].plot(zmm, d[:, 4], ".", ms=1)
    axs[0, j].set_title(f"after block {b}\n|mean Mxy|={abs(mxy.mean()):.3f}", fontsize=9)
    axs[2, j].set_xlabel("z [mm]")
axs[0, 0].set_ylabel("|Mxy|"); axs[1, 0].set_ylabel("phase Mxy [rad]"); axs[2, 0].set_ylabel("Mz")
fig.tight_layout()

if args.save:
    for n in plt.get_fignums():
        f = plt.figure(n)
        f.savefig(f"{stem}_{f.get_label().replace(' ', '_')}.png", dpi=150)
plt.show()
