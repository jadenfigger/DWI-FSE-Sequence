"""
view_seq.py  -  Inspect a Pulseq .seq file with PyPulseq.

What it shows
  1. Summary: definitions, total duration, block count, PyPulseq test report
  2. RF table: time, use (excitation/refocusing), flip angle, phase of every RF pulse
  3. Sequence diagram (RF, ADC, Gx, Gy, Gz) for a chosen time window
  4. Gradient 0th moment between consecutive RF pulses (checks the CPMG condition)
  5. b-value at every ADC center for the main spin-echo pathway
  6. k-space trajectory for the chosen window

Usage
  python view_seq.py my_seq.seq                    # window = first excitation to second excitation
  python view_seq.py my_seq.seq --t0 0 --t1 0.05   # explicit window in seconds
  python view_seq.py my_seq.seq --no-report        # skip the (slow) full test report
  python view_seq.py my_seq.seq --save             # also save the figures as PNG

Requires: pip install pypulseq matplotlib numpy
"""
import argparse
import numpy as np
import matplotlib.pyplot as plt
import pypulseq as pp


# ---------------------------------------------------------------- RF events
def rf_events(seq):
    """Walk every block and return a list of dicts, one per RF pulse."""
    events, t_block = [], 0.0
    for idx in seq.block_events:
        b = seq.get_block(idx)
        if b.rf is not None:
            rf = b.rf
            dt = np.diff(rf.t, prepend=0.0)
            # flip angle = 2*pi * |integral of B1(t) in Hz|
            flip = 2 * np.pi * abs(np.sum(rf.signal * dt))
            events.append(dict(
                t_center=t_block + rf.delay + rf.center,
                flip_deg=np.degrees(flip),
                phase_deg=np.degrees(rf.phase_offset) % 360,
                use=getattr(rf, "use", "undefined"),
            ))
        t_block += b.block_duration
    return events


def default_window(rfs, total):
    exc = [e["t_center"] for e in rfs if e["use"] == "excitation" or e["flip_deg"] < 120]
    if not exc:
        return 0.0, total
    t0 = max(exc[0] - 2e-3, 0.0)
    t1 = exc[1] - 2e-3 if len(exc) > 1 else total
    return t0, t1


# --------------------------------------------------------- gradient sampling
def sample_gradients(seq, t0, t1, dt=1e-6):
    """Sample Gx, Gy, Gz (Hz/m) on a uniform grid between t0 and t1."""
    waves = seq.waveforms(time_range=[t0, t1])  # piecewise-linear [time; amp] per axis
    t = np.arange(t0, t1, dt)
    g = np.zeros((3, t.size))
    for ax in range(3):
        w = waves[ax]
        if w.size:
            g[ax] = np.interp(t, w[0], w[1], left=0.0, right=0.0)
    return t, g


def moments_between_rf(t, g, rf_times):
    """0th gradient moment (1/m) on each axis between consecutive RF centers."""
    dt = t[1] - t[0]
    rows = []
    edges = [t[0]] + list(rf_times) + [t[-1]]
    for a, b in zip(edges[:-1], edges[1:]):
        m = (t >= a) & (t < b)
        rows.append((a, b, g[:, m].sum(axis=1) * dt))
    return rows


def spin_echo_bvalue(t, g, rfs, adc_times):
    """b-value (s/mm^2) for the main spin-echo pathway, at each ADC center.

    Every refocusing pulse flips the sign of the phase accumulated so far,
    which is the same as flipping the sign of every gradient that came before it.
    So we use g_eff(t) = g(t) * (-1)^(number of refocusing pulses after t) up to
    the echo, then q(t) = 2*pi * integral g_eff, b = integral |q|^2 dt.
    NOTE: stimulated-echo pathways see a different b-value. Use the MRzero
    script for those.
    """
    dt = t[1] - t[0]
    exc = [e["t_center"] for e in rfs if e["use"] == "excitation" or e["flip_deg"] < 120]
    ref = [e["t_center"] for e in rfs if not (e["use"] == "excitation" or e["flip_deg"] < 120)]
    out = []
    for ta in adc_times:
        if ta < t[0] or ta > t[-1]:
            continue
        t_exc = max([x for x in exc if x < ta], default=None)
        if t_exc is None:
            continue
        sel = (t >= t_exc) & (t <= ta)
        tt, gg = t[sel], g[:, sel].copy()
        for tr in ref:
            if t_exc < tr < ta:
                gg[:, tt < tr] *= -1
        q = 2 * np.pi * np.cumsum(gg, axis=1) * dt          # rad/m
        b_axes = (q ** 2).sum(axis=1) * dt * 1e-6           # s/mm^2 per axis
        out.append((ta, b_axes, b_axes.sum()))
    return out


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seq_file")
    ap.add_argument("--t0", type=float, default=None, help="window start [s]")
    ap.add_argument("--t1", type=float, default=None, help="window end [s]")
    ap.add_argument("--no-report", action="store_true")
    ap.add_argument("--save", action="store_true", help="also save figures as PNG")
    args = ap.parse_args()

    seq = pp.Sequence()
    seq.read(args.seq_file)
    total = float(sum(seq.block_durations.values()))

    # 1. summary
    print("=" * 70)
    print(f"File: {args.seq_file}")
    print(f"Blocks: {len(seq.block_events)}   Total duration: {total:.4f} s")
    for k, v in seq.definitions.items():
        print(f"  {k}: {v}")
    ok, err = seq.check_timing()
    print(f"Timing check: {'OK' if ok else 'FAILED'}")
    if not ok:
        for e in err[:10]:
            print("   ", e)
    if not args.no_report:
        print(seq.test_report())

    # 2. RF table
    rfs = rf_events(seq)
    t0, t1 = default_window(rfs, total)
    t0 = args.t0 if args.t0 is not None else t0
    t1 = args.t1 if args.t1 is not None else t1
    print("=" * 70)
    print(f"RF pulses in window {t0*1e3:.2f} to {t1*1e3:.2f} ms")
    print(f"{'#':>3} {'t [ms]':>9} {'dt prev [ms]':>13} {'flip [deg]':>11} {'phase [deg]':>12}  use")
    prev = None
    win = [e for e in rfs if t0 <= e["t_center"] <= t1]
    for i, e in enumerate(win):
        d = "" if prev is None else f"{(e['t_center'] - prev)*1e3:.3f}"
        print(f"{i:>3} {e['t_center']*1e3:9.3f} {d:>13} {e['flip_deg']:11.1f} {e['phase_deg']:12.1f}  {e['use']}")
        prev = e["t_center"]

    # 3. gradient moments between RF pulses
    t, g = sample_gradients(seq, t0, t1)
    rf_c = [e["t_center"] for e in win]
    print("=" * 70)
    print("Gradient 0th moment between RF centers [cycles/m]  (Gx, Gy, Gz)")
    print("CPMG condition: every refocusing interval should have the SAME moment,")
    print("and excitation->1st refocusing should be HALF of that.")
    for a, b, m in moments_between_rf(t, g, rf_c):
        print(f"  {a*1e3:8.3f} -> {b*1e3:8.3f} ms : {m[0]:10.1f} {m[1]:10.1f} {m[2]:10.1f}")

    # 4. b-values
    adc_t = []
    t_block = 0.0
    for idx in seq.block_events:
        b = seq.get_block(idx)
        if b.adc is not None:
            adc_t.append(t_block + b.adc.delay + b.adc.num_samples * b.adc.dwell / 2)
        t_block += b.block_duration
    print("=" * 70)
    print("Spin-echo-pathway b-value at each ADC center [s/mm^2]  (bxx, byy, bzz | trace)")
    for ta, bax, btot in spin_echo_bvalue(t, g, rfs, adc_t):
        print(f"  ADC @ {ta*1e3:8.3f} ms : {bax[0]:9.1f} {bax[1]:9.1f} {bax[2]:9.1f} | {btot:9.1f}")

    # 5. sequence diagram
    seq.plot(time_range=(t0, t1), time_disp="ms", grad_disp="mT/m", plot_now=False)

    # 6. k-space trajectory for the window
    #    (spin-echo pathway: k resets to 0 at excitation, k -> -k at each refocusing)
    dt = t[1] - t[0]
    k = np.zeros_like(g)
    is_exc = {e["t_center"]: (e["use"] == "excitation" or e["flip_deg"] < 120) for e in win}
    rf_idx = {int(np.searchsorted(t, tc)): tc for tc in rf_c}
    for i in range(1, t.size):
        k[:, i] = k[:, i - 1] + g[:, i] * dt
        if i in rf_idx:
            k[:, i] = 0.0 if is_exc[rf_idx[i]] else -k[:, i]
    adc_samples = []
    t_block = 0.0
    for idx in seq.block_events:
        b = seq.get_block(idx)
        if b.adc is not None:
            ts = t_block + b.adc.delay + (np.arange(b.adc.num_samples) + 0.5) * b.adc.dwell
            adc_samples.append(ts[(ts >= t0) & (ts <= t1)])
        t_block += b.block_duration
    adc_samples = np.concatenate(adc_samples) if adc_samples else np.array([])
    ka = np.array([np.interp(adc_samples, t, k[ax]) for ax in range(3)])
    plt.figure("k-space")
    plt.plot(k[0], k[1], lw=0.5, label="trajectory")
    plt.plot(ka[0], ka[1], ".", ms=2, label="ADC samples")
    plt.xlabel("kx [1/m]"); plt.ylabel("ky [1/m]"); plt.legend()
    if ka.size:  # zoom to the sampled region (diffusion lobes go far outside it)
        span = max(np.ptp(ka[0]), np.ptp(ka[1]), 1.0)
        plt.xlim(ka[0].min() - 0.25 * span, ka[0].max() + 0.25 * span)
        plt.ylim(ka[1].min() - 0.25 * span, ka[1].max() + 0.25 * span)
    plt.title("k-space (window)")

    if args.save:
        for n in plt.get_fignums():
            plt.figure(n).savefig(f"view_seq_fig{n}.png", dpi=150)
    plt.show()


if __name__ == "__main__":
    main()
