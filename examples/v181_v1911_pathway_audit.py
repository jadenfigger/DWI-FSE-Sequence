"""Independent bounded instantaneous-RF pathway audit of mapped PPL events.

This additive tool does not use dwfse.pathways or its longitudinal diffusion
equation. RF/gradient/ADC input is the shared source ledger, not a console trace.
Finite slice profiles, diffusion during finite RF, motion and ETL > 8 are outside
the model. The finite-RF Bloch validator is an essential separate check.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.ledger import build_ledger, adc_middle_times
from dwfse.ppl.run import map_events
from dwfse.vendor_seq import decode

AXES = "SPR"
COHERENCE = np.array([1, -1, 0], dtype=np.int8)
LABELS = ("+", "-", "Z")
PAIRS = ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))
TWOPI2 = (2 * np.pi) ** 2


def _outer6(k):
    return np.stack([k[..., i] * k[..., j] for i, j in PAIRS], axis=-1)


def _cross6(k, j):
    return np.stack([k[..., a] * j[..., b] + j[..., a] * k[..., b]
                     for a, b in PAIRS], axis=-1)


def tensor_matrix(b):
    out = np.zeros((3, 3))
    for value, (i, j) in zip(b, PAIRS):
        out[i, j] = out[j, i] = float(value)
    return out.tolist()


def interval_stats(led, ta_us, tb_us, latency_us=0.0):
    """Exact area A, integral q dt J, integral q q^T dt Q (cycles/m).

    G is piecewise constant; q(t)=integral G dt is linear on each segment.
    Integrate the polynomial exactly, independent of sampled k_path/b_tensor.
    """
    if tb_us < ta_us:
        raise ValueError("interval end precedes start")
    cuts = {float(ta_us), float(tb_us)}
    for axis in AXES:
        t = led["G"][axis].t + latency_us
        cuts.update(t[(t > ta_us) & (t < tb_us)].tolist())
    cuts = sorted(cuts)
    q, j, qq = np.zeros(3), np.zeros(3), np.zeros(6)
    fac = led["H"] * 1e3 / 32767.0
    for a, b in zip(cuts[:-1], cuts[1:]):
        dt = (b - a) * 1e-6
        g = np.array([led["G"][ax].value_at((a+b)/2-latency_us)
                      for ax in AXES]) * fac
        dq = g * dt
        j += dt * (q + dq / 2)
        qq += dt * (_outer6(q) + _cross6(q, dq) / 2 + _outer6(dq) / 3)
        q += dq
    return {"dt_s": (tb_us-ta_us)*1e-6, "area_cycles_m": q,
            "int_q_dt": j, "int_qq_dt": qq}


def rf_transfer(angle, phase):
    """F+, F-, Z transfer for dM/dt=2pi(M cross B), m=Mx+iMy.

    These are physical transverse fields, with no sqrt(2) normalization.
    The Fourier exponent is exp(-i2pi*k.r) for all three fields.
    """
    c, s, sn = np.cos(angle/2)**2, np.sin(angle/2)**2, np.sin(angle)
    e = np.exp(1j * phase)
    return np.array([[c, e**2*s, 1j*e*sn],
                     [np.conjugate(e)**2*s, c, -1j*np.conjugate(e)*sn],
                     [.5j*np.conjugate(e)*sn, -.5j*e*sn, np.cos(angle)]])


def rf_calibration(it):
    stock = decode(ROOT / "scanner/utilities/rfstd44.seq").frame("3lobe_sinc_3kHz")
    area = np.sum(stock.samples) * stock.wait_ticks * .1e-6
    area *= float(it.vars["rfcal"].value) / 2047.0
    return .25 / area


def _reference_events(it, led, max_echoes=8, rf_reference_offsets_us=None):
    if len(led["adc"]) > max_echoes:
        raise ValueError(f"audit is bounded to {max_echoes} ADC-bearing echoes")
    offsets = rf_reference_offsets_us or {}
    events = []
    for i, rf in enumerate(led["rf"]):
        t = rf["t_center"] + offsets.get(rf["frame"], 0.0)
        events.append((float(t), "rf", i, rf))
    for i, (_, t) in enumerate(adc_middle_times(it, led)):
        events.append((float(t), "adc", i, led["adc"][i]))
    return sorted(events, key=lambda e: (e[0], e[1]))


def _history(code, count):
    digits = []
    for _ in range(count):
        code, d = divmod(int(code), 3)
        digits.append(LABELS[d])
    return " ".join(reversed(digits))


def analyze_pathways(it, led=None, *, b1=1.0, df_hz=0.0,
                     initial_phase_deg=0.0, diffusivity_mm2_s=.002,
                     T1_s=1.3, T2_s=.032, max_echoes=8,
                     grad_latency_us=None, rf_reference_offsets_us=None,
                     voxel_widths_m=None, top=12):
    """Enumerate all three RF branches without amplitude/path pruning.

    RF collapses to its signed-area flip at the supplied reference, default
    geometric sample center. Longitudinal spatial states retain k and diffuse.
    Return the complete coherent sum, and leading histories with their B.
    Per-path tensors, rather than one scalar effective b, describe low-angle FSE.
    """
    led = led or build_ledger(it, 1)
    if not led["rf"] or not led["adc"]:
        raise ValueError("need a complete RF and ADC-bearing shot")
    lat = float(it.vars["rfdelay"].value) if grad_latency_us is None else grad_latency_us
    # PPR effective FOV/no_views describes the modeled stationary box voxel;
    # this is not a measured point-spread function or a finite slice profile.
    widths = np.asarray(voxel_widths_m if voxel_widths_m is not None
                        else (1e-3, 35e-3/136, 35e-3/128), float)
    if widths.shape != (3,) or np.any(widths < 0):
        raise ValueError("voxel widths must be three nonnegative S/P/R values")
    events = _reference_events(it, led, max_echoes, rf_reference_offsets_us)
    if sum(e[1] == "rf" for e in events) > 13:
        raise ValueError("unpruned audit supports at most 13 RF events")
    typ = np.array([2], dtype=np.int8)
    mag = np.array([1.0+0j])  # RF/relaxation/B0 coefficient; diffusion applied at ADC
    k = np.zeros((1, 3))
    bt = np.zeros((1, 6))
    hist = np.zeros(1, dtype=np.int64)
    origin = np.zeros(1, dtype=np.int16)
    nrfs = 0
    previous = events[0][0]
    cal = rf_calibration(it)
    echoes, rf_report = [], []
    for t, kind, index, ev in events:
        stats = interval_stats(led, previous, t, lat)
        dt, a, j, q = (stats[x] for x in ("dt_s", "area_cycles_m", "int_q_dt", "int_qq_dt"))
        coherence = COHERENCE[typ]
        increment = dt * _outer6(k) + coherence[:, None] * _cross6(k, j)
        increment += (coherence != 0)[:, None] * q
        bt += TWOPI2 * 1e-6 * increment
        k += coherence[:, None] * a
        if df_hz:
            mag *= np.exp(-2j*np.pi*df_hz*coherence*dt)
        if T1_s is not None or T2_s is not None:
            r1 = np.exp(-dt/T1_s) if T1_s else 1.0
            r2 = np.exp(-dt/T2_s) if T2_s else 1.0
            mag *= np.where(coherence == 0, r1, r2)
            if T1_s and dt > 0:
                # Recovery is a new uniform Z0 lineage with no prior b.
                typ = np.append(typ, 2)
                mag = np.append(mag, 1-r1)
                k = np.vstack((k, np.zeros(3)))
                bt = np.vstack((bt, np.zeros(6)))
                hist = np.append(hist, 0)
                origin = np.append(origin, nrfs)
        previous = t
        if kind == "rf":
            angle = 2*np.pi*cal*np.sum(ev["amp"])*ev["dt"]*1e-6*b1
            phase = np.deg2rad(ev["phase_deg"] + (initial_phase_deg if nrfs == 0 else 0))
            matrix = rf_transfer(angle, phase)
            n = len(typ)
            mag = (mag[:, None] * matrix[:, typ].T).reshape(-1)
            typ = np.tile(np.arange(3, dtype=np.int8), n)
            k = np.repeat(k, 3, axis=0)
            bt = np.repeat(bt, 3, axis=0)
            hist = (hist[:, None]*3 + np.arange(3)).reshape(-1)
            origin = np.repeat(origin, 3)
            nrfs += 1
            rf_report.append({"rf": index+1, "frame": ev["frame"], "reference_us": t,
                              "flip_deg": float(np.rad2deg(angle)),
                              "phase_deg": float(np.rad2deg(phase))})
            continue
        use = np.flatnonzero(typ == 0)
        btrace = bt[use, :3].sum(axis=1)
        box = np.prod(np.sinc(k[use]*widths), axis=1)
        attenuation = np.exp(-diffusivity_mm2_s*btrace)
        receive = np.exp(1j*np.deg2rad(ev["rx_phase_deg"]))
        no_diff = mag[use] * box * receive
        values = no_diff * attenuation
        total, total0 = values.sum(), no_diff.sum()
        l1 = float(np.abs(values).sum())
        strongest = np.argsort(np.abs(values))[-top:][::-1] if top > 0 else []
        paths = []
        for pos in strongest:
            state = use[pos]
            count = nrfs-int(origin[state])
            paths.append({"origin_after_rf": int(origin[state]),
                          "history": _history(hist[state], count),
                          "signal_real_imag": [float(values[pos].real), float(values[pos].imag)],
                          "signal_no_diff_abs": float(abs(no_diff[pos])),
                          "k_cycles_m": k[state].tolist(),
                          "b_tensor_s_mm2": tensor_matrix(bt[state]),
                          "b_trace_s_mm2": float(btrace[pos]),
                          "diffusion_attenuation": float(attenuation[pos])})
        echoes.append({"echo": index+1, "time_us": t,
                       "rf_count": nrfs, "transverse_history_count": len(use),
                       "signal_real_imag": [float(total.real), float(total.imag)],
                       "signal_abs": float(abs(total)),
                       "signal_no_diff_abs": float(abs(total0)),
                       "diffusion_signal_ratio": float(abs(total)/abs(total0)) if total0 else None,
                       "l1_amplitude": l1,
                       "coherent_over_l1": float(abs(total)/l1) if l1 else None,
                       "top_paths": paths})
    return {"model": "unpruned instantaneous-RF three-state Fourier pathways; exact PWC gradient integration",
            "limitations": ["shared source ledger, no vendor execution", "RF signed-area rotations, no finite slice profile",
                            "finite-RF diffusion/motion excluded", "bounded to eight imaging echoes",
                            "stationary centered box voxel, not a PSF", "inferred rfcal linear transmit model"],
            "inputs": it.inputs, "settings": {"b1": b1, "df_hz": df_hz,
                      "initial_phase_deg": initial_phase_deg, "diffusivity_mm2_s": diffusivity_mm2_s,
                      "T1_s": T1_s, "T2_s": T2_s, "grad_latency_us": lat,
                      "rf_reference_offsets_us": rf_reference_offsets_us or {},
                      "voxel_widths_m_SPR": widths.tolist()},
            "rf": rf_report, "echoes": echoes}


def _train_boundaries(it, led, finite_rf=False):
    """First interval begins at re-excitation endpoint; repeated ones at ADC.

    Returns fixed logical ordering despite a changed absolute train timeline.
    Selector gradients are intentionally allowed during selective RF.
    """
    rfs = led["rf"]
    train = [r for r in rfs if r["frame"] == "v19_imaging180"]
    if not train:  # conventional v18: diffusion-prep 180 also forms ADC1
        train = rfs[1:]
    adc = [t for _, t in adc_middle_times(it, led)]
    if len(train) != len(adc):
        raise ValueError("train RF/ADC count mismatch")
    first_i = rfs.index(train[0])
    previous_rf = rfs[first_i-1]
    start = previous_rf["t_go"]+previous_rf["duration_us"] if finite_rf else previous_rf["t_center"]
    out = []
    for i, (rf, tc) in enumerate(zip(train, adc)):
        before = rf["t_go"] if finite_rf else rf["t_center"]
        after = rf["t_go"]+rf["duration_us"] if finite_rf else rf["t_center"]
        out.append((f"pre_RF{i+1}" if i == 0 else f"ADC{i}_to_RF{i+1}", start, before))
        out.append((f"RF{i+1}_to_ADC{i+1}", after, tc))
        start = tc
    return out, train


def _rf_waveform_difference(led0, led1, rf0, rf1, lat0, lat1):
    """Maximum selector difference on corresponding RF-relative intervals."""
    duration = min(rf0["duration_us"], rf1["duration_us"])
    cuts = {0., float(duration)}
    for led, rf, lat in ((led0, rf0, lat0), (led1, rf1, lat1)):
        for ax in AXES:
            relative = led["G"][ax].t+lat-rf["t_go"]
            cuts.update(relative[(relative > 0) & (relative < duration)].tolist())
    times = (np.asarray(sorted(cuts))[:-1]+np.asarray(sorted(cuts))[1:])/2
    differences = {}
    for ax in AXES:
        g0 = led0["G"][ax].sample(times+rf0["t_go"]-lat0)
        g1 = led1["G"][ax].sample(times+rf1["t_go"]-lat1)
        differences[ax] = float(np.max(np.abs(g1-g0), initial=0))
    return differences


def crusher_ratios(it, led=None):
    """Area ratios from decoded initial D and prep crusher shapes.

    After fusion no named standalone C lobe need exist: retained C is recovered
    from each interval sum after subtracting D and the RF-time selector terms.
    This helper reports baseline area parameters; compare_train_intervals proves
    their physical interval realization rather than trusting parameter names.
    """
    from dwfse.ppl.ledger import list_starts, list_duration_us
    led = led or build_ledger(it, 1)
    if "v19_l_d" not in it.vars:
        return {"available": False, "reason": "conventional sequence has no MGOT D lobe"}
    starts = list_starts(it, led, "v19_l_d")
    if not starts:
        return {"available": False}
    td = starts[0][0]
    dur = list_duration_us(it, "v19_l_d")
    d_dac_us = led["G"]["S"].integral(td, td+dur)
    d_amplitude = float(it.vars["v19_d_dac"].value)
    sec_ramp_area_us = d_dac_us/d_amplitude-float(it.vars["tdp"].value)
    c = float(it.vars["crusher_saved_train"].value)*(float(it.vars["tcrush"].value)+sec_ramp_area_us)
    c1 = float(it.vars["crusher_saved_first"].value)*(float(it.vars["diff_tcrush"].value)+sec_ramp_area_us)
    ratios = abs(c/d_dac_us), abs(c1/d_dac_us)
    return {"available": True, "D_DAC_us": d_dac_us,
            "C_DAC_us": c, "C1_DAC_us": c1,
            "decoded_secondary_ramp_equivalent_us": sec_ramp_area_us,
            "C_over_D": ratios[0], "C1_over_D": ratios[1],
            "within_existing_validated_windows": bool(3.81 <= ratios[0] <= 3.85 and 2.53 <= ratios[1] <= 2.57)}


def train_overlap_and_envelope(it, led=None, baseline_it=None, baseline_led=None,
                               grad_latency_us=None):
    """Full ADC-open slice check and summed-axis inherited demands.

    RF-time fused-lobe absence is proved by compare_train_intervals' complete
    RF-time waveform identity, rather than incorrectly rejecting the selector.
    Native-axis certification is only meaningful for the locked zero-orientation
    candidate. The source calibration and discrete raster are not analog tests.
    """
    led = led or build_ledger(it, 1)
    lat = float(it.vars["rfdelay"].value) if grad_latency_us is None else grad_latency_us
    rows = []
    s = led["G"]["S"]
    for i, adc in enumerate(led["adc"]):
        lo, hi = adc["t_init"]-lat, adc["t_complete"]-lat
        use = (s.t[:-1] < hi) & (s.t[1:] > lo)
        peak = float(np.max(np.abs(s.v[use]), initial=0.))
        area = s.integral(lo, hi)
        rows.append({"echo": i+1, "ADC_full_open_us": [adc["t_init"], adc["t_complete"]],
                     "physical_slice_gradient_peak_DAC_during_ADC": peak,
                     "physical_slice_gradient_area_DAC_us_during_ADC": area})

    def demands(x):
        out = {}
        for ax in AXES:
            w = x["G"][ax]
            use = (w.t[:-1] < x["t_end"]) & (w.t[1:] > x["t_start"])
            peak = float(np.max(np.abs(w.v[use]), initial=0.))
            # Compare identical vendor raster / inherited ramps. A sample
            # difference is not a measurement of analog amplifier slew.
            changes = np.diff(w.v)
            dt = np.diff(w.t[:-1])
            choose = use[1:] & (dt > 1e-10)
            slew = float(np.max(np.abs(changes[choose])/dt[choose], initial=0.))
            out[ax] = {"peak_summed_axis_DAC": peak, "raster_step_DAC_per_us": slew}
        return out

    current = demands(led)
    base = None
    within = None
    if baseline_it is not None or baseline_led is not None:
        base = demands(baseline_led or build_ledger(baseline_it, 1))
        within = all(current[a][metric] <= base[a][metric]+1e-7
                     for a in AXES for metric in current[a])
    return {"full_ADC_open_windows": rows,
            "slice_zero_through_all_full_ADC_open_windows": all(r["physical_slice_gradient_peak_DAC_during_ADC"] < 1e-9 for r in rows),
            "current_demands": current, "baseline_demands": base,
            "all_axes_within_inherited_peak_and_raster_step": within,
            "qualification": "Summed source logical/native demands at locked zero orientation; actual physical calibration, analog slew and simultaneous-axis amplifier capability remain scanner-verify"}


def compare_train_intervals(before_it, after_it, *, before_led=None, after_led=None,
                            grad_latency_us=None, tolerance_cycles_slice=.005,
                            slice_width_m=.001, voxel_widths_m=None):
    """All-history endpoint proof in instantaneous and finite-RF boundaries.

    Equal RF maps plus equal free-interval moments imply every RF history keeps
    the same gradient endpoint (Z states ignore gradients). This proves endpoint
    phase, not diffusion/relaxation equality; EPG loss is assessed separately.
    """
    b0, b1 = before_led or build_ledger(before_it, 1), after_led or build_ledger(after_it, 1)
    lat0 = float(before_it.vars["rfdelay"].value) if grad_latency_us is None else grad_latency_us
    lat1 = float(after_it.vars["rfdelay"].value) if grad_latency_us is None else grad_latency_us
    widths = np.array(voxel_widths_m if voxel_widths_m is not None
                      else (slice_width_m, 35e-3/136, 35e-3/128))
    reports = {}
    for finite in (False, True):
        boundaries0, train0 = _train_boundaries(before_it, b0, finite)
        boundaries1, train1 = _train_boundaries(after_it, b1, finite)
        if [x[0] for x in boundaries0] != [x[0] for x in boundaries1]:
            raise ValueError("baseline/candidate RF/ADC train boundary mismatch")
        rows = []
        for (name, a0, z0), (_, a1, z1) in zip(boundaries0, boundaries1):
            area0 = interval_stats(b0, a0, z0, lat0)["area_cycles_m"]
            area1 = interval_stats(b1, a1, z1, lat1)["area_cycles_m"]
            delta = area1-area0
            rows.append({"interval": name, "before_us": [a0, z0], "after_us": [a1, z1],
                         "before_cycles_m_SPR": area0.tolist(),
                         "after_cycles_m_SPR": area1.tolist(),
                         "delta_cycles_m_SPR": delta.tolist(),
                         "delta_cycles_across_voxel_SPR": (delta*widths).tolist(),
                         "delta_cycles_across_slice": float(delta[0]*slice_width_m)})
        reports["finite_RF_edges" if finite else "instantaneous_RF_centers"] = rows
    rf_difference = [_rf_waveform_difference(b0, b1, r0, r1, lat0, lat1)
                     for r0, r1 in zip(train0, train1)]
    rf_identity = all(r0["frame"] == r1["frame"] and r0["phase_units"] == r1["phase_units"]
                      and r0["mul"] == r1["mul"] and np.array_equal(r0["amp"], r1["amp"])
                      and r0["dt"] == r1["dt"] for r0, r1 in zip(train0, train1))
    maximum = max(abs(r["delta_cycles_across_slice"]) for rs in reports.values() for r in rs)
    maximum_all_axes = max(abs(v) for rs in reports.values() for r in rs
                           for v in r["delta_cycles_across_voxel_SPR"])
    # Explicitly enumerate endpoint ERROR histories independently of the signal
    # model. Starting with each possible incoming coherence proves every train
    # history, not only the desired carrier. This accumulates DAC-rounding
    # residuals; passing each interval separately is insufficient by itself.
    error_k = np.zeros((3, 3))
    error_type = np.arange(3, dtype=np.int8)
    error_echoes = []
    edges = reports["finite_RF_edges"]
    for i in range(len(train0)):
        pre, post = edges[2*i:2*i+2]
        error_k += COHERENCE[error_type, None]*np.array(pre["delta_cycles_m_SPR"])
        n = len(error_type)
        error_k = np.repeat(error_k, 3, axis=0)
        error_type = np.tile(np.arange(3, dtype=np.int8), n)
        error_k += COHERENCE[error_type, None]*np.array(post["delta_cycles_m_SPR"])
        observable = error_k[error_type == 0]
        maxima = np.max(np.abs(observable*widths), axis=0)
        error_echoes.append({"echo": i+1, "observable_history_count": len(observable),
                             "maximum_abs_error_cycles_voxel_SPR": maxima.tolist()})
    max_history = max(v for row in error_echoes for v in row["maximum_abs_error_cycles_voxel_SPR"])
    max_gradient = max(v for row in rf_difference for v in row.values())
    return {"inputs": {"before": before_it.inputs, "after": after_it.inputs},
            "proof_scope": "all train coherence histories given identical incoming preparation state: interval endpoint gradient area only; RF maps identical",
            "preparation_state_identity": "premise requiring separate source/event comparison",
            "tolerance_cycles_across_slice": tolerance_cycles_slice,
            "maximum_abs_slice_area_error_cycles_slice": maximum,
            "exact_slice_area_identity": bool(maximum < 1e-10),
            "slice_area_within_tolerance": bool(maximum <= tolerance_cycles_slice),
            "maximum_abs_all_axis_area_error_cycles_voxel": maximum_all_axes,
            "all_axis_area_within_tolerance": bool(maximum_all_axes <= tolerance_cycles_slice),
            "all_history_accumulated_endpoint_errors": error_echoes,
            "maximum_abs_history_endpoint_error_cycles_voxel": max_history,
            "rf_samples_phase_multiplier_identical": bool(rf_identity),
            "RF_time_gradient_max_abs_difference_DAC": max_gradient,
            "RF_time_gradient_differences_DAC_by_echo_SPR": rf_difference,
            "all_history_area_contract_within_tolerance": bool(max_history <= tolerance_cycles_slice and rf_identity and max_gradient < 1e-8),
            "intervals": reports,
            "overlap_and_inherited_envelope": train_overlap_and_envelope(after_it, b1, before_it, b0, grad_latency_us),
            "crusher_ratios_before": crusher_ratios(before_it, b0),
            "crusher_ratios_after": crusher_ratios(after_it, b1)}


def self_checks():
    """Independent physical oracles: RF rotation, diffusion PDE, exact b."""
    # RF matrix checked against Rodrigues in real Cartesian coordinates.
    worst = 0.
    rng = np.random.default_rng(881911)
    for _ in range(20):
        m = rng.normal(size=3)
        angle, phase = rng.uniform(-4, 4), rng.uniform(-np.pi, np.pi)
        axis = np.array([np.cos(phase), np.sin(phase), 0.])
        cart = m*np.cos(angle)-np.cross(axis, m)*np.sin(angle)+axis*np.dot(axis, m)*(1-np.cos(angle))
        physical = np.array([m[0]+1j*m[1], m[0]-1j*m[1], m[2]])
        expected = np.array([cart[0]+1j*cart[1], cart[0]-1j*cart[1], cart[2]])
        worst = max(worst, float(np.max(np.abs(rf_transfer(angle, phase)@physical-expected))))
    # Heat equation on a periodic 1/k domain: central-difference spatial
    # Laplacian eigenvalue, solved with a discrete time recurrence. Neither the
    # pathway b tensor nor its longitudinal update is used in this PDE oracle.
    wave_k, d_si, duration = 20000., 2e-9, .05
    exact = np.exp(-d_si*(2*np.pi*wave_k)**2*duration)
    pde_rows = []
    for n in (128, 256, 512):
        dx = 1/wave_k/n
        dt = .2*dx**2/d_si
        steps = int(np.ceil(duration/dt))
        dt = duration/steps
        x = np.arange(n)*dx
        u = np.cos(2*np.pi*wave_k*x)
        for _ in range(steps):
            u += d_si*dt/dx**2*(np.roll(u, 1)-2*u+np.roll(u, -1))
        amplitude = 2*np.mean(u*np.cos(2*np.pi*wave_k*x))
        pde_rows.append({"grid_points": n, "steps": steps,
                         "amplitude": float(amplitude), "absolute_error": float(abs(amplitude-exact))})
    from dwfse.ppl.events import PWC
    # Constant vector gradient, zero initial k: B=(2pi)^2 ggT*t^3/3.
    led = {"H": 32767./1e3, "G": {a: PWC(np.array([0., 1000.]), np.array([v]))
                                      for a, v in zip(AXES, (100., -20., 30.))}}
    stats = interval_stats(led, 0., 1000.)
    analytical = _outer6(np.array([100., -20., 30.]))*.001**3/3
    b_error = float(np.max(np.abs(stats["int_qq_dt"]-analytical)))
    # A stored Fourier state has no dk but the same physical nonzero decay.
    z_b = TWOPI2*wave_k**2*duration*1e-6
    z_attenuation = np.exp(-.002*z_b)
    passed = bool(worst < 1e-12 and b_error < 1e-15 and
                  abs(z_attenuation-exact) < 1e-14 and pde_rows[-1]["absolute_error"] < 2e-6)
    if not passed:
        raise AssertionError("independent physical oracle failed")
    return {"passed": passed, "RF_vs_Cartesian_Rodrigues_max_error": worst,
            "constant_gradient_exact_integral_max_error": b_error,
            "encoded_Z_diffusion_heat_equation": {"k_cycles_m": wave_k,
              "D_mm2_s": .002, "duration_s": duration, "analytic_amplitude": float(exact),
              "pathway_attenuation": float(z_attenuation), "PDE_refinement": pde_rows,
              "missing_2pi_expression_amplitude": float(np.exp(-d_si*wave_k**2*duration))}}


def parameter_sweep(before_it, after_it, *, diffusivity_mm2_s=.002, T1_s=1.3, T2_s=.032):
    """Required 36 B1/B0/initial-phase cases, with compact echo records."""
    led0, led1 = build_ledger(before_it, 1), build_ledger(after_it, 1)
    rows = []
    for b1 in (.8, .9, 1., 1.1):
        for b0 in (-128., 0., 128.):
            for phase in (0., 45., 90.):
                records = [analyze_pathways(it, led, b1=b1, df_hz=b0,
                          initial_phase_deg=phase, diffusivity_mm2_s=diffusivity_mm2_s,
                          T1_s=T1_s, T2_s=T2_s, top=0)
                           for it, led in ((before_it, led0), (after_it, led1))]
                echoes = []
                for a, b in zip(records[0]["echoes"], records[1]["echoes"]):
                    echoes.append({"echo": a["echo"],
                      "before_signal_abs": a["signal_abs"], "after_signal_abs": b["signal_abs"],
                      "after_over_before": b["signal_abs"]/a["signal_abs"] if a["signal_abs"] else None,
                      "before_diffusion_ratio": a["diffusion_signal_ratio"],
                      "after_diffusion_ratio": b["diffusion_signal_ratio"]})
                rows.append({"b1": b1, "b0_hz": b0, "phase_deg": phase, "echoes": echoes})
    return {"inputs": {"before": before_it.inputs, "after": after_it.inputs},
            "scope": "instantaneous-RF source model; no finite slice profile; D in mm2/s",
            "diffusivity_mm2_s": diffusivity_mm2_s, "T1_s": T1_s, "T2_s": T2_s,
            "minimum_after_over_before": min(e["after_over_before"] for r in rows for e in r["echoes"]),
            "rows": rows}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", type=Path)
    ap.add_argument("--before-ppr", type=Path)
    ap.add_argument("--after", type=Path)
    ap.add_argument("--after-ppr", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--sweep", action="store_true", help="36-case B1/B0/phase comparison")
    ap.add_argument("--b1", type=float, default=1.)
    ap.add_argument("--b0", type=float, default=0.)
    ap.add_argument("--phase", type=float, default=0.)
    ap.add_argument("--D", type=float, default=.002, help="diffusivity mm^2/s")
    ap.add_argument("--no-relaxation", action="store_true")
    args = ap.parse_args(argv)
    result = {"self_checks": self_checks()}
    mapped = {}
    for label in ("before", "after"):
        ppl = getattr(args, label)
        if ppl:
            ppr = getattr(args, label+"_ppr") or ppl.with_suffix(".ppr")
            mapped[label] = map_events(ppl, ppr, max_shots=1, expr_costs=True, expr_scale=.8)
            result[label] = analyze_pathways(mapped[label], b1=args.b1, df_hz=args.b0,
                                            initial_phase_deg=args.phase, diffusivity_mm2_s=args.D,
                                            T1_s=None if args.no_relaxation else 1.3,
                                            T2_s=None if args.no_relaxation else .032)
    if len(mapped) == 2:
        result["interval_area_comparison"] = compare_train_intervals(mapped["before"], mapped["after"])
        if args.sweep:
            result["parameter_sweep"] = parameter_sweep(mapped["before"], mapped["after"],
                 diffusivity_mm2_s=args.D, T1_s=None if args.no_relaxation else 1.3,
                 T2_s=None if args.no_relaxation else .032)
    payload = json.dumps(result, indent=2)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload)
        print(str(args.out))
    else:
        print(payload)


if __name__ == "__main__":
    main()
