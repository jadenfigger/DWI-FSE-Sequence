"""
epg.py  -  Phase Distribution Graph (generalized EPG) simulation of a Pulseq .seq file
                  with MRzero-Core.

How MRzero thinks about your sequence
  * A "repetition" in MRzero = everything from one RF pulse up to the next RF pulse.
    In an FSE train that is one echo-spacing interval. Repetition 0 starts at the 90.
  * Every RF pulse splits each existing state into up to 3 new states
    (transverse kept, transverse conjugated/refocused, stored as longitudinal), exactly
    like the EPG / Hennig echo-pathway picture. MRzero tracks each state by its real
    3D gradient moment (k_x, k_y, k_z) plus its off-resonance dephasing time (tau),
    so irregular gradients (diffusion lobes, crushers, phase encoding) are handled.
  * RF pulses are treated as instantaneous rotations (no slice profile).

What this script does
  1. Imports the .seq and builds a single-voxel phantom (T1, T2, T2', D, B0, B1)
  2. Builds the graph and simulates the signal
  3. Plots the graph (transverse states vs repetition, for k_x, k_y, k_z and tau)
  4. Prints, for each echo, the strongest coherence pathways that produce signal
  5. Sweeps B1 scale and B0 offset and plots echo amplitude vs echo number

Usage
  python dw.py epg my_seq.seq
  python dw.py epg my_seq.seq --b1 0.85 --b0 30 --T2 0.06 --D 2.0
  python dw.py epg my_seq.seq --b1-sweep 0.6 0.7 0.8 0.9 1.0 --b0-sweep 0 25 50 100
  python dw.py epg my_seq.seq --max-reps 20     # only simulate the first 20 RF intervals

Requires: pip install MRzeroCore matplotlib numpy torch
"""
import argparse
import os
import contextlib
import io

import numpy as np
import matplotlib.pyplot as plt
import torch
import MRzeroCore as mr0


# ------------------------------------------------------------------ helpers
def quiet(fn, *a, **kw):
    """Run fn while hiding MRzero's progress prints (Python and native Rust stdout)."""
    import os
    import sys
    sys.stdout.flush()
    saved = os.dup(1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 1)
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*a, **kw)
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(devnull)
        os.close(saved)


def make_phantom(args, b1=None, b0=None):
    """One voxel at the isocenter.

    voxel_size matters: a state with gradient moment k only contributes signal
    in proportion to sinc(k * voxel_size). So set it to your real voxel
    (in-plane resolution x slice thickness). Then crushed states are
    correctly suppressed and only refocused pathways produce echoes.
    """
    vs = [v * 1e-3 for v in args.voxel_mm]
    ph = mr0.CustomVoxelPhantom(
        pos=[[0.0, 0.0, 0.0]],
        PD=1.0, T1=args.T1, T2=args.T2, T2dash=args.T2dash,
        D=args.D,                                  # units: 1e-3 mm^2/s
        B0=args.b0 if b0 is None else b0,          # Hz
        B1=args.b1 if b1 is None else b1,          # relative flip-angle scale
        voxel_size=vs, voxel_shape="box",
    )
    return ph.build()


def simulate(seq, data, args):
    graph = quiet(mr0.compute_graph, seq, data, args.max_states, args.min_mag)
    signal = quiet(mr0.execute_graph, graph, seq, data, print_progress=False)
    return graph, signal[:, 0].detach().cpu().numpy()


def adc_layout(seq):
    """For every repetition with ADC: (rep index, sample slice, absolute sample times)."""
    out, t_rep, n = [], 0.0, 0
    for i, rep in enumerate(seq):
        et = rep.event_time.detach().cpu().numpy()
        adc = rep.adc_usage.detach().cpu().numpy() > 0
        t_abs = t_rep + np.cumsum(et)
        if adc.any():
            out.append((i, slice(n, n + adc.sum()), t_abs[adc]))
            n += adc.sum()
        t_rep += et.sum()
    return out


def echo_amplitudes(signal, layout):
    """Peak |signal| and center-sample |signal| for each ADC window (echo)."""
    peak = np.array([np.abs(signal[s]).max() for _, s, _ in layout])
    center = np.array([np.abs(signal[s])[len(signal[s]) // 2] for _, s, _ in layout])
    return peak, center


def _mag(state, conj):
    m = complex(state.prepass_mag)
    return m.conjugate() if conj else m


def decompose_state(state, level, min_frac=1e-3, max_paths=20000):
    """Split one graph state into the echo pathways that feed it.

    A state's magnetization is the sum of its ancestors' contributions
    (ancestor magnetization x RF transfer factor, conjugated for "-" transfers).
    Walking back through the graph and splitting proportionally at every
    branch gives every coherence pathway and its complex weight.

    Labels (one per RF interval, oldest first) are Hennig's echo-pathway signs:
      + / - : transverse; sign of that interval's dephasing in the total phase.
              The first transverse interval is defined as "+".
      Z     : stored longitudinally (phase kept, no dephasing, relaxes with T1)
      Z0    : unencoded longitudinal magnetization (initial or regrown by T1)
    An echo forms when the interval moments, weighted by these signs, sum to zero.
    """
    total = abs(complex(state.prepass_mag)) or 1.0
    out = []
    # stack items: (state, level, weight, conj, sign, labels_newest_first)
    stack = [(state, level, complex(state.prepass_mag), False, +1, ["+"])]
    while stack and len(out) < max_paths:
        s, lev, w, conj, sign, labels = stack.pop()
        if s.dist_type == "z0" and len(labels) > 1 or not s.ancestors:
            # everything before an unencoded z0 is just "Z0"
            labels = labels + ["Z0"] * (lev - 1)
            out.append((labels[::-1], w))
            continue
        parts = []
        for rel, anc, f in s.ancestors:
            c = (_mag(anc, conj ^ (rel[0] == "-"))) * complex(f)
            parts.append((rel, anc, c))
        tot = sum(c for _, _, c in parts)
        if abs(tot) == 0:
            continue
        for rel, anc, c in parts:
            w_new = w * c / tot
            if abs(w_new) < min_frac * total:
                continue
            new_conj = conj ^ (rel[0] == "-")
            new_sign = -sign if rel[0] == "-" else sign
            if anc.dist_type == "z0":
                lab = "Z0"
            elif anc.dist_type == "z":
                lab = "Z"
            else:
                lab = "+" if new_sign > 0 else "-"
            stack.append((anc, lev - 1, w_new, new_conj, new_sign, labels + [lab]))
    # normalize: first transverse interval is "+"; drop level 0 (before the first pulse)
    res = []
    for labels, w in out:
        labels = labels[1:]
        first = next((l for l in labels if l in "+-"), "+")
        if first == "-":
            labels = [{"+": "-", "-": "+"}.get(l, l) for l in labels]
        res.append((" ".join(labels), w))
    return res


def pathway_report(graph, layout, top=6):
    print("=" * 78)
    print("Echo pathway decomposition (Hennig notation, one label per RF interval, oldest first)")
    print("  + / - : transverse, sign of that interval's dephasing    Z : stored    Z0 : unencoded")
    print("  share = |pathway amplitude| / sum of |all pathway amplitudes| for that echo")
    print("  phase = pathway phase relative to the strongest one (pathways near 180 deg cancel)")
    for e, (rep_i, _, _) in enumerate(layout):
        level = rep_i + 1
        groups = {}
        for s in graph[level]:
            if s.dist_type != "+" or s.emitted_signal < 1e-3:
                continue
            for label, w in decompose_state(s, level):
                groups[label] = groups.get(label, 0j) + w * s.emitted_signal
        if not groups:
            print(f"-- echo {e+1}: no signal-producing states")
            continue
        items = sorted(groups.items(), key=lambda kv: -abs(kv[1]))
        tot = sum(abs(v) for _, v in items)
        ref_phase = np.angle(items[0][1])
        net = abs(sum(v for _, v in items))
        print(f"-- echo {e+1}  (RF interval {rep_i})   {len(items)} pathways,"
              f"  net/sum = {net/tot:.2f}  (1.00 = all pathways in phase)")
        for label, v in items[:top]:
            if abs(v) / tot < 1e-3:
                break
            ph = np.degrees(np.angle(v) - ref_phase)
            ph = (ph + 180) % 360 - 180
            print(f"   {100*abs(v)/tot:5.1f}%  phase {ph:7.1f} deg   {label}")


def plot_graph(graph, title):
    fig, axs = plt.subplots(2, 2, figsize=(12, 8), num=title)
    for ax, d in zip(axs.flat, ["k_x", "k_y", "k_z", "tau"]):
        plt.sca(ax)
        graph.plot(transversal_mag=True, dephasing=d, color="latent signal")
        ax.set_title(f"transverse states: {d}")
    fig.suptitle(title + "   (x axis: RF interval; color: log latent signal)")
    fig.tight_layout()


# --------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("seq_file")
    ap.add_argument("--T1", type=float, default=1.5, help="s")
    ap.add_argument("--T2", type=float, default=0.08, help="s")
    ap.add_argument("--T2dash", type=float, default=0.03, help="T2' in s (intravoxel B0 spread)")
    ap.add_argument("--D", type=float, default=2.0, help="diffusion, 1e-3 mm^2/s")
    ap.add_argument("--b1", type=float, default=1.0, help="B1 scale for the main run")
    ap.add_argument("--b0", type=float, default=0.0, help="B0 offset [Hz] for the main run")
    ap.add_argument("--voxel-mm", type=float, nargs=3, default=[0.2, 0.2, 1.0],
                    help="voxel size x y z [mm]; use your real resolution and slice thickness")
    ap.add_argument("--b1-sweep", type=float, nargs="*", default=[0.6, 0.7, 0.8, 0.9, 1.0])
    ap.add_argument("--b0-sweep", type=float, nargs="*", default=[0, 25, 50, 100, 200])
    ap.add_argument("--max-reps", type=int, default=None,
                    help="only simulate the first N RF intervals (keeps big sequences fast)")
    ap.add_argument("--max-states", type=int, default=500)
    ap.add_argument("--min-mag", type=float, default=1e-4)
    ap.add_argument("--top", type=int, default=6, help="pathways listed per echo")
    ap.add_argument("--save", action="store_true", help="also save figures as PNG")
    ap.add_argument("--outdir", default=".", help="folder for --save")
    args = ap.parse_args(argv)

    seq = quiet(mr0.Sequence.import_file, args.seq_file)
    if args.max_reps:
        seq = mr0.Sequence(list(seq)[: args.max_reps], normalized_grads=seq.normalized_grads)

    print("=" * 78)
    print(f"{args.seq_file}: {len(seq)} RF intervals, duration {seq.get_duration()*1e3:.2f} ms")
    for i, rep in enumerate(seq[:12]):
        print(f"  interval {i:3d}: {rep.pulse.usage.name:6s} flip {np.degrees(float(rep.pulse.angle)):6.1f} deg"
              f"  phase {np.degrees(float(rep.pulse.phase)) % 360:6.1f} deg"
              f"  ADC samples {int(rep.adc_usage.gt(0).sum())}")
    if len(seq) > 12:
        print("  ...")

    layout = adc_layout(seq)

    # ---- main run
    data = make_phantom(args)
    graph, sig = simulate(seq, data, args)
    print(f"Graph size per interval: {[len(r) for r in graph[:20]]}{' ...' if len(graph) > 20 else ''}")
    pathway_report(graph, layout, args.top)
    plot_graph(graph, f"PDG  B1={args.b1}  B0={args.b0} Hz")

    # ---- signal vs time (main run vs ideal)
    _, sig_ideal = simulate(seq, make_phantom(args, b1=1.0, b0=0.0), args)
    t_all = np.concatenate([t for _, _, t in layout]) * 1e3
    plt.figure("Signal vs time", figsize=(12, 4))
    plt.plot(t_all, np.abs(sig_ideal), ".", ms=2, label="B1=1, B0=0")
    plt.plot(t_all, np.abs(sig), ".", ms=2, label=f"B1={args.b1}, B0={args.b0} Hz")
    plt.xlabel("time [ms]"); plt.ylabel("|signal|"); plt.legend()
    plt.title("ADC samples (gaps between echoes not shown)")

    # ---- B1 sweep
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.5), num="Sweeps")
    for b1 in args.b1_sweep:
        _, s = simulate(seq, make_phantom(args, b1=b1, b0=args.b0), args)
        peak, center = echo_amplitudes(s, layout)
        axs[0].plot(np.arange(1, len(center) + 1), center, "o-", ms=3, label=f"B1={b1}")
    axs[0].set_xlabel("echo #"); axs[0].set_ylabel("|signal| at k-space center sample")
    axs[0].set_title(f"B1 sweep (B0={args.b0} Hz)"); axs[0].legend(fontsize=8)

    # ---- B0 sweep
    for b0 in args.b0_sweep:
        _, s = simulate(seq, make_phantom(args, b1=args.b1, b0=b0), args)
        peak, center = echo_amplitudes(s, layout)
        axs[1].plot(np.arange(1, len(center) + 1), center, "o-", ms=3, label=f"B0={b0} Hz")
    axs[1].set_xlabel("echo #"); axs[1].set_ylabel("|signal| at k-space center sample")
    axs[1].set_title(f"B0 sweep (B1={args.b1})"); axs[1].legend(fontsize=8)
    fig.tight_layout()

    if args.save:
        for n in plt.get_fignums():
            f = plt.figure(n)
            f.savefig(os.path.join(args.outdir, f"epg_{f.get_label().split()[0]}_{n}.png"), dpi=150)
    if plt.get_backend().lower() != "agg":
        plt.show()


if __name__ == "__main__":
    main()
